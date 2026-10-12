"""Deadline-bounded, neural-led candidate comparison over the existing transport.

The caller MUST configure KataGo reportAnalysisWinratesAs = BLACK. Every child
uses one visit and its rootInfo.winrate, normalized to the original player.
scoreLead breaks exact winrate ties only when every candidate supplies a finite
scoreLead. Otherwise stable nomination order (neural policy first) breaks ties.
Specialists nominate moves; their scores are never mixed into neural values.

No background work is created here. KataGo.request owns query cancellation and
draining. A proposer must honor its absolute deadline; an overrun is rejected
and measured, but a synchronous Python callback cannot be forcibly preempted.
"""
import copy
import math
import time

from lab import COLUMNS, Referee
from neural import make_query, vertex


VARIANTS = ('policy', 'neural', 'heuristic', 'tactical', 'combined')


class DecisionError(RuntimeError):
    """No usable root result, invalid input/result, or operational failure."""

    def __init__(self, message, trace):
        super().__init__(message)
        self.trace = trace


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


def _move(value, size):
    if not isinstance(value, str):
        raise ValueError('move must be a vertex string')
    if value.lower() == 'pass':
        return 'pass'
    if len(value) < 2 or value[0].upper() not in COLUMNS[:size]:
        raise ValueError('invalid move column')
    if not value[1:].isascii() or not value[1:].isdigit():
        raise ValueError('invalid move row')
    row = int(value[1:])
    if not 1 <= row <= size or value[1:] != str(row):
        raise ValueError('invalid move row')
    return value[0].upper() + str(row)


def _child(ref, color, move):
    # Board cells and the board tuples in seen are immutable. Copy their mutable
    # containers, preserving every historical position without recursively
    # visiting size**2 cells for each one. Each branch owns its board and seen
    # set; a board-only copy would silently lose positional superko.
    child = Referee(ref.size, ref.komi)
    child.board = ref.board.copy()
    child.seen = ref.seen.copy()
    child.passes = ref.passes
    child.play(color, move)
    return child


def _terminal(ref, color):
    black_score = ref.margin()
    score = black_score if color == 'B' else -black_score
    return {'winrate': 1.0 if score > 0 else 0.0 if score < 0 else 0.5,
            'score': score, 'black_score': black_score, 'exact': True}


def _value(response, expected_player, root_color):
    root = response['rootInfo']
    if root['currentPlayer'] != expected_player:
        raise ValueError('neural currentPlayer mismatch')
    winrate = _number(root['winrate'], 'winrate')
    if not 0 <= winrate <= 1:
        raise ValueError('winrate outside [0, 1]')
    score = None
    if 'scoreLead' in root:
        score = _number(root['scoreLead'], 'scoreLead')
    return {'winrate': winrate if root_color == 'B' else 1 - winrate,
            'score': score if root_color == 'B' or score is None else -score,
            'exact': False}


def choose(kata, moves, color, size, komi, time_ms, variant='neural',
           proposer=None, identifier='neural-led', clock=time.perf_counter,
           cancelled=None):
    """Return (move, trace) without modifying the game or caller's history.

    proposer(moves=..., color=..., size=..., komi=..., deadline=..., variant=...)
    returns a dict with heuristic/tactical lists and optional metadata. Up to
    two additional legal moves per selected specialist join the top three legal
    neural candidates. Pass is a normal legal candidate, not a forced addition.

    A failed root raises DecisionError. After a usable root, budget exhaustion
    or cooperative cancellation returns it. Invalid transport/model/proposer
    output raises DecisionError rather than disguising it as a timed fallback.
    Already terminal roots return (None, trace) and exact TT scoring, no query.
    Partial candidate values remain in trace but never affect the returned move.
    After an opponent pass, retain a policy-recommended pass without comparing
    an exact terminal loss to uncertain positive continuation values.
    """
    started = clock()
    trace = {'variant': variant, 'identifier': str(identifier), 'status': 'initializing',
             'report_perspective': 'BLACK', 'value_objective': 'root_player_winrate',
             'completed_rounds': 0, 'fallback': False, 'fallback_reason': None,
             'root_move': None, 'selected_move': None, 'candidates': [],
             'rejected': [], 'queries': [], 'root_ms': 0.0, 'nomination_ms': 0.0,
             'evaluation_ms': 0.0, 'policy_rank': None, 'pass_agreement': False}
    deadline = None

    def finish(move, status, reason=None):
        now = clock()
        if status in ('evaluated', 'pass_agreement') and now >= deadline:
            # Selection/telemetry work also belongs to the wall allowance.
            # Even a fully received round cannot replace the retained root if
            # the final decision boundary has already expired.
            move, status, reason = trace['root_move'], 'fallback', 'deadline'
            trace.update(completed_rounds=0, policy_rank=1, pass_agreement=False)
        trace.update(status=status, selected_move=move,
                     ms=(now - started) * 1000,
                     overshoot_ms=max(0.0, (now - deadline) * 1000) if deadline else 0.0)
        if reason:
            trace.update(fallback=True, fallback_reason=reason)
        return move, trace

    def stopped():
        if cancelled is not None and cancelled():
            return 'cancelled'
        return 'deadline' if clock() >= deadline else None

    def query(history, player, suffix):
        reason = stopped()
        if reason:
            raise TimeoutError(reason)
        request = make_query(f'{identifier}-{suffix}', copy.deepcopy(history), player,
                             size, komi, 'policy')
        reason = stopped()
        if reason:
            raise TimeoutError(reason)
        row = {'id': request['id'], 'player': player, 'move_count': len(history)}
        trace['queries'].append(row)
        query_started = clock()
        try:
            response = kata.request(request, deadline=deadline)
            row['rootInfo'] = copy.deepcopy(response.get('rootInfo'))
            reason = stopped()
            if reason:
                row['status'] = 'late' if reason == 'deadline' else reason
                raise TimeoutError(reason)
            if response.get('isDuringSearch') or response.get('_used_intermediate'):
                raise ValueError('intermediate response cannot complete evaluation')
            if response.get('id', request['id']) != request['id']:
                raise ValueError('neural response id mismatch')
            if 'error' in response or 'warning' in response:
                raise ValueError('neural response rejected or altered query')
            row['status'] = 'complete'
            return response
        except TimeoutError:
            row.setdefault('status', 'timeout')
            raise
        except Exception as exc:
            row.update(status='invalid', error=repr(exc))
            raise
        finally:
            row['ms'] = (clock() - query_started) * 1000

    try:
        if variant not in VARIANTS:
            raise ValueError('unknown neural-led variant')
        if color not in ('B', 'W'):
            raise ValueError('color must be B or W')
        if isinstance(size, bool) or not isinstance(size, int) or not 2 <= size <= len(COLUMNS):
            raise ValueError('invalid board size')
        _number(komi, 'komi')
        if _number(time_ms, 'time_ms') <= 0:
            raise ValueError('time_ms must be positive')
        deadline = started + time_ms / 1000
        trace['time_ms'] = time_ms
        if not isinstance(moves, (list, tuple)):
            raise ValueError('moves must be a sequence')
        history = []
        ref = Referee(size, komi)
        for entry in moves:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2 or entry[0] not in ('B', 'W'):
                raise ValueError('invalid history entry')
            if ref.passes >= 2:
                raise ValueError('history continues after two passes')
            move = _move(entry[1], size)
            ref.play(entry[0], move)
            history.append([entry[0], move])
        if history and history[-1][0] == color:
            raise ValueError('last move must belong to opponent')
        if stopped():
            raise TimeoutError('root unavailable: ' + stopped())
        if ref.passes >= 2:
            trace['terminal'] = _terminal(ref, color)
            return finish(None, 'terminal')

        root_started = clock()
        try:
            response = query(history, color, 'root')
            if response['rootInfo']['currentPlayer'] != color:
                raise ValueError('root currentPlayer mismatch')
            policy = response['policy']
            if not isinstance(policy, list) or len(policy) != size * size + 1:
                raise ValueError('invalid policy length')
            for probability in policy:
                _number(probability, 'policy probability')
                if not (probability == -1 or 0 <= probability <= 1):
                    raise ValueError('invalid policy probability')
            ranked = sorted((i for i, p in enumerate(policy) if p >= 0),
                            key=lambda i: -policy[i])
            if not ranked or policy[ranked[0]] <= 0:
                raise ValueError('policy has no positive legal probability')
            root_move = vertex(ranked[0], size)
            _child(ref, color, root_move)  # Disagreement invalidates the baseline.
            if stopped():
                raise TimeoutError('root result processing exceeded budget')
            trace['root_move'] = root_move
            trace['root_info'] = copy.deepcopy(response['rootInfo'])
            ranks = {vertex(index, size): rank + 1 for rank, index in enumerate(ranked)}
            probabilities = {vertex(index, size): policy[index] for index in ranked}
            trace['policy_rank'] = 1
        finally:
            trace['root_ms'] = (clock() - root_started) * 1000

        if variant == 'policy':
            return finish(root_move, 'policy')

        if ref.passes == 1 and root_move == 'pass':
            trace['agreed_terminal'] = _terminal(_child(ref, color, 'pass'), color)
            reason = stopped()
            if reason:
                return finish(root_move, 'fallback', reason)
            trace['pass_agreement'] = True
            return finish('pass', 'pass_agreement')

        children = {}

        def nominate(raw, source):
            try:
                move = _move(raw, size)
                if move in children:
                    row = next(row for row in trace['candidates'] if row['move'] == move)
                    if source not in row['sources']:
                        row['sources'].append(source)
                    return False
                child = _child(ref, color, move)
            except (ValueError, AssertionError, TypeError) as exc:
                trace['rejected'].append({'move': repr(raw), 'source': source, 'reason': str(exc)})
                return False
            children[move] = child
            trace['candidates'].append({'move': move, 'sources': [source],
                                        'policy_rank': ranks.get(move),
                                        'policy_probability': probabilities.get(move),
                                        'status': 'unevaluated'})
            return True

        nomination_started = clock()
        try:
            for index in ranked:
                if stopped():
                    return finish(root_move, 'fallback', stopped())
                nominate(vertex(index, size), 'neural')
                if len(children) == 3:
                    break
            specialist_sources = {'neural': (), 'heuristic': ('heuristic',),
                                  'tactical': ('tactical',),
                                  'combined': ('heuristic', 'tactical')}[variant]
            if specialist_sources:
                if proposer is None:
                    raise ValueError('specialist variant requires proposer')
                if stopped():
                    return finish(root_move, 'fallback', stopped())
                proposed = proposer(moves=copy.deepcopy(history), color=color, size=size,
                                    komi=komi, deadline=deadline, variant=variant)
                trace['proposals'] = copy.deepcopy(proposed)
                if stopped():
                    return finish(root_move, 'fallback', stopped())
                if not isinstance(proposed, dict):
                    raise ValueError('proposer must return a dictionary')
                for source in specialist_sources:
                    nominees = proposed.get(source, [])
                    if not isinstance(nominees, (list, tuple)):
                        raise ValueError('specialist nominees must be a sequence')
                    added = 0
                    for raw in nominees:
                        if stopped():
                            return finish(root_move, 'fallback', stopped())
                        added += nominate(raw, source)
                        if added == 2:
                            break
        except TimeoutError:
            return finish(root_move, 'fallback', stopped() or 'nomination_timeout')
        finally:
            trace['nomination_ms'] = (clock() - nomination_started) * 1000

        evaluation_started = clock()
        try:
            other = 'W' if color == 'B' else 'B'
            for index, row in enumerate(trace['candidates']):
                reason = stopped()
                if reason:
                    return finish(root_move, 'fallback', reason)
                child = children[row['move']]
                if child.passes >= 2:
                    value = _terminal(child, color)
                else:
                    child_response = query(history + [[color, row['move']]], other, f'child-{index}')
                    value = _value(child_response, other, color)
                row.update(value=value, status='evaluated')
                if stopped():
                    row['status'] = 'late'
                    return finish(root_move, 'fallback', stopped())
            use_score = all(row['value']['score'] is not None for row in trace['candidates'])
            best = max(trace['candidates'], key=lambda row:
                       (row['value']['winrate'], row['value']['score'] if use_score else 0))
            if stopped():
                return finish(root_move, 'fallback', stopped())
            trace.update(completed_rounds=1, score_tiebreak_used=use_score,
                         policy_rank=best['policy_rank'])
            return finish(best['move'], 'evaluated')
        except TimeoutError:
            return finish(root_move, 'fallback', stopped() or 'evaluation_timeout')
        finally:
            trace['evaluation_ms'] = (clock() - evaluation_started) * 1000
    except Exception as exc:
        finish(None, 'failed')
        trace['error'] = repr(exc)
        trace['failure_kind'] = 'root_unavailable' if isinstance(exc, TimeoutError) else 'operational'
        raise DecisionError(str(exc), trace) from exc

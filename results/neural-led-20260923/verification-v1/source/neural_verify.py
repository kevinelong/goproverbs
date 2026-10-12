"""Experimental fixed-margin override verification; existing chooser unchanged."""
import copy
import math
import time

from lab import Referee
from neural import make_query
from neural_led import DecisionError, _child, _terminal, _value, choose

MARGIN = .005


def checked_value(response, identifier, player, color, visits):
    if response.get('id') != identifier:
        raise ValueError('reference ID mismatch')
    if response.get('isDuringSearch') or response.get('_used_intermediate'):
        raise ValueError('incomplete search response')
    if 'error' in response or 'warning' in response:
        raise ValueError('query rejected or altered')
    count = response['rootInfo']['visits']
    if isinstance(count, bool) or not isinstance(count, (int, float)) or not math.isfinite(count) or not count >= visits:
        raise ValueError('insufficient completed visits')
    return _value(response, player, color)


def select_move(root, alternative, values):
    return alternative if values[alternative]['winrate'] - values[root]['winrate'] >= MARGIN else root


def choose_verified(kata, moves, color, size, komi, time_ms, visits,
                    variant='neural', proposer=None, identifier='verify',
                    clock=time.perf_counter, cancelled=None):
    started = clock()
    if isinstance(visits, bool) or visits not in (4, 8, 16):
        raise ValueError('visits must be 4, 8 or 16')
    deadline = started + time_ms / 1000
    baseline, base = choose(kata, moves, color, size, komi, (deadline-clock())*1000,
        variant=variant, proposer=proposer, identifier=identifier+'-base',
        clock=clock, cancelled=cancelled)
    trace = dict(baseline_move=baseline, root_move=base['root_move'], baseline=base,
                 visits=visits, margin=MARGIN, verification_complete=False,
                 verification_attempted=False, verification_fallback=False,
                 values={}, queries=[], pass_agreement=base['pass_agreement'])

    def finish(move, status):
        now = clock()
        if status == 'verified' and now >= deadline:
            move, status = base['root_move'], 'verification_fallback'
            trace.update(verification_fallback=True, verification_complete=False)
        trace.update(move=move, status=status, ms=(now-started)*1000,
                     overshoot_ms=max(0, (now-deadline)*1000))
        return move, trace

    def check():
        if cancelled is not None and cancelled():
            raise TimeoutError('cancelled')
        if clock() >= deadline:
            raise TimeoutError('deadline')

    if baseline is None or base['fallback'] or not base['completed_rounds'] or baseline == base['root_move']:
        return finish(baseline, 'baseline')
    trace['verification_attempted'] = True
    try:
        check()
        ref = Referee(size, komi)
        for player, move in moves:
            ref.play(player, move)
        other = 'W' if color == 'B' else 'B'
        for index, move in enumerate((base['root_move'], baseline)):
            check()
            child = _child(ref, color, move)
            if child.passes >= 2:
                value = _terminal(child, color)
            else:
                qid = identifier + '-verify-' + str(index)
                query = make_query(qid, copy.deepcopy(moves)+[[color, move]], other, size, komi, 'policy')
                query['maxVisits'] = visits
                check()
                response = kata.request(query, deadline=deadline)
                check()
                value = checked_value(response, qid, other, color, visits)
                trace['queries'].append(dict(id=qid, rootInfo=copy.deepcopy(response['rootInfo'])))
            trace['values'][move] = value
        check()
        move = select_move(base['root_move'], baseline, trace['values'])
        trace['verification_complete'] = True
        return finish(move, 'verified')
    except TimeoutError as exc:
        trace.update(verification_fallback=True, fallback_reason=str(exc))
        return finish(base['root_move'], 'verification_fallback')
    except Exception as exc:
        finish(None, 'failed')
        trace['error'] = repr(exc)
        raise DecisionError(str(exc), trace) from exc

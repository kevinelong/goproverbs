"""Conservative group diagnostics and bounded capture proof.

No heuristic group status changes legality or scoring. A capture result requires
all legal defenses to fail within the horizon; exhaustion returns unknown.
Attack choices are restricted, so missing a proof says nothing about life.
"""
import copy
from lab import COLUMNS


def vertex(p, size): return f'{COLUMNS[p % size]}{size - p // size}'


def groups(ref):
    seen, result = set(), []
    for p, color in enumerate(ref.board):
        if color == '.' or p in seen: continue
        stones, liberties = ref.group(ref.board, p)
        seen.update(stones)
        eyes = [q for q in liberties if all(ref.board[n] == color for n in ref.neighbors(q))]
        result.append({'color': color, 'stones': [vertex(q, ref.size) for q in sorted(stones)],
                       'liberties': [vertex(q, ref.size) for q in sorted(liberties)],
                       'eye_candidates': [vertex(q, ref.size) for q in sorted(eyes)],
                       'status': 'atari' if len(liberties) == 1 else 'unknown'})
    return result


def capture_proof(ref, target, attacker, to_play, plies=4, max_nodes=1000):
    if attacker not in ['B','W'] or to_play not in ['B','W'] or plies < 0 or max_nodes < 1:
        raise ValueError('invalid capture-reader limits or colors')
    x, y = COLUMNS.index(target[0]), ref.size-int(target[1:])
    anchor = y*ref.size+x
    if not 0 <= x < ref.size or not 0 <= y < ref.size:
        raise ValueError('target outside board')
    defender = ref.board[anchor]
    if defender == '.' or defender == attacker:
        raise ValueError('target must be an opponent stone')
    nodes = 0

    def walk(board, player, remaining):
        nonlocal nodes
        if nodes >= max_nodes: return None
        nodes += 1
        if board.board[anchor] != defender: return []
        if remaining == 0 or board.passes == 2: return None
        if player == attacker:
            stones, liberties = board.group(board.board, anchor)
            points = set(liberties)
            # Also allow liberty-adding moves for adjacent attacking chains.
            for p in stones:
                for n in board.neighbors(p):
                    if board.board[n] == attacker:
                        _, libs = board.group(board.board, n)
                        points.update(libs)
            choices = [vertex(p, board.size) for p in sorted(points)]
        else:
            # Completeness of defense is essential for a positive proof.
            choices = [vertex(p, board.size) for p,c in enumerate(board.board) if c == '.'] + ['pass']
        longest = []
        for move in choices:
            child = copy.deepcopy(board)
            try: child.play(player, move)
            except AssertionError: continue
            line = walk(child, 'W' if player == 'B' else 'B', remaining-1)
            if player == attacker and line is not None: return [[player,move]]+line
            if player != attacker:
                if line is None: return None
                if len(line)+1 > len(longest): longest = [[player,move]]+line
        return None if player == attacker else longest

    line = walk(ref, to_play, plies)
    return {'status': 'capture-proven-within-horizon' if line is not None else 'unknown',
            'line': line, 'nodes': nodes, 'plies': plies, 'max_nodes': max_nodes,
            'all_legal_defenses_considered_for_positive_proof': True}

"""SGF FF4 syntax and explicit first-variation replay subset.

Parses/preserves property maps, escaped values and variations. Replay supports
square Go boards, komi and colored move history. Setup/edit properties are
rejected instead of being misrepresented as ordinary moves.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from lab import COLUMNS, Referee


def parse(text):
    index = 0

    def space():
        nonlocal index
        while index < len(text) and text[index].isspace():
            index += 1

    def take(char):
        nonlocal index
        space()
        if index >= len(text) or text[index] != char:
            raise ValueError(f'expected {char!r} at offset {index}')
        index += 1

    def value():
        nonlocal index
        take('[')
        out = []
        while index < len(text):
            char = text[index]
            index += 1
            if char == ']':
                return ''.join(out)
            if char == '\\':
                if index == len(text):
                    raise ValueError('unfinished SGF escape')
                char = text[index]
                index += 1
                if char in '\r\n':
                    if index < len(text) and text[index] in '\r\n' and text[index] != char:
                        index += 1
                    continue
            out.append(char)
        raise ValueError('unterminated SGF value')

    def tree(depth=0):
        nonlocal index
        if depth > 128:
            raise ValueError('SGF nesting limit exceeded')
        take('(')
        nodes, children = [], []
        space()
        while index < len(text) and text[index] == ';':
            index += 1
            node = {}
            space()
            while index < len(text) and 'A' <= text[index] <= 'Z':
                start = index
                while index < len(text) and 'A' <= text[index] <= 'Z':
                    index += 1
                name = text[start:index]
                if name in node:
                    raise ValueError('duplicate property ' + name)
                values = []
                space()
                while index < len(text) and text[index] == '[':
                    values.append(value())
                    space()
                if not values:
                    raise ValueError('property without a value: ' + name)
                node[name] = values
            nodes.append(node)
        if not nodes:
            raise ValueError('empty SGF sequence')
        while index < len(text) and text[index] == '(':
            children.append(tree(depth + 1))
            space()
        take(')')
        return {'nodes': nodes, 'children': children}

    games = []
    space()
    while index < len(text):
        games.append(tree())
        space()
    if not games:
        raise ValueError('empty SGF collection')
    return games


def vertex(text, size):
    if text == '' or (text == 'tt' and size <= 19):
        return 'pass'
    if len(text) != 2 or any(not 'a' <= c <= 'y' for c in text):
        raise ValueError('invalid SGF move')
    x, y = (ord(c) - ord('a') for c in text)
    if x >= size or y >= size:
        raise ValueError('SGF move outside board')
    return f'{COLUMNS[x]}{size-y}'


def read_game(text, game_index=0):
    games = parse(text)
    if not 0 <= game_index < len(games):
        raise ValueError('SGF game index outside collection')
    current, nodes, variations = games[game_index], [], 0
    while current:
        nodes.extend(current['nodes'])
        variations += max(0, len(current['children']) - 1)
        current = current['children'][0] if current['children'] else None
    root = nodes[0]

    def single(node, key, default):
        values = node.get(key, [default])
        if len(values) != 1:
            raise ValueError('multiple values for ' + key)
        return values[0]

    if single(root, 'GM', '1') != '1':
        raise ValueError('only Go SGF is supported')
    if single(root, 'FF', '4') not in ['3', '4']:
        raise ValueError('only SGF FF3/FF4 replay is supported')
    size_text = single(root, 'SZ', '19')
    sides = size_text.split(':')
    if len(sides) > 2 or len(set(sides)) != 1:
        raise ValueError('only square boards are supported')
    size = int(sides[0])
    komi = float(single(root, 'KM', '0'))
    if not 2 <= size <= 25 or not math.isfinite(komi):
        raise ValueError('invalid board size or komi')
    moves = []
    for i, node in enumerate(nodes):
        if any(key in node for key in ['AB', 'AW', 'AE', 'HA']):
            raise ValueError('setup/handicap SGF replay is not implemented')
        if i and any(key in node for key in ['SZ', 'KM', 'RU', 'PL']):
            raise ValueError('midgame setup/rule changes are not supported')
        if 'B' in node and 'W' in node:
            raise ValueError('two moves in one node')
        for color in ['B', 'W']:
            if color in node:
                moves.append([color, vertex(single(node, color, ''), size)])
    player = single(root, 'PL', moves[0][0] if moves else 'B')
    if player not in ['B', 'W']:
        raise ValueError('invalid player')
    return {'size': size, 'komi': komi, 'rules': single(root, 'RU', 'unspecified'),
            'initial_player': player, 'moves': moves, 'nodes': nodes,
            'ignored_variations': variations, 'collection_games': len(games),
            'source_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}


def replay(record, assume_tt=False):
    if record['rules'].lower() not in ['tromp-taylor', 'tromp taylor', 'tt'] and not assume_tt:
        raise ValueError('SGF rules are not explicitly Tromp-Taylor; use an explicit rules-conversion assumption')
    ref = Referee(record['size'], record['komi'])
    for color, move in record['moves']:
        if ref.passes == 2:
            raise ValueError('moves after two-pass termination are unsupported')
        ref.play(color, move)
    return ref


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--assume-tt', action='store_true')
    args = parser.parse_args()
    record = read_game(args.file.read_text(encoding='utf-8-sig'))
    ref = replay(record, args.assume_tt)
    print(json.dumps({k: v for k, v in record.items() if k != 'nodes'}, indent=2))
    print('Replayed legally; board area margin:', ref.margin())

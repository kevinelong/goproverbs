"""Human terminal play with ASCII boards, undo, explanations and SGF replay."""
import argparse
import json
from pathlib import Path
import shlex

from lab import GTP, ROOT
from sgf_io import read_game, replay
from safety import groups, capture_proof


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,default=ROOT/'target/release/goproverbs.exe')
    p.add_argument('--time-ms',type=int,default=1000)
    p.add_argument('--size',type=int,default=19)
    p.add_argument('--komi',type=float,default=7.5)
    p.add_argument('--color',choices=['B','W'],default='B')
    args=p.parse_args()
    print('Commands: coordinate/pass, go, undo, rank, explain, groups, capture POINT, save FILE, load FILE, board, quit')
    print('Tromp-Taylor: capture dead stones before both players pass. No life/death adjudication.')
    history=[]; turn='B'
    with GTP(args.exe,size=args.size,search_mode='hybrid',time_ms=args.time_ms,depth=12,nodes=10000000,beam=12) as gp:
        gp.command(f'komi {args.komi}')
        while True:
            try: finished=gp.command('final_score')
            except RuntimeError: finished=None
            if not finished and turn != args.color:
                move=gp.command(f'genmove {turn}'); print('Engine:',move)
                history.append(turn); turn='W' if turn=='B' else 'B'
                try: finished=gp.command('final_score')
                except RuntimeError: finished=None
            print(gp.command('showboard'))
            try: words=shlex.split(input(f'{turn}> '),posix=False)
            except EOFError: break
            if not words: continue
            command=words[0].lower()
            try:
                if command in ['quit','exit']: break
                if command=='board': continue
                if command=='save' and len(words)==2:
                    path=Path(words[1].strip('"'))
                    with path.open('x',encoding='ascii') as file: file.write(gp.command('gp-sgf'))
                    print('Saved',path); continue
                if command=='load' and len(words)==2:
                    record=read_game(Path(words[1].strip('"')).read_text(encoding='utf-8-sig'))
                    replay(record)  # Validate fully before replacing the current game.
                    gp.command(f"boardsize {record['size']}"); gp.command(f"komi {record['komi']}")
                    for c,m in record['moves']: gp.command(f'play {c} {m}')
                    history=[c for c,_ in record['moves']]
                    turn=('W' if history[-1]=='B' else 'B') if history else record['initial_player']
                    if record['ignored_variations']: print('Loaded first variation; other variations not replayed.')
                    continue
                if command=='undo':
                    if not history: print('Nothing to undo'); continue
                    gp.command('undo'); turn=history.pop()
                    if history and turn!=args.color: gp.command('undo'); turn=history.pop()
                    continue
                if command=='rank': print('\n'.join(gp.command(f'gp-candidates {turn}').splitlines()[:8])); continue
                if command=='explain': print(gp.command('gp-last-search')); continue
                if command=='groups':
                    print(json.dumps(groups(replay(read_game(gp.command('gp-sgf')))),indent=2)); continue
                if command=='capture' and len(words)==2:
                    ref=replay(read_game(gp.command('gp-sgf')))
                    from lab import COLUMNS
                    target=words[1].upper()
                    x,y=COLUMNS.index(target[0]),ref.size-int(target[1:])
                    if not 0<=x<ref.size or not 0<=y<ref.size: raise ValueError('target outside board')
                    owner=ref.board[y*ref.size+x]
                    if owner=='.': raise ValueError('target is empty')
                    print(json.dumps(capture_proof(ref,target,'W' if owner=='B' else 'B',turn),indent=2)); continue
                if finished: print('Game finished:',finished,'; use undo, load, or quit.'); continue
                if command=='go':
                    move=gp.command(f'genmove {turn}'); print('Engine:',move)
                    history.append(turn); turn='W' if turn=='B' else 'B'
                else:
                    gp.command(f'play {turn} {words[0]}')
                    history.append(turn); turn='W' if turn=='B' else 'B'
                    try: result=gp.command('final_score')
                    except RuntimeError: result=None
                    if result: print('Game finished:',result); continue
                    move=gp.command(f'genmove {turn}'); print('Engine:',move)
                    history.append(turn); turn='W' if turn=='B' else 'B'
                try: print('Game finished:',gp.command('final_score'))
                except RuntimeError: pass
            except (RuntimeError,ValueError,AssertionError,OSError) as exc: print('Error:',exc)


if __name__=='__main__': main()

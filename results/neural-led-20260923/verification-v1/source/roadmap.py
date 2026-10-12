"""Controlled nomination/evaluation ablation on the unchanged hybrid tree logic."""
import argparse
import copy
import json
from pathlib import Path
import random
import statistics
import time

from guidance import Broker, choose
from lab import GTP, ROOT, Referee
from neural import KataGo, config_text, digest, hardware


def make_engine(args, komi=7.5):
    gp = GTP(args.exe, args.profile, size=19, search_mode='hybrid',
             time_ms=args.time_ms, nodes=10000000, depth=12, beam=12)
    gp.command(f'komi {komi}')
    return gp


def load_position(gp, moves, komi):
    gp.command('clear_board')
    gp.command(f'komi {komi}')
    ref = Referee(19, komi)
    for color, move in moves:
        ref.play(color, move)
        gp.command(f'play {color} {move}')
    ref.compare(gp.command('showboard'))
    return ref


def probe(args, kata, broker):
    corpus = json.loads(args.corpus.read_text())['positions']
    # Spread probes over source games and phases rather than taking only the
    # first game's four positions. Fixed seed/order, never optimize on labels.
    rng = random.Random(20260921)
    rng.shuffle(corpus)
    selected = corpus[:args.positions]
    rows = []
    with make_engine(args) as gp:
        for case in selected:
            for mode in args.modes:
                ref = load_position(gp, case['moves'], case['komi'])
                kata.request({'id': f'clear-{len(rows)}', 'action': 'clear_cache'})
                move, trace = choose(gp, broker, case['moves'], case['color'], case['komi'], mode, args.time_ms)
                ref.play(case['color'], move)
                ref.compare(gp.command('showboard'))
                rows.append({'id': case['id'], 'source_game': case['source_game'], 'mode': mode,
                             'move': move, 'trace': trace})
                (args.output/'probes.json').write_text(json.dumps(rows, indent=2), encoding='ascii')
                print(case['id'], mode, trace['report'].splitlines()[0], flush=True)
    return rows


def arena(args, kata, broker):
    openings = json.loads(args.openings.read_text())['openings'][:args.pairs]
    games = []
    for opening in openings:
        for mode in [m for m in args.modes if m != 'HH']:
            for variant_color in ['B', 'W']:
                stem = f"{opening['id']}-{mode}-{variant_color}"
                moves = copy.deepcopy(opening['moves'])
                decisions = []
                kata.request({'id': 'clear-'+stem, 'action': 'clear_cache'})
                with make_engine(args) as variant, make_engine(args) as control:
                    ref = load_position(variant, moves, 7.5)
                    load_position(control, moves, 7.5)
                    with (args.output/(stem+'.jsonl')).open('w', encoding='ascii') as wire:
                        for turn in range(722):
                            if (args.output/'STOP').exists(): break
                            color = 'B' if turn % 2 == 0 else 'W'
                            actor, observer = (variant, control) if color == variant_color else (control, variant)
                            selected_mode = mode if color == variant_color else 'HH'
                            move, trace = choose(actor, broker, moves, color, 7.5, selected_mode, args.time_ms)
                            observer.command(f'play {color} {move}')
                            ref.play(color, move)
                            for gp in [variant, control]: ref.compare(gp.command('showboard'))
                            moves.append([color, move])
                            decision = {'color': color, 'mode': selected_mode, 'move': move, 'trace': trace}
                            decisions.append(decision)
                            wire.write(json.dumps(decision)+'\n'); wire.flush()
                            if ref.passes == 2: break
                            if (turn+1) % 100 == 0: print(stem, turn+1, flush=True)
                    finished = ref.passes == 2
                    margin = ref.margin()
                    winner_color = 'B' if margin > 0 else 'W' if margin < 0 else 'draw'
                    score = f'{winner_color}+{abs(margin):g}' if margin else '0'
                    if finished:
                        for gp in [variant, control]: assert gp.command('final_score') == score
                    (args.output/(stem+'.sgf')).write_text(variant.command('gp-sgf'), encoding='ascii')
                row = {'opening': opening['id'], 'mode': mode, 'variant_color': variant_color,
                       'finished': finished, 'result': score if finished else 'unfinished',
                       'variant_won': finished and winner_color == variant_color, 'moves':len(moves)}
                games.append(row)
                (args.output/'games.json').write_text(json.dumps(games, indent=2), encoding='ascii')
                print(stem, row['result'], 'variant_won', row['variant_won'], flush=True)
                if (args.output/'STOP').exists(): return games
    return games


def backend(args, kata, broker):
    cases = json.loads(args.corpus.read_text())['positions'][:args.positions]
    rows = []
    for i, case in enumerate(cases):
        kata.request({'id':f'backend-clear-{i}', 'action':'clear_cache'})
        start = time.perf_counter()
        response = broker.query(case['moves'], case['color'], 19, case['komi'])
        rows.append({'id':case['id'], 'ms':(time.perf_counter()-start)*1000,
                     'root':response['rootInfo'], 'policy':response['policy']})
    (args.output/'backend.json').write_text(json.dumps(rows, indent=2), encoding='ascii')
    print('median policy inference ms', statistics.median(r['ms'] for r in rows), flush=True)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('task', choices=['probe','arena','backend'])
    p.add_argument('--katago', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--exe', type=Path, default=ROOT/'target/release/goproverbs.exe')
    p.add_argument('--profile', type=Path, default=ROOT/'profiles/baseline.weights')
    p.add_argument('--corpus', type=Path, default=ROOT/'results/roadmap-20260921/corpus/positions.json')
    p.add_argument('--openings', type=Path, default=ROOT/'results/roadmap-20260921/corpus/openings.json')
    p.add_argument('--modes', nargs='+', choices=['HH','NH','HN','NN'], default=['HH','NH','HN','NN'])
    p.add_argument('--time-ms', type=int, default=200)
    p.add_argument('--pairs', type=int, default=2)
    p.add_argument('--positions', type=int, default=8)
    p.add_argument('--cpu', action='store_true')
    args = p.parse_args()
    if args.pairs < 1 or args.positions < 1 or args.time_ms < 1: p.error('positive limits required')
    args.output = args.output.resolve(); args.output.mkdir(parents=True, exist_ok=False)
    cfg = args.output/'analysis.cfg'
    cfg.write_text(config_text(args.time_ms) + ('\nnumEigenThreadsPerModel = 4\n' if args.cpu else ''), encoding='ascii')
    manifest = {'status':'running', 'settings':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
                'hashes':{str(path):digest(path) for path in [args.katago,args.model,args.exe,args.profile,args.corpus,args.openings,cfg,
                          Path(__file__),ROOT/'benchmarks/guidance.py',ROOT/'benchmarks/sgf_io.py',ROOT/'benchmarks/lab.py',ROOT/'benchmarks/neural.py']}}
    def save(): (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='ascii')
    save()
    try:
        manifest['before'] = hardware()
        for directory in ['round-20260920','overnight-20260916']:
            if (Path.home()/'ai_bench'/directory/'RUNNING.lock').exists(): raise RuntimeError('competing runner lock')
        if len(manifest['before']['ollama']['stdout'].strip().splitlines()) > 1: raise RuntimeError('resident Ollama model')
        with KataGo(args.katago.resolve(),args.model.resolve(),cfg,args.output) as kata:
            manifest['version'] = kata.request({'id':'version','action':'query_version'})
            with Broker(kata) as broker:
                broker.query([], 'B', 19, 7.5)
                manifest['loaded'] = hardware()
                manifest['records'] = {'probe':probe,'arena':arena,'backend':backend}[args.task](args,kata,broker)
                manifest['broker_queries'] = broker.count
                manifest['broker_errors'] = broker.errors
                if broker.errors: raise RuntimeError('neural broker errors; inspect manifest')
            manifest['status'] = 'stopped' if (args.output/'STOP').exists() else 'complete'
    except BaseException as exc:
        manifest['status'] = 'failed'; manifest['error'] = repr(exc); raise
    finally:
        manifest['after'] = hardware(); save()


if __name__ == '__main__': main()

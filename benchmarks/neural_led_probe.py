"""Frozen development probes for the neural-led controller; never strength claims."""
import argparse
import copy
import json
import math
from pathlib import Path
import queue
import random
import re
import shutil
import statistics
import threading
import time

from lab import GTP, Referee
from neural import KataGo, config_text, digest

GO = Path('C:/Users/kevin/local-llm-lab/goproverbs')
BENCH = Path('C:/Users/kevin/ai_bench')
VARIANTS = ('policy','neural','heuristic','tactical','combined')
DEFAULT = GO/'results/neural-led-20260923/probe-v1'
SOURCES = ('neural_led.py','test_neural_led.py','neural_led_probe.py','test_neural_led_probe.py',
           'lab.py','neural.py','sgf_io.py')


def save(path, data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='ascii')
    temporary.replace(path)


def parse_candidates(text):
    rows=[]
    for line in text.splitlines():
        fields=line.split()
        if len(fields)<2:
            raise ValueError('Malformed gp-candidates row')
        score=float(fields[1])
        if not math.isfinite(score):
            raise ValueError('Nonfinite heuristic preference')
        rows.append({'move':fields[0],'preference':score,'features':fields[2:]})
    return rows


def parse_tactical(text):
    first=text.splitlines()[0] if text else ''
    match=re.search(r'^move=(\S+)',first)
    if not match:
        raise ValueError('Missing tactical move')
    selected=match.group(1)
    evidence=[]
    for line in text.splitlines():
        found=re.search(r'^\s+(\S+) heuristic=\S+ scout=\S+ verified=([-+0-9.eE]+) depth=(\d+)',line)
        if found:
            value=float(found.group(2))
            if not math.isfinite(value):
                raise ValueError('Nonfinite tactical preference')
            evidence.append((int(found.group(3)),value,found.group(1)))
    # The selected move is a proposal even if no verification round finished.
    # Only comparable completed-depth evidence can nominate an additional move.
    depth=max((row[0] for row in evidence),default=0)
    extra=sorted((row for row in evidence if row[0]==depth and depth>0),key=lambda r:(-r[1],r[2]))
    return [selected]+[r[2] for r in extra if r[2]!=selected][:1]


class Proposer:
    def __init__(self,gp,moves):
        self.gp=gp
        self.moves=copy.deepcopy(moves)
        self.poisoned=False
        self.threads=[]
        self.last={}

    def command(self,text,deadline):
        if self.poisoned:
            raise RuntimeError('GTP transport poisoned after deadline')
        remaining=deadline-time.perf_counter()
        if remaining<=0:
            raise TimeoutError('Nomination budget expired')
        response=queue.Queue()
        def work():
            try: response.put((True,self.gp.command(text)))
            except BaseException as exc: response.put((False,exc))
        thread=threading.Thread(target=work,daemon=True)
        self.threads.append(thread)
        thread.start()
        try:
            ok,value=response.get(timeout=max(0,deadline-time.perf_counter()))
        except queue.Empty:
            self.poisoned=True
            self.gp.proc.kill()
            raise TimeoutError('GTP nomination did not return before deadline') from None
        if not ok: raise value
        if time.perf_counter()>=deadline:
            raise TimeoutError('Late GTP nomination ignored')
        return value

    def __call__(self,*,moves,color,size,komi,deadline,variant):
        if moves!=self.moves:
            raise ValueError('Proposer board history mismatch')
        start=time.perf_counter()
        # Reserve at least 70% of the post-root remainder for neural comparison.
        proposal_deadline=min(deadline,start+min(.05,max(0,(deadline-start)*.30)))
        result={'heuristic':[],'tactical':[]}
        self.last={'variant':variant,'heuristic':[],'tactical':[],'search_report':None}
        try:
            if variant in ('heuristic','combined'):
                candidates=parse_candidates(self.command('gp-candidates '+color,proposal_deadline))
                result['heuristic']=[r['move'] for r in candidates[:2]]
                self.last['heuristic']=candidates[:2]
            if variant in ('tactical','combined'):
                left=proposal_deadline-time.perf_counter()
                if left<=.004: raise TimeoutError('No tactical nomination allowance remains')
                allowance=max(1,min(25,int(left*1000)-3))
                self.command(f'gp-limits {allowance} 100000 4 8',proposal_deadline)
                report=self.command('gp-search '+color,proposal_deadline)
                result['tactical']=parse_tactical(report)
                self.last.update(tactical=result['tactical'],search_report=report)
            return dict(result,metadata=dict(self.last))
        finally:
            self.last['ms']=(time.perf_counter()-start)*1000

    def close(self):
        if self.poisoned:
            if self.gp.proc.poll() is None: self.gp.proc.kill()
            self.gp.proc.wait(timeout=3)
        self.gp.close()
        for thread in self.threads: thread.join(timeout=1)
        if any(t.is_alive() for t in self.threads):
            raise RuntimeError('GTP command thread did not finish')


def schedule(cases):
    rows=[{'case':c['id'],'budget':b,'variant':v} for c in cases for b in (200,400) for v in VARIANTS]
    random.Random(260923).shuffle(rows)
    return rows


def prepare(output):
    output.mkdir(parents=True,exist_ok=False)
    source=output/'source'
    source.mkdir()
    for name in SOURCES: shutil.copy2(GO/'benchmarks'/name,source/name)
    corpus=GO/'results/roadmap-20260921/corpus/positions.json'
    cases=json.loads(corpus.read_text())['positions']
    random.Random(20260921).shuffle(cases)
    cases=cases[:8]
    save(output/'positions.json',cases)
    save(output/'schedule.json',schedule(cases))
    shutil.copy2(GO/'docs/NEURAL-LED-PLAN-2026-09-23.md',output/'PROTOCOL.md')
    (output/'analysis.cfg').write_text(config_text(400),encoding='ascii')
    assets={'katago':BENCH/'katago/opencl-1.18.1/katago.exe',
            'model':BENCH/'katago/kata1-b10c128-s919229184-d169515535.txt.gz',
            'exe':GO/'results/direct-20260922/source-v2/goproverbs.exe',
            'profile':GO/'results/direct-20260922/source-v2/profiles/baseline.weights'}
    paths=list(source.iterdir())+list(assets.values())+[corpus,output/'positions.json',output/'schedule.json',output/'analysis.cfg',output/'PROTOCOL.md']
    save(output/'identity.json',{'assets':{k:str(v) for k,v in assets.items()},'hashes':{str(p):digest(p) for p in paths}})
    save(output/'status.json',{'status':'prepared','expected':80})


def verify(output):
    identity=json.loads((output/'identity.json').read_text())
    for path,expected in identity['hashes'].items():
        if digest(path)!=expected: raise RuntimeError('Frozen input changed: '+path)
    return identity


def report(output,rows,status):
    lines=['# Neural-led development probes','',f'Status: {status}.',
           'Eight reused development positions. These are not strength results.','',
           '| Budget | Variant | Decisions | Complete rounds | Root fallback | Median ms | Max overshoot ms |',
           '|---:|---|---:|---:|---:|---:|---:|']
    for budget in (200,400):
        for variant in VARIANTS:
            group=[r for r in rows if r['budget']==budget and r['variant']==variant and 'move' in r]
            if not group: continue
            lines.append(f"| {budget} | {variant} | {len(group)} | {sum(bool(r['trace'].get('completed_rounds')) for r in group)} | {sum(bool(r['trace'].get('fallback')) for r in group)} | {statistics.median(r['measured_ms'] for r in group):.2f} | {max(max(0,r['measured_ms']-budget) for r in group):.2f} |")
    lines+=['','Inspect raw traces for policy overrides, partial evaluations and nominee provenance.',
            'Fallback is a usable root-policy decision, not a completed neural comparison.',
            'No automatic strength expansion or engine-default promotion follows these probes.','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='ascii')


def run(output):
    from neural_led import choose
    identity=verify(output)
    assets={k:Path(v) for k,v in identity['assets'].items()}
    cases={r['id']:r for r in json.loads((output/'positions.json').read_text())}
    entries=json.loads((output/'schedule.json').read_text())
    if (output/'results.json').exists(): raise RuntimeError('Refusing to reuse completed/partial labels')
    # Read-only preflight shared with the LLM lab, without loading any models.
    import sys
    sys.path.insert(0,str(GO.parent/'benchmarks'))
    import compare_bonsai_packing_20260922 as resource
    preflight=resource.preflight()
    if preflight.get('ram_bytes',{}).get('available',0)<4*1024**3:
        raise RuntimeError('Less than 4 GiB physical headroom')
    others=[p for p in (GO/'results').glob('**/RUNNING.lock') if p!=output/'RUNNING.lock']
    others.extend(BENCH.glob('*/RUNNING.lock'))
    if others: raise RuntimeError('Other Go run lock present: '+str(others))
    if 'reportAnalysisWinratesAs = BLACK' not in (output/'analysis.cfg').read_text():
        raise RuntimeError('Neural value perspective must be BLACK')
    state={'status':'running','started':time.time(),'expected':len(entries),'preflight':preflight}
    rows=[]
    lock=output/'RUNNING.lock'
    with lock.open('x') as handle: handle.write(str(__import__('os').getpid()))
    def record():
        state['completed']=len(rows)
        save(output/'status.json',state)
        save(output/'results.json',rows)
        report(output,rows,state['status'])
    try:
        record()
        with KataGo(assets['katago'],assets['model'],output/'analysis.cfg',output) as kata:
            state['version']=kata.request({'id':'version','action':'query_version'},deadline=time.perf_counter()+30)
            from neural import make_query
            kata.request(make_query('warmup',[],'B',19,7.5,'policy'),deadline=time.perf_counter()+60)
            for index,entry in enumerate(entries):
                if (output/'STOP').exists():
                    state['status']='stopped'
                    break
                verify(output)
                case=cases[entry['case']]
                state['active']=entry
                record()
                kata.request({'id':f'clear-{index}','action':'clear_cache'},deadline=time.perf_counter()+30)
                gp=GTP(assets['exe'],assets['profile'],size=case['size'],nodes=100000,depth=4,beam=8,
                       tactical=2,search_mode='hybrid',time_ms=25)
                proposer=Proposer(gp,case['moves'])
                row=dict(entry,source_game=case['source_game'])
                try:
                    gp.command(f"komi {case['komi']}")
                    ref=Referee(case['size'],case['komi'])
                    for color,move in case['moves']:
                        ref.play(color,move)
                        gp.command(f'play {color} {move}')
                    ref.compare(gp.command('showboard'))
                    before=gp.command('gp-sgf')
                    started=time.perf_counter()
                    move,trace=choose(kata,case['moves'],case['color'],case['size'],case['komi'],entry['budget'],
                                      variant=entry['variant'],proposer=proposer,identifier=f'probe-{index}',
                                      cancelled=lambda:(output/'STOP').exists())
                    elapsed=(time.perf_counter()-started)*1000
                    if move is None: raise RuntimeError('Nonterminal probe returned no move')
                    if not proposer.poisoned and gp.command('gp-sgf')!=before:
                        raise RuntimeError('Nomination mutated root game')
                    ref.play(case['color'],move)
                    if not proposer.poisoned:
                        gp.command(f"play {case['color']} {move}")
                        ref.compare(gp.command('showboard'))
                    row.update(move=move,trace=trace,measured_ms=elapsed,proposer=proposer.last,
                               gtp_poisoned=proposer.poisoned,referee_legal=True)
                except BaseException as exc:
                    row.update(error=repr(exc),trace=getattr(exc,'trace',{}))
                    rows.append(row)
                    record()
                    raise
                finally:
                    proposer.close()
                rows.append(row)
                record()
                print(entry,move,round(elapsed,2),flush=True)
            else: state['status']='complete'
            state['transport_metrics']=dict(kata.metrics)
        verify(output)
        state['inputs_unchanged']=True
    except BaseException as exc:
        state.update(status='failed',error=repr(exc))
        raise
    finally:
        state['finished']=time.time()
        try:
            state['remaining_model_processes']=resource.active_processes()
            if state['remaining_model_processes']:
                state.update(status='failed',cleanup_error='Model process remains after cleanup')
        except Exception as exc:
            state.update(status='failed',cleanup_error=repr(exc))
        finally:
            lock.unlink()
            record()
        if state.get('cleanup_error'):
            raise RuntimeError(state['cleanup_error'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    if args.action=='prepare': prepare(args.output)
    else:
        if Path(__file__).parent.resolve()!=(args.output/'source').resolve():
            raise RuntimeError('Run frozen source copy')
        run(args.output)


if __name__=='__main__': main()

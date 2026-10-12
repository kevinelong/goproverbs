"""Freeze current research source and verify the original baseline manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    baseline=ROOT/'results/reference-20260921'
    reference=json.loads((baseline/'manifest.json').read_text())
    for name,expected in reference.items():
        assert digest(baseline/name)==expected, name
    args.output.mkdir(parents=True,exist_ok=False)
    files={}
    for directory in ['src','tests','benchmarks','profiles','docs','scripts']:
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                files[path.relative_to(ROOT).as_posix()]=path
    for name in ['Cargo.toml','Cargo.lock','README.md','.gitignore']:
        files[name]=ROOT/name
    files['goproverbs.exe']=ROOT/'target/release/goproverbs.exe'
    manifest={}
    for name,path in files.items():
        target=args.output/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        manifest[name]=digest(path)
        assert digest(target)==manifest[name],name
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='ascii')
    print('Verified original baseline files:',len(reference))
    print('Frozen and verified current files:',len(manifest))


if __name__=='__main__': main()

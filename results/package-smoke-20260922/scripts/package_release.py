"""Build a local Windows research bundle with an internal SHA256 manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--evidence', type=Path, action='append',
                        help='Explicit evidence directory; repeat as needed. Defaults to the September 21 roadmap.')
    parser.add_argument('--snapshot', type=Path, action='append', default=[],
                        help='Also include an exact frozen experiment snapshot inside the project.')
    args=parser.parse_args()
    if args.output.exists(): parser.error('refusing to overwrite a release bundle')
    files={}
    for directory in ['src','tests','benchmarks','profiles','docs','examples','scripts']:
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                files[path.relative_to(ROOT).as_posix()]=path
    for name in ['Cargo.toml','Cargo.lock','README.md','.gitignore']:
        files[name]=ROOT/name
    files['bin/goproverbs.exe']=ROOT/'target/release/goproverbs.exe'
    for evidence in args.evidence or [ROOT/'results/roadmap-20260921']:
        evidence = evidence.resolve()
        evidence.relative_to(ROOT)  # Evidence must remain inside this project.
        if not evidence.is_dir(): parser.error(f'evidence directory missing: {evidence}')
        for path in evidence.rglob('*'):
            if any(part.startswith('source-') for part in path.relative_to(evidence).parts):
                continue
            if path.is_file() and path.suffix in ['.json','.sgf','.cfg','.txt']:
                files[path.relative_to(ROOT).as_posix()]=path
    for snapshot in args.snapshot:
        snapshot = snapshot.resolve()
        snapshot.relative_to(ROOT)
        if not snapshot.is_dir(): parser.error(f'snapshot directory missing: {snapshot}')
        for path in snapshot.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = path
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(files.items()): archive.write(path,name)
        archive.writestr('BUNDLE-MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
        for name,expected in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==expected
    args.output.with_suffix('.sha256').write_text(hashlib.sha256(args.output.read_bytes()).hexdigest()+'\n',encoding='ascii')
    print('Verified bundle:',args.output,'files:',len(manifest))


if __name__=='__main__': main()

"""Restore the directory layout from the flat files of the Secret Gist."""
from pathlib import Path
import argparse,hashlib,json,shutil

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='ConferenceDirector-Recovered')
    args=parser.parse_args()
    base=Path(__file__).resolve().parent
    rows=json.loads((base/'project-files.json').read_text(encoding='utf-8'))['files']
    target=Path(args.output).resolve()
    if target.exists():raise SystemExit('Output directory already exists; choose a new --output directory.')
    prepared=[]
    for row in rows:
        source=(base/row['gist_file']).resolve()
        dest=(target/row['project_path']).resolve()
        if not source.is_relative_to(base) or not dest.is_relative_to(target):raise SystemExit('Unsafe path in manifest')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:raise SystemExit('Checksum mismatch: '+row['gist_file'])
        prepared.append((source,dest))
    target.mkdir(parents=True,exist_ok=False)
    for source,dest in prepared:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
    print('Restored',len(prepared),'files to',target)

if __name__=='__main__':main()

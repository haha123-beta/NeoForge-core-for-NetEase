"""NeoCore 0.9.8 compatibility mining CLI; no input JAR is executed."""
import argparse,json,sys
from pathlib import Path
from tools.compat_mining098.engine import scan,compare,save,load

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    q=s.add_parser('fetch-modrinth');q.add_argument('--output',required=True,type=Path);q.add_argument('--count',type=int,default=100);q.add_argument('--max-mb',type=int,default=20)
    q=s.add_parser('scan');q.add_argument('inputs',nargs='+',type=Path);q.add_argument('--output',required=True,type=Path)
    q.add_argument('--cache',type=Path);q.add_argument('--reports',nargs='*',type=Path,default=[]);q.add_argument('--weights',type=Path)
    q=s.add_parser('compare');q.add_argument('before',type=Path);q.add_argument('after',type=Path);q.add_argument('--output',required=True,type=Path)
    q=s.add_parser('propose');q.add_argument('run',type=Path);q.add_argument('--output',required=True,type=Path)
    q=s.add_parser('validate-patch');q.add_argument('proposal',type=Path);q.add_argument('--apply',action='store_true')
    q=s.add_parser('observe');q.add_argument('run',type=Path);q.add_argument('--backend',required=True,type=Path);q.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.command=='fetch-modrinth':
        from tools.compat_mining098.corpus import fetch
        r=fetch(a.output,a.count,a.max_mb);print(json.dumps(r,ensure_ascii=True));return 0 if r['status']=='FETCHED' else 2
    if a.command=='scan':
        r=scan(a.inputs,a.output,a.cache,a.reports,load(a.weights) if a.weights else None,lambda r:print(json.dumps(r,ensure_ascii=True),flush=True))
        print(json.dumps(r['summary'],ensure_ascii=True));return 0 if r['status']=='PASSED' else 2
    if a.command=='compare':
        if a.output.exists():raise ValueError('Comparison output already exists')
        r=compare(a.before,a.after);save(a.output,r);print(r['status']);return 0
    if a.command=='propose':
        from tools.compat_mining098.patches import propose
        print(json.dumps(propose(a.run,a.output),ensure_ascii=True));return 0
    if a.command=='validate-patch':
        from tools.compat_mining098.patches import validate
        r=validate(a.proposal,a.apply);print(json.dumps(r,ensure_ascii=True));return 0 if r['status'].startswith('PASSED') else 2
    if a.command=='observe':
        from tools.compat_mining098.observe import observe
        r=observe(a.run,a.backend,a.output);print(json.dumps(r,ensure_ascii=True));return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError) as e:print(type(e).__name__+': '+str(e),file=sys.stderr);sys.exit(1)

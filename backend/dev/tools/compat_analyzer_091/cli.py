"""Independent Python 3.11+ analysis CLI. No installation in game Scripts."""
import argparse,hashlib,json,subprocess,sys,zlib
from pathlib import Path
from locking import VERSION,create_default,verify,load,save,digest
from abi import build,load_index
from analysis import analyze
from ranking import rank
from reporting import write_html

def source_hashes():return {p.name:digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',action='version',version=VERSION)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('lock-default');p.add_argument('output',type=Path)
    p=sub.add_parser('verify');p.add_argument('lock',type=Path)
    p=sub.add_parser('analyze');p.add_argument('lock',type=Path);p.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.command=='lock-default':
        if args.output.exists():raise ValueError('Lock exists; never silently rebaseline')
        create_default(args.output);print('LOCKED');return 0
    lock=load(args.lock);verify(lock)
    if args.command=='verify':print('INPUTS_AND_FROZEN_PRODUCTION_VERIFIED');return 0
    args.output.mkdir(exist_ok=False,parents=True)
    save(args.output/'versions.lock.json',lock)
    source_before=source_hashes();lock_before=digest(args.lock)
    manifest={'version':VERSION,'status':'RUNNING','lock_sha256':digest(args.lock),'engine_verified':False,
        'analysis_environment':{'python':sys.version,'executable':sys.executable,'zlib':zlib.ZLIB_VERSION,'stdlib_only_analyzer':True,
            'cfr_cst_probe':'explicit subprocess using frozen 0.9.0 parser; not installed into runtime'}}
    target=args.output/'run_manifest.json';save(target,manifest)
    try:
        print('Indexing locked reference ABIs',flush=True)
        abi=build(lock,args.output/'official_abi.json.gz')
        print('Cross-checking CFR using frozen parser',flush=True)
        probe=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('cfr_probe.py')),str(args.lock),str(args.output/'cfr_index.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
        (args.output/'cfr_probe.log').write_text(probe.stdout+probe.stderr,encoding='utf-8')
        if probe.returncode:raise ValueError('CFR probe failed; see cfr_probe.log')
        graph=analyze(lock,abi,load(args.output/'cfr_index.json'));ranking=rank(graph)
        save(args.output/'analysis.json',graph);save(args.output/'ranking.json',ranking)
        write_html(args.output/'report.html',graph,ranking,lock)
        verify(lock)
        if source_hashes()!=source_before:raise ValueError('Analyzer source changed during run; results not accepted')
        if digest(args.lock)!=lock_before:raise ValueError('Version lock changed during run; results not accepted')
        manifest.update(status='PASSED',summary=graph['summary'],abi_types=len(abi['classes']),ambiguous_types=abi['ambiguous_types'],
            production_unchanged=True,inputs_unchanged=True,static_analysis_only=True,
            analyzer_sha256=source_before,analyzer_unchanged_during_run=True,
            outputs={p.name:digest(p) for p in sorted(args.output.iterdir()) if p.is_file() and p!=target})
        save(target,manifest);print(json.dumps(manifest['summary'],ensure_ascii=True));return 0
    except Exception as error:
        manifest.update(status='FAILED',error=str(error));save(target,manifest);raise

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError) as error:print('ANALYSIS_FAILED: '+str(error),file=sys.stderr);sys.exit(1)

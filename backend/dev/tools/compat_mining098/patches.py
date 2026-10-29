"""Closed, trusted recipes. Frequency never grants arbitrary source-writing power."""
from pathlib import Path
import concurrent.futures,hashlib,json,os,shutil,subprocess,sys,time,uuid
from .engine import DEV,load,save,digest,stable,profile

ADAPTER='''"""Validated mining recipe: Java21 Optional.ofNullable, reference subset only."""
def resolve(base,name,arity,actual):
    if base!='java.util.Optional' or name!='ofNullable' or arity!=1 or len(actual)!=1:return None
    kind=actual[0]
    if kind=='<null>':
        return dict(return_type='java.util.Optional',parameters=['java.lang.Object'],static_owner=base,
                    receiver_kind='game_api',checked_arguments=True,polymorphic_empty_optional=True)
    if not kind or kind in ('void','boolean','byte','short','char','int','long','float','double'):return None
    if '?' in kind or '<unknown>' in kind or ('.' not in kind and not kind.endswith('[]')):return None
    return dict(return_type='java.util.Optional<'+kind+'>',parameters=[kind],static_owner=base,
                receiver_kind='game_api',checked_arguments=True)
'''
TEST='''import sys,unittest,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_interfaces082 as oracle
from translate_java import translate
from harness import Package
class MinedOptional098(unittest.TestCase):
 def test_factory_translates_and_executes_java_python2_python3(self):
  oracle.Interfaces082().compare({'use/Run.java':\'''package use;import java.util.Optional;
public class Run {public int run(){Optional<String> a=Optional.ofNullable("value");
Optional<String> b=Optional.ofNullable(null);String v=null;Optional<String> c=Optional.ofNullable(v);
if(a==null||b==null||c==null)return -1;return 7;}}\'''},'7')
 def test_runtime_value_and_empty_semantics(self):
  o=Package().load('java_stdlib.util').JavaOptional
  self.assertFalse(o.ofNullable(None).isPresent());self.assertEqual(o.ofNullable('x').get(),'x')
 def test_generic_mismatch_and_primitive_subset_remain_blocked(self):
  for body in ['java.util.Optional<Integer> o=java.util.Optional.ofNullable("x");','Object o=java.util.Optional.ofNullable(1);','Object o=java.util.Optional.ofNullable("a","b");']:
   with tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'Run.java').write_text('class Run {void run(){'+body+'}}')
    r=translate(root,dry_run=True);self.assertEqual(r['manual_review'],1,r)
if __name__=='__main__':unittest.main()
'''

def hook(text):
    anchor='def resolve(base,name,arity,actual):\n'
    if text.count(anchor)!=1:raise ValueError('Reviewed compiler hook anchor differs')
    return text.replace(anchor,anchor+'    from mining_verified_adapters098 import resolve as mined_signature\n    mined=mined_signature(base,name,arity,actual)\n    if mined is not None:return mined\n',1)

def propose(run,output):
    run=Path(run)
    if (run/'ranking.json').exists():
        data=load(run/'ranking.json');data['profile_sha256']=data['profile']
    else:data=load(run/'run.json')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    key='api.member:java.util.Optional#ofNullable'
    g=next((g for g in data['groups'] if g['key']==key and g['tier']=='A' and g['descriptors']==['(Ljava/lang/Object;)Ljava/util/Optional;']),None)
    if not g:
        result=dict(status='NO_ELIGIBLE_REVIEWED_RECIPE',proposals=[],source_profile=data['profile_sha256']);save(out/'proposal.json',result);return result
    if profile()['sha256']!=data['profile_sha256']:raise ValueError('Scan profile differs; rescan before proposing')
    if (DEV/'mining_verified_adapters098.py').exists():raise ValueError('Recipe already installed; rescan instead of reapplying')
    original=(DEV/'java_existing_call_signatures.py').read_text(encoding='utf-8')
    files={'java_existing_call_signatures.py':hook(original),'mining_verified_adapters098.py':ADAPTER,'tests/test_mined_optional098.py':TEST}
    records=[]
    for name,content in files.items():
        p=DEV/name;target=out/'after'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8')
        records.append(dict(file=name,before_sha256=digest(p) if p.exists() else None,after_sha256=digest(target)))
        if p.exists():
            b=out/'before'/name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,b)
    result=dict(schema_version=1,status='REVIEWED_RECIPE_CANDIDATE',recipe='optional_ofNullable_reference_v1',capability=key,
                affected_mods=g['affected_mods'],files=records,source_profile=data['profile_sha256'],
                runtime_provider='Existing java_stdlib.util.JavaOptional.ofNullable; no duplicate runtime class',
                limitations=['No primitive boxing inference','No target-only generic inference except null-as-empty'],auto_applied=False)
    save(out/'proposal.json',result)
    import difflib
    patch=''
    for row in records:
        n=row['file'];before=(DEV/n).read_text(encoding='utf-8').splitlines(True) if row['before_sha256'] else []
        patch+=''.join(difflib.unified_diff(before,(out/'after'/n).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+n,tofile='after/'+n))
    (out/'candidate.patch').write_text(patch,encoding='utf-8')
    return result

def regression(stage,out):
    """Invoke in a separate interpreter so the cloned harness owns all imports."""
    source='''from pathlib import Path
import concurrent.futures,json,os,subprocess,sys,time
dev=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir();sys.path.insert(0,str(dev))
import run_selftest as core
from validation_report import source_fingerprint
from workspace_paths import PACK_ROOT
before=source_fingerprint(PACK_ROOT)
checks={name:fn() for name,fn in [('python2',core.run_py3only_lint),('whitelist',core.run_whitelist_lint),('keywords',core.run_keyword_lint),('api_coverage',core.run_api_coverage)]}
files=core.discover()+[str(p) for name in ['neocore_gui_090','neocore_gui_092'] for p in sorted((dev/'tools'/name).glob('test_*.py'))]
report=dict(status='RUNNING',total=len(files),files=[],static_issues=checks)
def save():(out/'regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
save();temp=dev.parent.parent/'validation_temp';temp.mkdir()
env=dict(os.environ,TEMP=str(temp),TMP=str(temp),PYTHONIOENCODING='utf-8',PYTHONUTF8='0',NEOCORE_PYTHON2=os.environ.get('NEOCORE_PYTHON2','D:/NeoCore工具/python27_validation/runtime/python.exe'))
def one(file):
 start=time.monotonic();p=subprocess.run([sys.executable,'-B',file],cwd=dev,env=env,capture_output=True)
 name=Path(file).parent.name+'_'+Path(file).stem+'.log';(out/name).write_bytes(p.stdout+p.stderr)
 return dict(file=str(Path(file).relative_to(dev)),exit_code=p.returncode,seconds=round(time.monotonic()-start,2),log=name)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for f in concurrent.futures.as_completed([pool.submit(one,p) for p in files]):
  row=f.result();report['files'].append(row);save()
  if row['exit_code'] or len(report['files'])%20==0:print(len(report['files']),len(files),row['file'],row['exit_code'],flush=True)
after=source_fingerprint(PACK_ROOT)
report['changed_during_run']=[k for k in set(before)|set(after) if before.get(k)!=after.get(k)]
report['status']='PASSED' if not report['changed_during_run'] and not any(checks.values()) and all(r['exit_code']==0 for r in report['files']) else 'FAILED'
save();print('FINAL',report['status'],flush=True);sys.exit(0 if report['status']=='PASSED' else 1)
'''
    runner=out.parent/'regression_runner.py';runner.write_text(source,encoding='utf-8')
    p=subprocess.run([sys.executable,'-B',str(runner),str(stage/'backend/dev'),str(out)],capture_output=True)
    (out.parent/'regression_runner.log').write_bytes(p.stdout+p.stderr)
    return p.returncode

def validate(proposal,apply=False):
    proposal=Path(proposal).resolve();data=load(proposal/'proposal.json')
    if data.get('recipe')!='optional_ofNullable_reference_v1':raise ValueError('No trusted recipe selected')
    expected={'java_existing_call_signatures.py':hook((DEV/'java_existing_call_signatures.py').read_text(encoding='utf-8')),
              'mining_verified_adapters098.py':ADAPTER,'tests/test_mined_optional098.py':TEST}
    if {r['file'] for r in data['files']}!=set(expected):raise ValueError('Unexpected patch targets')
    if profile()['sha256']!=data['source_profile']:raise ValueError('Compiler changed since proposal; rescan')
    for row in data['files']:
        name=row['file'];target=DEV/name;candidate=proposal/'after'/name
        if (digest(target) if target.exists() else None)!=row['before_sha256']:raise ValueError('Target changed since proposal')
        if candidate.read_text(encoding='utf-8')!=expected[name] or digest(candidate)!=row['after_sha256']:raise ValueError('Untrusted candidate content')
    work=proposal/'validation';work.mkdir(exist_ok=False)
    stage_root=Path(os.environ.get('NEOCORE_VALIDATION_ROOT',str(Path(DEV.anchor)/'NeoCoreValidation098'))).resolve()
    if not str(stage_root).isascii():raise ValueError('Legacy Python 2 reference probes need an ASCII NEOCORE_VALIDATION_ROOT path')
    stage_root.mkdir(parents=True,exist_ok=True);stage=stage_root/('candidate_'+uuid.uuid4().hex)
    save(work/'stage.json',dict(path=str(stage),retained_for_review=True,reason='ASCII paths required by legacy Python 2 imp probes; production paths are unchanged'))
    from .snapshot import snapshot
    snapshot(stage,validation_refs=True)
    for row in data['files']:
        p=stage/'backend/dev'/row['file'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(proposal/'after'/row['file'],p)
    test=stage/'backend/dev/tests/test_mined_optional098.py'
    process=subprocess.run([sys.executable,'-B',str(test)],capture_output=True,cwd=stage/'backend/dev',env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='0'))
    (work/'java_python2_python3.log').write_bytes(process.stdout+process.stderr)
    result=dict(status='FAILED_TARGETED',recipe=data['recipe'],applied=False,engine_verified=False)
    if process.returncode==0:
        code=regression(stage,work/'full_regression')
        result['status']='PASSED_VALIDATED' if code==0 else 'FAILED_REGRESSION'
        if code==0 and apply:
            if profile()['sha256']!=data['source_profile']:raise ValueError('Production changed during candidate validation')
            for row in data['files']:
                target=DEV/row['file']
                if (digest(target) if target.exists() else None)!=row['before_sha256']:raise ValueError('Production target changed')
            for row in data['files']:
                target=DEV/row['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(proposal/'after'/row['file'],target)
            result.update(status='PASSED_APPLIED',applied=True,applied_files=data['files'])
    save(work/'result.json',result);return result

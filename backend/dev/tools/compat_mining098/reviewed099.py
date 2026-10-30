"""Closed reviewed patch batches; candidates never define their own write rules."""
from pathlib import Path
import hashlib,json,sys,subprocess,os,shutil,difflib
from .engine import DEV,digest,load,save,profile,stable

CATALOG_SHA256='6ba83d2158981d19b9b0ee2019fd321d149ec4169c84faff1d0d6e631c7ce08e'
RECIPE='reviewed_foundations099_v1'

def catalog():
    path=Path(__file__).with_name('reviewed_patchset099.json')
    if digest(path)!=CATALOG_SHA256:raise ValueError('Reviewed catalog integrity mismatch')
    data=load(path)
    if data['recipe']!=RECIPE:raise ValueError('Unknown reviewed recipe')
    return data

def materialize(row,before):
    if (hashlib.sha256(before).hexdigest() if before is not None else None)!=row['before_sha256']:
        raise ValueError('Reviewed recipe baseline differs: '+row['file'])
    if before is None:after=row['content'].encode('utf-8')
    else:
        lines=before.decode('utf-8').splitlines(True)
        for change in reversed(row['edits']):lines[change['start']:change['end']]=change['replacement']
        after=''.join(lines).encode('utf-8')
    if hashlib.sha256(after).hexdigest()!=row['after_sha256']:raise ValueError('Reviewed recipe output differs: '+row['file'])
    return after

def reviewed_evidence(run):
    root=Path(run)
    data=load(root/'ranking.json' if (root/'ranking.json').exists() else root/'run.json')
    groups=[g for g in data.get('groups',[]) if g['key']=='java.unicode_prelexing' and g.get('observed_blocked_mods',0)>0]
    if not groups:raise ValueError('Reviewed foundations recipe requires observed Unicode blockers; static frequency is insufficient')
    return dict(path=str(root.resolve()),ranking_sha256=digest(root/'ranking.json' if (root/'ranking.json').exists() else root/'run.json'),
        source_profile=data.get('profile_sha256') or data.get('profile'),
        observed_blocked_mods=groups[0]['observed_blocked_mods'],
        scope='Historical observations reused only with exact pinned compiler before hashes; no static-to-generation gain claim')

def propose(run,output):
    rules=catalog();evidence=reviewed_evidence(run);prepared=[];installed=[]
    for row in rules['files']:
        target=DEV/row['file'];current=target.read_bytes() if target.exists() else None
        sha=hashlib.sha256(current).hexdigest() if current is not None else None
        if sha==row['after_sha256']:installed.append(row['file']);continue
        after=materialize(row,current);prepared.append((row,current,after))
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=profile();patch='';records=[]
    for row,before,after in prepared:
        relative=row['file'];destination=out/'after'/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(after)
        if before is not None:
            backup=out/'before'/relative;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(before)
        records.append({k:row[k] for k in ('file','before_sha256','after_sha256')})
        patch+=''.join(difflib.unified_diff((before or b'').decode('utf-8').splitlines(True),after.decode('utf-8').splitlines(True),fromfile='before/'+relative,tofile='after/'+relative))
    result=dict(schema_version=2,recipe=RECIPE,status='REVIEWED_BATCH_CANDIDATE' if prepared else 'ALREADY_INSTALLED',
        files=records,already_installed=installed,catalog_sha256=CATALOG_SHA256,source_profile=source['sha256'],evidence=evidence,
        targeted_tests=rules['targeted_tests'],capabilities=rules['capabilities'],auto_applied=False,engine_verified=False)
    (out/'candidate.patch').write_text(patch,encoding='utf-8');save(out/'proposal.json',result);return result

def checked(proposal):
    rules=catalog();data=load(Path(proposal)/'proposal.json')
    if data.get('recipe')!=RECIPE or data.get('catalog_sha256')!=CATALOG_SHA256:raise ValueError('Unknown reviewed proposal or catalog')
    expected={r['file']:r for r in rules['files']};records=data.get('files',[])
    if len({r.get('file') for r in records})!=len(records) or set(r.get('file') for r in records)|set(data.get('already_installed',[]))!=set(expected):raise ValueError('Unexpected reviewed patch targets')
    if profile()['sha256']!=data['source_profile']:raise ValueError('Compiler changed since reviewed proposal')
    for row in records:
        rule=expected[row['file']]
        if row!={k:rule[k] for k in ('file','before_sha256','after_sha256')}:raise ValueError('Untrusted proposed hashes')
        p=DEV/row['file'];before=p.read_bytes() if p.exists() else None;after=materialize(rule,before)
        if (Path(proposal)/'after'/row['file']).read_bytes()!=after:raise ValueError('Untrusted candidate content')
    for relative in data.get('already_installed',[]):
        if digest(DEV/relative)!=expected[relative]['after_sha256']:raise ValueError('Installed source changed')
    if data.get('targeted_tests')!=rules['targeted_tests']:raise ValueError('Candidate cannot choose validation commands')
    evidence=data['evidence'];current=reviewed_evidence(evidence['path'])
    if current!=evidence:raise ValueError('Observation evidence changed')
    return data

def validate(proposal,apply=False):
    proposal=Path(proposal).resolve();data=checked(proposal)
    if not data['files']:return dict(status='ALREADY_INSTALLED',applied=False)
    work=proposal/'validation';work.mkdir(exist_ok=False)
    stage=work/'candidate'
    if not str(stage).isascii():raise ValueError('Python 2 probes require an ASCII candidate path')
    from .snapshot import snapshot
    snapshot(stage,validation_refs=True,reuse_dependencies=True)
    for row in data['files']:
        p=stage/'backend/dev'/row['file'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(proposal/'after'/row['file'],p)
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='0');targeted=[]
    def candidate_profile():
        process=subprocess.run([sys.executable,'-B','-c','import json;from tools.compat_mining098.engine import profile;print(json.dumps(profile(),ensure_ascii=True))'],cwd=stage/'backend/dev',env=env,capture_output=True)
        if process.returncode:raise ValueError('Candidate source profile could not be verified')
        return json.loads(process.stdout)
    expected=candidate_profile();save(work/'candidate_source_before.json',expected)
    for relative in catalog()['targeted_tests']:
        p=subprocess.run([sys.executable,'-B',str(stage/'backend/dev'/relative)],cwd=stage/'backend/dev',env=env,capture_output=True)
        log=relative.replace('/','_')+'.log';(work/log).write_bytes(p.stdout+p.stderr);targeted.append(dict(test=relative,exit_code=p.returncode,log=log))
    save(work/'targeted.json',targeted)
    result=dict(status='FAILED_TARGETED',applied=False,engine_verified=False,dependency_reuse=True)
    if all(r['exit_code']==0 for r in targeted):
        from .patches import regression
        code=regression(stage,work/'full_regression')
        result['status']='PASSED_VALIDATED' if code==0 else 'FAILED_REGRESSION'
        final=candidate_profile();save(work/'candidate_source_after.json',final)
        changed=[k for k in set(expected['source_files'])|set(final['source_files']) if expected['source_files'].get(k)!=final['source_files'].get(k)]
        result['candidate_changed_during_validation']=changed
        if changed:result['status']='FAILED_CANDIDATE_SOURCE_CHANGED'
        if code==0 and not changed and apply:
            checked(proposal)
            # Validate the complete write set before changing any file.
            for row in data['files']:
                p=DEV/row['file'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(proposal/'after'/row['file'],p)
            result.update(status='PASSED_APPLIED',applied=True,applied_files=data['files'])
    save(work/'result.json',result);return result

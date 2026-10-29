"""Content-addressed, bounded JAR mining. Input bytecode is never executed."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,tomllib,zipfile
from . import VERSION
from .capabilities import canonical,OFFICIAL,aggregate,identify,feature_for_owner

DEV=Path(__file__).resolve().parents[2]
MAX_JAR=512*1024*1024
MAX_CLASS=8*1024*1024
MAX_TOTAL=1024*1024*1024
MAX_ENTRIES=50000
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def stable(x):
    h=hashlib.sha256()
    for part in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=True).iterencode(x):h.update(part.encode())
    return h.hexdigest()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
    tmp.replace(p)
def load(p):
    with Path(p).open('r',encoding='utf-8-sig') as f:return json.load(f)

def profile():
    from workspace_paths import PACK_ROOT
    from validation_report import source_fingerprint
    files=source_fingerprint(PACK_ROOT)
    for p in (DEV/'profiles').glob('*.json'):files['profiles/'+p.name]=digest(p)
    for p in (DEV/'tools/neocore_gui_092').glob('*.py'):files['workbench/'+p.name]=digest(p)
    for p in Path(__file__).parent.glob('*.py'):files['mining/'+p.name]=digest(p)
    files['reader/classfile.py']=digest(DEV/'tools/compat_analyzer_091/classfile.py')
    index=load(DEV/'java_import_index.json')
    core=Path(PACK_ROOT)/'NeoForgeCoreScripts'
    stale=[n for n,h in index.get('runtime_sha256',{}).items() if not (core/n).is_file() or digest(core/n)!=h]
    if stale:raise ValueError('Runtime API index is stale; regenerate before mining')
    return dict(version=VERSION,source_files=files,sha256=stable(files),analysis_sha256=stable({k:v for k,v in files.items() if k.startswith(('mining/','reader/'))}),
                mapped_types=sorted({canonical(n) for n in index['java_types']}),
                limitations=['Missing call metadata is a static suspect, not proof of missing runtime behavior.',
                             'First compiler diagnostics do not expose the rest of a blocked file.'])

def discover(inputs):
    paths=[];missing=[]
    for item in inputs:
        p=Path(item).resolve()
        if p.is_dir():paths.extend(x for x in p.rglob('*.jar') if x.is_file() and not x.is_symlink())
        elif p.is_file() and p.suffix.lower()=='.jar':paths.append(p)
        else:missing.append(dict(path=str(p),error='INPUT_NOT_FOUND_OR_NOT_JAR'))
    return sorted(set(paths),key=lambda p:str(p).casefold()),missing

def metadata(z):
    names=set(z.namelist())
    def raw(n):
        if z.getinfo(n).file_size>2*1024*1024:raise ValueError('Oversize mod metadata')
        return z.read(n).decode('utf-8-sig')
    for n,loader in [('META-INF/neoforge.mods.toml','neoforge'),('META-INF/mods.toml','forge')]:
        if n in names:
            d=tomllib.loads(raw(n));mods=d.get('mods',[])
            ids=sorted({m['modId'] for m in mods if isinstance(m.get('modId'),str)})
            if not ids:raise ValueError('Mod metadata has no modId')
            deps=[]
            for rows in d.get('dependencies',{}).values():
                for row in rows:
                    if isinstance(row,dict):deps.append(dict(id=row.get('modId'),version=row.get('versionRange'),type=row.get('type'),mandatory=row.get('mandatory')))
            return dict(loader=loader,mod_ids=ids,logical_mod=loader+':'+','.join(ids),
                        versions=[str(m.get('version','UNKNOWN')) for m in mods],dependencies=deps,metadata_path=n)
    if 'fabric.mod.json' in names:
        d=json.loads(raw('fabric.mod.json'));name=d.get('id')
        if not isinstance(name,str) or not name:raise ValueError('Fabric metadata has no id')
        return dict(loader='fabric',mod_ids=[name],logical_mod='fabric:'+name,versions=[str(d.get('version','UNKNOWN'))],dependencies=d.get('depends',{}),metadata_path='fabric.mod.json')
    return None

def analyze_jar(path,prof):
    from tools.compat_analyzer_091.classfile import read,descriptor
    from java_library_signatures import resolve,resolve_field
    result=dict(status='ANALYZED',findings=[],classes=0,source_files=[],unknown_classes=[],nested_jars=[])
    with zipfile.ZipFile(path) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(infos)>MAX_ENTRIES or len(names)!=len(set(names)):raise ValueError('ZIP entry limit or duplicate names')
        if sum(i.file_size for i in infos)>MAX_TOTAL:raise ValueError('ZIP expanded size limit')
        if any(i.flag_bits&1 for i in infos):raise ValueError('Encrypted ZIP entries unsupported')
        meta=metadata(z);result['metadata']=meta
        if meta is None:result['status']='EXCLUDED_NON_MOD_ARTIFACT';return result
        if any(n.endswith('.java') for n in names) and not any(n.endswith('.class') for n in names):
            result.update(status='EXCLUDED_SOURCE_ARCHIVE',metadata=None,source_metadata=meta)
            return result
        logical=meta['logical_mod'];mapped=set(prof['mapped_types'])
        manifest=z.read('META-INF/MANIFEST.MF').decode('utf-8',errors='replace') if 'META-INF/MANIFEST.MF' in names and z.getinfo('META-INF/MANIFEST.MF').file_size<2*1024*1024 else ''
        multi='multi-release: true' in manifest.lower();chosen={}
        for info in infos:
            name=info.filename
            if name.endswith('.jar'):result['nested_jars'].append(dict(entry=name,bytes=info.file_size))
            if not name.endswith('.class'):continue
            level=0
            if name.startswith('META-INF/versions/'):
                bits=name.split('/',3)
                if not multi or len(bits)!=4 or not bits[2].isdigit():continue
                level=int(bits[2]);name=bits[3]
                if level>21:continue
            if name=='module-info.class':continue
            if level>chosen.get(name,(-1,None))[0]:chosen[name]=(level,info)
        own={canonical(n[:-6].replace('/','.')) for n in chosen}
        seen=set();sources=set()
        def add(file,reason,details,evidence='STATIC_SUSPECT',line=None,**extra):
            row=dict(file=file,reason=reason,details=details,evidence=evidence,line=line,**extra)
            key=(file,identify(row)['key'],details.get('descriptor'),line,extra.get('class_name'))
            if key not in seen:seen.add(key);result['findings'].append(row)
        if meta['loader']!='neoforge':add(meta['metadata_path'],'Target converter accepts NeoForge Java modules',dict(capability='platform.loader',loader=meta['loader']),evidence='PROFILE_BOUNDARY')
        if any('mixin' in n.lower() and n.endswith('.json') for n in names):
            for n in names:
                if 'mixin' in n.lower() and n.endswith('.json'):
                    add(n,'Mixin configuration requires semantic port',dict(capability='jvm.mixin'),evidence='STATIC_REQUIREMENT')
        for name,(_,info) in sorted(chosen.items()):
            if info.file_size>MAX_CLASS:
                result['unknown_classes'].append(dict(entry=name,error='CLASS_SIZE_LIMIT'));continue
            try:row=read(z.read(info),code=True)
            except (ValueError,IndexError,KeyError,UnicodeError,RecursionError) as e:
                result['unknown_classes'].append(dict(entry=name,error=type(e).__name__+': '+str(e)));continue
            result['classes']+=1
            file=row['name'].rsplit('.',1)[0].replace('.','/')+'/'+row.get('source_file',row['name'].rsplit('.',1)[-1]+'.java') if '.' in row['name'] else row.get('source_file',name)
            sources.add(file)
            parent=row.get('superclass')
            if parent and ('L'+parent.replace('.','/')+'<') in row.get('signature',''):
                add(file,'Parameterized superclass requires substitution review',dict(capability='java.generic_superclass_substitution',parent=parent,signature=row['signature']),class_name=row['name'])
            if row['major']>65:add(file,'Class targets a later Java version than the selected Java 21 profile',dict(capability='platform.version',major=row['major']))
            if 'record_components' in row and ('$' in row['name'] or row.get('enclosing_method')):
                add(file,'Nested record requires owner/generic lowering',dict(capability='java.nested_record',signature=row.get('signature')),class_name=row['name'])
            elif 'record_components' in row:
                add(file,'Record requires reviewed structural lowering',dict(capability='java.generic_record' if row.get('signature','').startswith('<') else 'java.simple_record'),class_name=row['name'])
            for member in row['methods']:
                if member['access']&0x120: # synchronized or native
                    add(file,'Native/synchronized method requires JVM semantics',dict(capability='jvm.concurrency',method=member['name'],descriptor=member['descriptor']),class_name=row['name'])
            for owner in row['type_references']:
                owner=canonical(owner)
                if owner in own or owner in mapped or owner.startswith('['):continue
                add(file,'Referenced type absent from selected runtime type index',dict(category='EXTERNAL_ABI_REQUIRED',symbol=owner),class_name=row['name'])
            calls=[]
            for call in row['calls']:
                if call.get('target'):calls.append(call)
                for handle in call.get('dynamic',{}).get('method_handles',[]):
                    calls.append(dict(call,target=handle))
            for call in calls:
                target=call.get('target') or call.get('method_handle')
                if not target:continue
                owner=canonical(target['owner']);method=target['name'];desc=target['descriptor']
                if owner in own or method in ('<init>','<clinit>'):continue
                if not owner.startswith(OFFICIAL) and not owner.startswith('org.spongepowered.asm.'):continue
                detail=dict(category='REVIEWED_API_CONTRACT_MISSING',owner=owner,method=method,descriptor=desc,opcode=call['opcode'])
                known=None
                if owner in mapped:
                    try:
                        if target['kind']=='field':known=resolve_field(owner,method,canonical)
                        else:
                            args=descriptor(desc)['parameters'];known=resolve(owner,method,len(args),args,canonical)
                    except (ValueError,KeyError,TypeError,IndexError):known=None
                if not known:add(file,'Call contract not confirmed by conservative metadata probe',detail,line=call.get('line'),class_name=row['name'])
        result['source_files']=sorted(sources)
        result['complete_static_read']=not result['unknown_classes']
        result['raw_findings']=len(result['findings'])
    return result

def import_reports(paths,artifacts,prof):
    findings=[];observations=[];errors=[];by_sha={a['sha256']:a for a in artifacts if a.get('metadata')}
    seen=set()
    expanded=[]
    for p in paths:
        p=Path(p);expanded.extend(sorted(p.glob('*_report.json')) if p.is_dir() else [p])
    for path in expanded:
        try:
            doc=load(path);report=doc.get('result',doc);sha=report.get('input_sha256')
            if sha not in by_sha:
                errors.append(dict(report=str(path),reason='INPUT_SHA_NOT_IN_COHORT'));continue
            source=report.get('backend_source_sha256',{});current=bool(source) and all(prof['source_files'].get(k)==v for k,v in source.items())
            reports=doc.get('source_reports',[])
            rows=[r for s in reports for r in s.get('results',[])] or report.get('diagnostics',[])
            artifact=by_sha[sha];logical=artifact['metadata']['logical_mod']
            for r in rows:
                if r.get('status') not in ('MANUAL_REVIEW','FAILED'):continue
                r=dict(r,artifact_sha256=sha,logical_mod=logical,evidence='OBSERVED_BLOCKER' if current else 'HISTORICAL_BLOCKER',report=str(path),profile_current=current)
                k=(sha,r.get('file'),identify(r)['key'],r.get('line'))
                if k not in seen:seen.add(k);findings.append(r)
            tr=report.get('translation')
            for blocker in (tr or {}).get('capability_blockers',[]):
                kind=blocker.get('kind')
                f=dict(file=blocker.get('source') or '<package>',reason=blocker.get('message') or blocker.get('category','package requirement'),
                    details=dict(capability='jvm.mixin') if kind=='mixin' else dict(category=blocker.get('category')),
                    artifact_sha256=sha,logical_mod=logical,evidence='OBSERVED_BLOCKER' if current else 'HISTORICAL_BLOCKER',report=str(path),profile_current=current)
                k=(sha,f['file'],identify(f)['key'],None)
                if k not in seen:seen.add(k);findings.append(f)
            if tr is not None:observations.append(dict(artifact_sha256=sha,logical_mod=logical,profile_current=current,translation=tr,report=str(path)))
        except (OSError,ValueError,KeyError,TypeError) as e:errors.append(dict(report=str(path),reason=type(e).__name__+': '+str(e)))
    return findings,observations,errors

def scan(inputs,output,cache=None,reports=(),weights=None,progress=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    prof=profile();save(output/'profile.json',prof)
    paths,errors=discover(inputs);artifacts=[];aliases={};cache_hits=0
    run=dict(version=VERSION,status='RUNNING',input_paths=[str(p) for p in paths],profile_sha256=prof['sha256'],analysis_profile_sha256=prof['analysis_sha256'],errors=errors)
    save(output/'run.json',run)
    for i,p in enumerate(paths):
        if progress:progress(dict(done=i,total=len(paths),name=p.name))
        try:
            if p.stat().st_size>MAX_JAR:raise ValueError('JAR size limit')
            sha=digest(p)
            if sha in aliases:aliases[sha]['aliases'].append(str(p));continue
            key=stable(dict(input=sha,profile=prof['sha256'],java_target=21,limits=[MAX_CLASS,MAX_JAR,MAX_TOTAL,MAX_ENTRIES]))
            cp=Path(cache)/key[:2]/(key+'.json') if cache else None
            hit=False
            if cp and cp.exists():
                try:
                    envelope=load(cp);data=envelope['result']
                    if envelope['key']==key and envelope['result_sha256']==stable(data):hit=True
                except (OSError,ValueError,KeyError,TypeError):pass
            if not hit:
                data=analyze_jar(p,prof)
                if cp:save(cp,dict(key=key,result=data,result_sha256=stable(data)))
            else:cache_hits+=1
            if digest(p)!=sha:raise ValueError('INPUT_CHANGED_DURING_SCAN')
            artifact=dict(data,sha256=sha,path=str(p),aliases=[str(p)],cache_hit=hit)
            artifacts.append(artifact);aliases[sha]=artifact
        except (OSError,ValueError,zipfile.BadZipFile,RuntimeError,RecursionError) as e:
            errors.append(dict(path=str(p),error=type(e).__name__+': '+str(e)))
    for a in artifacts:
        for alias in a['aliases']:
            try:
                if digest(Path(alias))!=a['sha256']:errors.append(dict(path=alias,error='INPUT_CHANGED_AFTER_SCAN'))
            except OSError as e:errors.append(dict(path=alias,error='INPUT_CHANGED_AFTER_SCAN: '+str(e)))
    findings=[]
    for a in artifacts:
        if not a.get('metadata'):continue
        for f in a.pop('findings'):
            f.update(artifact_sha256=a['sha256'],logical_mod=a['metadata']['logical_mod']);findings.append(f)
    observed,observations,report_errors=import_reports(reports,artifacts,prof);findings.extend(observed)
    groups=aggregate(findings,artifacts,weights)
    unchanged=profile()['sha256']==prof['sha256']
    current={};conflicted=set()
    for o in observations:
        if not o['profile_current']:continue
        h=o['artifact_sha256']
        if h in conflicted:continue
        if h in current and current[h]['translation']!=o['translation']:
            errors.append(dict(artifact=h,error='CONFLICTING_CURRENT_COMPILER_REPORTS'));current.pop(h,None);conflicted.add(h)
        else:current[h]=o
    unknown=sum(len(a.get('unknown_classes',[])) for a in artifacts)
    run.update(status='PASSED' if unchanged and not errors and not unknown and not report_errors else 'PARTIAL',
        inputs_unchanged=not any('CHANGED' in e.get('error','') for e in errors),profile_unchanged=unchanged,
        artifacts=artifacts,groups=groups,observations=list(current.values()),report_errors=report_errors,
        summary=dict(input_paths=len(paths),unique_artifacts=len(artifacts),duplicate_paths=len(paths)-len(artifacts)-len([e for e in errors if 'path' in e]),
            mod_artifacts=sum(bool(a.get('metadata')) for a in artifacts),logical_mods=len({a['metadata']['logical_mod'] for a in artifacts if a.get('metadata')}),
            excluded_non_mod=sum(not a.get('metadata') for a in artifacts),class_files=sum(a.get('classes',0) for a in artifacts),
            raw_findings=len(findings),unique_capabilities=len(groups),unknown_classes=unknown,cache_hits=cache_hits,
            observed_current_reports=len(current),observed_first_blockers=sum(r['evidence']=='OBSERVED_BLOCKER' for r in findings)),
        evidence_limits=['Static suspects and historical diagnostics are separate from current observed blockers.',
                         'Priority measures potential reach, not successful ports; counts deduplicate artifact aliases and mod versions.',
                         'Bytecode scan does not discover every Java inference failure or prove runtime execution.',
                         'Network, native, Mixin and reflection semantics are never auto-patched from frequency alone.'],engine_verified=False)
    save(output/'run.json',run)
    run_sha=digest(output/'run.json')
    header={k:run[k] for k in ('version','status','profile_sha256','analysis_profile_sha256','summary','errors','report_errors','inputs_unchanged','profile_unchanged','engine_verified')}
    save(output/'summary.json',header)
    save(output/'cohort.json',dict(header,artifacts=artifacts,run_sha256=run_sha))
    unique={(g['key'],r['artifact_sha256'],r['file'],r['evidence']) for g in groups for r in g['occurrences']}
    save(output/'comparison_basis.json',dict(header,run_sha256=run_sha,
        artifacts=[dict(sha256=a['sha256'],metadata=a.get('metadata')) for a in artifacts],
        observations=run['observations'],findings=sorted(unique)))
    del unique
    from .report import write_outputs
    if progress:progress(dict(done=len(paths),total=len(paths),name='正在生成能力排名与任务包'))
    write_outputs(output,run)
    if progress:progress(dict(done=len(paths),total=len(paths),status=run['status']))
    return run

def compare(before,after):
    def basis(root):
        root=Path(root);p=root/'comparison_basis.json'
        if not p.exists():return load(root/'run.json')
        data=load(p)
        if digest(root/'run.json')!=data['run_sha256']:raise ValueError('Comparison basis no longer matches raw evidence')
        return data
    a=basis(before);b=basis(after)
    aa={x['sha256'] for x in a['artifacts'] if x.get('metadata')};bb={x['sha256'] for x in b['artifacts'] if x.get('metadata')};common=aa&bb
    if any(run.get('status','PASSED')!='PASSED' for run in (a,b)):
        return dict(schema_version=1,status='INCOMPLETE_RUN_NO_GAIN_CLAIM',matched_artifacts=len(common),
            before_status=a.get('status'),after_status=b.get('status'),measured_translation=[],
            static_cleared_is_not_compilation_gain=True,engine_verified=False)
    if a.get('analysis_profile_sha256')!=b.get('analysis_profile_sha256'):
        return dict(schema_version=1,status='ANALYSIS_RULES_CHANGED_NO_GAIN_CLAIM',matched_artifacts=len(common),measured_translation=[],
            static_cleared_is_not_compilation_gain=True,engine_verified=False)
    def keys(run):
        if 'findings' in run:return {tuple(r) for r in run['findings'] if r[1] in common}
        return {(g['key'],r['artifact_sha256'],r['file'],r['evidence']) for g in run['groups'] for r in g['occurrences'] if r['artifact_sha256'] in common}
    ka,kb=keys(a),keys(b)
    observed_a={r['artifact_sha256']:r['translation'] for r in a['observations']};observed_b={r['artifact_sha256']:r['translation'] for r in b['observations']}
    measured=[]
    for h in sorted(common & observed_a.keys() & observed_b.keys()):
        x,y=observed_a[h],observed_b[h]
        if x['files']!=y['files']:
            measured.append(dict(artifact=h,status='DENOMINATOR_CHANGED_NO_GAIN_CLAIM'));continue
        measured.append(dict(artifact=h,status='MATCHED_DENOMINATOR',files=x['files'],
                             generated_before=x['generated_for_review'],generated_after=y['generated_for_review'],
                             generated_delta=y['generated_for_review']-x['generated_for_review']))
    return dict(schema_version=1,status='COMPARABLE' if common else 'NO_COMMON_COHORT',matched_artifacts=len(common),
        added_artifacts=sorted(bb-aa),removed_artifacts=sorted(aa-bb),profiles_differ=a['profile_sha256']!=b['profile_sha256'],
        cleared_findings=[list(x) for x in sorted(ka-kb)],new_findings=[list(x) for x in sorted(kb-ka)],
        measured_translation=measured,static_cleared_is_not_compilation_gain=True,engine_verified=False)

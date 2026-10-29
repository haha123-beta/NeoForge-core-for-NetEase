"""Content-owned translated dependency ABI manifests; no library types enter core."""
import ast,hashlib,json,re
from pathlib import Path,PurePosixPath
from java_frontend import isolated_parse,api_index
from java_project_types import add_unit

SCHEMA=1
HARD_OPERATIONS={'inheritance','override','overload','constructor','interface_contract'}

def export(source,translation,source_jar,version,dependency_id,neocore_abi,generated_root,use_parser_worker=True):
    """Export identical ABI metadata using a bounded, task-local parser process.

    The isolated path remains available for independent equivalence checks.
    No declarations or implementation-availability guards are bypassed.
    """
    source=Path(source).resolve()
    def snapshot():
        return {p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(source.rglob('*.java'))}
    before=snapshot()
    arguments=(source,translation,source_jar,version,dependency_id,neocore_abi,generated_root)
    if use_parser_worker:
        from java_parser_worker import ParserWorker
        context=dict(source=before,source_jar_sha256=hashlib.sha256(Path(source_jar).read_bytes()).hexdigest(),
                     version=version,dependency_id=dependency_id,neocore_abi=neocore_abi,
                     rules={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ('java_frontend.py','java_parser_worker.py','java_import_index.json','dependency_abi.py')})
        key=hashlib.sha256(json.dumps(context,sort_keys=True).encode('utf-8')).hexdigest()
        with ParserWorker(key) as worker:result=_export(*arguments,parser_backend=worker.parse)
    else:result=_export(*arguments,parser_backend=isolated_parse)
    if snapshot()!=before:raise ValueError('Dependency ABI source changed during export')
    return result

def _export(source,translation,source_jar,version,dependency_id,neocore_abi,generated_root,parser_backend):
    source=Path(source).resolve();source_jar=Path(source_jar).resolve()
    generated_root=Path(generated_root).resolve()
    if not re.fullmatch(r'[a-z][a-z0-9_.-]*',dependency_id):raise ValueError('Invalid dependency identity')
    if not isinstance(version,str) or not version:raise ValueError('Dependency version is required')
    if type(neocore_abi) is not int or neocore_abi<1:raise ValueError('NeoCore ABI version is required')
    known,stale=api_index()
    if stale:raise ValueError('Core ABI index is stale')
    records={};results={r['file']:r for r in translation['results']};export_issues=[]
    paths=sorted(source.rglob('*.java'))
    for number,path in enumerate(paths):
        relative=path.relative_to(source).as_posix()
        try:
            from translation_observer import call as observed
            ir=observed('dependency_abi_parse',parser_backend,path.read_bytes(),relative,known,
                        observation=dict(file=relative,processed=number,total=len(paths)))
            add_unit(records,ir)
        except ValueError as error:
            export_issues.append({'file':relative,'reason':str(error),'status':'ABI_UNAVAILABLE'})
    types={}
    for identity,entries in records.items():
        if len(entries)!=1:raise ValueError('Ambiguous dependency symbol: '+identity)
        record=entries[0];row=results.get(record['file'],{});generated=row.get('status')=='GENERATED_REVIEW_REQUIRED'
        if generated and row.get('source_sha256')!=record['source_sha256']:raise ValueError('Translated source changed: '+identity)
        metadata=record['inheritance_metadata'];module=generated_root/Path(record['file']).with_suffix('.py')
        if generated and not module.is_file():raise ValueError('ABI export requires the physical translated module: '+identity)
        raw=module.read_bytes() if module.is_file() else None
        exported=raw is not None and any(isinstance(n,ast.ClassDef) and n.name==record['attribute_chain'][0] for n in ast.parse(raw).body)
        available=generated and exported and not translation.get('capability_blockers') and not row.get('missing_generated_dependencies') and not any(s.get('deferred') for s in row.get('external_symbols',[]))
        constructors=[m for m in metadata['methods'] if m['constructor']]
        if not constructors and record['kind']=='class_declaration':constructors=[{'name':record['attribute_chain'][0],'parameters':[],'modifiers':['public'] if 'public' in metadata['modifiers'] else [],'implicit':True}]
        types[identity]={'package':metadata.get('package'),'kind':'record' if metadata.get('record_components') is not None else record['kind'],'superclass':metadata.get('superclass'),
            'interfaces':metadata.get('interfaces') or metadata.get('interface_extends'),'generic_signature':metadata.get('type_parameters'),
            'methods':[m for m in metadata['methods'] if not m['constructor']],
            'constructors':constructors, 'fields':metadata['fields'],
            'implementation_status':row.get('status','UNTRANSLATED'),'implementation_available':available,'abi_complete':generated,
            'source_record':record,'runtime_module':record['module'],'source_sha256':record['source_sha256'],
            'python_sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None,
            'missing_generated_dependencies':row.get('missing_generated_dependencies',[])}
    unavailable={row['source_record']['file'] for row in types.values() if not row['implementation_available']}
    changed=True
    while changed:
        changed=False
        for row in types.values():
            file=row['source_record']['file']
            if file not in unavailable and any(dep in unavailable for dep in results[file].get('project_dependencies',[])):
                unavailable.add(file);changed=True
    for row in types.values():
        if row['source_record']['file'] in unavailable:row['implementation_available']=False
    return {'schema_version':SCHEMA,'dependency_id':dependency_id,'version':version,'source_jar':source_jar.name,
        'source_jar_sha256':hashlib.sha256(source_jar.read_bytes()).hexdigest(),'neocore_abi':neocore_abi,
        'generated_class_abi':2,'packages':sorted({v['package'] for v in types.values() if v['package']}),'types':types,
        'requires_translated_dependencies':sorted({dep for r in translation['results'] for dep in r.get('translated_dependencies',[])}),
        'export_issues':export_issues,
        'capability_blockers':translation.get('capability_blockers',[]),'skipped_optional':translation.get('skipped_optional',[]),
        'engine_verified':False,'limits':['Only generated implementations can satisfy a translated dependency.', 'ABI declarations are not an engine or semantic compatibility certificate.']}

class Index:
    def __init__(self,manifests=(),core_symbols=(),available_neocore_abi=7,optional_packages=()):
        self.types={};self.core=set(core_symbols);self.optional=tuple(optional_packages)
        for manifest in manifests:
            if manifest.get('schema_version')!=SCHEMA:raise ValueError('Unsupported dependency ABI schema')
            if type(manifest.get('neocore_abi')) is not int or not 1<=manifest['neocore_abi']<=available_neocore_abi:raise ValueError('Dependency needs a valid supported NeoCore ABI')
            if not re.fullmatch('[0-9a-f]{64}',manifest.get('source_jar_sha256','')):raise ValueError('Missing dependency JAR provenance')
            for identity,row in manifest['types'].items():
                identifier=r'[A-Za-z_$][A-Za-z0-9_$]*'
                if not re.fullmatch(identifier+r'(\.'+identifier+r')*',identity):raise ValueError('Invalid dependency Java identity')
                if identity.startswith(('java.','net.minecraft.','net.neoforged.','com.mojang.','neocore.')):raise ValueError('Dependency cannot claim a core-owned namespace')
                record=row['source_record'];relative=PurePosixPath(record['file'])
                if relative.is_absolute() or '..' in relative.parts or '\\' in record['file'] or ':' in record['file']:raise ValueError('Invalid dependency source path')
                if record['module']!='.'.join(relative.with_suffix('').parts):raise ValueError('Dependency module/source path mismatch')
                if any(not re.fullmatch(identifier,a) for a in record['attribute_chain']):raise ValueError('Invalid dependency export name')
                if identity in self.types or identity in self.core:raise ValueError('Dependency symbol ownership conflict: '+identity)
                self.types[identity]=(manifest,row)
    def resolve(self,identity,operation='reference'):
        if identity in self.core:return {'category':'CORE_SYMBOL','symbol':identity,'deferred':False}
        hit=self.types.get(identity)
        if hit:
            manifest,row=hit
            if row['implementation_status']=='GENERATED_REVIEW_REQUIRED' and row['abi_complete'] and row['implementation_available']:
                return {'category':'TRANSLATED_DEPENDENCY_SYMBOL','symbol':identity,'dependency_id':manifest['dependency_id'],'version':manifest['version'],'deferred':False,'abi':row}
            return {'category':'EXTERNAL_ABI_REQUIRED' if operation in HARD_OPERATIONS else 'UNRESOLVED_EXTERNAL','symbol':identity,'reason':'Dependency ABI or generated implementation is incomplete','dependency_id':manifest['dependency_id'],'deferred':operation not in HARD_OPERATIONS}
        optional=any(identity==p or identity.startswith(p+'.') for p in self.optional)
        if operation in HARD_OPERATIONS:return {'category':'EXTERNAL_ABI_REQUIRED','symbol':identity,'operation':operation,'optional':optional,'deferred':False}
        return {'category':'OPTIONAL_DEPENDENCY' if optional else 'UNRESOLVED_EXTERNAL','symbol':identity,'operation':operation,'deferred':True}
    def project_records(self):
        result={}
        for identity,(manifest,row) in self.types.items():
            if not row['abi_complete'] or not row['implementation_available'] or row['implementation_status']!='GENERATED_REVIEW_REQUIRED':continue
            record=dict(row['source_record'],dependency_id=manifest['dependency_id'],external_dependency=True)
            result[identity]=[record]
        return result

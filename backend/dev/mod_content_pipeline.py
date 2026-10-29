"""Unified, non-executing inventory and lossless staging for every mod content lane.

Preservation is deliberately distinct from schema conversion and engine support.
"""
import hashlib,json,re
from collections import Counter
from pathlib import Path

LANES=('java_code','data_json','assets_resources','metadata_dependencies','mixin_at')
DATA_KINDS={'recipe':'recipe','recipes':'recipe','tags':'tag','tag':'tag','loot_table':'loot_table','loot_tables':'loot_table','advancement':'advancement','advancements':'advancement'}
REASONS={'recipe':'Original Java recipe schema retained; NetEase recipe mapping is not yet validated.',
 'tag':'Original registry tag retained; runtime tag ingestion is not yet connected.',
 'loot_table':'Original loot schema retained; loot context/functions need a target adapter.',
 'advancement':'Original advancement retained; criteria, triggers and rewards need a target adapter.'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def classify(relative):
    p=Path(relative);parts=p.parts;name=p.as_posix();lower=name.lower()
    if lower.endswith(('.class','.java','.py')):return 'java_code',p.suffix[1:]
    if p.suffix=='.json' and re.search(r'mixins?(?:[._-]|$)',p.stem.lower()) or lower.endswith(('accesstransformer.cfg','accesswidener')):return 'mixin_at','access_transformer' if lower.endswith('.cfg') else 'transformer_config'
    if parts[0]=='data' and p.suffix=='.json':return 'data_json',DATA_KINDS.get(parts[2],'unsupported_data_type') if len(parts)>3 else 'malformed_data_path'
    if parts[0]=='assets' or parts[0]=='data':return 'assets_resources','asset' if parts[0]=='assets' else 'data_binary'
    if parts[0]=='META-INF' or p.name in ('fabric.mod.json','quilt.mod.json','pack.mcmeta') or p.suffix=='.jar':return 'metadata_dependencies','service_provider' if lower.startswith('meta-inf/services/') else 'metadata'
    return 'assets_resources','other_resource'

def scan(root):
    root=Path(root).resolve();rows=[]
    if not root.is_dir():raise ValueError('Content source is missing')
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('Content source contains a link')
        if not path.is_file():continue
        relative=path.relative_to(root).as_posix();raw=path.read_bytes();lane,kind=classify(relative)
        row={'source':relative,'lane':lane,'kind':kind,'bytes':len(raw),'sha256':sha(raw),'status':'CODE_PIPELINE_REQUIRED' if lane=='java_code' else 'PRESERVED_ORIGINAL','semantic_conversion':False,'engine_verified':False}
        if lane=='data_json':
            try:
                payload=json.loads(raw.decode('utf-8-sig'))
                if not isinstance(payload,(dict,list)):raise ValueError('Expected a JSON object or array')
                row['json_valid']=True
                row['reason']=REASONS.get(kind,'Original JSON retained; no converter exists for data type '+kind)
                if isinstance(payload,dict) and isinstance(payload.get('type'),str):row['declared_type']=payload['type']
            except (ValueError,UnicodeError) as error:
                row.update(status='INVALID_JSON_PRESERVED',json_valid=False,reason=str(error))
        elif lane=='mixin_at':row['reason']='Analyzed independently by Mixin/AT pipeline; preservation does not apply transformations.'
        elif kind=='service_provider':row['reason']='Provider declaration preserved; providers are never executed by the importer.'
        elif lane!='java_code':row['reason']='Original resource or metadata retained; target support is not implied.'
        rows.append(row)
    counts=Counter(row['lane'] for row in rows)
    return {'schema_version':1,'lanes':{name:{'files':counts[name]} for name in LANES},'files':rows,
        'has_code':bool(counts['java_code']),'has_non_java_content':bool(sum(counts[n] for n in LANES if n!='java_code')),
        'data_types':dict(Counter(r['kind'] for r in rows if r['lane']=='data_json')),
        'invalid_json_files':sum(r['status']=='INVALID_JSON_PRESERVED' for r in rows),'engine_verified':False}

def stage(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.exists() or root==output or root in output.parents or output in root.parents:raise ValueError('Content stage output exists or overlaps source')
    report=scan(root);output.mkdir(parents=True)
    for row in report['files']:
        if row['lane']=='java_code':continue
        path=root/row['source'];raw=path.read_bytes()
        if sha(raw)!=row['sha256']:raise ValueError('Content changed during staging: '+row['source'])
        target=output/'preserved_original'/row['source'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        row['output']=target.relative_to(output).as_posix()
    report['preserved_files']=sum('output' in r for r in report['files'])
    report['status']='CONTENT_STAGED_REVIEW_REQUIRED'
    (output/'content_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

"""Read-only compiler-selected signatures vs original binary symbol sets.

No expression alignment, no line/name/order anchors and no production override.
Unresolved source nested names/type variables remain unknown.
"""
import collections
from resolution import Index

PRIMITIVES={'boolean':'Z','byte':'B','char':'C','short':'S','int':'I','long':'J','float':'F','double':'D','void':'V'}

def erased_type(raw,classes):
    if not raw or '?' in raw:return None
    rank=0
    while raw.endswith('[]'):rank+=1;raw=raw[:-2]
    depth=0;parts=[]
    for c in raw:
        if c=='<':depth+=1
        elif c=='>':depth-=1
        elif not depth:parts.append(c)
    base=''.join(parts)
    if depth:return None
    if base in PRIMITIVES:value=PRIMITIVES[base]
    elif base in classes:value='L'+base.replace('.','/')+';'
    else:return None
    return '['*rank+value

def compare(classes,official,events):
    project={r['name']:r for r in classes};definitions=dict(official,**project);index=Index(definitions)
    binary=collections.defaultdict(set)
    def symbol(owner,name,desc,kind='method'):
        resolved=index.member(owner,name,desc,kind)
        return (resolved.get('declaring_type',owner),name,desc) if resolved['status'] in ('FOUND','ARRAY_CLONE') else (owner,name,desc)
    for row in classes:
        if not row.get('source_file'):continue
        package=row['name'].rpartition('.')[0].replace('.','/')
        file=(package+'/' if package else '')+row['source_file']
        for call in row['calls']:
            if 'target' in call and call['opcode'].startswith('invoke'):
                ref=call['target'];binary[file].add(symbol(ref['owner'],ref['name'],ref['descriptor'],ref['kind']))
            for ref in call.get('dynamic',{}).get('method_handles',[]):
                binary[file].add(symbol(ref['owner'],ref['name'],ref['descriptor'],ref['kind']))
    observations=[];seen=set()
    for e in events:
        if e.get('phase')!='compiler_resolution':continue
        key=(e.get('file'),e.get('owner'),e.get('name'),tuple(e.get('parameters',[])),e.get('return_type'),e.get('observation_kind'))
        if key in seen:continue
        seen.add(key);owner=e['owner'];parameters=[erased_type(t,definitions) for t in e['parameters']]
        result=dict(compiler={k:e.get(k) for k in ('file','java_class','owner','name','parameters','return_type','observation_kind')},
            status='UNKNOWN',runtime_behavior='NOT_VERIFIED',expression_anchor=False)
        if owner not in definitions or any(t is None for t in parameters):
            result['unknown_reason']='Exact binary owner/type-variable/nested source name mapping is unresolved';observations.append(result);continue
        prefix='('+''.join(parameters)+')';todo=[owner];visited=set();candidates=set()
        while todo:
            current=todo.pop()
            if current in visited:continue
            visited.add(current);row=definitions.get(current)
            if row is None:continue
            for method in row['methods']:
                if method['name']==e['name'] and method['descriptor'].startswith(prefix):
                    resolved=index.member(owner,e['name'],method['descriptor'],'method')
                    if resolved['status']=='FOUND':candidates.add((resolved['declaring_type'],e['name'],method['descriptor']))
            if e['name']!='<init>':todo.extend(row.get('interfaces',[]));todo.extend([row['superclass']] if row.get('superclass') else [])
        result['abi_descriptor_candidates']=sorted(candidates)
        if len(candidates)==1:
            candidate=next(iter(candidates));result['unique_abi_symbol']=candidate
            result['status']='SAME_SYMBOL_OBSERVED_IN_SOURCEFILE_BYTECODE' if candidate in binary.get(e['file'],set()) else 'NO_AGGREGATE_SYMBOL_MATCH_REVIEW'
        else:result['unknown_reason']='No unique ABI descriptor; bridges/covariance/erasure or incomplete hierarchy need review'
        observations.append(result)
    return dict(schema_version=1,status='OBSERVATIONS_COMPARED' if observations else 'NO_COMPILER_OBSERVATIONS',comparison_kind='AGGREGATE_SYMBOL_SETS_NOT_EXPRESSION_ALIGNMENT',
        observations=observations,counts=dict(collections.Counter(r['status'] for r in observations)),
        trusted_expression_anchors=[],production_descriptor_overrides=0,
        unknowns=['Source-file symbol equality does not prove correspondence of individual expressions',
                  'Compiler signature is not presumed to be a JVM descriptor','NO_AGGREGATE match is a review signal, not a proven compiler bug',
                  'Fields, dynamic dispatch, class initialization, access control and runtime behavior are not certified by this comparison'])

if __name__=='__main__':
    import argparse,hashlib,json,zipfile
    from pathlib import Path
    from classfile import read
    from abi import load_index
    from locking import load,verify,digest
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('jar',type=Path);p.add_argument('events',type=Path);p.add_argument('abi',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();root=a.abi.parent;lock=load(root/'versions.lock.json');verify(lock)
    if digest(a.abi)!=load(root/'run_manifest.json')['outputs'][a.abi.name]:raise ValueError('Official ABI artifact hash mismatch')
    identity=load(a.events.parent/'task_identity.json')
    if digest(a.jar)!=identity['input_sha256']:raise ValueError('Compiler event log belongs to a different original JAR')
    with zipfile.ZipFile(a.jar) as z:classes=[read(z.read(n)) for n in z.namelist() if n.endswith('.class')]
    events=[json.loads(line) for line in a.events.read_text(encoding='utf-8').splitlines()]
    result=compare(classes,load_index(a.abi)['classes'],events)
    result['inputs']={str(path):digest(path) for path in (a.jar,a.events,a.abi)};result['task_identity']=identity
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    verify(lock);print(json.dumps(result['counts'],ensure_ascii=True))

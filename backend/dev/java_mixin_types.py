"""Resolved source Mixin type identities and JVM descriptors, without guessed type variables."""
import re
from java_method_overloads import canonical

PRIMITIVES={'boolean':'Z','byte':'B','short':'S','char':'C','int':'I','long':'J','float':'F','double':'D','void':'V'}
LANG={'java.lang.'+name for name in ('Object','String','Integer','Boolean','Long','Double','Float','Number','Character','Short','Byte')}


def split_arguments(raw):
    result=[];depth=0;start=0
    for index,char in enumerate(raw):
        if char=='<':depth+=1
        elif char=='>':depth-=1
        elif char==',' and depth==0:result.append(raw[start:index]);start=index+1
        if depth<0:raise ValueError('Unbalanced generic type')
    result.append(raw[start:])
    if depth or any(not item for item in result):raise ValueError('Malformed generic type')
    return result


def identity(raw,owner,unit,allow_wildcard=False):
    raw=re.sub(r'\s+','',raw or '')
    if raw=='?' and allow_wildcard:return '?'
    for bound in ('?extends','?super'):
        if raw.startswith(bound):
            if not allow_wildcard:raise ValueError('Wildcard outside generic argument')
            return bound+identity(raw[len(bound):],owner,unit)
    arrays=0
    while raw.endswith('[]'):arrays+=1;raw=raw[:-2]
    if not raw:raise ValueError('Empty type')
    base=raw.split('<',1)[0]
    resolved=canonical(base,dict(owner,external=True),unit)
    records=unit.get('_project_types',{}).get(resolved,[])
    if 'known_api_types' in unit:
        known=set(unit['known_api_types'])
    elif resolved in PRIMITIVES or resolved in LANG or len(records)==1:
        known=set()
    else:
        from java_frontend import api_index
        known,stale=api_index()
        if stale:raise ValueError('Stale runtime type catalog')
        known=set(known)
    if resolved not in PRIMITIVES and resolved not in LANG and resolved not in known and len(records)!=1:
        raise ValueError('Unresolved class/type-variable identity: '+base)
    if len(records)>1:raise ValueError('Ambiguous type identity: '+base)
    if '<' in raw:
        if not raw.endswith('>') or resolved in PRIMITIVES:raise ValueError('Malformed parameterized type')
        args=split_arguments(raw[raw.index('<')+1:-1])
        resolved+='<' + ','.join(identity(arg,owner,unit,True) for arg in args)+'>'
    if resolved=='void' and arrays:raise ValueError('void array')
    return resolved+'[]'*arrays


def descriptor_type(raw,owner,unit):
    resolved=identity(raw,owner,unit)
    arrays=0
    while resolved.endswith('[]'):arrays+=1;resolved=resolved[:-2]
    base=resolved.split('<',1)[0]
    if base in PRIMITIVES:return '['*arrays+PRIMITIVES[base]
    rows=unit.get('_project_types',{}).get(base,[])
    if rows:
        chain=rows[0]['attribute_chain']
        package=base[:-(sum(len(part) for part in chain)+len(chain)-1)].rstrip('.')
        binary=(package.replace('.','/')+'/' if package else '')+'$'.join(chain)
    else:
        # Known runtime identities with nested exports need a separate binary-name declaration.
        pieces=base.split('.')
        first=next((i for i,piece in enumerate(pieces) if piece[:1].isupper()),len(pieces)-1)
        if first<len(pieces)-1:raise ValueError('Nested external binary name requires explicit ABI')
        binary=base.replace('.','/')
    return '['*arrays+'L'+binary+';'


def method_descriptor(method,owner,unit):
    try:
        args=[descriptor_type(p['declared_type'],owner,unit) for p in method['parameters']]
        if 'V' in args:raise ValueError('void parameter')
        result=descriptor_type('void' if method['constructor'] else method['return_type'],owner,unit)
        return ('<init>' if method['constructor'] else method['name'])+'('+''.join(args)+')'+result
    except ValueError:
        return None

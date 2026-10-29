"""Identity-only reference maps; selectors still require exact target validation.

Mixin 0.8.7 ReferenceMapper.read uses a passthrough mapper for missing resources.
This adapter deliberately rejects malformed and nonidentity maps instead of
guessing an obfuscation context. It does not perform namespace remapping.
"""
import hashlib
import json
from pathlib import PurePosixPath


def inspect(root, config, origin):
    from java_mixin_plan import MixinPlanError
    def error(message):raise MixinPlanError(origin,message)
    name=config.get('refmap','mixin.refmap.json')
    if (not isinstance(name,str) or not name or '\\' in name or ':' in name
            or name.startswith('/') or any(ord(c)<32 for c in name)
            or any(p in ('','.','..') for p in name.split('/'))):
        error('Refmap must name a relative resource inside the content')
    path=root.joinpath(*PurePosixPath(name).parts)
    if root.resolve() not in path.resolve().parents:
        error('Refmap resource escapes content root')
    if any(p.is_symlink() for p in (path,*path.parents) if p!=root and root in p.parents):
        error('Refmap resource links require explicit preparation')
    result={'resource':name,'declared':'refmap' in config,'sha256':None,
            'mode':'missing_passthrough','mapping_count':0,
            'limits':'No namespace remapping; original selectors must match reviewed source/runtime targets.'}
    if not path.exists():return result
    if not path.is_file() or path.stat().st_size>4*1024*1024:error('Refmap must be a bounded JSON file')
    raw=path.read_bytes()
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('Duplicate refmap key: '+key)
            out[key]=value
        return out
    try:data=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique)
    except (UnicodeError,ValueError) as exc:error('Unreadable refmap '+name+': '+str(exc))
    if not isinstance(data,dict) or set(data)-{'mappings','data'}:error('Unsupported refmap structure: '+name)
    def table(mapping):
        if not isinstance(mapping,dict):error('Invalid refmap mappings: '+name)
        count=0
        for owner,entries in mapping.items():
            if not isinstance(owner,str) or not owner or not isinstance(entries,dict):error('Invalid refmap owner: '+name)
            for reference,mapped in entries.items():
                if not isinstance(reference,str) or not reference or not isinstance(mapped,str):error('Invalid refmap reference: '+name)
                if reference!=mapped:error('Nonidentity refmap requires explicit namespace remapping: '+name)
                count+=1
        return count
    count=table(data.get('mappings',{}));contexts=data.get('data',{})
    if not isinstance(contexts,dict):error('Invalid refmap contexts: '+name)
    for context,mapping in contexts.items():
        if not isinstance(context,str) or not context:error('Invalid refmap context: '+name)
        count+=table(mapping)
    result.update(mode='identity_only',sha256=hashlib.sha256(raw).hexdigest(),mapping_count=count)
    return result

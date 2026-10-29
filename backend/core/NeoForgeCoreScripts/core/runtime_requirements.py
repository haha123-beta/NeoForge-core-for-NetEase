# -*- coding: utf-8 -*-
"""Pre-import consistency/type/helper checks, never a platform-version substitute.

This consumes trusted content metadata; it is not a Python security sandbox.
No content module is imported here. API presence is not method-semantic proof.
"""
from __future__ import absolute_import
import hashlib
import re

SCHEMA_VERSION=1
EVIDENCE_SCOPE='api_type_presence_and_helper_abi'
MANIFEST_FILE='_nc_runtime_requirements.json'
try:
    _strings=(basestring,)
    _integers=(int,long)
except NameError:
    _strings=(str,)
    _integers=(int,)

def code_digest(source):
    return hashlib.sha256(source if isinstance(source,bytes) else source.encode('utf-8')).hexdigest()

def _name(value):
    return isinstance(value,_strings) and bool(re.match(r'^[^\W\d]\w*(\.[^\W\d]\w*)*$',value,re.UNICODE))

def validate(manifest,sources):
    if not isinstance(manifest,dict) or isinstance(manifest.get('schema_version'),bool) or not isinstance(manifest.get('schema_version'),_integers) or manifest.get('schema_version')!=SCHEMA_VERSION:
        raise ValueError('Unsupported runtime requirements schema')
    if manifest.get('evidence_scope')!=EVIDENCE_SCOPE:
        raise ValueError('Runtime requirements evidence scope is not supported')
    rows=manifest.get('modules')
    if not isinstance(rows,dict) or not rows:raise ValueError('Runtime requirements must name generated modules')
    issues=[]
    for name,row in sorted(rows.items()):
        if not _name(name) or not isinstance(row,dict):raise ValueError('Malformed module runtime requirements')
        digest=row.get('code_sha256')
        if not isinstance(digest,_strings) or not re.match(r'^[0-9a-f]{64}$',digest):raise ValueError('Invalid generated-code checksum: '+name)
        for key in ('required_api_types','required_runtime_helpers'):
            values=row.get(key)
            if not isinstance(values,list) or any(not isinstance(value,_strings) for value in values):
                raise ValueError('Malformed '+key+': '+name)
        if any(not _name(value.replace('$','.')) for value in row['required_api_types']):
            raise ValueError('Invalid Java API identity: '+name)
        for token in row['required_runtime_helpers']:
            identity,separator,version=token.rpartition('@')
            if not separator or not _name(identity) or not identity.startswith('neocore.runtime.') or not re.match(r'^[1-9][0-9]*$',version) or len(version)>10 or int(version)>2147483647:
                raise ValueError('Invalid runtime helper requirement: '+token)
        if name not in sources:
            issues.append({'module':name,'category':'missing_source','message':'Required generated module is missing'})
        elif code_digest(sources[name]['source'])!=digest:
            issues.append({'module':name,'category':'source_changed','message':'Generated source changed after requirements were recorded'})
    return issues

def inspect_requirements(manifest,sources,api):
    if manifest is None:
        return {'status':'not_declared','schema_version':None,'evidence_scope':EVIDENCE_SCOPE,
                'checked_modules':[],'untracked_modules':sorted(sources),'issues':[],
                'limits':['Legacy/native sources have no generated requirements declaration.']}
    try:issues=validate(manifest,sources)
    except (ValueError,TypeError,KeyError) as error:
        return {'status':'blocked','schema_version':manifest.get('schema_version') if isinstance(manifest,dict) else None,
                'evidence_scope':EVIDENCE_SCOPE,'checked_modules':[],'untracked_modules':sorted(sources),
                'issues':[{'category':'invalid_manifest','message':str(error)}]}
    canonical={}
    for name,value in api.items():
        identity=name.replace('$','.')
        if identity in canonical and canonical[identity] is not value:raise ValueError('Ambiguous runtime API identity: '+identity)
        canonical[identity]=value
    for name,row in sorted(manifest['modules'].items()):
        for identity in sorted(set(row['required_api_types'])):
            if canonical.get(identity.replace('$','.')) is None:
                issues.append({'module':name,'category':'missing_api_type','requirement':identity,
                    'message':'Required Java API type is not mapped'})
        for token in sorted(set(row['required_runtime_helpers'])):
            identity,unused,minimum=token.rpartition('@');value=canonical.get(identity)
            available=getattr(value,'ABI_VERSION',None)
            if isinstance(available,bool) or not isinstance(available,_integers) or available<int(minimum):
                issues.append({'module':name,'category':'helper_abi','requirement':token,
                    'available':available if isinstance(available,_integers) else None,
                    'message':'Required runtime helper ABI is unavailable'})
    return {'status':'blocked' if issues else 'requirements_satisfied','schema_version':SCHEMA_VERSION,
            'evidence_scope':EVIDENCE_SCOPE,'checked_modules':sorted(manifest['modules']),
            'untracked_modules':sorted(set(sources)-set(manifest['modules'])), 'issues':issues,
            'limits':['Type presence/helper ABI checks do not prove complete Java semantics or satisfy platform dependencies.']}

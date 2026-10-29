from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream: data = json.load(stream)
scope = {'__name__': 'stability_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
contract = {}
eval(compile(data['probe'].encode('utf-8'), 'stability-contract.py', 'exec'), contract)
old = scope['SourceModuleLoader'](data['old_core']['sources'])
before = contract['before_trace'](old.load)
old.close()
assert before == {'escaped': 'UnicodeEncodeError', 'accepted': None, 'errors': 1, 'records': 0}, repr(before)
current = scope['SourceModuleLoader'](data['core']['sources'])
after = contract['before_trace'](current.load)
checks = contract['run'](current.load)
current.close()
print(json.dumps({'python': sys.version, 'before_r48': before, 'after_r49': after,
    'check_count': len(checks), 'checks': checks, 'engine_verified': False}))

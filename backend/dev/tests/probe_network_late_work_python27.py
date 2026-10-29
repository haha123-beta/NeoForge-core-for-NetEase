from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
scope = {'__name__': 'late_work_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
loader_type = scope['SourceModuleLoader']
contract = {}
eval(compile(data['probe'].encode('utf-8'), 'late-work-contract.py', 'exec'), contract)
old = loader_type(data['old_core']['sources'])
before = contract['before_trace'](old.load)
assert before == {'executed': ['initial'], 'late_tick_done': 0,
    'context_pending': 1, 'transport_pending': 0}, repr(before)
old.close()
current = loader_type(data['core']['sources'])
after = contract['before_trace'](current.load)
checks = contract['run'](current.load)
current.close()
print(json.dumps({'python': sys.version, 'before_r46': before, 'after_r47': after,
    'check_count': len(checks), 'checks': checks, 'engine_verified': False}))

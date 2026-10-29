from __future__ import print_function
import io
import json
import sys

with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
scope = {'__name__': 'fairness_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
loader_type = scope['SourceModuleLoader']
contract = {}
eval(compile(data['fairness_probe'].encode('utf-8'), 'fairness-contract.py', 'exec'), contract)
old = loader_type(data['r45_core']['sources'])
before = contract['replenishing_trace'](old.load)
assert before['counts'] == {'a': 45, 'b': 45, 'c': 0}, repr(before)
old.close()
current = loader_type(data['core']['sources'])
checks = contract['run'](current.load)
current.close()
print(json.dumps({'python': sys.version, 'before_r45': before['counts'],
    'after_r46': checks, 'scenario_count': len(checks), 'engine_verified': False}))

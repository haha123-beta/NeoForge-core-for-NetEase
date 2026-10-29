from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream: data = json.load(stream)
scope = {'__name__': 'acceptance_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
base, contract, network = {}, {}, {}
eval(compile(data['base_probe'].encode('utf-8'), 'stability-contract.py', 'exec'), base)
eval(compile(data['probe'].encode('utf-8'), 'acceptance-contract.py', 'exec'), contract)
eval(compile(data['content_probe'].encode('utf-8'), 'network-content-contract.py', 'exec'), network)
old = scope['SourceModuleLoader'](data['old_core']['sources'])
before = contract['before_trace'](old.load, base['setup'])
old.close()
assert before['self_close']['failures'] == 0
assert before['startup']['escaped'] == before['destroy']['escaped'] == 'UnicodeEncodeError', repr(before)
runtime = scope['SourceModuleLoader'](data['core']['sources'])
after = contract['before_trace'](runtime.load, base['setup'])
checks = contract['run'](runtime.load, base['setup'])
runtime.close()
cycles = []
for unused in range(2):
    server = scope['SourceModuleLoader'](data['core']['sources'])
    client = scope['SourceModuleLoader'](data['core']['sources'])
    try:
        result = network['run'](server, client, data['core']['sources'], data['network_content'], data['entity_contents'])
        result.update(entity_ready_and_unloaded_both_sides=True, entity_ticks_server=100, entity_ticks_client=0)
        cycles.append(result)
    finally: server.close(); client.close()
print(json.dumps({'python': sys.version, 'before_r49': before, 'after_r50': after,
    'check_count': len(checks), 'checks': checks, 'combined_cycles': cycles, 'engine_verified': False}))

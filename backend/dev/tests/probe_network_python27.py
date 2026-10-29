from __future__ import print_function
import io
import json
import sys

with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
scope = {'__name__': 'network_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
loader_type = scope['SourceModuleLoader']
runtime = loader_type(data['core']['sources'])
contract = {}
eval(compile(data['session_probe'].encode('utf-8'), 'network-contract.py', 'exec'), contract)
checks = contract['run'](runtime.load)
runtime.close()
contract = {}
eval(compile(data['content_probe'].encode('utf-8'), 'network-content.py', 'exec'), contract)
server, client = loader_type(data['core']['sources']), loader_type(data['core']['sources'])
result = contract['run'](server, client, data['core']['sources'], data['network_content'])
server.close(); client.close()
print(json.dumps({'python': sys.version, 'session_contract_checks': len(checks),
    'checks': checks, 'native_content_simulation': result, 'engine_verified': False}))

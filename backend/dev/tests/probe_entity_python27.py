from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
scope = {'__name__': 'entity_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
loader_type = scope['SourceModuleLoader']
contract = {}
eval(compile(data['entity_probe'].encode('utf-8'), 'entity-contract.py', 'exec'), contract)
for side in ('SERVER', 'CLIENT'):
    runtime = loader_type(data['core']['sources'])
    session = runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'], data['entity_contents'], side=side, runtime=runtime)
    try:
        result = session.loader.activate()
        assert result['runtime_entity_example']['ready'], repr(result)
        assert result['runtime_entity_example']['runtime_requirements']['status'] == 'requirements_satisfied'
        driver = runtime.load('core.content_events').ContentTickDriver(session.loader, side)
        for unused in range(150): driver.on_tick()
        main = session.loader.contexts['runtime_entity_example'].instance
        assert main.ticks == (100 if side == 'SERVER' else 0)
        lifecycle = contract['run'](runtime, session) if side == 'SERVER' else None
        entities = runtime.load('minecraft.entity')
        levels = runtime.load('minecraft.level')
        for case in data['entity_cases']:
            module = {'__builtins__': dict(vars(__builtins__) if not isinstance(__builtins__, dict) else __builtins__)}
            module['__builtins__']['__import__'] = runtime.import_module
            eval(compile(case['python_source'].encode('utf-8'), 'generated-entity.py', 'exec'), module)
            access = runtime.load('minecraft.level_access').InMemoryLevelAccess()
            level = levels.ServerLevel(access)
            obj = module[case['class_name']](entities.EntityType.of('r48:case'), level)
            obj.tick(); tag = runtime.load('minecraft.nbt').CompoundTag()
            obj.capture(tag); obj.value = 20; obj.restore(tag)
            actual = ':'.join(str(value) for value in (obj.observed, obj.value, obj.ticks, obj.tickCount, tag.getInt('Value')))
            assert actual == case['jdk_contract_double_result'], repr((actual, case))
        session.close()
        assert session.loader.results['runtime_entity_example']['state'] == 'unloaded'
        assert session.loader.contexts['runtime_entity_example'].game_bus.listenerCount() == 0
        print(json.dumps({'side': side, 'driver_ticks': 100, 'mod_ticks': main.ticks,
            'entity_lifecycle': lifecycle, 'jdk_contract_double_cases': len(data['entity_cases']),
            'python': sys.version, 'closed': True, 'engine_verified': False}))
    finally:
        session.close(); runtime.close()
old_runtime = loader_type(data['r47_core']['sources'])
old_session = old_runtime.load('core.bundled_mods').BundledModSession(
    data['r47_core']['sources'], data['entity_contents'], runtime=old_runtime)
try:
    result = old_session.loader.results['runtime_entity_example']
    assert result['state'] == 'blocked' and result['runtime_requirements']['status'] == 'blocked', repr(result)
    assert 'runtime_entity_example' not in old_session.loader.contexts
    print(json.dumps({'r47_core_rejects_new_entity_requirements_before_entrypoint': True, 'result': result}))
finally:
    old_session.close(); old_runtime.close()

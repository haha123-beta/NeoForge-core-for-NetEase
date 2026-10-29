from __future__ import print_function
import io
import json
import sys

with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
namespace = {'__name__': 'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), namespace)

for side in ('SERVER', 'CLIENT'):
    runtime = namespace['SourceModuleLoader'](data['core']['sources'])
    session = runtime.load('core.bundled_mods').BundledModSession(
        data['core']['sources'], data['contents'], side=side, runtime=runtime)
    try:
        results = session.loader.activate()
        assert len(results) == 3 and all(row.get('ready') for row in results.values()), repr(results)
        assert all(row['runtime_requirements']['status'] == 'requirements_satisfied' for row in results.values())
        driver = runtime.load('core.content_events').ContentTickDriver(session.loader, side)
        for unused in range(150):
            driver.on_tick()
        assert driver.ticks == 100
        instance = session.loader.contexts['runtime_map_example'].instance
        assert instance.ticks == (100 if side == 'SERVER' else 0)
        assert instance.live.size() == (2 if side == 'SERVER' else 1)
        assert instance.total() == (102 if side == 'SERVER' else 2)
        util = runtime.load('java_stdlib.util')
        try:
            instance.readonly.put('bad', 99)
            raise AssertionError('Readonly write was accepted')
        except util.UnsupportedOperationException:
            pass
        text = runtime.load('java_stdlib.lang').JavaString
        # JSON and generated Java strings are Unicode under Python2.
        m = util.JavaMap()
        m.put(text(u'key'), 1)
        m.put('key', 2)
        assert m.size() == 1 and m.get(u'key') == 2
        class Key(object):
            def __init__(self, value):
                self.value = value
            def hashCode(self):
                return 7
            def equals(self, other):
                return isinstance(other, Key) and self.value == other.value
        m.put(Key(1), 3)
        m.put(Key(2), 4)
        assert m.size() == 3 and m.get(Key(1)) == 3 and m.get(Key(2)) == 4
        for source, expected in data['java_cases']:
            module = {}
            module['__builtins__'] = dict(vars(__builtins__) if not isinstance(__builtins__, dict) else __builtins__)
            module['__builtins__']['__import__'] = runtime.import_module
            eval(compile(source.encode('utf-8'), 'generated-map-case.py', 'exec'), module)
            actual = module['A']().run()
            assert str(actual) == expected, repr((actual, expected))
        expected_ticks = 2 if side == 'SERVER' else 0
        for mod_id in ('runtime_goal_example', 'runtime_enumset_example'):
            assert session.loader.contexts[mod_id].instance.goal.ticks == expected_ticks
        total = instance.total()
        session.close()
        assert all(row['state'] == 'unloaded' for row in session.loader.results.values())
        assert all(ctx.game_bus.listenerCount() == 0 for ctx in session.loader.contexts.values())
        print(json.dumps({'side': side, 'python': sys.version,
            'independent_java_mods': 3, 'driver_ticks': 100, 'map_total': total,
            'java_cases_match_jdk': len(data['java_cases']), 'unicode_and_collision_keys': True,
            'closed': True, 'engine_verified': False}))
    finally:
        session.close()
        runtime.close()

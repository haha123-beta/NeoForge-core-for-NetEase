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
        assert len(results) == len(data['contents']) and all(row.get('ready') for row in results.values()), repr(results)
        assert all(row['runtime_requirements']['status'] == 'requirements_satisfied' for row in results.values())
        driver = runtime.load('core.content_events').ContentTickDriver(session.loader, side)
        for unused in range(150):
            driver.on_tick()
        assert driver.ticks == 100
        instance = session.loader.contexts['runtime_map_example'].instance
        assert instance.ticks == (100 if side == 'SERVER' else 0)
        assert instance.total() == (102 if side == 'SERVER' else 2)
        set_instance = session.loader.contexts['runtime_set_example'].instance
        assert set_instance.ticks == (100 if side == 'SERVER' else 0)
        assert list(set_instance.values) == (['tick'] if side == 'SERVER' else ['initial'])
        util = runtime.load('java_stdlib.util')
        for action in (lambda: set_instance.fixed.clear(), lambda: util.JavaSet.of('a', 'a')):
            try:
                action()
                raise AssertionError('factory mutation/duplicate accepted')
            except (util.UnsupportedOperationException, util.IllegalArgumentException):
                pass
        assert not util.Collections.emptySet().addAll([])
        assert util.Collections.emptyMap().remove('missing') is None
        if 'runtime_map_defaults_example' in session.loader.contexts:
            defaults = session.loader.contexts['runtime_map_defaults_example'].instance
            assert defaults.ticks == (100 if side == 'SERVER' else 0)
            assert defaults.values.get('count') == (100 if side == 'SERVER' else 0)
            assert defaults.values.get('mirror') == (100 if side == 'SERVER' else None)
        if 'runtime_linked_map_example' in session.loader.contexts:
            linked = session.loader.contexts['runtime_linked_map_example'].instance
            assert linked.ticks == (100 if side == 'SERVER' else 0)
            assert str(linked.order()) == ('ba' if side == 'SERVER' else 'ab')
        text = runtime.load('java_stdlib.lang').JavaString
        values = util.JavaSet([text(u'\U0001f600')])
        assert not values.add(u'\U0001f600') and values.size() == 1
        class Key(object):
            def __init__(self, value):
                self.value = value
            def hashCode(self):
                return 7
            def equals(self, other):
                return isinstance(other, Key) and self.value == other.value
        values.add(Key(1))
        values.add(Key(2))
        assert values.size() == 3 and values.contains(Key(1)) and values.contains(Key(2))
        for source, expected in data['java_cases']:
            module = {}
            module['__builtins__'] = dict(vars(__builtins__) if not isinstance(__builtins__, dict) else __builtins__)
            module['__builtins__']['__import__'] = runtime.import_module
            eval(compile(source.encode('utf-8'), 'generated-collection-case.py', 'exec'), module)
            actual = module['A']().run()
            assert str(actual) == expected, repr((actual, expected))
        for mod_id in ('runtime_goal_example', 'runtime_enumset_example'):
            assert session.loader.contexts[mod_id].instance.goal.ticks == (2 if side == 'SERVER' else 0)
        session.close()
        assert all(row['state'] == 'unloaded' for row in session.loader.results.values())
        assert all(ctx.game_bus.listenerCount() == 0 for ctx in session.loader.contexts.values())
        print(json.dumps({'side': side, 'python': sys.version,
            'independent_java_mods': len(data['contents']), 'driver_ticks': 100,
            'java_cases_match_jdk': len(data['java_cases']), 'unicode_and_collision_keys': True,
            'closed': True, 'engine_verified': False}))
    finally:
        session.close()
        runtime.close()

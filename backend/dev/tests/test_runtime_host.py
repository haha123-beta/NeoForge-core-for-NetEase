import os
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import types
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle, content_bundle
from test_content_registry import FakeEngine
host_module = Package().load('core.runtime_host')


class RuntimeHostTests(unittest.TestCase):
    def test_diagnostics_report_real_session_ticks_and_cleanup(self):
        for invalid in (False, True):
            engine, exports = FakeEngine(), {}
            def register(namespace, name, path):
                instance = exports[path.rsplit('.', 1)[-1]](namespace, name)
                engine.systems[(namespace, name)] = instance
                return instance
            engine.RegisterSystem = register
            output = io.StringIO()
            with redirect_stdout(output):
                host = host_module.SourceRuntimeHost(core_bundle(), engine, 'CLIENT',
                    exports, 'NeoCoreSourceScripts', diagnostics=True)
                core = engine.GetSystem('NeoCore', 'Loader')
                name = 'neocore_example_base'
                root = Path(__file__).resolve().parents[1]/'examples/multi_mod'/name
                bundle = content_bundle(root, {name:'example.' + name + '.Main:start'})
                if invalid:
                    bundle['schema_version'] = -1
                core.RegisterContent('example_pack', 2, [{'bundle':bundle}])
                engine.emit('Minecraft', 'Engine', 'LoadClientAddonScriptsAfter', {})
                engine.emit('Minecraft', 'Engine', 'LoadClientAddonScriptsAfter', {})
                for unused in range(151):
                    engine.emit('Minecraft', 'Engine', 'OnScriptTickClient', {})
                before_close = core.GetContentReport()
                host.close()
                host.close()
                core.Destroy()
            text = output.getvalue()
            self.assertEqual(text.count('[NeoCore diagnostic] session CLIENT'), 1)
            self.assertEqual(text.count('[NeoCore diagnostic] closed CLIENT'), 1)
            if invalid:
                self.assertEqual(before_close['state'], 'failed')
                self.assertIn("'state': 'failed'", text)
                self.assertNotIn('[NeoCore diagnostic] ticks', text)
            else:
                self.assertTrue(before_close['mods'][name]['ready'])
                for count in (1, 20, 100):
                    self.assertEqual(text.count('[NeoCore diagnostic] ticks CLIENT ' + str(count) + ' '), 1)
                self.assertIn("'state': 'closed'", text)
            self.assertEqual(engine.listeners, [])

    def test_registration_failure_closes_previously_created_system(self):
        engine, exports, created = FakeEngine(), {}, []
        def register(namespace, name, path):
            if name == 'Loader':
                return None
            instance = exports[path.rsplit('.', 1)[-1]](namespace, name)
            created.append(instance)
            return instance
        engine.RegisterSystem = register
        engine.GetEngineCompFactory = lambda: object()
        engine.GetMinecraftEnum = lambda: types.SimpleNamespace(AttrType=types.SimpleNamespace(HEALTH=0))
        with self.assertRaisesRegex(RuntimeError, 'NeoCore/Loader'):
            host_module.SourceRuntimeHost(core_bundle(), engine, 'SERVER', exports, 'NeoCoreSourceScripts')
        self.assertEqual(len(created), 1)
        self.assertEqual(engine.listeners, [])

    def test_sdk_systems_and_content_share_private_event_classes(self):
        for side in ('SERVER', 'CLIENT'):
            engine, exports = FakeEngine(), {}
            def register(namespace, name, path):
                instance = exports[path.rsplit('.', 1)[-1]](namespace, name)
                engine.systems[(namespace, name)] = instance
                return instance
            engine.RegisterSystem = register
            engine.GetEngineCompFactory = lambda: object()
            engine.GetMinecraftEnum = lambda: types.SimpleNamespace(AttrType=types.SimpleNamespace(HEALTH=0))
            host = host_module.SourceRuntimeHost(core_bundle(), engine, side, exports, 'NeoCoreSourceScripts')
            core = engine.GetSystem('NeoCore', 'Loader')
            self.assertEqual(core.GetRegistrationApiVersion(), 2)
            root = Path(__file__).resolve().parents[1] / 'examples/multi_mod'
            name = 'neocore_example_base'
            bundle = content_bundle(root / name, {name: 'example.' + name + '.Main:start'})
            core.RegisterContent('example_pack', 2, [{'bundle': bundle}])
            engine.emit('Minecraft', 'Engine', 'Load' + side.title() + 'AddonScriptsAfter', {})
            report = core.GetContentReport()
            self.assertTrue(report['mods'][name]['ready'])
            state = core.registry._session.loader.contexts[name].instance
            for unused in range(30):
                engine.emit('Minecraft', 'Engine', 'OnScriptTick' + side.title(), {})
            self.assertEqual(state['ticks'], 20 if side == 'SERVER' else 0)
            if side == 'SERVER':
                runtime = core.GetEntityRuntime(0)
                self.assertIs(runtime, core.GetEntityRuntime(0))
                self.assertIsNot(runtime, core.GetEntityRuntime(1))
            self.assertEqual(host.close(), [])
            self.assertTrue(state['closed'])
            self.assertEqual(engine.listeners, [])
            self.assertEqual(host.close(), [])


if __name__ == '__main__':
    unittest.main()

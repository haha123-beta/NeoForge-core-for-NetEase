import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
loader = pkg.load('core.translated_loader')
config = pkg.load('neoforge.config')
events = pkg.load('neoforge.event.fml.config')


class ConfigSessionTests(unittest.TestCase):
    def test_apply_reload_invalid_input_and_unload_order(self):
        context = loader.ModContext({'mod_id': 'sample'})
        builder = config.ModConfigSpec.Builder()
        value = builder.defineInRange('count', 2, 0, 10)
        spec = builder.build()
        context.mod_container.registerConfig(config.ModConfig.Type.COMMON, spec)
        registered = context.mod_container.getConfigs()[0]
        observed = []
        def listen(event):
            observed.append((type(event), value.get(), spec.isLoaded()))
        context.mod_bus.addListener(events.ModConfigEvent, listen)
        context.config_session.apply(registered, {'count': 3})
        context.config_session.apply(registered, {'count': 4})
        with self.assertRaises(config.IllegalArgumentException):
            context.config_session.apply(registered, {'count': 99})
        self.assertEqual(len(observed), 2)
        self.assertEqual(context.close(), [])
        self.assertEqual(observed, [(events.ModConfigEvent.Loading, 3, True),
            (events.ModConfigEvent.Reloading, 4, True),
            (events.ModConfigEvent.Unloading, 4, False)])
        self.assertEqual(context.mod_container.getConfigs(), [])
        self.assertEqual(context.close(), [])

    def test_listener_failure_is_visible_and_cleanup_still_runs(self):
        context = loader.ModContext({'mod_id': 'sample'})
        builder = config.ModConfigSpec.Builder()
        builder.define('enabled', True)
        context.mod_container.registerConfig(config.ModConfig.Type.COMMON, builder.build())
        registered = context.mod_container.getConfigs()[0]
        def fail(event):
            raise RuntimeError('listener failed')
        context.mod_bus.addListener(events.ModConfigEvent, fail)
        with self.assertRaises(RuntimeError):
            context.config_session.apply(registered, {})
        self.assertIn('listener failed', context.close()[0])
        self.assertEqual(context.mod_container.getConfigs(), [])
        self.assertFalse(registered.getSpec().isLoaded())


if __name__ == '__main__':
    unittest.main()

import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
loader = package.load('core.translated_loader')
registries = package.load('neoforge.registries')
lifecycle = package.load('neoforge.event.fml.lifecycle')


class ActivationTests(unittest.TestCase):
    def test_registration_setup_and_idempotence(self):
        seen = []
        def start(ctx):
            registry = registries.DeferredRegister.create('minecraft:item', ctx.mod_id)
            registry.register('one', lambda: 17)
            registry.register(ctx.mod_bus)
            ctx.mod_bus.subscribe(lambda event: seen.append(ctx.mod_id), lifecycle.FMLCommonSetupEvent)
        manager = loader.TranslatedModLoader(lambda path: start)
        manager.load({'schema_version': 1, 'mods': [{'mod_id': 'sample', 'entrypoint': 'start'}]})
        self.assertTrue(manager.activate()['sample']['ready'])
        self.assertEqual(manager.registries['minecraft:item']['sample:one'], 17)
        manager.activate()
        self.assertEqual(seen, ['sample'])
        manager.close()
        self.assertEqual(manager.registries, {})

    def test_setup_failure_rolls_back_and_closes_dependents(self):
        closed = []
        def fail(event):
            raise ValueError('setup failed')
        def start(ctx):
            ctx.on_close(lambda: closed.append(ctx.mod_id))
            if ctx.mod_id == 'base':
                ctx.mod_bus.subscribe(fail, lifecycle.FMLCommonSetupEvent)
        manager = loader.TranslatedModLoader(lambda path: start)
        manager.load({'schema_version': 1, 'mods': [
            {'mod_id': 'base', 'entrypoint': 'start'},
            {'mod_id': 'dependent', 'entrypoint': 'start', 'requires': ['base']},
            {'mod_id': 'good', 'entrypoint': 'start'}]})
        report = manager.activate()
        self.assertFalse(report['base']['ready'])
        self.assertEqual(report['dependent']['phase'], 'dependencies')
        self.assertTrue(report['good']['ready'])
        self.assertEqual(closed, ['base', 'dependent'])


if __name__ == '__main__':
    unittest.main()

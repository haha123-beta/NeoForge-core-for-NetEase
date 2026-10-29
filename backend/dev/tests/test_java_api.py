import os
from pathlib import Path
import sys
import types
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
from harness import Package
from update_java_api_catalog import catalog
package = Package()
api = package.load('core.java_api')


class JavaApiTests(unittest.TestCase):
    def test_attribute_cleanup_error_does_not_leave_other_owned_modules(self):
        system = types.SimpleNamespace(modules={})
        scope = api.JavaApiImports(system).install({'demo.Type': object()})
        class Protected(object):
            def __delattr__(self, name):
                if name == 'blocked':
                    raise RuntimeError('cannot remove protected attribute')
                object.__delattr__(self, name)
        owner = Protected()
        scope._attribute(owner, 'blocked', object())
        scope._attribute(owner, 'normal', object())
        with self.assertRaisesRegex(RuntimeError, 'attribute blocked'):
            scope.close()
        self.assertEqual(system.modules, {})
        self.assertFalse(hasattr(owner, 'normal'))
        self.assertTrue(hasattr(owner, 'blocked'))
        self.assertEqual(scope._exposed, {})
        self.assertTrue(scope.cleanup_errors)
        with self.assertRaisesRegex(RuntimeError, 'attribute blocked'):
            scope.close()

    def test_original_package_imports_nested_classes_and_release(self):
        original_io = sys.modules.get('io')
        mapping = api.collect_java_api()
        scope = api.JavaApiImports(sys).install(mapping)
        try:
            from net.minecraft.world.entity import Entity
            from net.neoforged.neoforge.registries import DeferredRegister
            from java.util.Map import Entry
            from java.util import Map
            from net.neoforged.neoforge.client.event import RegisterShadersEvent
            self.assertIs(Entity, mapping['net.minecraft.world.entity.Entity'])
            self.assertIs(DeferredRegister, mapping['net.neoforged.neoforge.registries.DeferredRegister'])
            self.assertIs(Map.Entry, Entry)
            self.assertIs(RegisterShadersEvent, package.load('shader.material').RegisterShadersEvent)
            self.assertIs(sys.modules['io'].open, original_io.open)
            self.assertFalse(hasattr(original_io,'netty'))
        finally:
            scope.close()
        self.assertNotIn('net.minecraft', sys.modules)
        self.assertIs(sys.modules['io'],original_io)

    def test_collision_rolls_back_only_owned_mutations(self):
        system = types.SimpleNamespace(modules={})
        existing = types.ModuleType('existing')
        existing.__path__ = []
        existing.Conflict = object()
        system.modules['existing'] = existing
        scope = api.JavaApiImports(system)
        with self.assertRaises(ValueError):
            scope.install({'aaa.NewClass': object(), 'existing.Conflict': object()})
        self.assertEqual(system.modules, {'existing': existing})
        self.assertFalse(hasattr(existing, 'NewClass'))

    def test_reference_count_and_catalog_are_complete(self):
        system = types.SimpleNamespace(modules={})
        key = api.acquire_java_api(system, {'demo.Type': object()})
        second = api.acquire_java_api(system, {})
        api.release_java_api(key)
        self.assertIn('demo', system.modules)
        api.release_java_api(second)
        self.assertEqual(system.modules, {})
        root = Path(_PROJECT_SCRIPTS)
        self.assertEqual(api.API_MODULES, catalog(root))


if __name__ == '__main__':
    unittest.main()

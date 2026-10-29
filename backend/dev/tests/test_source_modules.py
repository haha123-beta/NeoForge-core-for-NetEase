import builtins
import json
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
from harness import Package
source_loader = Package().load('core.source_modules')


def row(source, package=False):
    return {'source': source, 'is_package': package}


class SourceModuleTests(unittest.TestCase):
    def test_json_decoded_module_names_keep_package_identity(self):
        sources = json.loads(json.dumps({
            'example':row('', True),
            'example.base':row('VALUE = 7'),
            'example.addon':row('from .base import VALUE\nRESULT = VALUE + 1')}))
        loader = source_loader.SourceModuleLoader(sources)
        addon = loader.load(next(name for name in sources if name.endswith('.addon')))
        self.assertEqual(addon.RESULT, 8)
        self.assertEqual(addon.__name__, 'example.addon')
        self.assertIs(loader.load('example').addon, addon)
        loader.close()

    def test_package_initializer_relative_import_and_cycle(self):
        loader = source_loader.SourceModuleLoader({
            'private_example': row('MARKER = 7\nfrom . import child\n', True),
            'private_example.child': row('from . import MARKER\nfrom . import sibling\nVALUE = MARKER + sibling.VALUE'),
            'private_example.sibling': row('from . import child\nVALUE = 10')})
        child = loader.load('private_example.child')
        self.assertEqual(child.VALUE, 17)
        self.assertIs(loader.modules['private_example.sibling'].child, child)
        self.assertNotIn('private_example.child', sys.modules)
        loader.close()
        with self.assertRaises(ImportError):
            loader.load('private_example.child')

    def test_failed_import_is_cleaned_and_forbidden_imports_are_not_delegated(self):
        called = []
        loader = source_loader.SourceModuleLoader({
            'fixture.bad': row('import os'),
            'fixture.good': row('VALUE = 17')}, lambda *args: called.append(args))
        with self.assertRaises(ImportError):
            loader.load('fixture.bad')
        self.assertEqual(called, [])
        self.assertNotIn('fixture.bad', loader.modules)
        self.assertFalse(hasattr(loader.modules['fixture'], 'bad'))
        self.assertEqual(loader.load('fixture.good').VALUE, 17)

    def test_complete_core_map_and_startup_use_no_os_sys_import(self):
        root = Path(_PROJECT_SCRIPTS)
        sources, imports = {}, []
        for path in root.rglob('*.py'):
            if path.name == 'modMain.py':
                continue
            name = '.'.join(path.relative_to(root).with_suffix('').parts)
            package = path.name == '__init__.py'
            if package:
                name = name[:-9]
            if name:
                sources[name] = row(path.read_text(encoding='utf-8-sig'), package)
        def external(name, *args):
            imports.append(name)
            return builtins.__import__(name, *args)
        loader = source_loader.SourceModuleLoader(sources, external)
        api = loader.load('core.java_api')
        mapping = api.collect_java_api()
        scope = api.JavaApiImports(loader).install(mapping)
        entity_package = loader.import_module('net.minecraft.world.entity', fromlist=['Entity'])
        self.assertIs(entity_package.Entity, mapping['net.minecraft.world.entity.Entity'])
        manager = loader.load('core.translated_loader').TranslatedModLoader(lambda path: lambda ctx: None)
        manager.load({'schema_version': 1, 'mods': [{'mod_id': 'sample', 'entrypoint': 'start'}]})
        self.assertTrue(manager.activate()['sample']['ready'])
        self.assertFalse(set(name.split('.')[0] for name in imports) & {'os', 'sys', 'importlib'})
        manager.close()
        scope.close()
        loader.close()


if __name__ == '__main__':
    unittest.main()

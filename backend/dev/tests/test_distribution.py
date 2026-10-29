import ast
import json
import hashlib
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
from build_distribution import build, DEV, write_pack_archive
from test_content_registry import FakeEngine


class DistributionTests(unittest.TestCase):
    def test_java_archives_sources_and_metadata_are_not_delivered_in_behavior_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'original'
            shutil_module = __import__('shutil')
            shutil_module.copytree(DEV/'examples/multi_mod/neocore_example_base', root)
            for name in ('library.jar','Main.class','Main.java','notes.md','cache.pyc','data.json'):
                (root/name).write_text('development-only',encoding='utf-8')
            output = Path(temp)/'delivery'
            report = build(output,[{'pack_id':'test_content','folder':str(root),
                'entrypoints':{'neocore_example_base':'example.neocore_example_base.Main:start'}}])
            for pack in output.glob('*_behavior_pack'):
                self.assertTrue(all(p.suffix in ('.py','.json') for p in pack.rglob('*') if p.is_file()))
            mirror = output/'test_content_behavior_pack/original'
            self.assertTrue((mirror/'example/neocore_example_base/Main.py').exists())
            self.assertFalse((mirror/'META-INF/neoforge.mods.toml').exists())
            self.assertFalse((mirror/'data.json').exists())
            self.assertTrue((root/'library.jar').exists())
            self.assertTrue(report['excluded_development_files'])

    def test_generated_native_thin_entries_and_snapshots_run_together(self):
        names = ('neocore_example_base', 'neocore_example_addon')
        contents = [{'pack_id': name, 'folder': str(DEV / 'examples/multi_mod' / name),
                     'entrypoints': {name: 'example.' + name + '.Main:start'}} for name in names]
        saved_path, saved_modules = list(sys.path), dict(sys.modules)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'distribution'
            report = build(output, contents)
            self.assertFalse(report['engine_verified'])
            for pack in output.glob('*_behavior_pack'):
                manifest = json.loads((pack/'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual([m['type'] for m in manifest['modules']], ['data'])
                self.assertTrue((pack/'entities').is_dir())
                archive_path = Path(temp)/(pack.name + '.zip')
                write_pack_archive(pack, archive_path)
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertIn(pack.name + '/entities/', archive.namelist())
                    extracted = Path(temp)/('extracted_' + pack.name)
                    archive.extractall(extracted)
                    self.assertTrue((extracted/pack.name/'entities').is_dir())

                entries = list(pack.glob('*Scripts/modMain.py'))
                self.assertEqual(len(entries), 1)
                self.assertNotIn(b'\0', (entries[0].parent/'__init__.py').read_bytes())

            self.assertEqual(report['target']['neoforge_reference'], '21.1.233')
            self.assertFalse(report['target']['verified_compatibility'])
            inventory = json.loads((output / report['source_inventory']).read_text(encoding='utf-8'))
            self.assertEqual(len(inventory['core']), report['core_modules'])
            self.assertIn('core.config_session', inventory['core'])
            self.assertNotIn('core.extracted_mods', inventory['core'])
            for record in inventory['core'].values():
                source = Path(_PROJECT_SCRIPTS) / record['origin']
                self.assertEqual(record['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            for path in output.rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        self.assertFalse(any(alias.name.split('.')[0] in ('os', 'sys', 'importlib') for alias in node.names))
            sdk = types.ModuleType('mod')
            sdk.__path__ = []
            common = types.ModuleType('mod.common')
            common.__path__ = []
            binding_module = types.ModuleType('mod.common.mod')
            class Binding(object):
                @staticmethod
                def Binding(**kwargs):
                    return lambda cls: cls
                @staticmethod
                def InitServer():
                    return lambda method: method
                InitClient = InitServer
                DestroyServer = InitServer
                DestroyClient = InitServer
            binding_module.Mod = Binding
            engine, core = FakeEngine(), None
            try:
                sys.modules.update({'mod': sdk, 'mod.common': common, 'mod.common.mod': binding_module})
                for pack in output.glob('*_behavior_pack'):
                    sys.path.insert(0, str(pack))
                def register(namespace, name, path):
                    module_name, class_name = path.rsplit('.', 1)
                    cls = getattr(importlib.import_module(module_name), class_name)
                    instance = cls(namespace, name)
                    engine.systems[(namespace, name)] = instance
                    return instance
                engine.RegisterSystem = register
                core = importlib.import_module('NeoCoreSourceScripts.modMain')
                core.start(engine, 'SERVER')
                providers = []
                for name in names:
                    entry = importlib.import_module(name + 'Scripts.modMain')
                    providers.append(entry.register_provider(engine, 'SERVER'))
                engine.emit('Minecraft', 'Engine', 'LoadServerAddonScriptsAfter', {})
                system = engine.GetSystem('NeoCore', 'Loader')
                self.assertTrue(all(value['ready'] for value in system.GetContentReport()['mods'].values()))
                for unused in range(30):
                    engine.emit('Minecraft', 'Engine', 'OnScriptTickServer', {})
                states = [system.registry._session.loader.contexts[name].instance for name in names]
                self.assertEqual([state['ticks'] for state in states], [20, 20])
                core.close('SERVER')
                for provider in providers:
                    provider.Destroy()
                self.assertEqual(engine.listeners, [])
                self.assertTrue(all(state['closed'] for state in states))
                with self.assertRaises(ValueError):
                    build(output, contents)
            finally:
                if core is not None:
                    core.close('SERVER')
                sys.path[:] = saved_path
                prefixes = ('NeoCoreSourceScripts',) + tuple(name + 'Scripts' for name in names)
                for key in list(sys.modules):
                    if key.split('.')[0] in prefixes or key in ('mod', 'mod.common', 'mod.common.mod'):
                        if key in saved_modules:
                            sys.modules[key] = saved_modules[key]
                        else:
                            sys.modules.pop(key, None)


if __name__ == '__main__':
    unittest.main()

import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
config = Package().load('neoforge.config')


class Storage(object):
    def __init__(self):
        self.documents = {}
    def read_text(self, path):
        return self.documents.get(path)
    def write_text(self, path, text):
        self.documents[path] = text


class ConfigStorageTests(unittest.TestCase):
    def make_spec(self):
        builder = config.ModConfigSpec.Builder()
        first = builder.defineInRange('a', 1, 0, 10)
        second = builder.defineInRange('z', 2, 0, 10)
        return builder.build(), first, second

    def test_register_overloads_and_void_return(self):
        container = config.ModContainer('sample')
        empty = config.ModConfigSpec.Builder().build()
        self.assertIsNone(container.registerConfig(config.ModConfig.Type.COMMON, empty))
        self.assertEqual(container.getConfigs(), [])
        spec, _, _ = self.make_spec()
        self.assertIsNone(container.registerConfig(config.ModConfig.Type.COMMON, spec))
        self.assertEqual(container.getConfig(config.ModConfig.Type.COMMON).getFileName(), 'sample-common.toml')
        other, _, _ = self.make_spec()
        container.registerConfig(config.ModConfig.Type.CLIENT, other, 'custom.toml')
        self.assertEqual(container.getConfig(config.ModConfig.Type.CLIENT).getFileName(), 'custom.toml')

    def test_session_names_conflict_and_release(self):
        registry = config.ConfigRegistry()
        first = config.ModContainer('first', registry)
        second = config.ModContainer('second', registry)
        spec, _, _ = self.make_spec()
        first.registerConfig(config.ModConfig.Type.COMMON, spec, 'shared.toml')
        with self.assertRaises(config.IllegalStateException):
            second.registerConfig(config.ModConfig.Type.CLIENT, spec, 'shared.toml')
        self.assertEqual(second.getConfigs(), [])
        first.close()
        second.registerConfig(config.ModConfig.Type.CLIENT, spec, 'shared.toml')
        self.assertEqual(len(second.getConfigs()), 1)
        with self.assertRaises(config.IllegalStateException):
            first.registerConfig(config.ModConfig.Type.COMMON, spec)
        independent = config.ModContainer('independent', config.ConfigRegistry())
        independent.registerConfig(config.ModConfig.Type.COMMON, spec, 'shared.toml')

    def test_roundtrip_and_missing_document(self):
        spec, first, second = self.make_spec()
        storage = Storage()
        self.assertEqual(config.load_config_file(spec, 'missing', storage), 0)
        self.assertTrue(spec.isLoaded())
        first.set(7)
        config.save_config_file(spec, 'settings', storage)
        restored, a, z = self.make_spec()
        self.assertEqual(config.load_config_file(restored, 'settings', storage), 2)
        self.assertEqual((a.get(), z.get()), (7, 2))

    def test_invalid_document_never_partially_updates_values(self):
        spec, first, second = self.make_spec()
        storage = Storage()
        for text in ('{"a": 7, "z": 99}', '[1, 2]', 'null', 'false', '{'):
            storage.documents['settings'] = text
            with self.assertRaises(config.IllegalArgumentException):
                config.load_config_file(spec, 'settings', storage)
            self.assertEqual((first.get(), second.get()), (1, 2))
            self.assertFalse(spec.isLoaded())
        spec.loadFrom({'a': 4})
        with self.assertRaises(config.IllegalArgumentException):
            spec.loadFrom({'a': 8, 'z': 99})
        self.assertEqual(first.get(), 4)
        self.assertTrue(spec.isLoaded())

    def test_storage_failures_are_not_reported_as_success(self):
        spec, first, second = self.make_spec()
        with self.assertRaises(NotImplementedError):
            config.load_config_file(spec, 'settings')
        with self.assertRaises(NotImplementedError):
            config.save_config_file(spec, 'settings')
        class Broken(Storage):
            def read_text(self, path):
                raise IOError('read failed')
            def write_text(self, path, text):
                raise IOError('write failed')
        with self.assertRaises(IOError):
            config.load_config_file(spec, 'settings', Broken())
        with self.assertRaises(IOError):
            config.save_config_file(spec, 'settings', Broken())
        self.assertFalse(spec.isLoaded())


if __name__ == '__main__':
    unittest.main()

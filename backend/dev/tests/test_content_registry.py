# -*- coding: utf-8 -*-
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
registry = Package().load("core.content_registry")


class FakeSession(object):
    def __init__(self):
        self.loader = self
        self.results = {"sample": {"state": "initialized"}}
        self.closed = 0

    def close(self):
        self.closed += 1
        self.results["sample"]["state"] = "unloaded"


class FakeEngine(object):
    def __init__(self):
        self.listeners = []
        self.systems = {}

    def emit(self, namespace, system, event, args):
        for row in list(self.listeners):
            if row[:3] == (namespace, system, event):
                row[4](args)

    def GetServerSystemCls(self):
        engine = self
        class System(object):
            def __init__(self, namespace, name):
                self.namespace, self.name = namespace, name

            def ListenForEvent(self, namespace, system, event, owner, callback):
                engine.listeners.append((namespace, system, event, owner, callback))

            def UnListenForEvent(self, namespace, system, event, owner, callback):
                engine.listeners.remove((namespace, system, event, owner, callback))

            def BroadcastEvent(self, event, args):
                engine.emit(self.namespace, self.name, event, args)
        return System

    GetClientSystemCls = GetServerSystemCls

    def GetEngineNamespace(self):
        return "Minecraft"

    def GetEngineSystemName(self):
        return "Engine"

    def GetSystem(self, namespace, name):
        return self.systems.get((namespace, name))


class RegistryTests(unittest.TestCase):
    def test_destroy_attempts_all_owned_cleanup_and_all_engine_listeners(self):
        for missing_listener in (False, True):
            with self.subTest(missing_listener=missing_listener):
                engine = FakeEngine()
                session = FakeSession()
                cls = registry.install_content_system(engine, lambda specs: session)
                core = cls('NeoCore', 'Loader')
                core.RegisterContent('sample_pack', 1, [{'folder':'original'}])
                core._on_scripts_loaded()
                calls = []
                class Broken(object):
                    def close(self):
                        calls.append('broken')
                        raise RuntimeError('teardown failed')
                class Healthy(object):
                    def close(self):
                        calls.append('healthy')
                core._owned_runtimes = {0:Broken(),1:Healthy()}
                core._entity_mod_bus = Broken()
                if missing_listener:
                    engine.listeners.pop(0)
                core.Destroy()
                self.assertEqual(calls.count('broken'), 2)
                self.assertIn('healthy', calls)
                self.assertEqual(session.closed, 1)
                self.assertEqual(engine.listeners, [])
                self.assertEqual(core._owned_runtimes, {})
                self.assertEqual(core.GetContentReport()['state'], 'close_failed')
                self.assertTrue(core.GetContentReport()['cleanup_errors'])
                core.Destroy()
                self.assertEqual(session.closed, 1)

    def test_activation_failure_closes_session_and_does_not_start_runtime_driver(self):
        class Session(FakeSession):
            def activate(self):
                raise RuntimeError('activation failed')
        session = Session()
        engine = FakeEngine()
        cls = registry.install_content_system(engine, lambda specs: session)
        core = cls('NeoCore', 'Loader')
        core.RegisterContent('sample_pack', 1, [{'folder':'original'}])
        core._on_scripts_loaded()
        self.assertEqual(core.GetContentReport()['state'], 'failed')
        self.assertEqual(session.closed, 1)
        self.assertIsNone(core._tick_driver)
        self.assertRaises(ValueError, core.GetEntityRuntime)
        core.Destroy()

    def test_activation_and_cleanup_errors_are_both_preserved(self):
        class Session(FakeSession):
            def activate(self):
                raise RuntimeError('activation root cause')
            def close(self):
                self.closed += 1
                raise RuntimeError('cleanup root cause')
        session = Session()
        reg = registry.ContentRegistry(lambda specs: session)
        reg.register('sample_pack', 1, [{'folder':'original'}])
        report = reg.start()
        self.assertEqual(report['error'], 'activation root cause')
        self.assertEqual(report['cleanup_errors'], ['cleanup root cause'])
        self.assertEqual(session.closed, 1)

    def test_context_cleanup_continues_after_bus_failure_and_validation_is_retryable(self):
        pkg = Package()
        loader_module = pkg.load('core.translated_loader')
        context = loader_module.ModContext({'mod_id':'sample'})
        calls = []
        context.on_close(lambda: calls.append('callback'))
        class Broken(object):
            def clear(self):
                raise RuntimeError('bus clear failed')
        class Healthy(object):
            def clear(self):
                calls.append('mod_bus')
        context.game_bus, context.mod_bus = Broken(), Healthy()
        self.assertEqual(context.close(), ['game_bus: bus clear failed'])
        self.assertEqual(calls, ['callback', 'mod_bus'])
        context.close()
        self.assertEqual(calls, ['callback', 'mod_bus'])
        loader = loader_module.TranslatedModLoader(lambda entry: lambda context: None)
        with self.assertRaises(ValueError):
            loader.load({'schema_version':1,'mods':[{'mod_id':'sample','side':'BAD'}]})
        self.assertFalse(loader._started)
        self.assertEqual(loader.load({'schema_version':1,'mods':[]}), {})
        loader.close()

    def test_init_order_does_not_change_combined_session(self):
        for side, core_first in (("SERVER", True), ("SERVER", False),
                                 ("CLIENT", True), ("CLIENT", False)):
            with self.subTest(core_first=core_first, side=side):
                engine = FakeEngine()
                calls = []
                session = FakeSession()
                def factory(specs):
                    calls.append(specs)
                    return session
                def start_core():
                    cls = registry.install_content_system(engine, factory, side)
                    engine.systems[("NeoCore", "Loader")] = cls("NeoCore", "Loader")
                def start_provider():
                    provider = engine.GetServerSystemCls()("Content", "Provider")
                    def register(args):
                        core = engine.GetSystem("NeoCore", "Loader")
                        core.RegisterContent("content_pack", 1, [
                            {"folder": "own_pack/mod", "entrypoints": {"sample": "com.sample.Main:start"}}])
                    provider.ListenForEvent("NeoCore", "Loader", "NeoCoreCollectContent", provider, register)
                if core_first:
                    start_core()
                    start_provider()
                else:
                    start_provider()
                    start_core()
                self.assertEqual(calls, [])
                engine.emit("Minecraft", "Engine",
                            "LoadServerAddonScriptsAfter" if side == "SERVER" else "LoadClientAddonScriptsAfter", {})
                core = engine.GetSystem("NeoCore", "Loader")
                self.assertEqual(len(calls), 1)
                self.assertEqual(core.GetContentReport()["packs"], ["content_pack"])
                engine.emit("Minecraft", "Engine",
                            "LoadServerAddonScriptsAfter" if side == "SERVER" else "LoadClientAddonScriptsAfter", {})
                self.assertEqual(len(calls), 1)
                core.Destroy()
                self.assertEqual(session.closed, 1)

    def test_distributed_thin_template_registers_both_sides_without_core_imports(self):
        import types
        from py2to3lite import compile_module
        sdk = types.ModuleType("mod")
        sdk.__path__ = []
        common = types.ModuleType("mod.common")
        common.__path__ = []
        binding_module = types.ModuleType("mod.common.mod")
        class Binding(object):
            @staticmethod
            def Binding(**kwargs):
                return lambda cls: cls
            @staticmethod
            def InitServer():
                return lambda method: method
            InitClient = InitServer
        binding_module.Mod = Binding
        stubs = {"mod": sdk, "mod.common": common, "mod.common.mod": binding_module}
        saved = dict((key, sys.modules.get(key)) for key in stubs)
        try:
            sys.modules.update(stubs)
            source = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "examples", "ExampleContentScripts", "modMain.py")
            template = compile_module(source, "_content_template_test", False)
            for side in ("SERVER", "CLIENT"):
                engine = FakeEngine()
                def register(namespace, name, path):
                    cls = getattr(template, path.rsplit(".", 1)[-1])
                    instance = cls(namespace, name)
                    engine.systems[(namespace, name)] = instance
                    return instance
                engine.RegisterSystem = register
                provider = template.register_provider(engine, side)
                cls = registry.install_content_system(engine, lambda specs: FakeSession(), side)
                core = cls("NeoCore", "Loader")
                engine.systems[("NeoCore", "Loader")] = core
                engine.emit("Minecraft", "Engine",
                            "LoadServerAddonScriptsAfter" if side == "SERVER"
                            else "LoadClientAddonScriptsAfter", {})
                self.assertEqual(core.GetContentReport()["packs"], ["example_content_pack"])
                provider.Destroy()
                core.Destroy()
                self.assertEqual(engine.listeners, [])
        finally:
            for key, previous in saved.items():
                if previous is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = previous

    def test_cleanup_failure_is_visible_and_not_retried(self):
        class FailedSession(FakeSession):
            def close(self):
                self.closed += 1
                self.results["sample"] = {
                    "state": "cleanup_failed", "message": "listener removal failed"}
        session = FailedSession()
        manager = registry.ContentRegistry(lambda specs: session)
        manager.register("pack", 1, [{"folder": "pack/mod"}])
        manager.start()
        report = manager.close()
        self.assertEqual(report["state"], "close_failed")
        self.assertIn("sample: listener removal failed", report["error"])
        self.assertEqual(manager.close(), report)
        self.assertEqual(session.closed, 1)

    def test_protocol_duplicate_conflict_and_late_registration(self):
        manager = registry.ContentRegistry(lambda specs: FakeSession())
        spec = [{"folder": "pack/mod"}]
        with self.assertRaises(ValueError):
            manager.register("pack", 2, spec)
        manager.register("pack", 1, spec)
        self.assertTrue(manager.register("pack", 1, spec)["duplicate"])
        with self.assertRaises(ValueError):
            manager.register("pack", 1, [{"folder": "other"}])
        spec[0]["folder"] = "mutated"
        self.assertEqual(manager._packs["pack"][0]["folder"], "pack/mod")
        manager.start()
        with self.assertRaises(ValueError):
            manager.register("late", 1, spec)
        manager.close()
        manager.close()

    def test_all_folders_reach_one_session_and_failure_is_reported(self):
        seen = []
        def failed(specs):
            seen.extend(specs)
            raise RuntimeError("duplicate module")
        manager = registry.ContentRegistry(failed)
        manager.register("bb", 1, [{"folder": "bb"}])
        manager.register("aa", 1, [{"folder": "aa"}])
        report = manager.start()
        self.assertEqual(seen, [{"folder": "aa"}, {"folder": "bb"}])
        self.assertEqual(report["state"], "failed")
        self.assertIn("duplicate module", report["error"])


if __name__ == "__main__":
    unittest.main()

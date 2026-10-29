# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import zipfile
import json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from prepare_translated_mods import prepare
loader = Package().load("core.translated_loader")


class LoaderTests(unittest.TestCase):
    def test_content_cannot_publish_builtin_or_override_host_platform_versions(self):
        for platform in ({},{'neoforge':'21.1.1'},{'host_platform':'3'}):
            with self.subTest(platform=platform):
                calls=[];manager=loader.TranslatedModLoader(lambda path:lambda ctx:calls.append(ctx.mod_id),platform_versions=platform)
                claimed='host_platform' if 'host_platform' in platform else 'neoforge'
                rows=[{'mod_id':claimed,'version':'21.1.233','entrypoint':'fake'},
                      {'mod_id':'addon','entrypoint':'bad','dependency_constraints':[{'modId':'neoforge','versionRange':'[21.1.233,21.2)','type':'required'}]},
                      {'mod_id':'independent','entrypoint':'ok'}]
                report=manager.load({'schema_version':1,'mods':rows})
                self.assertEqual(report[claimed]['phase'],'identity');self.assertEqual(report['addon']['state'],'blocked')
                self.assertEqual(calls,['independent']);self.assertEqual(manager.platform_versions,platform)
                manager.close()
    def test_shutdown_preserves_activation_failure_and_cleanup_diagnostics(self):
        pkg = Package()
        lifecycle = pkg.load('neoforge.event.fml.lifecycle')
        module = pkg.load('core.translated_loader')
        def entry(ctx):
            if ctx.mod_id == 'bad':
                def fail(event):
                    raise RuntimeError('setup root cause')
                ctx.mod_bus.subscribe(fail, lifecycle.FMLCommonSetupEvent)
        manager = module.TranslatedModLoader(lambda path: entry)
        manager.load({'schema_version':1,'mods':[
            {'mod_id':'bad','entrypoint':'entry'}, {'mod_id':'good','entrypoint':'entry'}]})
        report = manager.activate()
        self.assertEqual(report['bad']['state'], 'failed')
        self.assertTrue(report['good']['ready'])
        closed = manager.close()
        self.assertEqual(closed['bad']['startup_result']['message'], 'setup root cause')
        self.assertEqual(closed['bad']['startup_result']['phase'], 'common_setup')
        self.assertEqual(closed['bad']['cleanup_errors'], [])
        self.assertEqual(manager.close(), closed)

    def test_failed_entrypoint_releases_config_names(self):
        class Spec(object):
            def isEmpty(self):
                return False
        class Kind(object):
            def name(self):
                return 'COMMON'
        def entry(context):
            context.mod_container.registerConfig(Kind(), Spec(), 'shared.toml')
            if context.mod_id == 'a_bad':
                raise ValueError('entrypoint failed')
        manager = loader.TranslatedModLoader(lambda path: entry)
        report = manager.load({'schema_version': 1, 'mods': [
            {'mod_id': 'a_bad', 'entrypoint': 'x'},
            {'mod_id': 'b_good', 'entrypoint': 'x'}]})
        self.assertEqual(report['a_bad']['state'], 'failed')
        self.assertEqual(report['b_good']['state'], 'initialized')
        self.assertEqual(len(manager.config_registry._files), 1)
        manager.close()
        self.assertEqual(manager.config_registry._files, {})

    def test_dependency_order_and_context_isolation(self):
        calls = []
        manager = loader.TranslatedModLoader(lambda path: lambda ctx: calls.append(ctx.mod_id))
        result = manager.load({"schema_version": 1, "mods": [
            {"mod_id": "addon", "entrypoint": "addon:start", "requires": ["base"]},
            {"mod_id": "base", "entrypoint": "base:start"}]})
        self.assertEqual(calls, ["base", "addon"])
        self.assertEqual(result["addon"]["state"], "initialized")
        self.assertIsNot(manager.contexts["base"].mod_bus, manager.contexts["addon"].mod_bus)
        with self.assertRaises(ValueError):
            manager.load({"schema_version": 1, "mods": []})

    def test_failure_blocks_dependents_but_not_independent_mods(self):
        def resolve(path):
            if path == "bad":
                raise ImportError("missing translation")
            return lambda context: None
        manager = loader.TranslatedModLoader(resolve)
        rows = [{"mod_id": "bad", "entrypoint": "bad"},
                {"mod_id": "dependent", "entrypoint": "ok", "requires": ["bad"]},
                {"mod_id": "good", "entrypoint": "ok"},
                {"mod_id": "missing", "entrypoint": "ok", "requires": ["absent"]},
                {"mod_id": "cycle_a", "entrypoint": "ok", "requires": ["cycle_b"]},
                {"mod_id": "cycle_b", "entrypoint": "ok", "requires": ["cycle_a"]}]
        result = manager.load({"schema_version": 1, "mods": rows})
        self.assertEqual(result["good"]["state"], "initialized")
        self.assertEqual(result["bad"]["state"], "failed")
        for name in ("dependent", "missing", "cycle_a", "cycle_b"):
            self.assertEqual(result[name]["state"], "blocked")

    def test_duplicate_rejected_before_any_entrypoint_runs(self):
        calls = []
        manager = loader.TranslatedModLoader(lambda path: calls.append(path))
        with self.assertRaises(ValueError):
            manager.load({"schema_version": 1, "mods": [
                {"mod_id": "same"}, {"mod_id": "same"}]})
        self.assertEqual(calls, [])

    def test_numeric_range_boundaries_and_unsupported_versions(self):
        versions = Package().load("core.mod_versions")
        self.assertTrue(versions.matches("1.2.0", "[1.2]"))
        self.assertTrue(versions.matches("1.9", "[1.2,2)"))
        self.assertFalse(versions.matches("2", "[1.2,2)"))
        self.assertTrue(versions.matches("3", "[1,)"))
        with self.assertRaises(ValueError):
            versions.matches("1.0-beta", "[1,2)")
        with self.assertRaises(ValueError):
            versions.matches("1", "[2,1]")

    def test_version_failure_happens_before_import(self):
        calls = []
        manager = loader.TranslatedModLoader(lambda path: lambda ctx: calls.append(ctx.mod_id))
        report = manager.load({"schema_version": 1, "mods": [
            {"mod_id": "base", "version": "2", "entrypoint": "ok"},
            {"mod_id": "addon", "entrypoint": "ok", "dependency_constraints": [
                {"modId": "base", "versionRange": "[1,2)", "type": "required"}]}]})
        self.assertEqual(calls, ["base"])
        self.assertEqual(report["addon"]["phase"], "dependencies")

    def test_platform_must_be_explicit_and_other_side_is_skipped(self):
        index = {"schema_version": 1, "mods": [
            {"mod_id": "addon", "entrypoint": "ok", "dependency_constraints": [
                {"modId": "minecraft", "versionRange": "[1.21,1.22)", "type": "required"},
                {"modId": "client_lib", "type": "required", "side": "CLIENT"}]},
            {"mod_id": "client_only", "side": "CLIENT", "entrypoint": "missing"}]}
        manager = loader.TranslatedModLoader(lambda path: lambda ctx: None)
        self.assertEqual(manager.load(index)["addon"]["state"], "blocked")
        manager = loader.TranslatedModLoader(lambda path: lambda ctx: None,
                                               platform_versions={"minecraft": "1.21.1"})
        result = manager.load(index)
        self.assertEqual(result["addon"]["state"], "initialized")
        self.assertEqual(result["client_only"]["state"], "skipped")

    def test_required_before_dependency_failure_cleans_dependent(self):
        cleaned = []
        def resolve(path):
            if path == "bad":
                raise RuntimeError("broken dependency")
            def start(ctx):
                ctx.on_close(lambda: cleaned.append(ctx.mod_id))
            return start
        manager = loader.TranslatedModLoader(resolve)
        report = manager.load({"schema_version": 1, "mods": [
            {"mod_id": "addon", "entrypoint": "ok", "dependency_constraints": [
                {"modId": "base", "type": "required", "ordering": "BEFORE"}]},
            {"mod_id": "base", "entrypoint": "bad"}]})
        self.assertEqual(report["addon"]["state"], "blocked")
        self.assertEqual(cleaned, ["addon"])

    def test_shared_dispatch_and_reverse_idempotent_cleanup(self):
        messages, cleaned = [], []
        class Event(object):
            pass
        def resolve(path):
            def start(ctx):
                ctx.game_bus.subscribe(lambda event: messages.append(ctx.mod_id), Event)
                ctx.on_close(lambda: cleaned.append(ctx.mod_id))
            return start
        manager = loader.TranslatedModLoader(resolve)
        manager.load({"schema_version": 1, "mods": [
            {"mod_id": "base", "entrypoint": "ok"},
            {"mod_id": "addon", "entrypoint": "ok", "requires": ["base"]}]})
        self.assertEqual(manager.post_game_event(Event()), 2)
        self.assertEqual(messages, ["base", "addon"])
        manager.close()
        manager.close()
        self.assertEqual(cleaned, ["addon", "base"])
        self.assertEqual(manager.post_game_event(Event()), 0)

    def test_failed_entrypoint_runs_registered_cleanup(self):
        cleaned = []
        def start(ctx):
            ctx.on_close(lambda: cleaned.append("closed"))
            raise RuntimeError("entry failed")
        manager = loader.TranslatedModLoader(lambda path: start)
        result = manager.load({"schema_version": 1, "mods": [
            {"mod_id": "broken", "entrypoint": "ok"}]})
        self.assertEqual(result["broken"]["state"], "failed")
        self.assertEqual(cleaned, ["closed"])

    def test_preparation_preserves_jar_and_declared_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jar = root / "unchanged.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/neoforge.mods.toml",
                    '[[mods]]\nmodId="sample"\nversion="1.0"\n')
            before = jar.read_bytes()
            config = root / "bindings.json"
            config.write_text(json.dumps({"bindings": [{
                "source_jar": "unchanged.jar", "entrypoints": {"sample": "translated.sample:start"}}]}))
            result = prepare(config)
            self.assertEqual(result["mods"][0]["mod_id"], "sample")
            self.assertEqual(result["mods"][0]["source_jar"], str(jar.resolve()))
            self.assertEqual(jar.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

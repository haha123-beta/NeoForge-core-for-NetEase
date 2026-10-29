# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
extracted = package.load("core.extracted_mods")


class ExtractedTests(unittest.TestCase):
    def make_mod(self, base, mod_id, extra=""):
        root = base / mod_id
        (root / "META-INF").mkdir(parents=True)
        (root / "META-INF/neoforge.mods.toml").write_text(
            '[[mods]]\nmodId="' + mod_id + '"\nversion="1.0"\n' + extra)
        code = root / "example_namespace" / mod_id
        code.mkdir(parents=True)
        (code / "helper.py").write_text("VALUE = 42\n")
        (code / "Main.py").write_text(
            "from example_namespace." + mod_id + ".helper import VALUE\n"
            "def start(context):\n    return VALUE\n")
        return {"folder": str(root), "entrypoints": {
            mod_id: "example_namespace." + mod_id + ".Main:start"}}

    def test_declared_mixin_and_transformer_block_before_import(self):
        for kind in ("toml", "manifest", "service", "invalid"):
            with tempfile.TemporaryDirectory() as temp:
                spec = self.make_mod(Path(temp), "guarded",
                    '\n[[mixins]]\nconfig="hooks.json"\n' if kind == "toml" else "")
                root = Path(spec["folder"])
                if kind == "toml":
                    (root / "hooks.json").write_text('{}')
                elif kind == "manifest":
                    (root / "META-INF/MANIFEST.MF").write_text('MixinConfigs: hooks.json\n')
                elif kind == "invalid":
                    (root / "broken.mixins.json").write_text('{')
                else:
                    service = root / "META-INF/services/cpw.mods.modlauncher.api.ITransformationService"
                    service.parent.mkdir()
                    service.write_text('example.Transformer')
                session = extracted.ExtractedModSession([spec], os, sys)
                try:
                    self.assertEqual(session.report["guarded"]["phase"], "compatibility")
                    self.assertNotIn("example_namespace.guarded.Main", sys.modules)
                finally:
                    session.close()

    def test_two_real_unpacked_mods_keep_paths_and_share_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = self.make_mod(root, "first")
            two = self.make_mod(root, "second",
                '[[dependencies.second]]\nmodId="first"\ntype="required"\n'
                'versionRange="[1,2)"\nordering="AFTER"\n')
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            previous = sys.dont_write_bytecode
            sys.dont_write_bytecode = True
            try:
                session = extracted.ExtractedModSession([two, one], os, sys)
                self.assertEqual(session.loader.order, ["first", "second"])
                self.assertEqual(session.loader.contexts["second"].instance, 42)
                self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))
                session.close()
                session.close()
                self.assertNotIn("example_namespace", sys.modules)
                self.assertNotIn(one["folder"], sys.path)
            finally:
                sys.dont_write_bytecode = previous

    def test_two_sides_share_imports_until_last_session_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.make_mod(Path(temp), "shared")
            server = extracted.ExtractedModSession([spec], os, sys, side="SERVER")
            client = extracted.ExtractedModSession([spec], os, sys, side="CLIENT")
            try:
                self.assertIs(server.imports, client.imports)
                self.assertIsNot(server.loader.contexts["shared"], client.loader.contexts["shared"])
                self.assertEqual(client.loader.contexts["shared"].side, "CLIENT")
                server.close()
                server.close()
                self.assertIn("example_namespace.shared.Main", sys.modules)
                self.assertEqual(client.loader.contexts["shared"].instance, 42)
            finally:
                server.close()
                client.close()
            self.assertNotIn("example_namespace.shared.Main", sys.modules)
            self.assertNotIn("example_namespace", sys.modules)

    def test_existing_package_initializer_is_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.make_mod(Path(temp), "regular")
            root = Path(spec["folder"])
            (root / "example_namespace/__init__.py").write_text("MARKER = 17\n")
            session = extracted.ExtractedModSession([spec], os, sys)
            try:
                self.assertEqual(session.report["regular"]["state"], "initialized")
                self.assertEqual(__import__("example_namespace").MARKER, 17)
            finally:
                session.close()

    def test_original_metadata_dependency_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.make_mod(Path(temp), "dependent",
                '[[dependencies.dependent]]\nmodId="absent"\ntype="required"\n')
            session = extracted.ExtractedModSession([spec], os, sys)
            try:
                self.assertEqual(session.report["dependent"]["state"], "blocked")
                self.assertNotIn("example_namespace.dependent.Main", sys.modules)
            finally:
                session.close()

    def test_duplicate_modules_rejected_without_import_pollution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.make_mod(root / "a", "same")
            second = self.make_mod(root / "b", "same")
            with self.assertRaises(ValueError):
                extracted.ExtractedModSession([first, second], os, sys)
            self.assertNotIn("example_namespace", sys.modules)

    def test_missing_entrypoint_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.make_mod(Path(temp), "missing")
            spec["entrypoints"]["missing"] = "example_namespace.missing.NoSuchModule:start"
            session = extracted.ExtractedModSession([spec], os, sys)
            try:
                self.assertEqual(session.report["missing"]["state"], "failed")
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()

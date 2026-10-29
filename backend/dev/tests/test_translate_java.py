import os
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate


class DirectoryTranslationTests(unittest.TestCase):
    def test_duplicate_project_declarations_and_consumers_are_not_generated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'mod'
            (root / 'demo').mkdir(parents=True)
            for name in ('Helper.java', 'Second.java'):
                (root/'demo'/name).write_text('package demo; class Helper {}')
            (root/'demo/Main.java').write_text('package demo; class Main { '
                'Object create(){return new Helper();} }')
            report = translate(root, dry_run=True)
            self.assertEqual(report['generated_for_review'], 0)
            self.assertEqual(report['manual_review'], 3)
            self.assertEqual(report['ambiguous_project_types'], ['demo.Helper'])
            for row in report['results']:
                self.assertEqual(len(row['details']['candidates']), 2)
                self.assertEqual({x['file'] for x in row['details']['candidates']},
                    {'demo/Helper.java', 'demo/Second.java'})

    def test_same_package_types_use_original_paths_without_eager_unused_imports(self):
        from harness import Package
        from build_source_bundle import collect_sources
        pkg = Package()
        loader_type = pkg.load('core.source_modules').SourceModuleLoader
        java_api = pkg.load('core.java_api')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'mod'
            (root / 'demo').mkdir(parents=True)
            (root / 'demo/Helper.java').write_text(
                'package demo; class Helper { static boolean is(){return true;} }')
            (root / 'demo/Main.java').write_text(
                'package demo; class Main { boolean check(){return new Helper().is();} '
                'boolean checkStatic(){return Helper.is();} '
                'boolean checkQualifiedStatic(){return demo.Helper.is();} '
                'boolean checkQualified(){return new demo.Helper().is();} }')
            (root / 'demo/Unused.java').write_text(
                'package demo; class Unused { synchronized long unsupported(long x){return x+1L;} }')
            report = translate(root, Path(temporary) / 'out')
            main = next(r for r in report['results'] if r['file']=='demo/Main.java')
            self.assertEqual(main['project_dependencies'], ['demo/Helper.java'])
            self.assertEqual(main['missing_generated_dependencies'], [])
            runtime = loader_type(collect_sources(Path(temporary) / 'out/mod'))
            scope = java_api.JavaApiImports(runtime).install(java_api.collect_java_api())
            try:
                obj = runtime.load('demo.Main').Main()
                self.assertNotIn('demo.Helper', runtime.modules)
                self.assertTrue(obj.check())
                self.assertTrue(obj.checkStatic())
                self.assertTrue(obj.checkQualifiedStatic())
                self.assertTrue(obj.checkQualified())
                self.assertNotIn('demo.Unused', runtime.modules)
            finally:
                scope.close()
                runtime.close()

    def test_annotations_and_parse_errors_retain_actionable_source_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'input'
            root.mkdir()
            (root / 'Annotated.java').write_text(
                'class Annotated {\n @EventBusSubscriber(modid="original")\n void call() {}\n}', encoding='utf-8')
            (root / 'Broken.java').write_text(
                'class Broken {\n int call() {\n return ???;\n }\n}', encoding='utf-8')
            report = translate(root, dry_run=True)
            rows = {row['file']: row for row in report['results']}
            annotation = rows['Annotated.java']
            self.assertEqual(annotation['line'], 2)
            self.assertEqual(annotation['details']['name'], 'EventBusSubscriber')
            self.assertIn('modid="original"', annotation['details']['source'])
            syntax = rows['Broken.java']
            self.assertGreater(syntax['line'], 1)
            self.assertEqual(syntax['details']['category'], 'syntax')
            self.assertTrue(syntax['details']['syntax_errors'])
            self.assertIn('span', syntax['details']['syntax_errors'][0])

    def test_mirrored_paths_resources_and_explicit_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'mod'
            (root / 'sample').mkdir(parents=True)
            (root / 'assets').mkdir()
            (root / 'assets/data.txt').write_text('original resource')
            good = root / 'sample/Good.java'
            good.write_text('package sample; class Good { boolean is(){return true;} }')
            (root / 'sample/NeedsMath.java').write_text('package sample; class NeedsMath { synchronized long f(long x){return x+1L;} }')
            output = Path(temporary) / 'converted'
            report = translate(root, output)
            self.assertEqual((report['generated_for_review'], report['manual_review'], report['failed']), (1, 1, 0))
            self.assertTrue((output / 'mod/sample/Good.py').is_file())
            self.assertFalse((output / 'mod/sample/NeedsMath.py').exists())
            self.assertEqual((output / 'mod/assets/data.txt').read_text(), 'original resource')
            self.assertEqual(good.read_text(), 'package sample; class Good { boolean is(){return true;} }')
            self.assertTrue((output / 'manual_review.txt').is_file())
            self.assertEqual(report['ready_mods'], 0)
            with self.assertRaises(ValueError):
                translate(root, output)

    def test_project_import_uses_original_module_and_reports_missing_generation(self):
        import types
        from harness import Package
        from build_source_bundle import collect_sources
        pkg = Package()
        loader_type = pkg.load('core.source_modules').SourceModuleLoader
        java_api = pkg.load('core.java_api')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'mod'
            (root / 'demo').mkdir(parents=True)
            (root / 'demo/Helper.java').write_text('package demo; public class Helper { public boolean is(){return true;} }')
            (root / 'demo/Main.java').write_text('package demo; import demo.Helper; public class Main { public boolean check(){return new Helper().is();} }')
            output = Path(temporary) / 'result'
            report = translate(root, output)
            self.assertEqual(report['generated_for_review'], 2)
            main = next(row for row in report['results'] if row['file']=='demo/Main.java')
            self.assertEqual(main['project_dependencies'], ['demo/Helper.java'])
            self.assertEqual(main['missing_generated_dependencies'], [])
            runtime = loader_type(collect_sources(output / 'mod'))
            scope = java_api.JavaApiImports(runtime).install(java_api.collect_java_api())
            try:
                self.assertTrue(runtime.load('demo.Main').Main().check())
            finally:
                scope.close()
                runtime.close()
            (root / 'demo/Helper.java').write_text('package demo; public class Helper { public synchronized long value(long x){return x+1L;} }')
            dry = translate(root, dry_run=True)
            main = next(row for row in dry['results'] if row['file']=='demo/Main.java')
            self.assertEqual(main['status'], 'MANUAL_REVIEW')
            self.assertEqual(main['details']['name'], 'is')
            (root / 'demo/Factory.java').write_text('package demo; class Factory {Object make(){return new Helper();}}')
            dry = translate(root, dry_run=True)
            factory = next(row for row in dry['results'] if row['file']=='demo/Factory.java')
            self.assertEqual(factory['missing_generated_dependencies'], ['demo/Helper.java'])
            self.assertEqual(dry['ready_mods'], 0)

    def test_dry_run_and_existing_python_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'input'
            root.mkdir()
            (root / 'A.java').write_text('class A {}')
            (root / 'A.py').write_text('preserve = True')
            output = Path(temporary) / 'result'
            report = translate(root, output, dry_run=True)
            self.assertEqual(report['manual_review'], 1)
            self.assertFalse(output.exists())
            self.assertEqual((root / 'A.py').read_text(), 'preserve = True')
            with self.assertRaises(ValueError):
                translate(root, root / 'nested')


if __name__ == '__main__':
    unittest.main()

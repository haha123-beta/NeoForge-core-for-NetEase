import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from translate_java import translate
from build_source_bundle import core_bundle, collect_sources
from probe_session_cleanup_r51_contract import run as cleanup
JAVA = Path('E:/Java/jdk-21.0.10/bin/java.exe')
TOOLS = '''package util; public class Tools {
public static final int BASE=7; public static final String TITLE="ok";
public static int add(int a,int b){return a+b;}
public static int choose(int a){return a+2;} public static int choose(Object a){return 9;}
}'''
IMPORTS = 'package demo; import static util.Tools.BASE; import static util.Tools.TITLE; import static util.Tools.add; import static util.Tools.choose; '
CASES = [
    IMPORTS + 'public class Use {public int run(){return add(BASE,choose(1));}}',
    IMPORTS + 'public class Use {public int run(){int BASE=5;return add(BASE,choose((Object)null));}}',
    IMPORTS + 'public class Use {public int BASE=2;public int choose(int n){return n+1;}public int run(){return add(BASE,choose(1));}}',
    IMPORTS + 'public class Use {public String run(){return TITLE;}}']
CROSS_FILES = {
    'util/Box.java':'package util; public class Box {}',
    'util/Tools.java':'package util; public class Tools {public static Box make(){return new Box();} public static int choose(Box value){return 3;} public static int choose(Object value){return 9;}}',
    'demo/Use.java':'package demo; import static util.Tools.make; import static util.Tools.choose; public class Use {public int run(){return choose(make());}}'}


def fixture(root, consumer):
    files = {'util/Tools.java': TOOLS, 'demo/Use.java': consumer}
    for name, text in files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8')
    return files


def oracle(root, files):
    probe = root / 'Probe.java'
    probe.write_text('public class Probe {public static void main(String[] args){System.out.print(new demo.Use().run());}}', encoding='utf-8')
    build = root / 'classes'; build.mkdir()
    process = subprocess.run([str(JAVA.with_name('javac.exe')), '-encoding', 'UTF-8', '-d', str(build)] + [str(root/name) for name in files] + [str(probe)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    process = subprocess.run([str(JAVA), '-cp', str(build), 'Probe'], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    return process.stdout


class TranslationR51Tests(unittest.TestCase):
    def test_cross_package_reference_return_keeps_declaring_type_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir()
            for name,source in CROSS_FILES.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')
            report=translate(root,Path(folder)/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report)
            core=core_bundle()['sources'];core.update(collect_sources(Path(folder)/'out/original'))
            runtime=Package().load('core.source_modules').SourceModuleLoader(core)
            scope=runtime.load('core.java_api').JavaApiImports(runtime).install(runtime.load('core.java_api').collect_java_api())
            try: actual=str(runtime.load('demo.Use').Use().run())
            finally:scope.close();runtime.close()
            self.assertEqual(actual,oracle(root,CROSS_FILES))
            self.assertEqual(actual,'3')
    def test_four_original_java_cases_match_jdk_with_no_new_runtime_helper(self):
        for index, source in enumerate(CASES):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)/'original'; root.mkdir(); files = fixture(root,source)
                report = translate(root, Path(folder)/'out')
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(2,0,0),report)
                loader = Package().load('core.source_modules').SourceModuleLoader
                core = core_bundle()['sources']; core.update(collect_sources(Path(folder)/'out/original'))
                runtime = loader(core)
                scope = runtime.load('core.java_api').JavaApiImports(runtime).install(runtime.load('core.java_api').collect_java_api())
                try: actual = str(runtime.load('demo.Use').Use().run())
                finally: scope.close(); runtime.close()
                self.assertEqual(actual,oracle(root,files))
                self.assertNotIn('StaticImports@',json.dumps(report))

    def test_constant_only_import_does_not_load_owner_at_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'original'; root.mkdir()
            fixture(root,'package demo; import static util.Tools.BASE; public class Use {public int run(){return BASE;}}')
            report = translate(root,Path(folder)/'out')
            self.assertEqual(report['generated_for_review'],2,report)
            core = core_bundle()['sources']; core.update(collect_sources(Path(folder)/'out/original'))
            runtime = Package().load('core.source_modules').SourceModuleLoader(core)
            scope = runtime.load('core.java_api').JavaApiImports(runtime).install(runtime.load('core.java_api').collect_java_api())
            try:
                self.assertEqual(runtime.load('demo.Use').Use().run(),7)
                self.assertNotIn('util.Tools',runtime.modules)
            finally: scope.close(); runtime.close()

    def test_unsupported_imports_are_diagnosed(self):
        variants = [IMPORTS.replace('util.Tools.BASE','util.Tools.missing'),
            IMPORTS.replace('util.Tools.BASE','java.lang.Integer.MAX_VALUE')]
        for prefix in variants:
            with self.subTest(prefix=prefix),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();fixture(root,prefix+'public class Use {public int run(){return 1;}}')
                report=translate(root,Path(folder)/'out')
                row=next(row for row in report['results'] if row['file']=='demo/Use.java')
                self.assertEqual(row['status'],'MANUAL_REVIEW',report)
                self.assertIn('Static',row['reason'])

    def test_nonpublic_or_instance_method_import_is_rejected(self):
        for replacement in ('private static int add','public int add'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();fixture(root,CASES[0])
                path=root/'util/Tools.java';path.write_text(TOOLS.replace('public static int add',replacement),encoding='utf-8')
                report=translate(root,Path(folder)/'out')
                row=next(row for row in report['results'] if row['file']=='demo/Use.java')
                self.assertEqual(row['status'],'MANUAL_REVIEW',report)

    def test_nonliteral_fields_and_conflicting_owners_stay_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root,CASES[0])
            path=root/'util/Tools.java';path.write_text(TOOLS.replace('int BASE=7','int BASE=add(3,4)'),encoding='utf-8')
            report=translate(root,Path(folder)/'out')
            row=next(row for row in report['results'] if row['file']=='demo/Use.java')
            self.assertEqual(row['status'],'MANUAL_REVIEW',report)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir()
            fixture(root,CASES[0].replace('public class Use','import static other.Tools.BASE; public class Use'))
            path=root/'other/Tools.java';path.parent.mkdir();path.write_text('package other; public class Tools {public static final int BASE=8;}',encoding='utf-8')
            report=translate(root,Path(folder)/'out')
            row=next(row for row in report['results'] if row['file']=='demo/Use.java')
            self.assertEqual(row['status'],'MANUAL_REVIEW',report)

    def test_unicode_session_cleanup_attempts_all_owned_resources(self):
        self.assertEqual(len(cleanup(Package().load)['errors']),3)


if __name__=='__main__': unittest.main()

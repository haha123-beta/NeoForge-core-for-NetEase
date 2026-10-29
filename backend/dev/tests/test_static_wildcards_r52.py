import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle,collect_sources
from translate_java import translate
import test_translation_r51 as previous
UTILS={
 'left/Ints.java':'''package left; public class Ints {public static final int BASE=7;
 public static int choose(int n){return n+2;} public static int only(int n){return 1;}
 public static int add(int n){return n+1;} private static int hidden(){return 0;}
 public static int mutable=3;}''',
 'right/Refs.java':'''package right; public class Refs {public static final int BASE=30;
 public static int choose(Object n){return 9;} public static int only(String n){return 8;}
 public static int specific(String n){return 4;}}''',
 'third/Other.java':'''package third; public class Other {public static int specific(Object n){return 6;}
 public static int choose(int n){return 5;}}'''}
WILD='package demo; import static left.Ints.*; import static right.Refs.*; '
CASES=[
 WILD+'public class Use {public int run(){return choose(1)+choose((Object)null);}}',
 WILD+'import static left.Ints.BASE; public class Use {public int run(){return BASE+choose(2);}}',
 WILD+'public class Use {public int BASE=2;public int choose(int n){return 6;}public int run(){return BASE+choose(1);}}',
 'package demo; import static right.Refs.specific; import static third.Other.specific; public class Use {public int run(){return specific(null);}}',
 'package demo; import static right.Refs.*; import static third.Other.*; public class Use {public int run(){return specific(null);}}',
 WILD+'import static left.Ints.only; public class Use {public int run(){return only(1);}}',
 WILD+'public class Use {public int run(){int BASE=5;return BASE;}}',
 'package demo; import static left.Ints.*; import static left.Ints.*; public class Use {public int run(){return choose(1);}}',
 WILD+'public class Use {public int run(){return 1;}}',
 'package demo; import static right.Refs.*; import static left.Ints.*; public class Use {public int run(){return choose(1);}}',
 'package demo; import static third.Other.*; import static left.Ints.choose; public class Use {public int run(){return choose(1);}}']
BAD=[
 WILD+'public class Use {public int run(){return BASE;}}',
 'package demo; import static left.Ints.*; import static third.Other.*; public class Use {public int run(){return choose(1);}}',
 WILD+'import static left.Ints.only; public class Use {public int run(){return only("x");}}',
 WILD+'public class Use {public int run(){return mutable;}}',
 WILD+'public class Use {public int run(){return hidden();}}',
 'package demo; import static left.Ints.choose; import static third.Other.choose; public class Use {public int run(){return choose(1);}}']


def fixture(root,consumer):
    files=dict(UTILS,**{'demo/Use.java':consumer})
    for name,source in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')
    return files


def actual(folder):
    sources=core_bundle()['sources'];sources.update(collect_sources(folder))
    runtime=Package().load('core.source_modules').SourceModuleLoader(sources)
    api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
    try:return str(runtime.load('demo.Use').Use().run())
    finally:scope.close();runtime.close()


class StaticWildcardsR52Tests(unittest.TestCase):
    def test_eleven_original_java_cases_match_jdk(self):
        for index,source in enumerate(CASES):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,source)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(4,0,0),report)
                self.assertEqual(actual(Path(folder)/'out/original'),previous.oracle(root,files))

    def test_ambiguity_inaccessible_fields_and_explicit_priority_match_javac_rejection(self):
        for index,source in enumerate(BAD):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,source)
                report=translate(root,Path(folder)/'out')
                row=next(row for row in report['results'] if row['file']=='demo/Use.java')
                self.assertEqual(row['status'],'MANUAL_REVIEW',report)
                # Mutable field is valid Java but outside this translator batch.
                if index==3:continue
                process=subprocess.run([str(previous.JAVA.with_name('javac.exe')),'-encoding','UTF-8','-d',str(Path(folder)/'classes')]+[str(root/name) for name in files],capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)


if __name__=='__main__':unittest.main()

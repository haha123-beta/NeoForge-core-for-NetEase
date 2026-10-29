import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
import test_static_wildcards_r52 as previous

TOOLS = """package util; public class Tools {
 public static final int BASE=7;
 static final int LOCAL=2; protected static final int PROTECTED=3; private static final int PRIVATE=4;
 public static int choose(Object value){return 4;}
 private static int choose(String value){return 9;}
 public static int take(Object value){return 5;}
 private static int take(String value){return 8;}
 public static int packageChoice(Object value){return 6;}
 static int packageChoice(String value){return 10;}
 public static int protectedChoice(Object value){return 7;}
 protected static int protectedChoice(String value){return 11;}
 public static Object make(Object value){return value;}
 private static String make(String value){return value;}
 public static int narrow(int value){return value+2;}
 private static int narrow(Object value){return 12;}
 private static int hidden(){return 0;}
 public int instanceOnly(){return 0;}
}"""
OTHER='package other; public class Other {public static int choose(String value){return 2;}}'
PREFIX='package demo; import static util.Tools.*; '
CASES=[
 PREFIX+'public class Use {public int run(){return choose("x");}}',
 PREFIX+'public class Use {public int run(){return choose(null);}}',
 'package demo; import static util.Tools.choose; public class Use {public int run(){return choose("x");}}',
 PREFIX+'public class Use {public int run(){return take("x");}}',
 PREFIX+'public class Use {public int run(){return packageChoice("x")+protectedChoice(null);}}',
 PREFIX+'public class Use {public int run(){return choose(make("x"));}}',
 PREFIX+'import static other.Other.*; public class Use {public int run(){return choose(null);}}',
 PREFIX+'public class Use {public int run(){return narrow(3)+BASE;}}',
 PREFIX+'public class Use {public int choose(String value){return 1;}public int run(){return choose("x");}}',
 'package demo; import static util.Tools.take; public class Use {public int run(){return take(null);}}',
 'package demo; import static demo.Tools.*; public class Use {public int run(){return packageChoice("x")+protectedChoice(null)+choose("x");}}',
 'package demo; import static demo.Tools.packageChoice; public class Use {public int run(){return packageChoice(null);}}',
 'package demo; import static demo.Tools.LOCAL; import static demo.Tools.*; public class Use {public int run(){return LOCAL+PROTECTED;}}']
BAD=[
 PREFIX+'public class Use {public int run(){return hidden();}}',
 PREFIX+'public class Use {public int run(){return instanceOnly();}}',
 PREFIX+'public class Use {public int run(){return narrow((Object)null);}}',
 'package demo; import static util.Tools.hidden; public class Use {public int run(){return 1;}}',
 'package demo; import static util.Tools.instanceOnly; public class Use {public int run(){return 1;}}',
 PREFIX+'public class Use {public int run(){return choose();}}',
 PREFIX+'public class Use {public int run(){return LOCAL;}}',
 PREFIX+'public class Use {public int run(){return PROTECTED;}}',
 'package demo; import static demo.Tools.*; public class Use {public int run(){return PRIVATE;}}']

def fixture(root,consumer):
    files={'util/Tools.java':TOOLS,'other/Other.java':OTHER,'demo/Use.java':consumer}
    if 'static demo.Tools.' in consumer:
        files['demo/Tools.java']=files.pop('util/Tools.java').replace('package util;','package demo;')
    for name,source in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')
    return files

class StaticAccessR53Tests(unittest.TestCase):
    def test_mixed_instance_owner_keeps_dependency_block_instead_of_false_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root,CASES[3])
            path=root/'util/Tools.java'
            path.write_text(TOOLS.replace('private static int take(String','public int take(String'),encoding='utf-8')
            report=translate(root,Path(folder)/'out')
            owner=next(row for row in report['results'] if row['file']=='util/Tools.java')
            use=next(row for row in report['results'] if row['file']=='demo/Use.java')
            self.assertEqual(owner['status'],'MANUAL_REVIEW',report)
            self.assertIn('Mixed static/instance',owner['reason'])
            self.assertIn('util/Tools.java',use['missing_generated_dependencies'])

    def test_original_java_access_filter_and_selected_signature_match_jdk(self):
        for index,source in enumerate(CASES):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,source)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report)
                self.assertEqual(previous.actual(Path(folder)/'out/original'),previous.previous.oracle(root,files))
    def test_inaccessible_instance_and_inapplicable_calls_match_javac_rejection(self):
        for index,source in enumerate(BAD):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,source)
                report=translate(root,Path(folder)/'out')
                row=next(row for row in report['results'] if row['file']=='demo/Use.java')
                self.assertEqual(row['status'],'MANUAL_REVIEW',report)
                process=subprocess.run([str(previous.previous.JAVA.with_name('javac.exe')),'-encoding','UTF-8','-d',str(Path(folder)/'classes')]+[str(root/name) for name in files],capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)

if __name__=='__main__':unittest.main()

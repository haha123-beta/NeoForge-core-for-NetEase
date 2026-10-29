import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
import test_static_wildcards_r52 as actual
import test_translation_r51 as oracle

FILES={'demo/Token.java':'package demo;public class Token {}','demo/Child.java':'package demo;public class Child extends Token {}'}
CASES=[
 'package demo;public class Use {public int run(){Object x=new Token();if(x instanceof Token)return 7;return 0;}}',
 'package demo;public class Use {public int run(){Object x=null;if(x instanceof Token)return 1;return 2;}}',
 'package demo;public class Use {public int run(){Object x=new Child();if(x instanceof Token)return 3;return 0;}}',
 'package demo;public class Use {public static int calls=0;public static Object next(){calls=calls+1;return new Token();}public int run(){if(next() instanceof Token)return calls;return 0;}}'
]

class InstanceofTests(unittest.TestCase):
    def test_null_hierarchy_and_single_operand_evaluation_match_jdk(self):
        for code in CASES:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=dict(FILES,**{'demo/Use.java':code})
                for name,value in files.items():
                    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8')
                report=translate(root,Path(folder)/'out');self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                self.assertEqual(actual.actual(Path(folder)/'out/original'),oracle.oracle(root,files))

if __name__=='__main__':unittest.main()

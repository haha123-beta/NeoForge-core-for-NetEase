import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from java_mixin_plan import plan,MixinPlanError
import test_mixin_fields_r60 as base

CASES=[
 {'target':'package demo;import java.util.List;public class Target {private List<?> items;public Target(List<?> initial){items=initial;}public int run(){if(items==null)return 1;return 2;}}',
  'fields':'@Shadow private List<?> items;', 'extra_imports':'import java.util.List;',
  'handlers':base.base.hook('run','HEAD','items=null;',params='CallbackInfoReturnable<Integer> ci',static=False),
  'use':'return new Target(null).run();','expected':1},
 {'target':'package demo;public class Target {private int[] items=new int[2];public int run(){return items[0];}}',
  'fields':'@Shadow private int[] items;',
  'handlers':base.base.hook('run','HEAD','items[0]=7;',params='CallbackInfoReturnable<Integer> ci',static=False),
  'use':'return new Target().run();','expected':7}]

class GenericShadowTests(unittest.TestCase):
    def test_generic_and_array_fields_keep_original_storage(self):
        for case in CASES:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=base.fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                self.assertEqual(base.base.previous.actual(Path(folder)/'out/original'),str(case['expected']))
                self.assertEqual(base.base.oracle(root,files),str(case['expected']))
    def test_erasure_does_not_hide_generic_mismatch(self):
        case=dict(CASES[0],fields='@Shadow private List<Integer> items;')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();base.fixture(root,case)
            with self.assertRaises(MixinPlanError):plan(root)

if __name__=='__main__':unittest.main()

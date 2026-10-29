import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_mixin_weave_r55 as base
from translate_java import translate
from build_source_bundle import collect_sources

CASES=[
 {'target':'package demo; public class Target {public static boolean run(int n){return n>0;}}',
  'handlers':base.hook('run(I)Z','RETURN','ci.setReturnValue(!ci.getReturnValueZ());',True,'int n, CallbackInfoReturnable<Boolean> ci'),
  'use':'if(Target.run(1))return 1; if(Target.run(-1))return 2;return 3;','expected':2},
 {'target':'package demo; public class Target {public static boolean run(int n){Audit.next();return true;}}',
  'handlers':base.hook('run','HEAD','if(n<0)ci.cancel();',True,'int n, CallbackInfoReturnable<Boolean> ci'),
  'use':'if(Target.run(-1))return 1;if(!Target.run(1))return 2;return Audit.count+10;','expected':11},
 {'target':'package demo; public class Target {public boolean run(){return false;}}',
  'handlers':base.hook('run','RETURN','ci.setReturnValue(true);',True,'CallbackInfoReturnable<Boolean> ci',static=False),
  'use':'if(new Target().run())return 7;return 1;','expected':7},
 {'target':'package demo; public class Target {public static boolean run(){return Audit.next()>0;}}',
  'handlers':base.hook('run','RETURN','ci.cancel();',True,'CallbackInfoReturnable<Boolean> ci'),
  'use':'if(!Target.run())return 1;return Audit.count+20;','expected':21},
]

class BooleanCallbackTests(unittest.TestCase):
    def test_boolean_callbacks_match_official_callback_java(self):
        for case in CASES:
            with self.subTest(expected=case['expected']),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=base.fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                actual=base.previous.actual(Path(folder)/'out/original')
                self.assertEqual(actual,str(case['expected']));self.assertEqual(actual,base.oracle(root,files))
                source=collect_sources(Path(folder)/'out/original')['demo.Target']['source']
                self.assertIn('MixinCallbacks ABI2',source)
    def test_wrong_generic_and_primitive_getter_remain_blocked(self):
        for text in ('CallbackInfoReturnable<Integer>','CallbackInfoReturnable<String>'):
            case=dict(CASES[0],handlers=CASES[0]['handlers'].replace('CallbackInfoReturnable<Boolean>',text))
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();base.fixture(root,case)
                report=translate(root,Path(folder)/'out');self.assertGreater(report['manual_review'],0)

if __name__=='__main__':unittest.main()

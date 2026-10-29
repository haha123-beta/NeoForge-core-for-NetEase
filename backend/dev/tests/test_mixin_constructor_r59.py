import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_mixin_weave_r55 as base
from java_mixin_plan import plan,MixinPlanError
from translate_java import translate

CASES=[
 {'target':'package demo; public class Target {private int value=Audit.next();public Target(int n){value=value+n;Audit.mark(value);} public int read(){return value;}}',
  'handlers':base.hook('<init>(I)V','TAIL','Audit.mark(n);',params='int n, CallbackInfo ci',static=False),
  'use':'Target t=new Target(3);return t.read()+Audit.trace*100;','expected':4304},
 {'target':'package demo; public class Target {public Target(){Audit.mark(2);return;} }',
  'handlers':base.hook('<init>()V','TAIL','if(ci.getId().equals("<init>"))Audit.mark(3);',params='CallbackInfo ci',static=False),
  'use':'new Target();return Audit.trace;','expected':23},
 {'target':'package demo; public class Target {public Target(int n){if(n<0)throw new IllegalStateException("fail");Audit.mark(2);} }',
  'handlers':base.hook('<init>(I)V','TAIL','Audit.mark(3);',params='CallbackInfo ci',static=False),
  'use':'try{new Target(-1);}catch(IllegalStateException e){Audit.mark(1);}new Target(1);return Audit.trace;','expected':123},
 {'target':'package demo; public class Target {public Target(int n){Audit.mark(n);}public Target(){Audit.mark(4);} }',
  'handlers':base.hook('<init>(I)V','TAIL','Audit.mark(3);',params='CallbackInfo ci',static=False),
  'use':'new Target(2);new Target();return Audit.trace;','expected':234},
]

class ConstructorCallbackTests(unittest.TestCase):
    def test_tail_after_fields_and_body_matches_java(self):
        for case in CASES:
            with self.subTest(expected=case['expected']),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=base.fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                self.assertEqual(base.previous.actual(Path(folder)/'out/original'),str(case['expected']))
                self.assertEqual(base.oracle(root,files),str(case['expected']))
    def test_constructor_head_cancellation_chaining_early_returns_and_require_block(self):
        variants=[dict(CASES[0],handlers=CASES[0]['handlers'].replace('TAIL','HEAD')),
                  dict(CASES[0],handlers=CASES[0]['handlers'].replace('cancellable=false','cancellable=true')),
                  dict(CASES[0],handlers=CASES[0]['handlers'].replace('cancellable=false','cancellable=false,require=2')),
                  dict(CASES[0],target=CASES[0]['target'].replace('value=value+n;','if(n<0)return;value=value+n;')),
                  dict(CASES[1],target=CASES[1]['target'].replace('Audit.mark(2);','super();Audit.mark(2);'))]
        for case in variants:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();base.fixture(root,case)
                with self.assertRaises(MixinPlanError):plan(root)

if __name__=='__main__':unittest.main()

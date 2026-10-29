import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
import test_mixin_modify_arg_r64 as previous
import test_mixin_weave_r55 as base

CASES=[
 {'target':'package demo;public class Target {public static int run(){return Sink.accept(Audit.next(),Audit.next());}}',
  'handlers':previous.handler()+base.hook('run','RETURN','ci.setReturnValue(ci.getReturnValueI()+5);',True,'CallbackInfoReturnable<Integer> ci',name='after'),
  'use':'return Target.run()*10+Audit.count;','expected':472},
 {'target':'package demo;public class Target {public static int run(){return Sink.accept(Audit.next(),Audit.next());}}',
  'handlers':previous.handler()+base.hook('run','HEAD','ci.setReturnValue(9);',True,'CallbackInfoReturnable<Integer> ci',name='before')+base.hook('run','RETURN','Audit.mark(7);',False,'CallbackInfoReturnable<Integer> ci',name='after'),
  'use':'return Target.run()*100+Audit.count*10+Audit.trace;','expected':900},
]

class ComposedMixinTests(unittest.TestCase):
    def test_return_subject_value_and_head_cancellation_preserve_order(self):
        for case in CASES:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=previous.fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                self.assertEqual(base.previous.actual(Path(folder)/'out/original'),str(case['expected']))
                self.assertEqual(base.oracle(root,files),str(case['expected']))

if __name__=='__main__':unittest.main()

import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from java_mixin_plan import plan,MixinPlanError
import test_mixin_weave_r55 as base

def handler(body='return v+3;',parameters='int v',index=0):
    return '@ModifyArg(method="run",at=@At(value="INVOKE",target="Ldemo/Sink;accept(II)I"),index='+str(index)+') private static int adjust('+parameters+'){'+body+'}'

CASES=[
 {'target':'package demo;public class Target {public static int run(){int n=Sink.accept(Audit.next(),Audit.next());return n*10+Audit.count;}}',
  'handlers':handler(),'use':'return Target.run();','expected':422},
 {'target':'package demo;public class Target {public static int run(){int n=Sink.accept(Audit.next(),Audit.next());return n;}}',
  'handlers':handler('Audit.mark(Audit.count);return v+Audit.count;'),'use':'return Target.run()*100+Audit.trace;','expected':3202},
 {'target':'package demo;public class Target {public static int run(){int a=Sink.accept(1,2);int b=Sink.accept(3,4);return a+b;}}',
  'handlers':handler(parameters='int a,int v',body='return a+v;',index=1),'use':'return Target.run();','expected':50},
 {'target':'package demo;public class Target {public static int run(Sink s){return s.accept(Audit.next(),Audit.next());}}',
  'handlers':handler('Audit.mark(1);return v+3;'),
  'use':'try{Target.run(null);}catch(NullPointerException e){return Audit.count*10+Audit.trace;}return 0;','expected':21,
  'extra':{'demo/Sink.java':'package demo;public class Sink {public int accept(int a,int b){return a*10+b;}}'}},
 {'target':'package demo;public class Target {public static int run(){return Sink.accept(Audit.next(),Throwing.fail());}}',
  'handlers':handler('Audit.mark(1);return v+3;'),
  'use':'try{Target.run();}catch(IllegalStateException e){return Audit.count*10+Audit.trace;}return 0;','expected':10,
  'extra':{'demo/Throwing.java':'package demo;public class Throwing {public static int fail(){throw new IllegalStateException("argument failure");}}'}},
]

def fixture(root,case):
    extra={'demo/Sink.java':'package demo;public class Sink {public static int accept(int a,int b){return a*10+b;}}'}
    extra.update(case.get('extra',{}))
    files=base.fixture(root,dict(case,extra=extra))
    p=root/'demo/Hooks.java';source=p.read_text(encoding='utf-8').replace('import org.spongepowered.asm.mixin.injection.Inject;', 'import org.spongepowered.asm.mixin.injection.Inject;import org.spongepowered.asm.mixin.injection.ModifyArg;')
    p.write_text(source,encoding='utf-8');files['demo/Hooks.java']=source
    return files

class ModifyArgTests(unittest.TestCase):
    def test_argument_order_counts_and_all_argument_capture(self):
        for case in CASES:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                self.assertEqual(base.previous.actual(Path(folder)/'out/original'),str(case['expected']))
                self.assertEqual(base.oracle(root,files),str(case['expected']))
    def test_bad_index_wrong_descriptor_require_and_ambiguity_block(self):
        for original,replacement in [('index=0','index=2'),('accept(II)I','accept(IZ)I'),('index=0','require=3,index=0'),(',index=0','')]:
            case=dict(CASES[0],handlers=CASES[0]['handlers'].replace(original,replacement))
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();fixture(root,case)
                with self.assertRaises(MixinPlanError):plan(root)

if __name__=='__main__':unittest.main()

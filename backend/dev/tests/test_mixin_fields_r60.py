import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_mixin_weave_r55 as base
from java_mixin_plan import plan,MixinPlanError
from java_mixin_weave import weave
from translate_java import translate

FIELD_IMPORTS='import org.spongepowered.asm.mixin.Shadow;import org.spongepowered.asm.mixin.Final;import org.spongepowered.asm.mixin.Mutable;'

CASES=[
 {'target':'package demo; public class Target {private final int value;public Target(int n){value=n;}public int read(){return value;}}',
  'fields':'@Shadow @Final @Mutable private int value;',
  'handlers':base.hook('<init>(I)V','TAIL','this.value=this.value+3;',params='int n, CallbackInfo ci',static=False),
  'use':'Target a=new Target(2);Target b=new Target(7);return a.read()*100+b.read();','expected':510},
 {'target':'package demo; public class Target {private int count=2;public int run(int n){return count+n;}}',
  'fields':'@Shadow private int count;',
  'handlers':base.hook('run','HEAD','count=count+1;',params='CallbackInfoReturnable<Integer> ci',static=False),
  'use':'Target a=new Target();Target b=new Target();return a.run(1)*100+a.run(1)*10+b.run(1);','expected':454},
 {'target':'package demo; public class Target {private static int count=2;public static int run(){return count;}}',
  'fields':'@Shadow private static int count;',
  'handlers':base.hook('run','HEAD','count=count+1;',params='CallbackInfoReturnable<Integer> ci'),
  'use':'return Target.run()*10+Target.run();','expected':34},
 {'target':'package demo; public class Target {private final int value=8;public int run(){return 1;}}',
  'fields':'@Shadow @Final private int value;',
  'handlers':base.hook('run','RETURN','ci.setReturnValue(value+ci.getReturnValueI());',True,'CallbackInfoReturnable<Integer> ci',static=False),
  'use':'return new Target().run();','expected':9},
]

def fixture(root,case,cross=False):
    case=dict(case)
    case['handlers']=case['fields']+case['handlers']
    files=base.fixture(root,case)
    path=root/'demo/Hooks.java'
    original=path.read_text(encoding='utf-8').replace('@Mixin(Target.class)',FIELD_IMPORTS+case.get('extra_imports','')+'@Mixin(Target.class)')
    path.write_text(original,encoding='utf-8');files['demo/Hooks.java']=original
    if cross:
        source=original.replace('package demo;','package hooks;import demo.Target;')
        path.unlink();files.pop('demo/Hooks.java')
        path=root/'hooks/Hooks.java';path.parent.mkdir();path.write_text(source,encoding='utf-8');files['hooks/Hooks.java']=source
        config=dict(base.initial.CONFIG,package='hooks');files['demo.mixins.json']=json.dumps(config)
        (root/'demo.mixins.json').write_text(files['demo.mixins.json'],encoding='utf-8')
    return files

class ShadowFieldsTests(unittest.TestCase):
    def test_shadow_identity_mutable_final_and_cross_package_match_java(self):
        for index,case in enumerate(CASES):
            for cross in (False,True):
                with self.subTest(index=index,cross=cross),tempfile.TemporaryDirectory() as folder:
                    root=Path(folder)/'original';root.mkdir();files=fixture(root,case,cross)
                    report=translate(root,Path(folder)/'out')
                    self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
                    self.assertEqual(base.previous.actual(Path(folder)/'out/original'),str(case['expected']))
                    self.assertEqual(base.oracle(root,files),str(case['expected']))
                    bindings=report['mixin_plan']['field_bindings'];self.assertEqual(len(bindings),1)
                    self.assertEqual({name:(root/name).read_text(encoding='utf-8') for name in files},files)
    def test_missing_type_static_final_mutable_alias_initializer_and_unbound_access_rejected(self):
        variants=[dict(CASES[0],fields='@Shadow @Final @Mutable private boolean value;'),
                  dict(CASES[0],fields='@Shadow @Final @Mutable private static int value;'),
                  dict(CASES[0],fields='@Shadow @Final @Mutable private int missing;'),
                  dict(CASES[0],fields='@Shadow @Final private int value;'),
                  dict(CASES[0],fields='@Shadow @Mutable private int value;'),
                  dict(CASES[0],fields='@Shadow(aliases="other") @Final @Mutable private int value;'),
                  dict(CASES[0],fields='@Shadow @Final @Mutable private int value=0;'),
                  dict(CASES[0],target=CASES[0]['target'].replace('private final int value;', 'private final int value=8;').replace('value=n;', '')),
                  dict(CASES[0],handlers=CASES[0]['handlers'].replace('this.value=this.value+3;', 'int value=1;this.value=value;')),
                  dict(CASES[0],target=CASES[0]['target'].replace('package demo;', 'package demo;import java.util.*;')),
                  dict(CASES[0],target=CASES[0]['target'].replace('package demo;', 'package demo;import static java.lang.Integer.*;')),
                  dict(CASES[0],handlers=CASES[0]['handlers'].replace('this.value=this.value+3;', 'this.read();')),
                  dict(CASES[0],target=CASES[0]['target'].replace('private final int value;', 'private Audit marker;private final int value;'),extra_imports='import other.Audit;',extra={'other/Audit.java':'package other;public class Audit {}'}),
                  dict(CASES[0],fields='')]
        for case in variants:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();fixture(root,case)
                with self.assertRaises(MixinPlanError):plan(root)

if __name__=='__main__':unittest.main()

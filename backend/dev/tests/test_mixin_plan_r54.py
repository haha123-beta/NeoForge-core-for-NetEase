import json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_mixin_plan import plan,MixinPlanError
TARGET='package demo; public class Target {\n public static int run(int n){if(n<0)return 2;return n+1;}\n public void touch(int n){}\n}'
HOOKS='package demo;\nimport org.spongepowered.asm.mixin.Mixin;\nimport org.spongepowered.asm.mixin.injection.Inject;\nimport org.spongepowered.asm.mixin.injection.At;\nimport org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;\n@Mixin(value=Target.class,priority=1200) public class Hooks {\n @Inject(method="run(I)I",at=@At("RETURN"),cancellable=true,require=2)\n private static void change(int n, CallbackInfoReturnable<Integer> ci){ci.setReturnValue(ci.getReturnValueI()+3);}\n}'
CONFIG={'required':True,'package':'demo','mixins':['Hooks'],'injectors':{'defaultRequire':1}}
def fixture(root,target=TARGET,hooks=HOOKS,config=None):
    files={'demo/Target.java':target,'demo/Hooks.java':hooks,'demo.mixins.json':json.dumps(CONFIG if config is None else config)}
    for name,value in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8')
    return files
class MixinPlanR54Tests(unittest.TestCase):
    def test_exact_descriptor_return_count_and_original_input_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);files=fixture(root);result=plan(root)
            self.assertEqual(result['scope'],'same_content_source_callbacks')
            row=result['injections'][0]
            self.assertEqual((row['target'],row['descriptor'],row['matches'],row['priority']),('demo.Target','run(I)I',2,1200))
            self.assertTrue(row['capture_arguments']);self.assertTrue(row['cancellable'])
            self.assertEqual({name:(root/name).read_text(encoding='utf-8') for name in files},files)
    def test_unsupported_or_ambiguous_contracts_fail_before_weaving(self):
        variants=[
            {'hooks':HOOKS.replace('@At("RETURN")','@At(value="RETURN",ordinal=0)')},
            {'hooks':HOOKS.replace('"RETURN"','"INVOKE"')},
            {'hooks':HOOKS.replace('run(I)I','missing(I)I')},
            {'hooks':HOOKS.replace('require=2','require=3')},
            {'hooks':HOOKS.replace('private static void','private void')},
            {'hooks':HOOKS.replace('CallbackInfoReturnable<Integer>','CallbackInfoReturnable<String>')},
            {'hooks':HOOKS.replace('public class Hooks {','public class Hooks { private int state;')},
            {'target':TARGET.replace('if(n<0)return 2;return n+1;','try{return n+1;}finally{}')},
            {'config':dict(CONFIG,plugin='demo.Plugin')},
            {'config':dict(CONFIG,client=['ClientHooks'])},
            {'config':dict(CONFIG,mixins=['Hooks','Hooks'])},
            {'hooks':HOOKS.replace('run(I)I','run'),'target':TARGET.replace('public void touch','public static int run(Object n){return 0;}public void touch')},
        ]
        for index,args in enumerate(variants):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);fixture(root,**args)
                with self.assertRaises(MixinPlanError):plan(root)
if __name__=='__main__':unittest.main()

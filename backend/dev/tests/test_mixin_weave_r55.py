import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from java_mixin_plan import plan,MANIFEST
from java_mixin_weave import weave
from build_source_bundle import collect_sources,content_bundle
import test_static_wildcards_r52 as previous
import test_mixin_plan_r54 as initial
JAVA=previous.previous.JAVA
MIXIN=Path(__file__).resolve().parents[1]/'references/mixin-r55/mixin-0.8.7.jar'
IMPORTS='package demo; import org.spongepowered.asm.mixin.Mixin;\nimport org.spongepowered.asm.mixin.injection.Inject; import org.spongepowered.asm.mixin.injection.At;\nimport org.spongepowered.asm.mixin.injection.callback.CallbackInfo;\nimport org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;\n@Mixin(Target.class) public class Hooks {'
AUDIT='package demo; public class Audit {public static int count=0;public static int trace=0;public static int next(){count=count+1;return count;}public static void mark(int n){trace=trace*10+n;}}'
def hook(method,at,body,cancel=False,params='int n, CallbackInfoReturnable<Integer> ci',name='change',static=True):
    return '@Inject(method="'+method+'",at=@At("'+at+'"),cancellable='+str(cancel).lower()+') private '+('static ' if static else '')+'void '+name+'('+params+'){'+body+'}'
CASES=[
 {'target':initial.TARGET,'handlers':hook('run(I)I','RETURN','ci.setReturnValue(ci.getReturnValueI()+3);',True),'use':'return Target.run(3)+Target.run(-1);','expected':12},
 {'target':'package demo; public class Target {public static int run(int n){Audit.next();return n+1;}}','handlers':hook('run','HEAD','if(n<0)ci.setReturnValue(40);',True),'use':'int a=Target.run(-1);int b=Target.run(2);return a+b+Audit.count*100;','expected':143},
 {'target':'package demo; public class Target {public static void run(int n){Audit.mark(2);}}','handlers':hook('run','HEAD','Audit.mark(1);if(n<0)ci.cancel();',True,'int n, CallbackInfo ci'),'use':'Target.run(-1);Target.run(1);return Audit.trace;','expected':112},
 {'target':'package demo; public class Target {public static void run(int n){if(n<0)return;Audit.mark(2);}}','handlers':hook('run','RETURN','Audit.mark(3);',False,'CallbackInfo ci'),'use':'Target.run(-1);Target.run(1);return Audit.trace;','expected':323},
 {'target':'package demo; public class Target {public static int run(){return Audit.next();}}','handlers':hook('run','RETURN','ci.setReturnValue(ci.getReturnValueI()+2);',True,'CallbackInfoReturnable<Integer> ci'),'use':'int a=Target.run();return a+Audit.count*100;','expected':103},
 {'target':'package demo; public class Target {public static int run(){throw new IllegalStateException("fail");}}','handlers':hook('run','RETURN','Audit.mark(3);',False,'CallbackInfoReturnable<Integer> ci').replace('cancellable=false','cancellable=false,require=0'),'use':'try{Target.run();}catch(IllegalStateException e){Audit.mark(1);}return Audit.trace;','expected':1,'unsupported':True},
 {'target':'package demo; public class Target {public static int run(int n){return 1;}public static int run(Object n){return 2;}}','handlers':hook('run(I)I','RETURN','ci.setReturnValue(5);',True),'use':'return Target.run(3)+Target.run((Object)null);','expected':7},
 {'target':initial.TARGET,'handlers':hook('run(I)I','RETURN','ci.setReturnValue(ci.getReturnValueI()+3);',True,name='hook$after'),'use':'return Target.run(3);','expected':7},
 {'target':initial.TARGET,'handlers':hook('run(I)I','HEAD','if(ci.getId().equals("run"))ci.cancel();',True,'CallbackInfoReturnable<Integer> ci'),'use':'return Target.run(3);','expected':0},
 {'target':'package demo; public class Target {public int run(int n){return n+1;}}','handlers':hook('run','RETURN','ci.setReturnValue(ci.getReturnValueI()+4);',True,static=False),'use':'return new Target().run(2);','expected':7},
 {'target':initial.TARGET,'handlers':hook('run(I)I','RETURN','if(n<0)ci.cancel();',True),'use':'return Target.run(-1);','expected':2},
 {'target':'package demo; public class Target {public static int run(int n){if(n<0)throw new IllegalStateException("fail");return n+1;}}','handlers':hook('run','RETURN','Audit.mark(3);',False),'use':'try{Target.run(-1);}catch(IllegalStateException e){Audit.mark(1);}Target.run(2);return Audit.trace;','expected':13},
 {'target':'package demo; public class Target {public static int run(int n){Audit.mark(3);return n;}}',
  'handlers':hook('run','HEAD','Audit.mark(2);',False,name='low')+hook('run','RETURN','Audit.mark(4);',False,name='tail'),
  'use':'Target.run(1);return Audit.trace;','expected':1234,
  'extra':{'demo/Priority.java':IMPORTS.replace('@Mixin(Target.class) public class Hooks','@Mixin(value=Target.class,priority=1500) public class Priority')+hook('run','HEAD','Audit.mark(1);',False,name='high')+'}'},
  'config':dict(initial.CONFIG,mixins=['Hooks','Priority'])},
]
# A method with no return instruction is deliberately unsupported even require=0.
ACTIVE=[case for case in CASES if not case.get('unsupported')]
def fixture(root,case):
    files=initial.fixture(root,target=case['target'],hooks=IMPORTS+case['handlers']+'}')
    files.update(case.get('extra',{}))
    if 'config' in case:files['demo.mixins.json']=json.dumps(case['config'])
    files.update({'demo/Audit.java':AUDIT,'demo/Use.java':'package demo; public class Use {public int run(){'+case['use']+'}}'})
    for name,value in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8')
    return files

def oracle(root,files):
    contract=plan(root);woven=weave(root,contract);folder=root/'jdk';folder.mkdir()
    for name,value in files.items():
        if name.endswith('.java'):
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(woven.get(name,(root/name).read_bytes()))
    probe=folder/'Probe.java';probe.write_text('public class Probe {public static void main(String[] args){System.out.print(new demo.Use().run());}}',encoding='utf-8')
    build=folder/'classes';build.mkdir()
    process=subprocess.run([str(JAVA.with_name('javac.exe')),'-proc:none','-encoding','UTF-8','-cp',str(MIXIN),'-d',str(build)]+[str(p) for p in folder.rglob('*.java')],capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    process=subprocess.run([str(JAVA),'-cp',str(build)+os.pathsep+str(MIXIN),'Probe'],capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    return process.stdout

class MixinWeaveR55Tests(unittest.TestCase):
    def test_original_handlers_source_weave_jdk_and_generated_python_agree(self):
        for index,case in enumerate(ACTIVE):
            with self.subTest(index=index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'original';root.mkdir();files=fixture(root,case)
                report=translate(root,Path(folder)/'out')
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(sum(name.endswith('.java') for name in files),0,0),report)
                result=previous.actual(Path(folder)/'out/original')
                self.assertEqual(result,str(case['expected']))
                self.assertEqual(result,oracle(root,files))
                self.assertEqual({name:(root/name).read_text(encoding='utf-8') for name in files},files)
    def test_validated_config_only_and_stale_plan_or_code_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root,ACTIVE[0])
            report=translate(root,Path(folder)/'out');self.assertEqual(report['manual_review'],0,report)
            out=Path(folder)/'out/original'
            meta=out/'META-INF/neoforge.mods.toml';meta.parent.mkdir();meta.write_text('[[mods]]\nmodId="reviewed"\nversion="1"\n',encoding='utf-8')
            bundle=content_bundle(out,{'reviewed':'demo.Use:Use'})
            self.assertFalse(bundle['mods'][0]['compatibility_issues'])
            self.assertEqual(bundle['mods'][0]['source_mixin_adaptation']['injections'],1)
            code=out/'demo/Target.py';saved=code.read_bytes();code.write_bytes(saved+b'\n# stale\n')
            with self.assertRaises(ValueError):content_bundle(out,{'reviewed':'demo.Use:Use'})
            code.write_bytes(saved)
            single=meta.read_bytes()
            meta.write_bytes(single+b'[[mods]]\nmodId="second"\nversion="1"\n')
            with self.assertRaises(ValueError):content_bundle(out,{'reviewed':'demo.Use:Use','second':'demo.Use:Use'})
            meta.write_bytes(single)
            config=out/'demo.mixins.json';config.write_text(json.dumps(dict(initial.CONFIG,plugin='demo.Plugin')),encoding='utf-8')
            with self.assertRaises(ValueError):content_bundle(out,{'reviewed':'demo.Use:Use'})
    def test_zero_return_site_and_unconfigured_annotation_stay_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root,next(case for case in CASES if case.get('unsupported')))
            report=translate(root,Path(folder)/'out');self.assertGreater(report['manual_review'],0)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root,ACTIVE[0]);(root/'demo.mixins.json').unlink()
            report=translate(root,Path(folder)/'out');self.assertGreater(report['manual_review'],0)
if __name__=='__main__':unittest.main()

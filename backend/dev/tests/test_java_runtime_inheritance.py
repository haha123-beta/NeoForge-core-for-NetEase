import os,sys,unittest,tempfile,subprocess,hashlib,copy
import json,shutil
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering
from translate_java import translate
from build_source_bundle import collect_sources,core_bundle,content_bundle
from run_translation_job import run_job
from workspace_paths import DEV_ROOT
pkg=helper.pkg;goals=pkg.load('minecraft.goals');runtime_api=pkg.load('minecraft.runtime_classes').RuntimeClasses
PREFIX='import net.minecraft.world.entity.ai.goal.Goal;'
BASE='class A extends Goal {public boolean canUse(){return true;}}'

class RuntimeInheritance(unittest.TestCase):
    def python(self,source):return helper.ArrayTests().python(PREFIX+source)
    def original_goal_java(self,source,body):
        root=DEV_ROOT/'references/minecraft-1.21.1';launcher=root/'goal-jvm-probe'
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);path=folder/'NeoCoreGoalProbe.java'
            path.write_text(source+' public class NeoCoreGoalProbe {public static void main(String[] args){'+body+'}}',encoding='utf-8')
            result=subprocess.run([str(helper.JAVAC),'-encoding','UTF-8','-cp',str(root/'client.jar'),'-d',directory,str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(helper.JAVA),'-cp',str(launcher),'neocoreprobe.GoalProbeLauncher',str(root/'client.jar'),directory],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
    def test_original_constructor_field_order_and_super_virtual_call(self):
        source='class A extends Goal {int seen=read();int value=7;A(){super();}int read(){return value;}public boolean canUse(){return value==7;}boolean run(){return super.canContinueToUse();}}'
        namespace,result=self.python(source);obj=namespace['A']()
        actual=str(obj.seen)+':'+str(obj.value)+':'+str(obj.run()).lower()
        # Only external API spellings change for the original obfuscated jar.
        mapped=source.replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('super.canContinueToUse()','super.c()')
        oracle=self.original_goal_java(mapped,'A a=new A();System.out.print(a.seen+":"+a.value+":"+a.run());')
        self.assertEqual(actual,oracle);self.assertEqual(actual,'0:7:true')
        self.assertIsInstance(obj,goals.Goal);self.assertEqual(obj.getFlags(),set())
        self.assertIn('neocore.runtime.RuntimeClasses@1',result['required_runtime_helpers'])
        self.assertNotIn('_nc_JavaClassABI',runtime_api.bind('net.minecraft.world.entity.ai.goal.Goal',runtime_api.contracts()['net.minecraft.world.entity.ai.goal.Goal']).__dict__)
    def test_this_constructor_delegation_initializes_runtime_parent_once(self):
        namespace,_=self.python('class A extends Goal {int count=init();A(){this(3);}A(int n){super();count+=n;}int init(){return 1;}public boolean canUse(){return count==4;}}')
        obj=namespace['A']();self.assertEqual(obj.count,4);self.assertTrue(obj.canUse());obj.getFlags().add(goals.Goal.Flag.MOVE);self.assertEqual(obj.getFlags(),{goals.Goal.Flag.MOVE})
    def test_three_levels_virtual_override_and_super_original_goal_jvm(self):
        source='class A extends Goal {int count;public boolean canUse(){return false;}public void start(){super.start();count++;}}class B extends A {int value=4;public boolean canUse(){return value==4;}boolean run(){super.start();return super.canContinueToUse();}}'
        namespace,_=self.python(source);obj=namespace['B']();actual=str(obj.run()).lower()+':'+str(obj.count)
        mapped=source.replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('void start()','void d()').replace('super.start()','super.d()').replace('super.canContinueToUse()','super.c()')
        oracle=self.original_goal_java(mapped,'B b=new B();System.out.print(b.run()+":"+b.count);')
        self.assertEqual(actual,oracle);self.assertEqual(actual,'true:1')
    def test_native_goal_and_generated_goal_both_accept_original_typed_call(self):
        namespace,_=self.python(BASE+'class Logic {static boolean run(Goal target){return target.canContinueToUse();}}')
        class Native(goals.Goal):
            def canUse(self):return True
        self.assertTrue(namespace['Logic'].run(Native()));self.assertTrue(namespace['Logic'].run(namespace['A']()))
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):namespace['Logic'].run(None)
    def test_bound_native_goal_reference_captures_once_and_checks_null_on_creation(self):
        namespace,_=self.python('import java.lang.Runnable;class Logic {static Runnable make(Goal target){return target::start;}}')
        class Native(goals.Goal):
            def __init__(self):super(Native,self).__init__();self.count=0
            def start(self):self.count+=1
        obj=Native();callback=namespace['Logic'].make(obj);callback.run();self.assertEqual(obj.count,1)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):namespace['Logic'].make(None)
    def test_unbound_runtime_method_reference(self):
        namespace,_=self.python('import java.util.function.Predicate;class Logic {static boolean run(Goal target){Predicate<Goal> predicate=Goal::canUse;return predicate.test(target);}}')
        class Native(goals.Goal):
            def canUse(self):return True
        self.assertTrue(namespace['Logic'].run(Native()))
    def test_super_method_reference_stays_nonvirtual_at_selected_declaration(self):
        namespace,_=self.python('import java.lang.Runnable;class A extends Goal {int count;public boolean canUse(){return true;}public void start(){count++;}void run(){Runnable task=super::start;task.run();}}')
        obj=namespace['A']();obj.run();self.assertEqual(obj.count,0)
    def test_cross_package_generated_parent_preserves_paths_input_and_runtime_abi(self):
        files={'base/A.java':'package base;import net.minecraft.world.entity.ai.goal.Goal;public class A extends Goal {public int value=3;public A(){super();}public boolean canUse(){return value==3;}public int read(){return value;}}',
            'demo/B.java':'package demo;import base.A;public class B extends A {public int extra=4;public B(){super();}public boolean canUse(){return extra==4;}public boolean run(){return super.canContinueToUse();}public int total(){return super.read()+extra;}}'}
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original';output=Path(directory)/'out'
            for name,source in files.items():path=original/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')
            before={name:hashlib.sha256((original/name).read_bytes()).hexdigest() for name in files}
            report=translate(original,output);self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(2,0,0),report)
            runtime=pkg.load('core.source_modules').SourceModuleLoader(collect_sources(output/'original'));scope=helper.api.JavaApiImports(runtime).install(helper.api.collect_java_api())
            try:
                obj=runtime.load('demo.B').B();self.assertTrue(obj.run());self.assertEqual(obj.total(),7);self.assertIsInstance(obj,goals.Goal)
            finally:scope.close();runtime.close()
            self.assertEqual(before,{name:hashlib.sha256((original/name).read_bytes()).hexdigest() for name in files})
            self.assertEqual(report['ready_mods'],0)
    def test_goal_selector_runs_generated_original_methods(self):
        namespace,_=self.python('class A extends Goal {int count;public boolean canUse(){return true;}public void start(){count+=1;}public void tick(){count+=2;}public void stop(){count+=4;}}')
        obj=namespace['A']();selector=goals.GoalSelector();selector.addGoal(1,obj);selector.tick();selector.stopAll();self.assertEqual(obj.count,7)
    def test_missing_abstract_implementation_is_diagnosed(self):
        with self.assertRaisesRegex(NeedsLowering,'abstract method'):self.python('class A extends Goal {}')
    def test_bad_constructor_and_unknown_runtime_base_are_diagnosed(self):
        with self.assertRaises(NeedsLowering):self.python('class A extends Goal {A(){super(1);}public boolean canUse(){return true;}}')
        with self.assertRaises(NeedsLowering):self.python('import net.minecraft.world.entity.Entity;class A extends Entity {}')
    def test_wrong_override_type_static_access_and_private_storage_are_diagnosed(self):
        for body in ('public int canUse(){return 1;}','public static boolean canUse(){return true;}','protected boolean canUse(){return true;}','int _flags;public boolean canUse(){return true;}'):
            with self.subTest(body=body),self.assertRaises(NeedsLowering):self.python('class A extends Goal {'+body+'}')
    def test_abstract_super_call_and_reference_are_diagnosed(self):
        for call in ('boolean run(){return super.canUse();}','java.util.function.BooleanSupplier run(){return super::canUse;}'):
            with self.subTest(call=call),self.assertRaises(NeedsLowering):self.python('class A extends Goal {public boolean canUse(){return true;}'+call+'}')
    def test_changed_runtime_contract_or_signature_is_refused(self):
        name='net.minecraft.world.entity.ai.goal.Goal';contract=runtime_api.contracts()[name]
        bad=copy.deepcopy(contract);bad['methods'][0]['return_type']='int'
        with self.assertRaises(RuntimeError):runtime_api.bind(name,bad)
        bad=copy.deepcopy(contract);bad['methods']=[]
        with self.assertRaises(RuntimeError):runtime_api.bind(name,bad)
        parent=runtime_api.bind(name,contract)
        with self.assertRaises(TypeError):parent(_nc_java_constructor=('int',))
        with self.assertRaises(TypeError):parent().start(_nc_java_signature=('int',))
    def test_abstract_runtime_construction_and_constructor_reference_are_diagnosed(self):
        for source in ('class Logic {Goal run(){return new Goal();}}','import java.util.function.Supplier;class Logic {Supplier<Goal> run(){return Goal::new;}}'):
            with self.subTest(source=source),self.assertRaises(NeedsLowering):self.python(source)
    def test_source_overload_keeps_runtime_virtual_zero_argument_dispatch(self):
        namespace,_=self.python('class A extends Goal {public boolean canUse(){return true;}public boolean canUse(int n){return false;}boolean run(){return super.canContinueToUse();}}')
        self.assertTrue(namespace['A']().run())
    def test_real_java_example_translates_packages_loads_events_and_unloads(self):
        fixture=DEV_ROOT/'examples/runtime_goal'
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);original=base/'input';shutil.copytree(fixture,original)
            before={path.relative_to(original).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in original.rglob('*') if path.is_file()}
            config=base/'job.json';config.write_text(json.dumps({'input':'input','output_root':'output','distribution':{'pack_id':'runtime_goal_content'}}),encoding='utf-8')
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            content=content_bundle(Path(report['output'])/'converted/input',report['discovered_entrypoints'])
            session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[content])
            try:
                context=session.loader.contexts['runtime_goal_example'];self.assertEqual(context.instance.goal.ticks,0)
                self.assertTrue(session.loader.activate()['runtime_goal_example']['ready'])
                event_type=session.runtime.load('neoforge.event.tick').ServerTickEvent.Post
                for _ in range(3):session.loader.post_game_event(event_type())
                self.assertEqual(context.instance.goal.ticks,2)
                self.assertEqual(context.game_bus.listenerCount(),1)
                session.close();self.assertEqual(context.game_bus.listenerCount(),0)
            finally:session.close()
            self.assertEqual(before,{path.relative_to(original).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in original.rglob('*') if path.is_file()})
            self.assertFalse(report['engine_verified']);self.assertEqual(report['ready_mods'],0)

if __name__=='__main__':unittest.main()

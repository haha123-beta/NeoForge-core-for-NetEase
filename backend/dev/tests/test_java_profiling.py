import os,sys,unittest,tempfile,json,hashlib
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
import test_profiling as native
from java_codegen import NeedsLowering
pkg=helper.pkg;profiling=pkg.load('minecraft.profiling')
PREFIX='import net.minecraft.util.profiling.ProfilerFiller;import net.minecraft.util.profiling.InactiveProfiler;import net.minecraft.util.profiling.ProfileResults;import net.minecraft.util.profiling.EmptyProfileResults;'

class JavaProfiling(unittest.TestCase):
    def python(self,source):return helper.ArrayTests().python(PREFIX+source)
    def test_original_selector_constructor_supplier_and_logic_match_original_jvm(self):
        source='import net.minecraft.world.entity.ai.goal.Goal;import net.minecraft.world.entity.ai.goal.GoalSelector;class A extends Goal {int starts;int ticks;public boolean canUse(){return ticks<2;}public void start(){starts++;}public void tick(){ticks++;}}class Logic {static int run(){GoalSelector selector=new GoalSelector(() -> InactiveProfiler.INSTANCE);A goal=new A();selector.addGoal(1,goal);selector.tick();selector.tick();selector.tick();return goal.starts*10+goal.ticks;}}'
        ns,result=self.python(source);self.assertEqual(ns['Logic'].run(),12)
        mapped=source.replace('import net.minecraft.world.entity.ai.goal.Goal;','').replace('import net.minecraft.world.entity.ai.goal.GoalSelector;','').replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('void start()','void d()').replace('void tick()','void a()').replace('GoalSelector selector=new GoalSelector','can selector=new can').replace('InactiveProfiler.INSTANCE','bnc.a').replace('selector.addGoal','selector.a').replace('selector.tick()','selector.a()')
        self.assertEqual(native.original('System.out.print(Logic.run());',mapped),'12')
        self.assertIn('neocore.runtime.Profilers@1',result['required_runtime_helpers'])
    def test_inactive_supplier_callback_is_not_evaluated(self):
        ns,_=self.python('class Logic {int count;String read(){count++;return "x";}int run(){ProfilerFiller profiler=InactiveProfiler.INSTANCE;profiler.push(() -> read());profiler.popPush(() -> read());profiler.incrementCounter(() -> read());return count;}}')
        self.assertEqual(ns['Logic']().run(),0)
    def test_counter_default_and_two_argument_api_calls(self):
        ns,_=self.python('class Logic {static void run(ProfilerFiller profiler){profiler.incrementCounter("x");profiler.incrementCounter("x",3);}}')
        trace=[];ns['Logic'].run(native.Recorder('r',trace));self.assertEqual(trace,['rcount1','rcount3'])
    def test_original_empty_result_call_chain(self):
        ns,_=self.python('class Logic {int run(){ProfileResults results=InactiveProfiler.INSTANCE.getResults();return results.getTickDuration()+results.getTimes("root").size();}boolean same(){return InactiveProfiler.INSTANCE.getResults()==EmptyProfileResults.EMPTY;}}')
        self.assertEqual(ns['Logic']().run(),0);self.assertTrue(ns['Logic']().same())
    def test_tee_identity_on_empty_profiler(self):
        ns,result=self.python('class Logic {static boolean run(ProfilerFiller profiler){return ProfilerFiller.tee(InactiveProfiler.INSTANCE,profiler)==profiler;}}')
        self.assertTrue(ns['Logic'].run(native.Recorder('r',[])))
        self.assertIn('neocore.runtime.Profilers@1',result['required_runtime_helpers'])
    def test_null_check_occurs_after_argument_evaluation(self):
        ns,_=self.python('class Logic {int count;String label(){count++;return "x";}int run(ProfilerFiller profiler){try{profiler.push(label());}catch(NullPointerException e){return count;}return -1;}}')
        self.assertEqual(ns['Logic']().run(None),1)
    def test_static_final_field_and_null_expression_qualifier(self):
        ns,_=self.python('class Logic {int count;InactiveProfiler read(){count++;return null;}int run(){InactiveProfiler result=read().INSTANCE;return count;}}')
        self.assertEqual(ns['Logic']().run(),1)
        for source in ('class Logic {void run(){InactiveProfiler.INSTANCE=null;}}','class Logic {void run(){ProfilerFiller.ROOT="bad";}}'):
            with self.subTest(source=source),self.assertRaisesRegex(NeedsLowering,'Final profiler field'):self.python(source)
    def test_private_and_interface_constructors_are_rejected(self):
        for cls in ('InactiveProfiler','ProfilerFiller','EmptyProfileResults','ProfileResults'):
            with self.subTest(cls=cls),self.assertRaisesRegex(NeedsLowering,'constructor cannot'):
                self.python('class Logic {Object run(){return new '+cls+'();}}')
    def test_null_overload_ambiguity_is_not_guessed(self):
        with self.assertRaisesRegex(NeedsLowering,'Ambiguous profiler'):self.python('class Logic {void run(ProfilerFiller p){p.push(null);}}')
    def test_string_overload_accepts_cast_null_without_dereference(self):
        ns,_=self.python('class Logic {void run(){InactiveProfiler.INSTANCE.push((String)null);}}');ns['Logic']().run()
    def test_metric_enum_description_and_chart_api(self):
        ns,_=self.python('import net.minecraft.util.profiling.metrics.MetricCategory;class Logic {String run(){InactiveProfiler.INSTANCE.markForCharting(MetricCategory.CPU);return MetricCategory.CPU.getDescription();}}')
        self.assertEqual(ns['Logic']().run(),'cpu')
    def test_reference_cast_preserves_identity_and_throws_java_class_cast(self):
        ns,_=self.python('class Logic {static boolean run(Object value){return ((ProfilerFiller)value)!=null;}static ProfilerFiller cast(Object value){return (ProfilerFiller)value;}}')
        self.assertTrue(ns['Logic'].run(profiling.InactiveProfiler.INSTANCE))
        self.assertIs(ns['Logic'].cast(profiling.InactiveProfiler.INSTANCE),profiling.InactiveProfiler.INSTANCE)
        self.assertIsNone(ns['Logic'].cast(None))
        with self.assertRaises(pkg.load('java_stdlib.lang').ClassCastException):ns['Logic'].cast(object())
        self.assertEqual(native.original('Object p=bnc.a;System.out.print(((bnf)p)!=null);try{bnf q=(bnf)new Object();}catch(ClassCastException e){System.out.print(":cast");}'),'true:cast')
    def test_unknown_and_numeric_casts_are_not_erased(self):
        for source in ('class Logic {Object run(){return (NotMapped)null;}}','class Logic {double run(boolean n){return (double)n;}}'):
            with self.subTest(source=source),self.assertRaises(NeedsLowering):self.python(source)
    def test_reviewed_integer_narrowing_matches_original_jdk(self):
        ns,_=self.python('class Logic {int run(long n){return (int)n;}}')
        expected=native.original('long n=4294967297L;System.out.print((int)n);')
        self.assertEqual(str(ns['Logic']().run(4294967297)),expected)
        self.assertEqual(ns['Logic']().run(2147483648),-2147483648)
    def test_selector_source_logic_and_declared_platform_dependency_remain_separate(self):
        from workspace_paths import DEV_ROOT
        from run_translation_job import run_job
        from build_source_bundle import core_bundle,content_bundle,collect_sources
        original=DEV_ROOT/'examples/runtime_selector'
        before={str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'job.json';config.write_text(json.dumps({'input':str(original),'output_root':str(Path(directory)/'output'),'distribution':{'pack_id':'runtime_selector_content'}}),encoding='utf-8')
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            bundle=content_bundle(Path(report['output'])/'converted/runtime_selector',report['discovered_entrypoints'])
            session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[bundle])
            try:
                blocked=session.loader.activate()['runtime_selector_example']
                self.assertEqual(blocked['state'],'blocked')
                self.assertIn('neoforge',blocked['message'])
            finally:session.close()
            # Execute the original non-Mod Java logic without changing its descriptor
            # or publishing a fictitious NeoForge platform version.
            runtime=pkg.load('core.source_modules').SourceModuleLoader(collect_sources(Path(report['output'])/'converted/runtime_selector'))
            api=pkg.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
            try:self.assertEqual(runtime.load('generic.selector.Logic').Logic.run(),12)
            finally:scope.close();runtime.close()
        self.assertEqual(before,{str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()

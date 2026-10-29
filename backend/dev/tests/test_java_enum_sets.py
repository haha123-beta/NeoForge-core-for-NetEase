import os,sys,unittest,tempfile,json,hashlib
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
import test_java_runtime_inheritance as inheritance_helper
from java_codegen import NeedsLowering
pkg=helper.pkg;Goal=pkg.load('minecraft.goals').Goal
PREFIX='import net.minecraft.world.entity.ai.goal.Goal;import java.util.EnumSet;'
BASE='class A extends Goal {A(){setFlags(EnumSet.of(Goal.Flag.LOOK,Goal.Flag.MOVE));}public boolean canUse(){return true;}'
class JavaEnumSets(unittest.TestCase):
    def python(self,source):return helper.ArrayTests().python(PREFIX+source)
    def original(self,source,body):
        source='import java.util.EnumSet;'+source
        for constant,field in [('MOVE','a'),('LOOK','b'),('JUMP','c'),('TARGET','d')]:source=source.replace('Goal.Flag.'+constant,'cam.a.'+field)
        source=source.replace('Goal.Flag','cam.a').replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('setFlags(','a(').replace('getFlags()','j()')
        return inheritance_helper.RuntimeInheritance().original_goal_java(source,body)
    def test_original_set_flags_and_java_order_match_signed_goal_jvm(self):
        source=BASE+'String run(){return getFlags().toString();}}';ns,_=self.python(source)
        self.assertEqual(str(ns['A']().run()),self.original(source,'System.out.print(new A().run());'))
    def test_class_literal_generic_local_and_bulk_factories(self):
        source='class A extends Goal {A(){EnumSet<Goal.Flag> flags=EnumSet.noneOf(Goal.Flag.class);flags.add(Goal.Flag.JUMP);setFlags(flags);}public boolean canUse(){return true;}String run(){EnumSet<Goal.Flag> copy=EnumSet.copyOf(getFlags());copy.addAll(EnumSet.range(Goal.Flag.MOVE,Goal.Flag.LOOK));return copy.toString();}}'
        ns,_=self.python(source);self.assertEqual(str(ns['A']().run()),self.original(source,'System.out.print(new A().run());'))
    def test_live_flags_identity_and_self_alias_clear(self):
        ns,_=self.python(BASE+'boolean run(){EnumSet<Goal.Flag> flags=getFlags();flags.add(Goal.Flag.TARGET);setFlags(flags);return flags.isEmpty();}}')
        a=ns['A']();flags=a.getFlags();self.assertTrue(a.run());self.assertIs(a.getFlags(),flags)
    def test_enum_values_array_iteration_and_name_chain(self):
        source='class A extends Goal {public boolean canUse(){return true;}int run(){int sum=0;for(Goal.Flag f:Goal.Flag.values()){sum+=f.ordinal();}return sum;}boolean named(){return Goal.Flag.valueOf("MOVE").name().equals("MOVE");}}'
        ns,_=self.python(source);a=ns['A']();self.assertEqual(a.run(),6);self.assertTrue(a.named())
        self.assertEqual(str(a.run())+':'+str(a.named()).lower(),self.original(source,'A a=new A();System.out.print(a.run()+":"+a.named());'))
    def test_getter_to_typed_iterator_to_name_keeps_original_chain(self):
        ns,_=self.python(BASE+'boolean run(){return getFlags().iterator().next().name().equals("MOVE");}}')
        self.assertTrue(ns['A']().run())
    def test_enum_set_factories_and_clone_do_not_mutate_original(self):
        ns,_=self.python(BASE+'int run(){EnumSet<Goal.Flag> copy=getFlags().clone();copy.remove(Goal.Flag.MOVE);return getFlags().size()*10+copy.size();}}')
        self.assertEqual(ns['A']().run(),21)
    def test_java_enum_varargs_array_and_typed_to_array(self):
        source='class A extends Goal {public boolean canUse(){return true;}int run(){EnumSet<Goal.Flag> flags=EnumSet.of(Goal.Flag.MOVE,new Goal.Flag[]{Goal.Flag.JUMP,Goal.Flag.LOOK});Goal.Flag[] array=flags.toArray(new Goal.Flag[0]);return array.length*10+array[1].ordinal();}}'
        ns,_=self.python(source);self.assertEqual(ns['A']().run(),31)
    def test_set_flags_accepts_native_and_generated_goal_with_no_fake_class_abi(self):
        source='class Logic {static int run(Goal target){target.setFlags(EnumSet.of(Goal.Flag.TARGET));return target.getFlags().iterator().next().ordinal();}}'
        ns,_=self.python(source);self.assertEqual(ns['Logic'].run(Goal()),3)
    def test_null_flags_retains_clear_before_exception(self):
        source=BASE+'boolean run(){try{setFlags(null);}catch(NullPointerException e){return getFlags().isEmpty();}return false;}}'
        ns,_=self.python(source);self.assertTrue(ns['A']().run())
    def test_collection_default_callbacks_keep_enum_parameter_type(self):
        source=BASE+'int count;int run(){getFlags().forEach(flag -> count+=flag.ordinal()+1);getFlags().removeIf(flag -> flag.ordinal()==0);getFlags().iterator().forEachRemaining(flag -> count+=flag.ordinal());return count*10+getFlags().size();}}'
        ns,_=self.python(source);self.assertEqual(ns['A']().run(),41)
        self.assertEqual(str(ns['A']().run()),self.original(source,'System.out.print(new A().run());'))
    def test_scalar_enum_constants_emit_actual_capability_guard(self):
        ns,result=self.python('class Logic {Goal.Flag run(){return Goal.Flag.MOVE;}}')
        self.assertIn('neocore.runtime.EnumSets@1',result['required_runtime_helpers'])
        self.assertIs(ns['Logic']().run(),Goal.Flag.MOVE)
    def test_unimplemented_stream_is_explicit_and_not_forwarded_as_success(self):
        with self.assertRaisesRegex(NeedsLowering,'implemented adapter: stream'):
            self.python(BASE+'Object run(){return getFlags().stream();}}')
    def test_void_expression_lambda_updates_are_lowered_as_statements(self):
        source='class Logic {int count;int run(){Runnable r=() -> count++;r.run();return count;}}'
        ns,_=helper.ArrayTests().python(source);self.assertEqual(ns['Logic']().run(),1)
        self.assertEqual(str(ns['Logic']().run()),helper.ArrayTests().java(source,'System.out.print(new Logic().run());'))
    def test_two_independently_translated_java_packs_share_core_without_entry_collision(self):
        from run_translation_job import run_job
        from build_source_bundle import core_bundle,content_bundle
        from workspace_paths import DEV_ROOT
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundles=[];entries=[];before={}
            for name in ('runtime_goal','runtime_enumset'):
                original=DEV_ROOT/'examples'/name
                before[name]={str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
                config=root/(name+'.json');config.write_text(json.dumps({'input':str(original),'output_root':str(root/'outputs'),'distribution':{'pack_id':name+'_content'}}),encoding='utf-8')
                report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
                if name=='runtime_enumset':
                    repeated=run_job(config);self.assertEqual(repeated['discovered_entrypoints'],report['discovered_entrypoints'])
                    self.assertNotEqual(repeated['output'],report['output'])
                entries.extend(report['discovered_entrypoints'].values())
                bundles.append(content_bundle(Path(report['output'])/'converted'/name,report['discovered_entrypoints']))
            self.assertEqual(len(set(value.split(':')[0] for value in entries)),2)
            session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],bundles)
            try:
                results=session.loader.activate();self.assertTrue(all(row.get('ready') for row in results.values()))
                contexts=session.loader.contexts;flags=contexts['runtime_enumset_example'].instance.goal.getFlags()
                self.assertEqual(str(flags),'[MOVE, LOOK]')
                event=session.runtime.load('neoforge.event.tick').ServerTickEvent.Post
                for unused in range(3):session.loader.post_game_event(event())
                self.assertEqual([context.instance.goal.ticks for context in contexts.values()],[2,2])
                session.close();self.assertTrue(all(context.game_bus.listenerCount()==0 for context in contexts.values()))
            finally:session.close()
            for name in before:
                original=DEV_ROOT/'examples'/name
                self.assertEqual(before[name],{str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()})
    def test_wrong_enum_factory_type_is_a_location_diagnostic(self):
        with self.assertRaisesRegex(NeedsLowering,'Line 1.*resolved reviewed enum type'):
            self.python('class A extends Goal {A(){setFlags(EnumSet.of("MOVE"));}public boolean canUse(){return true;}}')
if __name__=='__main__':unittest.main()

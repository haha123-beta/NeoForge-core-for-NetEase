import os,sys,tempfile,json,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
from java_codegen import NeedsLowering
from translate_java import translate
from run_translation_job import run_job
from build_source_bundle import core_bundle,content_bundle

SOURCE='import net.neoforged.fml.common.Mod;import net.neoforged.bus.api.IEventBus;import net.neoforged.fml.ModContainer;import net.neoforged.fml.javafmlmod.FMLModContainer;import net.neoforged.api.distmarker.Dist;import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;@Mod("demo_mod") public class Main {public int total;public String id;public String side;public Main(Dist dist,FMLModContainer actual,ModContainer metadata,IEventBus bus){id=metadata.getModId();side=dist.name();bus.addListener(this::setup);}private void setup(FMLCommonSetupEvent event){total+=1;}}'

class ModEntryTests(unittest.TestCase):
    def load(self,source,mod_id='demo_mod',side='SERVER'):
        namespace,result=arrays_test.ArrayTests().python(source)
        entry=result['mod_entrypoints'][0]
        loader=arrays_test.pkg.load('core.translated_loader').TranslatedModLoader(lambda _:namespace[entry['attribute']],side)
        report=loader.load({'schema_version':1,'mods':[{'mod_id':mod_id,'entrypoint':'example:start'}]})
        return loader,report,result
    def test_constructor_injection_and_original_listener_activate(self):
        loader,report,result=self.load(SOURCE)
        try:
            self.assertEqual(report['demo_mod']['state'],'initialized')
            context=loader.contexts['demo_mod'];obj=context.instance
            self.assertEqual((str(obj.id),str(obj.side),obj.total),('demo_mod','CLIENT',0))
            self.assertEqual(result['mod_entrypoints'][0]['constructor_signature'],['net.neoforged.api.distmarker.Dist','net.neoforged.fml.javafmlmod.FMLModContainer','net.neoforged.fml.ModContainer','net.neoforged.bus.api.IEventBus'])
            self.assertIs(context.mod_container.getEventBus(),context.mod_bus)
            self.assertTrue(loader.activate()['demo_mod']['ready']);self.assertEqual(obj.total,1)
            loader.close();self.assertEqual(context.mod_bus.listenerCount(),0)
        finally:loader.close()
    def test_invalid_public_or_duplicate_injection_declarations_are_rejected(self):
        prefixes='import net.neoforged.fml.common.Mod;import net.neoforged.bus.api.IEventBus;@Mod("demo_mod") '
        for body in ('class Main {}','public class Main {private Main(){}}','public class Main {public Main(){}public Main(IEventBus bus){}}','public class Main {public Main(IEventBus one,IEventBus two){}}'):
            with self.assertRaises(NeedsLowering):arrays_test.ArrayTests().python(prefixes+body)
    def test_annotation_id_mismatch_fails_and_cleans_context(self):
        loader,report,_=self.load(SOURCE,'other_mod')
        try:self.assertEqual(report['other_mod']['state'],'failed');self.assertNotIn('other_mod',loader.contexts)
        finally:loader.close()
    def test_physical_dist_is_separate_from_logical_server(self):
        source='import net.neoforged.fml.common.Mod;import net.neoforged.api.distmarker.Dist;@Mod(value="demo_mod",dist=Dist.DEDICATED_SERVER) public class Main {public Main(){throw new IllegalStateException();}}'
        loader,report,_=self.load(source,side='SERVER')
        try:self.assertEqual(report['demo_mod']['state'],'initialized');self.assertIsNone(loader.contexts['demo_mod'].instance)
        finally:loader.close()
    def test_source_constant_mod_id_preserves_package_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'input';(root/'demo').mkdir(parents=True)
            (root/'demo/Ids.java').write_text('package demo;public class Ids {public static final String MOD_ID="demo_mod";}')
            (root/'demo/Main.java').write_text('package demo;import net.neoforged.fml.common.Mod;@Mod(Ids.MOD_ID) public class Main {}')
            report=translate(root,Path(directory)/'output')
            self.assertEqual(report['manual_review'],0,report)
            row=next(row for row in report['results'] if row['file']=='demo/Main.java')
            self.assertEqual(row['mod_entrypoints'][0]['mod_id'],'demo_mod')
            self.assertTrue((Path(directory)/'output/input/demo/Main.py').exists())
    def test_annotation_entry_auto_packaging_runs_original_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'input';(root/'demo').mkdir(parents=True);(root/'META-INF').mkdir()
            (root/'demo/Main.java').write_text('package demo;'+SOURCE)
            (root/'META-INF/neoforge.mods.toml').write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="demo_mod"\nversion="1"\n')
            config=base/'job.json';config.write_text(json.dumps({'input':'input','output_root':'output','distribution':{'pack_id':'demo_content'}}))
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            folder=Path(report['output'])/'converted/input'
            content=content_bundle(folder,report['discovered_entrypoints'])
            session=arrays_test.pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[content])
            try:
                context=session.loader.contexts['demo_mod'];self.assertEqual(context.instance.total,0)
                session.loader.activate();self.assertEqual(context.instance.total,1)
            finally:session.close()

    def test_global_bus_listeners_are_owned_and_constructor_failure_rolls_back(self):
        base='import net.neoforged.fml.common.Mod;import net.neoforged.neoforge.common.NeoForge;import net.neoforged.neoforge.event.tick.ServerTickEvent;'
        good=base+'@Mod("good_mod") public class Main {public int hits;public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}private void tick(ServerTickEvent.Post event){hits+=1;}}'
        bad=base+'@Mod("bad_mod") public class Bad {public Bad(){NeoForge.EVENT_BUS.addListener(this::tick);throw new IllegalStateException();}private void tick(ServerTickEvent.Post event){}}'
        n1,r1=arrays_test.ArrayTests().python(good);n2,r2=arrays_test.ArrayTests().python(bad)
        entries={'good':n1[r1['mod_entrypoints'][0]['attribute']],'bad':n2[r2['mod_entrypoints'][0]['attribute']]}
        loader=arrays_test.pkg.load('core.translated_loader').TranslatedModLoader(lambda path:entries[path]);seen=[]
        def bad_entry(context):seen.append(context);return entries['bad'](context)
        loader.resolver=lambda path:bad_entry if path=='bad' else entries['good']
        try:
            report=loader.load({'schema_version':1,'mods':[{'mod_id':'good_mod','entrypoint':'good'},{'mod_id':'bad_mod','entrypoint':'bad'}]})
            self.assertEqual(report['bad_mod']['state'],'failed');self.assertEqual(seen[0].game_bus.listenerCount(),0)
            context=loader.contexts['good_mod'];self.assertEqual(context.game_bus.listenerCount(),1)
            event=arrays_test.pkg.load('neoforge.event.tick').ServerTickEvent.Post()
            loader.post_game_event(event);self.assertEqual(context.instance.hits,1)
            loader.close();self.assertEqual(context.game_bus.listenerCount(),0)
        finally:loader.close()
    def test_multiple_entry_classes_and_dist_skip_before_static_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'input';(root/'demo').mkdir(parents=True);(root/'META-INF').mkdir()
            head='package demo;import net.neoforged.fml.common.Mod;'
            (root/'demo/Common.java').write_text(head+'@Mod("demo_mod") public class Common {public int value=1;}')
            (root/'demo/Client.java').write_text(head+'import net.neoforged.api.distmarker.Dist;@Mod(value="demo_mod",dist=Dist.CLIENT) public class Client {public int value=2;}')
            (root/'demo/Dedicated.java').write_text(head+'import net.neoforged.api.distmarker.Dist;@Mod(value="demo_mod",dist=Dist.DEDICATED_SERVER) public class Dedicated {static int bad=fail();static int fail(){throw new IllegalStateException();}}')
            (root/'META-INF/neoforge.mods.toml').write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="demo_mod"\nversion="1"\n')
            config=base/'job.json';config.write_text(json.dumps({'input':'input','output_root':'output','distribution':{'pack_id':'demo_content'}}))
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            content=content_bundle(Path(report['output'])/'converted/input',report['discovered_entrypoints'])
            session=arrays_test.pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[content])
            try:
                self.assertEqual(session.report['demo_mod']['state'],'initialized',session.report)
                self.assertEqual(sorted(obj.value for obj in session.loader.contexts['demo_mod'].instance),[1,2])
                self.assertNotIn('demo.Dedicated',session.runtime.modules)
            finally:session.close()

    def test_original_enqueue_work_is_deferred_and_keeps_global_bus_owner(self):
        source='import net.neoforged.fml.common.Mod;import net.neoforged.bus.api.IEventBus;import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;import net.neoforged.neoforge.common.NeoForge;import net.neoforged.neoforge.event.tick.ServerTickEvent;@Mod("demo_mod") public class Main {public int stage;public int observed;public int hits;public Main(IEventBus bus){bus.addListener(this::setup);}private void setup(FMLCommonSetupEvent event){stage=1;event.enqueueWork(this::work);stage=2;}private void work(){observed=stage;NeoForge.EVENT_BUS.addListener(this::tick);}private void tick(ServerTickEvent.Post event){hits+=1;}}'
        loader,report,_=self.load(source)
        try:
            self.assertEqual(report['demo_mod']['state'],'initialized')
            self.assertTrue(loader.activate()['demo_mod']['ready'])
            context=loader.contexts['demo_mod'];self.assertEqual(context.instance.observed,2)
            loader.post_game_event(arrays_test.pkg.load('neoforge.event.tick').ServerTickEvent.Post())
            self.assertEqual(context.instance.hits,1);loader.close();self.assertEqual(context.game_bus.listenerCount(),0)
        finally:loader.close()
    def test_all_stage_handlers_finish_before_work_and_failed_work_isolated(self):
        pkg=arrays_test.pkg;event_type=pkg.load('neoforge.event.fml.lifecycle').FMLCommonSetupEvent
        order=[];futures=[]
        def first(context):
            def handler(event):
                order.append('first-handler');futures.append(event.enqueueWork(lambda:order.append('first-work')))
            context.mod_bus.subscribe(handler,event_type)
        def second(context):
            def handler(event):
                order.append('second-handler')
                def fail():raise RuntimeError('queued failure')
                event.enqueueWork(fail)
            context.mod_bus.subscribe(handler,event_type)
        entries={'first':first,'second':second};loader=pkg.load('core.translated_loader').TranslatedModLoader(lambda path:entries[path])
        try:
            loader.load({'schema_version':1,'mods':[{'mod_id':'aa_mod','entrypoint':'first'},{'mod_id':'bb_mod','entrypoint':'second'}]})
            result=loader.activate()
            self.assertEqual(order,['first-handler','second-handler','first-work'])
            self.assertTrue(result['aa_mod']['ready']);self.assertEqual(result['bb_mod']['state'],'failed')
            self.assertTrue(futures[0].isDone());self.assertIsNone(futures[0].join())
            self.assertEqual(loader.contexts['bb_mod'].mod_bus.listenerCount(),0)
        finally:loader.close()

if __name__=='__main__':unittest.main()

import os,sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
from java_codegen import NeedsLowering
from run_translation_job import run_job
from build_source_bundle import core_bundle,content_bundle

HEAD='package demo;import net.neoforged.fml.common.EventBusSubscriber;import net.neoforged.bus.api.SubscribeEvent;import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;import net.neoforged.neoforge.event.tick.ServerTickEvent;'

class EventAnnotationTests(unittest.TestCase):
    def session(self,folder,handler,explicit=False):
        root=folder/'input';(root/'demo').mkdir(parents=True);(root/'META-INF').mkdir()
        (root/'demo/Main.java').write_text('package demo;import net.neoforged.fml.common.Mod;@Mod("demo_mod") public class Main {}')
        (root/'demo/Handlers.java').write_text(handler)
        (root/'META-INF/neoforge.mods.toml').write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="demo_mod"\nversion="1"\n')
        distribution={'pack_id':'demo_content'}
        if explicit:distribution['entrypoints']={'demo_mod':'demo.Main:_nc_mod_entry_0'}
        config=folder/'job.json';config.write_text(json.dumps({'input':'input','output_root':'output','distribution':distribution}))
        report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
        sources=content_bundle(Path(report['output'])/'converted/input',report['discovered_entrypoints'])
        return arrays_test.pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[sources]),report
    def test_private_overloaded_handlers_select_buses_and_keep_original_name(self):
        source=HEAD+'@EventBusSubscriber(modid="demo_mod",bus=EventBusSubscriber.Bus.MOD) public class Handlers {public static int value;@SubscribeEvent private static void handle(FMLCommonSetupEvent event){value+=1;}@SubscribeEvent private static void handle(ServerTickEvent.Post event){value+=10;}}'
        with tempfile.TemporaryDirectory() as directory:
            session,report=self.session(Path(directory),source)
            try:
                context=session.loader.contexts['demo_mod'];handler=session.runtime.load('demo.Handlers').Handlers
                self.assertEqual((context.mod_bus.listenerCount(),context.game_bus.listenerCount()),(1,1))
                self.assertTrue(session.loader.activate()['demo_mod']['ready']);self.assertEqual(handler.value,1)
                session.loader.post_game_event(session.runtime.load('neoforge.event.tick').ServerTickEvent.Post());self.assertEqual(handler.value,11)
                self.assertEqual(context.game_bus.unregister(handler),0)
                session.close();self.assertEqual(context.game_bus.listenerCount(),0)
            finally:session.close()
    def test_automatic_non_static_and_abstract_event_are_rejected(self):
        for body in ('@EventBusSubscriber public class Handlers {@SubscribeEvent void run(FMLCommonSetupEvent event){}}','public class Handlers {@SubscribeEvent void run(ServerTickEvent event){}}'):
            with self.assertRaises(NeedsLowering):arrays_test.ArrayTests().python(HEAD+body)
    def test_manual_instance_registration_is_idempotent_and_unregisters_owner(self):
        source=HEAD+'public class Handlers {public int count;@SubscribeEvent private void handle(ServerTickEvent.Post event){count+=1;}}'
        namespace,result=arrays_test.ArrayTests().python(source)
        bus=arrays_test.pkg.load('neoforge.event.base').IEventBus('test');obj=namespace['Handlers']()
        bus.register(obj);bus.register(obj);self.assertEqual(bus.listenerCount(),1)
        bus.post(arrays_test.pkg.load('neoforge.event.tick').ServerTickEvent.Post(),strict=True);self.assertEqual(obj.count,1)
        self.assertEqual(bus.unregister(obj),1);self.assertIn('neocore.runtime.ModEntrypoints@2',result['required_runtime_helpers'])
    def test_single_bus_automatic_registration_keeps_class_unregistration(self):
        source=HEAD+'@EventBusSubscriber(modid="demo_mod") public class Handlers {public static int count;@SubscribeEvent private static void handle(ServerTickEvent.Post event){count+=1;}}'
        with tempfile.TemporaryDirectory() as directory:
            session,report=self.session(Path(directory),source)
            try:
                context=session.loader.contexts['demo_mod'];cls=session.runtime.load('demo.Handlers').Handlers
                self.assertEqual(context.game_bus.unregister(cls),1)
            finally:session.close()
    def test_wrong_physical_side_is_skipped_before_class_initialization(self):
        source=HEAD+'import net.neoforged.api.distmarker.Dist;@EventBusSubscriber(modid="demo_mod",value=Dist.DEDICATED_SERVER) public class Handlers {static int bad=fail();static int fail(){throw new IllegalStateException();}@SubscribeEvent private static void handle(ServerTickEvent.Post event){}}'
        with tempfile.TemporaryDirectory() as directory:
            session,report=self.session(Path(directory),source)
            try:self.assertNotIn('demo.Handlers',session.runtime.modules)
            finally:session.close()
    def test_priority_and_canceled_metadata_are_preserved(self):
        source=HEAD+'import net.neoforged.bus.api.EventPriority;public class Handlers {@SubscribeEvent(priority=EventPriority.LOW,receiveCanceled=true) private void handle(ServerTickEvent.Post event){}}'
        namespace,result=arrays_test.ArrayTests().python(source)
        metadata=namespace['Handlers']._nc_event_handlers[0]
        self.assertEqual(metadata['priority'],'LOW');self.assertTrue(metadata['receive_canceled'])

    def test_manual_source_class_registration_keeps_private_static_handler(self):
        source='import net.neoforged.fml.common.Mod;import net.neoforged.neoforge.common.NeoForge;import net.neoforged.bus.api.SubscribeEvent;import net.neoforged.neoforge.event.tick.ServerTickEvent;class Handlers {static int count;@SubscribeEvent private static void tick(ServerTickEvent.Post event){count+=1;}}@Mod("demo_mod") public class Main {public Main(){NeoForge.EVENT_BUS.register(Handlers.class);}}'
        namespace,result=arrays_test.ArrayTests().python(source)
        entry=result['mod_entrypoints'][0]['attribute'];loader=arrays_test.pkg.load('core.translated_loader').TranslatedModLoader(lambda _:namespace[entry])
        try:
            report=loader.load({'schema_version':1,'mods':[{'mod_id':'demo_mod','entrypoint':'source:entry'}]});self.assertEqual(report['demo_mod']['state'],'initialized',report)
            loader.post_game_event(arrays_test.pkg.load('neoforge.event.tick').ServerTickEvent.Post());self.assertEqual(namespace['Handlers'].count,1)
        finally:loader.close()
    def test_manual_registration_static_instance_mismatch_rejected(self):
        namespace,_=arrays_test.ArrayTests().python(HEAD+'public class Handlers {@SubscribeEvent private static void handle(ServerTickEvent.Post event){}}')
        bus=arrays_test.pkg.load('neoforge.event.base').IEventBus('test')
        with self.assertRaises(ValueError):bus.register(namespace['Handlers']())
        self.assertEqual(bus.listenerCount(),0)

    def test_annotation_constant_import_does_not_initialize_unrelated_class(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);root=folder/'input';(root/'demo').mkdir(parents=True);(root/'META-INF').mkdir()
            (root/'demo/Ids.java').write_text('package demo;public class Ids {public static final String MOD_ID="demo_mod";static int bad=fail();static int fail(){throw new IllegalStateException();}}')
            (root/'demo/Main.java').write_text('package demo;import net.neoforged.fml.common.Mod;@Mod("demo_mod") public class Main {}')
            (root/'demo/Handlers.java').write_text(HEAD+'import demo.Ids;@EventBusSubscriber(modid=Ids.MOD_ID) public class Handlers {@SubscribeEvent private static void handle(ServerTickEvent.Post event){}}')
            (root/'META-INF/neoforge.mods.toml').write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="demo_mod"\nversion="1"\n')
            config=folder/'job.json';config.write_text(json.dumps({'input':'input','output_root':'output','distribution':{'pack_id':'demo_content'}}))
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            sources=content_bundle(Path(report['output'])/'converted/input',report['discovered_entrypoints'])
            session=arrays_test.pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[sources])
            try:self.assertEqual(session.report['demo_mod']['state'],'initialized',session.report);self.assertNotIn('demo.Ids',session.runtime.modules)
            finally:session.close()
    def test_automatic_class_failure_retracts_constructor_listeners(self):
        bad=HEAD+'@EventBusSubscriber(modid="demo_mod") public class Handlers {static int bad=fail();static int fail(){throw new IllegalStateException();}@SubscribeEvent private static void handle(ServerTickEvent.Post event){}}'
        with tempfile.TemporaryDirectory() as directory:
            session,report=self.session(Path(directory),bad)
            try:self.assertEqual(session.report['demo_mod']['state'],'failed');self.assertNotIn('demo_mod',session.loader.contexts)
            finally:session.close()

    def test_explicit_entrypoints_still_register_automatic_subscribers(self):
        source=HEAD+'@EventBusSubscriber(modid="demo_mod") public class Handlers {public static int count;@SubscribeEvent private static void tick(ServerTickEvent.Post event){count+=1;}}'
        with tempfile.TemporaryDirectory() as directory:
            session,report=self.session(Path(directory),source,explicit=True)
            try:
                context=session.loader.contexts['demo_mod'];self.assertEqual(context.game_bus.listenerCount(),1)
                session.loader.post_game_event(session.runtime.load('neoforge.event.tick').ServerTickEvent.Post())
                self.assertEqual(session.runtime.load('demo.Handlers').Handlers.count,1)
            finally:session.close()

if __name__=='__main__':unittest.main()

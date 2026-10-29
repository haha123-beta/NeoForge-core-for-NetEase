import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from build_source_bundle import core_bundle,content_bundle
from harness import Package
from run_translation_job import run_job

MAIN='''package sample;
import net.neoforged.fml.common.Mod;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
@Mod("entity_generic_example") public class Main {
 public final DeferredRegister types=DeferredRegister.createEntities("entity_generic_example");
 public Main(IEventBus bus){
  types.register("counter",()->EntityType.Builder.of(Counter::new,MobCategory.MISC).sized(0.6f,1.8f).build("entity_generic_example:counter"));
  types.register(bus);
 }
}'''
COUNTER='''package sample;
import net.minecraft.world.entity.Entity;import net.minecraft.world.entity.EntityType;import net.minecraft.world.level.Level;
import net.minecraft.network.syncher.SynchedEntityData;import net.minecraft.nbt.CompoundTag;
public class Counter extends Entity {
 public int value=7;public int ticks;
 public Counter(EntityType type,Level level){super(type,level);}
 protected void defineSynchedData(SynchedEntityData.Builder builder){}
 protected void readAdditionalSaveData(CompoundTag tag){value=tag.getInt("v");}
 protected void addAdditionalSaveData(CompoundTag tag){tag.putInt("v",value);}
 public void tick(){super.tick();ticks++;value++;}
}'''

def fixture(root,namespace='entity_generic_example',package='sample'):
    root.mkdir(parents=True,exist_ok=True)
    metadata=root/'META-INF/neoforge.mods.toml';metadata.parent.mkdir();metadata.write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="'+namespace+'"\nversion="1"\n',encoding='utf-8')
    for name,raw in [('Main',MAIN),('Counter',COUNTER)]:
        p=root/package/(name+'.java');p.parent.mkdir(exist_ok=True);p.write_text(raw.replace('entity_generic_example',namespace).replace('package sample;','package '+package+';'),encoding='utf-8')

class EntityLoadingTests(unittest.TestCase):
    def test_complete_resources_export_attaches_only_declared_owned_static_visuals(self):
        from test_entity_visuals_080 import MODEL,png
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);root=tmp/'input';fixture(root)
            visual=tmp/'visual';visual.mkdir();(visual/'model.java').write_text(MODEL,encoding='utf-8');(visual/'texture.png').write_bytes(png())
            declaration={'schema_version':1,'pack_id':'generic_entity','entities':[{'identifier':'entity_generic_example:counter',
                'model_source':'model.java','layer_method':'layer','texture':'texture.png','collision':[0.6,1.8],'health':20}]}
            request=tmp/'job.json';request.write_text(json.dumps({'input':str(root),'output_root':str(tmp/'jobs'),
                'distribution':{'pack_id':'generic_entity','layout':'resources','visuals':{'source':str(visual),'declaration':declaration}}}),encoding='utf-8')
            result=run_job(request);self.assertEqual(result['status'],'PACKAGED_REVIEW_REQUIRED',result)
            output=Path(result['output'])/'distribution';content=result['distribution']['contents'][0]
            self.assertEqual(content['resource_pack_path'],'resource_pack-generic_entity')
            self.assertEqual(content['entity_visuals']['status'],'STATIC_VISUALS_ATTACHED')
            manifest=json.loads((output/content['pack_path']/'manifest.json').read_bytes())
            self.assertEqual(len(manifest['dependencies']),2)
            self.assertTrue((output/content['pack_path']/'entities/entity_generic_example__counter.json').is_file())
            self.assertFalse(any(p.suffix=='.java' for p in output.rglob('*')))

    def test_original_java_registers_two_namespaces_and_spawns_original_factories(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);contents=[]
            for namespace,package in [('entity_generic_example','sample'),('another_example','other')]:
                root=tmp/namespace;fixture(root,namespace,package)
                result=translate(root,tmp/(namespace+'_output'));self.assertEqual(result['manual_review'],0,result)
                self.assertEqual(result['failed'],0,result)
                contents.append(content_bundle(tmp/(namespace+'_output')/namespace,{namespace:package+'.Main:_nc_mod_entry_0'}))
            core=core_bundle();runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
            session=runtime.load('core.bundled_mods').BundledModSession(core['sources'],contents,runtime=runtime)
            try:
                result=session.loader.activate();self.assertTrue(all(row.get('ready') for row in result.values()),result)
                kinds=session.loader.registries['minecraft:entity_type'];self.assertEqual(len(kinds),2)
                entities=runtime.load('minecraft.entity');level=runtime.load('minecraft.level').Level.wrap(runtime.load('minecraft.level_access').InMemoryLevelAccess())
                self.assertEqual([str(value.name()) for value in entities.MobCategory.values()],['MONSTER','CREATURE','AMBIENT','AXOLOTLS','UNDERGROUND_WATER_CREATURE','WATER_CREATURE','WATER_AMBIENT','MISC'])
                self.assertIs(entities.MobCategory.valueOf('MISC'),entities.MobCategory.MISC)
                self.assertEqual(str(entities.MobCategory.MISC.getName()),'misc')
                objects=[]
                for key,kind in kinds.items():
                    self.assertAlmostEqual(kind.getWidth(),0.6000000238418579)
                    self.assertIsInstance(kind._factory,entities._EntityFactory)
                    obj=kind.create(level);obj.tick();self.assertEqual((obj.value,obj.ticks),(8,1));objects.append(obj)
                self.assertIsNot(type(objects[0]),type(objects[1]))
                retained=list(kinds.values());session.close()
                self.assertTrue(all(kind._factory is None for kind in retained))
                self.assertNotIn('entity_generic_example:counter',entities.EntityType._cache)
            finally:session.close();runtime.close()

if __name__=='__main__':unittest.main()

"""Build, packaging and binding protocol tests; SDK doubles are NOT engine proof."""
import copy, json, sys, tempfile, types, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_item_content import build, PROFILE
from run_translation_job import run_job
from harness import Package
from test_content_registry import FakeEngine

PNG = b'\x89PNG\r\n\x1a\n'  # Resource transport test, not image/render validation.


def fixture(root, namespace='sample'):
    def put(name, data):
        p=root/name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode())
    put('assets/'+namespace+'/models/item/one.json', {'parent':'minecraft:item/generated','textures':{'layer0':namespace+':item/one'}})
    put('assets/'+namespace+'/textures/item/one.png', PNG)
    put('assets/'+namespace+'/lang/en_us.json', {'item.'+namespace+'.one':'One'})
    put('data/'+namespace+'/recipe/one.json', {'type':'minecraft:crafting_shapeless','ingredients':[{'item':'minecraft:coal'}],'result':{'id':namespace+':one','count':8}})
    return {'schema_version':1,'profile':PROFILE,'native_items':['minecraft:coal'],
        'items':[{'identifier':namespace+':one','java_class':'net.minecraft.world.item.Item','max_stack_size':64,'unverified_behaviors':[]}]}


class ItemContent093Tests(unittest.TestCase):
    def test_identity_resource_and_recipe_share_exact_ids(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); declaration=fixture(root)
            data=build(root,'content',declaration)
            files=data['files']
            behavior=json.loads(files['behavior/netease_items_beh/sample/one.json'])['minecraft:item']
            resource=json.loads(files['resource/netease_items_res/sample/one.json'])['minecraft:item']
            self.assertEqual(behavior['description']['identifier'],'sample:one')
            self.assertEqual(resource['components']['minecraft:icon'],'sample:one')
            self.assertEqual(files['resource/texts/en_US.lang'],b'item.sample:one.name=One\n')
            recipe=json.loads(files['behavior/netease_recipes/sample/one.json'])['minecraft:recipe_shapeless']
            self.assertEqual(recipe['result'],{'item':'sample:one','count':8})
            self.assertFalse(data['report']['engine_verified'])

    def test_unmapped_recipe_missing_texture_and_unknown_model_fail(self):
        for problem in ('recipe','texture','model'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as t:
                root=Path(t);d=fixture(root)
                if problem=='recipe':d['native_items']=[]
                elif problem=='texture':(root/'assets/sample/textures/item/one.png').unlink()
                else:(root/'assets/sample/models/item/one.json').write_text('{"parent":"unsupported","textures":{}}')
                with self.assertRaises((ValueError,FileNotFoundError)):build(root,'content',d)

    def test_bad_and_duplicate_ids_fail(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=fixture(root)
            for name in ('sample:../one','sample:/one','minecraft:one'):
                x=copy.deepcopy(d);x['items'][0]['identifier']=name
                with self.assertRaises(ValueError):build(root,'content',x)
            d['items']*=2
            with self.assertRaises(ValueError):build(root,'content',d)

    def test_fuel_and_recipe_unlock_translation_is_bounded(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=fixture(root)
            d['items'][0]['creative_tab']='minecraft:ingredients'
            d['items'][0]['fuel']={'ticks':200,'proof':{'abi':1,'kind':'CONSTANT_FUEL_PRIVATE_FIELD',
                'field':'ticks','java_source_sha256':'0'*64,
                'descriptor':'(Lnet/minecraft/world/item/ItemStack;Lnet/minecraft/world/item/crafting/RecipeType;)I'}}
            p=root/'data/sample/advancement/recipes/one.json';p.parent.mkdir(parents=True)
            advancement={'parent':'minecraft:recipes/root','rewards':{'recipes':['sample:one']},
                         'criteria':{'input':{'trigger':'minecraft:inventory_changed','conditions':{'items':[{'items':['minecraft:coal']}]}},
                                     'known':{'trigger':'minecraft:recipe_unlocked','conditions':{'recipe':'sample:one'}}},
                         'requirements':[['input','known']]}
            p.write_text(json.dumps(advancement))
            data=build(root,'content',d)
            behavior=json.loads(data['files']['behavior/netease_items_beh/sample/one.json'])['minecraft:item']
            self.assertEqual(behavior['components']['netease:fuel']['duration'],10.0)
            self.assertTrue(behavior['description']['register_to_create_menu'])
            self.assertEqual(behavior['description']['category'],'Items')
            recipe=json.loads(data['files']['behavior/netease_recipes/sample/one.json'])
            self.assertEqual(recipe['format_version'],'1.20.10')
            self.assertEqual(recipe['minecraft:recipe_shapeless']['unlock'],[{'item':'minecraft:coal'}])
            self.assertEqual(data['contract']['unconverted_content'],[])
            advancement['requirements']=[['input'],['known']];p.write_text(json.dumps(advancement))
            data=build(root,'content',d)
            self.assertTrue(data['contract']['unconverted_content'])

    def test_real_pipeline_distribution_and_host_binding_protocol(self):
        for namespace in ('sample','another'):
            with self.subTest(namespace=namespace), tempfile.TemporaryDirectory() as t:
                tmp=Path(t);root=tmp/'input';d=fixture(root,namespace)
                meta=root/'META-INF/neoforge.mods.toml';meta.parent.mkdir()
                meta.write_text('modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="'+namespace+'"\nversion="1"\n')
                java=root/'Main.java';java.write_text('''import net.neoforged.fml.common.Mod;
import net.neoforged.bus.api.IEventBus;import net.neoforged.neoforge.registries.DeferredRegister;
import net.minecraft.world.item.Item;
@Mod("'''+namespace+'''") public class Main {
 public static final DeferredRegister.Items ITEMS=DeferredRegister.createItems("'''+namespace+'''");
 public Main(IEventBus bus){ITEMS.register("one",()->new Item(new Item.Properties()));ITEMS.register(bus);}
}''')
                request=tmp/'request.json';request.write_text(json.dumps({'input':str(root),'output_root':str(tmp/'jobs'),
                    'distribution':{'pack_id':'content','layout':'resources','items':('auto' if namespace=='sample' else d)}}))
                result=run_job(request)
                self.assertEqual(result['status'],'PACKAGED_REVIEW_REQUIRED',result)
                if namespace == 'sample':
                    self.assertTrue(result['item_registration']['python2_executed'])
                out=Path(result['output'])/'distribution'
                self.assertTrue((out/'behavior_pack-content/netease_items_beh'/namespace/'one.json').is_file())
                rp=out/'resource_pack-content';self.assertTrue((rp/'manifest.json').is_file())
                manifest=json.loads((out/'behavior_pack-content/manifest.json').read_bytes())
                self.assertEqual(len(manifest['dependencies']),2)
                scope={};exec((out/'behavior_pack-content/contentScripts/resources/_nc_resources.py').read_text(),scope)
                resource=scope['RESOURCE']
                engine,exports=FakeEngine(),{}
                def register(ns,name,path):
                    instance=exports[path.rsplit('.',1)[-1]](ns,name);engine.systems[(ns,name)]=instance;return instance
                engine.RegisterSystem=register
                # Explicit SDK test double; never recorded as a real engine run.
                component=types.SimpleNamespace(GetItemBasicInfo=lambda name,aux,ench:{'maxStackSize':64})
                engine.GetEngineCompFactory=lambda:types.SimpleNamespace(CreateItem=lambda level:component)
                engine.GetLevelId=lambda:'test-double-level'
                core_scope={};exec((out/'NeoCore_behavior_pack/NeoCoreSourceScripts/source_snapshot.py').read_text(),core_scope)
                host=Package().load('core.runtime_host').SourceRuntimeHost(core_scope['BUNDLE'],engine,'CLIENT',exports,'NeoCoreSourceScripts')
                try:
                    core=engine.GetSystem('NeoCore','Loader')
                    self.assertEqual(core.ITEM_CONTENT_PROTOCOL,1)
                    core.RegisterResourceContent('content',resource)
                    engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
                    report=core.GetContentReport()
                    self.assertEqual(report['state'],'initialized',report)
                    self.assertEqual(report['item_bindings']['status'],'NATIVE_IDS_BOUND',report)
                    self.assertFalse(report['item_bindings']['engine_verified'])
                    session=core.registry._session
                    item=session.loader.registries['minecraft:item'][namespace+':one']
                    stack=session.runtime.load('minecraft.item').ItemStack(item,3)
                    self.assertEqual(session.item_codec.encode(stack)['itemName'],namespace+':one')
                    self.assertEqual(session.item_codec.decode(session.item_codec.encode(stack)).getCount(),3)
                finally:host.close()

    def test_runtime_mismatch_missing_api_and_unverified_behavior_are_blocked(self):
        p=Package();module=p.load('core.item_content');Item=p.load('minecraft.item').Item
        contract={'schema_version':1,'profile':PROFILE,'owners':['sample'], 'items':[{
            'identifier':'sample:one','java_class':'net.minecraft.world.item.Item','max_stack_size':64,'unverified_behaviors':[]}]}
        results={'sample':{'ready':True}}
        with self.assertRaises(ValueError):module.bind([contract],{},results,None)
        registry={'minecraft:item':{'sample:one':Item()}}
        with self.assertRaises(RuntimeError):module.bind([contract],registry,results,None)
        api=types.SimpleNamespace(GetLevelId=lambda:'level',GetEngineCompFactory=lambda:types.SimpleNamespace(
            CreateItem=lambda level:types.SimpleNamespace(GetItemBasicInfo=lambda *args:None)))
        with self.assertRaises(ValueError):module.bind([contract],registry,results,api)
        contract['items'][0]['unverified_behaviors']=['fuel dispatch']
        with self.assertRaisesRegex(ValueError,'behavior remains unverified'):module.bind([contract],registry,results,api)

    def test_unsupported_properties_are_not_silently_dropped(self):
        p=Package();module=p.load('core.item_content');items=p.load('minecraft.item')
        for props in (items.ItemProperties().durability(17),items.ItemProperties().fireResistant()):
            row=module.describe(items.Item(props))
            self.assertTrue(row['unverified_behaviors'])


if __name__=='__main__':unittest.main()

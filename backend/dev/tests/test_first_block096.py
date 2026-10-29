"""Bounded method inference and generic cube content acceptance, no mod-ID cases."""
import sys,unittest,json,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from build_item_content import build

SOURCE='''import java.util.function.Supplier;
import net.minecraft.world.level.block.Block;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredBlock;
class Cube {
static final DeferredRegister.Blocks R=DeferredRegister.createBlocks("other");
static <T extends Block> DeferredBlock<T> add(String name,Supplier<T> value){
 DeferredBlock holder=R.register(name,value);return pass(holder);
}
static <T extends Block> DeferredBlock<T> pass(DeferredBlock<T> holder){return holder;}
static final DeferredBlock<Block> A=add("cube",()->new Block());
}'''

class FirstBlock096(unittest.TestCase):
 def generate(self,source):
  known,_=api_index();return generate(parse_source(source,known_types=known))
 def test_bounded_method_inference_preserves_erased_runtime_signature(self):
  value=self.generate(SOURCE)['python_source']
  self.assertIn("'java.util.function.Supplier')",value)
  self.assertNotIn('@methodvar:',value)
 def test_wrong_supplier_raw_unproven_bounds_and_unsound_return_rejected(self):
  cases=[SOURCE.replace('()->new Block()','()->"wrong"'),
         SOURCE.replace('Supplier<T> value','Supplier value'),
         SOURCE.replace('return holder;}','return new Block();}'),
         SOURCE.replace('return pass(holder);','holder=null;return pass(holder);')]
  for source in cases:
   with self.subTest(source=source),self.assertRaises((NeedsLowering,ValueError)):self.generate(source)
 def fixture(self,root,ns):
  name=ns+':stone';model=ns+':block/stone'
  def write(path,value):
   p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),encoding='utf-8')
  write('assets/'+ns+'/blockstates/stone.json',{'variants':{'':{'model':model}}})
  write('assets/'+ns+'/models/block/stone.json',{'parent':'minecraft:block/cube_all','textures':{'all':model}})
  write('assets/'+ns+'/models/item/stone.json',{'parent':model})
  write('assets/'+ns+'/lang/en_us.json',{'block.'+ns+'.stone':'Stone cube'})
  p=root/('assets/'+ns+'/textures/block/stone.png');p.parent.mkdir(parents=True);p.write_bytes(b'\x89PNG\r\n\x1a\n')
  write('data/'+ns+'/loot_table/blocks/stone.json',{'type':'minecraft:block','pools':[{'rolls':1,'entries':[{'type':'minecraft:item','name':name}],'conditions':[{'condition':'minecraft:survives_explosion'}]}]})
  return {'schema_version':1,'profile':'netease_pc_item_1_10','native_items':[],
   'items':[{'identifier':name,'java_class':'net.minecraft.world.item.BlockItem','max_stack_size':64,'unverified_behaviors':['Subclass gameplay requires target bridge: net.minecraft.world.item.BlockItem'],'creative_tab':'minecraft:building_blocks'}],
   'blocks':[{'identifier':name,'item':name,'java_class':'net.minecraft.world.level.block.Block','destroy_time':0.7,'explosion_resistance':2,'sound':'gravel','shape':'cube','states':{}}]}
 def test_same_converter_two_independent_namespaces_and_linked_native_definitions(self):
  for ns in ('first','unrelated'):
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);declaration=self.fixture(root,ns);value=build(root,'cubes',declaration)
    self.assertFalse(value['contract']['unconverted_content']);self.assertFalse(value['report']['issues'])
    block=json.loads(value['files']['behavior/netease_blocks/'+ns+'/stone.json'])['minecraft:block']
    self.assertEqual(block['description']['identifier'],ns+':stone')
    self.assertEqual(block['components']['minecraft:loot']['table'],'loot_tables/blocks/'+ns+'/stone.json')
    self.assertEqual(value['contract']['items'][0]['block'],ns+':stone')
    self.assertEqual(declaration['items'][0]['unverified_behaviors'],['Subclass gameplay requires target bridge: net.minecraft.world.item.BlockItem'])
 def test_state_variants_item_identity_and_behavior_gaps_never_flattened(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);good=self.fixture(root,'sample')
   for change in ('states','item','behavior','shape'):
    bad=copy.deepcopy(good)
    if change=='states':bad['blocks'][0]['states']={'axis':['x','y','z']}
    elif change=='item':bad['blocks'][0]['item']='sample:other'
    elif change=='shape':bad['blocks'][0]['shape']='slab'
    else:bad['items'][0]['unverified_behaviors'].append('custom callback')
    with self.subTest(change=change),self.assertRaises(ValueError):build(root,'cubes',bad)

if __name__=='__main__':unittest.main()

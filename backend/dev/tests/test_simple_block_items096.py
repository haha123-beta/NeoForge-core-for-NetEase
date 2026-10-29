"""Reviewed four overloads, lazy factories and invariant Holder base identity."""
import sys,unittest,json,subprocess,tempfile,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from java_method_overloads import subtype
from build_source_bundle import core_bundle
from workspace_paths import SCRIPTS_ROOT
from harness import Package

SOURCE='''import net.minecraft.world.level.block.Block;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.BlockItem;
import java.util.function.Supplier;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredBlock;
import net.neoforged.neoforge.registries.DeferredItem;
public class Run {
 public static final DeferredRegister.Items A=DeferredRegister.createItems("one");
 public static final DeferredRegister.Items B=DeferredRegister.createItems("two");
 public static void setup(DeferredBlock<Block> block,Supplier<Block> supplier,Item.Properties properties){
  A.registerSimpleBlockItem("named",supplier,properties);
  A.registerSimpleBlockItem("default",block);
  A.registerSimpleBlockItem(block);
  B.registerSimpleBlockItem(block,properties);
 }
 public static DeferredItem<BlockItem> lambda(Supplier<Block> source){return B.registerSimpleBlockItem("lambda",()->source.get());}
 public static BlockItem read(DeferredItem<BlockItem> item){return item.get();}
}'''

PROBE='''from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'simple_block_item_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources'])
api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
 Run=runtime.load('Run').Run
 r=runtime.load('neoforge.registries');items=runtime.load('minecraft.item');Block=runtime.load('minecraft.block').Block
 Supplier=runtime.load('java_stdlib.function').Supplier
 blocks=r.DeferredRegister.createBlocks('foreign');seen=[]
 block=blocks.register('rock',Supplier(lambda: seen.append('block') or Block()))
 props=items.Item.Properties().stacksTo(16)
 Run.setup(block,Supplier(lambda: block.get()),props)
 h=getattr(Run,'lambda')(Supplier(lambda: block.get()))
 assert seen==[] and not h.isBound()
 assert [x.getId().toString() for x in Run.A.getEntries()]==['one:named','one:default','one:rock']
 assert [x.getId().toString() for x in Run.B.getEntries()]==['two:rock','two:lambda']
 blocks.freeze_and_register();Run.A.freeze_and_register();Run.B.freeze_and_register()
 assert seen==['block']
 for reg in (Run.A,Run.B):
  for value in reg.getEntries():
   item=Run.read(value)
   assert isinstance(item,items.BlockItem) and item.getBlock() is block.get()
   gaps=runtime.load('core.item_content').describe(item)['unverified_behaviors']
   assert gaps and 'target bridge' in gaps[0]
 assert Run.A.getHolder('named').get().getMaxStackSize()==16
 assert Run.A.getHolder('default').get().getMaxStackSize()==64
 # This stage does not substitute an ordinary item for native block placement.
 try:h.get().place(None);raise AssertionError('placement unexpectedly accepted')
 except NotImplementedError:pass
 # Exercise the real loader barrier and cleanup on both interpreters.
 manager_type=runtime.load('core.translated_loader').TranslatedModLoader
 lifecycle=runtime.load('neoforge.event.fml.lifecycle')
 for broken_setup in (False,True):
  blocks2=r.DeferredRegister.createBlocks('second')
  h2=blocks2.register('rock',Supplier(lambda: Block()))
  items2=r.DeferredRegister.createItems('first');i2=items2.registerSimpleBlockItem(h2)
  def entry(ctx):
   if ctx.mod_id=='first':
    items2.register(ctx.mod_bus)
    if broken_setup:
     def fail(event):raise ValueError('setup rejected')
     ctx.mod_bus.subscribe(fail,lifecycle.FMLCommonSetupEvent)
   else:blocks2.register(ctx.mod_bus)
  manager=manager_type(lambda path:entry)
  manager.load({'schema_version':1,'mods':[{'mod_id':'first','entrypoint':'entry'},{'mod_id':'second','entrypoint':'entry'}]})
  result=manager.activate()
  assert result['second']['ready'] and result['first']['ready']==(not broken_setup)
  if broken_setup:assert h2.get().asItem() is None
  else:assert h2.get().asItem() is i2.get()
  manager.close();assert h2.get().asItem() is None and manager.registries=={}
 print('GENERATED_BLOCK_ITEMS_PASS; engine_verified=false')
finally:imports.close();runtime.close()
'''

class SimpleBlockItems096(unittest.TestCase):
 def test_four_overloads_and_lambda_execute_on_actual_python2_and_python3(self):
  known,_=api_index();code=generate(parse_source(SOURCE,known_types=known))['python_source']
  sources=core_bundle()['sources'];sources['Run']={'source':code,'origin':'Run.java','sha256':hashlib.sha256(code.encode()).hexdigest()}
  payload={'sources':sources,'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8')}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'input.json').write_text(json.dumps(payload),encoding='utf-8');(root/'probe.py').write_text(PROBE,encoding='utf-8')
   for interpreter in (r'D:\NeoCore工具\python27_validation\runtime\python.exe',sys.executable):
    p=subprocess.run([interpreter,'-B',str(root/'probe.py'),str(root/'input.json')],capture_output=True,text=True)
    self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertIn('GENERATED_BLOCK_ITEMS_PASS',p.stdout)

 def test_strict_invalid_calls_and_wrong_lambda_returns(self):
  known,_=api_index()
  cases=[SOURCE.replace('Supplier<Block> supplier','Supplier<String> supplier'),
   SOURCE.replace('DeferredBlock<Block> block','DeferredItem<Item> block'),
   SOURCE.replace('"named",supplier,properties','"named",supplier,"wrong"'),
   SOURCE.replace('()->source.get()','()->"wrong"'),
   SOURCE.replace('Supplier<Block> supplier','Supplier supplier'),
   SOURCE.replace('A.registerSimpleBlockItem(block);','A.registerSimpleBlockItem();')]
  for source in cases:
   with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

 def test_deferred_generic_ancestry_keeps_registry_and_value_types_distinct(self):
  h='net.neoforged.neoforge.registries.DeferredHolder';b='net.minecraft.world.level.block.Block';i='net.minecraft.world.item.Item'
  self.assertTrue(subtype(h+'<'+b+','+b+'>','net.minecraft.core.Holder<'+b+'>',{},{}))
  self.assertTrue(subtype(h+'<'+b+','+b+'>','java.util.function.Supplier<? extends '+b+'>',{},{}))
  self.assertFalse(subtype(h+'<'+i+','+i+'>','net.minecraft.core.Holder<'+b+'>',{},{}))
  self.assertFalse(subtype(h+'<'+b+','+b+'>','net.minecraft.core.Holder<'+i+'>',{},{}))
  self.assertFalse(subtype('java.util.function.Supplier<java.lang.String>','java.util.function.Supplier<? extends '+b+'>',{},{}))
  self.assertFalse(subtype(h+'<'+b+','+i+'>','net.minecraft.core.Holder<'+b+'>',{},{}))
  self.assertFalse(subtype('net.neoforged.neoforge.registries.DeferredBlock<java.lang.String>','net.minecraft.core.Holder<'+b+'>',{},{}))
  self.assertFalse(subtype(h+'<int,int>','net.minecraft.core.Holder<int>',{},{}))

 def test_registry_binding_is_reversible_and_preserves_virtual_mapping(self):
  p=Package();r=p.load('neoforge.registries');items=p.load('minecraft.item');Block=p.load('minecraft.block').Block
  block,other=Block(),Block();before=items.Item();block.setItem(before)
  class Virtual(items.BlockItem):
   def registerBlocks(self,mapping,item):mapping[other]=item
  value=Virtual(block,items.Item.Properties());registry=r.Registry('minecraft:item')
  registry.put('test:virtual',value)
  self.assertIs(block.asItem(),before);self.assertIs(other.asItem(),value)
  registry.clear();self.assertIsNone(other.asItem());self.assertIs(block.asItem(),before)
  registry=r.Registry('minecraft:block');registry.put('test:rock',block)
  self.assertEqual(block.getDescriptionId(),'block.test.rock')

 def test_global_block_barrier_precedes_item_factories_and_failure_cleans_links(self):
  for fail in (False,True):
   p=Package();r=p.load('neoforge.registries');items=p.load('minecraft.item');Block=p.load('minecraft.block').Block
   loader=p.load('core.translated_loader');lifecycle=p.load('neoforge.event.fml.lifecycle');seen=[]
   blocks=r.DeferredRegister.createBlocks('z_blocks');h=blocks.register('rock',lambda:seen.append('block') or Block())
   components=r.DeferredRegister.create('minecraft:data_component_type','z_blocks')
   components.register('marker',lambda:seen.append('component') or object())
   native_items=r.DeferredRegister.createItems('a_items');item=native_items.registerSimpleBlockItem(h)
   def entry(context):
    if context.mod_id=='a_items':
     native_items.register(context.mod_bus)
     if fail:
      def broken(event):raise ValueError('intentional setup failure')
      context.mod_bus.subscribe(broken,lifecycle.FMLCommonSetupEvent)
    else:
     blocks.register(context.mod_bus)
     components.register(context.mod_bus)
   manager=loader.TranslatedModLoader(lambda path:entry)
   manager.load({'schema_version':1,'mods':[{'mod_id':'a_items','entrypoint':'entry'},{'mod_id':'z_blocks','entrypoint':'entry'}]})
   report=manager.activate();self.assertEqual(seen,['component','block'])
   self.assertEqual(report['a_items'].get('ready'),not fail)
   self.assertTrue(report['z_blocks']['ready'])
   self.assertEqual(h.get().getRegistryName(),'z_blocks:rock')
   if fail:
    self.assertIsNone(h.get().asItem());self.assertNotIn('a_items:rock',manager.registries['minecraft:item'])
   else:self.assertIs(h.get().asItem(),item.get())
   manager.close();self.assertIsNone(h.get().asItem());self.assertEqual(manager.registries,{})

 def test_lazy_null_and_keyed_holder_runtime_contract(self):
  p=Package();r=p.load('neoforge.registries');items=p.load('minecraft.item');Block=p.load('minecraft.block').Block
  lang=p.load('java_stdlib.lang');Holder=p.load('minecraft.registries').Holder
  reg=r.DeferredRegister.createItems('one')
  self.assertRaises(lang.NullPointerException,reg.registerSimpleBlockItem,None)
  self.assertRaises(p.load('java_stdlib.util').NoSuchElementException,reg.registerSimpleBlockItem,Holder.direct(None))
  h=reg.registerSimpleBlockItem('null_supplier',None)
  self.assertFalse(h.isBound());self.assertRaises(lang.NullPointerException,reg.freeze_and_register);self.assertFalse(h.isBound())
  reg=r.DeferredRegister.createItems('two');block=Block();key=r.ResourceKey('minecraft:block',r.ResourceLocation('foreign','rock'))
  h=reg.registerSimpleBlockItem(Holder(block,key));reg.freeze_and_register()
  self.assertEqual(h.getId().toString(),'two:rock');self.assertIs(h.get().getBlock(),block)
  self.assertIs(block.asItem(),h.get()) # Only the registry barrier establishes the link.
  block2=Block();registered=r.Registry('minecraft:block');registered.put('foreign:reference',block2)
  reg2=r.DeferredRegister.createItems('third');h2=reg2.registerSimpleBlockItem(registered._holder_for_value(block2))
  reg2.freeze_and_register();self.assertEqual(h2.getId().toString(),'third:reference')
  self.assertIs(h2.get().getBlock(),block2)

if __name__=='__main__':unittest.main()

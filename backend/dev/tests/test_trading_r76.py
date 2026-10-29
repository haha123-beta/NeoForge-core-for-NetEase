import json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workspace_paths import DEV_ROOT
sys.path.insert(0,str(DEV_ROOT))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from build_source_bundle import core_bundle
from harness import Package

SOURCE='''package trades;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.trading.ItemCost;
import net.minecraft.world.item.trading.MerchantOffer;
import net.minecraft.world.item.trading.MerchantOffers;
public class Logic {
 public static MerchantOffer make(Item payment,Item sold){return new MerchantOffer(new ItemCost(payment,3),new ItemStack(sold,2),2,5,0);}
 public static int run(MerchantOffer offer,ItemStack a,ItemStack b){if(!offer.take(a,b))return -1;offer.increaseUses();MerchantOffers all=new MerchantOffers();all.add(offer);return all.get(0).getUses()*100+a.getCount();}
}'''

class TradingTests(unittest.TestCase):
 def test_original_source_payment_chain_and_new_type_requirements(self):
  known,_=api_index();result=generate(parse_source(SOURCE,known_types=known))
  self.assertIn('net.minecraft.world.item.trading.MerchantOffer',result['required_api_types'])
  core=core_bundle();raw=result['python_source']
  import hashlib
  core['sources']['trades.Logic']={'source':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
  runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
  api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
  try:
   items=runtime.load('minecraft.item');payment=items.Item();sold=items.Item()
   cls=runtime.load('trades.Logic').Logic;offer=cls.make(payment,sold);stack=items.ItemStack(payment,7)
   self.assertEqual(cls.run(offer,stack,items.ItemStack.EMPTY),104)
   self.assertEqual(cls.run(offer,stack,items.ItemStack.EMPTY),201)
   self.assertEqual(cls.run(offer,stack,items.ItemStack.EMPTY),-1)
   self.assertEqual((stack.getCount(),offer.getUses()),(1,2))
  finally:scope.close();runtime.close()
 def test_unsupported_components_constructors_and_wrong_types_are_blocked(self):
  known,_=api_index()
  for old,new in [('new ItemCost(payment,3)','new ItemCost(payment,true)'),('new MerchantOffers()','new MerchantOffers(2)'),('offer.increaseUses()','offer.setSpecialPriceDiff(true)'),('offer.increaseUses()','offer.getItemCostA().components()')]:
   with self.subTest(new=new),self.assertRaises(NeedsLowering):generate(parse_source(SOURCE.replace(old,new),known_types=known))
 def test_payment_edges_and_jdk_float32_contract_on_actual_python2(self):
  script=DEV_ROOT/'references/trading-r76/verify_trading.py'
  p=subprocess.run([sys.executable,'-B',str(script)],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_fourteen_contents_and_old_core_gate_on_actual_python2(self):
  script=DEV_ROOT/'references/trading-r76/verify_content.py'
  p=subprocess.run([sys.executable,'-B',str(script)],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)

if __name__=='__main__':unittest.main()

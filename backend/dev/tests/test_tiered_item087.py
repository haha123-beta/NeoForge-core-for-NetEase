import os,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import run_original,mapping
from test_network086 import GROUPS
from java_method_overloads import canonical,subtype
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
import test_official_interfaces086 as execution

class TieredItem087(unittest.TestCase):
    def test_original_constructor_and_delegation_in_actual_python2(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        result=run_original((ref/'tiered_item_probe.java.txt').read_text(),GROUPS+('com.google.guava:failureaccess',))
        # Bootstrap freezes vanilla registries, so inspect a real registered iron
        # pickaxe rather than reopening the registry to construct an artificial item.
        self.assertEqual(result,'RESULT:true,14,1,false')
        self.assertIn('void <init>(net.minecraft.world.item.Tier,net.minecraft.world.item.Item$Properties)',mapping('net.minecraft.world.item.TieredItem'))
        source='''import net.minecraft.world.item.Tier;import net.minecraft.world.item.TieredItem;import net.minecraft.world.item.Item;import net.minecraft.world.item.crafting.Ingredient;import net.minecraft.tags.TagKey;import net.minecraft.world.level.block.Block;
class Material implements Tier {public int getUses(){return 17;}public float getSpeed(){return 3.5f;}public float getAttackDamageBonus(){return 2.0f;}public TagKey<Block> getIncorrectBlocksForDrops(){return null;}public int getEnchantmentValue(){return 9;}public Ingredient getRepairIngredient(){return Ingredient.EMPTY;}}
public class Run extends TieredItem {public Run(){super(new Material(),new Item.Properties().stacksTo(6));}public int run(){TieredItem item=this;Item base=this;if(item.isValidRepairItem(null,null))return 99;return getTier().getUses()+item.getEnchantmentValue()+base.getDefaultMaxStackSize();}}'''
        execution.OfficialInterfaces086().execute(source,'27')
        digger=source.replace('import net.minecraft.world.item.TieredItem;','import net.minecraft.world.item.TieredItem;import net.minecraft.world.item.DiggerItem;').replace('Run extends TieredItem','Run extends DiggerItem').replace('super(new Material(),new Item.Properties()', 'super(new Material(),null,new Item.Properties()')
        execution.OfficialInterfaces086().execute(digger,'27')
        sword=source.replace('import net.minecraft.world.item.TieredItem;','import net.minecraft.world.item.TieredItem;import net.minecraft.world.item.SwordItem;').replace('Run extends TieredItem','Run extends SwordItem')
        execution.OfficialInterfaces086().execute(sword,'27')

    def test_builder_mutation_snapshot_null_and_virtual_tier(self):
        p=Package();m=p.load('minecraft.tool_rules');items=p.load('minecraft.item');rt=p.load('minecraft.runtime_classes').RuntimeClasses
        class Material(m.Tier):
            def getUses(self):return 17
            def getSpeed(self):return 3.5
            def getIncorrectBlocksForDrops(self):return None
            def getEnchantmentValue(self):return 9
            def getRepairIngredient(self):return p.load('minecraft.crafting').Ingredient.of(material)
        material=items.Item();other=items.Item();tier=Material();props=items.ItemProperties().stacksTo(6)
        contract=rt.contracts()['net.minecraft.world.item.TieredItem'];cls=rt.bind(contract['java_name'],contract);item=cls(tier,props)
        self.assertIs(item.getTier(),tier);self.assertEqual((props.max_damage,props.max_stack_size),(17,1));self.assertEqual(item.getEnchantmentValue(),9)
        props.durability(99);self.assertEqual(item.getMaxDamage(),17)
        self.assertTrue(item.isValidRepairItem(None,items.ItemStack(material)));self.assertFalse(item.isValidRepairItem(None,items.ItemStack(other)))
        lang=p.load('java_stdlib.lang')
        with self.assertRaises(lang.NullPointerException):cls(None,props)
        with self.assertRaises(lang.NullPointerException):cls(tier,None)
        with self.assertRaises(TypeError):cls(object(),props)
        digger_contract=rt.contracts()['net.minecraft.world.item.DiggerItem'];digger=rt.bind(digger_contract['java_name'],digger_contract)(tier,None,props)
        self.assertEqual(digger.properties._tool_component.rules().size(),2)
        self.assertEqual(digger.properties._tool_component.rules().get(1).speed().get().floatValue(),3.5)
        self.assertTrue(digger.hurtEnemy(None,None,None))
        sword_contract=rt.contracts()['net.minecraft.world.item.SwordItem'];sword=rt.bind(sword_contract['java_name'],sword_contract)(tier,items.ItemProperties())
        tool=sword.properties._tool_component;rules=tool.rules();cobweb=p.load('minecraft.block').BLOCKS.COBWEB
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        result=run_original((ref/'sword_tool_probe.java.txt').read_text(),GROUPS+('com.google.guava:failureaccess',))
        actual='RESULT:'+','.join(str(x).lower() if isinstance(x,bool) else str(x) for x in (rules.size(),tool.defaultMiningSpeed(),tool.damagePerBlock(),rules.get(0).speed().get().floatValue(),rules.get(0).correctForDrops().get().booleanValue(),rules.get(1).speed().get().floatValue(),rules.get(1).correctForDrops().isEmpty()))
        self.assertEqual(actual,result)
        self.assertEqual(tool.getMiningSpeed(cobweb.defaultBlockState()),15.0);self.assertTrue(tool.isCorrectForDrops(cobweb.defaultBlockState()))

    def test_generic_argument_canonicalization_and_invariant_types(self):
        unit={'package':'demo','imports':[{'name':'net.minecraft.tags.TagKey','static':False,'wildcard':False},{'name':'net.minecraft.world.level.block.Block','static':False,'wildcard':False}]}
        expected='net.minecraft.tags.TagKey<net.minecraft.world.level.block.Block>'
        self.assertEqual(canonical('TagKey<Block>',{},unit),expected)
        self.assertEqual(canonical('TagKey<? extends Block>[]',{},unit),'net.minecraft.tags.TagKey<? extends net.minecraft.world.level.block.Block>[]')
        self.assertFalse(subtype(expected,'net.minecraft.tags.TagKey<java.lang.Object>',{},unit))
        self.assertFalse(subtype(expected,'net.minecraft.tags.TagKey<java.lang.String>',{},unit))
        with self.assertRaises(ValueError):canonical('?extendsBlock',{},unit)
        from java_entity_signatures import resolve
        from java_library_signatures import generic_arguments,canonical_generic
        result=resolve('net.neoforged.neoforge.registries.DeferredHolder<?extendsjava.lang.Object,java.lang.String>','net.neoforged.neoforge.registries.DeferredHolder','get',0,[],canonical_generic,generic_arguments,lambda name:canonical(name,{},unit))
        self.assertEqual(result['return_type'],'java.lang.String')

    def test_world_behavior_and_wrong_constructor_stay_review(self):
        known,_=api_index()
        for source in ['import net.minecraft.world.item.TieredItem;class Run extends TieredItem {Run(){super(true,null);}}','import net.minecraft.world.item.TieredItem;class Run {void f(TieredItem t){t.use(null,null,null);}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

if __name__=='__main__':unittest.main()

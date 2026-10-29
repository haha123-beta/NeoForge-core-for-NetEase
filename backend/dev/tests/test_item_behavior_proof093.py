"""Constant-fuel proof must reject contextual/mutable gameplay shapes."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source, api_index
from java_codegen import generate
from java_symbols import declarations
from java_method_overloads import canonical
from java_item_bridges import constant_fuel

SOURCE='''import net.minecraft.world.item.Item;import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.RecipeType;
public class Fuel extends Item {
 private int ticks=0;
 public Fuel(Item.Properties properties,int value){super(properties);this.ticks=value;}
 public int getBurnTime(ItemStack stack,RecipeType<?> recipe){return this.ticks;}
}'''


class ItemBehaviorProof093Tests(unittest.TestCase):
    def proof(self, source):
        known,_=api_index();ir=parse_source(source,known_types=known)
        row=declarations(ir)['classes'][0]
        return constant_fuel(row,ir,lambda value:canonical(value,row,ir))

    def test_private_field_constructor_and_getter_prove_constant_behavior(self):
        proof=self.proof(SOURCE)
        self.assertEqual(proof['field'],'ticks')
        known,_=api_index();output=generate(parse_source(SOURCE,known_types=known))
        self.assertIn('_nc_ItemBehaviorBridge',str(output))

    def test_contextual_returns_mutators_visibility_and_constructor_effects_fail_closed(self):
        cases=[SOURCE.replace('extends Item {','extends Item implements java.lang.Cloneable {'),
               SOURCE.replace('return this.ticks;','return stack.getCount();'),
               SOURCE.replace('return this.ticks;','return this.ticks+1;'),
               SOURCE.replace('private int ticks','public int ticks'),
               SOURCE.replace('private int ticks','protected int ticks'),
               SOURCE.replace('this.ticks=value;','this.ticks=value;this.ticks++;'),
               SOURCE.replace('public int getBurnTime','public void mutate(){this.ticks++;} public int getBurnTime')]
        for source in cases:
            with self.subTest(source=source):self.assertIsNone(self.proof(source))


if __name__=='__main__':unittest.main()

"""Full frontend/codegen contracts for the typed item registration subset."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source, api_index
from java_codegen import generate, NeedsLowering

SOURCE = '''import net.minecraft.world.item.Item;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredItem;
public class Run {
 public static final DeferredRegister.Items ITEMS=DeferredRegister.createItems("sample");
 public static final DeferredItem<Item> ONE=ITEMS.register("one",()->new Item(new Item.Properties()));
}'''


class ItemRegistrationCodegen093Tests(unittest.TestCase):
    def test_independent_namespaces_use_the_same_contract(self):
        known, _ = api_index()
        for namespace in ('sample', 'other'):
            with self.subTest(namespace=namespace):
                result = generate(parse_source(SOURCE.replace('"sample"', '"'+namespace+'"'), known_types=known))
                self.assertTrue(result)

    def test_illegal_argument_types_and_supplier_result_are_rejected(self):
        known, _ = api_index()
        cases = [SOURCE.replace('createItems("sample")', 'createItems(7)'),
                 SOURCE.replace('()->new Item(new Item.Properties())', '()->"wrong"'),
                 SOURCE.replace('ITEMS.register("one",', 'ITEMS.register(7,'),
                 SOURCE.replace('ITEMS.register("one",()->new Item(new Item.Properties()))',
                                'ITEMS.register("one",7)')]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(NeedsLowering):
                generate(parse_source(source, known_types=known))


if __name__ == '__main__':
    unittest.main()

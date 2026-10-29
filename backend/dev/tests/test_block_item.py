import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package


class BlockItemTests(unittest.TestCase):
    def setUp(self):
        pkg = Package()
        self.items = pkg.load('minecraft.item')
        self.blocks = pkg.load('minecraft.block')

    def test_identity_properties_description_and_mapping_only_registration(self):
        block = self.blocks.Block().setRegistryName('demo:block')
        props = self.items.Item.Properties().stacksTo(16)
        item = self.items.BlockItem(block, props).setRegistryName('demo:other_item_id')
        self.assertIs(item.getBlock(), block)
        self.assertEqual(item.getMaxStackSize(), 16)
        self.assertEqual(item.getDescriptionId(), 'block.demo.block')
        mapping = {}
        other = self.items.Item(self.items.Item.Properties())
        self.assertIsNone(item.registerBlocks(mapping, other))
        self.assertIs(mapping[block], other)
        self.assertIsNone(block.asItem())
        self.assertIs(self.items.JAVA_MAP['net.minecraft.world.item.BlockItem'], self.items.BlockItem)

    def test_virtual_get_block_and_java_map_put(self):
        block = self.blocks.Block().setRegistryName('demo:override')
        class Override(self.items.BlockItem):
            def getBlock(self):
                return block
        item = Override(None, self.items.Item.Properties())
        class Map(object):
            def put(self, key, value):
                self.key, self.value = key, value
                return 'old'
        mapping = Map()
        self.assertEqual(item.getDescriptionId(), 'block.demo.override')
        self.assertIsNone(item.registerBlocks(mapping, item))
        self.assertIs(mapping.key, block)
        self.assertIs(mapping.value, item)
        context = object()
        self.assertIs(item.updatePlacementContext(context), context)
        self.assertTrue(item.mustSurvive())

    def test_native_operations_fail_explicitly(self):
        item = self.items.BlockItem(self.blocks.Block(), self.items.Item.Properties())
        for name, args in [('useOn', (None,)), ('place', (None,)),
                           ('placeBlock', (None, None)), ('canFitInsideContainerItems', ())]:
            with self.subTest(method=name), self.assertRaises(NotImplementedError):
                getattr(item, name)(*args)


if __name__ == '__main__':
    unittest.main()

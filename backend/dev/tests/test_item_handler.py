import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
handlers = pkg.load('neoforge.items')
items = pkg.load('minecraft.item')
capabilities = pkg.load('neoforge.capabilities')


class SmallHandler(handlers.ItemStackHandler):
    def __init__(self):
        self.changed = []
        handlers.ItemStackHandler.__init__(self, 2)
    def getSlotLimit(self, slot):
        return 4
    def onContentsChanged(self, slot):
        self.changed.append(slot)


class HandlerTests(unittest.TestCase):
    def test_insert_remainder_simulation_and_extract(self):
        handler = SmallHandler()
        item = items.Item(identifier='sample:item')
        input_stack = items.ItemStack(item, 6)
        remainder = handler.insertItem(0, input_stack, True)
        self.assertEqual(remainder.getCount(), 2)
        self.assertTrue(handler.getStackInSlot(0).isEmpty())
        self.assertEqual(handler.changed, [])
        remainder = handler.insertItem(0, input_stack, False)
        self.assertEqual((input_stack.getCount(), remainder.getCount(), handler.getStackInSlot(0).getCount()), (6, 2, 4))
        self.assertEqual(handler.changed, [0])
        extracted = handler.extractItem(0, 2, True)
        self.assertEqual(extracted.getCount(), 2)
        self.assertEqual(handler.getStackInSlot(0).getCount(), 4)
        self.assertEqual(handler.changed, [0])
        self.assertEqual(handler.extractItem(0, 2, False).getCount(), 2)
        self.assertEqual(handler.getStackInSlot(0).getCount(), 2)
        self.assertEqual(handler.extractItem(0, 9, False).getCount(), 2)
        self.assertTrue(handler.getStackInSlot(0).isEmpty())

    def test_default_handler_keeps_excess_remainder_and_java_count_semantics(self):
        handler = handlers.ItemStackHandler()
        item = items.Item(identifier='sample:bulk')
        stack = items.ItemStack(item, 999)
        remainder = handler.insertItem(0, stack, False)
        self.assertEqual(stack.getCount(), 999)
        self.assertEqual(handler.getStackInSlot(0).getCount(), 64)
        self.assertEqual(remainder.getCount(), 935)
        stack.setCount(-5)
        self.assertEqual(stack.getCount(), 0)
        stack.grow(3)
        self.assertEqual(stack.getCount(), 3)
        stack.setCount(2147483647)
        stack.grow(1)
        self.assertEqual(stack.getCount(), 0)
        self.assertEqual(stack._count, -2147483648)
        self.assertTrue(items.ItemStack(items.ITEMS.AIR, 1).isEmpty())

    def test_unresolved_storage_roundtrip_preserves_id_and_count(self):
        blocks = pkg.load('minecraft.block_entity')
        nbt = pkg.load('minecraft.nbt')
        slots = blocks.NonNullList.withSize(1, items.ItemStack.EMPTY)
        slots.set(0, items.ItemStack(items.Item(identifier='sample:stored'), 999))
        first = nbt.CompoundTag()
        blocks.ContainerHelper.saveAllItems(first, slots)
        restored = blocks.NonNullList.withSize(1, items.ItemStack.EMPTY)
        blocks.ContainerHelper.loadAllItems(first, restored)
        self.assertEqual(restored.get(0).getCount(), 999)
        self.assertEqual(restored.get(0).getRestoredId(), 'sample:stored')
        second = nbt.CompoundTag()
        blocks.ContainerHelper.saveAllItems(second, restored)
        self.assertEqual(second.getList('Items')[0]['id'], 'sample:stored')
        self.assertEqual(second.getList('Items')[0]['count'], 999)

    def test_mismatch_bounds_and_serialization_gap_are_explicit(self):
        handler = SmallHandler()
        first, other = items.Item(identifier='sample:first'), items.Item(identifier='sample:other')
        handler.setStackInSlot(0, items.ItemStack(first, 1))
        other_stack = items.ItemStack(other, 1)
        self.assertIs(handler.insertItem(0, other_stack, False), other_stack)
        for slot in (-1, 2):
            with self.assertRaises(RuntimeError):
                handler.getStackInSlot(slot)
        self.assertEqual(handlers.ItemStackHandler().getSlotLimit(0), 99)
        with self.assertRaises(NotImplementedError):
            handler.serializeNBT(None)
        self.assertIs(capabilities.Capabilities.ItemHandler.ITEM.typeClass(), handlers.IItemHandler)
        self.assertIs(capabilities.Capabilities.ItemHandler.ENTITY.contextClass(), type(None))


if __name__ == '__main__':
    unittest.main()

import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
energy = pkg.load('neoforge.energy')
capabilities = pkg.load('neoforge.capabilities')
attachments = pkg.load('neoforge.attachment')
entities = pkg.load('minecraft.entity')
nbt = pkg.load('minecraft.nbt')
storage = pkg.load('minecraft.entity_storage')


class EnergyTests(unittest.TestCase):
    def test_limits_simulation_disabled_and_initial_clamp(self):
        value = energy.EnergyStorage(100, 20, 10, 90)
        self.assertEqual(value.receiveEnergy(30, True), 10)
        self.assertEqual(value.getEnergyStored(), 90)
        self.assertEqual(value.receiveEnergy(30, False), 10)
        self.assertEqual(value.extractEnergy(30, True), 10)
        self.assertEqual(value.getEnergyStored(), 100)
        self.assertEqual(value.extractEnergy(30, False), 10)
        self.assertEqual(value.receiveEnergy(-1, False), 0)
        disabled = energy.EnergyStorage(100, 0, 0, 200)
        self.assertEqual(disabled.getEnergyStored(), 100)
        self.assertEqual(disabled.receiveEnergy(10, False), 0)
        self.assertEqual(disabled.extractEnergy(10, False), 0)
        self.assertEqual(energy.EnergyStorage(100, 10).maxExtract, 10)

    def test_energy_attachment_nbt_snapshot_roundtrip(self):
        kind = attachments.AttachmentType.serializable(lambda: energy.EnergyStorage(100)).build()
        first = entities.Entity(identifier='sample:machine')
        second = entities.Entity(identifier='sample:machine')
        first._attachment_types = second._attachment_types = {'sample:energy': kind}
        first.getData(kind).receiveEnergy(37, False)
        second.load(storage.loads(storage.dumps(first)))
        self.assertEqual(second.getData(kind).getEnergyStored(), 37)
        with self.assertRaises(energy.IllegalArgumentException):
            second.getData(kind).deserializeNBT(None, nbt.CompoundTag())
        self.assertEqual(nbt.IntTag.valueOf(2147483648).getAsInt(), -2147483648)

    def test_int_tag_keeps_numeric_type_through_compound_and_snapshot(self):
        tag = nbt.CompoundTag()
        value = nbt.IntTag.valueOf(37)
        tag.put('energy', value)
        self.assertEqual(tag.getTagType('energy'), nbt.TagType.INT)
        self.assertEqual(tag.getInt('energy'), 37)
        self.assertEqual(tag.getDouble('energy'), 37.0)
        self.assertIs(tag.get('energy'), value)
        restored = storage.decode_tag(storage.encode_tag(tag))
        self.assertEqual(restored.getTagType('energy'), nbt.TagType.INT)
        self.assertIsInstance(restored.get('energy'), nbt.IntTag)
        self.assertEqual(restored.getInt('energy'), 37)
        self.assertEqual(restored.copy().getInt('energy'), 37)

    def test_energy_capability_constant_and_item_provider(self):
        items = pkg.load('minecraft.item')
        cap = capabilities.Capabilities.EnergyStorage.ITEM
        self.assertIs(cap.typeClass(), energy.IEnergyStorage)
        self.assertEqual(cap.name().toString(), 'neoforge:energy')
        registry = capabilities.EntityCapabilityRegistry()
        item = items.Item(identifier='sample:battery')
        store = energy.EnergyStorage(100)
        event = capabilities.RegisterCapabilitiesEvent(registry, object())
        event.registerItem(cap, capabilities.ICapabilityProvider(lambda stack, ctx: store), item)
        stack = registry.bind_stack(items.ItemStack(item))
        self.assertIs(stack.getCapability(cap), store)
        registry.close()
        self.assertIsNone(stack.getCapability(cap))


if __name__ == '__main__':
    unittest.main()

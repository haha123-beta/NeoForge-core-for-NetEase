import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
attachments = package.load('neoforge.attachment')
entities = package.load('minecraft.entity')
registries = package.load('neoforge.registries')


class AttachmentTests(unittest.TestCase):
    def test_entity_defaults_supplier_and_independent_storage(self):
        register = registries.DeferredRegister.create(registries.NEOFORGE_REGISTRIES.ATTACHMENT_TYPES, 'sample')
        holder = register.register('cache', lambda: attachments.AttachmentType.builder(list).build())
        register.freeze_and_register(registries.NEOFORGE_REGISTRIES.ATTACHMENT_TYPES)
        first, second = entities.Entity(), entities.Entity()
        self.assertFalse(first.hasData(holder))
        first.getData(holder).append(17)
        self.assertEqual(second.getData(holder), [])
        self.assertEqual(first.setData(holder, [21]), [17])
        self.assertEqual(first.removeData(holder), [21])
        self.assertFalse(first.hasData(holder))
        self.assertEqual(register.registry_key.registry(), 'neoforge:attachment_types')
        self.assertEqual(registries.NEOFORGE_REGISTRIES.FLUID_TYPES.name, 'neoforge:fluid_type')

    def test_serializer_survives_entity_snapshot(self):
        storage = package.load('minecraft.entity_storage')
        nbt = package.load('minecraft.nbt')
        observed = []
        class Serializer(attachments.IAttachmentSerializer):
            def write(self, value, provider):
                tag = nbt.CompoundTag()
                tag.putInt('value', value)
                return tag
            def read(self, holder, tag, provider):
                observed.append(holder)
                return tag.getInt('value')
        kind = attachments.AttachmentType.builder(lambda: 0).serialize(Serializer()).build()
        first, restored = entities.Entity(identifier='sample:entity'), entities.Entity(identifier='sample:entity')
        first._attachment_types = restored._attachment_types = {'sample:counter': kind}
        first.setData(kind, 42)
        restored.load(storage.loads(storage.dumps(first)))
        self.assertEqual(restored.getData(kind), 42)
        self.assertEqual(observed, [restored])
        self.assertTrue(restored.hasAttachments())
        bad = nbt.CompoundTag()
        bad.putCompound('missing:type', nbt.CompoundTag())
        with self.assertRaises(ValueError):
            restored.deserializeAttachments(None, bad)
        self.assertEqual(restored.getData(kind), 42)
        unregistered = entities.Entity()
        unregistered.setData(kind, 1)
        with self.assertRaises(ValueError):
            storage.dumps(unregistered)

    def test_nbt_serializable_holder_factory_and_reused_tag(self):
        nbt = package.load('minecraft.nbt')
        class Data(attachments.INBTSerializable):
            def __init__(self, holder):
                self.holder, self.count = holder, 0
            def serializeNBT(self, provider):
                tag = nbt.CompoundTag()
                tag.putInt('count', self.count)
                return tag
            def deserializeNBT(self, provider, tag):
                self.count = tag.getInt('count')
        class Factory(object):
            def apply(self, holder):
                return Data(holder)
        builder = attachments.AttachmentType.serializable(Factory())
        with self.assertRaises(attachments.IllegalStateException):
            builder.serialize(object())
        kind = builder.build()
        first, second = entities.Entity(identifier='sample:x'), entities.Entity(identifier='sample:x')
        first._attachment_types = second._attachment_types = {'sample:data': kind}
        first.getData(kind).count = 17
        self.assertIs(first.getData(kind).holder, first)
        tag = nbt.CompoundTag()
        first.save(tag)
        second.load(tag)
        self.assertEqual(second.getData(kind).count, 17)
        self.assertIs(second.getData(kind).holder, second)
        first.removeData(kind)
        first.save(tag)
        self.assertFalse(tag.contains(first.ATTACHMENTS_NBT_KEY))

    def test_failed_decode_does_not_publish_partial_attachment_values(self):
        nbt = package.load('minecraft.nbt')
        class Serializer(attachments.IAttachmentSerializer):
            def write(self, value, provider):
                return value
            def read(self, holder, tag, provider):
                if tag.getInt('value') < 0:
                    raise ValueError('bad attachment')
                return tag.getInt('value')
        a = attachments.AttachmentType.builder(lambda: 0).serialize(Serializer()).build()
        b = attachments.AttachmentType.builder(lambda: 0).serialize(Serializer()).build()
        entity = entities.Entity()
        entity._attachment_types = {'sample:a': a, 'sample:b': b}
        entity.setData(a, 1)
        entity.setData(b, 2)
        tag = nbt.CompoundTag()
        for name, number in [('sample:a', 7), ('sample:b', -1)]:
            value = nbt.CompoundTag()
            value.putInt('value', number)
            tag.putCompound(name, value)
        with self.assertRaises(ValueError):
            entity.deserializeAttachments(None, tag)
        self.assertEqual((entity.getData(a), entity.getData(b)), (1, 2))

    def test_entity_copy_respects_death_flag_and_custom_handler(self):
        nbt = package.load('minecraft.nbt')
        class Serializer(attachments.IAttachmentSerializer):
            def write(self, value, provider):
                tag = nbt.CompoundTag()
                tag.putList('values', list(value))
                return tag
            def read(self, holder, tag, provider):
                return list(tag.get('values'))
        normal = attachments.AttachmentType.builder(list).serialize(Serializer()).build()
        death = attachments.AttachmentType.builder(list).serialize(Serializer()).copyOnDeath().build()
        transient = attachments.AttachmentType.builder(list).build()
        first, second, third = entities.Entity(), entities.Entity(), entities.Entity()
        for kind in (normal, death, transient):
            first.setData(kind, [1])
        second.copyAttachmentsFrom(first, True)
        self.assertFalse(second.hasData(normal))
        self.assertFalse(second.hasData(transient))
        second.getData(death).append(2)
        self.assertEqual(first.getData(death), [1])
        third.copyAttachmentsFrom(first, False)
        self.assertEqual(third.getData(normal), [1])
        self.assertFalse(third.hasData(transient))
        calls = []
        class Handler(attachments.IAttachmentCopyHandler):
            def copy(self, value, holder, provider):
                calls.append(holder)
                return [9]
        custom = attachments.AttachmentType.builder(list).serialize(Serializer()).copyHandler(Handler()).build()
        first.setData(custom, [3])
        third.copyAttachmentsFrom(first, False)
        self.assertEqual(third.getData(custom), [9])
        self.assertEqual(calls, [third])

    def test_unsupported_persistence_is_explicit(self):
        builder = attachments.AttachmentType.builder(lambda: 0)
        with self.assertRaises(NotImplementedError):
            builder.serialize(object())
        with self.assertRaises(attachments.IllegalStateException):
            builder.copyOnDeath()
        with self.assertRaises(ValueError):
            entities.Entity().getData(attachments.AttachmentType.builder(lambda: None).build())


if __name__ == '__main__':
    unittest.main()

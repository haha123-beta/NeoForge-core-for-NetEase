# -*- coding: utf-8 -*-
"""NeoForge 1.21.1 entity attachments with explicit serializers; codecs and sync remain gaps."""
from __future__ import absolute_import
from java_stdlib._base import IllegalStateException


class AttachmentType(object):
    def __init__(self, factory, serializer=None, copy_on_death=False, copy_handler=None):
        self.copy_on_death = copy_on_death
        self.copy_handler = copy_handler
        self.serializer = serializer
        if not callable(factory) and not callable(getattr(factory, "get", None)) and not callable(getattr(factory, "apply", None)):
            raise ValueError("Attachment default requires a supplier")
        self.factory = factory

    @staticmethod
    def builder(factory):
        return AttachmentType.Builder(factory)

    @staticmethod
    def serializable(factory):
        class Serializer(IAttachmentSerializer):
            def read(self, holder, tag, provider):
                value = _default_value(factory, holder)
                value.deserializeNBT(provider, tag)
                return value

            def write(self, value, provider):
                return value.serializeNBT(provider)
        return AttachmentType.builder(factory).serialize(Serializer())

    class Builder(object):
        def __init__(self, factory):
            self.factory = factory
            self.serializer = None
            self.copy_on_death = False
            self.copy_handler = None

        def build(self):
            return AttachmentType(self.factory, self.serializer, self.copy_on_death, self.copy_handler)

        def serialize(self, serializer):
            if self.serializer is not None:
                raise IllegalStateException("Serializer already set")
            if not callable(getattr(serializer, "read", None)) or not callable(getattr(serializer, "write", None)):
                raise NotImplementedError("Expected IAttachmentSerializer; Codec overload is not integrated")
            self.serializer = serializer
            return self

        def copyOnDeath(self):
            if self.serializer is None:
                raise IllegalStateException("copyOnDeath requires a serializer")
            self.copy_on_death = True
            return self

        def copyHandler(self, handler):
            if self.serializer is None:
                raise IllegalStateException("copyHandler requires a serializer")
            if not callable(getattr(handler, "copy", None)):
                raise ValueError("Expected IAttachmentCopyHandler")
            self.copy_handler = handler
            return self

        def sync(self, *args):
            raise NotImplementedError("Attachment network synchronization is not integrated")


def _type(value):
    if not isinstance(value, AttachmentType):
        supplier = getattr(value, "get", None)
        if not callable(supplier):
            supplier = value if callable(value) else None
        if callable(supplier):
            value = supplier()
    if not isinstance(value, AttachmentType):
        raise ValueError("Expected AttachmentType or its supplier")
    return value


def _default_value(factory, holder):
    apply = getattr(factory, "apply", None)
    get = getattr(factory, "get", None)
    if callable(apply):
        value = apply(holder)
    elif callable(get):
        value = get()
    else:
        value = factory()
    if value is None:
        raise ValueError("Attachment default cannot be null")
    return value


class INBTSerializable(object):
    def serializeNBT(self, provider):
        raise NotImplementedError("Implement serializeNBT")

    def deserializeNBT(self, provider, tag):
        raise NotImplementedError("Implement deserializeNBT")


class IAttachmentCopyHandler(object):
    def copy(self, attachment, holder, provider):
        raise NotImplementedError("Implement attachment copy")


def copy_entity_attachments(source, target, is_death):
    provider = getattr(source, "_registry_provider", None)
    staged = {}
    for kind, value in source._attachment_data().items():
        if kind.serializer is None or (is_death and not kind.copy_on_death):
            continue
        if kind.copy_handler is not None:
            copied = kind.copy_handler.copy(value, target, provider)
        else:
            encoded = kind.serializer.write(value, provider)
            copied = None if encoded is None else kind.serializer.read(target, encoded, provider)
        if copied is not None:
            staged[kind] = copied
    target._attachment_data().update(staged)


class IAttachmentSerializer(object):
    def read(self, holder, tag, provider):
        raise NotImplementedError("Implement attachment read")

    def write(self, attachment, provider):
        raise NotImplementedError("Implement attachment write")


class AttachmentHolder(object):
    ATTACHMENTS_NBT_KEY = "neoforge:attachments"

    def hasAttachments(self):
        return bool(self._attachment_data())

    def _registered_attachment_types(self):
        explicit = getattr(self, "_attachment_types", None)
        if explicit is not None:
            return explicit
        loader = getattr(getattr(self, "_event_bus", None), "loader", None)
        return getattr(loader, "registries", {}).get("neoforge:attachment_types", {})

    def serializeAttachments(self, provider):
        from minecraft.nbt import CompoundTag
        registry = self._registered_attachment_types()
        result = CompoundTag()
        for kind, value in self._attachment_data().items():
            if kind.serializer is None:
                continue
            names = [name for name, registered in registry.items() if registered is kind]
            if len(names) != 1:
                raise ValueError("Serializable attachment needs one registered name")
            encoded = kind.serializer.write(value, provider)
            if encoded is not None:
                result.put(names[0], encoded)
        return result if result.getAllKeys() else None

    def deserializeAttachments(self, provider, tag):
        registry = self._registered_attachment_types()
        staged = {}
        for name in tag.getAllKeys():
            kind = registry.get(name)
            if kind is None or kind.serializer is None:
                raise ValueError("Unknown or nonserializable attachment: " + name)
            value = kind.serializer.read(self, tag.get(name), provider)
            if value is None:
                raise ValueError("Attachment read cannot return null")
            staged[kind] = value
        self._attachment_data().update(staged)

    def _attachment_data(self):
        if not hasattr(self, "_neocore_attachments"):
            self._neocore_attachments = {}
        return self._neocore_attachments

    def hasData(self, attachment_type):
        return _type(attachment_type) in self._attachment_data()

    def getData(self, attachment_type):
        kind = _type(attachment_type)
        data = self._attachment_data()
        if kind not in data:
            value = _default_value(kind.factory, self)
            data[kind] = value
        return data[kind]

    def setData(self, attachment_type, value):
        if value is None:
            raise ValueError("Use removeData to remove an attachment")
        kind = _type(attachment_type)
        data = self._attachment_data()
        previous = data.get(kind)
        data[kind] = value
        return previous

    def removeData(self, attachment_type):
        return self._attachment_data().pop(_type(attachment_type), None)


JAVA_MAP = {
    "net.neoforged.neoforge.attachment.IAttachmentCopyHandler": IAttachmentCopyHandler,
    "net.neoforged.neoforge.common.util.INBTSerializable": INBTSerializable,
    "net.neoforged.neoforge.attachment.IAttachmentSerializer": IAttachmentSerializer,
    "net.neoforged.neoforge.attachment.AttachmentType": AttachmentType,
    "net.neoforged.neoforge.attachment.AttachmentType$Builder": AttachmentType.Builder,
    "net.neoforged.neoforge.attachment.IAttachmentHolder": AttachmentHolder,
    "net.neoforged.neoforge.attachment.AttachmentHolder": AttachmentHolder,
}
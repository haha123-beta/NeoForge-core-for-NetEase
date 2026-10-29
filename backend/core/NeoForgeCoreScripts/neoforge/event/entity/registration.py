# -*- coding: utf-8 -*-
"""Default attribute registration and entity world lifecycle events."""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException
from minecraft.attributes import AttributeSupplier, Attributes
from neoforge.event.base import Event
from neoforge.event.entity.base import EntityEvent


class EntityAttributeCreationEvent(Event):
    def __init__(self, attributes=None):
        Event.__init__(self)
        self._attributes = attributes if attributes is not None else {}

    def put(self, entity_type, supplier):
        if not isinstance(supplier, AttributeSupplier):
            raise IllegalArgumentException("Expected built AttributeSupplier")
        if not supplier.hasAttribute(Attributes.MAX_HEALTH):
            raise IllegalArgumentException("Living entity needs MAX_HEALTH")
        if entity_type in self._attributes or entity_type._attributes is not None:
            raise IllegalArgumentException("Attributes already registered for entity")
        self._attributes[entity_type] = supplier
        entity_type._attributes = supplier


class EntityJoinLevelEvent(EntityEvent):
    def __init__(self, entity, level, loaded_from_disk=False):
        EntityEvent.__init__(self, entity)
        self._level = level
        self._loaded = bool(loaded_from_disk)

    def getLevel(self):
        return self._level

    def loadedFromDisk(self):
        return self._loaded


class EntityLeaveLevelEvent(EntityEvent):
    def __init__(self, entity, level):
        EntityEvent.__init__(self, entity)
        self._level = level

    def getLevel(self):
        return self._level

    def isCancelable(self):
        return False


JAVA_MAP = {
    "net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent": EntityAttributeCreationEvent,
    "net.neoforged.neoforge.event.entity.EntityJoinLevelEvent": EntityJoinLevelEvent,
    "net.neoforged.neoforge.event.entity.EntityLeaveLevelEvent": EntityLeaveLevelEvent,
}

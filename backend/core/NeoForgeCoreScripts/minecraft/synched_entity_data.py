# -*- coding: utf-8 -*-
"""Tracked entity data with explicit serializers and immutable wire snapshots."""
from __future__ import absolute_import
import copy
import math

try:
    _string_type = basestring
    _integer_types = (int, long)
except NameError:
    _string_type = str
    _integer_types = (int,)
from java_stdlib._base import IllegalArgumentException
from minecraft.nbt import CompoundTag
from minecraft.entity_storage import encode_tag, decode_tag


class EntityDataSerializer(object):
    def __init__(self, name, validator):
        self.name, self.validator = name, validator

    def copy(self, value):
        if not self.validator(value):
            raise IllegalArgumentException("Invalid entity data for " + self.name)
        return copy.deepcopy(value)


def _integer(value):
    return not isinstance(value, bool) and isinstance(value, _integer_types)


def _number(value):
    return isinstance(value, _integer_types + (float,)) and not isinstance(value, bool) and not (
        math.isnan(float(value)) or math.isinf(float(value)))


class EntityDataSerializers(object):
    BYTE = EntityDataSerializer("byte", lambda v: _integer(v) and -128 <= v <= 127)
    INT = EntityDataSerializer("int", _integer)
    FLOAT = EntityDataSerializer("float", _number)
    BOOLEAN = EntityDataSerializer("boolean", lambda v: isinstance(v, bool))
    STRING = EntityDataSerializer("string", lambda v: isinstance(v, _string_type))
    OPTIONAL_UUID = EntityDataSerializer("optional_uuid",
                                         lambda v: v is None or isinstance(v, _string_type))
    COMPOUND_TAG = EntityDataSerializer("compound", lambda v: isinstance(v, CompoundTag))


class EntityDataAccessor(object):
    def __init__(self, owner, identifier, serializer):
        self.owner, self._id, self._serializer = owner, identifier, serializer

    def getId(self):
        return self._id

    def getSerializer(self):
        return self._serializer


class SynchedEntityData(object):
    _defined = {}

    @staticmethod
    def defineId(owner, serializer):
        ids = []
        for base in owner.__mro__:
            ids.extend(SynchedEntityData._defined.get(base, []))
        identifier = max(ids) + 1 if ids else 0
        if identifier > 254:
            raise IllegalArgumentException("Too many tracked entity data fields")
        SynchedEntityData._defined.setdefault(owner, []).append(identifier)
        return EntityDataAccessor(owner, identifier, serializer)

    class Builder(object):
        def __init__(self, owner):
            self.owner = owner
            self.items = {}

        def define(self, accessor, value):
            identifier = accessor.getId()
            if identifier in self.items or not isinstance(self.owner, accessor.owner):
                raise IllegalArgumentException("Duplicate or foreign entity data accessor")
            value = accessor.getSerializer().copy(value)
            self.items[identifier] = (accessor, value)
            return self

        def build(self):
            return SynchedEntityData(self.owner, self.items)

    def __init__(self, owner, items):
        self.owner = owner
        self._items = dict((key, [accessor, accessor.getSerializer().copy(value)])
                           for key, (accessor, value) in items.items())
        self._dirty = set()

    def _item(self, accessor):
        item = self._items.get(accessor.getId())
        if item is None or item[0] is not accessor:
            raise IllegalArgumentException("Undefined entity data accessor")
        return item

    def get(self, accessor):
        return self._item(accessor)[1]

    def set(self, accessor, value, force=False):
        item = self._item(accessor)
        value = accessor.getSerializer().copy(value)
        if force or value != item[1]:
            item[1] = value
            self._dirty.add(accessor.getId())
            self.owner.onSyncedDataUpdated(accessor)

    def isDirty(self):
        return bool(self._dirty)

    def snapshot(self):
        return [{"id": key, "type": item[0].getSerializer().name,
                 "value": encode_tag(item[0].getSerializer().copy(item[1]))}
                for key, item in sorted(self._items.items())]

    def packDirty(self):
        if not self._dirty:
            return None
        rows = [row for row in self.snapshot() if row["id"] in self._dirty]
        self._dirty.clear()
        return rows

    def assignValues(self, rows):
        # Validate the complete packet before changing any field.
        updates = []
        for row in rows:
            item = self._items.get(row["id"])
            if item is None or item[0].getSerializer().name != row["type"]:
                raise IllegalArgumentException("Entity data schema mismatch")
            value = item[0].getSerializer().copy(decode_tag(row["value"]))
            updates.append((item, value))
        for item, value in updates:
            item[1] = value
            self.owner.onSyncedDataUpdated(item[0])


JAVA_MAP = {
    "net.minecraft.network.syncher.SynchedEntityData$Builder": SynchedEntityData.Builder,
    "net.minecraft.network.syncher.EntityDataAccessor": EntityDataAccessor,
    "net.minecraft.network.syncher.EntityDataSerializer": EntityDataSerializer,
    "net.minecraft.network.syncher.EntityDataSerializers": EntityDataSerializers,
    "net.minecraft.network.syncher.SynchedEntityData": SynchedEntityData,
}

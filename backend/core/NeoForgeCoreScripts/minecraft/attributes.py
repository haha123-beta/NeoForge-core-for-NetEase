# -*- coding: utf-8 -*-
"""Entity attributes and per-entity modifier state (1.21-style subset).

No engine or filesystem access. Synchronization and persistence belong to the
engine adapter; permanent modifiers are tracked but not written to disk here.
"""
from __future__ import absolute_import
import math
from java_stdlib._base import IllegalArgumentException
from java_stdlib.lang import java_to_string


def unwrap(attribute):
    if isinstance(attribute, Attribute):
        return attribute
    if hasattr(attribute, "value"):
        return attribute.value()
    return attribute.get()


class Attribute(object):
    def __init__(self, description_id, default_value):
        self._description_id = description_id
        self._default = float(default_value)
        self._syncable = False

    def value(self):
        return self

    def getDefaultValue(self):
        return self._default

    def getDescriptionId(self):
        return self._description_id

    def setSyncable(self, value):
        self._syncable = bool(value)
        return self

    def isClientSyncable(self):
        return self._syncable

    def sanitizeValue(self, value):
        return float(value)


class RangedAttribute(Attribute):
    def __init__(self, description_id, default_value, minimum, maximum):
        Attribute.__init__(self, description_id, default_value)
        self._min = float(minimum)
        self._max = float(maximum)
        if not self._min <= self._default <= self._max:
            raise IllegalArgumentException("Invalid attribute bounds/default")

    def getMinValue(self):
        return self._min

    def getMaxValue(self):
        return self._max

    def sanitizeValue(self, value):
        value = float(value)
        if math.isnan(value):
            return self._min
        return max(self._min, min(self._max, value))


class AttributeModifier(object):
    class Operation(object):
        ADD_VALUE = 0
        ADD_MULTIPLIED_BASE = 1
        ADD_MULTIPLIED_TOTAL = 2

    def __init__(self, identifier, amount, operation):
        if operation not in (0, 1, 2):
            raise IllegalArgumentException("Unknown attribute operation")
        self._id = java_to_string(identifier)
        self._amount = float(amount)
        self._operation = operation

    def id(self):
        return self._id

    def amount(self):
        return self._amount

    def operation(self):
        return self._operation


class AttributeInstance(object):
    def __init__(self, attribute, on_dirty=None):
        self._attribute = unwrap(attribute)
        self._base = self._attribute.getDefaultValue()
        self._modifiers = {}
        self._permanent = set()
        self._on_dirty = on_dirty

    def _changed(self):
        if self._on_dirty is not None:
            self._on_dirty(self)

    def getAttribute(self):
        return self._attribute

    def getBaseValue(self):
        return self._base

    def setBaseValue(self, value):
        self._base = float(value)
        self._changed()

    def getValue(self):
        modifiers = list(self._modifiers.values())
        added = self._base
        for modifier in modifiers:
            if modifier.operation() == 0:
                added += modifier.amount()
        value = added
        for modifier in modifiers:
            if modifier.operation() == 1:
                value += added * modifier.amount()
        for modifier in modifiers:
            if modifier.operation() == 2:
                value *= 1.0 + modifier.amount()
        return self._attribute.sanitizeValue(value)

    def getModifier(self, identifier):
        if isinstance(identifier, AttributeModifier):
            identifier = identifier.id()
        return self._modifiers.get(java_to_string(identifier))

    def hasModifier(self, identifier):
        return self.getModifier(identifier) is not None

    def getModifiers(self):
        return list(self._modifiers.values())

    def getPermanentModifiers(self):
        return [self._modifiers[key] for key in self._permanent]

    def _add(self, modifier, permanent):
        if self.hasModifier(modifier.id()):
            raise IllegalArgumentException("Duplicate attribute modifier: " + modifier.id())
        self._modifiers[modifier.id()] = modifier
        if permanent:
            self._permanent.add(modifier.id())
        self._changed()

    def addTransientModifier(self, modifier):
        self._add(modifier, False)

    def addPermanentModifier(self, modifier):
        self._add(modifier, True)

    def removeModifier(self, identifier):
        if isinstance(identifier, AttributeModifier):
            identifier = identifier.id()
        key = java_to_string(identifier)
        removed = self._modifiers.pop(key, None)
        self._permanent.discard(key)
        if removed is not None:
            self._changed()

    def removeModifiers(self):
        self._modifiers.clear()
        self._permanent.clear()
        self._changed()


class AttributeSupplier(object):
    def __init__(self, values):
        self._values = dict(values)

    @staticmethod
    def builder():
        return AttributeSupplier.Builder()

    def hasAttribute(self, attribute):
        return unwrap(attribute) in self._values

    def getBaseValue(self, attribute):
        attribute = unwrap(attribute)
        if attribute not in self._values:
            raise IllegalArgumentException("Attribute not registered on entity")
        return self._values[attribute]

    class Builder(object):
        def __init__(self):
            self._values = {}

        def add(self, attribute, value=None):
            attribute = unwrap(attribute)
            self._values[attribute] = (attribute.getDefaultValue()
                                       if value is None else float(value))
            return self

        def build(self):
            return AttributeSupplier(self._values)


class AttributeMap(object):
    def __init__(self, supplier, on_dirty=None):
        self._instances = {}
        for attribute, value in supplier._values.items():
            instance = AttributeInstance(attribute, on_dirty)
            instance._base = value
            self._instances[attribute] = instance

    def hasAttribute(self, attribute):
        return unwrap(attribute) in self._instances

    def getInstance(self, attribute):
        return self._instances.get(unwrap(attribute))

    def _require(self, attribute):
        result = self.getInstance(attribute)
        if result is None:
            raise IllegalArgumentException("Attribute not registered on entity")
        return result

    def getValue(self, attribute):
        return self._require(attribute).getValue()

    def getBaseValue(self, attribute):
        return self._require(attribute).getBaseValue()

    def hasModifier(self, attribute, identifier):
        instance = self.getInstance(attribute)
        return instance is not None and instance.hasModifier(identifier)

    def getModifierValue(self, attribute, identifier):
        modifier = self._require(attribute).getModifier(identifier)
        if modifier is None:
            raise IllegalArgumentException("Attribute modifier not present")
        return modifier.amount()


class Attributes(object):
    MAX_HEALTH = RangedAttribute("attribute.name.generic.max_health", 20, 1, 1024)
    FOLLOW_RANGE = RangedAttribute("attribute.name.generic.follow_range", 32, 0, 2048)
    MOVEMENT_SPEED = RangedAttribute("attribute.name.generic.movement_speed", 0.7, 0, 1024)
    FLYING_SPEED = RangedAttribute("attribute.name.generic.flying_speed", 0.4, 0, 1024)
    ATTACK_DAMAGE = RangedAttribute("attribute.name.generic.attack_damage", 2, 0, 2048)
    ATTACK_SPEED = RangedAttribute("attribute.name.generic.attack_speed", 4, 0, 1024)
    ATTACK_KNOCKBACK = RangedAttribute("attribute.name.generic.attack_knockback", 0, 0, 5)
    ARMOR = RangedAttribute("attribute.name.generic.armor", 0, 0, 30)
    ARMOR_TOUGHNESS = RangedAttribute("attribute.name.generic.armor_toughness", 0, 0, 20)
    KNOCKBACK_RESISTANCE = RangedAttribute("attribute.name.generic.knockback_resistance", 0, 0, 1)


JAVA_MAP = {}
for _class in (Attribute, RangedAttribute, AttributeModifier, AttributeInstance,
               AttributeSupplier, AttributeMap, Attributes):
    JAVA_MAP["net.minecraft.world.entity.ai.attributes." + _class.__name__] = _class
JAVA_MAP["net.minecraft.world.entity.ai.attributes.AttributeModifier$Operation"] = AttributeModifier.Operation
JAVA_MAP["net.minecraft.world.entity.ai.attributes.AttributeSupplier$Builder"] = AttributeSupplier.Builder

# -*- coding: utf-8 -*-
"""Damage sources and event-aware local combat; native worlds delegate to SDK Hurt."""
from __future__ import absolute_import
import math
from minecraft.attributes import Attributes
from neoforge.event.entity.living import (
    LivingIncomingDamageEvent, LivingHurtEvent, LivingHealEvent, LivingDeathEvent)


class DamageSource(object):
    def __init__(self, damage_type="generic", direct_entity=None, causing_entity=None):
        self._type = damage_type
        self._direct = direct_entity
        self._entity = direct_entity if causing_entity is None else causing_entity

    def getEntity(self):
        return self._entity

    def getDirectEntity(self):
        return self._direct

    def getMsgId(self):
        return self._type

    def isIndirect(self):
        return self._direct is not self._entity

    def getSourcePosition(self):
        return self._direct.position() if self._direct is not None else None


class DamageSources(object):
    def generic(self):
        return DamageSource("generic")

    def mobAttack(self, mob):
        return DamageSource("mob", mob)

    def playerAttack(self, player):
        return DamageSource("player", player)

    def arrow(self, projectile, owner):
        return DamageSource("arrow", projectile, owner)

    def fall(self):
        return DamageSource("fall")

    def magic(self):
        return DamageSource("magic")


def post(entity, event):
    bus = getattr(entity, "_event_bus", None)
    if bus is not None:
        bus.post(event)
    return event


def valid_amount(amount):
    value = float(amount)
    return value if value > 0 and not math.isnan(value) and not math.isinf(value) else 0.0


def incoming(entity, source, amount):
    event = post(entity, LivingIncomingDamageEvent(entity, source, amount))
    return 0.0 if event.isCanceled() else valid_amount(event.getAmount())


def final_damage(entity, source, amount):
    event = post(entity, LivingHurtEvent(entity, source, amount))
    return 0.0 if event.isCanceled() else valid_amount(event.getAmount())


def death_allowed(entity, source):
    return not post(entity, LivingDeathEvent(entity, source)).isCanceled()


def heal(entity, amount):
    if not entity.isAlive() or valid_amount(amount) == 0:
        return
    event = post(entity, LivingHealEvent(entity, amount))
    if not event.isCanceled():
        entity.setHealth(entity.getHealth() + valid_amount(event.getAmount()))


def hurt(entity, source, amount):
    amount = valid_amount(amount)
    if not entity.isAlive() or amount == 0:
        return False
    access = entity._level_access
    if access is not None and hasattr(access, "hurtEntity") and entity.getId() is not None:
        return access.hurtEntity(entity, source, amount)
    amount = incoming(entity, source, amount)
    if not amount:
        return False
    # Local approximation for armor/toughness; native SDK performs its own reduction.
    armor = entity.getAttributeValue(Attributes.ARMOR)
    toughness = entity.getAttributeValue(Attributes.ARMOR_TOUGHNESS)
    reduction = min(20.0, max(armor * 0.2, armor - amount / (2.0 + toughness / 4.0)))
    if getattr(source, "_type", None) not in ("fall", "magic", "out_of_world"):
        amount *= 1.0 - reduction / 25.0
    amount = final_damage(entity, source, amount)
    if not amount:
        return False
    remaining = entity.getHealth() - amount
    if remaining <= 0 and not death_allowed(entity, source):
        remaining = max(1.0, entity.getHealth())
    entity.damage_taken.append((amount, source))
    entity.lastHurtBy = source
    attacker = source.getEntity() if hasattr(source, "getEntity") else None
    entity._last_hurt_by_mob = attacker
    entity.setHealth(remaining)
    if remaining <= 0:
        entity.die(source)
    return True


JAVA_MAP = {
    "net.minecraft.world.damagesource.DamageSource": DamageSource,
    "net.minecraft.world.damagesource.DamageSources": DamageSources,
}

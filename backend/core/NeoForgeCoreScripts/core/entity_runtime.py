# -*- coding: utf-8 -*-
"""Explicit server-side entity lifecycle bridge.

The caller supplies a Level and buses, then drives tick() from the server tick.
The optional modsdk_entity system drives this runtime with a real entity adapter.
"""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException
from minecraft.entity import LivingEntity, EntityType
from minecraft.entity_storage import loads
from neoforge.event.entity.registration import (
    EntityAttributeCreationEvent, EntityJoinLevelEvent, EntityLeaveLevelEvent)


class EntityRuntime(object):
    def __init__(self, level, game_bus):
        if level.isClientSide():
            raise IllegalArgumentException("EntityRuntime requires a server level")
        self.level = level
        self.game_bus = game_bus
        self.level._event_bus = game_bus
        self._entities = {}
        self._attributes_initialized = False
        self._closed = False
        self.cleanup_errors = []

    def initialize(self, mod_bus):
        if self._closed:
            raise IllegalArgumentException("Entity runtime is closed")
        if self._attributes_initialized:
            raise IllegalArgumentException("Entity runtime already initialized")
        mod_bus.freeze_registries()
        mod_bus.post(EntityAttributeCreationEvent())
        self._attributes_initialized = True

    def spawn(self, entity_type, position):
        if self._closed:
            raise IllegalArgumentException("Entity runtime is closed")
        if not self._attributes_initialized:
            raise IllegalArgumentException("Initialize registries and attributes first")
        entity = entity_type.create(self.level)
        if entity is None:
            return None
        if isinstance(entity, LivingEntity) and entity_type._attributes is None:
            raise IllegalArgumentException("Missing registered living attributes")
        if hasattr(position, "getX"):
            entity.setPos(position.getX(), position.getY(), position.getZ())
        else:
            entity.setPos(position)
        entity._event_bus = self.game_bus
        event = EntityJoinLevelEvent(entity, self.level)
        self.game_bus.post(event)
        if event.isCanceled() or entity.isRemoved():
            return None
        entity_id = self.level.addFreshEntity(entity)
        # ILevelAccess returns an ID, not a Java boolean. None/False signal failure.
        if entity_id is None or entity_id is False:
            return None
        self._entities[entity_id] = entity
        return entity

    def restore(self, snapshot, engine_id=None):
        if self._closed:
            raise IllegalArgumentException("Entity runtime is closed")
        if not self._attributes_initialized:
            raise IllegalArgumentException("Initialize registries and attributes first")
        tag = loads(snapshot)
        kind = EntityType.of(tag.getString("id"))
        entity = kind.create(self.level)
        if entity is None:
            return None
        if isinstance(entity, LivingEntity) and kind._attributes is None:
            raise IllegalArgumentException("Missing registered living attributes")
        entity._event_bus = self.game_bus
        entity.load(tag)
        for existing in self._entities.values():
            if existing.getUUID() == entity.getUUID():
                raise IllegalArgumentException("Entity UUID already loaded")
        entity._event_bus = self.game_bus
        event = EntityJoinLevelEvent(entity, self.level)
        self.game_bus.post(event)
        if event.isCanceled() or entity.isRemoved():
            return None
        if engine_id is None:
            entity_id = self.level.addFreshEntity(entity)
        else:
            entity_id = self.level.getAccess().bindEntity(entity, engine_id)
        if entity_id is None or entity_id is False:
            return None
        self._entities[entity_id] = entity
        return entity

    def remove(self, entity):
        entity_id = entity.getId()
        if self._entities.get(entity_id) is not entity:
            return False
        entity.discard()
        self._forget(entity_id, entity)
        return True

    def _forget(self, entity_id, entity):
        if self._entities.get(entity_id) is entity:
            del self._entities[entity_id]
            self.game_bus.post(EntityLeaveLevelEvent(entity, self.level))

    def tick(self):
        if self._closed:
            return
        # Snapshot: entities spawned during callbacks start ticking next frame.
        for entity_id, entity in list(self._entities.items()):
            if self._entities.get(entity_id) is not entity:
                continue
            access = self.level.getAccess()
            active = getattr(access, "isEntityActive", lambda value: True)
            if not entity.isRemoved() and active(entity):
                entity.tick()
            if entity.isRemoved():
                self._forget(entity_id, entity)

    def collectRemoved(self):
        for entity_id, entity in list(self._entities.items()):
            if entity.isRemoved():
                self._forget(entity_id, entity)

    def close(self):
        self._closed = True
        errors = []
        for entity in list(self._entities.values()):
            try:
                self.remove(entity)
            except Exception as error:
                errors.append("entity " + str(entity.getId()) + ": " + str(error))
        self.cleanup_errors.extend(errors)
        if errors:
            raise RuntimeError("; ".join(errors))

# -*- coding: utf-8 -*-
"""ModSDK entity-only LevelAccess. SDK objects are injected, never imported.

References: refs/mcn-docs/site/interface-equivalent Chinese paths:
world/entity management: CreateEngineEntityByTypeStr, DestroyEntity;
entity/attributes: GetFootPos, SetFootPos, GetRot, SetRot, GetAttrValue,
SetAttrMaxValue, SetAttrValue. Unsupported block/world calls stay explicit.
"""
from __future__ import absolute_import
import math
from java_stdlib._base import IllegalArgumentException, IllegalStateException
from minecraft.core import Vec3
from minecraft.entity_storage import dumps
from minecraft.combat import DamageSource, incoming, final_damage, death_allowed
from minecraft.entity import LivingEntity
from minecraft.level_access import ILevelAccess


class EngineBridgeError(IllegalStateException):
    pass


class ModSdkEntityAccess(ILevelAccess):
    name = "modsdk-entity"

    def _unsupported(self, method_name, *args):
        self.unsupported.append((method_name, args))
        raise EngineBridgeError("Unimplemented ModSDK world operation: " + str(method_name))

    def __init__(self, server_system, server_api, dimension_id=0, world_access=None):
        ILevelAccess.__init__(self)
        self.world_access = world_access
        self.system = server_system
        self.api = server_api
        self.dimension_id = int(dimension_id)
        self.factory = server_api.GetEngineCompFactory()
        self.health_type = server_api.GetMinecraftEnum().AttrType.HEALTH
        self._next_id = 0
        self._entities = {}
        self._engine_ids = {}
        self._local_ids = {}
        self._ack = {}
        self._active = set()
        self._pending_remove = set()
        self.errors = []
        self._closed = False
        self._damage_sources = {}
        self._damage_serial = 0

    def getBlockState(self, pos):
        if self._closed:
            raise EngineBridgeError("Entity/world access is closed")
        if self.world_access is None:
            return self._unsupported("getBlockState", pos)
        return self.world_access.getBlockState(pos)

    def setBlock(self, pos, state, flags=3):
        if self._closed:
            raise EngineBridgeError("Entity/world access is closed")
        if self.world_access is None:
            return self._unsupported("setBlock", pos, state, flags)
        return self.world_access.setBlock(pos, state, flags)

    def hurtEntity(self, entity, source, amount):
        engine_id = self.getEngineId(entity)
        if engine_id is None or not self.isEntityActive(entity):
            return False
        # Push pending script health edits before asking the engine to apply damage.
        self._push(entity)
        causing = source.getEntity() if hasattr(source, "getEntity") else None
        direct = source.getDirectEntity() if hasattr(source, "getDirectEntity") else None
        attacker = self.getEngineId(causing) if causing is not None else None
        projectile = self.getEngineId(direct) if direct is not None and direct is not causing else None
        causes = {"mob": "entity_attack", "player": "entity_attack",
                  "arrow": "projectile", "fall": "fall", "magic": "magic"}
        cause = causes.get(getattr(source, "_type", ""), "custom")
        self._damage_serial += 1
        tag = "neocore.damage." + str(self._damage_serial)
        self._damage_sources[tag] = source
        try:
            return bool(self.factory.CreateHurt(engine_id).Hurt(
                float(amount), cause, attacker, projectile, attacker is not None, tag))
        finally:
            self._damage_sources.pop(tag, None)

    def onDamage(self, args, final=False):
        entity = self.getByEngineId(args.get("entityId"))
        if not isinstance(entity, LivingEntity):
            return
        source = self._damage_sources.get(args.get("customTag"))
        if source is None:
            attacker = self.getByEngineId(args.get("srcId"))
            projectile = self.getByEngineId(args.get("projectileId"))
            source = DamageSource(args.get("cause", "generic"),
                                  projectile or attacker, attacker)
        amount = args.get("damage", 0)
        if final:
            amount = final_damage(entity, source, amount)
            health = self.factory.CreateAttr(args["entityId"]).GetAttrValue(self.health_type)
            if health is not None and amount >= health and amount > 0:
                if not death_allowed(entity, source):
                    amount = 0.0
            if amount > 0:
                entity.damage_taken.append((amount, source))
                entity.lastHurtBy = source
                entity.setLastHurtByMob(source.getEntity())
        else:
            amount = incoming(entity, source, amount)
        args["damage"] = amount
        if amount == 0 and not final:
            args["knock"] = False
            args["ignite"] = False

    def moveEntityTo(self, entity, position, speed, callback):
        engine_id = self.getEngineId(entity)
        if self._closed or engine_id is None or entity.isRemoved() or not self.isEntityActive(entity):
            return False
        position, speed = tuple(position), float(speed)
        if len(position) != 3 or speed <= 0 or not self._finite(position + (speed,)) or not callable(callback):
            raise IllegalArgumentException("Invalid navigation target/speed/callback")
        def completed(callback_id, result):
            if (not self._closed and callback_id == engine_id
                    and self.getByEngineId(engine_id) is entity and self.isEntityActive(entity)):
                callback(result)
        # SetMoveSetting has no return value; only its callback reports success.
        self.factory.CreateMoveTo(engine_id).SetMoveSetting(tuple(position),
                                                           float(speed), 200, completed)
        return True

    def stopEntityNavigation(self, entity):
        engine_id = self.getEngineId(entity)
        if not self._closed and engine_id is not None and not entity.isRemoved() and self.isEntityActive(entity):
            # SDK has no documented stop call: supersede with the current foot position.
            pos = (entity.getX(), entity.getY(), entity.getZ())
            self.factory.CreateMoveTo(engine_id).SetMoveSetting(
                pos, 1.0, 200, lambda callback_id, result: None)

    def isClientSide(self):
        return False

    def getEntity(self, entity_id):
        return self._entities.get(int(entity_id))

    def getEntities(self):
        return list(self._entities.values())

    def getEngineId(self, entity):
        return self._engine_ids.get(entity.getId())

    def getByEngineId(self, engine_id):
        return self._entities.get(self._local_ids.get(engine_id))

    def isEntityActive(self, entity):
        return entity.getId() in self._active

    def _error(self, operation, engine_id, error):
        self.errors.append((operation, engine_id, str(error)))
        del self.errors[:-100]

    @staticmethod
    def _finite(values):
        return all(not math.isnan(float(value)) and not math.isinf(float(value))
                   for value in values)

    @staticmethod
    def _state(entity):
        state = {
            "position": (entity.getX(), entity.getY(), entity.getZ()),
            "rotation": (entity.getXRot(), entity.getYRot()),
        }
        if isinstance(entity, LivingEntity):
            state["maximum"] = entity.getMaxHealth()
            state["health"] = entity.getHealth()
        return state

    def _require(self, result, operation):
        if not result:
            raise EngineBridgeError("ModSDK rejected " + operation)

    SAVE_KEY = "neocore.entity.v1"

    def saveEntity(self, entity):
        engine_id = self.getEngineId(entity)
        if engine_id is None or not self.isEntityActive(entity):
            return False
        self._push(entity)
        data = dumps(entity)
        return bool(self.factory.CreateExtraData(engine_id).SetExtraData(
            self.SAVE_KEY, data, True))

    def readEntitySave(self, engine_id):
        return self.factory.CreateExtraData(engine_id).GetExtraData(self.SAVE_KEY)

    def bindEntity(self, entity, engine_id):
        if self._closed or entity.getId() is not None or entity.isRemoved():
            raise IllegalArgumentException("Cannot bind this entity")
        if engine_id in self._local_ids:
            raise IllegalArgumentException("Engine entity already bound")
        pos = self.factory.CreatePos(engine_id).GetFootPos()
        rot = self.factory.CreateRot(engine_id).GetRot()
        health = None
        if isinstance(entity, LivingEntity):
            health = self.factory.CreateAttr(engine_id).GetAttrValue(self.health_type)
            if health is None or health <= 0 or not self._finite((health,)):
                raise EngineBridgeError("Saved entity is unavailable or dead")
        if pos is None or rot is None:
            raise EngineBridgeError("Saved entity is unloaded")
        if len(pos) != 3 or len(rot) != 2 or not self._finite(tuple(pos) + tuple(rot)):
            raise EngineBridgeError("Invalid saved engine transform")
        # The engine owns current motion and damage, even if its save is newer than ours.
        entity.setPos(*pos)
        entity.setXRot(rot[0])
        entity.setYRot(rot[1])
        if health is not None:
            entity.setHealth(health)
        self._next_id += 1
        local_id = self._next_id
        entity._id = local_id
        entity.setLevelAccess(self)
        self._entities[local_id] = entity
        self._engine_ids[local_id] = engine_id
        self._local_ids[engine_id] = local_id
        self._ack[local_id] = self._state(entity)
        self._active.add(local_id)
        return local_id

    def addEntity(self, entity):
        if self._closed:
            raise IllegalStateException("Entity adapter is closed")
        if entity is None or entity.isRemoved():
            raise IllegalArgumentException("Cannot spawn a missing/removed entity")
        if entity.getId() is not None:
            raise IllegalArgumentException("Entity already has a world ID")
        state = self._state(entity)
        if not self._finite(state["position"] + state["rotation"]):
            raise IllegalArgumentException("Entity coordinates must be finite")
        engine_id = self.system.CreateEngineEntityByTypeStr(
            entity.getIdentifier(), state["position"], state["rotation"],
            self.dimension_id)
        if engine_id is None or engine_id == "" or engine_id == "-1":
            return None
        self._next_id += 1
        local_id = self._next_id
        entity._id = local_id
        entity.setLevelAccess(self)
        self._entities[local_id] = entity
        self._engine_ids[local_id] = engine_id
        self._local_ids[engine_id] = local_id
        self._ack[local_id] = {
            "position": state["position"], "rotation": state["rotation"]}
        self._active.add(local_id)
        try:
            self._push(entity)
            if self.getByEngineId(engine_id) is not entity:
                raise EngineBridgeError("Entity disappeared during initialization")
        except Exception:
            # Failed initialization must not produce an apparently usable entity.
            # A failed rollback remains tracked and will be retried by syncFromEngine.
            self._pending_remove.add(local_id)
            try:
                self.removeEntity(entity)
            except Exception:
                pass
            raise
        return local_id

    def _detach(self, engine_id):
        local_id = self._local_ids.pop(engine_id, None)
        if local_id is None:
            return None
        entity = self._entities.pop(local_id)
        self._engine_ids.pop(local_id, None)
        self._ack.pop(local_id, None)
        self._active.discard(local_id)
        self._pending_remove.discard(local_id)
        entity._removed = True
        for name in ("goalSelector", "targetSelector"):
            selector = getattr(entity, name, None)
            if selector is not None:
                selector.stopAll()
        return entity

    def onEngineRemoved(self, engine_id):
        # Never destroy the SDK entity again in response to its removal event.
        return self._detach(engine_id)

    def removeEntity(self, entity):
        local_id = entity.getId()
        if self._entities.get(local_id) is not entity:
            return False
        engine_id = self._engine_ids[local_id]
        self._pending_remove.add(local_id)
        result = self.system.DestroyEntity(engine_id)
        # DestroyEntity can synchronously deliver EntityRemoveEvent.
        if self.getByEngineId(engine_id) is not entity:
            return True
        if not result:
            self._active.discard(local_id)
            raise EngineBridgeError("ModSDK rejected DestroyEntity: " + str(engine_id))
        self._detach(engine_id)
        return True

    def _push(self, entity):
        local_id = entity.getId()
        engine_id = self._engine_ids.get(local_id)
        if engine_id is None:
            return
        state = self._state(entity)
        ack = self._ack[local_id]
        if state["position"] != ack.get("position"):
            if not self._finite(state["position"]):
                raise EngineBridgeError("Non-finite position")
            self._require(self.factory.CreatePos(engine_id).SetFootPos(
                state["position"]), "SetFootPos")
            ack["position"] = state["position"]
        if self._entities.get(local_id) is not entity:
            return
        if state["rotation"] != ack.get("rotation"):
            if not self._finite(state["rotation"]):
                raise EngineBridgeError("Non-finite rotation")
            self._require(self.factory.CreateRot(engine_id).SetRot(
                state["rotation"]), "SetRot")
            ack["rotation"] = state["rotation"]
        if self._entities.get(local_id) is not entity or "health" not in state:
            return
        if not self._finite((state["maximum"], state["health"])):
            raise EngineBridgeError("Non-finite health")
        attr = self.factory.CreateAttr(engine_id)
        if state["maximum"] != ack.get("maximum"):
            self._require(attr.SetAttrMaxValue(self.health_type, state["maximum"]),
                          "SetAttrMaxValue")
            ack["maximum"] = state["maximum"]
        if self._entities.get(local_id) is not entity:
            return
        if state["health"] != ack.get("health"):
            self._require(attr.SetAttrValue(self.health_type, state["health"], 0),
                          "SetAttrValue")
            ack["health"] = state["health"]

    def syncToEngine(self):
        for local_id, entity in list(self._entities.items()):
            if local_id not in self._active or local_id in self._pending_remove:
                continue
            try:
                self._push(entity)
            except Exception as error:
                self._active.discard(local_id)
                self._error("push", self._engine_ids.get(local_id), error)

    def syncFromEngine(self):
        for local_id, entity in list(self._entities.items()):
            if local_id in self._pending_remove:
                try:
                    self.removeEntity(entity)
                except Exception as error:
                    self._error("remove", self._engine_ids.get(local_id), error)
                continue
            engine_id = self._engine_ids.get(local_id)
            try:
                # Local edits since the last snapshot win for that field only.
                # Commit them before reading, so an external heal/hurt or teleport
                # is not overwritten merely because Python held yesterday's value.
                self._push(entity)
                if self._entities.get(local_id) is not entity:
                    continue
                pos = self.factory.CreatePos(engine_id).GetFootPos()
                rot = self.factory.CreateRot(engine_id).GetRot()
                health = None
                if isinstance(entity, LivingEntity):
                    health = self.factory.CreateAttr(engine_id).GetAttrValue(self.health_type)
                if pos is None or rot is None or (
                        isinstance(entity, LivingEntity) and health is None):
                    # Chunk unload is not a death event. Keep identity and pause AI.
                    self._active.discard(local_id)
                    continue
                if len(pos) != 3 or len(rot) != 2 or not self._finite(tuple(pos) + tuple(rot)):
                    raise EngineBridgeError("Invalid SDK transform")
                if health is not None and not self._finite((health,)):
                    raise EngineBridgeError("Invalid SDK health")
                if self._entities.get(local_id) is not entity:
                    continue
                entity._position = Vec3(*pos)
                entity._x_rot, entity._y_rot = rot
                if health is not None:
                    entity.setHealth(health)
                self._ack[local_id] = self._state(entity)
                self._active.add(local_id)
            except Exception as error:
                self._active.discard(local_id)
                self._error("pull", engine_id, error)

    def close(self):
        self._closed = True
        world_success = True
        if self.world_access is not None:
            try:
                self.world_access.close()
            except Exception as error:
                world_success = False
                self._error("world-close", None, error)
        for entity in list(self._entities.values()):
            try:
                self.removeEntity(entity)
            except Exception as error:
                self._error("close", self.getEngineId(entity), error)
        return not self._entities and world_success

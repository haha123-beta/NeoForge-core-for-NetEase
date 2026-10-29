# -*- coding: utf-8 -*-
"""Server-only ModSDK system factory; safe to import without the game SDK."""
from __future__ import absolute_import
from __future__ import print_function
from java_stdlib._base import IllegalArgumentException
from minecraft.level import Level
from minecraft.modsdk_entity_access import ModSdkEntityAccess
from core.entity_runtime import EntityRuntime


class EntityBridgeController(object):
    """One explicitly configured runtime per dimension, sharing one server system."""
    def __init__(self, system, server_api):
        self.system = system
        self.api = server_api
        self._runtimes = {}
        self._accesses = {}
        self._tick_units = 0
        self._closed = False
        self.cleanup_errors = []

    def createRuntime(self, dimension_id, mod_bus, game_bus, world_mappings=None, world_write_policy=None):
        if self._closed:
            raise IllegalArgumentException("Entity bridge is closed")
        dimension_id = int(dimension_id)
        if dimension_id in self._runtimes:
            raise IllegalArgumentException("A runtime already owns this dimension")
        world_access = None
        if world_mappings is not None:
            from minecraft.modsdk_world_access import ModSdkWorldAccess
            world_access = ModSdkWorldAccess(self.api, dimension_id, world_mappings, world_write_policy)
        elif world_write_policy is not None:
            raise IllegalArgumentException("World write policy requires mappings")
        access = ModSdkEntityAccess(self.system, self.api, dimension_id, world_access)
        level = Level.wrap(access)
        names = {0: "minecraft:overworld", 1: "minecraft:the_nether",
                 2: "minecraft:the_end"}
        level.setDimension(names.get(dimension_id, "netease:" + str(dimension_id)))
        runtime = EntityRuntime(level, game_bus)
        try:
            runtime.initialize(mod_bus)
        except Exception:
            Level._wrappers.pop(id(access), None)
            if world_access is not None:
                world_access.close()
            raise
        self._accesses[dimension_id] = access
        self._runtimes[dimension_id] = runtime
        return runtime

    def restoreEntity(self, engine_id, dimension_id=0):
        access = self._accesses.get(int(dimension_id))
        if access is None:
            return None
        existing = access.getByEngineId(engine_id)
        if existing is not None:
            return existing
        snapshot = access.readEntitySave(engine_id)
        if snapshot is None:
            return None
        return self._runtimes[int(dimension_id)].restore(snapshot, engine_id)

    def checkpoint(self):
        success = True
        for access in list(self._accesses.values()):
            access.syncFromEngine()
            for entity in access.getEntities():
                if not access.isEntityActive(entity):
                    success = False
                    continue
                try:
                    if not access.saveEntity(entity):
                        success = False
                except Exception as error:
                    success = False
                    access._error("save", access.getEngineId(entity), error)
        return success

    def getRuntime(self, dimension_id=0):
        return self._runtimes.get(int(dimension_id))

    def onTick(self, args=None):
        if self._closed:
            return
        # Integer accumulator: 30 SDK ticks yield exactly 20 logic ticks.
        self._tick_units += 20
        run_logic = self._tick_units >= 30
        if run_logic:
            self._tick_units -= 30
        for dimension_id, runtime in list(self._runtimes.items()):
            access = self._accesses[dimension_id]
            access.syncFromEngine()
            runtime.collectRemoved()
            if run_logic:
                runtime.tick()
            access.syncToEngine()
            runtime.collectRemoved()

    def onDamage(self, args):
        if self._closed:
            return
        for access in list(self._accesses.values()):
            access.onDamage(args)

    def onActuallyHurt(self, args):
        if self._closed:
            return
        for access in list(self._accesses.values()):
            access.onDamage(args, final=True)

    def onEntityRemoved(self, args):
        engine_id = args.get("id")
        if engine_id is None:
            return
        for dimension_id, access in list(self._accesses.items()):
            if access.onEngineRemoved(engine_id) is not None:
                self._runtimes[dimension_id].collectRemoved()

    def close(self):
        self._closed = True
        success = True
        for dimension_id, runtime in list(self._runtimes.items()):
            access = self._accesses[dimension_id]
            runtime._closed = True
            try:
                if not access.close():
                    success = False
                    self.cleanup_errors.append("dimension " + str(dimension_id) + ": entity removal incomplete")
            except Exception as error:
                success = False
                self.cleanup_errors.append("dimension " + str(dimension_id) + " access: " + str(error))
            try:
                runtime.collectRemoved()
            except Exception as error:
                success = False
                self.cleanup_errors.append("dimension " + str(dimension_id) + " runtime: " + str(error))
            # Release only this controller's wrappers, never another world.
            try:
                if not access.getEntities() and not runtime._entities:
                    Level._wrappers.pop(id(access), None)
                    del self._runtimes[dimension_id]
                    del self._accesses[dimension_id]
            except Exception as error:
                success = False
                self.cleanup_errors.append("dimension " + str(dimension_id) + " ownership: " + str(error))
        return success


def install_server_system(server_api):
    """Install a dynamically SDK-derived class for RegisterSystem's dotted path."""
    base = server_api.GetServerSystemCls()

    class _EntityBridgeSystem(base):
        def __init__(self, namespace, system_name):
            base.__init__(self, namespace, system_name)
            self.entityBridge = EntityBridgeController(self, server_api)
            self._engine_namespace = server_api.GetEngineNamespace()
            self._engine_system = server_api.GetEngineSystemName()
            self._entity_events = (
                ("OnScriptTickServer", self._on_entity_tick),
                ("EntityRemoveEvent", self._on_entity_removed),
                ("DamageEvent", self._on_damage),
                ("ActuallyHurtServerEvent", self._on_actually_hurt),
            )
            self._listened = []
            try:
                for name, callback in self._entity_events:
                    self.ListenForEvent(self._engine_namespace, self._engine_system,
                                        name, self, callback)
                    self._listened.append((name, callback))
            except Exception as error:
                self.entityBridge.close()
                try:
                    self._unlisten()
                except Exception as cleanup_error:
                    raise RuntimeError("Entity system startup failed: " + str(error) +
                                       "; cleanup failed: " + str(cleanup_error))
                raise

        def _unlisten(self):
            pending, errors = [], []
            for name, callback in list(self._listened):
                try:
                    self.UnListenForEvent(self._engine_namespace, self._engine_system,
                                          name, self, callback)
                except Exception as error:
                    pending.append((name, callback))
                    errors.append("listener " + name + ": " + str(error))
            self._listened = pending
            self.entityBridge.cleanup_errors.extend(errors)
            if errors:
                raise RuntimeError("; ".join(errors))

        def _on_entity_tick(self, args=None):
            self.entityBridge.onTick(args)

        def _on_damage(self, args):
            self.entityBridge.onDamage(args)

        def _on_actually_hurt(self, args):
            self.entityBridge.onActuallyHurt(args)

        def _on_entity_removed(self, args):
            self.entityBridge.onEntityRemoved(args)

        def createEntityRuntime(self, dimension_id, mod_bus, game_bus):
            return self.entityBridge.createRuntime(dimension_id, mod_bus, game_bus)

        def getEntityRuntime(self, dimension_id=0):
            return self.entityBridge.getRuntime(dimension_id)

        def Destroy(self):
            try:
                if not self.entityBridge.close():
                    print("[NeoForge] Some entity deletions failed; inspect bridge access.errors")
            finally:
                self._unlisten()

    globals()["EntityBridgeSystem"] = _EntityBridgeSystem
    return _EntityBridgeSystem

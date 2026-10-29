# -*- coding: utf-8 -*-
"""SDK contract tests; no game installation or fake passing engine calls."""
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
entity = pkg.load("minecraft.entity")
attrs = pkg.load("minecraft.attributes")
events = pkg.load("neoforge.event")
bridge = pkg.load("core.modsdk_entity")
access_module = pkg.load("minecraft.modsdk_entity_access")
registry = pkg.load("neoforge.registries")
level_module = pkg.load("minecraft.level")


class FakeSystem(object):
    def __init__(self, namespace="test", system_name="test"):
        self.entities = {}
        self.calls = []
        self.fail = set()
        self.serial = 0
        self.remove_callback = None
        self.listeners = []
        self.moves = []

    def CreateEngineEntityByTypeStr(self, identifier, pos, rot, dimension):
        self.calls.append(("create", identifier, pos, rot, dimension))
        if "create" in self.fail:
            return None
        self.serial += 1
        key = "sdk:entity/" + str(self.serial)
        self.entities[key] = {"position": tuple(pos), "rotation": tuple(rot),
                              "health": 20.0, "maximum": 20.0, "loaded": True}
        return key

    def DestroyEntity(self, key):
        self.calls.append(("destroy", key))
        if "destroy" in self.fail:
            return False
        self.entities.pop(key, None)
        if self.remove_callback:
            self.remove_callback({"id": key})
        return True

    def ListenForEvent(self, namespace, system, name, owner, callback):
        self.listeners.append((namespace, system, name, owner, callback))

    def UnListenForEvent(self, namespace, system, name, owner, callback):
        self.listeners.remove((namespace, system, name, owner, callback))


class FakeComponent(object):
    def __init__(self, system, key):
        self.system, self.key = system, key

    def _get(self, field):
        if "read" in self.system.fail:
            raise RuntimeError("SDK read failed")
        state = self.system.entities.get(self.key)
        if state is None or not state["loaded"]:
            return None
        return state[field]

    def _set(self, operation, field, value, extra=()):
        self.system.calls.append((operation, self.key, value) + extra)
        if operation in self.system.fail:
            return False
        self.system.entities[self.key][field] = value
        return True

    def SetExtraData(self, key, value, auto_save=True):
        if "save" in self.system.fail:
            return False
        self.system.entities[self.key].setdefault("extra", {})[key] = value
        return True

    def GetExtraData(self, key):
        return self.system.entities[self.key].get("extra", {}).get(key)

    def SetMoveSetting(self, position, speed, iterations, callback):
        self.system.moves.append((position, speed, iterations, callback))

    def Hurt(self, damage, cause, attacker, projectile, knocked, tag):
        args = dict(entityId=self.key, damage=damage, cause=cause,
                    srcId=attacker, projectileId=projectile, customTag=tag)
        self.system.damage_callback(args)
        self.system.final_damage_callback(args)
        self.system.entities[self.key]["health"] = max(
            0, self.system.entities[self.key]["health"] - args["damage"])
        return True

    def GetFootPos(self):
        return self._get("position")

    def SetFootPos(self, pos):
        return self._set("position", "position", tuple(pos))

    def GetRot(self):
        return self._get("rotation")

    def SetRot(self, rot):
        return self._set("rotation", "rotation", tuple(rot))

    def GetAttrValue(self, kind):
        assert kind == 91
        return self._get("health")

    def SetAttrMaxValue(self, kind, value):
        assert kind == 91
        return self._set("maximum", "maximum", value)

    def SetAttrValue(self, kind, value, set_default):
        assert kind == 91
        return self._set("health", "health", value, (set_default,))


class FakeFactory(object):
    def __init__(self, system):
        self.system = system

    def CreatePos(self, key):
        return FakeComponent(self.system, key)

    CreateRot = CreatePos
    CreateAttr = CreatePos
    CreateMoveTo = CreatePos
    CreateHurt = CreatePos
    CreateExtraData = CreatePos


class FakeApi(object):
    class Enums(object):
        class AttrType(object):
            HEALTH = 91

    def __init__(self, system):
        self.system = system

    def GetEngineCompFactory(self):
        return FakeFactory(self.system)

    def GetMinecraftEnum(self):
        return self.Enums

    def GetServerSystemCls(self):
        return FakeSystem

    def GetEngineNamespace(self):
        return "Minecraft"

    def GetEngineSystemName(self):
        return "Engine"


class SdkEntityTests(unittest.TestCase):
    def test_unimplemented_world_calls_cannot_look_like_empty_world_success(self):
        pos = pkg.load('minecraft.core').BlockPos(0,64,0)
        for name, args in [('getBlockState',(pos,)),('isEmptyBlock',(pos,)),
                           ('setBlock',(pos,None,3)),('getFluidState',(pos,)),
                           ('getBlockEntity',(pos,))]:
            with self.subTest(operation=name), self.assertRaises(access_module.EngineBridgeError):
                getattr(self.access,name)(*args)
        self.assertTrue(self.access.unsupported)

    def test_navigation_request_order_stop_and_closed_access_guard(self):
        mob = self.spawn()
        nav = mob.getNavigation()
        key = self.access.getEngineId(mob)
        self.assertTrue(nav.moveTo(2,64,3,1.0))
        old = self.system.moves[-1][-1]
        self.assertTrue(nav.moveTo(4,64,5,1.0))
        current = self.system.moves[-1][-1]
        old(key, 0)
        self.assertFalse(nav.isDone())
        current(key, 0)
        self.assertTrue(nav.isDone())
        self.assertEqual(nav.getLastResult(), 0)
        nav.moveTo(6,64,7,1.0)
        stopped = self.system.moves[-1][-1]
        nav.stop()
        stopped(key, 0)
        self.assertTrue(nav.isDone())
        self.assertIsNone(nav.getLastResult())
        calls = len(self.system.moves)
        self.access._closed = True
        self.assertFalse(nav.moveTo(8,64,9,1.0))
        self.assertEqual(len(self.system.moves), calls)

    def test_controller_close_isolates_dimensions_and_retains_failed_owner_for_retry(self):
        first = self.spawn()
        other = self.controller.createRuntime(0, events.IEventBus('other_mod'), self.gamebus)
        second = other.spawn(self.holder.get(), (0,64,0))
        original = self.access.close
        def fail():
            raise RuntimeError('dimension teardown failed')
        self.access.close = fail
        self.assertFalse(self.controller.close())
        self.assertFalse(first.isRemoved())
        self.assertTrue(second.isRemoved())
        self.assertNotIn(0, self.controller._runtimes)
        self.assertIn(2, self.controller._runtimes)
        self.assertIn(id(self.access), level_module.Level._wrappers)
        self.assertTrue(self.controller.cleanup_errors)
        with self.assertRaises(Exception):
            self.runtime.spawn(self.holder.get(), (0,0,0))
        self.access.close = original
        self.assertTrue(self.controller.close())
        self.assertTrue(first.isRemoved())
        self.assertNotIn(id(self.access), level_module.Level._wrappers)

    def test_runtime_close_continues_after_one_rejected_entity_and_prevents_new_work(self):
        first, second = self.spawn(), self.spawn()
        first_key = self.access.getEngineId(first)
        original = self.system.DestroyEntity
        def reject_one(key):
            if key == first_key:
                return False
            return original(key)
        self.system.DestroyEntity = reject_one
        with self.assertRaisesRegex(RuntimeError, 'rejected DestroyEntity'):
            self.runtime.close()
        self.assertFalse(first.isRemoved())
        self.assertTrue(second.isRemoved())
        self.assertTrue(self.runtime.cleanup_errors)
        with self.assertRaises(Exception):
            self.runtime.spawn(self.holder.get(), (0,0,0))
        count = first.tickCount
        self.runtime.tick()
        self.assertEqual(first.tickCount, count)
        self.system.DestroyEntity = original
        self.runtime.close()
        self.assertTrue(first.isRemoved())
        self.runtime.close()

    def setUp(self):
        entity.EntityType.clear()
        self.system = FakeSystem()
        self.api = FakeApi(self.system)
        self.controller = bridge.EntityBridgeController(self.system, self.api)
        self.modbus, self.gamebus = events.IEventBus("mod"), events.IEventBus("game")
        types = registry.DeferredRegister.createEntities("sdk_test")
        self.holder = types.register("mob", lambda:
            entity.EntityType.Builder.of(entity.Mob, entity.MobCategory.CREATURE)
            .build("sdk_test:mob"))
        types.register_event_bus(self.modbus)
        self.modbus.subscribe(lambda event: event.put(self.holder.get(),
            entity.Mob.createMobAttributes().add(attrs.Attributes.MAX_HEALTH, 40)
            .build()), events.EntityAttributeCreationEvent)
        self.runtime = self.controller.createRuntime(2, self.modbus, self.gamebus)
        self.access = self.runtime.level.getAccess()
        self.system.remove_callback = self.controller.onEntityRemoved

    def tearDown(self):
        self.system.fail.clear()
        self.controller.close()
        entity.EntityType.clear()
        level_module.Level.resetWrappers()

    def spawn(self):
        return self.runtime.spawn(self.holder.get(), (1.25, 64.5, -2.75))

    def leave_events(self):
        return [e for e in self.gamebus.posted
                if isinstance(e, events.EntityLeaveLevelEvent)]

    def test_attachment_roundtrip_via_extradata_after_runtime_restart(self):
        import copy
        import types
        attachments = pkg.load('neoforge.attachment')
        nbt = pkg.load('minecraft.nbt')
        class Serializer(attachments.IAttachmentSerializer):
            def write(self, value, provider):
                tag = nbt.CompoundTag()
                tag.putInt('value', value)
                return tag
            def read(self, holder, tag, provider):
                return tag.getInt('value')
        kind = attachments.AttachmentType.builder(lambda: 0).serialize(Serializer()).build()
        table = {'neoforge:attachment_types': {'sdk_test:counter': kind}}
        self.gamebus.loader = types.SimpleNamespace(registries=table)
        mob = self.spawn()
        mob.setData(kind, 42)
        key = self.access.getEngineId(mob)
        self.assertTrue(self.controller.checkpoint())
        restarted_system = FakeSystem()
        restarted_system.entities = copy.deepcopy(self.system.entities)
        restarted_api = FakeApi(restarted_system)
        restarted = bridge.EntityBridgeController(restarted_system, restarted_api)
        bus = events.IEventBus('restarted')
        bus.loader = types.SimpleNamespace(registries=table)
        try:
            restarted.createRuntime(2, events.IEventBus("restarted-mod"), bus)
            restored = restarted.restoreEntity(key, 2)
            self.assertIsNot(restored, mob)
            self.assertEqual(restored.getData(kind), 42)
            self.assertEqual(restored.getUUID(), mob.getUUID())
            self.assertIs(restarted.restoreEntity(key, 2), restored)
            self.assertEqual([row for row in restarted_system.calls if row[0] == 'create'], [])
        finally:
            restarted.close()

    def test_spawn_id_dimension_and_health_contract(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        self.assertIsInstance(mob.getId(), int)
        self.assertEqual(key, "sdk:entity/1")
        self.assertIs(self.runtime.level.getEntity(mob.getId()), mob)
        self.assertEqual(self.system.calls[:3], [
            ("create", "sdk_test:mob", (1.25, 64.5, -2.75), (0.0, 0.0), 2),
            ("maximum", key, 40.0), ("health", key, 40.0, 0)])
        self.assertIs(self.access.getByEngineId(key), mob)

    def test_engine_damage_and_motion_not_overwritten(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        self.system.entities[key].update(health=11, position=(9, 8, 7),
                                        rotation=(20, 100))
        self.system.calls[:] = []
        self.controller.onTick()
        self.assertEqual(mob.getHealth(), 11)
        self.assertEqual((mob.getX(), mob.getY(), mob.getZ()), (9, 8, 7))
        self.assertEqual((mob.getXRot(), mob.getYRot()), (20, 100))
        self.assertEqual(self.system.calls, [])

    def test_local_changes_commit_before_pull(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        mob.setPos(3, 4, 5)
        mob.setXRot(15)
        mob.setYRot(80)
        mob.getAttribute(attrs.Attributes.MAX_HEALTH).setBaseValue(60)
        mob.setHealth(55)
        self.controller.onTick()
        self.assertEqual(self.system.entities[key]["position"], (3, 4, 5))
        self.assertEqual(self.system.entities[key]["rotation"], (15, 80))
        self.assertEqual(self.system.entities[key]["maximum"], 60)
        self.assertEqual(self.system.entities[key]["health"], 55)

    def test_logic_changes_flush_after_tick(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        mob.tick = lambda: mob.setPos(100, 64, 100)
        self.controller.onTick()
        self.controller.onTick()
        self.assertEqual(self.system.entities[key]["position"], (100, 64, 100))

    def test_tick_rate_30_to_20(self):
        mob = self.spawn()
        for unused in range(30):
            self.controller.onTick()
        self.assertEqual(mob.tickCount, 20)
        for unused in range(30):
            self.controller.onTick()
        self.assertEqual(mob.tickCount, 40)

    def test_create_failure_leaves_no_mapping(self):
        self.system.fail.add("create")
        self.assertIsNone(self.spawn())
        self.assertEqual(self.access.getEntities(), [])
        self.assertEqual(self.runtime._entities, {})

    def test_attribute_failure_rolls_back_engine_entity(self):
        self.system.fail.add("health")
        with self.assertRaises(access_module.EngineBridgeError):
            self.spawn()
        self.assertEqual(self.system.entities, {})
        self.assertEqual(self.access.getEntities(), [])
        self.assertEqual(self.runtime._entities, {})

    def test_failed_rollback_retries_without_ticking(self):
        self.system.fail.update(["health", "destroy"])
        with self.assertRaises(access_module.EngineBridgeError):
            self.spawn()
        mob = self.access.getEntities()[0]
        self.system.fail.clear()
        self.controller.onTick()
        self.assertEqual(self.system.entities, {})
        self.assertTrue(mob.isRemoved())
        self.assertEqual(mob.tickCount, 0)

    def test_cancelled_join_never_calls_create(self):
        self.gamebus.subscribe(lambda event: event.cancel(), events.EntityJoinLevelEvent)
        self.assertIsNone(self.spawn())
        self.assertEqual(self.system.calls, [])

    def test_remove_synchronous_event_exactly_once(self):
        mob = self.spawn()
        self.assertTrue(self.runtime.remove(mob))
        self.assertEqual(len(self.leave_events()), 1)
        self.controller.onTick()
        self.assertEqual(len(self.leave_events()), 1)
        self.assertEqual(self.access.getEntities(), [])

    def test_external_removal_and_unknown_id(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        self.system.calls[:] = []
        self.system.entities.pop(key)
        self.controller.onEntityRemoved({"id": key})
        self.controller.onEntityRemoved({"id": "other-mod-entity"})
        self.controller.onEntityRemoved({"id": key})
        self.assertTrue(mob.isRemoved())
        self.assertEqual(self.system.calls, [])
        self.assertEqual(len(self.leave_events()), 1)

    def test_failed_destroy_stays_tracked_then_retries(self):
        mob = self.spawn()
        self.system.fail.add("destroy")
        with self.assertRaises(access_module.EngineBridgeError):
            self.runtime.remove(mob)
        self.assertFalse(mob.isRemoved())
        self.assertIs(self.runtime.level.getEntity(mob.getId()), mob)
        self.assertEqual(len(self.leave_events()), 0)
        self.system.fail.clear()
        self.controller.onTick()
        self.assertTrue(mob.isRemoved())
        self.assertEqual(len(self.leave_events()), 1)

    def test_unloaded_chunk_pauses_without_death(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        self.system.entities[key]["loaded"] = False
        for unused in range(9):
            self.controller.onTick()
        self.assertEqual(mob.tickCount, 0)
        self.assertFalse(mob.isRemoved())
        self.assertEqual(self.leave_events(), [])
        self.system.entities[key]["loaded"] = True
        for unused in range(3):
            self.controller.onTick()
        self.assertEqual(mob.tickCount, 2)

    def test_read_failure_is_reported_and_recovers(self):
        mob = self.spawn()
        self.system.fail.add("read")
        self.controller.onTick()
        self.assertFalse(self.access.isEntityActive(mob))
        self.assertEqual(self.access.errors[-1][0], "pull")
        self.system.fail.clear()
        self.controller.onTick()
        self.assertTrue(self.access.isEntityActive(mob))

    def test_failed_write_preserves_local_edit_for_retry(self):
        mob = self.spawn()
        key = self.access.getEngineId(mob)
        mob.setPos(90, 80, 70)
        self.system.fail.add("position")
        self.controller.onTick()
        self.assertEqual(mob.getX(), 90)
        self.assertNotEqual(self.system.entities[key]["position"], (90, 80, 70))
        self.system.fail.clear()
        self.controller.onTick()
        self.assertEqual(self.system.entities[key]["position"], (90, 80, 70))

    def test_close_only_owned_entities_and_reports_failure(self):
        mob = self.spawn()
        self.system.entities["unrelated"] = {"loaded": True}
        self.system.fail.add("destroy")
        self.assertFalse(self.controller.close())
        self.assertFalse(mob.isRemoved())
        self.system.fail.clear()
        self.assertTrue(self.controller.close())
        self.assertIn("unrelated", self.system.entities)
        self.assertTrue(mob.isRemoved())
        self.assertEqual(len(self.leave_events()), 1)
        with self.assertRaises(Exception):
            self.runtime.spawn(self.holder.get(), (0, 0, 0))


class SystemLifecycleTests(unittest.TestCase):
    def test_unlisten_attempts_remaining_callbacks_and_retries_failed_binding(self):
        api = FakeApi(None)
        system = bridge.install_server_system(api)('core', 'bridge')
        original = system.UnListenForEvent
        first_event = system._listened[0][0]
        def reject_one(namespace, engine, name, owner, callback):
            if name == first_event:
                raise RuntimeError('SDK unlisten failed')
            return original(namespace, engine, name, owner, callback)
        system.UnListenForEvent = reject_one
        with self.assertRaisesRegex(RuntimeError, 'SDK unlisten failed'):
            system.Destroy()
        self.assertEqual(len(system.listeners), 1)
        self.assertEqual(len(system._listened), 1)
        self.assertTrue(system.entityBridge.cleanup_errors)
        system.UnListenForEvent = original
        system.Destroy()
        self.assertEqual(system.listeners, [])
        system.Destroy()

    def test_register_and_unlisten_with_no_client_import(self):
        api = FakeApi(None)
        cls = bridge.install_server_system(api)
        system = cls("NeoForgeCore", "EntityBridge")
        api.system = system
        self.assertEqual([row[2] for row in system.listeners],
                         ["OnScriptTickServer", "EntityRemoveEvent", "DamageEvent", "ActuallyHurtServerEvent"])
        system.Destroy()
        system.Destroy()
        self.assertEqual(system.listeners, [])

    def test_event_export_identity(self):
        runtime = pkg.load("core.entity_runtime")
        self.assertIs(runtime.EntityAttributeCreationEvent, events.EntityAttributeCreationEvent)
        self.assertIs(runtime.EntityLeaveLevelEvent, events.EntityLeaveLevelEvent)



class DemoAndResourceTests(unittest.TestCase):
    def setUp(self):
        entity.EntityType.clear()
        self.api = FakeApi(None)
        self.system = bridge.install_server_system(self.api)("NeoForgeCore", "EntityBridge")
        self.api.system = self.system
        self.system.remove_callback = self.system.entityBridge.onEntityRemoved

    def tearDown(self):
        self.system.Destroy()
        entity.EntityType.clear()
        level_module.Level.resetWrappers()

    def test_demo_generates_and_rotates_after_server_ticks(self):
        demo = pkg.load("core.entity_demo")
        mob = demo.spawn_training_mob(self.system, (3, 70, 4))
        access = self.system.getEntityRuntime().level.getAccess()
        key = access.getEngineId(mob)
        self.assertEqual(self.system.calls[0][1], "neocore:training_mob")
        for unused in range(30):
            self.system._on_entity_tick()
        self.assertEqual(mob.tickCount, 20)
        self.assertEqual(self.system.entities[key]["rotation"], (0, 60))
        self.assertEqual(mob.getHealth(), 40)
        other = demo.spawn_training_mob(self.system, (4, 70, 4))
        self.assertNotEqual(mob.getId(), other.getId())

    def test_demo_multiple_dimensions_share_type_not_instances(self):
        demo = pkg.load("core.entity_demo")
        first = demo.spawn_training_mob(self.system, (0, 64, 0), 0)
        second = demo.spawn_training_mob(self.system, (0, 64, 0), 1)
        self.assertIs(first.getType(), second.getType())
        first.setHealth(5)
        self.assertEqual(second.getHealth(), 40)
        self.system.Destroy()
        self.assertEqual(self.system.entities, {})

    def test_resource_references_and_dimensions_match(self):
        import json
        from pathlib import Path
        from harness import PACK_ROOT
        pack = Path(PACK_ROOT)
        resource = pack.parent / "resource_pack_kFreO1qQ"
        def read(path):
            return json.loads(path.read_text(encoding="utf-8-sig"))
        behavior = read(pack / "entities/neocore_training_mob.json")["minecraft:entity"]
        client = read(resource / "entity/neocore_training_mob.entity.json")["minecraft:client_entity"]["description"]
        geometry = read(resource / "models/entity/neocore_training_mob.geo.json")["minecraft:geometry"][0]
        controllers = read(resource / "render_controllers/neocore_training_mob.render_controllers.json")["render_controllers"]
        manifest = read(pack / "manifest.json")
        resource_header = read(resource / "manifest.json")["header"]
        self.assertIn({"uuid": resource_header["uuid"], "version": resource_header["version"]},
                      manifest["dependencies"])
        self.assertEqual(behavior["description"]["identifier"], client["identifier"])
        self.assertEqual(client["geometry"]["default"], geometry["description"]["identifier"])
        self.assertIn(client["render_controllers"][0], controllers)
        demo = pkg.load("core.entity_demo")
        mob = demo.spawn_training_mob(self.system, (0, 64, 0))
        box = behavior["components"]["minecraft:collision_box"]
        self.assertEqual((box["width"], box["height"]), (mob.getWidth(), mob.getHeight()))
        self.assertEqual(behavior["components"]["minecraft:health"]["max"], mob.getMaxHealth())

    def test_modmain_registers_only_in_server_init(self):
        import types
        from py2to3lite import compile_module
        from harness import SCRIPTS_ROOT
        sdk_mod = types.ModuleType("mod")
        sdk_mod.__path__ = []
        common = types.ModuleType("mod.common")
        common.__path__ = []
        modmod = types.ModuleType("mod.common.mod")
        server = types.ModuleType("mod.server")
        server.__path__ = []
        api_module = types.ModuleType("mod.server.extraServerApi")
        class Binding(object):
            @staticmethod
            def Binding(**kwargs):
                return lambda cls: cls
            @staticmethod
            def InitServer():
                return lambda function: function
            InitClient = InitServer
            DestroyServer = InitServer
            DestroyClient = InitServer
        modmod.Mod = Binding
        sdk_mod.common, sdk_mod.server = common, server
        common.mod, server.extraServerApi = modmod, api_module
        client = types.ModuleType("mod.client")
        client.__path__ = []
        client_api = types.ModuleType("mod.client.extraClientApi")
        client_registrations = []
        client_api.GetClientSystemCls = self.api.GetServerSystemCls
        client_api.RegisterSystem = lambda *args: client_registrations.append(args)
        sdk_mod.client = client
        client.extraClientApi = client_api
        registrations = []
        api_module.GetServerSystemCls = self.api.GetServerSystemCls
        api_module.RegisterSystem = lambda *args: registrations.append(args)
        modules = {"mod": sdk_mod, "mod.common": common, "mod.common.mod": modmod,
                   "mod.server": server, "mod.server.extraServerApi": api_module,
                   "mod.client": client, "mod.client.extraClientApi": client_api}
        saved = dict((key, sys.modules.get(key)) for key in modules)
        try:
            sys.modules.update(modules)
            main = compile_module(os.path.join(SCRIPTS_ROOT, "modMain.py"),
                                  "_entity_entry_test", False)
            self.assertEqual(registrations, [])
            instance = main.NeoForgeCore()
            instance.init_client()
            self.assertEqual(registrations, [])
            instance.init_server()
            self.assertEqual(len(registrations), 2)
            self.assertEqual(registrations[1][:2], ("NeoCore", "Loader"))
            namespace, name, path = registrations[0]
            self.assertEqual((namespace, name), ("NeoForgeCore", "EntityBridge"))
            module_name, class_name = path.rsplit(".", 1)
            module = __import__(module_name, fromlist=[class_name])
            self.assertTrue(issubclass(getattr(module, class_name), FakeSystem))
            self.assertEqual(len(client_registrations), 1)
            self.assertEqual(client_registrations[0][:2], ("NeoCore", "Loader"))
            self.assertTrue(client_registrations[0][2].endswith(".NeoCoreClientLoaderSystem"))
            self.assertEqual(instance.get_translated_report("SERVER"), {"error": None, "mods": {}})
            self.assertEqual(instance.get_translated_report("CLIENT"), {"error": None, "mods": {}})
            instance.destroy_client()
            instance.destroy_server()
        finally:
            for key, value in saved.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value

if __name__ == "__main__":
    unittest.main()

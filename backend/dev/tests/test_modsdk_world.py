# -*- coding: utf-8 -*-
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
world = pkg.load("minecraft.modsdk_world_access")
block = pkg.load("minecraft.block")
core = pkg.load("minecraft.core")
level = pkg.load("minecraft.level")
entity_access = pkg.load("minecraft.modsdk_entity_access")
bridge = pkg.load("core.modsdk_entity")
events = pkg.load("neoforge.event")


class Sdk(object):
    def __init__(self):
        self.cells = {(0, 1, 2): ("test:a", {})}
        self.calls = []
        self.aux = 7
        self.changed = True
        self.bad_readback = False
    def GetEngineCompFactory(self): return self
    def GetLevelId(self): return "level"
    def GetMinecraftEnum(self):
        return type("Enums", (), {"AttrType": type("Attrs", (), {"HEALTH": 1})})
    def CreateBlockInfo(self, key): return self
    def CreateBlockState(self, key): return self
    def GetBlockNew(self, pos, dimension):
        self.calls.append(("read", pos, dimension))
        cell = self.cells.get(pos)
        return {"name": cell[0], "aux": 7} if cell else None
    def GetBlockStates(self, pos, dimension):
        cell = self.cells.get(pos)
        return dict(cell[1]) if cell else None
    def GetBlockAuxValueFromStates(self, name, values):
        self.calls.append(("aux", name, dict(values)))
        return self.aux
    def SetBlockNew(self, pos, value, handling, dimension, legacy, neighbors):
        self.calls.append(("write", pos, dict(value), handling, dimension, legacy, neighbors))
        if self.changed:
            self.cells[pos] = ("test:wrong" if self.bad_readback else value["name"], {})
        return self.changed


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.a = block.Block().defaultBlockState()
        self.b = block.Block().defaultBlockState()
        self.maps = world.BlockStateMappings().register(self.a, "test:a", {}).register(self.b, "test:b", {})
        self.sdk = Sdk()
        self.pos = core.BlockPos(0, 1, 2)
        self.access = world.ModSdkWorldAccess(self.sdk, 7, self.maps, self.policy)
    @staticmethod
    def policy(flags):
        if flags not in (2, 3): raise ValueError("Unreviewed flags")
        return flags == 3
    def writes(self): return [call for call in self.sdk.calls if call[0] == "write"]
    def test_level_read_and_replace(self):
        wrapped = level.Level.wrap(self.access)
        self.assertIs(wrapped.getBlockState(self.pos), self.a)
        self.assertTrue(wrapped.setBlock(self.pos, self.b, 2))
        self.assertEqual(self.writes()[0], ("write", (0, 1, 2), {"name": "test:b", "aux": 7}, 0, 7, True, False))
        self.assertIs(wrapped.getBlockState(self.pos), self.b)
    def test_noop_does_not_clear_container(self):
        self.assertFalse(self.access.setBlock(self.pos, self.a))
        self.assertFalse(self.writes())
    def test_missing_or_unknown_is_not_air(self):
        for cell in (None, ("test:unknown", {}), ("test:a", {"unexpected": 1})):
            if cell is None: self.sdk.cells.clear()
            else: self.sdk.cells[(0, 1, 2)] = cell
            with self.assertRaises(world.EngineBridgeError): self.access.isEmptyBlock(self.pos)
    def test_failed_aux_flags_policy_do_not_write(self):
        self.sdk.aux = -1
        with self.assertRaises(world.EngineBridgeError): self.access.setBlock(self.pos, self.b)
        self.sdk.aux = 7
        with self.assertRaises(ValueError): self.access.setBlock(self.pos, self.b, 16)
        self.access.write_policy = None
        with self.assertRaises(world.EngineBridgeError): self.access.setBlock(self.pos, self.b)
        self.assertFalse(self.writes())
    def test_write_failure_and_mismatch(self):
        self.sdk.changed = False
        self.assertFalse(self.access.setBlock(self.pos, self.b))
        self.sdk.changed = True
        self.sdk.bad_readback = True
        with self.assertRaises(world.EngineBridgeError): self.access.setBlock(self.pos, self.b)
    def test_collision_and_copy(self):
        with self.assertRaises(Exception): self.maps.register(self.b, "test:a", {})
        with self.assertRaises(Exception): self.maps.register(self.a, "test:c", {})
        name, values = self.maps.encode(self.a)
        values["mutated"] = 1
        self.assertIs(self.maps.decode("test:a", {}), self.a)
    def test_same_identifier_changes_refused(self):
        self.sdk.cells[(0, 1, 2)] = ("test:b", {"variant": 1})
        with self.assertRaises(world.EngineBridgeError): self.access.setBlock(self.pos, self.b)
        self.assertFalse(self.writes())
    def test_entity_controller_world_and_cleanup(self):
        controller = bridge.EntityBridgeController(object(), self.sdk)
        runtime = controller.createRuntime(7, events.IEventBus("mod"), events.IEventBus("game"), self.maps, self.policy)
        access = controller._accesses[7]
        self.assertIs(runtime.level.getBlockState(self.pos), self.a)
        self.assertTrue(runtime.level.setBlock(self.pos, self.b, 3))
        self.assertTrue(controller.close())
        self.assertTrue(access.world_access._closed)
        self.assertEqual(controller._accesses, {})
        with self.assertRaises(world.EngineBridgeError): runtime.level.getBlockState(self.pos)
    def test_close_and_unsupported(self):
        with self.assertRaises(world.EngineBridgeError): self.access.getBlockEntity(self.pos)
        self.access.close()
        self.assertIsNone(self.access.blocks)
        with self.assertRaises(world.EngineBridgeError): self.access.getBlockState(self.pos)

if __name__ == "__main__": unittest.main()

# -*- coding: utf-8 -*-
"""Entity mod integration: registration, attributes, spawning and custom AI."""
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package

pkg = Package()
entities = pkg.load("minecraft.entity")
attributes = pkg.load("minecraft.attributes")
goals = pkg.load("minecraft.goals")
world = pkg.load("minecraft.level")
access = pkg.load("minecraft.level_access")
events = pkg.load("neoforge.event")
registries = pkg.load("neoforge.registries")
runtime = pkg.load("core.entity_runtime")
A = attributes.Attributes
Modifier = attributes.AttributeModifier


class AttributeTests(unittest.TestCase):
    def test_modifier_order_and_removal(self):
        instance = attributes.AttributeInstance(A.MAX_HEALTH)
        instance.addTransientModifier(Modifier("test:add", 10, 0))
        instance.addTransientModifier(Modifier("test:base", 0.5, 1))
        instance.addPermanentModifier(Modifier("test:total", 1, 2))
        self.assertEqual(instance.getValue(), 90)
        self.assertEqual(len(instance.getPermanentModifiers()), 1)
        with self.assertRaises(Exception):
            instance.addTransientModifier(Modifier("test:add", 1, 0))
        instance.removeModifier("test:base")
        self.assertEqual(instance.getValue(), 60)
        instance.removeModifiers()
        self.assertEqual(instance.getValue(), 20)

    def test_bounds_and_unknown_attributes(self):
        instance = attributes.AttributeInstance(A.MAX_HEALTH)
        instance.setBaseValue(99999)
        self.assertEqual(instance.getValue(), 1024)
        instance.setBaseValue(float("nan"))
        self.assertEqual(instance.getValue(), 1)
        with self.assertRaises(Exception):
            attributes.RangedAttribute("bad", 2, 0, 1)
        living = entities.LivingEntity()
        unknown = attributes.Attribute("test:unknown", 3)
        self.assertIsNone(living.getAttribute(unknown))
        with self.assertRaises(Exception):
            living.getAttributeValue(unknown)

    def test_supplier_snapshot_and_instance_isolation(self):
        builder = attributes.AttributeSupplier.builder().add(A.MAX_HEALTH, 40)
        supplier = builder.build()
        builder.add(A.MAX_HEALTH, 80)
        first = attributes.AttributeMap(supplier)
        second = attributes.AttributeMap(supplier)
        first.getInstance(A.MAX_HEALTH).setBaseValue(60)
        self.assertEqual(second.getValue(A.MAX_HEALTH), 40)
        self.assertEqual(supplier.getBaseValue(A.MAX_HEALTH), 40)

    def test_holder_and_health_integration(self):
        class Holder(object):
            def value(self):
                return A.MAX_HEALTH
        living = entities.LivingEntity()
        living.getAttribute(Holder()).setBaseValue(60)
        living.setHealth(100)
        self.assertEqual(living.getHealth(), 60)
        living.getAttribute(A.MAX_HEALTH).addTransientModifier(Modifier("boost", 20, 0))
        self.assertEqual(living.getMaxHealth(), 80)
        living.heal(30)
        self.assertEqual(living.getHealth(), 80)


class ProbeGoal(goals.Goal):
    def __init__(self, name, trace, flag=goals.Goal.Flag.MOVE):
        goals.Goal.__init__(self)
        self.name, self.trace = name, trace
        self.enabled = True
        self.interruptable = True
        self.setFlags([flag])

    def canUse(self):
        return self.enabled

    def isInterruptable(self):
        return self.interruptable

    def start(self):
        self.trace.append((self.name, "start"))

    def stop(self):
        self.trace.append((self.name, "stop"))

    def tick(self):
        self.trace.append((self.name, "tick"))


class GoalTests(unittest.TestCase):
    def test_preemption_and_resumption(self):
        selector, trace = goals.GoalSelector(), []
        low, high = ProbeGoal("low", trace), ProbeGoal("high", trace)
        high.enabled = False
        selector.addGoal(5, low)
        selector.addGoal(1, high)
        selector.tick()
        high.enabled = True
        selector.tick()
        self.assertEqual(trace[:5], [("low", "start"), ("low", "tick"),
                                     ("low", "stop"), ("high", "start"),
                                     ("high", "tick")])
        high.enabled = False
        selector.tick()
        self.assertEqual(trace[-3:], [("high", "stop"), ("low", "start"),
                                      ("low", "tick")])

    def test_flags_equal_priority_and_noninterruptible(self):
        selector, trace = goals.GoalSelector(), []
        first, second = ProbeGoal("first", trace), ProbeGoal("second", trace)
        look = ProbeGoal("look", trace, goals.Goal.Flag.LOOK)
        selector.addGoal(2, first)
        selector.addGoal(2, second)
        selector.addGoal(2, look)
        selector.tick()
        self.assertEqual(len(selector.getRunningGoals()), 2)
        first.interruptable = False
        higher = ProbeGoal("higher", trace)
        selector.addGoal(0, higher)
        selector.tick()
        self.assertNotIn(("higher", "start"), trace)
        selector.disableControlFlag(goals.Goal.Flag.MOVE)
        selector.tick()
        self.assertEqual(len(selector.getRunningGoals()), 1)
        self.assertIn(("first", "stop"), trace)
        selector.removeGoal(look)
        self.assertEqual(selector.getRunningGoals(), [])

    def test_self_removal_does_not_break_iteration(self):
        selector, trace = goals.GoalSelector(), []
        class Once(ProbeGoal):
            def tick(self):
                selector.removeGoal(self)
        once = Once("once", trace)
        selector.addGoal(0, once)
        selector.tick()
        self.assertEqual(trace, [("once", "start"), ("once", "stop")])
        self.assertEqual(selector.getRunningGoals(), [])


class EntityModTests(unittest.TestCase):
    def setUp(self):
        entities.EntityType.clear()
        self.access = access.InMemoryLevelAccess()
        self.level = world.Level.wrap(self.access)
        self.bus = events.IEventBus("game")
        self.modbus = events.IEventBus("mod")
        self.runtime = runtime.EntityRuntime(self.level, self.bus)

    def tearDown(self):
        self.runtime.close()
        world.Level.resetWrappers()
        entities.EntityType.clear()

    def register(self):
        class TrainingMob(entities.Monster):
            def registerGoals(self):
                self.trace = []
                self.goalSelector.addGoal(1, ProbeGoal("watch", self.trace))
        register = registries.DeferredRegister.createEntities("test")
        holder = register.register("training", lambda:
            entities.EntityType.Builder.of(TrainingMob, entities.MobCategory.MONSTER)
            .sized(1.2, 2.4).eyeHeight(2.0).build("test:training"))
        register.register_event_bus(self.modbus)
        self.modbus.subscribe(lambda event: event.put(holder.get(),
            entities.Monster.createMonsterAttributes().add(A.MAX_HEALTH, 50)
            .add(A.ATTACK_DAMAGE, 7).build()), events.EntityAttributeCreationEvent)
        self.runtime.initialize(self.modbus)
        return holder.get()

    def test_end_to_end_custom_mob(self):
        kind = self.register()
        first = self.runtime.spawn(kind, (1.5, 64, -2))
        second = self.runtime.spawn(kind, (2, 64, -2))
        self.assertIs(first.getType(), kind)
        self.assertIs(first.level(), self.level)
        self.assertIs(self.level.getEntity(first.getId()), first)
        self.assertEqual(first.getWidth(), 1.2)
        self.assertEqual(first.getEyeHeight(), 2.0)
        self.assertEqual(first.getHealth(), 50)
        self.assertEqual(first.getAttributeValue(A.ATTACK_DAMAGE), 7)
        first.getAttribute(A.MAX_HEALTH).setBaseValue(75)
        self.assertEqual(second.getMaxHealth(), 50)
        self.runtime.tick()
        self.assertEqual(first.tickCount, 1)
        self.assertEqual(first.trace, [("watch", "start"), ("watch", "tick")])
        first.setNoAi(True)
        self.runtime.tick()
        self.assertEqual(first.trace[-1], ("watch", "stop"))
        first.setNoAi(False)
        self.runtime.tick()
        self.assertEqual(first.trace[-2:], [("watch", "start"), ("watch", "tick")])
        first.hurt(None, 100)
        self.assertIsNone(self.level.getEntity(first.getId()))
        self.runtime.tick()
        leaves = [event for event in self.bus.posted
                  if isinstance(event, events.EntityLeaveLevelEvent)]
        self.assertEqual(len(leaves), 1)
        self.assertIs(leaves[0].getEntity(), first)
        with self.assertRaises(Exception):
            leaves[0].cancel()
        self.runtime.tick()
        self.assertEqual(sum(isinstance(e, events.EntityLeaveLevelEvent)
                             for e in self.bus.posted), 1)

    def test_cancel_spawn_and_close(self):
        kind = self.register()
        entry = self.bus.subscribe(lambda event: event.cancel(),
                                   events.EntityJoinLevelEvent)
        self.assertIsNone(self.runtime.spawn(kind, (0, 0, 0)))
        self.assertEqual(self.access.entityCount(), 0)
        self.bus.unregister(entry["callback"])
        mob = self.runtime.spawn(kind, (0, 0, 0))
        self.runtime.close()
        self.assertTrue(mob.isRemoved())
        self.assertEqual(self.access.entityCount(), 0)
        self.runtime.close()

    def test_missing_attributes_and_initialization(self):
        kind = entities.EntityType.Builder.of(entities.Mob,
            entities.MobCategory.CREATURE).build("test:missing")
        with self.assertRaises(Exception):
            self.runtime.spawn(kind, (0, 0, 0))
        self.runtime.initialize(self.modbus)
        with self.assertRaises(Exception):
            self.runtime.spawn(kind, (0, 0, 0))
        with self.assertRaises(Exception):
            self.runtime.initialize(self.modbus)
        self.assertEqual(self.access.entityCount(), 0)

    def test_duplicate_type_and_invalid_dimensions(self):
        self.register()
        with self.assertRaises(Exception):
            entities.EntityType.Builder.of(entities.Mob,
                entities.MobCategory.CREATURE).build("test:training")
        for width in (-1, 0, float("nan"), float("inf")):
            with self.assertRaises(Exception):
                entities.EntityType.Builder.of(entities.Mob,
                    entities.MobCategory.CREATURE).sized(width, 1)

    def test_client_rejected_and_unimplemented_factory_explicit(self):
        with self.assertRaises(Exception):
            runtime.EntityRuntime(world.Level(access.InMemoryLevelAccess(True)), self.bus)
        with self.assertRaises(Exception):
            entities.EntityType.PIG.create(self.level)

    def test_removed_during_tick_skipped(self):
        kind = self.register()
        first = self.runtime.spawn(kind, (0, 0, 0))
        second = self.runtime.spawn(kind, (0, 0, 0))
        first.tick = lambda: self.runtime.remove(second)
        self.runtime.tick()
        self.assertEqual(second.tickCount, 0)


if __name__ == "__main__":
    unittest.main()

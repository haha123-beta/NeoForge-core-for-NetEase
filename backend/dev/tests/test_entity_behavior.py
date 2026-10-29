# -*- coding: utf-8 -*-
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_modsdk_entity as sdk
entity, attrs, events, pkg = sdk.entity, sdk.attrs, sdk.events, sdk.pkg
access = pkg.load("minecraft.level_access")
combat = pkg.load("minecraft.combat")
common = pkg.load("minecraft.common_goals")
blocks = pkg.load("minecraft.block")
core = pkg.load("minecraft.core")


class LocalBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.world = access.InMemoryLevelAccess()
        self.mob = entity.Mob(self.world)
        self.world.addEntity(self.mob)
        self.bus = events.IEventBus("combat")
        self.mob._event_bus = self.bus

    def test_navigation_finishes_and_stops(self):
        nav = self.mob.getNavigation()
        self.assertTrue(nav.moveTo(3, 0, 0, 1))
        for unused in range(100):
            nav.tick()
        self.assertTrue(nav.isDone())
        self.assertAlmostEqual(self.mob.getX(), 3)
        self.assertTrue(nav.moveTo(8, 0, 0, 1))
        nav.stop()
        before = self.mob.getX()
        nav.tick()
        self.assertEqual(before, self.mob.getX())

    def test_unreachable_height_and_invalid_speed(self):
        self.assertFalse(self.mob.getNavigation().moveTo(0, 10, 0, 1))
        with self.assertRaises(Exception):
            self.mob.getNavigation().moveTo(0, 0, 0, float("nan"))

    def test_clear_cancels_navigation(self):
        nav = self.mob.getNavigation()
        nav.moveTo(8, 0, 0, 1)
        self.world.clear()
        self.assertTrue(nav.isDone())

    def test_damage_events_heal_and_death_cancellation(self):
        source = combat.DamageSources().generic()
        self.bus.subscribe(lambda e: e.setAmount(4), events.LivingIncomingDamageEvent)
        self.assertTrue(self.mob.hurt(source, 9))
        self.assertEqual(self.mob.getHealth(), 16)
        self.mob.heal(2)
        self.assertEqual(self.mob.getHealth(), 18)
        self.mob.setHealth(1)
        self.bus.subscribe(lambda e: e.setCanceled(True), events.LivingDeathEvent)
        self.mob.hurt(source, 100)
        self.assertTrue(self.mob.isAlive())
        self.assertEqual(self.mob.getHealth(), 1)

    def test_canceled_listener_filter_and_nan_damage(self):
        seen = []
        self.bus.subscribe(lambda e: e.setCanceled(True), events.LivingIncomingDamageEvent)
        self.bus.subscribe(lambda e: seen.append("ordinary"), events.LivingIncomingDamageEvent)
        self.bus.subscribe(lambda e: seen.append("canceled"), events.LivingIncomingDamageEvent,
                           receive_canceled=True)
        self.assertFalse(self.mob.hurt(combat.DamageSources().generic(), 5))
        self.assertEqual(seen, ["canceled"])
        self.assertFalse(self.mob.hurt(combat.DamageSources().generic(), float("nan")))
        self.assertEqual(self.mob.getHealth(), 20)

    def test_attack_cooldown_and_retaliation(self):
        attacker = entity.Monster(self.world)
        # Direct constructors retain the base living supplier, so configure attack explicitly.
        attacker._attributes = attrs.AttributeMap(entity.Monster.createMonsterAttributes().build())
        self.world.addEntity(attacker)
        attacker.setTarget(self.mob)
        goal = common.MeleeAttackGoal(attacker, 1)
        goal.start()
        for unused in range(20):
            goal.tick()
        self.assertEqual(len(self.mob.damage_taken), 1)
        goal.tick()
        self.assertEqual(len(self.mob.damage_taken), 2)
        retaliate = common.HurtByTargetGoal(self.mob)
        self.assertTrue(retaliate.canUse())
        retaliate.start()
        self.assertIs(self.mob.getTarget(), attacker)
        self.assertFalse(retaliate.canUse())


class NativeBehaviorTests(unittest.TestCase):
    def setUp(self):
        sdk.SdkEntityTests.setUp(self)
        self.system.damage_callback = self.controller.onDamage
        self.system.final_damage_callback = self.controller.onActuallyHurt

    def tearDown(self):
        sdk.SdkEntityTests.tearDown(self)

    def spawn(self):
        return sdk.SdkEntityTests.spawn(self)

    def test_checkpoint_and_rebind_does_not_spawn(self):
        storage = pkg.load("minecraft.entity_storage")
        mob = self.spawn()
        mob.getPersistentData().putLong("counter", 2 ** 45)
        modifier = attrs.AttributeModifier("save:health", 10, 0)
        mob.getAttribute(attrs.Attributes.MAX_HEALTH).addPermanentModifier(modifier)
        self.assertTrue(self.controller.checkpoint())
        key = self.access.getEngineId(mob)
        snapshot = self.access.readEntitySave(key)
        tag = storage.loads(snapshot)
        self.assertEqual(tag.getCompound("NeoForgeData").getLong("counter"), 2 ** 45)
        self.assertEqual(tag.getCompound("NeoForgeData").getTagType("counter"), "long")
        original_uuid = mob.getUUID()
        self.access._detach(key)
        self.runtime.collectRemoved()
        created = len([row for row in self.system.calls if row[0] == "create"])
        self.system.entities[key]["position"] = (8, 9, 10)
        restored = self.controller.restoreEntity(key, 2)
        self.assertEqual(restored.getUUID(), original_uuid)
        self.assertEqual(restored.getX(), 8)
        self.assertEqual(restored.getMaxHealth(), 50)
        self.assertEqual(len([row for row in self.system.calls if row[0] == "create"]), created)
        self.assertIs(self.controller.restoreEntity(key, 2), restored)
        with self.assertRaises(Exception):
            self.runtime.restore(snapshot)

    def test_checkpoint_failure_is_reported(self):
        self.spawn()
        self.system.fail.add("save")
        self.assertFalse(self.controller.checkpoint())

    def test_snapshot_version_and_nonfinite_rejected(self):
        storage = pkg.load("minecraft.entity_storage")
        with self.assertRaises(Exception):
            storage.loads('{"version": 99}')
        mob = self.spawn()
        mob.setPos(float("nan"), 0, 0)
        with self.assertRaises(Exception):
            storage.dumps(mob)

    def test_native_damage_no_double_subtraction(self):
        mob = self.spawn()
        self.gamebus.subscribe(lambda e: e.setAmount(e.getAmount() / 2),
                               events.LivingIncomingDamageEvent)
        self.assertTrue(mob.hurt(combat.DamageSources().generic(), 10))
        self.access.syncFromEngine()
        self.assertEqual(mob.getHealth(), 35)
        self.assertEqual(len(mob.damage_taken), 1)
        self.access.syncToEngine()
        self.assertEqual(self.system.entities[self.access.getEngineId(mob)]["health"], 35)

    def test_native_cancel_death(self):
        mob = self.spawn()
        self.gamebus.subscribe(lambda e: e.setCanceled(True), events.LivingDeathEvent)
        mob.hurt(combat.DamageSources().generic(), 100)
        self.access.syncFromEngine()
        self.assertEqual(mob.getHealth(), 40)
        self.assertTrue(mob.isAlive())

    def test_native_navigation_stale_callback(self):
        mob = self.spawn()
        nav = mob.getNavigation()
        self.assertTrue(nav.moveTo(10, 64, 0, 1.2))
        old = self.system.moves[-1][-1]
        self.assertTrue(nav.moveTo(20, 64, 0, 1))
        old(self.access.getEngineId(mob), 3)
        self.assertFalse(nav.isDone())
        self.system.moves[-1][-1](self.access.getEngineId(mob), 0)
        self.assertTrue(nav.isDone())


if __name__ == "__main__":
    unittest.main()

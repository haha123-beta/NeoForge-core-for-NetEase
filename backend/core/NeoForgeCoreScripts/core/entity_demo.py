# -*- coding: utf-8 -*-
"""Opt-in visible training mob. No spawn occurs merely by importing this file."""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException
from minecraft.entity import EntityType, Mob, MobCategory
from minecraft.attributes import Attributes
from minecraft.goals import Goal
from neoforge.event import IEventBus, EntityAttributeCreationEvent
from neoforge.registries import DeferredRegister

IDENTIFIER = "neocore:training_mob"


class TurnInPlaceGoal(Goal):
    def __init__(self, mob):
        Goal.__init__(self)
        self.mob = mob
        self.setFlags([Goal.Flag.LOOK])

    def canUse(self):
        return self.mob.isAlive()

    def tick(self):
        self.mob.setYRot((self.mob.getYRot() + 3.0) % 360.0)


class TrainingMob(Mob):
    def registerGoals(self):
        self.goalSelector.addGoal(1, TurnInPlaceGoal(self))


def spawn_training_mob(server_system, position, dimension_id=0):
    """Call with a loaded position through the registered EntityBridge system."""
    runtime = server_system.getEntityRuntime(dimension_id)
    if runtime is None:
        mod_bus = IEventBus("neocore-demo-mod")
        game_bus = IEventBus("neocore-demo-game")
        registered = DeferredRegister.createEntities("neocore")

        def create_type():
            existing = EntityType.of(IDENTIFIER)
            if existing._factory is not None:
                if existing._factory is not TrainingMob:
                    raise IllegalArgumentException("Demo identifier is already in use")
                return existing
            return (EntityType.Builder.of(TrainingMob, MobCategory.CREATURE)
                    .sized(0.6, 1.8).build(IDENTIFIER))

        holder = registered.register("training_mob", create_type)
        registered.register_event_bus(mod_bus)

        def attributes(event):
            kind = holder.get()
            # Defaults are shared by type across dimensions, instances are not.
            if kind._attributes is None:
                event.put(kind, Mob.createMobAttributes()
                          .add(Attributes.MAX_HEALTH, 40).build())

        mod_bus.subscribe(attributes, EntityAttributeCreationEvent)
        runtime = server_system.createEntityRuntime(dimension_id, mod_bus, game_bus)
        runtime._demo_entity_type = holder.get()
    kind = getattr(runtime, "_demo_entity_type", None)
    if kind is None:
        raise IllegalArgumentException("Dimension already has a non-demo runtime")
    return runtime.spawn(kind, position)

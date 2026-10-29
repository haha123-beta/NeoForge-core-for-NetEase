# -*- coding: utf-8 -*-
from __future__ import print_function


def run(runtime, session):
    load = runtime.load
    main = session.loader.contexts['runtime_entity_example'].instance
    entities = load('minecraft.entity')
    levels = load('minecraft.level')
    access = load('minecraft.level_access').InMemoryLevelAccess()
    level = levels.ServerLevel(access)
    kind = entities.EntityType.of('r48:counter')
    kind._factory = main.create
    bus_type = load('neoforge.event').IEventBus
    mod_bus, game_bus = bus_type('r48:mod'), bus_type('r48:game')
    class ModBus(object):
        def freeze_registries(self): pass
        def post(self, event): return mod_bus.post(event)
    owner = load('core.entity_runtime').EntityRuntime(level, game_bus)
    owner.initialize(ModBus())
    entity = owner.spawn(kind, (1, 2, 3))
    assert entity.constructorObserved == 0 and entity.value == 7 and entity.ticks == 0
    assert entity.getType() is kind and entity.level() is level
    assert isinstance(entity, entities.Entity)
    for unused in range(100): owner.tick()
    assert (entity.ticks, entity.tickCount, entity.value) == (100, 100, 107)
    tag = load('minecraft.nbt').CompoundTag()
    assert entity.save(tag) and tag.getInt('CounterValue') == 107
    snapshot = load('minecraft.entity_storage').dumps(entity)
    # Restore the saved UUID only after removing the original live entity.
    assert owner.remove(entity) and entity.isRemoved()
    restored = owner.restore(snapshot)
    assert restored.getUUID() == entity.getUUID() and restored.value == 107
    assert restored.tickCount == 100 and restored.ticks == 0
    assert restored.level() is level and restored.getType() is kind
    owner.tick()
    assert restored.value == 108 and restored.ticks == 1 and restored.tickCount == 101
    # A cancelled entry must never be added to the world/runtime.
    join = load('neoforge.event.entity.registration').EntityJoinLevelEvent
    def veto(event): event.setCanceled(True)
    game_bus.addListener(join, veto)
    assert owner.spawn(kind, (4, 5, 6)) is None
    owner.close()
    assert restored.isRemoved() and not owner._entities
    assert not entity.save(tag)
    mod_bus.clear(); game_bus.clear()
    return {'constructor_observed_default': 0, 'source_ticks': 100, 'value_after_ticks': 107,
            'restored_value_after_tick': 108, 'world_identity': True,
            'join_cancelled': True, 'closed': True, 'engine_verified': False,
            'scope': 'Original Java generated class with in-memory EntityRuntime, not ModSDK entity creation'}

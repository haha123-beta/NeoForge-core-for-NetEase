import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
capabilities = package.load('neoforge.capabilities')
entities = package.load('minecraft.entity')
loaders = package.load('core.translated_loader')
events = package.load('core.content_events')
lifecycle = package.load('neoforge.event.fml.lifecycle')


class CapabilityTests(unittest.TestCase):
    def test_plain_block_lookup_order_changes_and_owner_cleanup(self):
        import types
        registry = capabilities.EntityCapabilityRegistry()
        capability = capabilities.BlockCapability.createVoid('example:block_test', dict)
        block, replacement, owner = object(), object(), object()
        class State(object):
            def __init__(self, block):
                self.block = block
            def getBlock(self):
                return self.block
        class World(object):
            state = State(block)
            def getBlockState(self, pos):
                return self.state
            def getBlockEntity(self, pos):
                return None
        world = World()
        world._capability_registry = registry
        event = capabilities.RegisterCapabilitiesEvent(registry, owner)
        event.registerBlock(capability, lambda *args: None, block)
        calls = []
        def provider(level, pos, state, block_entity, context):
            calls.append((level, pos, block_entity, context))
            return {'value': 7}
        event.registerBlock(capability, provider, block)
        self.assertTrue(event.isBlockRegistered(capability, block))
        self.assertEqual(capability.getCapability(world, (1, 2, 3))['value'], 7)
        self.assertEqual(calls, [(world, (1, 2, 3), None, None)])
        world.state = State(replacement)
        self.assertIsNone(capability.getCapability(world, (1, 2, 3)))
        event.close()
        with self.assertRaises(ValueError):
            event.registerBlock(capability, provider, block)
        registry.remove_owner(owner)
        world.state = State(block)
        self.assertIsNone(capability.getCapability(world, (1, 2, 3)))
        self.assertNotIn(capability, capabilities.EntityCapability.getAll())
        registry.close()

    def test_block_entity_provider_checks_type_and_releases_owner(self):
        import types
        block_entities = package.load('minecraft.block_entity')
        registry = capabilities.EntityCapabilityRegistry()
        cap = capabilities.BlockCapability.createVoid('example:block_entity_test', dict)
        block, owner = object(), object()
        kind = block_entities.BlockEntityType(lambda pos, state: None, [block])
        other = block_entities.BlockEntityType(lambda pos, state: None, [block])
        self.assertEqual(kind.getValidBlocks(), frozenset([block]))
        calls = []
        class Provider(object):
            def getCapability(self, block_entity, context):
                calls.append(block_entity)
                return {'side': context}
        event = capabilities.RegisterCapabilitiesEvent(registry, owner)
        event.registerBlockEntity(cap, kind, Provider())
        state = types.SimpleNamespace(getBlock=lambda: block)
        correct = types.SimpleNamespace(getType=lambda: kind)
        wrong = types.SimpleNamespace(getType=lambda: other)
        world = object()
        self.assertIsNone(registry.query_block(cap, world, None, state, None, None))
        self.assertIsNone(registry.query_block(cap, world, None, state, wrong, None))
        self.assertEqual(registry.query_block(cap, world, None, state, correct, 'north'), {'side': 'north'})
        self.assertEqual(calls, [correct])
        registry.remove_owner(owner)
        self.assertIsNone(registry.query_block(cap, world, None, state, correct, None))
        event.close()
        with self.assertRaises(ValueError):
            event.registerBlockEntity(cap, kind, Provider())

    def test_item_lookup_empty_stack_copy_split_and_session_cleanup(self):
        items = package.load('minecraft.item')
        cap = capabilities.ItemCapability.createVoid('example:item_test', dict)
        registry = capabilities.EntityCapabilityRegistry()
        owner, item = object(), items.Item(identifier='example:tool')
        event = capabilities.RegisterCapabilitiesEvent(registry, owner)
        calls = []
        def provider(stack, context):
            calls.append(stack)
            return {'count': stack.getCount()}
        event.registerItem(cap, lambda stack, context: None, item)
        event.registerItem(cap, provider, item)
        self.assertTrue(event.isItemRegistered(cap, item))
        stack = items.ItemStack(item, 4)
        self.assertIsNone(stack.getCapability(cap))
        registry.bind_stack(stack)
        self.assertEqual(stack.getCapability(cap), {'count': 4})
        clone = stack.copy()
        self.assertEqual(clone.getCapability(cap), {'count': 4})
        split = stack.split(2)
        self.assertEqual(split.getCapability(cap), {'count': 2})
        stack.setCount(0)
        before = len(calls)
        self.assertIsNone(stack.getCapability(cap))
        self.assertEqual(len(calls), before)
        with self.assertRaises(ValueError):
            capabilities.EntityCapabilityRegistry().bind_stack(clone)
        event.close()
        with self.assertRaises(ValueError):
            event.registerItem(cap, provider, item)
        registry.remove_owner(owner)
        self.assertIsNone(clone.getCapability(cap))
        registry.close()
        with self.assertRaises(ValueError):
            registry.bind_stack(items.ItemStack(item))

    def make_loader(self, value, fail=False):
        capability = capabilities.EntityCapability.createVoid('example:test', dict)
        entity_type = entities.EntityType.of('example:capability_mob')
        seen_events = []
        def start(ctx):
            def register(event):
                seen_events.append(event)
                event.registerEntity(capability, entity_type, lambda entity, context: None)
                event.registerEntity(capability, entity_type, lambda entity, context: {'value': value})
            ctx.mod_bus.subscribe(register, capabilities.RegisterCapabilitiesEvent)
            if fail:
                def broken(event):
                    raise ValueError('setup failure after registration')
                ctx.mod_bus.subscribe(broken, lifecycle.FMLCommonSetupEvent)
        manager = loaders.TranslatedModLoader(lambda path: start)
        manager.load({'schema_version': 1, 'mods': [{'mod_id': 'sample', 'entrypoint': 'start'}]})
        manager.activate()
        entity = entities.Entity(identifier='example:capability_mob')
        entity._event_bus = events.ContentGameBus(manager)
        return manager, entity, capability, seen_events

    def test_lookup_fallback_scope_isolation_and_close(self):
        first, entity, capability, seen = self.make_loader(1)
        second, other, same, unused = self.make_loader(2)
        self.assertIs(same, capability)
        self.assertEqual(entity.getCapability(capability), {'value': 1})
        self.assertEqual(other.getCapability(capability), {'value': 2})
        with self.assertRaises(ValueError):
            seen[0].registerEntity(capability, entity.getType(), lambda *a: {})
        first.close()
        self.assertIsNone(entity.getCapability(capability))
        self.assertEqual(other.getCapability(capability), {'value': 2})
        second.close()

    def test_failed_mod_provider_is_removed(self):
        manager, entity, capability, unused = self.make_loader(3, fail=True)
        self.assertEqual(manager.results['sample']['state'], 'failed')
        self.assertIsNone(entity.getCapability(capability))
        manager.close()

    def test_duplicate_definition_must_match_signature(self):
        capabilities.EntityCapability.createVoid('example:signature', dict)
        with self.assertRaises(ValueError):
            capabilities.EntityCapability.createVoid('example:signature', list)


if __name__ == '__main__':
    unittest.main()

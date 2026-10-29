# -*- coding: utf-8 -*-
"""NeoForge 1.21.1 entity capability lookup with session-owned providers.

No native block capability cache, automatic inventory provider or item query is implied.
"""
from __future__ import absolute_import
from neoforge.event.base import Event


class EntityCapability(object):
    _known = {}

    def __init__(self, name, type_class, context_class):
        self._name = name
        self._type_class = type_class
        self._context_class = context_class

    @classmethod
    def create(cls, name, type_class, context_class):
        key = name.toString() if hasattr(name, "toString") else str(name)
        if ":" not in key:
            raise ValueError("Capability requires a namespaced resource name")
        existing = cls._known.get(key)
        if existing is not None:
            if existing._type_class is not type_class or existing._context_class is not context_class:
                raise ValueError("Capability redefined with different types: " + key)
            return existing
        value = cls(name, type_class, context_class)
        cls._known[key] = value
        return value

    @classmethod
    def createVoid(cls, name, type_class):
        return cls.create(name, type_class, type(None))

    @classmethod
    def createSided(cls, name, type_class):
        from minecraft.core import Direction
        return cls.create(name, type_class, Direction)

    @classmethod
    def getAll(cls):
        return tuple(cls._known[key] for key in sorted(cls._known))

    def name(self):
        return self._name

    def typeClass(self):
        return self._type_class

    def contextClass(self):
        return self._context_class

    def getCapability(self, entity, context=None):
        registry = getattr(entity, "_capability_registry", None)
        if registry is None:
            bus = getattr(entity, "_event_bus", None)
            loader = getattr(bus, "loader", None)
            registry = getattr(loader, "capability_registry", None)
        if registry is None:
            return None
        return registry.query(self, entity, context)


class ItemCapability(EntityCapability):
    _known = {}

    def getCapability(self, stack, context=None):
        if stack.isEmpty():
            return None
        registry = getattr(stack, "_capability_registry", None)
        return None if registry is None else registry.query_item(self, stack, context)


class BlockCapability(EntityCapability):
    _known = {}

    def getCapability(self, level, pos, state=None, blockEntity=None, context=None):
        registry = getattr(level, "_capability_registry", None)
        if registry is None:
            loader = getattr(getattr(level, "_event_bus", None), "loader", None)
            registry = getattr(loader, "capability_registry", None)
        if registry is None:
            return None
        immutable = getattr(pos, "immutable", None)
        if callable(immutable):
            pos = immutable()
        if state is None:
            state = blockEntity.getBlockState() if blockEntity is not None else level.getBlockState(pos)
        if state is None:
            return None
        if blockEntity is None:
            blockEntity = level.getBlockEntity(pos)
        return registry.query_block(self, level, pos, state, blockEntity, context)


class EntityCapabilityRegistry(object):
    def __init__(self):
        self._providers = {}
        self._block_providers = {}
        self._item_providers = {}
        self._closed = False

    def register(self, owner, capability, entity_type, provider):
        if self._closed:
            raise ValueError("Capability registry is closed")
        if not isinstance(capability, EntityCapability) or isinstance(capability, (BlockCapability, ItemCapability)) or entity_type is None:
            raise ValueError("Expected entity capability and entity type")
        callback = getattr(provider, "getCapability", None)
        if not callable(callback):
            callback = provider
        if not callable(callback):
            raise ValueError("Capability provider must be callable")
        self._providers.setdefault((capability, entity_type), []).append((owner, callback))

    def query(self, capability, entity, context=None):
        if self._closed:
            return None
        for owner, callback in list(self._providers.get((capability, entity.getType()), [])):
            value = callback(entity, context)
            if value is not None:
                return value
        return None

    def register_block(self, owner, capability, provider, blocks):
        if self._closed:
            raise ValueError("Capability registry is closed")
        if not isinstance(capability, BlockCapability) or not blocks or any(block is None for block in blocks):
            raise ValueError("Expected block capability and at least one block")
        callback = getattr(provider, "getCapability", None)
        if not callable(callback):
            callback = provider
        if not callable(callback):
            raise ValueError("Block capability provider must be callable")
        for block in blocks:
            self._block_providers.setdefault((capability, block), []).append((owner, callback))

    def query_block(self, capability, level, pos, state, block_entity, context):
        if self._closed:
            return None
        for owner, callback in list(self._block_providers.get((capability, state.getBlock()), [])):
            value = callback(level, pos, state, block_entity, context)
            if value is not None:
                return value
        return None

    def bind_stack(self, stack):
        if self._closed:
            raise ValueError("Capability registry is closed")
        existing = getattr(stack, "_capability_registry", None)
        if existing is not None and existing is not self:
            raise ValueError("Item stack belongs to another capability session")
        stack._capability_registry = self
        return stack

    def register_item(self, owner, capability, provider, items):
        if self._closed:
            raise ValueError("Capability registry is closed")
        if not isinstance(capability, ItemCapability) or not items:
            raise ValueError("Expected item capability and at least one item")
        callback = getattr(provider, "getCapability", None)
        if not callable(callback):
            callback = provider
        if not callable(callback):
            raise ValueError("Capability provider must be callable")
        resolved = []
        for item in items:
            if item is None or not callable(getattr(item, "asItem", None)):
                raise ValueError("Expected ItemLike")
            value = item.asItem()
            if value is None:
                raise ValueError("ItemLike returned null")
            resolved.append(value)
        for item in resolved:
            self._item_providers.setdefault((capability, item), []).append((owner, callback))

    def query_item(self, capability, stack, context):
        if self._closed or stack.isEmpty():
            return None
        for owner, callback in list(self._item_providers.get((capability, stack.getItem()), [])):
            value = callback(stack, context)
            if value is not None:
                return value
        return None

    def remove_owner(self, owner):
        for providers in (self._providers, self._block_providers, self._item_providers):
            for key in list(providers):
                remaining = [row for row in providers[key] if row[0] is not owner]
                if remaining:
                    providers[key] = remaining
                else:
                    del providers[key]

    def close(self):
        self._closed = True
        self._providers.clear()
        self._block_providers.clear()
        self._item_providers.clear()


class RegisterCapabilitiesEvent(Event):
    def __init__(self, registry, owner):
        Event.__init__(self)
        self.registry = registry
        self.owner = owner
        self._open = True

    def registerEntity(self, capability, entity_type, provider):
        if not self._open:
            raise ValueError("Capability registration event has ended")
        self.registry.register(self.owner, capability, entity_type, provider)

    def isEntityRegistered(self, capability, entity_type):
        return bool(self.registry._providers.get((capability, entity_type)))

    def registerBlock(self, capability, provider, *blocks):
        if not self._open:
            raise ValueError("Capability registration event has ended")
        self.registry.register_block(self.owner, capability, provider, blocks)

    def isBlockRegistered(self, capability, block):
        return bool(self.registry._block_providers.get((capability, block)))

    def registerBlockEntity(self, capability, blockEntityType, provider):
        if not self._open:
            raise ValueError("Capability registration event has ended")
        callback = getattr(provider, "getCapability", None)
        if not callable(callback):
            callback = provider
        if not callable(callback):
            raise ValueError("Capability provider must be callable")
        if blockEntityType is None or not callable(getattr(blockEntityType, "getValidBlocks", None)):
            raise ValueError("Expected BlockEntityType")
        def adapted(level, pos, state, block_entity, context):
            if block_entity is None or block_entity.getType() is not blockEntityType:
                return None
            return callback(block_entity, context)
        blocks = tuple(blockEntityType.getValidBlocks())
        if not blocks:
            return
        self.registry.register_block(self.owner, capability, adapted, blocks)

    def registerItem(self, capability, provider, *items):
        if not self._open:
            raise ValueError("Capability registration event has ended")
        self.registry.register_item(self.owner, capability, provider, items)

    def isItemRegistered(self, capability, item):
        return bool(self.registry._item_providers.get((capability, item)))

    def close(self):
        self._open = False


class ICapabilityProvider(object):
    def __init__(self, callback=None):
        self.callback = callback

    def getCapability(self, value, context):
        if self.callback is None:
            raise NotImplementedError("Implement capability provider")
        return self.callback(value, context)


class IBlockCapabilityProvider(object):
    def __init__(self, callback=None):
        self.callback = callback

    def getCapability(self, level, pos, state, blockEntity, context):
        if self.callback is None:
            raise NotImplementedError("Implement block capability provider")
        return self.callback(level, pos, state, blockEntity, context)


class Capabilities(object):
    """Built-in capability identities; automatic native providers are still pending."""
    class EnergyStorage(object):
        from neoforge.energy import IEnergyStorage
        from neoforge.registries import ResourceLocation
        _name = ResourceLocation.fromNamespaceAndPath("neoforge", "energy")
        BLOCK = BlockCapability.createSided(_name, IEnergyStorage)
        ENTITY = EntityCapability.createSided(_name, IEnergyStorage)
        ITEM = ItemCapability.createVoid(_name, IEnergyStorage)

    class ItemHandler(object):
        from neoforge.items import IItemHandler
        from neoforge.registries import ResourceLocation
        _name = ResourceLocation.fromNamespaceAndPath("neoforge", "item_handler")
        BLOCK = BlockCapability.createSided(_name, IItemHandler)
        ENTITY = EntityCapability.createVoid(_name, IItemHandler)
        ENTITY_AUTOMATION = EntityCapability.createSided(
            ResourceLocation.fromNamespaceAndPath("neoforge", "item_handler_automation"), IItemHandler)
        ITEM = ItemCapability.createVoid(_name, IItemHandler)

    class FluidHandler(object):
        from neoforge.fluid_handler import IFluidHandler, IFluidHandlerItem
        from neoforge.registries import ResourceLocation
        _name = ResourceLocation.fromNamespaceAndPath("neoforge", "fluid_handler")
        BLOCK = BlockCapability.createSided(_name, IFluidHandler)
        ENTITY = EntityCapability.createSided(_name, IFluidHandler)
        ITEM = ItemCapability.createVoid(_name, IFluidHandlerItem)


JAVA_MAP = {
    "net.neoforged.neoforge.capabilities.Capabilities$FluidHandler": Capabilities.FluidHandler,
    "net.neoforged.neoforge.capabilities.Capabilities$ItemHandler": Capabilities.ItemHandler,
    "net.neoforged.neoforge.capabilities.Capabilities": Capabilities,
    "net.neoforged.neoforge.capabilities.Capabilities$EnergyStorage": Capabilities.EnergyStorage,
    "net.neoforged.neoforge.capabilities.ICapabilityProvider": ICapabilityProvider,
    "net.neoforged.neoforge.capabilities.IBlockCapabilityProvider": IBlockCapabilityProvider,
    "net.neoforged.neoforge.capabilities.ItemCapability": ItemCapability,
    "net.neoforged.neoforge.capabilities.BlockCapability": BlockCapability,
    "net.neoforged.neoforge.capabilities.EntityCapability": EntityCapability,
    "net.neoforged.neoforge.capabilities.RegisterCapabilitiesEvent": RegisterCapabilitiesEvent,
}
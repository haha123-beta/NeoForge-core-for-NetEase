# -*- coding: utf-8 -*-
# neoforge/registries.py
# β 层：NeoForge 注册系统
#
# 真实用法（从反编译源码提取，不是猜的）：
#
#   @Mod(value = "manaita_plus_legacy")
#   public class ManaitaPlusLegacy {
#       public static final DeferredRegister<Block> BLOCKS =
#           DeferredRegister.createBlocks("manaita_plus_legacy");
#       public static final DeferredRegister<Item> ITEMS =
#           DeferredRegister.create(BuiltInRegistries.ITEM, "manaita_plus_legacy");
#       public static final DeferredRegister<CreativeModeTab> TABS =
#           DeferredRegister.create(Registries.CREATIVE_MODE_TAB, "manaita_plus_legacy");
#
#       public ManaitaPlusLegacy(IEventBus modEventBus, ModContainer c) {
#           BLOCKS.register(modEventBus);      // ← 把注册器挂到事件总线上
#           ITEMS.register(modEventBus);
#       }
#   }
#
#   注册项本体：
#       public static final DeferredHolder<Block, CraftingBlock> CraftingBlock =
#           BLOCKS.register("crafting_manaita", CraftingBlock::new);
#
# 三个关键语义（照 Java 来，不能简化为「立即注册」）：
#   1. DeferredHolder 是**惰性**的：register 只登记名字与工厂，
#      真正创建对象发生在注册事件触发时；
#   2. DeferredHolder 要能当被注册对象本身用（它的 get() 会被自动调用），
#      所以实现了 __getattr__ 转发；
#   3. register 返回 holder，模组代码常直接把它当对象传下去。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
    )
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
    )
    from lang import java_to_string  # type: ignore


# ============================================================
# 注册表键
# ============================================================

class ResourceLocation(object):
    """
    对应 net.minecraft.resources.ResourceLocation。

    形态是 "命名空间:路径"（如 minecraft:item）。
    字符串里不含冒号时命名空间默认 minecraft —— 与 Java 语义一致。
    """

    def __init__(self, namespace, path=None):
        if path is None:
            text = java_to_string(namespace)
            if u":" in text:
                namespace, path = text.split(u":", 1)
            else:
                namespace, path = u"minecraft", text
        self.namespace = java_to_string(namespace)
        self.path = java_to_string(path)

    @staticmethod
    def fromNamespaceAndPath(namespace, path):
        return ResourceLocation(namespace, path)

    @staticmethod
    def parse(text):
        return ResourceLocation(text)

    @staticmethod
    def tryParse(text):
        """解析失败返回 None（Java 的 tryParse 语义）。"""
        try:
            return ResourceLocation(text)
        except Exception:
            return None

    def getNamespace(self):
        return self.namespace

    def getPath(self):
        return self.path

    def toString(self):
        return u"{}:{}".format(self.namespace, self.path)

    def equals(self, other):
        if not isinstance(other, ResourceLocation):
            return False
        return (self.namespace == other.namespace and self.path == other.path)

    def hashCode(self):
        from java_stdlib.lang import JavaString
        from java_stdlib.primitives import Int32
        return Int32.add(Int32.multiply(JavaString(self.namespace).hashCode(),31),JavaString(self.path).hashCode())

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<ResourceLocation {}>".format(self.toString())

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()


class ResourceKey(object):
    """
    对应 net.minecraft.resources.ResourceKey。

    Java 的泛型参数在 Python 里没有意义，这里只保留「注册表位置」——
    它决定注册项进哪张表。
    """

    _entry_keys = {}

    def __init__(self, registry_name, location=None):
        self.registry_name = java_to_string(registry_name)
        self._location = ResourceLocation(self.registry_name) if location is None else location

    @staticmethod
    def create(registry_name, *entry):
        if not entry:
            return ResourceKey(registry_name)
        from java_stdlib.lang import NullPointerException
        if len(entry) != 1:
            raise IllegalArgumentException('ResourceKey.create arity')
        if registry_name is None or entry[0] is None:
            raise NullPointerException('ResourceKey registry/location cannot be null')
        if not isinstance(registry_name,ResourceKey) or not isinstance(entry[0],ResourceLocation):
            raise IllegalArgumentException('ResourceKey.create requires registry key and location')
        identity = (registry_name.location().toString(), entry[0].toString())
        if identity not in ResourceKey._entry_keys:
            ResourceKey._entry_keys[identity] = ResourceKey(identity[0], entry[0])
        return ResourceKey._entry_keys[identity]

    def location(self):
        return self._location

    def registry(self):
        return self.registry_name

    def toString(self):
        return u"ResourceKey[{}]".format(self.registry_name)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


class Registry(object):
    """
    对应 net.minecraft.core.Registry / BuiltInRegistries 里的表。

    真实的 Minecraft 注册表在基岩版并不存在，这里的作用是：
      **提供一个稳定的身份**，让 DeferredRegister 知道条目该进哪张表，
      并在需要时按名字取回已注册的实例。
    """

    def __init__(self, name):
        self.name = java_to_string(name)
        self._entries = {}
        self._value_holders={}
        self._tags={}
        self._block_item_links=[]

    def put(self, location, value):
        if self.name == u'minecraft:block':
            from minecraft.block import Block
            if isinstance(value, Block):
                existing = Block.getRegistryName(value)
                if existing is not None and existing != java_to_string(location):
                    raise IllegalStateException('Block already belongs to another registry ID')
                Block.setRegistryName(value, location)
        if self.name == u'minecraft:item':
            from minecraft.item import Item, BlockItem
            if isinstance(value,Item):
                existing = Item.getRegistryName(value)
                if existing is not None and existing != java_to_string(location):
                    raise IllegalStateException('Item already belongs to another registry ID')
                Item.setRegistryName(value,location)
                if isinstance(value, BlockItem):
                    # NeoForge ItemCallbacks.onAdd invokes this virtual hook.
                    # Keep the identity links owned by this registry so failed
                    # activation and session close can restore prior bindings.
                    from minecraft.block import Block
                    mapping = {}
                    value.registerBlocks(mapping, value)
                    if any(not isinstance(block, Block) or not isinstance(item, Item)
                           for block, item in mapping.items()):
                        raise IllegalStateException('Unsupported block/item registration mapping')
                    for block, item in mapping.items():
                        previous = getattr(block, '_item', None)
                        self._block_item_links.append((block, previous, item))
                        Block.setItem(block, item)
        holder=self._holder_for_value(value)
        self._entries[java_to_string(location)] = value
        holder._key=java_to_string(location)
        return value

    def _holder_for_value(self,value):
        from minecraft.registries import ReferenceHolder
        from java_stdlib.lang import NullPointerException
        if value is None:raise NullPointerException()
        key=id(value)
        if key not in self._value_holders:self._value_holders[key]=ReferenceHolder(self,value)
        return self._value_holders[key]

    def getOrCreateTag(self,key):
        from minecraft.holder_sets import Named
        identity=id(key)
        if identity not in self._tags:self._tags[identity]=Named(self,key)
        return self._tags[identity]

    def getTag(self,key):
        from java_stdlib.util import Optional
        return Optional.ofNullable(self._tags.get(id(key)))

    def canSerializeIn(self,owner):return self is owner

    def bindTags(self,bindings):
        from minecraft.registries import ReferenceHolder
        from java_stdlib.lang import NullPointerException
        if bindings is None:raise NullPointerException()
        entries=[(e.getKey(),e.getValue()) for e in bindings.entrySet()] if hasattr(bindings,'entrySet') else list(bindings.items())
        pending={id(h):[] for h in self._value_holders.values()}
        checked=[]
        for key,holders in entries:
            if holders is None:raise NullPointerException()
            values=list(holders)
            for holder in values:
                if not isinstance(holder,ReferenceHolder) or holder._owner is not self or holder._key is None:raise IllegalStateException('Tag member must be a reference registered in this registry')
                pending[id(holder)].append(key)
            checked.append((key,values))
        for key,values in checked:self.getOrCreateTag(key).bind(values)
        for holder in self._value_holders.values():holder.bindTags(pending[id(holder)])

    def resetTags(self):
        for named in self._tags.values():named.bind([])
        for holder in self._value_holders.values():holder.bindTags([])

    def get(self, location):
        """Java 语义：取不到返回 null（这里返回 None），不抛异常。"""
        return self._entries.get(java_to_string(location))

    def containsKey(self, location):
        return java_to_string(location) in self._entries

    def keySet(self):
        return sorted(self._entries.keys())

    def size(self):
        return len(self._entries)

    def clear(self):
        from minecraft.block import Block
        for block, previous, item in reversed(self._block_item_links):
            if getattr(block, '_item', None) is item:
                Block.setItem(block, previous)
        self._block_item_links=[]
        self._entries = {}
        self._value_holders={};self._tags={}

    def __repr__(self):
        return u"<Registry {} size={}>".format(self.name, len(self._entries))


# ============================================================
# 注册表集合
# ============================================================

_KNOWN_REGISTRIES = (
    "ITEM", "BLOCK", "MENU", "ATTRIBUTE", "ENTITY_TYPE",
    "BLOCK_ENTITY_TYPE", "RECIPE_SERIALIZER", "DATA_COMPONENT_TYPE",
    "MOB_EFFECT", "ENCHANTMENT", "SOUND_EVENT", "PARTICLE_TYPE",
    "FLUID", "CREATIVE_MODE_TAB", "RECIPE_TYPE", "POTION",
    "VILLAGER_PROFESSION", "COMMAND_ARGUMENT_TYPE", "LOOT_POOL_ENTRY_TYPE",
)

_KNOWN_NEOFORGE_KEYS = (
    "INGREDIENT", "ATTACHMENT", "FLUID_TYPE", "GLOBAL_LOOT_MODIFIER",
    "CONDITION_CODECS", "ENTITY_DATA_SERIALIZER", "STRUCTURE_MODIFIER",
    "HOLDER_SET_OPERATOR", "FEATURE", "BIOME_MODIFIER",
)


class BuiltInRegistries(object):
    """
    对应 net.minecraft.core.registries.BuiltInRegistries。

    为什么用 __getattr__ 懒加载而不是逐个写字段：
      真实模组引用到的注册表有十几种，逐个写字段既啰嗦又容易漏。
      懒加载保证「用到哪个就建哪个」，且同一名字始终返回同一个对象。
    拼错名字会报错（有已知名单兜底），而不是悄悄造一张新表。
    """

    def __init__(self):
        self._registries = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in _KNOWN_REGISTRIES:
            raise AttributeError(
                u"BuiltInRegistries 里没有 {}（已知：{}）".format(
                    name, u", ".join(_KNOWN_REGISTRIES)))
        if name not in self._registries:
            self._registries[name] = Registry(
                u"minecraft:{}".format(name.lower()))
        return self._registries[name]

    def clear(self):
        self._registries = {}

    def __repr__(self):
        return u"<BuiltInRegistries {} 张表>".format(len(self._registries))


class Registries(object):
    """
    对应 net.minecraft.core.registries.Registries。

    与 BuiltInRegistries 的差别：这里成员是 **ResourceKey** 而非注册表实例，
    真实代码写的是 DeferredRegister.create(Registries.CREATIVE_MODE_TAB, modid)。
    """

    def __init__(self):
        self._keys = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in _KNOWN_REGISTRIES:
            raise AttributeError(
                u"Registries 里没有 {}（已知：{}）".format(
                    name, u", ".join(_KNOWN_REGISTRIES)))
        if name not in self._keys:
            self._keys[name] = ResourceKey(u"minecraft:{}".format(name.lower()))
        return self._keys[name]

    def clear(self):
        self._keys = {}

    def __repr__(self):
        return u"<Registries {} 个键>".format(len(self._keys))


# NeoForge 1.21.1 public names and actual resource paths.
_NEOFORGE_PATHS = {
    "ATTACHMENT_TYPES": "attachment_types",
    "ENTITY_DATA_SERIALIZERS": "entity_data_serializers",
    "GLOBAL_LOOT_MODIFIER_SERIALIZERS": "global_loot_modifier_serializers",
    "BIOME_MODIFIER_SERIALIZERS": "biome_modifier_serializers",
    "STRUCTURE_MODIFIER_SERIALIZERS": "structure_modifier_serializers",
    "FLUID_TYPES": "fluid_type", "HOLDER_SET_TYPES": "holder_set_type",
    "INGREDIENT_TYPES": "ingredient_serializer",
    "FLUID_INGREDIENT_TYPES": "fluid_ingredient_type",
    "CONDITION_CODECS": "condition_codecs",
    "BIOME_MODIFIERS": "biome_modifier", "STRUCTURE_MODIFIERS": "structure_modifier",
}


class _NeoForgeKeys(object):
    """对应 NeoForgeRegistries.Keys。"""

    def __init__(self):
        self._keys = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in _KNOWN_NEOFORGE_KEYS and name not in _NEOFORGE_PATHS:
            raise AttributeError(
                u"NeoForgeRegistries.Keys 里没有 {}（已知：{}）".format(
                    name, u", ".join(_KNOWN_NEOFORGE_KEYS)))
        if name not in self._keys:
            self._keys[name] = ResourceKey(u"neoforge:{}".format(_NEOFORGE_PATHS.get(name, name.lower())))
        return self._keys[name]

    def clear(self):
        self._keys = {}

    def __repr__(self):
        return u"<NeoForgeRegistries.Keys {} 个键>".format(len(self._keys))


class NeoForgeRegistries(object):
    """对应 net.neoforged.neoforge.registries.NeoForgeRegistries。"""

    def __init__(self):
        self.Keys = _NeoForgeKeys()
        self._registries = {}

    def __getattr__(self, name):
        if name == "CONDITION_SERIALIZERS":
            key = self.Keys.CONDITION_CODECS
        elif name in _NEOFORGE_PATHS and name not in ("BIOME_MODIFIERS", "STRUCTURE_MODIFIERS", "CONDITION_CODECS"):
            key = getattr(self.Keys, name)
        else:
            raise AttributeError(name)
        if name not in self._registries:
            self._registries[name] = Registry(key.registry())
        return self._registries[name]

    def clear(self):
        self.Keys.clear()
        self._registries.clear()

    def __repr__(self):
        return u"<NeoForgeRegistries>"


# 单例：Java 里这些是静态字段，全局唯一
BUILT_IN_REGISTRIES = BuiltInRegistries()
REGISTRIES = Registries()
NEOFORGE_REGISTRIES = NeoForgeRegistries()


def reset_registries():
    """清空所有注册表（自测与重载用）。"""
    BUILT_IN_REGISTRIES.clear()
    REGISTRIES.clear()
    NEOFORGE_REGISTRIES.clear()


# ============================================================
# DeferredHolder
# ============================================================

class DeferredHolder(object):
    """
    对应 net.neoforged.neoforge.registries.DeferredHolder。

    它是**惰性引用**：register 时只登记名字与工厂，
    真正创建对象在「注册事件」触发时发生。

    为什么必须实现 __getattr__ 转发：
      模组代码常把 holder 直接当被注册对象用（传进菜单、当 ItemLike）。
      没有转发的话 holder.getDamage() 这类调用会 AttributeError。
    """

    def __init__(self, registry_key, location, factory=None, value=None):
        self.registry_key = registry_key
        self.location = location
        self._factory = factory
        self._value = value
        self._bound = value is not None
        self._registry = None

    # ---------------- 惰性求值 ----------------

    def get(self):
        """Read an existing registry entry; never evaluate its supplier here."""
        if not self.isBound():
            from java_stdlib.lang import NullPointerException
            if self._find_registry() is None:
                raise IllegalStateException("Registry not present for " + java_to_string(self.location))
            raise NullPointerException("Trying to access unbound value: " + java_to_string(self.location))
        return self._value

    def isBound(self):
        if not self._bound:
            registry = self._find_registry()
            if registry is not None:
                value = registry.get(self.location.toString())
                if value is not None:
                    self.bindValue(value)
        return self._bound

    def _find_registry(self):
        if self._registry is not None:
            return self._registry
        name = self.registry_key.registry()
        for field in _KNOWN_REGISTRIES:
            if name == u"minecraft:" + field.lower():
                return getattr(BUILT_IN_REGISTRIES, field)
        for field, path in _NEOFORGE_PATHS.items():
            if name == u"neoforge:" + path and field not in (
                    "BIOME_MODIFIERS", "STRUCTURE_MODIFIERS", "CONDITION_CODECS"):
                return getattr(NEOFORGE_REGISTRIES, field)
        return None

    def bindValue(self, value):
        """注册流程用它把真实对象塞进来。"""
        if value is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException("Registry values cannot be null")
        self._value = value
        self._bound = True
        return value

    def getId(self):
        return self.location

    def getKey(self):
        return self.registry_key

    def value(self):
        return self.get()

    # ---------------- 当对象本身用 ----------------

    def __getattr__(self, name):
        # 只转发「非内部」属性，避免把 _factory / _value 的查找也拦下来
        if name.startswith(u"_"):
            raise AttributeError(name)
        return getattr(self.get(), name)

    def __call__(self, *args, **kwargs):
        target = self.get()
        if not callable(target):
            raise IllegalStateException(
                u"DeferredHolder {} 的值不可调用".format(self.location))
        return target(*args, **kwargs)

    def __str__(self):
        return java_to_string(self.location)

    def __repr__(self):
        if self._bound:
            return u"<DeferredHolder {} -> {!r}>".format(self.location, self._value)
        return u"<DeferredHolder {} (未求值)>".format(self.location)

    def __eq__(self, other):
        if isinstance(other, DeferredHolder):
            return self.location == other.location
        return self.get() == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(java_to_string(self.location))


# ============================================================
# DeferredRegister
# ============================================================

class DeferredRegister(object):
    """
    对应 net.neoforged.neoforge.registries.DeferredRegister。

    创建方式（真实代码都用到了）：
        DeferredRegister.create(registry_or_key, modid)
        DeferredRegister.createBlocks(modid)          # 等价 create(BLOCK, modid)
        DeferredRegister.createItems(modid)
        DeferredRegister.createDataComponents(modid)
        DeferredRegister.createEntities(modid)
    """

    def __init__(self, registry_key, modid):
        if isinstance(registry_key, ResourceKey):
            self.registry_key = registry_key
        else:
            # 传进来的是注册表实例：转成 ResourceKey
            name = getattr(registry_key, "name", java_to_string(registry_key))
            self.registry_key = ResourceKey(name)
        self.modid = java_to_string(modid)
        self._entries = {}
        self._entry_order = []
        self._event_bus = None
        self._frozen = False

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def create(registry_key, modid):
        return DeferredRegister(registry_key, modid)

    @staticmethod
    def createBlocks(modid):
        return DeferredRegister.Blocks(modid)

    @staticmethod
    def createItems(modid):
        return DeferredRegister.Items(modid)

    @staticmethod
    def createDataComponents(modid):
        return DeferredRegister(ResourceKey(u"minecraft:data_component_type"), modid)

    @staticmethod
    def createEntities(modid):
        return DeferredRegister(ResourceKey(u"minecraft:entity_type"), modid)

    @staticmethod
    def createBlockEntities(modid):
        return DeferredRegister(ResourceKey(u"minecraft:block_entity_type"), modid)

    # ---------------- 注册项 ----------------

    def register(self, name, factory=None):
        """
        登记一个注册项，返回 DeferredHolder。

        name 可以是路径（"crafting_manaita"）或完整位置（"modid:crafting_manaita"）。
        factory 是零参可调用对象（Java 的 Supplier，如 CraftingBlock::new）。
        """
        if factory is None and callable(getattr(name, "register_registry", None)):
            return self.register_event_bus(name)
        if self._frozen:
            raise IllegalStateException(
                u"注册器 {} 已完成注册，不能再添加条目".format(self.modid))

        text = java_to_string(name)
        if u":" in text:
            location = ResourceLocation(text)
        else:
            location = ResourceLocation(self.modid, text)

        path = location.getPath()
        if path in self._entries:
            raise IllegalArgumentException(
                u"{} 里已经注册过 {} 了".format(self.modid, path))

        holder = self._new_holder(location, factory)
        self._entries[path] = holder
        self._entry_order.append(path)
        return holder

    def _new_holder(self, location, factory):
        return DeferredHolder(self.registry_key, location, factory=factory)

    def getEntries(self):
        """Return holders in insertion order, as the official LinkedHashMap."""
        return [self._entries[key] for key in self._entry_order]

    def size(self):
        return len(self._entries)

    def contains(self, name):
        return java_to_string(name).split(u":")[-1] in self._entries

    def getHolder(self, name):
        return self._entries.get(java_to_string(name).split(u":")[-1])

    # ---------------- 绑定事件总线 ----------------

    def register_event_bus(self, event_bus):
        """
        对应 Java 的 `BLOCKS.register(modEventBus)`。

        名字带下划线是因为 Java 那边是**重载**
        （register(String, Supplier) 与 register(IEventBus)），
        Python 没有重载 —— 这是本层统一的规避方式（与 Boolean.toStringValue 同理）。
        register(bus) 现在直接分派到此方法；旧方法名保留向后兼容。
        """
        if self._event_bus is not None:
            raise IllegalStateException("Cannot register DeferredRegister to more than one event bus.")
        if event_bus is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException("Event bus cannot be null")
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.register_registry(self)
        return None

    def isBoundToEventBus(self):
        return self._event_bus is not None

    # ---------------- 执行注册 ----------------

    def freeze_and_register(self, registry=None):
        """
        真正把登记项建成对象并写进注册表（对应「注册事件触发时」）。

        返回 {路径: 值}。没有工厂的条目会在这一步报错 ——
        「登记了却造不出对象」说明模组代码有问题，不该静默跳过。
        """
        created = {}
        # This internal barrier is not a complete NeoForge RegisterEvent. It
        # models supplier order/binding, leaving engine registration separate.
        if registry is None:
            registry = Registry(self.registry_key.registry())
            context = getattr(self._event_bus, '_mod_context', None)
            if context is not None:
                context.on_close(registry.clear)
        self._frozen = True
        for holder in self.getEntries():
            holder._registry = registry
        for holder in self.getEntries():
            path = holder.location.getPath()
            if holder._bound:
                value = holder.get()
                registry.put(holder.location.toString(), value)
            else:
                if holder._factory is None:
                    raise IllegalStateException("Missing registration factory: " + path)
                value = holder._factory()
                if value is None:
                    from java_stdlib.lang import NullPointerException
                    raise NullPointerException("Registry values cannot be null: " + path)
                registry.put(holder.location.toString(), value)
                holder.bindValue(value)
            created[path] = value
        return created

    def __repr__(self):
        return u"<DeferredRegister {} {} 项>".format(
            self.registry_key.registry(), self.size())


# ============================================================
# 名称映射表：供翻译层查询
# ============================================================

from minecraft.official_interfaces import ItemLike


class DeferredItem(DeferredHolder, ItemLike):
    """ItemLike reads the registered item; it never invokes its factory."""
    def asItem(self):
        return self.get()


class _DeferredItems(DeferredRegister):
    def __init__(self, modid):
        DeferredRegister.__init__(self, ResourceKey(u"minecraft:item"), modid)

    def registerSimpleBlockItem(self, *args):
        """21.1.233 overloads; block factories are read only at the item barrier.

        This registers an ordinary BlockItem, not a native placement adapter.
        Holder overloads currently support NeoCore's keyed holder forms only.
        """
        from minecraft.item import BlockItem, ItemProperties
        from minecraft.registries import Holder, ReferenceHolder
        from java_stdlib.lang import NullPointerException, ClassCastException
        try:
            string_type = basestring
        except NameError:
            string_type = str
        if len(args) in (2, 3) and isinstance(args[0], string_type):
            name, block = args[:2]
            properties = args[2] if len(args) == 3 else ItemProperties()
            # A null Supplier is captured by the official lambda and fails
            # when evaluated; do not call it while collecting declarations.
            def null_supplier():raise NullPointerException('Block supplier cannot be null')
            read = null_supplier if block is None else getattr(block, 'get', None)
            if not callable(read):
                if not callable(block):raise ClassCastException('Expected block Supplier')
                read = block
        elif len(args) in (1, 2):
            block = args[0]
            if block is None:raise NullPointerException('Block holder cannot be null')
            properties = args[1] if len(args) == 2 else ItemProperties()
            if isinstance(block, DeferredHolder):
                if block.registry_key.registry() != u'minecraft:block':
                    raise ClassCastException('Expected Holder<Block>')
                name = block.location.getPath()
            elif isinstance(block, Holder):
                key = block.unwrapKey()
                if key is None:
                    from java_stdlib.util import NoSuchElementException
                    raise NoSuchElementException('No value present')
                if isinstance(block, ReferenceHolder) and isinstance(key, string_type) and block._owner.name == u'minecraft:block':
                    name = ResourceLocation(key).getPath()
                elif not isinstance(key, ResourceKey) or key.registry() != u'minecraft:block':
                    raise ClassCastException('Expected a keyed Holder<Block>')
                else:name = key.location().getPath()
            else:raise ClassCastException('Expected Holder<Block>')
            read = block.value
        else:raise IllegalArgumentException('registerSimpleBlockItem overload')
        def create():
            from minecraft.block import Block
            value = read()
            if value is not None and not isinstance(value, Block):raise ClassCastException('Block supplier returned a non-Block')
            if properties is None:raise NullPointerException('Item properties cannot be null')
            if not isinstance(properties, ItemProperties):raise ClassCastException('Expected Item.Properties')
            return BlockItem(value, properties)
        return self.register(name, create)

    def _new_holder(self, location, factory):
        from java_stdlib.lang import NullPointerException, ClassCastException
        from java_stdlib.function import Function
        if factory is None:
            raise NullPointerException("Item supplier cannot be null")
        if isinstance(factory, Function):
            invoke = lambda: factory.apply(location)
        else:
            invoke = getattr(factory, 'get', None)
            if not callable(invoke):
                invoke = factory
            if not callable(invoke):
                raise ClassCastException("Expected item Supplier or Function")
        def create():
            from minecraft.item import Item
            value = invoke()
            if value is None:
                raise NullPointerException("Item supplier returned null")
            if not isinstance(value, Item):
                raise ClassCastException("Item supplier returned a non-Item")
            return value
        return DeferredItem(self.registry_key, location, factory=create)


class DeferredBlock(DeferredHolder, ItemLike):
    def asItem(self):
        return self.get().asItem()


class _DeferredBlocks(DeferredRegister):
    def __init__(self, modid):
        DeferredRegister.__init__(self, ResourceKey(u"minecraft:block"), modid)

    def _new_holder(self, location, factory):
        from java_stdlib.lang import NullPointerException, ClassCastException
        from java_stdlib.function import Function
        if factory is None:
            raise NullPointerException("Block supplier cannot be null")
        if isinstance(factory, Function):
            invoke = lambda: factory.apply(location)
        else:
            invoke = getattr(factory, 'get', None)
            if not callable(invoke):invoke = factory
            if not callable(invoke):raise ClassCastException("Expected block Supplier or Function")
        def create():
            from minecraft.block import Block
            value = invoke()
            if value is None:raise NullPointerException("Block supplier returned null")
            if not isinstance(value, Block):raise ClassCastException("Block supplier returned a non-Block")
            return value
        return DeferredBlock(self.registry_key, location, factory=create)


DeferredRegister.Blocks = _DeferredBlocks


DeferredRegister.Items = _DeferredItems


JAVA_MAP = {
    "net.neoforged.neoforge.registries.DeferredRegister": DeferredRegister,
    "net.neoforged.neoforge.registries.DeferredRegister$Items": _DeferredItems,
    "net.neoforged.neoforge.registries.DeferredHolder": DeferredHolder,
    "net.neoforged.neoforge.registries.DeferredBlock": DeferredBlock,
    "net.neoforged.neoforge.registries.DeferredRegister$Blocks": _DeferredBlocks,
    "net.neoforged.neoforge.registries.DeferredItem": DeferredItem,
    "net.minecraft.resources.ResourceLocation": ResourceLocation,
    "net.minecraft.resources.ResourceKey": ResourceKey,
    "net.minecraft.core.Registry": Registry,
    "net.minecraft.core.registries.BuiltInRegistries": BUILT_IN_REGISTRIES,
    "net.minecraft.core.registries.Registries": REGISTRIES,
    "net.neoforged.neoforge.registries.NeoForgeRegistries": NEOFORGE_REGISTRIES,
}


__all__ = [
    "ResourceLocation", "ResourceKey", "Registry",
    "BuiltInRegistries", "Registries", "NeoForgeRegistries",
    "BUILT_IN_REGISTRIES", "REGISTRIES", "NEOFORGE_REGISTRIES",
    "reset_registries",
    "DeferredHolder", "DeferredRegister",
    "JAVA_MAP",
]

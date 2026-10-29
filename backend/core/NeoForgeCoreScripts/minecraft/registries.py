# -*- coding: utf-8 -*-
# minecraft/registries.py
# θ 层：注册表相关类型（Holder / HolderLookup / TagKey）
#
# 真实用法（逐字来自反编译源码）：
#
#   // Holder<T> —— 注册项句柄
#   level.gameEvent(GameEvent.BLOCK_PLACE, blockpos, GameEvent.Context.of(...));
#   public static final DeferredHolder<CreativeModeTab, CreativeModeTab> MANAITA_PLUS_TAB;
#
#   // HolderLookup.Provider —— 注册表访问入口（真实 12 个文件引用）
#   protected void loadAdditional(CompoundTag tag, HolderLookup.Provider registries)
#   protected void saveAdditional(CompoundTag tag, HolderLookup.Provider registries)
#   er.saveAllItems(tag, this.items, registries);
#   recipe.value()).assemble(new SingleRecipeInput(input), registryAccess);
#
#   // TagKey<T> —— 标签键（真实：ToolTier 用它声明「挖不动的方块」）
#   public TagKey<Block> getIncorrectBlocksForDrops()
#   public static final TagKey<Block> MINEABLE =
#       BlockTags.create(ResourceLocation.fromNamespaceAndPath(...))
#
# 与 neoforge/registries.py 的分工：
#   那边是**注册流程**（DeferredRegister / Registry / ResourceLocation）；
#   这边是**注册项的引用形式**（Holder / HolderLookup / TagKey），
#   也就是「拿到注册项之后怎么传、怎么存、怎么读」。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore


# ============================================================
# Holder
# ============================================================

def _is_dunder(name):
    """判断是不是 `__xxx__` 形式的名字。"""
    return len(name) > 4 and name.startswith(u"__") and name.endswith(u"__")


class Holder(object):
    """
    对应 net.minecraft.core.Holder。

    Holder 是「对注册项的一个引用」：它可以指向已注册的值，
    也可以只是一个**未绑定的键**（值还没注册进来时）。

    为什么需要这一层间接：
      `level.gameEvent(GameEvent.BLOCK_PLACE, ...)` 传的不是 GameEvent 本身，
      而是它的 Holder。这样即使注册表还没建好，也能先持有引用。

    真实代码里 Holder 常被写成 `Holder<GameEvent>` 这种泛型，
    翻译成 Python 后泛型消失，只剩这个类。
    """

    def __init__(self, value=None, key=None):
        self._value = value
        self._key = key          # ResourceKey 或名字

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def direct(value, key=None):
        """对应 Holder.direct(T)：直接包一个值，与注册表无关。"""
        return DirectHolder(value) if key is None else Holder(value,key)

    @staticmethod
    def of(value, key=None):
        """本实现新增的便利入口（真实代码没这个名字，但语义等价）。"""
        return Holder(value, key)

    # ---------------- 取值 ----------------

    def value(self):
        """
        对应 value()：取注册项本身。

        未绑定（还没注册）时抛异常 —— 与 Java 一致：
        Java 会抛 IllegalStateException（"Trying to access value of unbound holder"），
        而不是返回 null。这样空引用会**当场暴露**，不会静默传播。
        """
        if self._value is None:
            raise IllegalStateException(
                u"Holder 尚未绑定值（key={}）".format(
                    java_to_string(self._key) if self._key else u"无"))
        return self._value

    def isBound(self):
        """对应 isBound()：是否已经指向一个真实值。"""
        return self._value is not None

    def isTag(self,tag):return False

    def get(self):
        """
        DeferredHolder 风格的安全取值：未绑定时返回 None。

        与 value() 的区别是「不抛异常」—— 需要探测的场合用这个。
        """
        return self._value

    def key(self):
        """对应 unwrapKey()：取 ResourceKey。"""
        return self._key

    def unwrapKey(self):
        return self._key

    def bindValue(self, value):
        """绑定值（对应 DeferredHolder.bindValue）。"""
        self._value = value
        return None

    # ---------------- 属性转发 ----------------

    def __getattr__(self, name):
        """
        把属性访问转发给被持有的值。

        为什么需要：真实代码会把 Holder 当值本身用
        （例如 GameEvent.BLOCK_PLACE 的 Holder 被拿去查名字）。
        没有转发就会 AttributeError。

        **两个必须排除的情况**（实测踩到）：

        1. 下划线开头（`_value` 等）—— 否则 `hasattr` 和内部访问会递归。
        2. dunder（`__iter__` / `__len__` / `__deepcopy__` ...）——
           Python 的协议方法会走类型槽位，转发出去会把
           「探测某个能力」变成「真的调用那个能力」。
           实测：`hasattr(holder, "copy")` 触发了被持有值的 `iter(...)`，
           直接抛 `TypeError: argument of type 'Holder' is not iterable`。
           真实代码里 `hasattr` / `getattr(..., default)` 到处都是，
           不排除的话会莫名其妙地崩。
        """
        if name.startswith(u"_") or _is_dunder(name):
            raise AttributeError(name)

        value = object.__getattribute__(self, "_value")
        if value is None:
            raise AttributeError(
                u"Holder 未绑定，无法访问 {}".format(name))
        return getattr(value, name)

    # ---------------- 身份 ----------------

    def equals(self, other):
        if not isinstance(other, Holder):
            return False
        if self._key is not None and other._key is not None:
            return self._key == other._key
        return self._value is other._value

    def hashCode(self):
        return hash_code(java_to_string(self._key)
                         if self._key is not None else u"holder")

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        if self._value is not None:
            return java_to_string(self._value)
        return u"Holder[{}]".format(java_to_string(self._key)
                                    if self._key else u"未绑定")

    def __repr__(self):
        return u"<{}>".format(self.__str__())


# ============================================================
# HolderLookup.Provider
# ============================================================

class DirectHolder(Holder):
    def value(self):return self._value
    def isBound(self):return True
    def equals(self,other):
        from java_stdlib._base import equals
        return isinstance(other,DirectHolder) and equals(self._value,other._value)
    def hashCode(self):
        from java_stdlib.lang import JavaString
        from java_stdlib.primitives import Int32
        return JavaString(self._value).hashCode() if isinstance(self._value,(str,type(u''))) else Int32.wrap(hash_code(self._value))

class ReferenceHolder(Holder):
    def __init__(self,owner,value,key=None):Holder.__init__(self,value,key);self._owner=owner;self._tags=set()
    def isTag(self,tag):return tag in self._tags
    def bindTags(self,tags):
        from java_stdlib.lang import NullPointerException
        tags=list(tags)
        if any(t is None for t in tags):raise NullPointerException()
        self._tags=set(tags)
    def canSerializeIn(self,owner):return self._owner is owner
    def equals(self,other):return self is other
    def hashCode(self):
        from java_stdlib.lang import System
        return System.identityHashCode(self)

class HolderLookup(object):
    """
    对应 net.minecraft.core.HolderLookup。

    Java 里它是接口，`HolderLookup.Provider` 是内部子接口，
    代表「能按注册表名取到 Holder 集合」的东西。

    真实代码把它当**读写存档时的注册表上下文**用：
        loadAdditional(CompoundTag tag, HolderLookup.Provider registries)
        saveAdditional(CompoundTag tag, HolderLookup.Provider registries)
    也就是说：反序列化物品/方块需要知道注册表里有什么。

    内部结构是两层字典：`{注册表名: {项名: Holder}}`。
    `lookup(...)` 返回的是**限定到某一个注册表**的视图（scope），
    这样 `block_lookup.get("stone")` 不会意外命中别的注册表里的同名项 ——
    真实代码里方块和物品都可能有 "stone"，混起来会取错东西。
    """

    def __init__(self, registries=None, scope=None):
        # {注册表名: {项名: Holder}}
        self._registries = registries if registries is not None else {}
        # 限定到的注册表名；None 表示「看全部」
        self._scope = java_to_string(scope) if scope is not None else None

    # ---------------- 查询 ----------------

    def lookup(self, registry_key):
        """
        对应 lookup(ResourceKey)：取某个注册表的查找器。

        取不到时返回一个**空的** HolderLookup 而不是 None ——
        真实代码会直接在上面 `.getOrThrow(...)`，返回 None 会 NPE，
        而空查找器会给出「找不到 XXX」这种能看懂的错。
        """
        name = self._registry_name(registry_key)
        found = self._registries.get(name)
        if found is None:
            # 空查找器也要带 scope，这样报错信息能指出是哪个注册表缺东西
            return HolderLookup({}, name)
        return HolderLookup(self._registries, name)

    def _iter_visible(self):
        """
        产出当前可见的 (注册表名, {项名: Holder})。

        被 scope 限定在单个注册表时只产出那一个。
        """
        if self._scope is not None:
            registry = self._registries.get(self._scope)
            if registry is not None:
                yield self._scope, registry
            return
        for registry_name in sorted(self._registries):
            yield registry_name, self._registries[registry_name]

    def get(self, key):
        """按名字取 Holder；没有返回 None（对应 Optional 语义）。"""
        name = java_to_string(key)
        for _registry_name, registry in self._iter_visible():
            if name in registry:
                return registry[name]
        return None

    def getOrThrow(self, key):
        """
        对应 getOrThrow(...)：取不到就抛异常。

        真实代码里这个方法到处用（反序列化时找不到注册项是硬错误）。
        """
        found = self.get(key)
        if found is None:
            raise IllegalArgumentException(
                u"注册表{}里找不到 {}".format(
                    u"[{}]".format(self._scope) if self._scope else u"",
                    java_to_string(key)))
        return found

    def listRegistryKeys(self):
        """列出可见的注册表名（被 scope 限定时就只有一个）。"""
        return sorted([name for name, _registry in self._iter_visible()])

    def listNames(self, registry_key=None):
        if registry_key is not None:
            name = self._registry_name(registry_key)
            return sorted(self._registries.get(name, {}).keys())
        names = []
        for _registry_name, registry in self._iter_visible():
            names.extend(registry.keys())
        return sorted(names)

    def hasRegistry(self, registry_key):
        name = self._registry_name(registry_key)
        return name in self._registries

    def getScope(self):
        """当前限定到的注册表名（None 表示看全部）。"""
        return self._scope

    def isEmpty(self):
        for _registry_name, registry in self._iter_visible():
            if registry:
                return False
        return True

    # ---------------- 装配 ----------------

    def register(self, registry_name, item_name, value):
        """把一个值登记进某个注册表，并返回它的 Holder。"""
        registry = java_to_string(registry_name)
        item = java_to_string(item_name)
        holder = Holder(value, u"{}:{}".format(registry, item))
        self._registries.setdefault(registry, {})[item] = holder
        return holder

    @staticmethod
    def _registry_name(registry_key):
        """把 ResourceKey / 字符串 / 别的什么统一成注册表名字符串。"""
        if registry_key is None:
            return u""
        # TagKey 有自己的 registry()，要先认它 —— 它的 location 是标签名，
        # 不是注册表名。
        if isinstance(registry_key, TagKey):
            return registry_key.registry()
        if hasattr(registry_key, "registry") and callable(
                getattr(registry_key, "registry")):
            return java_to_string(registry_key.registry())
        if hasattr(registry_key, "location"):
            return java_to_string(registry_key.location)
        return java_to_string(registry_key)

    def __repr__(self):
        scope = u" scope={}".format(self._scope) if self._scope else u""
        return u"<HolderLookup {} 个注册表{}>".format(
            len(self.listRegistryKeys()), scope)


# Java 里 Provider 是 HolderLookup 的内部接口
HolderLookup.Provider = HolderLookup


# ============================================================
# TagKey / Tag
# ============================================================

class TagKey(object):
    """
    对应 net.minecraft.tags.TagKey。

    真实用法：
        public static final TagKey<Block> MINEABLE =
            BlockTags.create(ResourceLocation.fromNamespaceAndPath(...))
        public TagKey<Block> getIncorrectBlocksForDrops()
        ManaitaPlusLegacyToolBase(TagKey<Block> tagKey)

    标签是「一组注册项的集合」的**名字**；
    真正的内容在数据包里，由 TagKey 去查。
    """

    _interned={}
    def __init__(self, registry_name, location):
        if hasattr(registry_name,'location') and callable(registry_name.location):registry_name=registry_name.location()
        self._registry = java_to_string(registry_name)
        self._location = location    # ResourceLocation 或字符串

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def create(registry_name, location):
        """对应 TagKey.create(ResourceKey, ResourceLocation)。"""
        value=TagKey(registry_name,location);key=(value.registry(),value.location())
        if key not in TagKey._interned:TagKey._interned[key]=value
        return TagKey._interned[key]

    # ---------------- 查询 ----------------

    def location(self):
        """对应 location()：标签的资源位置。"""
        if hasattr(self._location, "toString"):
            return self._location.toString()
        return java_to_string(self._location)

    def registry(self):
        """对应 registry()：所属注册表名。"""
        return self._registry

    def isFor(self, registry_name):
        """对应 isFor(ResourceKey)：是不是某个注册表的标签。"""
        return self._registry == java_to_string(registry_name)

    # ---------------- 身份 ----------------

    def equals(self, other):
        if not isinstance(other, TagKey):
            return False
        return other._registry == self._registry \
            and other.location() == self.location()

    def hashCode(self):
        return hash_code(u"{}|{}".format(self._registry, self.location()))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def toString(self):
        return u"TagKey[{} / {}]".format(self._registry, self.location())

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


class Tag(object):
    """
    对应 net.minecraft.tags.Tag —— 「这个注册项属于哪些标签」的载体。

    真实代码里它只被当作 NBT 写入的容器用
    （`put("RecipesUsed", tag)`），本实现保持轻量。
    """

    def __init__(self):
        self._entries = []

    def add(self, holder):
        self._entries.append(holder)
        return None

    def contains(self, holder):
        for entry in self._entries:
            if entry == holder:
                return True
        return False

    def size(self):
        return len(self._entries)

    def toList(self):
        return list(self._entries)

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __repr__(self):
        return u"<Tag {} 项>".format(len(self._entries))


# ============================================================
# RegistryAccess
# ============================================================

class RegistryAccess(object):
    """
    对应 net.minecraft.core.RegistryAccess。

    真实代码：`assemble(input, registryAccess)` / `RegistryAccess registryAccess`
    —— 它是「取注册表」的入口，语义与 HolderLookup.Provider 高度重叠
    （实际 Java 里后者继承自前者的能力）。
    """

    def __init__(self, lookup=None):
        self._lookup = lookup if lookup is not None else HolderLookup()

    def registryOrThrow(self, registry_key):
        return self._lookup.lookup(registry_key)

    def lookupOrThrow(self, registry_key):
        return self._lookup.lookup(registry_key)

    def getLookup(self):
        return self._lookup

    def registries(self):
        return self._lookup.listRegistryKeys()

    def __repr__(self):
        return u"<RegistryAccess {} 个注册表>".format(
            len(self._lookup.listRegistryKeys()))


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.core.Holder": Holder,
    "net.minecraft.core.Holder$Reference": ReferenceHolder,
    "net.minecraft.core.Holder$Direct": DirectHolder,
    "net.minecraft.core.HolderLookup": HolderLookup,
    "net.minecraft.core.HolderLookup$Provider": HolderLookup,
    "net.minecraft.core.RegistryAccess": RegistryAccess,
    "net.minecraft.tags.TagKey": TagKey,
    "net.minecraft.tags.Tag": Tag,
}


__all__ = [
    "Holder", "HolderLookup", "RegistryAccess", "TagKey", "Tag",
    "JAVA_MAP",
]

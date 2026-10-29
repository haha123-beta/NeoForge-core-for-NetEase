# -*- coding: utf-8 -*-
# minecraft/item.py
# θ 层：物品（Item / ItemStack / Item.Properties）
#
# 真实用法（从反编译源码逐字提取）：
#
#   // 物品类的定义（属性走链式 Builder）
#   super(new Item.Properties().durability(-1).fireResistant());
#   super(new Item.Properties().stacksTo(1).durability(-1).fireResistant());
#
#   // 构造物品栈
#   new ItemStack((ItemLike) ManaitaPlusLegacyBlockCore.CraftingBlockItem.get())
#
#   // 实例方法（按引用次数）
#   stack.getItem() 44、stack.isEmpty() 22、stack.getCount() 21、stack.is(...) 20
#   stack.getDisplayName() 14、stack.copy() 9、stack.setCount() 8、stack.shrink() 7
#   stack.getMaxStackSize() 7、stack.grow() 7 …
#
# 两个容易写错的语义：
#   1. **数量为 0 的栈就是空栈**（isEmpty 判的是 count <= 0，不是「对象为 null」）；
#      模组代码大量依赖这一点，写成「对象存在就非空」会让逻辑全错。
#   2. getCount() 与 setCount() 的边界：Java 里 count 被夹在 0..maxStackSize 之间，
#      setCount(-1) 实际得到 0 而不是 -1。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import
import copy

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
        equals,
        hash_code,
    )
    from java_stdlib.lang import java_to_string, NullPointerException
    from minecraft.core import Component
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
        equals,
        hash_code,
    )
    from lang import java_to_string, NullPointerException  # type: ignore
    from core import Component  # type: ignore


# ============================================================
# ItemLike：能被放进物品栈的东西
# ============================================================

from minecraft.official_interfaces import ItemLike


# ============================================================
# Item.Properties：链式属性构建器
# ============================================================

class ItemProperties(object):
    """
    对应 Item.Properties。

    真实代码全是链式写法，且顺序不固定：
        new Item.Properties().durability(-1).fireResistant()
        new Item.Properties().stacksTo(1).durability(-1).fireResistant()

    所以每个设置方法都必须**返回自身**。

    durability 会写入最大损耗、将堆叠数设为 1；负数不等于 UNBREAKABLE 组件。
    """

    def __init__(self):
        self.max_stack_size = 64
        self.max_damage = 0
        self._damage_present = False
        self.fire_resistant = False
        # 字段用下划线前缀：本类有个同名的链式方法 rarity(...)，
        # 若字段也叫 self.rarity，方法定义会把它覆盖掉（Python 没有重载）。
        self._rarity = u"COMMON"
        self._unbreakable = False
        self._food = None
        self._custom_data = None
        self._craft_remainder = None
        # Reviewed Tool data used by DiggerItem. The generic public component
        # builder, codecs and component patches remain separate capabilities.
        self._tool_component = None

    # ---------------- 链式设置 ----------------

    def stacksTo(self, size):
        """设置最大堆叠数。"""
        self.max_stack_size = int(size)
        return self

    def durability(self, max_damage):
        """
        设置耐久度。

        按官方 Properties.durability 写入 maxDamage、stackSize=1 和损耗组件；
        不根据某个模组使用的负数伪造 UNBREAKABLE。
        """
        self.max_damage = int(max_damage)
        self.max_stack_size = 1
        self._damage_present = True
        return self

    def fireResistant(self):
        self.fire_resistant = True
        return self

    def rarity(self, value):
        """
        设置稀有度。

        传 Rarity 枚举时必须**保留对象本身**，不能转成字符串 ——
        真实代码会用 `== Rarity.EPIC` 做身份比较，
        转成字符串后这个比较永远为假（而且不报错）。
        """
        if isinstance(value, Rarity._Rarity):
            self._rarity = value
        else:
            self._rarity = java_to_string(value)
        return self

    def food(self, food_properties):
        self._food = food_properties
        return self

    def craftRemainder(self, item):
        """对应 craftRemainder：合成后剩下的物品（例如桶）。"""
        self._craft_remainder = item
        return self

    # ---------------- 读取 ----------------

    def getMaxStackSize(self):
        return self.max_stack_size

    def getMaxDamage(self):
        return self.max_damage

    def isFireResistant(self):
        return self.fire_resistant

    def isUnbreakable(self):
        return self._unbreakable

    def getRarity(self):
        return self._rarity

    def __repr__(self):
        return u"<Item.Properties stack={} damage={} fire={}>".format(
            self.max_stack_size, self.max_damage, self.fire_resistant)


# ============================================================
# Item
# ============================================================

class Item(ItemLike):
    ABSOLUTE_MAX_STACK_SIZE = 99

    """
    对应 net.minecraft.world.item.Item。

    Java 里的 Item 是「注册表里的类型」，不是「背包里那一格」——
    背包里的是 ItemStack。这个区分很重要：
      - Item 全局唯一，由 DeferredRegister 注册；
      - ItemStack 有数量，是每次操作的载体。

    这里不做「物品行为」（使用、挖掘、合成）—— 那些必须和引擎对接，
    属于引擎适配器的职责；本层只保证数据结构与方法签名正确。
    """

    # 全局计数器：Java 里每个 Item 有唯一 id，这里用同样的思路
    _next_id = [0]

    def onCraftedBy(self, stack, level, player):
        return self.onCraftedPostProcess(stack, level)

    def onCraftedPostProcess(self, stack, level):
        return None

    def __init__(self, properties=None, identifier=None):
        if properties is None:
            properties = ItemProperties()
        if not isinstance(properties, ItemProperties):
            raise IllegalArgumentException(
                u"Item 的构造参数应是 Item.Properties，收到 {}".format(
                    type(properties).__name__))

        self.properties = properties
        self._identifier = identifier

        Item._next_id[0] += 1
        self._id = Item._next_id[0]

        # 由 DeferredRegister 注册后填入，用于 getDescriptionId
        self._registry_name = None

    def getDefaultMaxStackSize(self):return self.properties.getMaxStackSize()
    def getDefaultInstance(self):return ItemStack(self)
    def getCraftingRemainingItem(self):return self.properties._craft_remainder
    def getEnchantmentValue(self):return 0
    def isValidRepairItem(self, stack, material):return False

    # ---------------- ItemLike ----------------

    def asItem(self):
        return self

    # ---------------- 属性 ----------------

    def getMaxStackSize(self):
        return self.properties.getMaxStackSize()

    def getMaxDamage(self):
        return self.properties.getMaxDamage()

    def isFireResistant(self):
        return self.properties.isFireResistant()

    def isDamageable(self):
        """
        对应 isDamageable()：有耐久且不是「不可损坏」才可损坏。

        注意 durability(-1) 的语义：它把 max_damage 记成 -1 并标记 unbreakable，
        所以这里判的是 unbreakable 标志与 max_damage > 0 的组合。
        """
        if self.properties.isUnbreakable():
            return False
        return self.properties.getMaxDamage() > 0

    # ---------------- 注册信息 ----------------

    def setRegistryName(self, name):
        self._registry_name = java_to_string(name)
        return self

    def getRegistryName(self):
        return self._registry_name

    def getDescriptionId(self):
        """
        对应 getDescriptionId()：语言文件里的键。

        真实代码用它取显示名。没注册时回退成一个稳定可读的形态，
        而不是 None —— 否则 getDisplayName 会跟着崩。
        """
        if self._registry_name:
            return u"item.{}".format(java_to_string(self._registry_name)
                                     .replace(u":", u"."))
        return u"item.unregistered.{}".format(self._id)

    @property
    def id(self):
        """本实现内部的唯一编号（Java 用物品实例本身做身份）。"""
        return self._id

    # ---------------- 身份 ----------------

    def equals(self, other):
        return self is other

    def hashCode(self):
        from java_stdlib.lang import System
        return System.identityHashCode(self)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __repr__(self):
        return u"<Item #{} {}>".format(self._id,
                                       self._registry_name or u"未注册")


# 让 Item.Properties 这个名字可用（Java 里是内部类）
Item.Properties = ItemProperties


class BlockItem(Item):
    """Minecraft 1.21.1 identity/registration subset; native placement is unsupported."""
    def __init__(self, block, properties):
        Item.__init__(self, properties)
        self._block = block

    def getBlock(self):
        return self._block

    def getDescriptionId(self):
        return self.getBlock().getDescriptionId()

    def registerBlocks(self, mapping, item):
        if isinstance(mapping, dict):
            mapping[self.getBlock()] = item
        else:
            mapping.put(self.getBlock(), item)

    def updatePlacementContext(self, context):
        return context

    def mustSurvive(self):
        return True

    def useOn(self, context):
        raise NotImplementedError('BlockItem.useOn requires native placement/interaction support')

    def place(self, context):
        raise NotImplementedError('BlockItem.place requires native placement support')

    def placeBlock(self, context, state):
        raise NotImplementedError('BlockItem.placeBlock requires native world placement support')

    def canFitInsideContainerItems(self):
        raise NotImplementedError('BlockItem container rules require ShulkerBoxBlock type support')


# ============================================================
# ItemStack
# ============================================================

class ItemStack(ItemLike):
    def onCraftedBy(self, level, player, amount):
        from minecraft.advancement import Stats
        player.awardStat(Stats.ITEM_CRAFTED.get(self.getItem()), amount)
        self.getItem().onCraftedBy(self, level, player)

    """
    对应 net.minecraft.world.item.ItemStack。

    这是整个模组里引用最多的类型（63 次）。核心语义：

      **空栈不是「None」，而是「count <= 0 的栈」**
        isEmpty() == (count <= 0)
      模组代码到处写 `if (stack.isEmpty())`，把它当成「对象是否存在」会全错。

      count 独立于堆叠上限；setCount 保存 Java int，空栈 getCount 返回 0。
    """

    EMPTY = None

    def __init__(self, item=None, count=1):
        # 所有字段先统一初始化，保证任何路径下属性都存在 ——
        # 曾经只在分支里创建 _custom_data，导致 copy() 时 AttributeError。
        self._item = None
        self._count = 0
        self._custom_data = None
        self._display_name = None

        # 对应 new ItemStack(ItemLike) 与 new ItemStack(ItemLike, int)
        if item is None:
            return

        if isinstance(item, ItemStack):
            # 对应 new ItemStack(ItemStack)：拷贝
            self._item = item._item
            self._count = item._count
            self._custom_data = item._custom_data
            self._display_name = item._display_name
            return

        if isinstance(item, ItemLike):
            self._item = item.asItem()
        elif isinstance(item, Item):
            self._item = item
        else:
            raise IllegalArgumentException(
                u"ItemStack 的参数应是 ItemLike，收到 {}".format(
                    type(item).__name__))

        # Java stores the requested count independently of the stacking limit.
        self.setCount(count)

    # ---------------- 基本查询 ----------------

    def getCapability(self, capability, context=None):
        from neoforge.capabilities import ItemCapability
        if not isinstance(capability, ItemCapability):
            raise IllegalArgumentException("Expected ItemCapability")
        return capability.getCapability(self, context)

    def isEmpty(self):
        """空栈的判定：数量 <= 0。**不是**判断对象是否为 None。"""
        if self is ItemStack.EMPTY or self._item is None or self._count <= 0:
            return True
        return self._item is ITEMS.AIR

    def getItem(self):
        """
        取物品类型。

        空栈返回 Items.AIR（包括原物品数量降至0的栈）。
        注意：真实代码常写 `stack.isEmpty() || stack.getItem() == ...`，
        所以这个顺序是安全的；但**不要**先 getItem 再判空。
        """
        if self.isEmpty():
            return ITEMS.AIR
        return self._item

    def getCount(self):
        return 0 if self.isEmpty() else self._count

    def setCount(self, count):
        """Store a Java int count; max stacking size does not clamp this value."""
        value = int(count)
        self._count = ((value + 2147483648) % 4294967296) - 2147483648
        return None

    def getMaxStackSize(self):
        if self.isEmpty():
            return 1
        if self._item is None:
            raise IllegalStateException("Unresolved saved item has no known stacking limit")
        return self._item.getMaxStackSize()

    def isStackable(self):
        """能堆叠才有意义；不可损坏且堆叠为 1 的物品不算可堆叠。"""
        return self.getMaxStackSize() > 1

    # ---------------- 比较 ----------------

    def isItem(self, item):
        """Item overload of original `is`, plus legacy Python convenience inputs.

        The original name is installed with setattr below; generated Java calls
        use getattr and retain `is`. Empty stacks expose AIR through getItem().
        """
        if self is None:
            raise NullPointerException()
        if isinstance(item, ItemStack):
            return self.getItem() is item.getItem()
        if isinstance(item, Item):
            return self.getItem() is item
        if isinstance(item, ItemLike):
            return self.getItem() is item.asItem()
        return False

    def isItemStack(self, other):
        """对应 is(ItemStack) 语义的别名，方便翻译层区分。"""
        return self.isItem(other)

    @staticmethod
    def isSameItem(left, right):
        if right is None:
            raise NullPointerException()
        if hasattr(right, 'getRestoredId') and right._item is None and not right.isEmpty():
            raise IllegalStateException('Resolve saved item before comparing Java item identity')
        item = right.getItem()
        if left is None:
            raise NullPointerException()
        if hasattr(left, 'getRestoredId') and left._item is None and not left.isEmpty():
            raise IllegalStateException('Resolve saved item before comparing Java item identity')
        return left.isItem(item)

    def isSameItemSameComponents(self, other):
        """Static Java contract, also callable by existing Python instance users.

        Compare the component representations currently supported by the bridge;
        arbitrary Java DataComponent values still require their own adapters.
        """
        if not ItemStack.isSameItem(self, other):
            return False
        if self.isEmpty() and other.isEmpty():
            return True
        return (self.getCustomData() == other.getCustomData()
                and equals(self._display_name, other._display_name)
                and getattr(self, "_native_item_components", None) == getattr(other, "_native_item_components", None))

    def matches(self, other):
        """Static Java equality: reference fast path, count, then components."""
        if self is other:
            return True
        if self is None:
            raise NullPointerException()
        count = self.getCount()
        if other is None:
            raise NullPointerException()
        return count == other.getCount() and ItemStack.isSameItemSameComponents(self, other)

    @staticmethod
    def listMatches(left, right):
        def size(values):
            return values.size() if hasattr(values, 'size') else len(values)
        def get(values, index):
            return values.get(index) if hasattr(values, 'get') else values[index]
        if left is None:
            raise NullPointerException()
        count = size(left)
        if right is None:
            raise NullPointerException()
        if count != size(right):
            return False
        index = 0
        while index < size(left):
            if not ItemStack.matches(get(left, index), get(right, index)):
                return False
            index += 1
        return True

    # ---------------- 数量变更 ----------------

    def grow(self, amount):
        """Increase the count using Java getCount/setCount semantics."""
        self.setCount(self.getCount() + int(amount))
        return None

    def shrink(self, amount):
        """Decrease count; an empty stack exposes zero through getCount."""
        self.grow(-int(amount))
        return None

    def split(self, amount):
        """
        对应 split(int)：从本栈分出 amount 个，**本栈减少**。
        返回分出去的新栈。
        """
        # Vanilla does not validate the sign here; native click/input adapters
        # must validate their own requests before invoking this public method.
        taken = min(int(amount), self.getCount())
        clone = self.copyWithCount(taken)
        self.shrink(taken)
        return clone

    def copy(self):
        """对应 copy()：拷贝一份（数量与数据都带过去）。"""
        if self.isEmpty():
            return ItemStack.EMPTY
        clone = ItemStack(self._item, self._count) if self._item is not None \
            else ItemStack()
        clone._custom_data = copy.deepcopy(self._custom_data)
        clone._display_name = self._display_name
        for name in ("_native_item_data", "_native_item_components"):
            if hasattr(self, name):
                setattr(clone, name, copy.deepcopy(getattr(self, name)))
        if hasattr(self, "_capability_registry"):
            clone._capability_registry = self._capability_registry
        return clone

    def copyWithCount(self, count):
        if self.isEmpty():
            return ItemStack.EMPTY
        clone = self.copy()
        clone.setCount(count)
        return clone

    # ---------------- 数据 ----------------

    def getCustomData(self):
        """本实现用普通字典承载「数据组件」的概念。"""
        return self._custom_data

    def setCustomData(self, data):
        self._custom_data = data
        return None

    def hasCustomData(self):
        return bool(self._custom_data)

    def getPersistentData(self):
        """
        对应 getPersistentData()（真实用了 8 次）。

        Java 里返回一个可以随便塞键值的 NBT 复合标签；
        这里返回一个**始终存在**的字典，调用方可以直接读写 ——
        避免每次都要判空。
        """
        if self._custom_data is None:
            self._custom_data = {}
        return self._custom_data

    # ---------------- 显示 ----------------

    def setDisplayName(self, name):
        self._display_name = name
        return None

    def getDisplayName(self):
        """
        对应 getDisplayName()（真实用了 14 次）。

        优先用显式设置的名字；否则按物品的 descriptionId 查翻译表 ——
        与 Component 的回退策略一致（查不到就显示键本身）。
        """
        if self._display_name is not None:
            return self._display_name
        if self._item is None:
            return Component.literal(u"")
        return Component.translatable(self._item.getDescriptionId())

    def getHoverName(self):
        return self.getDisplayName()

    # ---------------- 身份 ----------------

    def equals(self, other):
        return self is other

    def hashCode(self):
        return ((id(self) + 2147483648) % 4294967296) - 2147483648

    def toString(self):
        if self.isEmpty():
            return u"0 x <empty>"
        return u"{} x {}".format(self._count,
                                 self._item.getDescriptionId()
                                 if self._item else u"<empty>")

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<ItemStack {}>".format(self.toString())


ItemStack.EMPTY = ItemStack()
setattr(ItemStack, "is", ItemStack.isItem)


# ============================================================
# 常见物品（对应 Items.* 常量）
# ============================================================

class _ItemsHolder(object):
    """
    对应 net.minecraft.world.item.Items。

    真实代码会写 Items.AIR 之类的常量。这里**不预造全部物品** ——
    只有被真正引用到的才有意义，全部造出来既浪费又容易与注册表脱节。
    用懒加载：取哪个建哪个，且同名始终是同一个对象。
    """

    def __init__(self):
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in self._cache:
            item = Item(ItemProperties(), identifier=u"minecraft:{}".format(
                name.lower()))
            # 常见物品的堆叠数按 Minecraft 的约定设置
            if name in (u"AIR",):
                item.properties.stacksTo(0)
            self._cache[name] = item
        return self._cache[name]

    def clear(self):
        self._cache = {}

    def __repr__(self):
        return u"<Items {} 个已建>".format(len(self._cache))


ITEMS = _ItemsHolder()


# ============================================================
# Rarity
# ============================================================

class Rarity(object):
    """对应 net.minecraft.world.item.Rarity。"""

    class _Rarity(object):
        def __init__(self, name):
            self._name = name

        def name(self):
            return self._name

        def toString(self):
            return self._name

        def __eq__(self, other):
            return self is other

        def __ne__(self, other):
            return self is not other

        def __hash__(self):
            return id(self)

        def __str__(self):
            return self._name

        def __repr__(self):
            return u"<Rarity.{}>".format(self._name)

    COMMON = None
    UNCOMMON = None
    RARE = None
    EPIC = None


Rarity.COMMON = Rarity._Rarity(u"COMMON")
Rarity.UNCOMMON = Rarity._Rarity(u"UNCOMMON")
Rarity.RARE = Rarity._Rarity(u"RARE")
Rarity.EPIC = Rarity._Rarity(u"EPIC")


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.item.Item": Item,
    "net.minecraft.world.item.BlockItem": BlockItem,
    "net.minecraft.world.item.Item$Properties": ItemProperties,
    "net.minecraft.world.item.ItemStack": ItemStack,
    "net.minecraft.world.level.ItemLike": ItemLike,
    "net.minecraft.world.item.Items": ITEMS,
    "net.minecraft.world.item.Rarity": Rarity,
}


__all__ = [
    "ItemLike", "ItemProperties", "Item", "BlockItem", "ItemStack",
    "ITEMS", "Rarity",
    "JAVA_MAP",
]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)

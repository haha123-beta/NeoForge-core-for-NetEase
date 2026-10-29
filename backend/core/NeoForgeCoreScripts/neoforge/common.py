# -*- coding: utf-8 -*-
# neoforge/common.py
# β 层：NeoForge 通用类型
#
# 真实用法（从反编译源码逐字提取）：
#   EventResult.pass()      7 处（其中 FTBUltimineUtil.java:78 直接使用）
#
# **关键字冲突**：`pass` 是 Python 关键字，`EventResult.pass()` 在 Python 里
# 是语法错误，所以核心包里方法名是 `passResult`。
# 改名约定见 core/keyword_renames.py。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore


class EventResult(object):
    """
    对应 net.neoforged.neoforge.common.util.EventResult。

    三态结果，与 Minecraft 的 InteractionResult 思路一致但更简：
        DEFAULT  —— 不干预，按默认逻辑继续
        ALLOW    —— 明确允许
        DENY     —— 明确拒绝
        PASS     —— 交回给下一个处理器

    真实代码在事件处理器里返回它来表达「我管不管这件事」。
    """

    class _Result(object):
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
            return u"<EventResult.{}>".format(self._name)

    DEFAULT = None
    ALLOW = None
    DENY = None
    PASS = None

    @staticmethod
    def passResult():
        """
        对应 EventResult.pass()。

        **方法名不是 pass** —— `pass` 是 Python 关键字，
        `EventResult.pass()` 在 Python 里无法解析（实测 7 处）。
        """
        return EventResult.PASS

    @staticmethod
    def allow():
        return EventResult.ALLOW

    @staticmethod
    def deny():
        return EventResult.DENY

    @staticmethod
    def defaultValue():
        """对应 defaultResult()/DEFAULT 的取值入口。"""
        return EventResult.DEFAULT

    @staticmethod
    def valueOf(name):
        text = java_to_string(name).upper()
        for member in (EventResult.DEFAULT, EventResult.ALLOW,
                       EventResult.DENY, EventResult.PASS):
            if member.name() == text:
                return member
        raise IllegalArgumentException(
            u"No enum constant EventResult.{}".format(name))

    @staticmethod
    def values():
        return [EventResult.DEFAULT, EventResult.ALLOW,
                EventResult.DENY, EventResult.PASS]


EventResult.DEFAULT = EventResult._Result(u"DEFAULT")
EventResult.ALLOW = EventResult._Result(u"ALLOW")
EventResult.DENY = EventResult._Result(u"DENY")
EventResult.PASS = EventResult._Result(u"PASS")


class TriState(object):
    """
    对应 net.neoforged.neoforge.common.util.TriState。

    也是三态（TRUE / FALSE / DEFAULT），用于「是否允许」类判断。
    与 EventResult 的区别：TriState 表达布尔倾向，EventResult 表达处理归属。
    """

    class _Tri(object):
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
            return u"<TriState.{}>".format(self._name)

    TRUE = None
    FALSE = None
    DEFAULT = None

    @staticmethod
    def passResult():
        """
        对应 TriState.pass() —— 同 EventResult，必须避开 pass 关键字。
        语义是「不表态」，等同于 DEFAULT。
        """
        return TriState.DEFAULT

    @staticmethod
    def fromBoolean(value):
        """对应 fromBoolean：布尔转三态。"""
        return TriState.TRUE if value else TriState.FALSE

    @staticmethod
    def toBoolean(state):
        """对应 toBoolean：非 TRUE 都算假（DEFAULT 不等于 TRUE）。"""
        return state is TriState.TRUE


TriState.TRUE = TriState._Tri(u"TRUE")
TriState.FALSE = TriState._Tri(u"FALSE")
TriState.DEFAULT = TriState._Tri(u"DEFAULT")


# ============================================================
# ItemAbility / ItemAbilities
# ============================================================

class _AbilitySet(object):
    """
    `ItemAbilities.DEFAULT_AXE_ACTIONS` 这类常量集合。

    真实代码的用法是：
        return ItemAbilities.DEFAULT_AXE_ACTIONS.contains(itemAbility)
    所以必须有 `contains`（而不是 Python 的 in）——
    它是 Java 的 `Set.contains`。

    顺带支持 Python 的 `in` 与迭代，方便自测与调试。
    """

    def __init__(self, name, abilities):
        self._name = name
        self._items = list(abilities)

    def contains(self, ability):
        """对应 Set.contains(Object)。"""
        for candidate in self._items:
            if candidate is ability:
                return True
        return False

    def name(self):
        return self._name

    def size(self):
        return len(self._items)

    def toList(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __contains__(self, ability):
        return self.contains(ability)

    def __repr__(self):
        return u"<{} {} 项>".format(self._name, len(self._items))


class ItemAbility(object):
    """
    对应 net.neoforged.neoforge.common.ItemAbility。

    它描述「工具能做的一种动作」：剥皮、刮蜡、锄地、剪羊毛……
    真实用法（ManaitaPlusLegacyAxeItem）：
        public boolean canPerformAction(ItemStack stack, ItemAbility itemAbility) {
            return ItemAbilities.DEFAULT_AXE_ACTIONS.contains(itemAbility)
                || super.canPerformAction(stack, itemAbility);
        }

    注意名字里的 Ability 而不是 Action —— NeoForge 用的是前者，
    照抄以免翻译层找不到。
    """

    def __init__(self, name):
        self._name = java_to_string(name)

    def name(self):
        return self._name

    def getName(self):
        return self._name

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, ItemAbility) and other._name == self._name

    def hashCode(self):
        # 用名字的哈希 —— 这样跨实例也能对上，
        # 与 Java 里按同一个静态常量比较的效果一致。
        return hash(self._name)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<ItemAbility {}>".format(self._name)


class ItemAbilities(object):
    """
    对应 net.neoforged.neoforge.common.ItemAbilities。

    原版与 NeoForge 预定义的动作常量，以及按工具归类好的集合。
    真实代码用到：AXE_STRIP / AXE_SCRAPE / AXE_WAX_OFF /
                 DEFAULT_AXE_ACTIONS / DEFAULT_SHOVEL_ACTIONS /
                 SHEARS_DIG / SHEARS_HARVEST
    """

    # 斧
    AXE_STRIP = None
    AXE_SCRAPE = None
    AXE_WAX_OFF = None
    AXE_DIG = None
    # 锹
    SHOVEL_DIG = None
    SHOVEL_FLATTEN = None
    # 锄
    HOE_DIG = None
    HOE_TILL = None
    # 剪刀
    SHEARS_DIG = None
    SHEARS_HARVEST = None
    SHEARS_CARVE = None
    SHEARS_DISARM = None
    # 剑
    SWORD_DIG = None
    SWORD_SWEEP = None
    # 其他
    FISHING_ROD_CAST = None
    FLINT_AND_STEEL = None
    IGNITE = None

    # 按工具归类的集合（真实代码用 contains 查它们）
    DEFAULT_AXE_ACTIONS = None
    DEFAULT_SHOVEL_ACTIONS = None
    DEFAULT_HOE_ACTIONS = None
    DEFAULT_SHEARS_ACTIONS = None
    DEFAULT_SWORD_ACTIONS = None


def _init_item_abilities():
    """
    建立 ItemAbility 常量与工具集合。

    用函数而不是直接写在类体里：类体里逐个赋值要写几十行，
    而且集合依赖常量，拆开更清楚。
    """
    names = (
        u"AXE_STRIP", u"AXE_SCRAPE", u"AXE_WAX_OFF", u"AXE_DIG",
        u"SHOVEL_DIG", u"SHOVEL_FLATTEN",
        u"HOE_DIG", u"HOE_TILL",
        u"SHEARS_DIG", u"SHEARS_HARVEST", u"SHEARS_CARVE", u"SHEARS_DISARM",
        u"SWORD_DIG", u"SWORD_SWEEP",
        u"FISHING_ROD_CAST", u"FLINT_AND_STEEL", u"IGNITE",
    )
    for name in names:
        setattr(ItemAbilities, name,
                ItemAbility(u"neoforge:{}".format(name.lower())))

    ItemAbilities.DEFAULT_AXE_ACTIONS = _AbilitySet(
        u"DEFAULT_AXE_ACTIONS",
        [ItemAbilities.AXE_STRIP, ItemAbilities.AXE_SCRAPE,
         ItemAbilities.AXE_WAX_OFF, ItemAbilities.AXE_DIG])
    ItemAbilities.DEFAULT_SHOVEL_ACTIONS = _AbilitySet(
        u"DEFAULT_SHOVEL_ACTIONS",
        [ItemAbilities.SHOVEL_DIG, ItemAbilities.SHOVEL_FLATTEN])
    ItemAbilities.DEFAULT_HOE_ACTIONS = _AbilitySet(
        u"DEFAULT_HOE_ACTIONS",
        [ItemAbilities.HOE_DIG, ItemAbilities.HOE_TILL])
    ItemAbilities.DEFAULT_SHEARS_ACTIONS = _AbilitySet(
        u"DEFAULT_SHEARS_ACTIONS",
        [ItemAbilities.SHEARS_DIG, ItemAbilities.SHEARS_HARVEST,
         ItemAbilities.SHEARS_CARVE, ItemAbilities.SHEARS_DISARM])
    ItemAbilities.DEFAULT_SWORD_ACTIONS = _AbilitySet(
        u"DEFAULT_SWORD_ACTIONS",
        [ItemAbilities.SWORD_DIG, ItemAbilities.SWORD_SWEEP])


_init_item_abilities()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.neoforged.neoforge.common.util.EventResult": EventResult,
    "net.neoforged.neoforge.common.util.TriState": TriState,
    "net.neoforged.neoforge.common.ItemAbility": ItemAbility,
    "net.neoforged.neoforge.common.ItemAbilities": ItemAbilities,
}


__all__ = [
    "EventResult", "TriState",
    "ItemAbility", "ItemAbilities",
    "JAVA_MAP",
]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)

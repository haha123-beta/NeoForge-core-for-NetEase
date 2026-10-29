# -*- coding: utf-8 -*-
# neoforge/event/entity/player.py
# β 层：玩家事件（net.neoforged.neoforge.event.entity.player）
#
# 真实用法（逐字来自反编译源码 common/event/EventHandler.java）：
#
#   @SubscribeEvent
#   public static void onLeftClickBlock(PlayerInteractEvent.LeftClickBlock event) {
#       Player player = event.getEntity();
#       if (event.getAction() != PlayerInteractEvent.LeftClickBlock.Action.START) return;
#       BlockPos pos = event.getPos();
#       ManaitaPlusUtils.destroyBlocks(player.getMainHandItem(), event.getLevel(), pos, player);
#   }
#
#   @SubscribeEvent
#   public static void onPlayerRespawn(PlayerEvent.PlayerRespawnEvent event) {
#       Player player = event.getEntity();
#       ManaitaPlusLegacyEntityData.death.remove((Entity) event.getEntity());
#   }
#
#   @SubscribeEvent
#   public static void onLivingAttack(AttackEntityEvent event) {
#       Entity entity = event.getTarget();
#       if (...) { event.setCanceled(true); }
#   }
#
#   @SubscribeEvent
#   public static void onItemTooltip(ItemTooltipEvent event) {
#       Item item = event.getItemStack().getItem();
#       List toolTip = event.getToolTip();
#   }
#
# **嵌套类的继承关系要照抄**（同 ClientTickEvent 的处理）：
#   PlayerEvent.PlayerRespawnEvent extends PlayerEvent
#   PlayerInteractEvent.LeftClickBlock extends PlayerInteractEvent
#   PlayerInteractEvent.RightClickBlock extends PlayerInteractEvent
# 真实代码按父类订阅时靠这个继承生效。
#
# **`getToolTip()` 要返回可变列表**：真实代码会往里加提示行
# （`toolTip.add(...)`）。返回拷贝的话提示就加不上，而且不报错。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.entity.base import EntityEvent, LivingEvent
    from java_stdlib.lang import java_to_string
except ImportError:
    from base import EntityEvent, LivingEvent  # type: ignore
    from lang import java_to_string  # type: ignore


# ============================================================
# PlayerEvent
# ============================================================

class PlayerEvent(EntityEvent):
    """
    对应 net.neoforged.neoforge.event.entity.player.PlayerEvent。

    玩家事件的父类。真实代码用它的子类 `PlayerEvent.PlayerRespawnEvent`。

    `getEntity()` 在这里返回玩家（Java 里是协变返回类型）。
    """

    def getPlayer(self):
        """明确的别名：拿到的是玩家而不是泛指的实体。"""
        return self._entity


class PlayerRespawnEvent(PlayerEvent):
    """对应 PlayerEvent.PlayerRespawnEvent：玩家重生。"""

    def __init__(self, entity=None, conquered_end=False):
        PlayerEvent.__init__(self, entity)
        self._conquered_end = bool(conquered_end)

    def isEndConquered(self):
        """对应 isEndConquered()：是不是打完末影龙后的重生。"""
        return self._conquered_end


class PlayerLoggedInEvent(PlayerEvent):
    """对应 PlayerEvent.PlayerLoggedInEvent。"""


class PlayerLoggedOutEvent(PlayerEvent):
    """对应 PlayerEvent.PlayerLoggedOutEvent。"""


class PlayerCloneEvent(PlayerEvent):
    """对应 PlayerEvent.Clone：玩家数据克隆（死亡重生/换维度）。"""

    def __init__(self, entity=None, original=None, was_death=False):
        PlayerEvent.__init__(self, entity)
        self._original = original
        self._was_death = bool(was_death)

    def getOriginal(self):
        """对应 getOriginal()：克隆前的旧玩家。"""
        return self._original

    def isWasDeath(self):
        """对应 isWasDeath()：是不是因为死亡而克隆。"""
        return self._was_death


class PlayerChangedDimensionEvent(PlayerEvent):
    """对应 PlayerEvent.PlayerChangedDimensionEvent。"""


PlayerEvent.PlayerRespawnEvent = PlayerRespawnEvent
PlayerEvent.PlayerLoggedInEvent = PlayerLoggedInEvent
PlayerEvent.PlayerLoggedOutEvent = PlayerLoggedOutEvent
PlayerEvent.PlayerCloneEvent = PlayerCloneEvent
PlayerEvent.PlayerChangedDimensionEvent = PlayerChangedDimensionEvent


# ============================================================
# PlayerInteractEvent
# ============================================================

class PlayerInteractEvent(PlayerEvent):
    """
    对应 net.neoforged.neoforge.event.entity.player.PlayerInteractEvent。

    真实代码用它的嵌套子类区分「左键点方块」与「右键点方块」。
    """

    def __init__(self, entity=None, pos=None, face=None, level=None,
                 hand=None):
        PlayerEvent.__init__(self, entity)
        self._pos = pos
        self._face = face
        self._level = level
        self._hand = hand

    def getPos(self):
        """对应 getPos()：被点击的方块坐标（真实代码直接传给 destroyBlocks）。"""
        return self._pos

    def getFace(self):
        """对应 getFace()：点击的面。"""
        return self._face

    def getLevel(self):
        """对应 getLevel()：所在世界。"""
        return self._level

    def getHand(self):
        """对应 getHand()：用的哪只手。"""
        return self._hand


class LeftClickBlock(PlayerInteractEvent):
    """
    对应 PlayerInteractEvent.LeftClickBlock。

    真实代码读 `event.getAction()`，只在 START 时处理 ——
    因为一次点击会触发 START / STOP / ABORT 三次。
    """

    class _Action(object):
        """对应 Action 枚举：START / STOP / ABORT。"""

        def __init__(self, name):
            self._name = java_to_string(name)

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
            return u"<Action.{}>".format(self._name)

    START = None
    STOP = None
    ABORT = None

    def __init__(self, entity=None, pos=None, face=None, level=None, hand=None,
                 action=None):
        PlayerInteractEvent.__init__(self, entity, pos, face, level, hand)
        # 默认 START —— 真实代码最常处理的就是它
        self._action = action if action is not None else LeftClickBlock.START

    def getAction(self):
        """对应 getAction()：START / STOP / ABORT。"""
        return self._action

    def setUseBlock(self, value):
        """对应 setUseBlock(Result)：是否拦截方块交互。"""
        self._use_block = value
        return self

    def getUseBlock(self):
        return getattr(self, "_use_block", None)


class RightClickBlock(PlayerInteractEvent):
    """对应 PlayerInteractEvent.RightClickBlock。"""

    def setUseBlock(self, value):
        self._use_block = value
        return self

    def getUseBlock(self):
        return getattr(self, "_use_block", None)


class RightClickItem(PlayerInteractEvent):
    """对应 PlayerInteractEvent.RightClickItem。"""


LeftClickBlock.START = LeftClickBlock._Action(u"START")
LeftClickBlock.STOP = LeftClickBlock._Action(u"STOP")
LeftClickBlock.ABORT = LeftClickBlock._Action(u"ABORT")

PlayerInteractEvent.LeftClickBlock = LeftClickBlock
PlayerInteractEvent.RightClickBlock = RightClickBlock
PlayerInteractEvent.RightClickItem = RightClickItem


# ============================================================
# AttackEntityEvent
# ============================================================

class AttackEntityEvent(EntityEvent):
    """
    对应 net.neoforged.neoforge.event.entity.player.AttackEntityEvent。

    真实用法：
        Entity entity = event.getTarget();
        if (...) { event.setCanceled(true); }

    `getEntity()` 是攻击者（玩家），`getTarget()` 是被打的那个。
    """

    def __init__(self, entity=None, target=None, hand=None):
        EntityEvent.__init__(self, entity)
        self._target = target
        self._hand = hand

    def getTarget(self):
        """对应 getTarget()：被攻击的实体。"""
        return self._target

    def getHand(self):
        """对应 getHand()：用的哪只手。"""
        return self._hand


# ============================================================
# ItemTooltipEvent
# ============================================================

class ItemTooltipEvent(EntityEvent):
    """
    对应 net.neoforged.neoforge.event.entity.player.ItemTooltipEvent。

    真实用法：
        Item item = event.getItemStack().getItem();
        List toolTip = event.getToolTip();
        toolTip.add(...);       // 往里加提示行

    **`getToolTip()` 必须返回可变列表** —— 真实代码就是靠它往提示里追加内容的。
    返回拷贝的话提示加不上，而且不报错。
    """

    def __init__(self, item_stack=None, tool_tip=None, entity=None,
                 flags=None):
        EntityEvent.__init__(self, entity)
        self._item_stack = item_stack
        self._tool_tip = tool_tip if tool_tip is not None else []
        self._flags = flags

    def getItemStack(self):
        """对应 getItemStack()：被查看的物品。"""
        return self._item_stack

    def getToolTip(self):
        """
        对应 getToolTip()：**可变的**提示行列表。

        真实代码直接往里 add，所以必须返回内部列表本身。
        """
        return self._tool_tip

    def getFlags(self):
        """对应 getFlags()：TooltipFlag（决定要不要显示进阶提示）。"""
        return self._flags

    def getEntity(self):
        """对应 getEntity()：看着这个物品的玩家（可能为 None）。"""
        return self._entity


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.event.entity.player."

JAVA_MAP = {
    _PREFIX + "PlayerEvent": PlayerEvent,
    _PREFIX + "PlayerEvent$PlayerRespawnEvent": PlayerRespawnEvent,
    _PREFIX + "PlayerEvent$PlayerLoggedInEvent": PlayerLoggedInEvent,
    _PREFIX + "PlayerEvent$PlayerLoggedOutEvent": PlayerLoggedOutEvent,
    _PREFIX + "PlayerEvent$Clone": PlayerCloneEvent,
    _PREFIX + "PlayerEvent$PlayerChangedDimensionEvent":
        PlayerChangedDimensionEvent,
    _PREFIX + "PlayerInteractEvent": PlayerInteractEvent,
    _PREFIX + "PlayerInteractEvent$LeftClickBlock": LeftClickBlock,
    _PREFIX + "PlayerInteractEvent$RightClickBlock": RightClickBlock,
    _PREFIX + "PlayerInteractEvent$RightClickItem": RightClickItem,
    _PREFIX + "AttackEntityEvent": AttackEntityEvent,
    _PREFIX + "ItemTooltipEvent": ItemTooltipEvent,
}


__all__ = [
    "PlayerEvent", "PlayerRespawnEvent", "PlayerLoggedInEvent",
    "PlayerLoggedOutEvent", "PlayerCloneEvent",
    "PlayerChangedDimensionEvent",
    "PlayerInteractEvent", "LeftClickBlock", "RightClickBlock",
    "RightClickItem",
    "AttackEntityEvent", "ItemTooltipEvent",
    "JAVA_MAP",
]

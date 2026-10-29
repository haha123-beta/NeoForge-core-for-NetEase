# -*- coding: utf-8 -*-
# neoforge/event/level.py
# β 层：世界事件（net.neoforged.neoforge.event.level）
#
# 真实用法：BlockEvent 及其嵌套子类（方块破坏/放置前后）。
# 真实模组通过它做「破坏方块前拦截」这类逻辑。
#
# 与 PlayerInteractEvent 的区别：
#   PlayerInteractEvent 是「玩家点了方块」，带玩家与手；
#   BlockEvent 是「方块本身要发生变化」，带方块状态与世界，不一定要玩家。
#
# 嵌套类继承外层类（`BlockEvent.BreakEvent extends BlockEvent`），
# 与 ClientTickEvent 的处理一致 —— 按父类订阅也能收到。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.base import CancelableEvent
except ImportError:
    from base import CancelableEvent  # type: ignore


class BlockEvent(CancelableEvent):
    """
    对应 net.neoforged.neoforge.event.level.BlockEvent。

    所有方块事件的父类，持有世界、坐标与方块状态。
    **可取消** —— 真实代码用它阻止方块变化（`setCanceled(true)`）。
    """

    def __init__(self, level=None, pos=None, state=None):
        CancelableEvent.__init__(self)
        self._level = level
        self._pos = pos
        self._state = state

    def getLevel(self):
        """对应 getLevel()：所在世界。"""
        return self._level

    def getPos(self):
        """对应 getPos()：方块坐标。"""
        return self._pos

    def getState(self):
        """对应 getState()：方块状态。"""
        return self._state


class BreakEvent(BlockEvent):
    """
    对应 BlockEvent.BreakEvent：方块被破坏前。

    `getPlayer()` 拿到破坏者（可能为 None，例如爆炸破坏）。
    取消它等于「阻止这次破坏」。
    """

    def __init__(self, level=None, pos=None, state=None, player=None,
                 xp=0):
        BlockEvent.__init__(self, level, pos, state)
        self._player = player
        self._xp = int(xp)

    def getPlayer(self):
        """对应 getPlayer()：破坏方块的玩家。"""
        return self._player

    def getExpToDrop(self):
        """对应 getExpToDrop()：这次破坏该掉多少经验。"""
        return self._xp

    def setExpToDrop(self, amount):
        """对应 setExpToDrop(int)：改经验掉落量。"""
        self._xp = int(amount)
        return self


class PlaceEvent(BlockEvent):
    """
    对应 BlockEvent.PlaceEvent：方块被放置后。

    `getPlacedBlock()` 是新放上去的状态，`getState()` 是放置**前**的状态。
    """

    def __init__(self, level=None, pos=None, state=None, placed_block=None,
                 player=None):
        BlockEvent.__init__(self, level, pos, state)
        self._placed_block = placed_block
        self._player = player

    def getPlacedBlock(self):
        """对应 getPlacedBlock()：放上去的方块状态。"""
        return self._placed_block

    def getPlayer(self):
        return self._player


class EntityPlaceEvent(BlockEvent):
    """对应 BlockEvent.EntityPlaceEvent：实体（含玩家）放下方块。"""

    def __init__(self, level=None, pos=None, state=None, entity=None,
                 placed_block=None):
        BlockEvent.__init__(self, level, pos, state)
        self._entity = entity
        self._placed_block = placed_block

    def getEntity(self):
        return self._entity

    def getPlacedBlock(self):
        return self._placed_block


class BlockToolModificationEvent(BlockEvent):
    """
    对应 BlockEvent.BlockToolModificationEvent。

    工具改变方块（斧头剥皮、锹平土）时触发 —— 真实模组用 ItemAbilities
    处理这类动作，属于同一族。
    """

    def __init__(self, level=None, pos=None, state=None, context=None,
                 ability=None):
        BlockEvent.__init__(self, level, pos, state)
        self._context = context
        self._ability = ability
        self._final_state = None

    def getContext(self):
        """对应 getContext()：UseOnContext。"""
        return self._context

    def getItemAbility(self):
        """对应 getItemAbility()：触发的动作（ItemAbility）。"""
        return self._ability

    def setFinalState(self, state):
        """对应 setFinalState(BlockState)：指定改变后的状态。"""
        self._final_state = state
        return self

    def getFinalState(self):
        return self._final_state


BlockEvent.BreakEvent = BreakEvent
BlockEvent.PlaceEvent = PlaceEvent
BlockEvent.EntityPlaceEvent = EntityPlaceEvent
BlockEvent.BlockToolModificationEvent = BlockToolModificationEvent


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.event.level."

JAVA_MAP = {
    _PREFIX + "BlockEvent": BlockEvent,
    _PREFIX + "BlockEvent$BreakEvent": BreakEvent,
    _PREFIX + "BlockEvent$PlaceEvent": PlaceEvent,
    _PREFIX + "BlockEvent$EntityPlaceEvent": EntityPlaceEvent,
    _PREFIX + "BlockEvent$BlockToolModificationEvent": BlockToolModificationEvent,
}


__all__ = [
    "BlockEvent", "BreakEvent", "PlaceEvent", "EntityPlaceEvent",
    "BlockToolModificationEvent",
    "JAVA_MAP",
]

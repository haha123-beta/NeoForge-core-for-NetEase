# -*- coding: utf-8 -*-
# minecraft/physics.py
# θ 层：碰撞上下文与射线参数
#
# 真实用法（逐字来自反编译源码）：
#
#   // CollisionContext 出现在方块行为的签名里
#   public VoxelShape getCollisionShape(BlockState state, BlockGetter getter,
#                                       BlockPos pos, CollisionContext context)
#
#   // 两种构造形态
#   player == null ? CollisionContext.empty() : CollisionContext.of(player)
#
#   // 寻路类型（方块行为里判断「这个方块能不能走过去」）
#   public boolean isPathfindable(BlockState state, BlockGetter getter,
#                                 BlockPos pos, PathComputationType type)
#
# 本层是纯数据：`CollisionContext` 只是「谁在碰撞」，没有世界状态；
# `PathComputationType` 是三个枚举成员。都不涉及引擎。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib.lang import java_to_string
except ImportError:
    from lang import java_to_string  # type: ignore


class _EnumLike(object):
    """枚举常量的共用实现（身份比较 + 可哈希 + 可打印）。"""

    def __init__(self, name):
        self._name = java_to_string(name)

    def name(self):
        return self._name

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, _EnumLike) and other._name == self._name

    def hashCode(self):
        return hash(u"{}:{}".format(type(self).__name__, self._name))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<{} {}>".format(type(self).__name__, self._name)


# ============================================================
# PathComputationType
# ============================================================

class PathComputationType(object):
    """
    对应 net.minecraft.world.level.pathfinder.PathComputationType。

    三个成员对应「谁在问路」：
        LAND      陆地生物走着过去
        WATER     水生物游过去
        AIR       飞行生物飞过去

    真实代码用它判断方块对某一类寻路是否可通行。
    """

    LAND = None
    WATER = None
    AIR = None

    @staticmethod
    def values():
        return [PathComputationType.LAND, PathComputationType.WATER,
                PathComputationType.AIR]

    @staticmethod
    def byName(name):
        text = java_to_string(name).upper()
        for member in PathComputationType.values():
            if member.name() == text:
                return member
        raise ValueError(u"No enum constant PathComputationType.{}".format(name))


PathComputationType.LAND = _EnumLike(u"LAND")
PathComputationType.WATER = _EnumLike(u"WATER")
PathComputationType.AIR = _EnumLike(u"AIR")


# ============================================================
# CollisionContext
# ============================================================

class CollisionContext(object):
    """
    对应 net.minecraft.world.level.CollisionContext。

    「谁在碰撞」——影响方块是否把自己算作碰撞体
    （例如潜行的玩家不会触发某些方块的碰撞）。

    真实代码的两种用法：
        CollisionContext.empty()      没有特定实体（例如世界外的查询）
        CollisionContext.of(entity)   按某个实体的状态判定

    `empty()` 不是「返回 None」—— 它返回一个**有效的空上下文**，
    这样调用方不用到处判空（同 getCompound 的处理思路）。
    """

    EMPTY = None

    def __init__(self, entity=None):
        self._entity = entity

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def empty():
        """对应 CollisionContext.empty()。"""
        return CollisionContext._empty_instance()

    @staticmethod
    def of(entity=None):
        """
        对应 CollisionContext.of(Entity)。

        实体为 None 时等价于 empty() —— 真实代码正是这么用的：
        `player == null ? CollisionContext.empty() : CollisionContext.of(player)`
        """
        if entity is None:
            return CollisionContext.empty()
        return CollisionContext(entity)

    @staticmethod
    def ofEntity(entity):
        """明确版的 of（Python 没有重载，给个不含糊的名字）。"""
        return CollisionContext.of(entity)

    # ---------------- 查询 ----------------

    def getEntity(self):
        """对应 getEntity()：相关实体（可能为 None）。"""
        return self._entity

    def isDescending(self):
        """对应 isDescending()：实体是否在下落（影响某些方块碰撞）。"""
        if self._entity is None:
            return False
        return getattr(self._entity, "_descending", False)

    def isPlacement(self):
        """对应 isPlacement()：是不是「放置方块」时的查询。"""
        return False

    def isEmpty(self):
        """本实现新增：是不是空上下文（便于诊断）。"""
        return self._entity is None

    def toString(self):
        return u"CollisionContext[{}]".format(
            self._entity if self._entity is not None else u"empty")

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())

    # ---------------- 内部 ----------------

    @staticmethod
    def _empty_instance():
        """空上下文用**同一个对象**，这样身份比较也成立。"""
        CollisionContext._ensure_empty()
        return CollisionContext.EMPTY


# 空上下文的单例（第一次用时建，避免类体里 forward reference）
CollisionContext._EMPTY_INSTANCE = None


def _ensure_empty():
    if CollisionContext._EMPTY_INSTANCE is None:
        CollisionContext._EMPTY_INSTANCE = CollisionContext(None)
        CollisionContext.EMPTY = CollisionContext._EMPTY_INSTANCE
    return None


CollisionContext._ensure_empty = staticmethod(_ensure_empty)
_ensure_empty()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.level.CollisionContext": CollisionContext,
    "net.minecraft.world.level.pathfinder.PathComputationType":
        PathComputationType,
}


__all__ = ["CollisionContext", "PathComputationType", "JAVA_MAP"]

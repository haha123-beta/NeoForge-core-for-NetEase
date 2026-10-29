# -*- coding: utf-8 -*-
# neoforge/event/entity/base.py
# β 层：实体事件基类（net.neoforged.neoforge.event.entity）
#
# 这一层放「所有实体事件共享的东西」：
#
#     EntityEvent            持有实体
#     EntityEvent.EnteringSection  实体跨区块段
#     LivingEvent            持有活体（EntityEvent 的子类）
#     LivingEvent.LivingTickEvent  活体 tick
#
# 真实 Java 里 EntityEvent 与 LivingEvent 是两个平级类，
# LivingEvent 继承 EntityEvent。**这个继承要照抄** ——
# 真实代码会按父类订阅（`subscribe(cb, EntityEvent)` 收所有实体事件）。
#
# 为什么单独一个文件而不是塞进 living.py：
#   player.py 里的事件（AttackEntityEvent / PlayerEvent）也继承 EntityEvent，
#   而 living.py 里的事件继承 LivingEvent。放在这里两边都能用，
#   不必让 player 去 import living（那会形成依赖方向上的怪关系）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.base import CancelableEvent
    from java_stdlib._base import IllegalArgumentException
except ImportError:
    from base import CancelableEvent  # type: ignore
    from _base import IllegalArgumentException  # type: ignore


class EntityEvent(CancelableEvent):
    """
    对应 net.neoforged.neoforge.event.entity.EntityEvent。

    所有实体事件的父类，持有触发它的实体。

    真实用法：`event.getEntity()` 到处都在用
    （`Player player = event.getEntity();`）。
    """

    def __init__(self, entity=None):
        CancelableEvent.__init__(self)
        self._entity = entity

    def getEntity(self):
        """对应 getEntity()：触发事件的实体。"""
        return self._entity

    def setEntity(self, entity):
        self._entity = entity
        return self

    def __repr__(self):
        return u"<{} entity={}>".format(type(self).__name__, self._entity)


class LivingEvent(EntityEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingEvent。

    活体（有生命值的实体）事件的父类。
    """

    def getEntity(self):
        """
        对应 getEntity()：返回**活体**。

        与父类同名但语义更窄 —— Java 里是协变返回类型，
        Python 没有类型系统，所以只是把文档说清楚。
        """
        return self._entity

    def getLivingEntity(self):
        """明确的别名，避免调用方不确定拿到的是什么。"""
        return self._entity


# 嵌套类：真实代码写 LivingEvent.LivingTickEvent
class LivingTickEvent(LivingEvent):
    """对应 LivingEvent.LivingTickEvent。"""


LivingEvent.LivingTickEvent = LivingTickEvent


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.neoforged.neoforge.event.entity.EntityEvent": EntityEvent,
    "net.neoforged.neoforge.event.entity.living.LivingEvent": LivingEvent,
    "net.neoforged.neoforge.event.entity.living.LivingEvent$LivingTickEvent":
        LivingTickEvent,
}


__all__ = ["EntityEvent", "LivingEvent", "LivingTickEvent", "JAVA_MAP"]

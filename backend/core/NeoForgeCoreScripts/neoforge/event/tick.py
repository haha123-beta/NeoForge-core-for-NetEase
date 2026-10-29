# -*- coding: utf-8 -*-
# neoforge/event/tick.py
# β 层：tick 事件（net.neoforged.neoforge.event.tick）
#
# 真实用法（逐字来自反编译源码 common/event/EventHandler.java）：
#
#   @SubscribeEvent
#   public static void onPlayerTick(PlayerTickEvent.Pre event) {
#       Player player = event.getEntity();
#       ...
#   }
#
#   @SubscribeEvent
#   public static void clientTick(ClientTickEvent.Post event) { ... }   // client.py 里
#
# **嵌套类必须继承外层类**（`PlayerTickEvent.Pre extends PlayerTickEvent`）。
# 这样按父类订阅也能收到 —— 我最初把 Pre/Post 直接继承 Event，
# 导致「按父类订阅收不到子类事件」，自测抓到了。
# 沿用 client.py 里 ClientTickEvent 的写法：类体里声明，类定义完之后
# 用 __bases__ 重设（类体执行时外层类还没绑定）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.entity.base import EntityEvent
    from neoforge.event.base import Event
except ImportError:
    from base import EntityEvent  # type: ignore
    from base import Event  # type: ignore


class TickEvent(Event):
    """
    对应 net.neoforged.neoforge.event.TickEvent。

    它有两个有用的嵌套枚举：`Type`（LEVEL / PLAYER / CLIENT / SERVER / …）
    与 `Phase`（START / END）。本实现只保留 Phase 的语义 ——
    因为真实代码用的是 `PlayerTickEvent.Pre` 而不是 Type。
    """

    class _Phase(object):
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
            return u"<Phase.{}>".format(self._name)

    START = None
    END = None


TickEvent.START = TickEvent._Phase(u"START")
TickEvent.END = TickEvent._Phase(u"END")


class PlayerTickEvent(EntityEvent):
    """
    对应 net.neoforged.neoforge.event.tick.PlayerTickEvent。

    真实代码用 `PlayerTickEvent.Pre` —— 所以嵌套类必须继承它。
    """

    class Pre(Event):
        """玩家 tick 开始前。"""

    class Post(Event):
        """玩家 tick 结束后。"""


# 让嵌套类真正继承外层类（Java 的 nested class 语义）。
# 不能写在类体里写 `class Pre(PlayerTickEvent)` —— 类体执行时还不存在。
PlayerTickEvent.Pre.__bases__ = (PlayerTickEvent,)
PlayerTickEvent.Post.__bases__ = (PlayerTickEvent,)


class LevelTickEvent(EntityEvent):
    """对应 net.neoforged.neoforge.event.tick.LevelTickEvent（世界 tick）。"""

    class Pre(Event):
        pass

    class Post(Event):
        pass


LevelTickEvent.Pre.__bases__ = (LevelTickEvent,)
LevelTickEvent.Post.__bases__ = (LevelTickEvent,)


class ServerTickEvent(Event):
    """对应 net.neoforged.neoforge.event.tick.ServerTickEvent。"""

    class Pre(Event):
        pass

    class Post(Event):
        pass


ServerTickEvent.Pre.__bases__ = (ServerTickEvent,)
ServerTickEvent.Post.__bases__ = (ServerTickEvent,)


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.event.tick."

JAVA_MAP = {
    _PREFIX + "TickEvent": TickEvent,
    _PREFIX + "PlayerTickEvent": PlayerTickEvent,
    _PREFIX + "PlayerTickEvent$Pre": PlayerTickEvent.Pre,
    _PREFIX + "PlayerTickEvent$Post": PlayerTickEvent.Post,
    _PREFIX + "LevelTickEvent": LevelTickEvent,
    _PREFIX + "LevelTickEvent$Pre": LevelTickEvent.Pre,
    _PREFIX + "LevelTickEvent$Post": LevelTickEvent.Post,
    _PREFIX + "ServerTickEvent": ServerTickEvent,
    _PREFIX + "ServerTickEvent$Pre": ServerTickEvent.Pre,
    _PREFIX + "ServerTickEvent$Post": ServerTickEvent.Post,
}


__all__ = [
    "TickEvent", "PlayerTickEvent", "LevelTickEvent", "ServerTickEvent",
    "JAVA_MAP",
]

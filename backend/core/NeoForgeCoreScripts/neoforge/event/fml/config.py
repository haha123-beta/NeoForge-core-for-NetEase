# -*- coding: utf-8 -*-
# neoforge/event/fml/config.py
# β 层：配置事件（net.neoforged.fml.event.config）
#
# 真实用法（逐字来自反编译源码）：
#     @SubscribeEvent
#     static void onLoad(ModConfigEvent.Loading event) {
#         if (event.getConfig().getModId().equals("manaita_plus_legacy")
#                 && event.getConfig().getSpec() == SPEC) {
#             item_drops_doubling_value = (Integer) item_drops_doubling.get();
#         }
#     }
#
# **这两个事件必须派发**（不能像客户端事件那样跳过）：
# 跳过它们会让模组一直读到配置默认值，用户改了配置也不生效。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    # 包内相对导入：本模块住在 neoforge/event/fml/ 下
    from neoforge.event.base import Event
except ImportError:
    from base import Event  # type: ignore


class ModConfigEvent(Event):
    """对应 net.neoforged.fml.event.config.ModConfigEvent。"""

    def __init__(self, config=None):
        Event.__init__(self)
        self.config = config

    def getConfig(self):
        return self.config

class _Loading(ModConfigEvent):
    pass


class _Reloading(ModConfigEvent):
    pass


class _Unloading(ModConfigEvent):
    pass


ModConfigEvent.Loading = _Loading
ModConfigEvent.Reloading = _Reloading
ModConfigEvent.Unloading = _Unloading

# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.fml.event.config."

JAVA_MAP = {
    _PREFIX + "ModConfigEvent": ModConfigEvent,
    _PREFIX + "ModConfigEvent$Loading": ModConfigEvent.Loading,
    _PREFIX + "ModConfigEvent$Reloading": ModConfigEvent.Reloading,
    _PREFIX + "ModConfigEvent$Unloading": ModConfigEvent.Unloading,
}


__all__ = ["ModConfigEvent", "JAVA_MAP"]

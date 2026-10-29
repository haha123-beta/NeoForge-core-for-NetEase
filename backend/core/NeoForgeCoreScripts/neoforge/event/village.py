# -*- coding: utf-8 -*-
# neoforge/event/village.py
# β 层：村庄事件（net.neoforged.neoforge.event.village）
#
# 真实用法（逐字来自反编译源码 common/event/EventHandler.java）：
#
#   @SubscribeEvent
#   public static void addCustomTrades(VillagerTradesEvent event) {
#       ... 往对应职业与等级的列表里加交易项 ...
#   }
#
# `VillagerTradesEvent` 的 `getTrades()` 返回的是
# **{等级: [交易项]} 的映射，且列表是可变的** ——
# 真实代码就是靠往列表里 add 来注册自定义交易的。
# 返回拷贝的话交易加不上，而且不报错。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.base import Event
    from java_stdlib.lang import java_to_string
except ImportError:
    from base import Event  # type: ignore
    from lang import java_to_string  # type: ignore


class VillagerTradesEvent(Event):
    """
    对应 net.neoforged.neoforge.event.village.VillagerTradesEvent。

    给某个村民职业追加交易项。
    """

    # 村民等级：1 新手 → 5 大师
    NOVICE = 1
    APPRENTICE = 2
    JOURNEYMAN = 3
    EXPERT = 4
    MASTER = 5

    def __init__(self, villager_type=None, trades=None):
        Event.__init__(self)
        self._type = villager_type
        # {等级: [交易项]}；真实代码往里 add
        self._trades = trades if trades is not None else {
            1: [], 2: [], 3: [], 4: [], 5: []}

    def getType(self):
        """对应 getType()：村民职业类型。"""
        return self._type

    def getTrades(self):
        """
        对应 getTrades()：**可变的** {等级: [交易项]} 映射。

        真实代码形如：
            event.getTrades().get(1).add(new TradeOffer(...));
        所以必须返回内部映射本身，不能返回拷贝。
        """
        return self._trades

    def addTrade(self, level, trade):
        """便利入口：往某个等级追加一个交易项。"""
        level = int(level)
        if level not in self._trades:
            self._trades[level] = []
        self._trades[level].append(trade)
        return self

    def tradeCount(self):
        """所有等级的交易项总数（诊断用）。"""
        total = 0
        for level in self._trades:
            total += len(self._trades[level])
        return total

    def __repr__(self):
        return u"<VillagerTradesEvent {} 项交易>".format(self.tradeCount())


class WandererTradesEvent(Event):
    """对应 net.neoforged.neoforge.event.village.WandererTradesEvent（流浪商人）。"""

    def __init__(self, generic_trades=None, rare_trades=None):
        Event.__init__(self)
        self._generic = generic_trades if generic_trades is not None else []
        self._rare = rare_trades if rare_trades is not None else []

    def getGenericTrades(self):
        """对应 getGenericTrades()：普通交易（可变列表）。"""
        return self._generic

    def getRareTrades(self):
        """对应 getRareTrades()：稀有交易（可变列表）。"""
        return self._rare


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.event.village."

JAVA_MAP = {
    _PREFIX + "VillagerTradesEvent": VillagerTradesEvent,
    _PREFIX + "WandererTradesEvent": WandererTradesEvent,
}


__all__ = ["VillagerTradesEvent", "WandererTradesEvent", "JAVA_MAP"]

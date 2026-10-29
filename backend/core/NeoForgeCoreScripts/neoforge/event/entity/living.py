# -*- coding: utf-8 -*-
# neoforge/event/entity/living.py
# β 层：活体实体事件（net.neoforged.neoforge.event.entity.living）
#
# 真实用法（逐字来自反编译源码 common/event/EventHandler.java）：
#
#   @SubscribeEvent
#   public static void onLivingDrops(LivingDropsEvent event) {
#       if (event.getSource().getEntity() instanceof Player) {
#           player = (Player) event.getSource().getEntity();
#           LivingEntity killCredit = event.getEntity().getKillCredit();
#       }
#       for (ItemEntity drop : event.getDrops()) { ... }
#       event.getDrops().forEach(item -> player.getInventory().add(item.getItem()));
#       event.getDrops().clear();
#       event.setCanceled(true);
#   }
#
#   @SubscribeEvent
#   public static void onLivingExperienceDrop(LivingExperienceDropEvent event) {
#       Player attackingPlayer = event.getAttackingPlayer();
#       event.setDroppedExperience(event.getDroppedExperience() * 2);
#       event.setCancelled(true);
#       event.setDroppedExperience(0);
#   }
#
#   @SubscribeEvent
#   public static void onLivingFall(LivingFallEvent event) {
#       LivingEntity livingEntity = event.getEntity();
#       event.setCanceled(true);
#   }
#
#   @SubscribeEvent
#   public static void onLivingDeath(LivingDeathEvent event) {
#       LivingEntity livingEntity = event.getEntity();
#       event.setCanceled(true);
#   }
#
# **`setCanceled` 到处都是 —— 所以这些事件必须可取消。**
# 它们全部继承 `LivingEvent` → `EntityEvent` → `CancelableEvent`，
# 取消能力从那里来。少了这一层，真实代码第一句就 AttributeError。
#
# 另一个要点：`event.getDrops()` 返回的是**可变列表**，
# 真实代码会 `clear()` 它并自己接管掉落物。返回拷贝的话
# `clear()` 就白做了（而且是静默无效）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from neoforge.event.entity.base import LivingEvent, LivingTickEvent
    from java_stdlib.lang import java_to_string
except ImportError:
    from base import LivingEvent, LivingTickEvent  # type: ignore
    from lang import java_to_string  # type: ignore


class LivingDeathEvent(LivingEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingDeathEvent。

    真实用法：
        public static void onLivingDeath(LivingDeathEvent event) {
            LivingEntity livingEntity = event.getEntity();
            if (...) { event.setCanceled(true); }
        }

    **取消它等于「不让这个实体死」** —— 所以可取消是必需的。
    """

    def __init__(self, entity=None, source=None):
        LivingEvent.__init__(self, entity)
        self._source = source

    def getSource(self):
        """对应 getSource()：伤害来源。"""
        return self._source


class LivingDropsEvent(LivingEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingDropsEvent。

    真实用法见文件头 —— 它会读 `getDrops()`、往里面加东西、
    再 `clear()` 并取消事件，从而**完全接管掉落物**。
    """

    def __init__(self, entity=None, source=None, drops=None,
                 recently_hit=False):
        LivingEvent.__init__(self, entity)
        self._source = source
        # 用可变列表：真实代码要 clear() 与 forEach
        self._drops = drops if drops is not None else []
        self._recently_hit = bool(recently_hit)

    def getSource(self):
        """对应 getSource()：伤害来源（读 getEntity() 判断凶手是不是玩家）。"""
        return self._source

    def getDrops(self):
        """
        对应 getDrops()：掉落物列表。

        **返回内部列表本身，不是拷贝** —— 真实代码会
        `event.getDrops().clear()` 然后自己处理掉落。
        返回拷贝的话那个 clear 就静默无效了。
        """
        return self._drops

    def setDrops(self, drops):
        self._drops = drops if drops is not None else []
        return self

    def isRecentlyHit(self):
        """对应 isRecentlyHit()：是否刚被玩家打过（影响经验掉落）。"""
        return self._recently_hit


class LivingExperienceDropEvent(LivingEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingExperienceDropEvent。

    真实用法：
        Player attackingPlayer = event.getAttackingPlayer();
        event.setDroppedExperience(event.getDroppedExperience() * doubling);
        attackingPlayer.giveExperiencePoints(...);
        event.setDroppedExperience(0);
        event.setCanceled(true);
    """

    def __init__(self, entity=None, attacking_player=None,
                 original_experience=0, dropped_experience=0):
        LivingEvent.__init__(self, entity)
        self._attacking_player = attacking_player
        self._original_experience = int(original_experience)
        self._dropped_experience = int(dropped_experience)

    def getAttackingPlayer(self):
        """对应 getAttackingPlayer()：击杀者（可能为 None）。"""
        return self._attacking_player

    def getOriginalExperience(self):
        """对应 getOriginalExperience()：原本该掉多少（改之前的值）。"""
        return self._original_experience

    def getDroppedExperience(self):
        """对应 getDroppedExperience()：当前要掉多少。"""
        return self._dropped_experience

    def setDroppedExperience(self, amount):
        """
        对应 setDroppedExperience(int)。

        真实代码会先加倍、直接把经验给玩家、再设成 0 ——
        所以这个 setter 必须真的能改值。
        """
        self._dropped_experience = int(amount)
        return self


class LivingFallEvent(LivingEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingFallEvent。

    真实用法：`event.setCanceled(true)` 取消摔落伤害。
    """

    def __init__(self, entity=None, distance=0.0, damage_multiplier=1.0):
        LivingEvent.__init__(self, entity)
        self._distance = float(distance)
        self._damage_multiplier = float(damage_multiplier)

    def getDistance(self):
        """对应 getDistance()：摔了多高。"""
        return self._distance

    def setDistance(self, value):
        self._distance = float(value)
        return self

    def getDamageMultiplier(self):
        """对应 getDamageMultiplier()：伤害倍率。"""
        return self._damage_multiplier

    def setDamageMultiplier(self, value):
        self._damage_multiplier = float(value)
        return self


class LivingHurtEvent(LivingEvent):
    """
    对应 net.neoforged.neoforge.event.entity.living.LivingHurtEvent。

    受伤前触发，可改伤害量或取消。
    （本模组没直接引用，但它是同族里最常见的一个，一并提供。）
    """

    def __init__(self, entity=None, source=None, amount=0.0):
        LivingEvent.__init__(self, entity)
        self._source = source
        self._amount = float(amount)

    def getSource(self):
        return self._source

    def getAmount(self):
        return self._amount

    def setAmount(self, value):
        self._amount = float(value)
        return self


class LivingHealEvent(LivingEvent):
    """对应 LivingHealEvent：治疗前触发，可改治疗量或取消。"""

    def __init__(self, entity=None, amount=0.0):
        LivingEvent.__init__(self, entity)
        self._amount = float(amount)

    def getAmount(self):
        return self._amount

    def setAmount(self, value):
        self._amount = float(value)
        return self


class LivingIncomingDamageEvent(LivingEvent):
    """对应 LivingIncomingDamageEvent：伤害即将结算时触发。"""

    def __init__(self, entity=None, source=None, amount=0.0):
        LivingEvent.__init__(self, entity)
        self._source = source
        self._amount = float(amount)

    def getSource(self):
        return self._source

    def getAmount(self):
        return self._amount

    def setAmount(self, value):
        self._amount = float(value)
        return self


class LivingKnockBackEvent(LivingEvent):
    """对应 LivingKnockBackEvent：被击退前触发。"""

    def __init__(self, entity=None, strength=0.0, ratio_x=0.0, ratio_z=0.0):
        LivingEvent.__init__(self, entity)
        self._strength = float(strength)
        self._ratio_x = float(ratio_x)
        self._ratio_z = float(ratio_z)

    def getStrength(self):
        return self._strength

    def setStrength(self, value):
        self._strength = float(value)
        return self


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.event.entity.living."

JAVA_MAP = {
    _PREFIX + "LivingEvent": LivingEvent,
    _PREFIX + "LivingEvent$LivingTickEvent": LivingTickEvent,
    _PREFIX + "LivingDeathEvent": LivingDeathEvent,
    _PREFIX + "LivingDropsEvent": LivingDropsEvent,
    _PREFIX + "LivingExperienceDropEvent": LivingExperienceDropEvent,
    _PREFIX + "LivingFallEvent": LivingFallEvent,
    _PREFIX + "LivingHurtEvent": LivingHurtEvent,
    _PREFIX + "LivingHealEvent": LivingHealEvent,
    _PREFIX + "LivingIncomingDamageEvent": LivingIncomingDamageEvent,
    _PREFIX + "LivingKnockBackEvent": LivingKnockBackEvent,
}


__all__ = [
    "LivingEvent", "LivingTickEvent",
    "LivingDeathEvent", "LivingDropsEvent", "LivingExperienceDropEvent",
    "LivingFallEvent", "LivingHurtEvent", "LivingHealEvent",
    "LivingIncomingDamageEvent", "LivingKnockBackEvent",
    "JAVA_MAP",
]

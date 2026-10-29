# -*- coding: utf-8 -*-
# neoforge/event/__init__.py
# β 层：事件系统（按真实 Java 包拆分的包入口）
#
# 为什么要拆成包
# --------------
# 原来只有一个扁平的 `neoforge/event.py`（754 行），
# 但真实 Java 里这些事件类分散在 **7 个包**下：
#
#     net.neoforged.api.distmarker            Dist / OnlyIn
#     net.neoforged.fml.loading               FMLEnvironment
#     net.neoforged.bus.api                   Event / SubscribeEvent / IEventBus
#     net.neoforged.fml.common                EventBusSubscriber
#     net.neoforged.fml.event.lifecycle       FML*SetupEvent
#     net.neoforged.fml.event.config          ModConfigEvent
#     net.neoforged.neoforge.client.event     客户端事件
#     net.neoforged.neoforge.event.entity.*   实体/玩家/活体事件
#     net.neoforged.neoforge.event.tick       玩家/世界 tick
#     net.neoforged.neoforge.event.level      BlockEvent
#     net.neoforged.neoforge.event.village    VillagerTradesEvent
#
# 翻译层按包路径定位代码，目录与 Java 包长期不一致会一直添麻烦。
# 所以现在目录结构与 Java 包一一对应：
#
#     event/__init__.py        本文件：聚合入口
#     event/base.py            侧判断 / 事件基类 / 注解 / 事件总线
#     event/client.py          net.neoforged.neoforge.client.event
#     event/tick.py            net.neoforged.neoforge.event.tick
#     event/level.py           net.neoforged.neoforge.event.level
#     event/village.py         net.neoforged.neoforge.event.village
#     event/entity/base.py     EntityEvent / LivingEvent
#     event/entity/living.py   net.neoforged.neoforge.event.entity.living
#     event/entity/player.py   net.neoforged.neoforge.event.entity.player
#     event/fml/lifecycle.py   net.neoforged.fml.event.lifecycle
#     event/fml/config.py      net.neoforged.fml.event.config
#
# **本文件把全部名字重新导出**，所以下面两种导入都继续可用：
#     from neoforge.event import IEventBus          （旧路径）
#     from neoforge.event.base import IEventBus     （新路径）
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

from neoforge.event.base import (  # noqa: F401
    Dist,
    FMLEnvironment,
    OnlyIn,
    is_side_allowed,
    Event,
    CancelableEvent,
    SubscribeEvent,
    EventBusSubscriber,
    collect_listeners,
    IEventBus,
    EventPriority,
)

from neoforge.event.client import (  # noqa: F401
    ClientTickEvent,
    RenderFrameEvent,
    InputEvent,
    RegisterShadersEvent,
)

from neoforge.event.entity.base import (  # noqa: F401
    EntityEvent,
    LivingEvent,
    LivingTickEvent,
)

from neoforge.event.entity.living import (  # noqa: F401
    LivingDeathEvent,
    LivingDropsEvent,
    LivingExperienceDropEvent,
    LivingFallEvent,
    LivingHurtEvent,
    LivingHealEvent,
    LivingIncomingDamageEvent,
    LivingKnockBackEvent,
)

from neoforge.event.entity.player import (  # noqa: F401
    PlayerEvent,
    PlayerRespawnEvent,
    PlayerLoggedInEvent,
    PlayerLoggedOutEvent,
    PlayerCloneEvent,
    PlayerChangedDimensionEvent,
    PlayerInteractEvent,
    LeftClickBlock,
    RightClickBlock,
    RightClickItem,
    AttackEntityEvent,
    ItemTooltipEvent,
)

from neoforge.event.tick import (  # noqa: F401
    TickEvent,
    PlayerTickEvent,
    LevelTickEvent,
    ServerTickEvent,
)

from neoforge.event.level import (  # noqa: F401
    BlockEvent,
    BreakEvent,
    PlaceEvent,
    EntityPlaceEvent,
    BlockToolModificationEvent,
)

from neoforge.event.village import (  # noqa: F401
    VillagerTradesEvent,
    WandererTradesEvent,
)

from neoforge.event.fml.lifecycle import (  # noqa: F401
    ParallelDispatchEvent,
    FMLCommonSetupEvent,
    FMLClientSetupEvent,
    FMLDedicatedServerSetupEvent,
    FMLLoadCompleteEvent,
    InterModEnqueueEvent,
    InterModProcessEvent,
)

from neoforge.event.fml.config import ModConfigEvent  # noqa: F401


# ============================================================
# 名称映射表（聚合各子模块的）
# ============================================================

def _merged_java_map():
    """
    把各子模块的 JAVA_MAP 合并成一张总表。

    用函数而不是模块级字典推导：核心包源码要 Py2 兼容，
    字典推导在 Py2.7 其实可用，但这里需要 import 各子模块，
    写成函数更清楚，也避免导入期的顺序问题。
    """
    from neoforge.event import base as _base
    from neoforge.event import client as _client
    from neoforge.event import tick as _tick
    from neoforge.event import level as _level
    from neoforge.event import village as _village
    from neoforge.event.entity import base as _entity_base
    from neoforge.event.entity import living as _living
    from neoforge.event.entity import player as _player
    from neoforge.event.fml import lifecycle as _lifecycle
    from neoforge.event.fml import config as _config

    merged = {}
    for module in (_base, _client, _tick, _level, _village, _entity_base,
                   _living, _player, _lifecycle, _config):
        java_map = getattr(module, "JAVA_MAP", None)
        if java_map:
            merged.update(java_map)
    return merged


JAVA_MAP = _merged_java_map()


__all__ = [
    # 基础
    "Dist", "FMLEnvironment", "OnlyIn", "is_side_allowed",
    "Event", "CancelableEvent",
    "SubscribeEvent", "EventBusSubscriber", "collect_listeners", "IEventBus",
    # 客户端
    "ClientTickEvent", "RenderFrameEvent", "InputEvent", "RegisterShadersEvent",
    # 实体
    "EntityEvent", "LivingEvent", "LivingTickEvent",
    "LivingDeathEvent", "LivingDropsEvent", "LivingExperienceDropEvent",
    "LivingFallEvent", "LivingHurtEvent", "LivingHealEvent",
    "LivingIncomingDamageEvent", "LivingKnockBackEvent",
    "PlayerEvent", "PlayerRespawnEvent", "PlayerLoggedInEvent",
    "PlayerLoggedOutEvent", "PlayerCloneEvent", "PlayerChangedDimensionEvent",
    "PlayerInteractEvent", "LeftClickBlock", "RightClickBlock",
    "RightClickItem", "AttackEntityEvent", "ItemTooltipEvent",
    # tick / 世界 / 村庄
    "TickEvent", "PlayerTickEvent", "LevelTickEvent", "ServerTickEvent",
    "BlockEvent", "BreakEvent", "PlaceEvent", "EntityPlaceEvent",
    "BlockToolModificationEvent",
    "VillagerTradesEvent", "WandererTradesEvent",
    # FML
    "ParallelDispatchEvent", "FMLCommonSetupEvent", "FMLClientSetupEvent",
    "FMLDedicatedServerSetupEvent", "FMLLoadCompleteEvent",
    "InterModEnqueueEvent", "InterModProcessEvent",
    "ModConfigEvent",
    "JAVA_MAP",
]

# Entity registration and world lifecycle.
from neoforge.event.entity.registration import (
    EntityAttributeCreationEvent, EntityJoinLevelEvent, EntityLeaveLevelEvent)
__all__.extend(["EntityAttributeCreationEvent", "EntityJoinLevelEvent",
                "EntityLeaveLevelEvent"])

from neoforge.event.entity.registration import JAVA_MAP as _registration_map
JAVA_MAP.update(_registration_map)

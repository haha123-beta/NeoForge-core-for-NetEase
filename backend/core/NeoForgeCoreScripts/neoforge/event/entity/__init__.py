# -*- coding: utf-8 -*-
# neoforge/event/entity/__init__.py
# β 层：实体事件包（net.neoforged.neoforge.event.entity）
#
# 对应真实 Java 包 net.neoforged.neoforge.event.entity，下分：
#     base.py      EntityEvent / LivingEvent（共同基类）
#     living.py    net.neoforged.neoforge.event.entity.living
#     player.py    net.neoforged.neoforge.event.entity.player
#
# base.py 存在的理由：player.py 里的事件也继承 EntityEvent，
# 而 living.py 里的事件继承 LivingEvent。放在 base 里两边都能用，
# 不必让 player 去 import living（那会形成奇怪的依赖方向）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

from neoforge.event.entity.base import EntityEvent, LivingEvent, LivingTickEvent  # noqa: F401
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


__all__ = [
    "EntityEvent", "LivingEvent", "LivingTickEvent",
    "LivingDeathEvent", "LivingDropsEvent", "LivingExperienceDropEvent",
    "LivingFallEvent", "LivingHurtEvent", "LivingHealEvent",
    "LivingIncomingDamageEvent", "LivingKnockBackEvent",
    "PlayerEvent", "PlayerRespawnEvent", "PlayerLoggedInEvent",
    "PlayerLoggedOutEvent", "PlayerCloneEvent", "PlayerChangedDimensionEvent",
    "PlayerInteractEvent", "LeftClickBlock", "RightClickBlock",
    "RightClickItem", "AttackEntityEvent", "ItemTooltipEvent",
]

# Entity registration and world lifecycle.
from neoforge.event.entity.registration import (
    EntityAttributeCreationEvent, EntityJoinLevelEvent, EntityLeaveLevelEvent)
__all__.extend(["EntityAttributeCreationEvent", "EntityJoinLevelEvent",
                "EntityLeaveLevelEvent"])

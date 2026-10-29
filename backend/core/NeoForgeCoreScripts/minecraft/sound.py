# -*- coding: utf-8 -*-
# minecraft/sound.py
# θ 层：声音与游戏事件
#
# 真实用法（逐字来自反编译源码）：
#
#   // SoundSource —— 声音归属的「通道」（真实 20 次）
#   new SimpleSoundInstance(soundtype.getHitSound(), SoundSource.BLOCKS,
#                           (soundtype.getVolume() + 1.0f) / 8.0f, ...)
#
#   // SoundEvent / SoundEvents
#   SoundEvent.of(ResourceLocation.fromNamespaceAndPath(...))
#
#   // GameEvent —— 注意它是以 **Holder** 形式传递的（真实 21 次）
#   level.gameEvent(GameEvent.BLOCK_PLACE, blockpos,
#                   GameEvent.Context.of(player, blockState));
#   this.gameEvent(GameEvent.LIGHTNING_STRIKE);
#   level.gameEvent(GameEvent.BLOCK_CHANGE, mutableBlockPos,
#                   GameEvent.Context.of(entity, state));
#
# **一个必须照抄的细节**：`GameEvent.BLOCK_PLACE` 这类常量在 Java 里
# 本身就可能被当作 Holder 使用 —— 所以这里的常量做成 `Holder` 包着的
# GameEvent，与 registries.py 的 Holder 语义衔接。
# 真实代码里那个 `(Holder)` 强转就是这个意思。
#
# 为什么单独一个模块而不是塞进 core.py：
#   声音（通道 + 事件 + 原版常量表）自成一块，塞进 core 会让它继续膨胀
#   （core.py 已经 28KB）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
    from minecraft.registries import Holder
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from registries import Holder  # type: ignore


# ============================================================
# 枚举基类（多个类共用同一套身份语义）
# ============================================================

class _NamedConstant(object):
    """
    具名常量：身份比较 + 可哈希 + 可打印。

    声音通道、游戏事件这些「枚举」都靠它 —— 它们必须是**稳定对象**，
    因为真实代码会用 `==` 判断（例如区分不同的事件源）。
    """

    def __init__(self, name, payload=None):
        self._name = java_to_string(name)
        self._payload = payload

    def name(self):
        return self._name

    def getName(self):
        return self._name

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, _NamedConstant) \
            and other._name == self._name

    def hashCode(self):
        return hash_code(self._name)

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
# SoundSource
# ============================================================

class SoundSource(object):
    """
    对应 net.minecraft.sounds.SoundSource（真实 20 次）。

    它表示声音从哪来 —— 决定音量滑块（主音量 / 方块音 / 音乐…）
    以及听者过滤。基岩版没有同样的通道体系，但**常量本身必须存在**，
    因为真实代码会把它作为参数一路传下去。
    """

    MASTER = None
    MUSIC = None
    RECORDS = None
    WEATHER = None
    BLOCKS = None
    HOSTILE = None
    NEUTRAL = None
    PLAYERS = None
    AMBIENT = None
    VOICE = None

    @staticmethod
    def values():
        return [SoundSource.MASTER, SoundSource.MUSIC, SoundSource.RECORDS,
                SoundSource.WEATHER, SoundSource.BLOCKS, SoundSource.HOSTILE,
                SoundSource.NEUTRAL, SoundSource.PLAYERS, SoundSource.AMBIENT,
                SoundSource.VOICE]

    @staticmethod
    def byName(name):
        """对应 byName(String)：按名字取，取不到抛异常。"""
        text = java_to_string(name).upper()
        for member in SoundSource.values():
            if member.name() == text:
                return member
        raise IllegalArgumentException(
            u"No enum constant SoundSource.{}".format(name))


for _sound_source_name in (u"MASTER", u"MUSIC", u"RECORDS", u"WEATHER",
                           u"BLOCKS", u"HOSTILE", u"NEUTRAL", u"PLAYERS",
                           u"AMBIENT", u"VOICE"):
    setattr(SoundSource, _sound_source_name,
            _NamedConstant(_sound_source_name))


# ============================================================
# SoundEvent / SoundEvents
# ============================================================

class SoundEvent(object):
    """
    对应 net.minecraft.sounds.SoundEvent。

    它就是一个「有名字的音效」，名字是 ResourceLocation。
    真实代码用 `SoundEvent.of(location)` 建自定义音效。
    """

    def __init__(self, location):
        self._location = java_to_string(location)

    @staticmethod
    def of(location):
        """对应 SoundEvent.of(ResourceLocation)。"""
        return SoundEvent(location)

    @staticmethod
    def createFixedRangeEvent(location, range):
        """对应 createFixedRangeEvent：带固定传播范围的音效。"""
        event = SoundEvent(location)
        event._range = float(range)
        return event

    def location(self):
        """对应 location()：音效的资源位置。"""
        return self._location

    def getLocation(self):
        return self._location

    def getRange(self):
        """对应 getRange(float)：传播范围。固定范围事件才有意义。"""
        return getattr(self, "_range", 16.0)

    def equals(self, other):
        return isinstance(other, SoundEvent) \
            and other._location == self._location

    def hashCode(self):
        return hash_code(self._location)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def toString(self):
        return self._location

    def __str__(self):
        return self._location

    def __repr__(self):
        return u"<SoundEvent {}>".format(self._location)


class _SoundEventsHolder(object):
    """
    对应 net.minecraft.sounds.SoundEvents。

    懒加载 + 同名同对象。真实代码引用原版音效常量
    （例如铁砧落地 `SoundEvents.ANVIL_LAND`），
    这里按需生成，避免预造几百个没人用的对象。
    """

    def __init__(self):
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = SoundEvent(
                u"minecraft:{}".format(name.lower()))
        return self._cache[name]

    def clear(self):
        self._cache = {}
        return None

    def __repr__(self):
        return u"<SoundEvents {} 个已建>".format(len(self._cache))


SoundEvents = _SoundEventsHolder()


# ============================================================
# GameEvent
# ============================================================

class GameEvent(object):
    """
    对应 net.minecraft.world.level.gameevent.GameEvent。

    真实用法（21 次）：
        level.gameEvent(GameEvent.BLOCK_PLACE, pos, GameEvent.Context.of(...))
        this.gameEvent(GameEvent.LIGHTNING_STRIKE)

    两个要点：

    1. **常量是 Holder**。Java 里 `GameEvent.BLOCK_PLACE` 的类型是
       `Holder<GameEvent>`，所以 `level.gameEvent(...)` 的第一个参数
       才能直接收它（那边形参就是 Holder）。
       这里的常量同样是 Holder 包着的 GameEvent，
       `(Holder)` 那个强转语义就对上了。

    2. **Context.of(...)** 描述「谁触发的、涉及什么状态」，
       真实代码用两种形态：
           Context.of(Entity)                    —— 只有实体
           Context.of(Entity, BlockState)        —— 实体 + 方块状态
       Python 没有重载，用可选参数承接。
    """

    BLOCK_PLACE = None
    BLOCK_DESTROY = None
    BLOCK_CHANGE = None
    BLOCK_OPEN = None
    BLOCK_CLOSE = None
    BLOCK_ACTIVATE = None
    BLOCK_ATTACH = None
    BLOCK_DETACH = None
    LIGHTNING_STRIKE = None
    EXPLODE = None
    ENTITY_DIE = None
    ENTITY_DAMAGE = None
    ENTITY_INTERACT = None
    ITEM_INTERACT_FINISH = None
    CONTAINER_OPEN = None
    CONTAINER_CLOSE = None
    FLUID_PLACE = None
    FLUID_PICKUP = None
    NOTE_BLOCK_PLAY = None
    EQUIP = None
    UNEQUIP = None
    SHEAR = None
    TELEPORT = None
    RESONATE = None

    def __init__(self, name, radius=16):
        self._name = java_to_string(name)
        self._radius = float(radius)

    # ---------------- 查询 ----------------

    def name(self):
        return self._name

    def getName(self):
        return self._name

    def getRadius(self):
        """对应 getNotificationRadius()：通知半径。"""
        return self._radius

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, GameEvent) and other._name == self._name

    def hashCode(self):
        return hash_code(self._name)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<GameEvent {}>".format(self._name)

    # ---------------- 注册表式查找 ----------------

    @staticmethod
    def values():
        """所有已定义的常量（对应 Java 的注册表遍历）。"""
        result = []
        for name in sorted(GameEvent._names()):
            result.append(getattr(GameEvent, name))
        return result

    @staticmethod
    def _names():
        return [name for name in GameEvent._CONSTANT_NAMES]

    @staticmethod
    def byName(name):
        """按名字取 Holder；取不到抛异常。"""
        text = java_to_string(name).upper()
        for candidate in GameEvent._CONSTANT_NAMES:
            if candidate == text:
                return getattr(GameEvent, candidate)
        raise IllegalArgumentException(
            u"No game event named {}".format(name))


# 事件常量表：名字 -> 通知半径
# 半径按是否「值得远距离通知」区分：破坏/放置类较近，雷击/爆炸较远。
_GAME_EVENT_DEFS = (
    (u"BLOCK_PLACE", 16), (u"BLOCK_DESTROY", 16), (u"BLOCK_CHANGE", 16),
    (u"BLOCK_OPEN", 16), (u"BLOCK_CLOSE", 16), (u"BLOCK_ACTIVATE", 16),
    (u"BLOCK_ATTACH", 16), (u"BLOCK_DETACH", 16),
    (u"LIGHTNING_STRIKE", 32), (u"EXPLODE", 32),
    (u"ENTITY_DIE", 16), (u"ENTITY_DAMAGE", 16), (u"ENTITY_INTERACT", 16),
    (u"ITEM_INTERACT_FINISH", 16),
    (u"CONTAINER_OPEN", 16), (u"CONTAINER_CLOSE", 16),
    (u"FLUID_PLACE", 16), (u"FLUID_PICKUP", 16),
    (u"NOTE_BLOCK_PLAY", 16), (u"EQUIP", 16), (u"UNEQUIP", 16),
    (u"SHEAR", 16), (u"TELEPORT", 16), (u"RESONATE", 16),
)

GameEvent._CONSTANT_NAMES = tuple(name for name, _radius in _GAME_EVENT_DEFS)


def _init_game_events():
    """
    建立 GameEvent 常量。

    **常量是 Holder**，与 Java 的类型一致：
    `level.gameEvent(GameEvent.BLOCK_PLACE, ...)` 的第一个参数
    在 Java 形参表里就是 Holder<GameEvent>。
    """
    for name, radius in _GAME_EVENT_DEFS:
        event = GameEvent(u"minecraft:{}".format(name.lower()), radius)
        setattr(GameEvent, name, Holder(event, u"minecraft:game_event"))


_init_game_events()


class GameEvent_Context(object):
    """
    对应 GameEvent.Context。

    真实用法：
        GameEvent.Context.of(player, blockState)   —— 实体 + 状态
        GameEvent.Context.of(entity)               —— 只有实体

    Python 没有重载，第二个参数设为可选。
    """

    EMPTY = None

    def __init__(self, source_entity=None, affected_state=None):
        self._source_entity = source_entity
        self._affected_state = affected_state

    @staticmethod
    def of(source_entity=None, affected_state=None):
        return GameEvent_Context(source_entity, affected_state)

    @staticmethod
    def empty():
        """对应 Context.EMPTY。"""
        return GameEvent_Context.EMPTY

    def sourceEntity(self):
        """对应 sourceEntity()：触发者（可能为 None）。"""
        return self._source_entity

    def affectedState(self):
        """对应 affectedState()：受影响的方块状态。"""
        return self._affected_state

    def toString(self):
        return u"Context[{}, {}]".format(self._source_entity,
                                         self._affected_state)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


GameEvent.Context = GameEvent_Context
GameEvent_Context.EMPTY = GameEvent_Context()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.sounds.SoundSource": SoundSource,
    "net.minecraft.sounds.SoundEvent": SoundEvent,
    "net.minecraft.sounds.SoundEvents": SoundEvents,
    "net.minecraft.world.level.gameevent.GameEvent": GameEvent,
    "net.minecraft.world.level.gameevent.GameEvent$Context": GameEvent_Context,
}


__all__ = [
    "SoundSource", "SoundEvent", "SoundEvents",
    "GameEvent", "GameEvent_Context",
    "JAVA_MAP",
]

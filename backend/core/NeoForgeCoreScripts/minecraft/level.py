# -*- coding: utf-8 -*-
# minecraft/level.py
# θ 层：世界（Level / ServerLevel）
#
# 真实用法（引用次数来自 dev/scan_neoforge_api.py）：
#   Level         36 个文件引用
#   ServerLevel   20 个
#
#   getBlockState  40、setBlock 13、playSound 14、
#   gameEvent 11、levelEvent 8、getBlockEntity 7、
#   getFluidState 5、isClientSide 2
#
# **引擎边界**：这些都是真实的引擎操作（读写方块、播音效）。
# 本模块把它们**全部转发**给 `LevelAccess`（见 level_access.py），
# 自己不含任何引擎调用。好处有两个：
#   1. 整个世界逻辑可以脱离引擎完整自测；
#   2. 引擎接口确认后只改适配器一个文件。
#
# `Level.wrap(access)` 让同一个 LevelAccess 始终对应同一个 Level 对象 ——
# 这样 `entity.level() is other.level()` 这类身份判断才成立
# （真实代码会用它确认两个实体在不在同一个世界）。
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
    from minecraft.core import BlockPos
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from core import BlockPos  # type: ignore


# ============================================================
# 世界接口体系
# ============================================================
#
# Java 里这三个是**层层继承**的接口，真实代码用它们做参数类型：
#
#     getShape(BlockState, BlockGetter, BlockPos, CollisionContext)
#     isPathfindable(BlockState, BlockGetter, BlockPos, PathComputationType)
#     state.getSoundType((LevelReader) level, pos, entity)
#     state.canSurvive((LevelReader) level, pos)
#     block.dowse((Entity) player, (LevelAccessor) level, pos, state)
#
#     BlockGetter          只能读方块
#       └ LevelReader      读 + 高度/边界信息
#           └ LevelAccessor  读 + 写（方块、流体、方块实体）
#               └ Level      再加实体、音效、随机、配方
#
# **继承方向必须照抄**：真实代码把一个 Level 传给形参是 BlockGetter 的
# 方法（合法），反过来则不行。写反了类型检查就过不去
# （同 BlockPlaceContext extends UseOnContext 那次）。
#
# 本实现让它们实现为「按访问器（LevelAccess）取数据的薄包装」，
# 这样任何一方都能被独立传给需要该接口的函数。

class BlockGetter(object):
    """
    对应 net.minecraft.world.level.BlockGetter。

    最小的世界视图：**只能读方块**。真实模组用 4 次，
    出现在方块行为的方法签名里（`getShape` / `isPathfindable`）。
    """

    def __init__(self, access):
        if access is None:
            raise IllegalArgumentException(
                u"BlockGetter 需要 LevelAccess（见 level_access.py）")
        self._access = access

    def getAccess(self):
        return self._access

    def getBlockState(self, pos):
        """对应 getBlockState(BlockPos)。"""
        return self._access.getBlockState(_as_pos(pos))

    def isEmptyBlock(self, pos):
        return self._access.isEmptyBlock(_as_pos(pos))

    def getFluidState(self, pos):
        return self._access.getFluidState(_as_pos(pos))

    def getBlockEntity(self, pos):
        return self._access.getBlockEntity(_as_pos(pos))

    def getMaxBuildHeight(self):
        """对应 getMaxBuildHeight()：建筑高度上限。"""
        return 320

    def getMinBuildHeight(self):
        """对应 getMinBuildHeight()：建筑高度下限。"""
        return -64

    def __repr__(self):
        return u"<{} via {}>".format(type(self).__name__,
                                     type(self._access).__name__)


class LevelReader(BlockGetter):
    """
    对应 net.minecraft.world.level.LevelReader。

    在 BlockGetter 之上加「高度/边界」类信息。
    真实模组用 5 次，都是 `(LevelReader) level` 这种强转 ——
    说明拿到的是 Level，只是调用的方法只要求这个更窄的接口。
    """

    def getHeight(self):
        """对应 getHeight()：世界高度。"""
        return self.getMaxBuildHeight() - self.getMinBuildHeight()

    def isOutsideBuildHeight(self, pos):
        """
        对应 isOutsideBuildHeight(BlockPos)：坐标是否超出可建筑范围。

        接受 BlockPos 或整数 y —— Java 里是重载，Python 用可选参数区分。
        """
        if hasattr(pos, "getY"):
            y = pos.getY()
        else:
            y = int(pos)
        return y < self.getMinBuildHeight() or y >= self.getMaxBuildHeight()

    def canSeeSky(self, pos):
        """对应 canSeeSky(BlockPos)：这个位置能不能看到天。

        没有世界实现时保守返回 True（露天），
        这样依赖它的逻辑不会因为「查不到」而误判成全封闭。
        """
        return True

    def getBiome(self, pos):
        """对应 getBiome(BlockPos)：所在生物群系。"""
        return self._access.getBiome(_as_pos(pos)) \
            if hasattr(self._access, "getBiome") else None


class LevelAccessor(LevelReader):
    """
    对应 net.minecraft.world.level.LevelAccessor。

    在 LevelReader 之上加**写**能力。真实模组用 4 次，
    例如 `block.dowse((Entity) player, (LevelAccessor) level, pos, state)`
    （避雷针的引雷判定需要能改方块）。

    另外它还给「事件」能力（`gameEvent` / `levelEvent`）——
    真实代码会在这个接口上调它们。
    """

    def setBlock(self, pos, state, flags=3):
        """对应 setBlock(BlockPos, BlockState, int)。"""
        return self._access.setBlock(_as_pos(pos), state, flags)

    def setBlockAndUpdate(self, pos, state):
        return self._access.setBlock(pos, state, 3)

    def setBlockEntity(self, pos, block_entity):
        self._access.setBlockEntity(_as_pos(pos), block_entity)
        return None

    def destroyBlock(self, pos, drop_items=True):
        """对应 destroyBlock(BlockPos, boolean)。"""
        pos = _as_pos(pos)
        state = self._access.getBlockState(pos)
        if state is None or state.isAir():
            return False
        self._access.setBlock(pos, None, 3)
        return True

    def levelEvent(self, event_id, pos, data=0):
        """对应 levelEvent(int, BlockPos, int)。"""
        self._access.levelEvent(int(event_id), _as_pos(pos), int(data))
        return None

    def gameEvent(self, event, pos, context=None):
        """对应 gameEvent(Holder, BlockPos, Context)。"""
        self._access.gameEvent(event, _as_pos(pos), context)
        return None

    def sendBlockUpdated(self, pos, old_state, new_state, flags=3):
        self._access.sendBlockUpdated(_as_pos(pos), old_state, new_state, flags)
        return None

    def isClientSide(self):
        """对应 isClientSide()。"""
        return bool(self._access.isClientSide())

    def getRandom(self):
        """对应 getRandom()：世界随机源。"""
        if getattr(self, "_random", None) is None:
            try:
                from java_stdlib.util import JavaRandom
            except ImportError:
                from util import JavaRandom  # type: ignore
            self._random = JavaRandom()
        return self._random


class Level(LevelAccessor):
    """
    对应 net.minecraft.world.level.Level。

    它是「世界」的句柄：所有方块读写、实体增删、音效事件都从这里走。
    真实代码里 36 个文件引用了它，是最核心的入口之一。

    **继承链照抄 Java**：Level → LevelAccessor → LevelReader → BlockGetter。
    所以一个 Level 可以直接传给形参是 BlockGetter 的方法。
    """

    # 同一个 LevelAccess 始终对应同一个 Level 对象。
    # 用 id(access) 做键而不是 access 本身：LevelAccess 可能不实现 __hash__，
    # 而且我们就是要「按对象身份」而不是「按内容相等」来对应。
    _wrappers = {}

    def __init__(self, access, dimension=u"minecraft:overworld"):
        if access is None:
            raise IllegalArgumentException(
                u"Level 需要 LevelAccess（见 level_access.py）")
        LevelAccessor.__init__(self, access)
        self._dimension = java_to_string(dimension)

    # ---------------- 构造与对应 ----------------

    @staticmethod
    def wrap(access):
        """
        取（或创建）某个 LevelAccess 对应的 Level 对象。

        保证 `entity.level() is other.level()` 在同一个世界下为真 ——
        真实代码会用这个身份判断确认两个实体是否同界。
        """
        if access is None:
            raise IllegalArgumentException(u"wrap 收到 None")
        key = id(access)
        wrapper = Level._wrappers.get(key)
        if wrapper is None or wrapper._access is not access:
            wrapper = Level(access)
            Level._wrappers[key] = wrapper
        return wrapper

    @staticmethod
    def resetWrappers():
        """清空对应表（自测隔离用）。"""
        Level._wrappers = {}
        return None

    # 取底层适配器：继承自 BlockGetter（见上面的接口体系）
    #
    # 关于下方「方块」与「方块实体」两节：
    #   getBlockState / setBlock / setBlockAndUpdate / isEmptyBlock /
    #   getFluidState / destroyBlock / getBlockEntity / setBlockEntity /
    #   levelEvent / gameEvent / sendBlockUpdated / getRandom / isClientSide
    #   **全部继承自 LevelAccessor / LevelReader / BlockGetter**，
    #   这里不再重复定义 —— 重复写两份迟早会漂移
    #   （上一步加接口体系时就发现 Level 里已经有一整套同名实现了）。
    #
    # 只有下面这些是 Level **独有**的：端判断、维度、实体、音效、配方。

    def getCapability(self, capability, pos, *args):
        from neoforge.capabilities import BlockCapability
        if not isinstance(capability, BlockCapability):
            raise IllegalArgumentException("Expected BlockCapability")
        if len(args) == 1:
            return capability.getCapability(self, pos, context=args[0])
        if len(args) == 3:
            return capability.getCapability(self, pos, args[0], args[1], args[2])
        raise IllegalArgumentException("Expected context, or state/blockEntity/context")

    def isServerSide(self):
        return not self.isClientSide()

    # ---------------- 维度 ----------------

    def dimension(self):
        """对应 dimension()：维度标识。"""
        return self._dimension

    def setDimension(self, value):
        self._dimension = java_to_string(value)
        return self

    def getDescriptionId(self):
        return self._dimension

    # ---------------- 实体 ----------------

    def getEntity(self, entity_id):
        """对应 getEntity(int)：按数字 id 取实体（引用 3 次）。"""
        return self._access.getEntity(int(entity_id))

    def getEntities(self):
        """当前世界的实体列表。"""
        return list(self._access.getEntities())

    def addFreshEntity(self, entity):
        """
        对应 addFreshEntity(Entity)：把实体放进世界。

        会顺手把世界连接塞给实体，这样 `entity.level()` 立刻可用 ——
        免得调用方每次都要自己接一次。
        """
        if entity is None:
            raise IllegalArgumentException(u"addFreshEntity 收到 None")
        entity.setLevelAccess(self._access)
        entity_id = self._access.addEntity(entity)
        return entity_id

    def getNearestPlayer(self, position, max_distance):
        """
        对应 getNearestPlayer(...)：找最近的玩家。

        距离用平方比较（避免开方），与 Minecraft 的做法一致。
        """
        from minecraft.entity import Player
        pos = _as_pos(position)
        best = None
        best_distance = float(max_distance) * float(max_distance)

        for entity in self._access.getEntities():
            if not isinstance(entity, Player):
                continue
            other = entity.blockPosition()
            dx = other.getX() - pos.getX()
            dy = other.getY() - pos.getY()
            dz = other.getZ() - pos.getZ()
            distance = dx * dx + dy * dy + dz * dz
            if distance <= best_distance:
                best_distance = distance
                best = entity
        return best

    def getPlayers(self):
        """所有玩家（真实代码里常用于广播）。"""
        from minecraft.entity import Player
        result = []
        for entity in self._access.getEntities():
            if isinstance(entity, Player):
                result.append(entity)
        return result

    # ---------------- 声音与事件 ----------------

    def playSound(self, player, sound, volume=1.0, pitch=1.0):
        """对应 playSound(...)（引用 14 次）。"""
        self._access.playSound(player, sound, volume, pitch)
        return None

    def playSoundAt(self, pos, sound, volume=1.0, pitch=1.0):
        """
        对应 playSound(null, pos, sound, ...)：向所有玩家播。

        与 playSound 的区别是「有没有指定听众」；
        Java 用重载区分，Python 用独立名字（同 register_event_bus 的做法）。
        """
        self._access.playSound(None, sound, volume, pitch)
        return None

    # levelEvent / gameEvent / sendBlockUpdated / getRandom 都继承自
    # LevelAccessor（见上面的接口体系），这里不重复定义。

    def setRandom(self, random_source):
        """指定世界随机源（自测里用来让随机可复现）。"""
        self._random = random_source
        return self

    # ---------------- 身份 ----------------

    def equals(self, other):
        if not isinstance(other, Level):
            return False
        # 同一个适配器 = 同一个世界
        return self._access is other._access

    def hashCode(self):
        return hash_code(u"level:{}".format(id(self._access)))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._dimension

    def __repr__(self):
        side = u"client" if self.isClientSide() else u"server"
        return u"<Level {} [{}] via {}>".format(self._dimension, side,
                                                type(self._access).__name__)


class ServerLevel(Level):
    """
    对应 net.minecraft.server.level.ServerLevel（引用 20 次）。

    它保证只在服务端存在，并且能设置方块而不必担心客户端同步细节
    （那些由引擎处理）。

    `of(level)` 用来把已有的 Level 提升成 ServerLevel ——
    真实代码里到处是 `level instanceof ServerLevel` 的判断，
    对应到这里就是 `isinstance(level, ServerLevel)`。
    """

    def __init__(self, access, dimension=u"minecraft:overworld"):
        Level.__init__(self, access, dimension)
        if access.isClientSide():
            raise IllegalArgumentException(
                u"ServerLevel 不能在客户端侧创建（isClientSide 为真）")

    @staticmethod
    def of(level):
        """
        把 Level 提升成 ServerLevel；客户端侧返回 None。

        对应 Java 的：
            if (level instanceof ServerLevel) { ServerLevel sl = (ServerLevel) level; ... }
        """
        if level is None:
            return None
        if isinstance(level, ServerLevel):
            return level
        if level.isClientSide():
            return None
        return ServerLevel(level.getAccess(), level.dimension())

    def getServer(self):
        """对应 getServer()：服务端句柄（本实现返回适配器，落地时再具体化）。"""
        return self._access

    def __repr__(self):
        return u"<ServerLevel {} via {}>".format(self._dimension,
                                                 type(self._access).__name__)


# ============================================================
# 位置参数归一化
# ============================================================

def _as_pos(pos):
    """
    把外部传入的位置统一成 BlockPos。

    接受 BlockPos 本身、或 (x, y, z) 三元组 ——
    真实代码里这两种都常见，翻译后有时会退化成元组。
    """
    if isinstance(pos, BlockPos):
        return pos
    if isinstance(pos, (list, tuple)) and len(pos) == 3:
        return BlockPos(int(pos[0]), int(pos[1]), int(pos[2]))
    raise IllegalArgumentException(
        u"位置参数应是 BlockPos 或三元组，收到 {}".format(type(pos).__name__))


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.level.BlockGetter": BlockGetter,
    "net.minecraft.world.level.LevelReader": LevelReader,
    "net.minecraft.world.level.LevelAccessor": LevelAccessor,
    "net.minecraft.world.level.Level": Level,
    "net.minecraft.server.level.ServerLevel": ServerLevel,
}


__all__ = [
    "BlockGetter", "LevelReader", "LevelAccessor",
    "Level", "ServerLevel",
    "JAVA_MAP",
]

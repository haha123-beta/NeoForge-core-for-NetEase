# -*- coding: utf-8 -*-
# minecraft/level_access.py
# θ 层：世界访问接口（引擎适配点）
#
# 为什么需要这一层
# ----------------
# `Level.getBlockState(pos)` / `setBlock(...)` / `playSound(...)` 这些
# 真实操作必须落到网易引擎上，而引擎接口的确认还没完成（见概览.md
# 「待验证的部署问题」）。如果直接在 Level 里写引擎调用，
# 整个 θ 层就没法自测，而且一旦接口名不对就要大改。
#
# 所以把「需要引擎」的操作全部收进这个接口：
#   - Level / Entity / Player 只调这里的抽象方法，不碰引擎；
#   - InMemoryLevelAccess 让整条链路脱离引擎跑起来（自测用）；
#   - LoggingLevelAccess 把「本来会做什么」打出来（真机核对用）；
#   - 真实适配器等接口确认后再写，只改这一个文件。
#
# 这与 γ 层 injector 的 EngineAdapter 是同一个思路（那边管资源注入，
# 这边管世界读写），刻意保持一致的形态：抽象基类 + 空实现 + 日志实现。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import
import math
from minecraft.navigation import find_flat_path
from minecraft.attributes import Attributes

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
    )
    from java_stdlib.lang import java_to_string
    from minecraft.core import BlockPos
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
    )
    from lang import java_to_string  # type: ignore
    from core import BlockPos  # type: ignore


class ILevelAccess(object):
    """
    世界访问接口。

    每个方法都对应真实模组用到的一个 Level 操作
    （引用次数来自 dev/scan_neoforge_api.py 的统计）：

        getBlockState       40 次
        setBlock            13 次
        playSound           14 次
        gameEvent           11 次
        levelEvent           8 次
        getBlockEntity       7 次
        getFluidState        5 次
        isClientSide         2 次

    实现方只需覆盖自己支持的方法；未覆盖的会走基类的
    「不支持」实现（返回安全默认值并可选地记录），
    以免一个没接上的方法就让整条链路崩掉。
    """

    name = u"abstract"

    def __init__(self):
        self.unsupported = []      # [(方法名, 参数)] 便于诊断缺口

    # ---------------- 端判断 ----------------

    def isClientSide(self):
        """当前是不是客户端侧。真实代码用它区分双端逻辑。"""
        return self._unsupported(u"isClientSide")

    # ---------------- 方块读写 ----------------

    def getBlockState(self, pos):
        """取某个位置的方块状态。没有方块时返回 None。"""
        return self._unsupported(u"getBlockState", pos)

    def setBlock(self, pos, state, flags=3):
        """
        设置方块状态。

        flags 与 Minecraft 一致：1=更新邻居，2=发给客户端，3=两者都做。
        返回值表示「是否发生了改变」。
        """
        return self._unsupported(u"setBlock", pos, state, flags)

    def setBlockAndUpdate(self, pos, state):
        """对应 setBlockAndUpdate(pos, state)：等价于 flags=3。"""
        return self.setBlock(pos, state, 3)

    def isEmptyBlock(self, pos):
        """对应 isEmptyBlock(pos)：该位置是不是空气。"""
        state = self.getBlockState(pos)
        if state is None:
            return True
        return state.isAir()

    def getFluidState(self, pos):
        """对应 getFluidState(pos)：该位置的流体状态。"""
        return self._unsupported(u"getFluidState", pos)

    # ---------------- 方块实体 ----------------

    def getBlockEntity(self, pos):
        """对应 getBlockEntity(pos)：该位置的方块实体（没有则 None）。"""
        return self._unsupported(u"getBlockEntity", pos)

    def setBlockEntity(self, pos, block_entity):
        """本实现新增：登记方块实体（真实引擎里由 setBlock 连带创建）。"""
        return self._unsupported(u"setBlockEntity", pos, block_entity)

    # ---------------- 实体 ----------------

    def moveEntityTo(self, entity, position, speed, callback):
        self._unsupported("moveEntityTo", entity, position, speed)
        raise IllegalStateException("Navigation is not implemented by this adapter")

    def stopEntityNavigation(self, entity):
        self._unsupported("stopEntityNavigation", entity)
        raise IllegalStateException("Navigation cancellation is not implemented")

    def tickEntityNavigation(self, entity):
        return None

    def getEntity(self, entity_id):
        """对应 getEntity(int)：按数字 id 取实体。"""
        return self._unsupported(u"getEntity", entity_id)

    def addEntity(self, entity):
        """把实体放进世界。"""
        return self._unsupported(u"addEntity", entity)

    def removeEntity(self, entity):
        """把实体移出世界。"""
        return self._unsupported(u"removeEntity", entity)

    def getEntities(self):
        """当前世界里的实体列表。"""
        return self._unsupported(u"getEntities")

    # ---------------- 声音与事件 ----------------

    def playSound(self, player, sound, volume=1.0, pitch=1.0):
        """对应 playSound(...)：播音效（引用 14 次）。"""
        return self._unsupported(u"playSound", player, sound, volume, pitch)

    def levelEvent(self, event_id, pos, data=0):
        """对应 levelEvent(int, BlockPos, int)：世界级事件（引用 8 次）。"""
        return self._unsupported(u"levelEvent", event_id, pos, data)

    def gameEvent(self, event, pos, context=None):
        """对应 gameEvent(...)：给游戏事件系统发信号（引用 11 次）。"""
        return self._unsupported(u"gameEvent", event, pos, context)

    def noteDroppedItems(self, pos, stacks):
        self._unsupported("noteDroppedItems", pos, stacks)
        raise IllegalStateException("World item drops are not implemented")

    def sendBlockUpdated(self, pos, old_state, new_state, flags=3):
        """对应 sendBlockUpdated(...)：通知客户端方块变了。"""
        return self._unsupported(u"sendBlockUpdated", pos, old_state,
                                 new_state, flags)

    # ---------------- 内部 ----------------

    def _unsupported(self, method_name, *args):
        """
        未实现的方法：记录并返回 None。

        为什么**不抛异常**：世界读写失败不该让整个模组崩掉 ——
        例如一个没接上的音效方法不该导致方块逻辑中断。
        但缺口必须留痕，所以记进 unsupported，由 assert_no_gaps() 检查。
        """
        self.unsupported.append((method_name, args))
        return None

    def assert_no_gaps(self):
        """
        自测用：确认没有任何操作走到了「不支持」分支。

        这些缺口就是「等引擎确认后要补的接口」清单。
        """
        if self.unsupported:
            names = sorted(set([item[0] for item in self.unsupported]))
            raise IllegalStateException(
                u"有以下世界操作未被适配: {}".format(u", ".join(names)))
        return True

    def __repr__(self):
        return u"<{} 缺口 {} 个>".format(type(self).__name__,
                                         len(self.unsupported))


class InMemoryLevelAccess(ILevelAccess):
    def noteDroppedItems(self, pos, stacks):
        if not hasattr(self, "dropped_items"):
            self.dropped_items = []
        self.dropped_items.append((pos, [stack.copy() for stack in stacks]))


    """
    纯内存的世界实现。

    它让 `Level` / `Entity` / `ItemStack` 整条链路**完全脱离引擎**跑起来，
    是这一层能被自测的前提。方块用 (x,y,z) 元组做键，
    实体用数字 id 做键 —— 与 Minecraft 的组织方式一致。

    真实引擎适配器接上后，这个实现仍然有用：
      - 自测里断言逻辑；
      - 真机上作为「影子世界」做离线校验。
    """

    name = u"in-memory"

    def __init__(self, client_side=False):
        ILevelAccess.__init__(self)
        self._client_side = bool(client_side)
        self._blocks = {}          # (x,y,z) -> BlockState
        self._block_entities = {}  # (x,y,z) -> 方块实体
        self._fluids = {}          # (x,y,z) -> FluidState
        self._entities = {}        # id -> entity
        self._next_entity_id = [0]
        self._navigation = {}

        # 调用记录：自测里既验「结果」也验「过程」
        self.sounds_played = []
        self.level_events = []
        self.game_events = []
        self.block_updates = []

    # ---------------- 端 ----------------

    def isClientSide(self):
        return self._client_side

    def setClientSide(self, value):
        self._client_side = bool(value)
        return None

    # ---------------- 键换算 ----------------

    @staticmethod
    def _key(pos):
        if isinstance(pos, BlockPos):
            return (pos.getX(), pos.getY(), pos.getZ())
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            return (int(pos[0]), int(pos[1]), int(pos[2]))
        raise IllegalArgumentException(
            u"位置参数应是 BlockPos 或三元组，收到 {}".format(type(pos).__name__))

    # ---------------- 方块 ----------------

    def getBlockState(self, pos):
        return self._blocks.get(self._key(pos))

    def setBlock(self, pos, state, flags=3):
        key = self._key(pos)
        old = self._blocks.get(key)
        if state is None:
            self._blocks.pop(key, None)
        else:
            self._blocks[key] = state

        changed = old != state
        if changed:
            self.block_updates.append((key, old, state, int(flags)))
        return changed

    def getFluidState(self, pos):
        return self._fluids.get(self._key(pos))

    def setFluidState(self, pos, fluid_state):
        key = self._key(pos)
        if fluid_state is None:
            self._fluids.pop(key, None)
        else:
            self._fluids[key] = fluid_state
        return None

    # ---------------- 方块实体 ----------------

    def getBlockEntity(self, pos):
        return self._block_entities.get(self._key(pos))

    def setBlockEntity(self, pos, block_entity):
        self._block_entities[self._key(pos)] = block_entity
        return None

    # ---------------- 实体 ----------------

    def moveEntityTo(self, entity, position, speed, callback):
        self.stopEntityNavigation(entity)
        path = find_flat_path(self, entity, position)
        if path is None:
            callback(-3)
            return False
        self._navigation[entity.getId()] = [path, float(speed), callback]
        return True

    def stopEntityNavigation(self, entity):
        move = self._navigation.pop(entity.getId(), None)
        if move is not None:
            move[2](3)

    def tickEntityNavigation(self, entity):
        move = self._navigation.get(entity.getId())
        if move is None:
            return
        path, speed, callback = move
        if not path:
            self._navigation.pop(entity.getId(), None)
            callback(0)
            return
        target = path[0]
        block = self.getBlockState(BlockPos.containing(*target))
        if block is not None and not block.isAir():
            self._navigation.pop(entity.getId(), None)
            callback(2)
            return
        dx, dy, dz = target[0] - entity.getX(), target[1] - entity.getY(), target[2] - entity.getZ()
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        step = entity.getAttributeValue(Attributes.MOVEMENT_SPEED) * speed
        if distance <= step or distance < 0.000001:
            entity.setPos(target)
            path.pop(0)
            if not path:
                self._navigation.pop(entity.getId(), None)
                callback(0)
        elif step > 0:
            entity.setPos(entity.getX() + dx * step / distance,
                          entity.getY() + dy * step / distance,
                          entity.getZ() + dz * step / distance)

    def getEntity(self, entity_id):
        return self._entities.get(int(entity_id))

    def addEntity(self, entity):
        if entity is None:
            raise IllegalArgumentException(u"addEntity 收到 None")
        entity_id = getattr(entity, "_id", None)
        if entity_id is None:
            self._next_entity_id[0] += 1
            entity_id = self._next_entity_id[0]
            try:
                entity._id = entity_id
            except AttributeError:
                pass
        else:
            self._next_entity_id[0] = max(self._next_entity_id[0], entity_id)
        self._entities[entity_id] = entity
        return entity_id

    def removeEntity(self, entity):
        self.stopEntityNavigation(entity)
        entity_id = getattr(entity, "_id", None)
        if entity_id is None:
            return False
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    def getEntities(self):
        return [self._entities[key] for key in sorted(self._entities)]

    def entityCount(self):
        return len(self._entities)

    # ---------------- 声音与事件 ----------------

    def playSound(self, player, sound, volume=1.0, pitch=1.0):
        self.sounds_played.append((player, sound, float(volume), float(pitch)))
        return None

    def levelEvent(self, event_id, pos, data=0):
        self.level_events.append((int(event_id), self._key(pos), int(data)))
        return None

    def gameEvent(self, event, pos, context=None):
        self.game_events.append((event, self._key(pos), context))
        return None

    def sendBlockUpdated(self, pos, old_state, new_state, flags=3):
        self.block_updates.append((self._key(pos), old_state, new_state,
                                   int(flags)))
        return None

    # ---------------- 诊断 ----------------

    def blockCount(self):
        return len(self._blocks)

    def clear(self):
        for entity in list(self._entities.values()):
            self.stopEntityNavigation(entity)
        self._navigation = {}
        self._blocks = {}
        self._block_entities = {}
        self._fluids = {}
        self._entities = {}
        self.sounds_played = []
        self.level_events = []
        self.game_events = []
        self.block_updates = []
        return None

    def __repr__(self):
        return u"<InMemoryLevelAccess {} 方块 {} 实体>".format(
            len(self._blocks), len(self._entities))


class LoggingLevelAccess(InMemoryLevelAccess):
    """
    记录并打印每一次世界操作的实现。

    真机调试用：先看「本来会做什么」对不对，再接真实引擎。
    行为与内存实现完全一致（继承它），只是多打日志。
    """

    name = u"logging"

    def __init__(self, client_side=False, logger=None):
        InMemoryLevelAccess.__init__(self, client_side)
        self._logger = logger or (lambda text: print(text))
        self.log = []

    def _record(self, text):
        self.log.append(text)
        self._logger(u"[世界] {}".format(text))

    def setBlock(self, pos, state, flags=3):
        result = InMemoryLevelAccess.setBlock(self, pos, state, flags)
        self._record(u"setBlock({}, {}, flags={}) -> {}".format(
            pos, state, flags, result))
        return result

    def playSound(self, player, sound, volume=1.0, pitch=1.0):
        self._record(u"playSound({}, {}, {}, {})".format(
            player, sound, volume, pitch))
        return InMemoryLevelAccess.playSound(self, player, sound, volume, pitch)

    def levelEvent(self, event_id, pos, data=0):
        self._record(u"levelEvent({}, {}, {})".format(event_id, pos, data))
        return InMemoryLevelAccess.levelEvent(self, event_id, pos, data)

    def gameEvent(self, event, pos, context=None):
        self._record(u"gameEvent({}, {}, {})".format(event, pos, context))
        return InMemoryLevelAccess.gameEvent(self, event, pos, context)


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    # 这一层没有直接的 Java 对应物（是为落地引擎而设的适配点），
    # 但登记一下便于覆盖率工具与文档引用。
    "neocore.ILevelAccess": ILevelAccess,
    "neocore.InMemoryLevelAccess": InMemoryLevelAccess,
}


__all__ = [
    "ILevelAccess", "InMemoryLevelAccess", "LoggingLevelAccess",
    "JAVA_MAP",
]

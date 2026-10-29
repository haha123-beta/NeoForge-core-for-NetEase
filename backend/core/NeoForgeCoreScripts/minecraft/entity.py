# -*- coding: utf-8 -*-
# minecraft/entity.py
# θ 层：实体（Entity / LivingEntity / Player）
#
# 真实用法（引用次数来自 dev/scan_neoforge_api.py）：
#   Player        36 个文件引用
#   Entity        31 个
#   ServerPlayer  20 个
#   LivingEntity  20 个
#
#   实例方法：isShiftKeyDown 15、getInventory 14、getUUID 10、
#             getMainHandItem 9、getItemInHand 9、hurt 8、
#             getId 7、getAbilities 7、setHealth 6、getMaxHealth 5
#
# **引擎边界**：实体的位置、生命值、背包这些都存在引擎里。
# 所以凡是要读写世界或引擎的地方一律走 `LevelAccess`
# （见 level_access.py），本模块自己不做任何引擎调用。
# 这样实体逻辑可以脱离引擎完整自测，接引擎时也只改适配器。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

import math as _math
import uuid as _uuid
from minecraft.attributes import Attributes, AttributeSupplier, AttributeMap
from minecraft.goals import GoalSelector
from minecraft.nbt import CompoundTag
from minecraft.synched_entity_data import SynchedEntityData
from minecraft.entity_storage import save_entity, load_entity
from minecraft.navigation import GroundPathNavigation, LookControl
from minecraft.combat import DamageSources, hurt as apply_damage, heal as apply_heal

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string, Enum, JavaString
    from minecraft.core import AABB, BlockPos, Vec3
    from minecraft.item import ItemStack
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string, Enum, JavaString  # type: ignore
    from core import AABB, BlockPos, Vec3  # type: ignore
    from item import ItemStack  # type: ignore


# ============================================================
# UUID 辅助
# ============================================================

class _UuidFactory(object):
    """
    实体 UUID 的生成器。随机 UUID 避免脚本重启后与存档实体冲突。
    """

    def __init__(self):
        self._next = [0]

    def next(self):
        self._next[0] += 1
        return str(_uuid.uuid4())

    def reset(self):
        self._next = [0]
        return None


UUIDS = _UuidFactory()


# ============================================================
# Entity
# ============================================================

from neoforge.attachment import AttachmentHolder


class Entity(AttachmentHolder):
    """
    对应 net.minecraft.world.entity.Entity。

    它是所有实体的基类：有位置、有朝向、有 UUID、能受伤。
    真实代码主要用它的坐标与身份，所以这两块做得最完整。

    位置用 Vec3 保存（浮点），BlockPos 按需算出来 ——
    与 Minecraft 一致：实体是连续坐标，不是格子坐标。
    """

    def __init__(self, level_access=None, position=None, identifier=None):
        # LevelAccess 允许延迟注入：模块加载顺序上 level.py 会反过来引用
        # entity.py，构造时立刻强制要求会形成循环依赖。
        # 但只要在调用世界相关方法**之前**设上就安全（见 setLevelAccess）。
        # Java constructors use (EntityType, Level); retain the older access/pos API.
        self._entity_type = None
        self._level_wrapper = None
        if isinstance(level_access, _EntityType):
            self._entity_type = level_access
            self._level_wrapper = position
            identifier = level_access.toString()
            level_access = position.getAccess()
            position = None
        self._level_access = level_access
        self.tickCount = 0
        self._persistent_data = CompoundTag()

        # 数字 id：由 LevelAccess 在 addEntity 时分配
        self._id = None
        self._uuid = UUIDS.next()

        if position is None:
            self._position = Vec3(0.0, 0.0, 0.0)
        elif isinstance(position, Vec3):
            self._position = position
        else:
            # 接受 (x, y, z) 三元组
            self._position = Vec3(position[0], position[1], position[2])

        self._y_rot = 0.0
        self._x_rot = 0.0
        self._removed = False
        self._identifier = identifier
        builder = SynchedEntityData.Builder(self)
        self._invoke_entity_hook('defineSynchedData', builder)
        self._entity_data = builder.build()

    # ---------------- 世界连接 ----------------

    def setLevelAccess(self, level_access):
        if self._level_wrapper is not None and self._level_wrapper.getAccess() is not level_access:
            self._level_wrapper = None
        self._level_access = level_access
        return self

    def getLevelAccess(self):
        if self._level_access is None:
            raise IllegalArgumentException(
                u"实体还没有连接世界（请先调用 setLevelAccess，"
                u"或用 World.spawn 创建实体）")
        return self._level_access

    # ---------------- 身份 ----------------

    def getId(self):
        """对应 getId()：数字 id（未加入世界时为 None）。"""
        return self._id

    def getUUID(self):
        """对应 getUUID()（真实用了 10 次）。"""
        return self._uuid

    def setUUID(self, value):
        self._uuid = java_to_string(value)
        return self

    # ---------------- 位置 ----------------

    def position(self):
        """
        对应 position()：当前连续坐标。

        **返回拷贝**，不是内部引用。
        Minecraft 的 Vec3 是不可变的，所以 Java 里返回引用没问题；
        但本实现的 Vec3 字段是可写的（x/y/z 公开），
        返回引用会让 `entity.position().x = 999` 静默改掉实体坐标。
        返回拷贝把这个坑堵住。
        """
        return Vec3(self._position.x, self._position.y, self._position.z)

    def _invoke_entity_hook(self, name, value):
        # Engine/storage entrypoints do not carry a generated Java signature.
        # Preserve the reviewed virtual overload when crossing into source code.
        method = getattr(self, name)
        if (getattr(type(self), '_nc_JavaMethodsABI', 0) == 1 and
                getattr(type(self), '_nc_RuntimeSuperclassABI', 0) == 1):
            kind = ('net.minecraft.network.syncher.SynchedEntityData.Builder'
                    if name == 'defineSynchedData' else 'net.minecraft.nbt.CompoundTag')
            return method(value, _nc_java_signature=(kind,))
        return method(value)

    def defineSynchedData(self, builder):
        return None

    def getEntityData(self):
        return self._entity_data

    def onSyncedDataUpdated(self, accessor):
        return None

    def getPersistentData(self):
        return self._persistent_data

    def saveWithoutId(self, tag):
        return save_entity(self, tag, include_id=False)

    def save(self, tag):
        if self.isRemoved():
            return False
        save_entity(self, tag)
        return True

    def load(self, tag):
        load_entity(self, tag)

    def addAdditionalSaveData(self, tag):
        return None

    def readAdditionalSaveData(self, tag):
        return None

    def setPos(self, x, y=None, z=None):
        """对应 setPos(double,double,double) / setPos(Vec3)。"""
        if y is None and z is None:
            other = x
            if isinstance(other, Vec3):
                self._position = Vec3(other.x, other.y, other.z)
            else:
                self._position = Vec3(other[0], other[1], other[2])
        else:
            self._position = Vec3(x, y, z)
        return self

    def getX(self):
        return self._position.x

    def getY(self):
        return self._position.y

    def getZ(self):
        return self._position.z

    def blockPosition(self):
        """
        对应 blockPosition()：所在方块坐标（向下取整）。

        走 BlockPos.containing 而不是自己 int()：
        负数坐标必须向下取整（-0.5 -> -1），自己截断会得到 0。
        """
        return BlockPos.containing(self._position)

    def getEyePosition(self):
        """对应 getEyePosition()：眼睛位置（位置 + 身高）。"""
        return Vec3(self._position.x,
                    self._position.y + self.getEyeHeight(),
                    self._position.z)

    def getEyeHeight(self):
        return 0.0

    def getWidth(self):
        return self._entity_type.getWidth() if self._entity_type is not None else 0.6

    def getHeight(self):
        return self._entity_type.getHeight() if self._entity_type is not None else 1.8

    def getBoundingBox(self):
        """对应 getBoundingBox()：碰撞箱（以位置为底面中心）。"""
        half = self.getWidth() / 2.0
        return AABB(self._position.x - half, self._position.y,
                    self._position.z - half,
                    self._position.x + half,
                    self._position.y + self.getHeight(),
                    self._position.z + half)

    # ---------------- 朝向 ----------------

    def getYRot(self):
        return self._y_rot

    def getXRot(self):
        return self._x_rot

    def setYRot(self, value):
        self._y_rot = float(value)
        return self

    def setXRot(self, value):
        self._x_rot = float(value)
        return self

    def getViewVector(self, partial_tick=1.0):
        """
        对应 getViewVector(float)：朝向单位向量。

        按 Minecraft 的角度约定：yaw 绕 y 轴，0 度朝 +Z（南）。
        """
        yaw = self._y_rot * _math.pi / 180.0
        pitch = self._x_rot * _math.pi / 180.0
        horizontal = _math.cos(pitch)
        return Vec3(-_math.sin(yaw) * horizontal,
                    -_math.sin(pitch),
                    _math.cos(yaw) * horizontal)

    # ---------------- 世界 ----------------

    def level(self):
        """对应 level()：所属世界（Level 是 LevelAccess 的薄包装）。"""
        from minecraft.level import Level
        if self._level_wrapper is not None and self._level_wrapper.getAccess() is self.getLevelAccess():
            return self._level_wrapper
        return Level.wrap(self.getLevelAccess())

    def getLevel(self):
        return self.level()

    # ---------------- 生命周期 ----------------

    def remove(self, reason=None):
        """对应 remove(RemovalReason)：从世界移除自己。"""
        access = self._level_access
        if access is not None:
            # A rejected engine deletion must remain retryable, not disappear
            # from the runtime while the real entity still exists.
            access.removeEntity(self)
        self._removed = True
        return None

    def discard(self):
        """对应 discard()：丢弃（等价于移除）。"""
        return self.remove()

    def isRemoved(self):
        return self._removed

    def isAlive(self):
        return not self._removed

    # ---------------- 注册信息 ----------------

    def setIdentifier(self, value):
        self._identifier = java_to_string(value)
        return self

    def getIdentifier(self):
        return self._identifier

    def copyAttachmentsFrom(self, original, isDeath):
        from neoforge.attachment import copy_entity_attachments
        copy_entity_attachments(original, self, bool(isDeath))

    def getCapability(self, capability, context=None):
        from neoforge.capabilities import EntityCapability
        if not isinstance(capability, EntityCapability):
            raise IllegalArgumentException("Expected EntityCapability")
        return capability.getCapability(self, context)

    def getType(self):
        """
        对应 getType()：实体类型。

        同 identifier 的实体共享一个 EntityType 对象（懒建），
        这样才能用 `entity.getType() == EntityType.PIG` 做身份比较。
        """
        if self._entity_type is not None:
            return self._entity_type
        return EntityType.of(self._identifier or type(self).__name__)

    def tick(self):
        self.tickCount += 1

    def distanceToSqr(self, other):
        dx = self.getX() - other.getX()
        dy = self.getY() - other.getY()
        dz = self.getZ() - other.getZ()
        return dx * dx + dy * dy + dz * dz

    def distanceTo(self, other):
        return _math.sqrt(self.distanceToSqr(other))

    # ---------------- 身份比较 ----------------

    def equals(self, other):
        if not isinstance(other, Entity):
            return False
        # Minecraft 用 UUID 判断是不是同一个实体
        return self._uuid == other._uuid

    def hashCode(self):
        return hash_code(self._uuid)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return u"{}#{}".format(self._identifier or type(self).__name__,
                               self._uuid[-4:])

    def __repr__(self):
        return u"<{} at {}>".format(self.__str__(), self._position.toString())


# ============================================================
# LivingEntity
# ============================================================

class LivingEntity(Entity):
    """
    对应 net.minecraft.world.entity.LivingEntity。

    在 Entity 基础上加生命值与受伤逻辑。
    真实引用：hurt 8 次、setHealth 6 次、getMaxHealth 5 次。
    """

    def __init__(self, level_access=None, position=None, identifier=None,
                 max_health=20.0):
        Entity.__init__(self, level_access, position, identifier)
        supplier = (self._entity_type._attributes
                    if self._entity_type is not None else None)
        if supplier is None:
            supplier = self.createLivingAttributes().add(
                Attributes.MAX_HEALTH, max_health).build()
        self._attributes = AttributeMap(supplier)
        self._health = self.getMaxHealth()
        self._last_hurt_by_player = None
        self._last_hurt_by_mob = None
        self.damage_taken = []      # [(伤害量, 伤害来源)] 便于自测

    # ---------------- 生命值 ----------------

    @staticmethod
    def createLivingAttributes():
        return (AttributeSupplier.builder().add(Attributes.MAX_HEALTH)
                .add(Attributes.KNOCKBACK_RESISTANCE)
                .add(Attributes.MOVEMENT_SPEED).add(Attributes.ARMOR)
                .add(Attributes.ARMOR_TOUGHNESS))

    def getAttributes(self):
        return self._attributes

    def getAttribute(self, attribute):
        return self._attributes.getInstance(attribute)

    def getAttributeValue(self, attribute):
        return self._attributes.getValue(attribute)

    def getAttributeBaseValue(self, attribute):
        return self._attributes.getBaseValue(attribute)

    def getMaxHealth(self):
        return self.getAttributeValue(Attributes.MAX_HEALTH)

    def setMaxHealth(self, value):
        self.getAttribute(Attributes.MAX_HEALTH).setBaseValue(value)
        if self._health > self.getMaxHealth():
            self._health = self.getMaxHealth()
        return self

    def getHealth(self):
        return self._health

    def setHealth(self, value):
        """
        对应 setHealth(float)。

        **会被夹到 [0, maxHealth]** —— 与 Java 一致。
        直接赋值的话 setHealth(999) 会让实体变得打不死。
        """
        value = float(value)
        if value < 0.0:
            value = 0.0
        if value > self.getMaxHealth():
            value = self.getMaxHealth()
        self._health = value
        return None

    def isAlive(self):
        return not self._removed and self._health > 0.0

    def heal(self, amount):
        apply_heal(self, amount)
        return None

    # ---------------- 受伤 ----------------

    def hurt(self, source, amount):
        """
        对应 hurt(DamageSource, float)：受伤（引用 8 次）。

        返回「是否真的受到了伤害」—— 与 Java 一致：
        已死或无敌的实体返回 False，且不记录伤害。
        """
        return apply_damage(self, source, amount)

    def damageSources(self):
        return DamageSources()

    def getLastHurtByMob(self):
        return self._last_hurt_by_mob

    def setLastHurtByMob(self, entity):
        self._last_hurt_by_mob = entity

    def die(self, source):
        """对应 die(DamageSource)：死亡处理。"""
        self._health = 0.0
        self.remove()
        return None

    def setLastHurtByPlayer(self, player):
        """对应 setLastHurtByPlayer(Player)（真实用了 2 次）。"""
        self._last_hurt_by_player = player
        return None

    def getLastHurtByPlayer(self):
        return self._last_hurt_by_player

    def getEyeHeight(self):
        if self._entity_type is not None:
            return self._entity_type._eye_height
        return self.getHeight() * 0.85

    def __repr__(self):
        return u"<{} {}hp at {}>".format(self.__str__(), self._health,
                                         self._position.toString())


# ============================================================
# 背包
# ============================================================

class Inventory(object):
    """
    对应 net.minecraft.world.entity.player.Inventory（引用 10 次）。

    Minecraft 的背包有固定分区：主背包 36 格 + 护甲 4 格 + 副手。
    这里保持同样的结构，因为真实代码会直接访问 `armor` 这类字段。
    """

    HOTBAR_SIZE = 9
    ARMOR_SIZE = 4

    def __init__(self, size=36):
        self.size = int(size)
        self.items = [ItemStack() for _index in range(self.size)]
        self.armor = [ItemStack() for _index in range(self.ARMOR_SIZE)]
        self.selected = 0
        self.offhand = ItemStack()
        self.change_count = 0

    # ---------------- 槽位 ----------------

    def getItem(self, slot):
        """对应 getItem(int)。-1 表示副手（与 Minecraft 一致）。"""
        slot = int(slot)
        if slot in (-1, self.size + self.ARMOR_SIZE):
            return self.offhand
        if self.size <= slot < self.size + self.ARMOR_SIZE:
            return self.armor[slot - self.size]
        if slot < 0 or slot >= self.size:
            raise IllegalArgumentException(
                u"背包槽位越界: {}（有效范围 0..{}）".format(slot,
                                                            self.size - 1))
        return self.items[slot]

    def setItem(self, slot, stack):
        """对应 setItem(int, ItemStack)。"""
        slot = int(slot)
        if slot in (-1, self.size + self.ARMOR_SIZE):
            self.offhand = stack
            return None
        if self.size <= slot < self.size + self.ARMOR_SIZE:
            self.armor[slot - self.size] = stack
            return None
        if slot < 0 or slot >= self.size:
            raise IllegalArgumentException(
                u"背包槽位越界: {}（有效范围 0..{}）".format(slot,
                                                            self.size - 1))
        self.items[slot] = stack
        return None

    def getContainerSize(self):
        return self.size + self.ARMOR_SIZE + 1

    def getMaxStackSize(self, stack=None):
        return 99 if stack is None else min(99, stack.getMaxStackSize())

    def setChanged(self):
        self.change_count += 1

    def removeItem(self, index, amount):
        if int(amount) <= 0:
            return ItemStack()
        result = self.getItem(index).split(int(amount))
        if not result.isEmpty():
            self.setChanged()
        return result

    def removeItemNoUpdate(self, index):
        stack = self.getItem(index)
        self.setItem(index, ItemStack())
        return stack

    def canPlaceItem(self, index, stack):
        self.getItem(index)
        return True

    def clearContent(self):
        for index in range(self.getContainerSize()):
            self.setItem(index, ItemStack())
        self.setChanged()

    def getSelected(self):
        return self.selected

    def setSelected(self, slot):
        slot = int(slot)
        if slot < 0 or slot >= self.HOTBAR_SIZE:
            raise IllegalArgumentException(
                u"快捷栏槽位越界: {}（有效范围 0..{}）".format(
                    slot, self.HOTBAR_SIZE - 1))
        self.selected = slot
        return None

    # ---------------- 查询 ----------------

    def getSelectedItem(self):
        """对应 getSelected()：当前主手物品。"""
        return self.items[self.selected]

    def isEmpty(self):
        for stack in self.items:
            if not stack.isEmpty():
                return False
        for stack in self.armor:
            if not stack.isEmpty():
                return False
        return self.offhand.isEmpty()

    def count(self):
        """所有非空槽位的数量（诊断用）。"""
        total = 0
        for stack in self.items:
            if not stack.isEmpty():
                total += 1
        for stack in self.armor:
            if not stack.isEmpty():
                total += 1
        if not self.offhand.isEmpty():
            total += 1
        return total

    def findSlot(self, item):
        """对应 findSlot(ItemLike)：第一个装着该物品的槽位，没有返回 -1。"""
        for index in range(self.size):
            stack = self.items[index]
            if not stack.isEmpty() and stack.isItem(item):
                return index
        return -1

    def add(self, stack):
        """
        对应 add(ItemStack)：把物品放进背包。

        先叠到已有的同类未满栈上，再找空格子 —— 与 Minecraft 一致。
        返回 True 表示全部放进去了。
        """
        if stack is None or stack.isEmpty():
            return True

        remaining = stack.getCount()
        maximum = stack.getMaxStackSize()

        # 先合并到已有栈
        for index in range(self.size):
            current = self.items[index]
            if current.isEmpty() or not current.isItem(stack.getItem()):
                continue
            space = maximum - current.getCount()
            if space <= 0:
                continue
            moved = min(space, remaining)
            current.grow(moved)
            remaining -= moved
            if remaining <= 0:
                stack.setCount(0)
                return True

        # 再找空格子
        for index in range(self.size):
            if self.items[index].isEmpty():
                placed = min(remaining, maximum)
                self.items[index] = ItemStack(stack.getItem(), placed)
                remaining -= placed
                if remaining <= 0:
                    stack.setCount(0)
                    return True

        stack.setCount(remaining)
        return False

    def clear(self):
        self.items = [ItemStack() for _index in range(self.size)]
        self.armor = [ItemStack() for _index in range(self.ARMOR_SIZE)]
        self.offhand = ItemStack()
        return None

    def __repr__(self):
        return u"<Inventory {} 个非空槽位>".format(self.count())


# ============================================================
# Abilities
# ============================================================

class Abilities(object):
    """
    对应 net.minecraft.world.entity.player.Abilities。

    字段名保持 Java 的写法（`mayfly` / `instabuild`），
    因为翻译后的代码会**直接访问这些字段**，不是通过 getter。
    """

    def __init__(self):
        self.mayfly = False
        self.flying = False
        self.instabuild = False        # 创造模式（瞬间破坏）
        self.invulnerable = False
        self.mayBuild = True
        self.walkingSpeed = 0.1
        self.flyingSpeed = 0.05

    def setCreative(self, value):
        """便利方法：一次性切成创造模式相关开关。"""
        self.instabuild = bool(value)
        self.invulnerable = bool(value)
        self.mayfly = bool(value)
        return self

    def __repr__(self):
        return u"<Abilities creative={}>".format(self.instabuild)


# ============================================================
# Player
# ============================================================

class Player(LivingEntity):
    """
    对应 net.minecraft.world.entity.player.Player（36 个文件引用，最高）。

    在 LivingEntity 基础上加：背包、潜行、能力、经验。
    """

    def __init__(self, level_access=None, position=None,
                 identifier=u"player", name=None):
        LivingEntity.__init__(self, level_access, position, identifier,
                              max_health=20.0)
        self._inventory = Inventory()
        self._sneaking = False
        self._abilities = Abilities()
        self._experience_points = 0
        self._experience_level = 0
        self._name = name
        self.awarded_stats = {}     # 统计名 -> 次数（便于自测）

    # ---------------- 背包与手持 ----------------

    def getInventory(self):
        """对应 getInventory()（引用 14 次）。"""
        return self._inventory

    def getMainHandItem(self):
        """对应 getMainHandItem()（引用 9 次）：主手物品。"""
        return self._inventory.getSelectedItem()

    def getItemInHand(self, hand):
        """
        对应 getItemInHand(InteractionHand)（引用 9 次）。

        与 getMainHandItem 的区别：这个按「哪只手」取。
        """
        name = java_to_string(hand).upper()
        if name.endswith(u"OFF_HAND"):
            return self._inventory.offhand
        return self._inventory.getSelectedItem()

    def setItemInHand(self, hand, stack):
        name = java_to_string(hand).upper()
        if name.endswith(u"OFF_HAND"):
            self._inventory.offhand = stack
        else:
            self._inventory.setItem(self._inventory.getSelected(), stack)
        return None

    # ---------------- 潜行 ----------------

    def isShiftKeyDown(self):
        """对应 isShiftKeyDown()（引用 15 次）：是否按下潜行键。"""
        return self._sneaking

    def setShiftKeyDown(self, value):
        """对应 setShiftKeyDown(boolean)：切换潜行状态。"""
        self._sneaking = bool(value)
        return None

    def isCrouching(self):
        return self._sneaking

    # ---------------- 能力 ----------------

    def getAbilities(self):
        """对应 getAbilities()（引用 7 次）。"""
        return self._abilities

    # ---------------- 经验 ----------------

    def giveExperiencePoints(self, amount):
        """对应 giveExperiencePoints(int)（真实用了 3 次）。"""
        amount = int(amount)
        if amount < 0:
            amount = 0
        self._experience_points += amount
        # 每 (等级+1)*7 点升一级（简化公式；真实公式与等级相关）
        while self._experience_points >= (self._experience_level + 1) * 7:
            self._experience_points -= (self._experience_level + 1) * 7
            self._experience_level += 1
        return None

    def getExperiencePoints(self):
        return self._experience_points

    def getExperienceLevel(self):
        return self._experience_level

    # ---------------- 统计 ----------------

    def awardStat(self, stat, amount=1):
        """对应 awardStat(...)（引用 7 次）：记一次统计。"""
        key = java_to_string(stat)
        self.awarded_stats[key] = self.awarded_stats.get(key, 0) + int(amount)
        return None

    def getStat(self, stat):
        return self.awarded_stats.get(java_to_string(stat), 0)

    # ---------------- 名字 ----------------

    def setName(self, value):
        self._name = java_to_string(value)
        return self

    def getName(self):
        """对应 getName()：玩家名（未设置时回退成 UUID 前 8 位）。"""
        if self._name is not None:
            return self._name
        return u"player_" + self._uuid[:8]

    def getGameProfile(self):
        """对应 getGameProfile()：用字典表示（真实代码只读 name / id）。"""
        return {u"name": self.getName(), u"id": self._uuid}

    def getEyeHeight(self):
        return 1.62

    def __repr__(self):
        return u"<Player {} {}hp>".format(self.getName(), self._health)


class ServerPlayer(Player):
    """
    对应 net.minecraft.server.level.ServerPlayer（引用 20 次）。

    与 Player 的区别：只在服务端存在，能代表「一个连接」——
    可以发消息、开界面。这些要落引擎，所以走 LevelAccess。
    """

    def __init__(self, level_access=None, position=None, name=None):
        Player.__init__(self, level_access, position, u"server_player", name)
        self.sent_messages = []
        self.opened_menus = []

    def sendSystemMessage(self, message):
        """对应 sendSystemMessage(Component)：给玩家发一条系统消息。"""
        self.sent_messages.append(message)
        return None

    def openMenu(self, menu_provider):
        """对应 openMenu(MenuProvider)（引用 9 次）。"""
        self.opened_menus.append(menu_provider)
        return None

    def __repr__(self):
        return u"<ServerPlayer {} {}hp>".format(self.getName(), self._health)


# ============================================================
# EntityType
# ============================================================

class Mob(LivingEntity):
    def __init__(self, entity_type=None, level=None):
        LivingEntity.__init__(self, entity_type, level)
        self.goalSelector = GoalSelector()
        self.targetSelector = GoalSelector()
        self._target = None
        self._no_ai = False
        self._navigation = GroundPathNavigation(self)
        self._look_control = LookControl(self)
        self.registerGoals()

    @staticmethod
    def createMobAttributes():
        return LivingEntity.createLivingAttributes().add(Attributes.FOLLOW_RANGE)

    def registerGoals(self):
        return None

    def getNavigation(self):
        return self._navigation

    def getLookControl(self):
        return self._look_control

    def getRandom(self):
        return self.level().getRandom()

    def doHurtTarget(self, target):
        if target is None or not target.isAlive() or not self.isAlive():
            return False
        attribute = self.getAttribute(Attributes.ATTACK_DAMAGE)
        if attribute is None:
            return False
        return target.hurt(self.damageSources().mobAttack(self), attribute.getValue())

    def getTarget(self):
        return self._target

    def setTarget(self, target):
        self._target = target

    def setNoAi(self, value):
        self._no_ai = bool(value)
        if self._no_ai:
            self._navigation.stop()
            self.goalSelector.stopAll()
            self.targetSelector.stopAll()

    def isNoAi(self):
        return self._no_ai

    def tick(self):
        Entity.tick(self)
        if not self.isAlive() or self.isNoAi():
            self.goalSelector.stopAll()
            self.targetSelector.stopAll()
            return
        if self._level_access is None or self.level().isClientSide():
            return
        self.targetSelector.tick()
        self.goalSelector.tick()
        self._navigation.tick()
        self._look_control.tick()

    def remove(self, reason=None):
        self._navigation.stop()
        self.goalSelector.stopAll()
        self.targetSelector.stopAll()
        return Entity.remove(self, reason)


class PathfinderMob(Mob):
    # Base inheritance only; navigation remains an explicit unsupported feature.
    pass


class Monster(PathfinderMob):
    @staticmethod
    def createMonsterAttributes():
        return Mob.createMobAttributes().add(Attributes.ATTACK_DAMAGE)


class MobCategory(Enum):
    def __init__(self):
        raise IllegalArgumentException('MobCategory is an enum; use its constants')
    def getName(self):
        return JavaString(java_to_string(self.name()).lower())
    def getSerializedName(self):
        return self.getName()


_category_values = []
for _category_name in ('MONSTER', 'CREATURE', 'AMBIENT', 'AXOLOTLS',
                       'UNDERGROUND_WATER_CREATURE', 'WATER_CREATURE', 'WATER_AMBIENT', 'MISC'):
    _category_value = object.__new__(MobCategory)
    _category_value._name = _category_name
    _category_value._ordinal = len(_category_values)
    _category_values.append(_category_value)
    setattr(MobCategory, _category_name, _category_value)
MobCategory._values = tuple(_category_values)


class _EntityType(object):
    """Registered entity metadata and factory; engine spawning is separate."""

    def __init__(self, identifier):
        self._identifier = java_to_string(identifier)
        self._factory = None
        self._category = MobCategory.MISC
        self._width = 0.6
        self._height = 1.8
        self._eye_height = 1.53
        self._serialize = True
        self._client_tracking_range = 5
        self._update_interval = 3
        self._attributes = None

    def getWidth(self):
        return self._width

    def getHeight(self):
        return self._height

    def getCategory(self):
        return self._category

    def create(self, level):
        if self._factory is None:
            raise IllegalArgumentException("No entity factory for " + self._identifier)
        entity = self._factory(self, level)
        if entity is not None and not isinstance(entity, Entity):
            raise IllegalArgumentException("Entity factory returned a non-Entity")
        return entity

    def getDescriptionId(self):
        return u"entity.{}".format(self._identifier.replace(u":", u"."))

    def toString(self):
        return self._identifier

    def equals(self, other):
        return isinstance(other, _EntityType) \
            and other._identifier == self._identifier

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return hash(self._identifier)

    def __str__(self):
        return self._identifier

    def __repr__(self):
        return u"<EntityType {}>".format(self._identifier)


class _EntityTypeHolder(object):
    """
    对应 net.minecraft.world.entity.EntityType。

    懒加载 + 同名同对象，这样才能用 `==` 做身份比较
    （真实代码会写 `entity.getType() == EntityType.PIG`）。
    """

    def __init__(self):
        self._cache = {}

    def of(self, name):
        key = java_to_string(name)
        if key not in self._cache:
            self._cache[key] = _EntityType(key)
        return self._cache[key]

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        return self.of(u"minecraft:{}".format(name.lower()))

    def clear(self):
        self._cache = {}
        return None

    def __repr__(self):
        return u"<EntityType {} 种已建>".format(len(self._cache))


class _EntityTypeBuilder(object):
    def __init__(self, factory, category):
        if not callable(factory):
            raise IllegalArgumentException("Entity factory must be callable")
        self._factory = factory
        self._category = category
        self._width = 0.6
        self._height = 1.8
        self._eye_height = 1.53
        # Minecraft 1.21.1 EntityType.Builder constructor defaults.
        self._serialize = True
        self._client_tracking_range = 5
        self._update_interval = 3

    @staticmethod
    def of(factory, category):
        return _EntityTypeBuilder(factory, category)

    def sized(self, width, height):
        width, height = float(width), float(height)
        if width <= 0 or height <= 0 or not (width < float("inf") and height < float("inf")):
            raise IllegalArgumentException("Entity dimensions must be finite and positive")
        self._width, self._height = width, height
        self._eye_height = height * 0.85
        return self

    def eyeHeight(self, height):
        height = float(height)
        if not 0 <= height <= self._height:
            raise IllegalArgumentException("Eye height outside entity bounds")
        self._eye_height = height
        return self

    def noSave(self):
        self._serialize = False
        return self

    def clientTrackingRange(self, blocks):
        blocks = int(blocks)
        if blocks < 0:
            raise IllegalArgumentException('Client tracking range must not be negative')
        self._client_tracking_range = blocks
        return self

    def updateInterval(self, ticks):
        ticks = int(ticks)
        if ticks < 1:
            raise IllegalArgumentException('Update interval must be positive')
        self._update_interval = ticks
        return self

    def build(self, identifier):
        result = EntityType.of(identifier)
        if result._factory is not None:
            raise IllegalArgumentException("Duplicate entity type: " + java_to_string(identifier))
        result._factory = self._factory
        result._category = self._category
        result._width, result._height = self._width, self._height
        result._eye_height = self._eye_height
        result._serialize = self._serialize
        result._client_tracking_range = self._client_tracking_range
        result._update_interval = self._update_interval
        from neoforge.mod_entrypoints import _active_contexts
        if _active_contexts:
            original_factory = self._factory
            key = java_to_string(identifier)
            def release():
                if result._factory is original_factory:
                    result._factory = None
                    result._attributes = None
                    if EntityType._cache.get(key) is result:
                        del EntityType._cache[key]
            _active_contexts[-1].on_close(release)
        return result


EntityType = _EntityTypeHolder()
EntityType.Builder = _EntityTypeBuilder


class _EntityFactory(object):
    """The EntityType.EntityFactory SAM, distinct from java.util.BiFunction."""
    def __init__(self, callback):
        if not callable(callback):
            raise IllegalArgumentException('Entity factory callback must be callable')
        self._callback = callback
    def create(self, entity_type, level):
        return self._callback(entity_type, level)
    def __call__(self, entity_type, level):
        return self.create(entity_type, level)


EntityType.EntityFactory = _EntityFactory


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.entity.Mob": Mob,
    "net.minecraft.world.entity.PathfinderMob": PathfinderMob,
    "net.minecraft.world.entity.monster.Monster": Monster,
    "net.minecraft.world.entity.MobCategory": MobCategory,
    "net.minecraft.world.entity.EntityType$Builder": _EntityTypeBuilder,
    "net.minecraft.world.entity.EntityType$EntityFactory": _EntityFactory,
    "net.minecraft.world.entity.Entity": Entity,
    "net.minecraft.world.entity.LivingEntity": LivingEntity,
    "net.minecraft.world.entity.player.Player": Player,
    "net.minecraft.server.level.ServerPlayer": ServerPlayer,
    "net.minecraft.world.entity.player.Inventory": Inventory,
    "net.minecraft.world.entity.player.Abilities": Abilities,
    "net.minecraft.world.entity.EntityType": EntityType,
}


__all__ = [
    "Entity", "LivingEntity", "Player", "ServerPlayer",
    "Inventory", "Abilities", "EntityType", "Mob", "PathfinderMob", "Monster", "MobCategory",
    "JAVA_MAP",
]

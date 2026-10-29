# -*- coding: utf-8 -*-
# minecraft/util.py
# θ 层：通用工具（数学、随机、射线命中、交互结果包装、本地化）
#
# 真实用法（逐字来自反编译源码）：
#
#   // Mth：纯数学，用得最多
#   int l = Mth.clamp((18 * k + 20 - 1) / 20, 0, 18);
#   int totalXp = Mth.floor(craftedCount * xpPerItem);
#   float fractional = Mth.frac(craftedCount * xpPerItem);
#
#   // RandomSource：可复现的随机源
#   RandomSource randomsource = RandomSource.create(seed);
#
#   // 射线命中
#   HitResult hitResult = entity.pick(d0, mc.getTimer().getGameTimeDeltaPartialTick(true));
#   if (hitResult.getType() != HitResult.Type.MISS) { ... }
#   if (hitResult instanceof BlockHitResult) { BlockHitResult b = (BlockHitResult) hitResult; }
#   EntityHitResult entityhitresult = ProjectileUtil.getEntityHitResult(entity, vec3, vec32, ...);
#
#   // 交互结果包装（物品使用时返回它而不是 InteractionResult）
#   return InteractionResultHolder.pass(itemstack);
#   return InteractionResultHolder.success(itemstack);
#
#   // 本地化
#   Component.literal(I18n.get("block.brewing." + ManaitaPlusLegacyConfig.x));
#   I18n.get("mode.doubling.name", new Object[]{...});
#
# `Mth` 是纯函数，可以直接照抄语义；`InteractionResultHolder` 只是
# 「结果 + 物品栈」的打包，真实代码用它的 success / pass / fail 三个工厂。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

import math as _math

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
    from java_stdlib.util import JavaRandom
    from minecraft.core import BlockPos, Direction, Vec3
    from minecraft.item import ItemStack
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from util import JavaRandom  # type: ignore
    from core import BlockPos, Direction, Vec3  # type: ignore
    from item import ItemStack  # type: ignore


# ============================================================
# Mth
# ============================================================

class Mth(object):
    """
    对应 net.minecraft.util.Mth。

    纯数学工具，语义可以直接照抄 —— 但有两个**容易写错**的地方：

    1. **`floor` 与 Python 的 `//` 不同**。`Mth.floor(-0.5)` 是 -1，
       而 Python 的 `int(-0.5)` 是 0。所以必须用 `math.floor`，
       不能图省事写 int()。
    2. **`clamp` 的参数顺序是 (值, 下限, 上限)**，不是 (下限, 值, 上限)。
       真实代码写 `Mth.clamp(x, 0, 18)`。

    `frac` 与 `floor` 配合使用（真实代码用它拆「整数部分 + 小数部分」）：
        int total = Mth.floor(v);
        float fraction = Mth.frac(v);
    """

    # Java 里这些是常量字段
    PI = _math.pi
    E = _math.e
    DEG_TO_RAD = _math.pi / 180.0
    RAD_TO_DEG = 180.0 / _math.pi

    # ---------------- 取整 ----------------

    @staticmethod
    def floor(value):
        """对应 floor(double)：**向下**取整（负数往更小取，与 int() 不同）。"""
        return int(_math.floor(float(value)))

    @staticmethod
    def ceil(value):
        """对应 ceil(double)。"""
        return int(_math.ceil(float(value)))

    @staticmethod
    def abs(value):
        return abs(value)

    # ---------------- 夹取与拆分 ----------------

    @staticmethod
    def clamp(value, min_value, max_value):
        """
        对应 clamp(T value, T min, T max)：把值夹到 [min, max]。

        **注意参数顺序**：值是第一个。
        上限小于下限时返回下限（Java 的行为）。
        """
        if max_value < min_value:
            return min_value
        if value < min_value:
            return min_value
        if value > max_value:
            return max_value
        return value

    @staticmethod
    def clampInt(value, min_value, max_value):
        """整数版（Java 用重载区分，Python 用独立名字）。"""
        return Mth.clamp(int(value), int(min_value), int(max_value))

    @staticmethod
    def frac(value):
        """
        对应 frac(double)：取小数部分。

        Java 的实现是 `d - floor(d)`，所以**负数的小数部分也是正的**：
        frac(-1.25) == 0.75。用 `value % 1.0` 在 Python 里结果相同，
        但写清楚更贴近原实现。
        """
        value = float(value)
        return value - _math.floor(value)

    # ---------------- 三角函数（按角度，不是弧度） ----------------

    @staticmethod
    def sin(degrees):
        """对应 sin(float)：**参数是角度**，不是弧度。"""
        return _math.sin(float(degrees) * Mth.DEG_TO_RAD)

    @staticmethod
    def cos(degrees):
        return _math.cos(float(degrees) * Mth.DEG_TO_RAD)

    @staticmethod
    def atan2(y, x):
        """对应 atan2(double, double)：返回**角度**。"""
        return _math.atan2(float(y), float(x)) * Mth.RAD_TO_DEG

    @staticmethod
    def sqrt(value):
        return _math.sqrt(float(value))

    # ---------------- 其它 ----------------

    @staticmethod
    def square(value):
        return value * value

    @staticmethod
    def lerp(delta, start, end):
        """对应 lerp(double, double, double)：**delta 是第一个参数**。"""
        return start + delta * (end - start)

    @staticmethod
    def lerpInt(delta, start, end):
        return int(start + delta * (end - start))

    @staticmethod
    def positiveModulo(value, modulus):
        """对应 positiveModulo(int, int)：结果**一定非负**（Java 的 % 会出负数）。"""
        modulus = int(modulus)
        result = int(value) % modulus
        return result + modulus if result < 0 else result

    @staticmethod
    def nextInt(random_source, min_value, max_value=None):
        """
        对应 nextInt(RandomSource, int) / (RandomSource, int, int)。

        Python 没有重载，第二个上界可选：
          只给一个数时是 [0, bound)
          给两个数时是 [min, max)
        """
        if random_source is None:
            raise IllegalArgumentException(u"nextInt 需要随机源")
        if max_value is None:
            return random_source.nextInt(int(min_value))
        low = int(min_value)
        high = int(max_value)
        if low >= high:
            return low
        return low + random_source.nextInt(high - low)


# ============================================================
# RandomSource
# ============================================================

class RandomSource(object):
    """
    对应 net.minecraft.util.RandomSource。

    真实用法：`RandomSource randomsource = RandomSource.create(seed);`

    **同种子必须同序列** —— 真实代码靠它做可复现的随机
    （结构与装饰的生成）。所以这里直接复用 Σ 层的 `JavaRandom`
    （Java 的 LCG 算法），而不是 Python 的 random。
    """

    def __init__(self, seed=None):
        self._random = JavaRandom() if seed is None else JavaRandom(seed)
        self.seed = seed

    @staticmethod
    def create(seed):
        """对应 RandomSource.create(long)。"""
        return RandomSource(seed)

    def nextInt(self, bound=None):
        """对应 nextInt(int)：[0, bound)。不给上界时返回任意整数。"""
        if bound is None:
            return self._random.nextInt()
        return self._random.nextInt(int(bound))

    def nextDouble(self):
        return self._random.nextDouble()

    def nextFloat(self):
        """对应 nextFloat()：JavaRandom 本身有 nextFloat，直接用。"""
        return self._random.nextFloat()

    def nextBoolean(self):
        return bool(self._random.nextBoolean())

    def nextLong(self):
        return self._random.nextLong()

    def setSeed(self, seed):
        """
        对应 setSeed(long)：重置序列。

        用底层随机源的 setSeed 而不是重建对象 —— 重建会让
        外面拿着的引用失效（真实代码会把同一个 RandomSource 传下去）。
        """
        self._random.setSeed(seed)
        self.seed = seed
        return self

    def fork(self):
        """对应 fork()：派生一个独立随机源。"""
        return RandomSource(self.nextLong())

    def __repr__(self):
        return u"<RandomSource seed={}>".format(self.seed)


# ============================================================
# 射线命中
# ============================================================

class HitResult(object):
    """
    对应 net.minecraft.world.phys.HitResult。

    `getType()` 返回 MISS / BLOCK / ENTITY 之一。
    真实代码先判 `!= MISS`，再按具体子类分支。
    """

    class Type(object):
        """对应 HitResult.Type 枚举。"""

        def __init__(self, name):
            self._name = java_to_string(name)

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
            return u"<Type.{}>".format(self._name)

    MISS = None
    BLOCK = None
    ENTITY = None

    def __init__(self, location=None):
        self._location = location if location is not None else Vec3(0.0, 0.0,
                                                                    0.0)

    def getType(self):
        """对应 getType()：命中类型。"""
        return HitResult.MISS

    def getLocation(self):
        """对应 getLocation()：命中点坐标。"""
        return self._location

    def distanceTo(self, other):
        return self._location.distanceTo(other)

    def __repr__(self):
        return u"<{} at {}>".format(type(self).__name__,
                                    self._location.toString())


HitResult.MISS = HitResult.Type(u"MISS")
HitResult.BLOCK = HitResult.Type(u"BLOCK")
HitResult.ENTITY = HitResult.Type(u"ENTITY")


class BlockHitResult(HitResult):
    """
    对应 net.minecraft.world.phys.BlockHitResult。

    真实代码：`if (hitResult instanceof BlockHitResult) { ... }`
    然后读 `getBlockPos()` 与 `getDirection()`。
    """

    def __init__(self, location=None, direction=None, pos=None):
        HitResult.__init__(self, location)
        self._direction = direction if direction is not None else Direction.UP
        self._block_pos = pos

    def getType(self):
        return HitResult.BLOCK

    def getBlockPos(self):
        """对应 getBlockPos()：命中的方块坐标。"""
        if self._block_pos is not None:
            return self._block_pos
        return BlockPos.containing(self.getLocation())

    def getDirection(self):
        """对应 getDirection()：命中的面。"""
        return self._direction

    def withDirection(self, direction):
        return BlockHitResult(self.getLocation(), direction,
                              self._block_pos)


class EntityHitResult(HitResult):
    """
    对应 net.minecraft.world.phys.EntityHitResult。

    真实代码：`Entity entity1 = entityhitresult.getEntity();`
    """

    def __init__(self, entity=None, location=None):
        HitResult.__init__(self, location)
        self._entity = entity

    def getType(self):
        return HitResult.ENTITY

    def getEntity(self):
        """对应 getEntity()：命中的实体。"""
        return self._entity


# ============================================================
# InteractionResultHolder
# ============================================================

class InteractionResultHolder(object):
    """
    对应 net.minecraft.world.InteractionResultHolder。

    「交互结果 + 相关物品栈」的打包。真实代码在物品的 use 方法里返回它：

        return InteractionResultHolder.pass(itemstack);
        return InteractionResultHolder.success(itemstack);

    **与 InteractionResult 的区别**：后者只说「结果是什么」，
    前者还带上「哪个物品栈参与了这个交互」（可能被改变过）。
    """

    def __init__(self, result, item_stack=None):
        self._result = result
        self._item = item_stack if item_stack is not None else ItemStack()

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def success(item_stack=None):
        """对应 success(ItemStack)：交互成功。"""
        from minecraft.core import InteractionResult
        return InteractionResultHolder(InteractionResult.SUCCESS, item_stack)

    @staticmethod
    def consume(item_stack=None):
        """对应 consume(ItemStack)：消耗掉了（服务端语义）。"""
        from minecraft.core import InteractionResult
        return InteractionResultHolder(InteractionResult.CONSUME, item_stack)

    @staticmethod
    def passResult(item_stack=None):
        """
        对应 pass(ItemStack)。

        **方法名不是 pass** —— `pass` 是 Python 关键字，
        `InteractionResultHolder.pass(x)` 在 Python 里是语法错误。
        改名约定见 core/keyword_renames.py。
        """
        from minecraft.core import InteractionResult
        return InteractionResultHolder(InteractionResult.PASS, item_stack)

    @staticmethod
    def fail(item_stack=None):
        """对应 fail(ItemStack)：交互失败。"""
        from minecraft.core import InteractionResult
        return InteractionResultHolder(InteractionResult.FAIL, item_stack)

    # ---------------- 取值 ----------------

    def getResult(self):
        """对应 getResult()。"""
        return self._result

    def getObject(self):
        """对应 getObject()：参与交互的物品栈。"""
        return self._item

    def __repr__(self):
        return u"<InteractionResultHolder {} {}>".format(self._result,
                                                         self._item)


# ============================================================
# I18n
# ============================================================

class I18n(object):
    """
    对应 net.minecraft.client.resources.language.I18n。

    真实用法：
        Component.literal(I18n.get("block.brewing." + name));
        I18n.get("mode.doubling.name", new Object[]{arg});

    **与 Component 的分工**：`I18n.get` 直接返回**翻译后的字符串**，
    而 `Component.translatable` 返回一个延迟解析的组件。
    真实代码两者都用。

    本实现复用 `Component` 里的翻译表 —— 同一份数据，
    避免两处翻译表不一致（那会导致同一个键在两处显示不同）。
    """

    @staticmethod
    def get(key, *args):
        """
        对应 get(String, Object...)：取翻译文本。

        找不到键时**回退为键本身**（与 Component 的策略一致）——
        界面上至少能看出是哪个键，便于排查。
        """
        from minecraft.core import Component
        component = Component.translatable(key, *args)
        return component.getString()

    @staticmethod
    def exists(key):
        """对应 exists(String)：这个键有没有译文。"""
        from minecraft.core import Component
        return java_to_string(key) in Component._translations

    @staticmethod
    def getIfExists(key):
        """对应 getIfExists：没有译文时返回 None。"""
        if I18n.exists(key):
            return I18n.get(key)
        return None

    @staticmethod
    def loadFromLangFile(data):
        """把语言文件喂给 Component 的翻译表（两者共用一份）。"""
        from minecraft.core import Component
        return Component.loadFromLangFile(data)


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.util.Mth": Mth,
    "net.minecraft.util.RandomSource": RandomSource,
    "net.minecraft.world.phys.HitResult": HitResult,
    "net.minecraft.world.phys.HitResult$Type": HitResult.Type,
    "net.minecraft.world.phys.BlockHitResult": BlockHitResult,
    "net.minecraft.world.phys.EntityHitResult": EntityHitResult,
    "net.minecraft.world.InteractionResultHolder": InteractionResultHolder,
    "net.minecraft.client.resources.language.I18n": I18n,
}


__all__ = [
    "Mth", "RandomSource",
    "HitResult", "BlockHitResult", "EntityHitResult",
    "InteractionResultHolder", "I18n",
    "JAVA_MAP",
]

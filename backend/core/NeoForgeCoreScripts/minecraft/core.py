# -*- coding: utf-8 -*-
# minecraft/core.py
# θ 层：基础类型（位置、向量、方向、文本、交互结果）
#
# 这一层放「不依赖游戏世界、纯计算」的类型 —— 它们可以完全脱离引擎自测。
# 需要真实世界的类（ItemStack / Level / Entity …）放在同层的其它模块里。
#
# 真实用法（从反编译源码逐字提取，按引用次数排序）：
#
#   Component.literal("...")                     40 次
#   Component.translatable("itemGroup.ManaitaPlusTab")   11 次
#   Block.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0)   12 次
#   InteractionResult.sidedSuccess(level.isClientSide)    9 次
#   BlockPos.MutableBlockPos()                    6 次
#   BlockPos.containing(vec3.x, vec3.y - 1e-6, vec3.z)   1 次
#   BlockPos.randomInCube(level.random, 10, pos, 1)      1 次
#   Vec3.atCenterOf(pos)                          1 次
#
# 注意一个反编译假象：在 Screen 子类里，`super.init(...)` 会被 CFR 反编译成
# `Component.init(...)` —— 因为父类里有个叫 Component 的字段。
# 所以扫出来的 `Component.init/render/updateScreenPosition` 并不是真实 API，
# 不要照着实现。真正要实现的静态入口只有 literal / translatable / empty。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

import math as _math

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore


# ============================================================
# Component：聊天/界面文本
# ============================================================

class Component(object):
    """
    对应 net.minecraft.network.chat.Component。

    它是 Minecraft 的「可翻译文本」抽象：真正的显示内容由客户端按语言文件解析，
    而 Component 本身只记录「用哪个翻译键、带哪些参数」。

    真实代码里两种都用到：
        Component.literal("ManaitaPlus")                  直接字面量
        Component.translatable("itemGroup.ManaitaPlusTab") 翻译键

    基岩版没有 NeoForge 的翻译管线，所以这里：
      - 完整保留「字面量 / 翻译键 + 参数」的结构（保证翻译层语义不丢）；
      - getString() 在能解析翻译表时返回译文，否则**回退到键本身** ——
        回退到键而不是空串，至少界面上还能看出是哪个键，便于排查。
    """

    # 全局翻译表：由核心包在启动时用语言文件填充
    _translations = {}

    def __init__(self, kind, text, args=None, style=None):
        self.kind = kind                # "literal" / "translatable" / "empty"
        self.text = java_to_string(text)
        self.args = list(args) if args else []
        self.style = style

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def literal(text):
        return Component(u"literal", text)

    @staticmethod
    def translatable(key, *args):
        return Component(u"translatable", key, args)

    @staticmethod
    def empty():
        return Component(u"empty", u"")

    @staticmethod
    def nullToEmpty(value):
        """对应 Java 的 nullToEmpty：null 转成空组件。"""
        if value is None:
            return Component.empty()
        return value

    # ---------------- 内容 ----------------

    def getString(self):
        """取可显示文本。翻译键找不到时回退为键本身。"""
        if self.kind == u"empty":
            return u""
        if self.kind == u"literal":
            return self.text
        # translatable：先查翻译表，查不到就回退成键
        template = Component._translations.get(self.text)
        if template is None:
            return self.text
        return self._fill(template)

    def _fill(self, template):
        """
        用参数填充译文模板。

        支持两种最常见的占位形式：
          %s  / %1$s    —— Java 的 Formatter 风格
        逐项替换，参数不足时保留原样（宁可显示得难看一点，也不要抛异常）。
        """
        result = template
        for index in range(len(self.args)):
            value = java_to_string(self.args[index])
            # 先试 %N$s 形式（指定第几个参数）
            positioned = u"%{}$s".format(index + 1)
            if positioned in result:
                result = result.replace(positioned, value)
                continue
            # 再试普通的 %s
            if u"%s" in result:
                result = result.replace(u"%s", value, 1)
        return result

    # ---------------- 翻译表 ----------------

    @staticmethod
    def setTranslations(mapping):
        """装载翻译表 {键: 模板}（由核心包读取语言文件后调用）。"""
        if mapping:
            Component._translations.update(mapping)
        return None

    @staticmethod
    def loadFromLangFile(data):
        """
        从语言文件的数据载入翻译。

        只认识形状为 {"键": "值"} 的扁平字典 ——
        与 assets/<namespace>/lang/zh_cn.json 的结构一致。

        字符串判断用 `isinstance(value, type(u""))`：
        Py2 里 u"" 是 unicode、Py3 里是 str，两边都成立，
        不需要判断解释器版本（也就避免了引用 unicode 这个名字）。
        """
        if not isinstance(data, dict):
            raise IllegalArgumentException(
                u"语言文件应是 键->值 的字典，收到 {}".format(type(data).__name__))

        text_type = type(u"")
        loaded = 0
        for key in data:
            value = data[key]
            if isinstance(value, text_type):
                Component._translations[java_to_string(key)] = \
                    java_to_string(value)
                loaded += 1
        return loaded

    @staticmethod
    def clearTranslations():
        Component._translations = {}
        return None

    # ---------------- 展示 ----------------

    def toString(self):
        return java_to_string(self.getString())

    def equals(self, other):
        if not isinstance(other, Component):
            return False
        return (self.kind == other.kind and self.text == other.text
                and self.args == other.args)

    def hashCode(self):
        return hash_code(u"{}|{}".format(self.kind, self.text))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Component {} {!r}>".format(self.kind, self.text)


# ============================================================
# InteractionResult：交互结果
# ============================================================

class InteractionResult(object):
    """
    对应 net.minecraft.world.InteractionResult。

    真实用法：
        InteractionResult.sidedSuccess(level.isClientSide)   9 次
        InteractionResult.PASS

    枚举成员：SUCCESS / CONSUME / PASS / FAIL。
    sidedSuccess 的语义是「客户端返回 SUCCESS、服务端返回 CONSUME」，
    这样两端各做各的事而不会双重处理 —— 这是 Minecraft 的经典约定，
    照抄即可，不要简化成一个布尔。
    """

    class _Result(object):
        def __init__(self, name):
            self._name = name

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
            return u"<InteractionResult.{}>".format(self._name)

    SUCCESS = None
    CONSUME = None
    PASS = None
    FAIL = None

    @staticmethod
    def sidedSuccess(is_client_side):
        """
        对应 sidedSuccess：客户端 SUCCESS、服务端 CONSUME。

        参数是「当前是否客户端」。写成函数而不是两个常量，
        是因为真实代码就是按侧动态取的。
        """
        if is_client_side:
            return InteractionResult.SUCCESS
        return InteractionResult.CONSUME

    @staticmethod
    def sidedSuccessBoolean(is_client_side):
        """兼容别名：语义与 sidedSuccess 相同。"""
        return InteractionResult.sidedSuccess(is_client_side)

    @staticmethod
    def valueOf(name):
        text = java_to_string(name).upper()
        for member in (InteractionResult.SUCCESS, InteractionResult.CONSUME,
                       InteractionResult.PASS, InteractionResult.FAIL):
            if member.name() == text:
                return member
        raise IllegalArgumentException(
            u"No enum constant InteractionResult.{}".format(name))

    @staticmethod
    def values():
        return [InteractionResult.SUCCESS, InteractionResult.CONSUME,
                InteractionResult.PASS, InteractionResult.FAIL]


InteractionResult.SUCCESS = InteractionResult._Result(u"SUCCESS")
InteractionResult.CONSUME = InteractionResult._Result(u"CONSUME")
InteractionResult.PASS = InteractionResult._Result(u"PASS")
InteractionResult.FAIL = InteractionResult._Result(u"FAIL")


class InteractionHand(object):
    """对应 net.minecraft.world.InteractionHand：MAIN_HAND / OFF_HAND。"""

    class _Hand(object):
        def __init__(self, name):
            self._name = name

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
            return u"<InteractionHand.{}>".format(self._name)

    MAIN_HAND = None
    OFF_HAND = None


InteractionHand.MAIN_HAND = InteractionHand._Hand(u"MAIN_HAND")
InteractionHand.OFF_HAND = InteractionHand._Hand(u"OFF_HAND")


# ============================================================
# Direction
# ============================================================

class Direction(object):
    """
    对应 net.minecraft.core.Direction。

    枚举成员与 Minecraft 一致；每个方向带一个三维法向量，
    因为模组代码常用 getNormal() 做坐标偏移。
    """

    class _Dir(object):
        def __init__(self, name, step_x, step_y, step_z, opposite_name):
            self._name = name
            self._step = (step_x, step_y, step_z)
            self._opposite_name = opposite_name

        def name(self):
            return self._name

        def getStepX(self):
            return self._step[0]

        def getStepY(self):
            return self._step[1]

        def getStepZ(self):
            return self._step[2]

        def getNormal(self):
            return (self._step[0], self._step[1], self._step[2])

        def getOpposite(self):
            return Direction.valueOfJavaName(self._opposite_name)

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
            return u"<Direction.{}>".format(self._name)

    DOWN = None
    UP = None
    NORTH = None
    SOUTH = None
    WEST = None
    EAST = None

    @staticmethod
    def valueOfJavaName(name):
        table = {
            u"DOWN": Direction.DOWN, u"UP": Direction.UP,
            u"NORTH": Direction.NORTH, u"SOUTH": Direction.SOUTH,
            u"WEST": Direction.WEST, u"EAST": Direction.EAST,
        }
        result = table.get(java_to_string(name).upper())
        if result is None:
            raise IllegalArgumentException(
                u"No enum constant Direction.{}".format(name))
        return result

    @staticmethod
    def values():
        return [Direction.DOWN, Direction.UP, Direction.NORTH,
                Direction.SOUTH, Direction.WEST, Direction.EAST]


Direction.DOWN = Direction._Dir(u"DOWN", 0, -1, 0, u"UP")
Direction.UP = Direction._Dir(u"UP", 0, 1, 0, u"DOWN")
Direction.NORTH = Direction._Dir(u"NORTH", 0, 0, -1, u"SOUTH")
Direction.SOUTH = Direction._Dir(u"SOUTH", 0, 0, 1, u"NORTH")
Direction.WEST = Direction._Dir(u"WEST", -1, 0, 0, u"EAST")
Direction.EAST = Direction._Dir(u"EAST", 1, 0, 0, u"WEST")


# ============================================================
# BlockPos / Vec3i / MutableBlockPos
# ============================================================

class Vec3i(object):
    """
    对应 net.minecraft.core.Vec3i：整数三元组。

    Java 里它不可变；子类 MutableBlockPos 可变。
    """

    def __init__(self, x=0, y=0, z=0):
        self._x = int(x)
        self._y = int(y)
        self._z = int(z)

    def getX(self):
        return self._x

    def getY(self):
        return self._y

    def getZ(self):
        return self._z

    # ---------------- 运算 ----------------

    def offset(self, dx, dy=None, dz=None):
        """
        Java 里 offset 有多个重载：
          offset(int, int, int) / offset(Vec3i) / offset(Direction)
        Python 没有重载，这里按参数形态分派。
        """
        if dy is None and dz is None:
            other = dx
            if isinstance(other, Vec3i):
                return Vec3i(self._x + other.getX(), self._y + other.getY(),
                             self._z + other.getZ())
            if isinstance(other, Direction._Dir):
                return Vec3i(self._x + other.getStepX(),
                             self._y + other.getStepY(),
                             self._z + other.getStepZ())
            raise IllegalArgumentException(
                u"offset 参数不认识: {!r}".format(other))
        return Vec3i(self._x + int(dx), self._y + int(dy), self._z + int(dz))

    def above(self, distance=1):
        return self.offset(0, int(distance), 0)

    def below(self, distance=1):
        return self.offset(0, -int(distance), 0)

    def north(self, distance=1):
        return self.offset(0, 0, -int(distance))

    def south(self, distance=1):
        return self.offset(0, 0, int(distance))

    def west(self, distance=1):
        return self.offset(-int(distance), 0, 0)

    def east(self, distance=1):
        return self.offset(int(distance), 0, 0)

    def relative(self, direction, distance=1):
        """对应 relative(Direction, int)。"""
        step = int(distance)
        return Vec3i(self._x + direction.getStepX() * step,
                     self._y + direction.getStepY() * step,
                     self._z + direction.getStepZ() * step)

    def distSqr(self):
        return self._x * self._x + self._y * self._y + self._z * self._z

    # ---------------- 展示与比较 ----------------

    def equals(self, other):
        if not isinstance(other, Vec3i):
            return False
        return (self._x == other.getX() and self._y == other.getY()
                and self._z == other.getZ())

    def hashCode(self):
        return (self._y + self._z * 31) * 31 + self._x

    def toString(self):
        return u"({}, {}, {})".format(self._x, self._y, self._z)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __iter__(self):
        """让 `x, y, z = pos` 这种写法也能用。"""
        return iter((self._x, self._y, self._z))

    def __getitem__(self, index):
        return (self._x, self._y, self._z)[index]

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{} {}>".format(type(self).__name__, self.toString())


class BlockPos(Vec3i):
    """
    对应 net.minecraft.core.BlockPos。

    真实用法：
        BlockPos.MutableBlockPos()                          6 次
        BlockPos.containing(vec3.x, vec3.y - 1e-6, vec3.z)  1 次
        BlockPos.randomInCube(level.random, 10, pos, 1)     1 次
    """

    ZERO = None

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def containing(x, y=None, z=None):
        """
        对应 BlockPos.containing(double, double, double)：
        向**下**取整（floor），不是四舍五入也不是截断。

        这条语义很关键：坐标 -0.5 应当落在 -1，而不是 0。
        """
        if y is None and z is None:
            vector = x
            if isinstance(vector, Vec3):
                return BlockPos(int(_math.floor(vector.x)),
                                int(_math.floor(vector.y)),
                                int(_math.floor(vector.z)))
            if isinstance(vector, Vec3i):
                return BlockPos(vector.getX(), vector.getY(), vector.getZ())
            raise IllegalArgumentException(
                u"containing 参数不认识: {!r}".format(vector))
        return BlockPos(int(_math.floor(float(x))), int(_math.floor(float(y))),
                        int(_math.floor(float(z))))

    @staticmethod
    def randomInCube(random_source, radius, center, tries=1):
        """
        对应 BlockPos.randomInCube(RandomSource, int, BlockPos, int)。

        语义：在 center 周围边长为 radius 的立方体内随机取一个位置，
        找不到（这里没有世界可判空，故总能找到）就返回 None。
        为保证可复现，随机数一律走传入的 random_source。
        """
        if random_source is None:
            raise IllegalArgumentException(u"randomInCube 需要随机源")
        radius = int(radius)
        if radius <= 0:
            return None
        base_x = center.getX() if isinstance(center, Vec3i) else 0
        base_y = center.getY() if isinstance(center, Vec3i) else 0
        base_z = center.getZ() if isinstance(center, Vec3i) else 0

        for _try_index in range(int(tries)):
            dx = random_source.nextInt(radius * 2 + 1) - radius
            dy = random_source.nextInt(radius * 2 + 1) - radius
            dz = random_source.nextInt(radius * 2 + 1) - radius
            return BlockPos(base_x + dx, base_y + dy, base_z + dz)
        return None

    @staticmethod
    def mutable():
        """对应 new BlockPos.MutableBlockPos()。"""
        return MutableBlockPos(0, 0, 0)

    # ---------------- 偏移必须返回 BlockPos 而不是 Vec3i ----------------
    #
    # 为什么全部重写一遍：这些方法在 Vec3i 里已经实现了，但返回的是 Vec3i。
    # 真实代码到处写 `blockpos.relative(...)` 然后把它当 BlockPos 用
    # （传进只收 BlockPos 的方法、调 getX 之外的 API）。
    # 不重写的话类型会**静默退化**成 Vec3i —— 实测踩到：
    # `BlockPlaceContext.getClickedPos()` 内部调 relative() 之后，
    # 传进 Level.getBlockState() 直接被 `_as_pos` 拒绝
    # （"位置参数应是 BlockPos 或三元组，收到 Vec3i"）。
    # Minecraft 里 BlockPos.relative() 返回的就是 BlockPos，照抄。

    def offset(self, dx, dy=None, dz=None):
        """对应 offset(...)：返回 BlockPos（覆盖 Vec3i 的实现）。"""
        result = Vec3i.offset(self, dx, dy, dz)
        return BlockPos(result.getX(), result.getY(), result.getZ())

    def above(self, distance=1):
        return self.offset(0, int(distance), 0)

    def below(self, distance=1):
        return self.offset(0, -int(distance), 0)

    def north(self, distance=1):
        return self.offset(0, 0, -int(distance))

    def south(self, distance=1):
        return self.offset(0, 0, int(distance))

    def west(self, distance=1):
        return self.offset(-int(distance), 0, 0)

    def east(self, distance=1):
        return self.offset(int(distance), 0, 0)

    def relative(self, direction, distance=1):
        """对应 relative(Direction, int)：返回 BlockPos（覆盖 Vec3i）。"""
        result = Vec3i.relative(self, direction, distance)
        return BlockPos(result.getX(), result.getY(), result.getZ())

    # ---------------- 与 Vec3 互转 ----------------

    def getCenter(self):
        """对应 getCenter()：返回方块中心的精确坐标。"""
        return Vec3(self.getX() + 0.5, self.getY() + 0.5, self.getZ() + 0.5)

    def asLong(self):
        """
        对应 asLong()：把 (x, y, z) 打包成一个长整数。

        真实代码用它做区块内坐标的哈希键。这里用与 Minecraft 相同的
        位布局（y 占中间 12 位），保证打包结果可跨实现比对。
        """
        value=((self.getX() & 0x3FFFFFF) << 38) | ((self.getZ() & 0x3FFFFFF) << 12) | (self.getY() & 0xFFF)
        return value-(1<<64) if value&(1<<63) else value

    def __repr__(self):
        return u"<BlockPos {}>".format(self.toString())


BlockPos.ZERO = BlockPos(0, 0, 0)


class MutableBlockPos(BlockPos):
    """
    对应 BlockPos.MutableBlockPos：可以原地改坐标。

    为什么单独一个类：
      真实代码在循环里反复用它以避免创建大量对象
      （BlockPos 是不可变的，每次偏移都要新建）。
      语义上它就是「带 set 的 BlockPos」，所以继承并加上 setter。
    """

    def set(self, x, y=None, z=None):
        """对应 set(int,int,int) / set(Vec3i)。返回自身以便链式。"""
        if y is None and z is None:
            other = x
            self._x = other.getX()
            self._y = other.getY()
            self._z = other.getZ()
            return self
        self._x = int(x)
        self._y = int(y)
        self._z = int(z)
        return self

    def setX(self, x):
        self._x = int(x)
        return self

    def setY(self, y):
        self._y = int(y)
        return self

    def setZ(self, z):
        self._z = int(z)
        return self

    def move(self, direction, distance=1):
        """
        对应 move(Direction, int)：原地偏移。

        **特意不用 Vec3i.relative** —— 那是给不可变的 Vec3i 用的，
        它返回新对象；这里要原地改。MutableBlockPos 的 relative()
        继承自 BlockPos，会返回新的 BlockPos（与 Minecraft 一致）。
        """
        step = int(distance)
        self._x += direction.getStepX() * step
        self._y += direction.getStepY() * step
        self._z += direction.getStepZ() * step
        return self

    def __repr__(self):
        return u"<MutableBlockPos {}>".format(self.toString())


# ============================================================
# Vec3：浮点三元组
# ============================================================

class Vec3(object):
    """
    对应 net.minecraft.world.phys.Vec3。

    真实用法：Vec3.atCenterOf(pos)；以及大量 vec3.x / vec3.y / vec3.z 读取。
    所以 x / y / z 做成可直接访问的公开属性（不是下划线私有）。
    """

    ZERO = None

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @staticmethod
    def atCenterOf(vector):
        """对应 atCenterOf(Vec3i)：方块中心（+0.5）。"""
        return Vec3(vector.getX() + 0.5, vector.getY() + 0.5,
                    vector.getZ() + 0.5)

    @staticmethod
    def atLowerCornerOf(vector):
        """对应 atLowerCornerOf(Vec3i)：方块角（不加 0.5）。"""
        return Vec3(vector.getX(), vector.getY(), vector.getZ())

    # ---------------- 运算 ----------------

    def add(self, x, y=None, z=None):
        if y is None and z is None:
            other = x
            return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
        return Vec3(self.x + float(x), self.y + float(y), self.z + float(z))

    def subtract(self, x, y=None, z=None):
        if y is None and z is None:
            other = x
            return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
        return Vec3(self.x - float(x), self.y - float(y), self.z - float(z))

    def scale(self, factor):
        factor = float(factor)
        return Vec3(self.x * factor, self.y * factor, self.z * factor)

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        return Vec3(self.y * other.z - self.z * other.y,
                    self.z * other.x - self.x * other.z,
                    self.x * other.y - self.y * other.x)

    def length(self):
        return _math.sqrt(self.lengthSqr())

    def lengthSqr(self):
        return self.x * self.x + self.y * self.y + self.z * self.z

    def distanceTo(self, other):
        return _math.sqrt(self.distanceToSqr(other))

    def distanceToSqr(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz

    def normalize(self):
        length = self.length()
        if length < 1.0e-4:
            return Vec3.ZERO
        return self.scale(1.0 / length)

    def horizontalDistanceSqr(self):
        return self.x * self.x + self.z * self.z

    # ---------------- 展示与比较 ----------------

    def equals(self, other):
        if not isinstance(other, Vec3):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def hashCode(self):
        return hash_code(u"{}|{}|{}".format(self.x, self.y, self.z))

    def toString(self):
        return u"({}, {}, {})".format(self.x, self.y, self.z)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __getitem__(self, index):
        return (self.x, self.y, self.z)[index]

    def __add__(self, other):
        return self.add(other)

    def __sub__(self, other):
        return self.subtract(other)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Vec3 {}>".format(self.toString())


Vec3.ZERO = Vec3(0.0, 0.0, 0.0)


# ============================================================
# AABB：碰撞箱
# ============================================================

class AABB(object):
    """
    对应 net.minecraft.world.phys.AABB。

    真实代码里由 Block.box(...) 产出（12 次）：
        Block.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0)
    参数是「两个角」的坐标，而不是「角 + 尺寸」—— 这点容易搞错。
    """

    def __init__(self, min_x, min_y, min_z, max_x, max_y, max_z):
        self.minX = float(min_x)
        self.minY = float(min_y)
        self.minZ = float(min_z)
        self.maxX = float(max_x)
        self.maxY = float(max_y)
        self.maxZ = float(max_z)

    @staticmethod
    def box(x1, y1, z1, x2, y2, z2):
        """对应 Block.box：按两个角构造（允许传入顺序颠倒）。"""
        return AABB(min(x1, x2), min(y1, y2), min(z1, z2),
                    max(x1, x2), max(y1, y2), max(z1, z2))

    def getXSize(self):
        return self.maxX - self.minX

    def getYSize(self):
        return self.maxY - self.minY

    def getZSize(self):
        return self.maxZ - self.minZ

    def move(self, dx, dy, dz):
        return AABB(self.minX + dx, self.minY + dy, self.minZ + dz,
                    self.maxX + dx, self.maxY + dy, self.maxZ + dz)

    def inflate(self, amount):
        return AABB(self.minX - amount, self.minY - amount, self.minZ - amount,
                    self.maxX + amount, self.maxY + amount, self.maxZ + amount)

    def contains(self, x, y=None, z=None):
        if y is None and z is None:
            other = x
            x, y, z = other.x, other.y, other.z
        return (self.minX <= x <= self.maxX and self.minY <= y <= self.maxY
                and self.minZ <= z <= self.maxZ)

    def intersects(self, other):
        return (self.maxX > other.minX and self.minX < other.maxX
                and self.maxY > other.minY and self.minY < other.maxY
                and self.maxZ > other.minZ and self.minZ < other.maxZ)

    def toString(self):
        return u"AABB[{}, {}, {} -> {}, {}, {}]".format(
            self.minX, self.minY, self.minZ, self.maxX, self.maxY, self.maxZ)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.network.chat.Component": Component,
    "net.minecraft.network.chat.MutableComponent": Component,
    "net.minecraft.world.InteractionResult": InteractionResult,
    "net.minecraft.world.InteractionHand": InteractionHand,
    "net.minecraft.core.Direction": Direction,
    "net.minecraft.core.Vec3i": Vec3i,
    "net.minecraft.core.BlockPos": BlockPos,
    "net.minecraft.core.BlockPos$MutableBlockPos": MutableBlockPos,
    "net.minecraft.world.phys.Vec3": Vec3,
    "net.minecraft.world.phys.AABB": AABB,
}


__all__ = [
    "Component",
    "InteractionResult", "InteractionHand",
    "Direction",
    "Vec3i", "BlockPos", "MutableBlockPos",
    "Vec3", "AABB",
    "JAVA_MAP",
]

# -*- coding: utf-8 -*-
# minecraft/block_extra.py
# θ 层：方块的辅助类型（旋转、镜像、渲染形状、状态定义、标签）
#
# 真实用法（逐字来自反编译源码）：
#
#   // RenderShape —— 方块怎么被渲染
#   return RenderShape.INVISIBLE;   // 方块实体自己画
#   return RenderShape.MODEL;       // 用模型画
#
#   // 方块标签（TagKey<Block>）
#   super(BlockTags.MINEABLE_WITH_AXE)
#   return state.is(BlockTags.MINEABLE_WITH_AXE)
#   return BlockTags.INCORRECT_FOR_NETHERITE_TOOL
#   public static final TagKey<Block> MINEABLE =
#       BlockTags.create(ResourceLocation.fromNamespaceAndPath(...))
#
#   // 状态定义（createBlockStateDefinition 的参数类型）
#   protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState>)
#
#   // Mirror / Rotation（结构方块用；模组里出现在方块行为的签名里）
#
# 为什么单独一个文件：这些都是「方块的小辅助类型」，
# 塞进 block.py（已经 30KB）会让它继续膨胀，而且它们彼此无关。
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
    from minecraft.registries import TagKey
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from registries import TagKey  # type: ignore


# ============================================================
# 共用枚举基类
# ============================================================

class _EnumLike(object):
    """
    枚举常量的共用实现：身份比较 + 可哈希 + 可打印。

    这些「枚举」必须是**稳定对象** —— 真实代码用 `==` 或 `is` 判断，
    每次访问造新对象会让比较失败。
    """

    def __init__(self, name):
        self._name = java_to_string(name)

    def name(self):
        return self._name

    def getName(self):
        return self._name

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, _EnumLike) and other._name == self._name

    def hashCode(self):
        return hash_code(u"{}:{}".format(type(self).__name__, self._name))

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


def _make_enum(class_name, names):
    """
    按名字表造一个枚举类（成员挂成类常量）。

    为什么用 type(...) 动态造而不是手写三个类：
      三个枚举的结构完全一样（只有成员名不同），
      手写三遍既啰嗦又容易让行为漂移（比如只给其中一个加了 byName）。
      统一造出来，行为必然一致。
    """
    enum_class = type(str(class_name), (_EnumLike,), {
        "_MEMBER_NAMES": tuple(names),
    })

    for name in names:
        setattr(enum_class, name, _EnumLike(name))

    def _values(cls=enum_class):
        """对应 values()：按声明顺序返回全部常量。"""
        return [getattr(cls, name) for name in cls._MEMBER_NAMES]

    def _by_name(value, cls=enum_class):
        """对应 byName(String)：按名字取，取不到抛异常。"""
        text = java_to_string(value).upper()
        for name in cls._MEMBER_NAMES:
            if name == text:
                return getattr(cls, name)
        raise IllegalArgumentException(
            u"No enum constant {}.{}".format(cls.__name__, value))

    enum_class.values = staticmethod(_values)
    enum_class.byName = staticmethod(_by_name)
    return enum_class


# ============================================================
# RenderShape
# ============================================================

# 对应 net.minecraft.world.level.block.RenderShape —— 方块怎么被渲染
#   INVISIBLE  方块本身不画（由方块实体自己画，例如箱子、熔炉）
#   MODEL      用模型画（绝大多数方块）
#   ENTITYBLOCK_ANIMATED  动画方块实体
RenderShape = _make_enum(u"RenderShape",
                         (u"INVISIBLE", u"MODEL", u"ENTITYBLOCK_ANIMATED"))


# ============================================================
# Mirror / Rotation
# ============================================================

# 对应 net.minecraft.world.level.block.Mirror —— 结构镜像
#   NONE / LEFT_RIGHT / FRONT_BACK
Mirror = _make_enum(u"Mirror", (u"NONE", u"LEFT_RIGHT", u"FRONT_BACK"))


# 对应 net.minecraft.world.level.block.Rotation —— 结构旋转
#   NONE / CLOCKWISE_90 / CLOCKWISE_180 / COUNTERCLOCKWISE_90
Rotation = _make_enum(u"Rotation",
                      (u"NONE", u"CLOCKWISE_90", u"CLOCKWISE_180",
                       u"COUNTERCLOCKWISE_90"))


def _rotation_add(left, right):
    """两个旋转相加（对应 Rotation.add(Rotation)）。"""
    order = (u"NONE", u"CLOCKWISE_90", u"CLOCKWISE_180",
             u"COUNTERCLOCKWISE_90")
    total = (order.index(left.name()) + order.index(right.name())) % 4
    return getattr(Rotation, order[total])


def _rotation_rotate(rotation, times):
    """重复旋转（对应 Rotation.rotate(int)）。"""
    result = Rotation.NONE
    for _index in range(int(times) % 4):
        result = _rotation_add(result, rotation)
    return result


def _rotation_clockwise(rotation):
    """对应 Rotation.getRotated(Rotation)。"""
    return _rotation_add(rotation, Rotation.CLOCKWISE_90)


Rotation.add = staticmethod(_rotation_add)
Rotation.rotate = staticmethod(_rotation_rotate)
Rotation.getRotated = staticmethod(_rotation_clockwise)


def _mirror_mirror(mirror, rotation):
    """
    对应 Mirror.mirror(Rotation)：镜像后再旋转。

    真实语义按 Minecraft 的对照表；这里照抄关键结论：
    LEFT_RIGHT 与 FRONT_BACK 互换，NONE 保持。
    """
    if mirror is Mirror.NONE:
        return Mirror.NONE
    if mirror is Mirror.LEFT_RIGHT:
        return Mirror.FRONT_BACK
    return Mirror.LEFT_RIGHT


Mirror.mirror = staticmethod(_mirror_mirror)


# ============================================================
# DirectionProperty
# ============================================================

class DirectionProperty(object):
    """
    对应 net.minecraft.world.level.block.state.properties.DirectionProperty。

    它就是一个「值是 Direction 的 EnumProperty」。
    真实代码用 `DirectionProperty.create("facing")` 建它。

    实现上直接复用 block.py 的 EnumProperty —— 不重复造轮子。
    """

    @staticmethod
    def create(name, *values):
        from minecraft.block import EnumProperty
        from minecraft.core import Direction

        if values:
            members = list(values)
        else:
            members = [Direction.NORTH, Direction.SOUTH,
                       Direction.WEST, Direction.EAST]
        return EnumProperty.create(name, *members)


# ============================================================
# StateDefinition
# ============================================================

class StateDefinition(object):
    """
    对应 net.minecraft.world.level.block.state.StateDefinition。

    真实代码：
        protected void createBlockStateDefinition(
            StateDefinition.Builder<Block, BlockState> builder) {
            builder.add(FACING, OPEN);
        }

    所以 `Builder.add(...)` 是核心入口。
    它收集属性，`create(...)` 时产出 StateDefinition。
    """

    def __init__(self, owner=None, properties=None):
        self._owner = owner
        self._properties = list(properties) if properties else []
        self._by_name = {}
        for prop in self._properties:
            self._by_name[prop.getName()] = prop

    def getProperties(self):
        return list(self._properties)

    def getProperty(self, name):
        return self._by_name.get(java_to_string(name))

    def getPropertyNames(self):
        return sorted(self._by_name.keys())

    def size(self):
        return len(self._properties)

    def hasProperty(self, name):
        return java_to_string(name) in self._by_name

    def __len__(self):
        return len(self._properties)

    def __repr__(self):
        return u"<StateDefinition {} 个属性>".format(len(self._properties))


class StateDefinitionBuilder(object):
    """
    对应 StateDefinition.Builder。

    链式约定照 Java：`add(...)` 返回自身，
    `create(...)` 产出 StateDefinition。
    """

    def __init__(self, owner=None):
        self._owner = owner
        self._properties = []

    @staticmethod
    def of(owner=None):
        return StateDefinitionBuilder(owner)

    def add(self, *properties):
        """对应 add(Property...)：支持可变参数与列表。"""
        for prop in properties:
            if isinstance(prop, (list, tuple)):
                for inner in prop:
                    self._add_one(inner)
            else:
                self._add_one(prop)
        return self

    def _add_one(self, prop):
        if prop is None:
            raise IllegalArgumentException(u"add 收到 None")
        # 同名属性只允许加一次 —— 真实代码里重复加会在建状态表时出错，
        # 这里提前报，定位成本低得多。
        for existing in self._properties:
            if existing.getName() == prop.getName():
                raise IllegalArgumentException(
                    u"属性 {} 重复添加".format(prop.getName()))
        self._properties.append(prop)

    def create(self, owner=None, factory=None):
        """
        对应 create(...)：产出 StateDefinition。

        `factory` 参数接收但不用 —— Java 那边是用它把「属性组合」
        映射成 BlockState 实例；本实现的 BlockState 是通用的，
        不需要每个方块一套工厂。
        """
        return StateDefinition(owner if owner is not None else self._owner,
                               self._properties)

    def __repr__(self):
        return u"<StateDefinition.Builder {} 个属性>".format(
            len(self._properties))


StateDefinition.Builder = StateDefinitionBuilder


# ============================================================
# TooltipFlag
# ============================================================

class TooltipFlag(object):
    """
    对应 net.minecraft.world.item.TooltipFlag。

    真实代码在物品的 appendHoverText 里收它，用来决定
    「要不要显示进阶提示」（按 F3+H 切换的那个）。

    它有两个状态：NORMAL / ADVANCED。
    """

    NORMAL = None
    ADVANCED = None

    def __init__(self, advanced=False):
        self._advanced = bool(advanced)

    @staticmethod
    def of(advanced):
        return TooltipFlag(advanced)

    @staticmethod
    def defaultValue():
        """对应 TooltipFlag.Default.NORMAL。"""
        return TooltipFlag.NORMAL

    def isAdvanced(self):
        """对应 isAdvanced()：是否显示进阶提示。"""
        return self._advanced

    def name(self):
        return u"ADVANCED" if self._advanced else u"NORMAL"

    def toString(self):
        return self.name()

    def __eq__(self, other):
        return isinstance(other, TooltipFlag) \
            and other._advanced == self._advanced

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._advanced)

    def __str__(self):
        return self.name()

    def __repr__(self):
        return u"<TooltipFlag {}>".format(self.name())


TooltipFlag.NORMAL = TooltipFlag(False)
TooltipFlag.ADVANCED = TooltipFlag(True)
# Java 里还有 TooltipFlag.Default 枚举
TooltipFlag.Default = TooltipFlag


# ============================================================
# BlockTags
# ============================================================

class BlockTags(object):
    """
    对应 net.minecraft.tags.BlockTags。

    真实用法：
        super(BlockTags.MINEABLE_WITH_AXE)
        state.is(BlockTags.MINEABLE_WITH_AXE)
        BlockTags.INCORRECT_FOR_NETHERITE_TOOL
        BlockTags.create(ResourceLocation.fromNamespaceAndPath(...))

    **`create` 的语义要注意**：它建的是**自定义标签**，
    位置由传入的 ResourceLocation 决定，不是原版标签。
    """

    MINEABLE_WITH_PICKAXE = None
    MINEABLE_WITH_AXE = None
    MINEABLE_WITH_SHOVEL = None
    MINEABLE_WITH_HOE = None
    NEEDS_DIAMOND_TOOL = None
    NEEDS_IRON_TOOL = None
    NEEDS_STONE_TOOL = None
    INCORRECT_FOR_WOODEN_TOOL = None
    INCORRECT_FOR_STONE_TOOL = None
    INCORRECT_FOR_IRON_TOOL = None
    INCORRECT_FOR_DIAMOND_TOOL = None
    INCORRECT_FOR_NETHERITE_TOOL = None
    LOGS = None
    PLANKS = None
    LEAVES = None

    @staticmethod
    def create(location):
        """
        对应 BlockTags.create(ResourceLocation)：建一个**自定义**方块标签。

        真实代码：
            public static final TagKey<Block> MINEABLE =
                BlockTags.create(ResourceLocation.fromNamespaceAndPath(...))
        """
        return TagKey.create(u"minecraft:block", location)

    @staticmethod
    def createTag(name):
        """便利入口：按名字建原版风格的标签键。"""
        return TagKey.create(u"minecraft:block",
                      u"minecraft:{}".format(java_to_string(name)))


def _init_block_tags():
    """All public 1.21.1 fields, with paths read from the pinned original jar."""
    from minecraft.block_tag_data import BLOCK_TAG_LOCATIONS
    for name, location in BLOCK_TAG_LOCATIONS.items():
        setattr(BlockTags, name, BlockTags.create(location))


_init_block_tags()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.level.block.RenderShape": RenderShape,
    "net.minecraft.world.level.block.Mirror": Mirror,
    "net.minecraft.world.level.block.Rotation": Rotation,
    "net.minecraft.world.level.block.state.StateDefinition": StateDefinition,
    "net.minecraft.world.level.block.state.StateDefinition$Builder":
        StateDefinitionBuilder,
    "net.minecraft.world.level.block.state.properties.DirectionProperty":
        DirectionProperty,
    "net.minecraft.world.item.TooltipFlag": TooltipFlag,
    "net.minecraft.tags.BlockTags": BlockTags,
}


__all__ = [
    "RenderShape", "Mirror", "Rotation", "DirectionProperty",
    "StateDefinition", "StateDefinitionBuilder",
    "TooltipFlag", "BlockTags",
    "JAVA_MAP",
]

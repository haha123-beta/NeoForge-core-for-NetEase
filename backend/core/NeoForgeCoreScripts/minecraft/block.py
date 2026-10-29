# -*- coding: utf-8 -*-
# minecraft/block.py
# θ 层：方块（Block / BlockState / 方块属性）
#
# 真实用法（从反编译源码逐字提取）：
#
#   // 方块类定义：属性走链式 Builder
#   public ManaitaPlusCraftingBlock() {
#       super(BlockBehaviour.Properties.of().forceSolidOff());
#   }
#
#   // 属性读写（这两个是整个模组里最热的操作）
#   state.getValue(FACING)        64 次
#   state.setValue(FACING, dir)   67 次
#
#   // 世界侧读写
#   level.getBlockState(pos)      41 次
#   state.getBlock()              40 次
#   level.getFluidState(pos)       5 次
#
#   // 掉落物
#   Block.getDrops(state, serverLevel, pos, blockEntity)   3 次
#
# **核心语义**：`setValue` **不修改原对象**，而是返回一个新的 BlockState ——
# Minecraft 的 BlockState 是不可变的。写成原地修改会让方块状态在
# 各处共享时互相污染（而且不报错，极难排查）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
    from minecraft.core import AABB
    from minecraft.item import ItemStack
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore
    from core import AABB  # type: ignore
    from item import ItemStack  # type: ignore


# ============================================================
# 方块属性
# ============================================================

class Property(object):
    """
    对应 net.minecraft.world.level.block.state.properties.Property。

    一个属性有名字和一组可选值。BlockState 就是「属性 -> 值」的映射。

    真实用法里属性是**静态常量**，例如：
        public static final DirectionProperty FACING = ...;
        public static final BooleanProperty OPEN = BooleanProperty.create("open");
    靠**对象身份**做键（不是靠名字字符串），所以这里保持身份语义。
    """

    def __init__(self, name, values):
        self.name = java_to_string(name)
        self._values = list(values)
        # 值 -> 规范化后的值。
        #
        # 每个值登记**三种键**：真实值、字符串形态、小写字符串形态。
        # 为什么：属性值既可能以真实对象传入（setValue(prop, True)），
        # 也可能以文本传入（配置文件里读到的 "true"、从名字解析的 "north"）。
        # 只登记一种键会导致另一半查不到 —— 实测踩到：
        # BooleanProperty 用 "true" 查会报「没有值 true」，尽管可选值里明明有。
        self._index = {}
        for value in self._values:
            self._index[self._canonical_key(value)] = value
            text = java_to_string(value)
            self._index[(u"text", text)] = value
            self._index[(u"text", text.lower())] = value

    @staticmethod
    def _canonical_key(value):
        """值本身的规范键（不涉及文本解析）。"""
        if isinstance(value, bool):
            return (u"bool", value)
        if isinstance(value, int):
            return (u"int", value)
        return (u"text", java_to_string(value))

    @staticmethod
    def _key(value):
        """
        计算查询用的键。

        布尔要特别处理：Python 里 `isinstance(True, int)` 为真，
        但 `1 == True`，所以顺序上必须先判 bool，否则 True 会被当成整数 1。
        """
        if isinstance(value, bool):
            # 布尔同时按真实值和小写文本登记，所以这里两种键都试
            return (u"bool", value)
        if isinstance(value, int):
            return (u"int", value)
        return (u"text", java_to_string(value).lower())

    def getName(self):
        return self.name

    def getPossibleValues(self):
        return list(self._values)

    def getValue(self, name):
        """
        对应 Property.getValue(String)：按名字取枚举值。

        Java 里返回 Optional；这里取不到就**抛异常**而不是返回 None ——
        属性名写错是明确的 bug，早报早改。
        """
        key = self._key(name)
        if key in self._index:
            return self._index[key]
        # 文本形态再兜一次（大小写、布尔字面量）
        text_key = (u"text", java_to_string(name).lower())
        if text_key in self._index:
            return self._index[text_key]
        raise IllegalArgumentException(
            u"属性 {} 没有值 {}（可选值: {}）".format(
                self.name, name,
                u", ".join([java_to_string(v) for v in self._values])))

    def getValueCount(self):
        return len(self._values)

    def equals(self, other):
        return isinstance(other, Property) and other.name == self.name

    def hashCode(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __repr__(self):
        return u"<Property {} {}>".format(self.name, self._values)


class BooleanProperty(Property):
    """对应 BooleanProperty：true / false 两个值。"""

    def __init__(self, name):
        Property.__init__(self, name, [True, False])

    @staticmethod
    def create(name):
        return BooleanProperty(name)


class IntegerProperty(Property):
    """对应 IntegerProperty：一段连续的整数。"""

    def __init__(self, name, min_value, max_value):
        Property.__init__(self, name,
                          list(range(int(min_value), int(max_value) + 1)))
        self.min_value = int(min_value)
        self.max_value = int(max_value)

    @staticmethod
    def create(name, min_value, max_value):
        if min_value > max_value:
            raise IllegalArgumentException(
                u"IntegerProperty {} 的下限 {} 大于上限 {}".format(
                    name, min_value, max_value))
        return IntegerProperty(name, min_value, max_value)


class EnumProperty(Property):
    """对应 EnumProperty：一组枚举值（本实现里就是一组对象）。"""

    def __init__(self, name, values):
        Property.__init__(self, name, values)

    @staticmethod
    def create(name, *values):
        if len(values) == 1 and isinstance(values[0], (list, tuple)):
            values = values[0]
        if not values:
            raise IllegalArgumentException(
                u"EnumProperty {} 至少要有一个值".format(name))
        return EnumProperty(name, values)


# ============================================================
# BlockState
# ============================================================

class BlockState(object):
    """
    对应 net.minecraft.world.level.block.state.BlockState。

    **不可变**：`setValue` 返回新对象，不改原对象。
    这是 Minecraft 的核心设计 —— 全世界所有同类方块共享同一批
    BlockState 实例，原地修改会污染全局。

    真实验证：setValue 用了 67 次、getValue 用了 64 次，
    而且几乎全在渲染与逻辑代码里，一旦改成可变就会到处出错。
    """

    def __init__(self, block, values=None):
        self._block = block
        # 属性 -> 值，键用属性**对象身份**
        self._values = dict(values) if values else {}

    # ---------------- 属性读写 ----------------

    def getValue(self, prop):
        """
        对应 getValue(Property)：取某个属性的当前值。

        属性不存在时抛异常 —— 与 Java 一致（Java 会抛
        IllegalArgumentException，因为属性必须在定义时就声明）。
        """
        if not isinstance(prop, Property):
            raise IllegalArgumentException(
                u"getValue 需要 Property，收到 {}".format(type(prop).__name__))
        if prop not in self._values:
            raise IllegalArgumentException(
                u"方块 {} 没有属性 {}".format(
                    self._block.getDescriptionId() if self._block else u"<未知>",
                    prop.getName()))
        return self._values[prop]

    def hasProperty(self, prop):
        return prop in self._values

    def getProperties(self):
        """返回所有 (属性, 值) 对。"""
        return list(self._values.items())

    def getPropertyNames(self):
        return sorted([prop.getName() for prop in self._values])

    def setValue(self, prop, value):
        """
        对应 setValue(Property, Comparable)：返回**新** BlockState。

        值不合法时抛异常并列出可选值 —— 属性值写错是常见错误，
        含糊的报错会让人查很久。
        """
        if not isinstance(prop, Property):
            raise IllegalArgumentException(
                u"setValue 需要 Property，收到 {}".format(type(prop).__name__))
        if prop not in self._values:
            raise IllegalArgumentException(
                u"方块 {} 没有属性 {}".format(
                    self._block.getDescriptionId() if self._block else u"<未知>",
                    prop.getName()))

        normalized = prop._index.get(prop._key(value))
        if normalized is None:
            normalized = prop._index.get(
                (u"text", java_to_string(value).lower()))
        if normalized is None:
            raise IllegalArgumentException(
                u"属性 {} 不接受值 {}（可选: {}）".format(
                    prop.getName(), java_to_string(value),
                    u", ".join([java_to_string(v)
                                for v in prop.getPossibleValues()])))

        new_values = dict(self._values)
        new_values[prop] = normalized
        return BlockState(self._block, new_values)

    def cycle(self, prop):
        """对应 cycle(Property)：切到下一个值（用在交互里循环切换）。"""
        values = prop.getPossibleValues()
        current = self.getValue(prop)
        index = 0
        for position in range(len(values)):
            if prop._canonical_key(values[position]) \
                    == prop._canonical_key(current):
                index = position
                break
        return self.setValue(prop, values[(index + 1) % len(values)])

    # ---------------- 所属方块 ----------------

    def getBlock(self):
        """对应 getBlock()（真实用了 40 次）。"""
        return self._block

    def isBlock(self, block):
        """
        对应 is(Block)：是不是某个方块的状态。

        **方法名不是 is** —— `is` 是 Python 关键字，
        `state.is(block)` 在 Python 里无法解析。
        改名约定见 core/keyword_renames.py。
        """
        if isinstance(block, BlockState):
            return self._block is block._block
        from minecraft.registries import TagKey
        from minecraft.holder_sets import HolderSet
        if isinstance(block, (TagKey, HolderSet)):
            from neoforge.registries import BUILT_IN_REGISTRIES
            holder = BUILT_IN_REGISTRIES.BLOCK._holder_for_value(self._block)
            return holder.isTag(block) if isinstance(block, TagKey) else block.contains(holder)
        return self._block is block

    def isAir(self):
        return self._block is not None and self._block.isAir()

    # ---------------- 形状与掉落 ----------------

    def getShape(self):
        """对应 getShape(...)：碰撞形状。无形状时返回空形状。"""
        if self._block is None:
            return None
        return self._block.getShape()

    def getDrops(self, server_level=None, pos=None):
        """
        对应 Block.getDrops(...)（真实 3 次）。

        本实现返回「该方块对应的物品栈」——
        真实的掉落表（loot table）逻辑需要引擎支持，
        这里只做最直接的一一对应，落地方式留给引擎适配器。
        """
        if self._block is None:
            return []
        item = self._block.asItem()
        if item is None:
            return []
        return [ItemStack(item, 1)]

    # ---------------- 身份 ----------------

    def equals(self, other):
        if not isinstance(other, BlockState):
            return False
        if other._block is not self._block:
            return False
        if len(other._values) != len(self._values):
            return False
        for prop in self._values:
            if prop._canonical_key(self._values[prop]) \
                    != prop._canonical_key(other._values.get(prop)):
                return False
        return True

    def hashCode(self):
        parts = [str(id(self._block))]
        for prop in sorted(self._values, key=lambda p: p.getName()):
            parts.append(u"{}={}".format(prop.getName(), self._values[prop]))
        return hash(u"|".join(parts))

    def toString(self):
        if not self._values:
            return java_to_string(self._block) if self._block else u"<no block>"
        parts = []
        for prop in sorted(self._values, key=lambda p: p.getName()):
            parts.append(u"{}={}".format(prop.getName(), self._values[prop]))
        return u"{}[{}]".format(self._block.getDescriptionId()
                                if self._block else u"<no block>",
                                u",".join(parts))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<BlockState {}>".format(self.toString())


# ============================================================
# FluidState / 材质的轻量替身
# ============================================================

class FluidState(object):
    """
    对应 net.minecraft.world.level.material.FluidState。

    真实用法：level.getFluidState(pos) 5 次，主要用于判断是否含水。
    """

    class _Fluid(object):
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
            return u"<Fluid.{}>".format(self._name)

    EMPTY = None
    WATER = None
    LAVA = None

    def __init__(self, fluid=None, amount=0):
        self._fluid = fluid if fluid is not None else FluidState.EMPTY
        self._amount = int(amount)

    def getType(self):
        return self._fluid

    def isEmpty(self):
        return self._fluid is FluidState.EMPTY

    def isSource(self):
        """是否水源/岩浆源（amount 满）。"""
        return self._amount >= 8

    def getAmount(self):
        return self._amount

    def isFluid(self, fluid):
        """
        对应 FluidState.is(Fluid)。

        **方法名不是 is** —— `is` 在 Python 3 里是关键字，
        核心包源码必须 Py2/Py3 两版通吃，所以一律避开。
        全项目统一约定，见 core/keyword_renames.py。
        """
        return self._fluid is fluid

    def __repr__(self):
        return u"<FluidState {}({})>".format(self._fluid, self._amount)


FluidState.EMPTY = FluidState._Fluid(u"EMPTY")
FluidState.WATER = FluidState._Fluid(u"WATER")
FluidState.LAVA = FluidState._Fluid(u"LAVA")


# ============================================================
# BlockBehaviour.Properties
# ============================================================

class BlockProperties(object):
    """
    对应 BlockBehaviour.Properties。

    真实用法（链式，且每个方法返回自身）：
        BlockBehaviour.Properties.of().forceSolidOff()
        BlockBehaviour.Properties.of().strength(3.0F).sound(SoundType.WOOD)
    """

    def __init__(self):
        self._material = None
        self._destroy_time = 0.0
        self._explosion_resistance = 0.0
        self._sound = None
        self._requires_correct_tool = False
        self._no_occlusion = False
        self._force_solid_off = False
        self._light_emission = 0
        self._drops = None
        self._random_ticks = False

    @staticmethod
    def of():
        """对应 Properties.of()：建一份默认属性。"""
        return BlockProperties()

    @staticmethod
    def ofFullCopy(other):
        """对应 ofFullCopy(Properties)：拷贝一份。"""
        clone = BlockProperties()
        clone._material = other._material
        clone._destroy_time = other._destroy_time
        clone._explosion_resistance = other._explosion_resistance
        clone._sound = other._sound
        clone._requires_correct_tool = other._requires_correct_tool
        clone._no_occlusion = other._no_occlusion
        clone._force_solid_off = other._force_solid_off
        clone._light_emission = other._light_emission
        clone._drops = other._drops
        clone._random_ticks = other._random_ticks
        return clone

    # ---------------- 链式设置 ----------------

    def material(self, value):
        self._material = value
        return self

    def strength(self, destroy_time, explosion_resistance=None):
        """
        对应 strength(float) / strength(float, float)。
        Python 没有重载，第二个参数可选即可。
        """
        self._destroy_time = float(destroy_time)
        if explosion_resistance is None:
            self._explosion_resistance = float(destroy_time)
        else:
            self._explosion_resistance = float(explosion_resistance)
        return self

    def destroyTime(self, value):
        self._destroy_time = float(value)
        return self

    def explosionResistance(self, value):
        self._explosion_resistance = float(value)
        return self

    def sound(self, value):
        self._sound = value
        return self

    def requiresCorrectToolForDrops(self):
        self._requires_correct_tool = True
        return self

    def noOcclusion(self):
        self._no_occlusion = True
        return self

    def forceSolidOff(self):
        self._force_solid_off = True
        return self

    def lightLevel(self, value):
        self._light_emission = int(value)
        return self

    def dropsLike(self, block):
        self._drops = block
        return self

    def randomTicks(self):
        self._random_ticks = True
        return self

    def noLootTable(self):
        self._drops = None
        return self

    # ---------------- 读取 ----------------

    def getDestroyTime(self):
        return self._destroy_time

    def getExplosionResistance(self):
        return self._explosion_resistance

    def getSound(self):
        return self._sound

    def getLightEmission(self):
        return self._light_emission

    def isRequiresCorrectTool(self):
        return self._requires_correct_tool

    def isNoOcclusion(self):
        return self._no_occlusion

    def isForceSolidOff(self):
        return self._force_solid_off

    def hasRandomTicks(self):
        return self._random_ticks

    def __repr__(self):
        return u"<Block.Properties destroy={} solidOff={}>".format(
            self._destroy_time, self._force_solid_off)


# ============================================================
# Block
# ============================================================

class Block(object):
    """
    对应 net.minecraft.world.level.block.Block。

    与 Item 一样，Block 是「注册表里的类型」，不是世界里那一格。
    世界里的是 BlockState（带属性）与 BlockPos（带位置）。

    本层只做数据结构与形状，不做方块行为（破坏、放置、掉落表）——
    那些必须和引擎对接，属于引擎适配器的职责。
    """

    _next_id = [0]

    def requiredFeatures(self):
        from minecraft.feature_flags import FeatureFlags
        return FeatureFlags.VANILLA_SET

    def isEnabled(self, enabled):
        return self.requiredFeatures().isSubsetOf(enabled)

    def __init__(self, properties=None, identifier=None):
        if properties is None:
            properties = BlockProperties()
        if not isinstance(properties, BlockProperties):
            raise IllegalArgumentException(
                u"Block 的构造参数应是 BlockBehaviour.Properties，收到 {}".format(
                    type(properties).__name__))

        self.properties = properties
        self._identifier = identifier

        Block._next_id[0] += 1
        self._id = Block._next_id[0]

        self._registry_name = None
        self._state_definition = {}      # 属性名 -> Property
        self._shape = AABB.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
        self._air = False

    # ---------------- 状态定义 ----------------

    def createBlockStateDefinition(self, *properties):
        """
        对应 createBlockStateDefinition(StateDefinition.Builder)。

        Java 里是通过 Builder 收集属性；这里直接接受属性列表，
        语义相同而少一层无意义的包装。
        """
        for prop in properties:
            if isinstance(prop, (list, tuple)):
                for inner in prop:
                    self._add_property(inner)
            else:
                self._add_property(prop)
        return self

    def _add_property(self, prop):
        if not isinstance(prop, Property):
            raise IllegalArgumentException(
                u"方块属性应是 Property，收到 {}".format(type(prop).__name__))
        if prop.getName() in self._state_definition:
            raise IllegalArgumentException(
                u"方块属性 {} 重复定义".format(prop.getName()))
        self._state_definition[prop.getName()] = prop

    def getStateDefinition(self):
        return dict(self._state_definition)

    def defaultBlockState(self):
        """
        对应 defaultBlockState()：每个属性取第一个值。

        真实代码大量以它做起点，再 setValue 到需要的状态。
        """
        values = {}
        for prop in self._state_definition.values():
            values[prop] = prop.getPossibleValues()[0]
        return BlockState(self, values)

    def getStateForPlacement(self, **values):
        """便捷入口：按属性名给值构造状态（Java 里由各属性的 getStateForPlacement 负责）。"""
        state = self.defaultBlockState()
        for name in values:
            prop = self._state_definition.get(java_to_string(name))
            if prop is None:
                raise IllegalArgumentException(
                    u"方块 {} 没有属性 {}".format(self._registry_name, name))
            state = state.setValue(prop, values[name])
        return state

    # ---------------- 形状 ----------------

    def setShape(self, shape):
        self._shape = shape
        return self

    def getShape(self):
        return self._shape

    # ---------------- 物品形态 ----------------

    def asItem(self):
        """
        对应 asItem()：方块对应的物品（BlockItem）。

        返回 None 表示这个方块没有物品形态（例如纯技术方块）。
        注意 None 是合法返回 —— 与 Minecraft 里返回 Items.AIR 等价。
        """
        return getattr(self, "_item", None)

    def setItem(self, item):
        self._item = item
        return self

    # ---------------- 注册信息 ----------------

    def setRegistryName(self, name):
        self._registry_name = java_to_string(name)
        return self

    def getRegistryName(self):
        return self._registry_name

    def getDescriptionId(self):
        if self._registry_name:
            return u"block.{}".format(java_to_string(self._registry_name)
                                      .replace(u":", u"."))
        return u"block.unregistered.{}".format(self._id)

    def isAir(self):
        return self._air

    def setIsAir(self, value):
        self._air = bool(value)
        return self

    # ---------------- 身份 ----------------

    def equals(self, other):
        if isinstance(other, Block):
            return self._id == other._id
        return False

    def hashCode(self):
        return self._id

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.getDescriptionId()

    def __repr__(self):
        return u"<Block #{} {}>".format(self._id,
                                        self._registry_name or u"未注册")


# Java 里是内部类 BlockBehaviour.Properties
Block.Properties = BlockProperties
Block.Behaviour = Block


# ============================================================
# 常见方块（对应 Blocks.* 常量）
# ============================================================

class _BlocksHolder(object):
    """
    对应 net.minecraft.world.level.block.Blocks。

    懒加载：取哪个建哪个，且同名始终是同一个对象。
    与 Items 同样的理由 —— 预造全部方块既浪费又容易与注册表脱节。
    """

    def __init__(self):
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        if name not in self._cache:
            block = Block(BlockProperties(),
                          identifier=u"minecraft:{}".format(name.lower()))
            block.setRegistryName(u"minecraft:{}".format(name.lower()))
            if name == u"AIR":
                block.setIsAir(True)
            self._cache[name] = block
        return self._cache[name]

    def clear(self):
        self._cache = {}

    def __repr__(self):
        return u"<Blocks {} 个已建>".format(len(self._cache))


BLOCKS = _BlocksHolder()


# ============================================================
# SoundType
# ============================================================

class SoundType(object):
    """对应 net.minecraft.world.level.block.SoundType（真实代码里用于 .sound(...)）。"""

    class _Sound(object):
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
            return u"<SoundType.{}>".format(self._name)

    WOOD = None
    STONE = None
    METAL = None
    GLASS = None
    WOOL = None
    SAND = None
    GRAVEL = None
    LILY_PAD = None


SoundType.WOOD = SoundType._Sound(u"WOOD")
SoundType.STONE = SoundType._Sound(u"STONE")
SoundType.METAL = SoundType._Sound(u"METAL")
SoundType.GLASS = SoundType._Sound(u"GLASS")
SoundType.WOOL = SoundType._Sound(u"WOOL")
SoundType.SAND = SoundType._Sound(u"SAND")
SoundType.GRAVEL = SoundType._Sound(u"GRAVEL")
SoundType.LILY_PAD = SoundType._Sound(u"LILY_PAD")


# ============================================================
# 常用属性常量（对应 BlockStateProperties）
# ============================================================

class BlockStateProperties(object):
    """
    对应 net.minecraft.world.level.block.state.properties.BlockStateProperties。

    这些是原版预定义的常用属性；模组代码直接引用它们做 setValue/getValue。
    """

    FACING = None
    HORIZONTAL_FACING = None
    HOPPER_FACING = None
    OPEN = None
    POWERED = None
    LIT = None
    WATERLOGGED = None
    PERSISTENT = None
    AGE_0_25 = None
    SLAB_TYPE = None


def _init_block_state_properties():
    """属性常量延迟初始化：它们依赖 Direction，放在模块末尾更清楚。"""
    try:
        from minecraft.core import Direction
    except ImportError:
        from core import Direction  # type: ignore

    BlockStateProperties.FACING = EnumProperty.create(
        u"facing", Direction.DOWN, Direction.UP, Direction.NORTH,
        Direction.SOUTH, Direction.WEST, Direction.EAST)
    BlockStateProperties.HORIZONTAL_FACING = EnumProperty.create(
        u"facing", Direction.NORTH, Direction.SOUTH, Direction.WEST,
        Direction.EAST)
    BlockStateProperties.HOPPER_FACING = EnumProperty.create(
        u"facing", Direction.DOWN, Direction.NORTH, Direction.SOUTH,
        Direction.WEST, Direction.EAST)
    BlockStateProperties.OPEN = BooleanProperty.create(u"open")
    BlockStateProperties.POWERED = BooleanProperty.create(u"powered")
    BlockStateProperties.LIT = BooleanProperty.create(u"lit")
    BlockStateProperties.WATERLOGGED = BooleanProperty.create(u"waterlogged")
    BlockStateProperties.PERSISTENT = BooleanProperty.create(u"persistent")
    BlockStateProperties.AGE_0_25 = IntegerProperty.create(u"age", 0, 25)
    BlockStateProperties.SLAB_TYPE = EnumProperty.create(
        u"type", u"bottom", u"top", u"double")


_init_block_state_properties()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.level.block.Block": Block,
    "net.minecraft.world.level.block.Blocks": BLOCKS,
    "net.minecraft.world.level.block.state.BlockState": BlockState,
    "net.minecraft.world.level.block.state.BlockBehaviour": Block,
    "net.minecraft.world.level.block.state.BlockBehaviour$Properties":
        BlockProperties,
    "net.minecraft.world.level.block.state.properties.Property": Property,
    "net.minecraft.world.level.block.state.properties.BooleanProperty":
        BooleanProperty,
    "net.minecraft.world.level.block.state.properties.IntegerProperty":
        IntegerProperty,
    "net.minecraft.world.level.block.state.properties.EnumProperty":
        EnumProperty,
    "net.minecraft.world.level.block.state.properties.BlockStateProperties":
        BlockStateProperties,
    "net.minecraft.world.level.block.SoundType": SoundType,
    "net.minecraft.world.level.material.FluidState": FluidState,
}


__all__ = [
    "Property", "BooleanProperty", "IntegerProperty", "EnumProperty",
    "BlockState", "FluidState",
    "BlockProperties", "Block",
    "BLOCKS", "SoundType", "BlockStateProperties",
    "JAVA_MAP",
]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)

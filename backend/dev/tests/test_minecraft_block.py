# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/block.py（方块）

真实依据（逐字来自反编译源码）：
    public ManaitaPlusCraftingBlock() {
        super(BlockBehaviour.Properties.of().forceSolidOff());
    }

    state.getValue(FACING)        64 次
    state.setValue(FACING, dir)   67 次
    level.getBlockState(pos)      41 次
    state.getBlock()              40 次
    Block.box(...)                12 次
    level.getFluidState(pos)       5 次
    Block.getDrops(...)            3 次

验证点：
  1. 属性类型（Boolean / Integer / Enum）与取值校验
  2. **BlockState 的不可变性**（setValue 返回新对象，不污染原状态）—— 最关键
  3. cycle 循环切换
  4. 属性的身份语义（同名属性不等）
  5. BlockProperties 链式 + 各设置项
  6. Block 的状态定义、defaultBlockState、asItem
  7. FluidState / SoundType / BlockStateProperties 常量
  8. 名称映射表
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
block_mod = pkg.load("minecraft.block")

Block = block_mod.Block
BlockState = block_mod.BlockState
Properties = block_mod.BlockProperties
BSP = block_mod.BlockStateProperties


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("属性类型")
    # ------------------------------------------------------------
    open_prop = block_mod.BooleanProperty.create(u"open")
    check(u"BooleanProperty 有两个值", open_prop.getValueCount() == 2,
          open_prop.getValueCount())
    check(u"BooleanProperty 名字正确", open_prop.getName() == u"open")
    check(u"取 true 值", open_prop.getValue(u"true") is True
          or open_prop.getValue(u"True") is True)
    check(u"取 false 值", open_prop.getValue(u"false") is False)
    check(u"非法值报错", raises(open_prop.getValue, u"maybe"))

    age_prop = block_mod.IntegerProperty.create(u"age", 0, 3)
    check(u"IntegerProperty 值域正确", age_prop.getValueCount() == 4,
          age_prop.getValueCount())
    check(u"整数属性记录上下限",
          (age_prop.min_value, age_prop.max_value) == (0, 3))
    check(u"下限大于上限报错",
          raises(block_mod.IntegerProperty.create, u"bad", 5, 1))

    enum_prop = block_mod.EnumProperty.create(
        u"type", u"bottom", u"top", u"double")
    check(u"EnumProperty 三个值", enum_prop.getValueCount() == 3)
    check(u"按名字取枚举值",
          enum_prop.getValue(u"bottom") == u"bottom")
    check(u"枚举值大小写不敏感",
          enum_prop.getValue(u"BOTTOM") == u"bottom")
    check(u"空枚举报错", raises(block_mod.EnumProperty.create, u"empty"))

    check(u"属性按名字比较",
          block_mod.BooleanProperty.create(u"x")
          == block_mod.BooleanProperty.create(u"x"))
    check(u"同名属性是不同对象（身份语义）",
          block_mod.BooleanProperty.create(u"x")
          is not block_mod.BooleanProperty.create(u"x"))

    # ------------------------------------------------------------
    section("BlockState 不可变性（最关键）")
    # ------------------------------------------------------------
    # Minecraft 全世界共享 BlockState 实例，原地修改会污染全局。
    # 真实代码里 setValue 用了 67 次，一旦改成可变就会到处出错且不报错。
    block = Block(Properties()).setRegistryName(u"manaita:crafting_manaita")
    block.createBlockStateDefinition(BSP.HORIZONTAL_FACING, BSP.OPEN)

    base = block.defaultBlockState()
    check(u"默认状态取第一个值",
          base.getValue(BSP.HORIZONTAL_FACING) is mc.Direction.NORTH,
          base.getValue(BSP.HORIZONTAL_FACING))
    check(u"布尔属性默认第一个值是 True",
          base.getValue(BSP.OPEN) is True, base.getValue(BSP.OPEN))

    changed = base.setValue(BSP.HORIZONTAL_FACING, mc.Direction.SOUTH)
    check(u"setValue 返回新对象", changed is not base)
    check(u"新对象是目标值",
          changed.getValue(BSP.HORIZONTAL_FACING) is mc.Direction.SOUTH,
          changed.getValue(BSP.HORIZONTAL_FACING))
    check(u"**原对象未被修改**（不可变性）",
          base.getValue(BSP.HORIZONTAL_FACING) is mc.Direction.NORTH,
          base.getValue(BSP.HORIZONTAL_FACING))

    check(u"类型是 BlockState", isinstance(changed, BlockState))

    # 链式改两个属性
    both = base.setValue(BSP.HORIZONTAL_FACING, mc.Direction.EAST) \
               .setValue(BSP.OPEN, False)
    check(u"链式 setValue 生效",
          both.getValue(BSP.HORIZONTAL_FACING) is mc.Direction.EAST
          and both.getValue(BSP.OPEN) is False,
          (both.getValue(BSP.HORIZONTAL_FACING), both.getValue(BSP.OPEN)))
    check(u"链式后原状态仍未变",
          base.getValue(BSP.OPEN) is True)

    check(u"设非法属性值报错",
          raises(base.setValue, BSP.HORIZONTAL_FACING, u"sideways"))
    check(u"设未声明的属性报错", raises(base.setValue, BSP.POWERED, True))
    check(u"取未声明的属性报错", raises(base.getValue, BSP.POWERED))
    check(u"setValue 需要 Property", raises(base.setValue, u"not_prop", 1))
    check(u"getValue 需要 Property", raises(base.getValue, u"not_prop"))

    check(u"hasProperty 正确",
          base.hasProperty(BSP.OPEN) is True
          and base.hasProperty(BSP.POWERED) is False)

    # 不同的状态实例
    a = base.setValue(BSP.OPEN, True)
    b = base.setValue(BSP.OPEN, True)
    check(u"同属性同值的新状态相等", a == b)
    check(u"但仍是不同对象", a is not b)
    check(u"可作字典键", {a: u"v"}[b] == u"v")

    # ------------------------------------------------------------
    section("BlockState：cycle 循环切换")
    # ------------------------------------------------------------
    facing_prop = block_mod.EnumProperty.create(
        u"facing", u"north", u"south", u"west", u"east")
    cycle_block = Block(Properties()).setRegistryName(u"t:cycler")
    cycle_block.createBlockStateDefinition(facing_prop)
    state = cycle_block.defaultBlockState()
    check(u"起始是 north", state.getValue(facing_prop) == u"north")

    state = state.cycle(facing_prop)
    check(u"cycle 到 south", state.getValue(facing_prop) == u"south",
          state.getValue(facing_prop))
    state = state.cycle(facing_prop)
    state = state.cycle(facing_prop)
    check(u"cycle 到 east", state.getValue(facing_prop) == u"east",
          state.getValue(facing_prop))
    state = state.cycle(facing_prop)
    check(u"cycle 回到起点（取模）", state.getValue(facing_prop) == u"north",
          state.getValue(facing_prop))

    # ------------------------------------------------------------
    section("BlockState：getBlock / is / isAir")
    # ------------------------------------------------------------
    check(u"getBlock 返回所属方块", base.getBlock() is block)
    check(u"isBlock(Block) 同类为真", base.isBlock(block) is True)
    other_block = Block(Properties()).setRegistryName(u"t:other")
    check(u"isBlock(Block) 异类为假", base.isBlock(other_block) is False)
    check(u"isBlock(BlockState) 异类为假",
          base.isBlock(other_block.defaultBlockState()) is False)
    check(u"isBlock(BlockState) 同类为真",
          base.isBlock(base) is True)
    check(u"非空气方块 isAir 为假", base.isAir() is False)

    block_mod.BLOCKS.clear()
    check(u"Blocks.AIR 的 isAir 为真",
          block_mod.BLOCKS.AIR.isAir() is True)

    check(u"toString 形态含方块名与属性",
          u"manaita.crafting_manaita" in base.toString()
          and u"facing" in base.toString(),
          base.toString())

    # ------------------------------------------------------------
    section("BlockProperties：链式设置")
    # ------------------------------------------------------------
    props = Properties.of().forceSolidOff()
    check(u"of() 得到 Properties", isinstance(props, Properties))
    check(u"forceSolidOff 返回自身且生效",
          props.isForceSolidOff() is True)

    chained = Properties.of().strength(3.0, 6.0).sound(block_mod.SoundType.WOOD) \
                             .noOcclusion() \
                             .requiresCorrectToolForDrops().lightLevel(7)
    check(u"strength 两参",
          (chained.getDestroyTime(), chained.getExplosionResistance())
          == (3.0, 6.0),
          (chained.getDestroyTime(), chained.getExplosionResistance()))
    check(u"strength 单参时爆炸抗性等于硬度",
          Properties.of().strength(2.5).getExplosionResistance() == 2.5)
    check(u"sound", chained.getSound() is block_mod.SoundType.WOOD)
    check(u"noOcclusion", chained.isNoOcclusion() is True)
    check(u"requiresCorrectToolForDrops",
          chained.isRequiresCorrectTool() is True)
    check(u"lightLevel", chained.getLightEmission() == 7)
    check(u"默认不发光", Properties.of().getLightEmission() == 0)

    check(u"ofFullCopy 拷贝",
          Properties.ofFullCopy(chained).getDestroyTime() == 3.0)
    check(u"ofFullCopy 是不同对象",
          Properties.ofFullCopy(chained) is not chained)

    check(u"Block 构造参数类型不对报错",
          raises(Block, u"not_properties"))

    # ------------------------------------------------------------
    section("Block：状态定义与物品形态")
    # ------------------------------------------------------------
    def_block = Block(Properties())
    check(u"无属性时默认状态为空",
          def_block.defaultBlockState().getProperties() == [])

    def_block.createBlockStateDefinition(BSP.OPEN, BSP.POWERED)
    check(u"定义了两个属性",
          len(def_block.getStateDefinition()) == 2,
          len(def_block.getStateDefinition()))
    check(u"重复定义属性报错",
          raises(def_block.createBlockStateDefinition, BSP.OPEN))
    check(u"非属性参数报错",
          raises(def_block.createBlockStateDefinition, u"not_prop"))

    check(u"getStateForPlacement 按名取值",
          def_block.getStateForPlacement(open=False).getValue(BSP.OPEN) is False)
    check(u"getStateForPlacement 名字错时报错",
          raises(def_block.getStateForPlacement, nope=True))

    # asItem
    check(u"未绑定物品时 asItem 返回 None",
          def_block.asItem() is None)
    block_item = item_mod.Item(item_mod.ItemProperties())
    def_block.setItem(block_item)
    check(u"绑定后 asItem 返回物品", def_block.asItem() is block_item)

    check(u"getDescriptionId 由注册名推导",
          def_block.setRegistryName(u"manaita:crafting").getDescriptionId()
          == u"block.manaita.crafting",
          def_block.getDescriptionId())
    check(u"未注册方块也有可读 id",
          Block(Properties()).getDescriptionId().startswith(u"block.unregistered."))

    # Block 的身份比较
    b1 = Block(Properties())
    b2 = Block(Properties())
    check(u"两个方块不相等", b1 != b2)
    check(u"自身相等", b1 == b1)
    check(u"可作字典键", {b1: u"v"}[b1] == u"v")

    # ------------------------------------------------------------
    section("BlockState.getDrops")
    # ------------------------------------------------------------
    drop_block = Block(Properties()).setRegistryName(u"t:dropper")
    drop_block.setItem(item_mod.Item(item_mod.ItemProperties()))
    drops = drop_block.defaultBlockState().getDrops()
    check(u"getDrops 返回一个物品栈", len(drops) == 1, len(drops))
    check(u"掉落物是绑定物品", drops[0].getItem() is drop_block.asItem())
    check(u"掉落数量为 1", drops[0].getCount() == 1)

    no_item_block = Block(Properties())
    check(u"没有物品形态时掉落为空",
          no_item_block.defaultBlockState().getDrops() == [])

    # ------------------------------------------------------------
    section("形状（与 shapes.py 联动）")
    # ------------------------------------------------------------
    shapes = pkg.load("minecraft.shapes")
    shaped = Block(Properties())
    shaped.setShape(shapes.VoxelShape.box(0.0, 0.0, 0.0, 16.0, 16.0, 16.0))
    check(u"getShape 返回设置的形状",
          shaped.getShape().size() == 1, shaped.getShape().size())
    check(u"默认形状占满整格（AABB，尺寸为 1）",
          Block(Properties()).getShape().getXSize() == 1.0,
          Block(Properties()).getShape().getXSize())
    check(u"默认形状的 Y 尺寸也是 1",
          Block(Properties()).getShape().getYSize() == 1.0)

    # ------------------------------------------------------------
    section("FluidState / SoundType")
    # ------------------------------------------------------------
    check(u"EMPTY 流体 isEmpty 为真",
          block_mod.FluidState().isEmpty() is True)
    check(u"水不是空流体",
          block_mod.FluidState(block_mod.FluidState.WATER).isEmpty() is False)
    check(u"is(流体质) 用安全名 isFluid",
          block_mod.FluidState(block_mod.FluidState.WATER)
          .isFluid(block_mod.FluidState.WATER) is True)
    check(u"isFluid 对不同流体为假",
          block_mod.FluidState(block_mod.FluidState.WATER)
          .isFluid(block_mod.FluidState.LAVA) is False)
    check(u"水源 isSource 为真",
          block_mod.FluidState(block_mod.FluidState.WATER, 8).isSource() is True)
    check(u"少量水不算源",
          block_mod.FluidState(block_mod.FluidState.WATER, 3).isSource() is False)
    check(u"getType", block_mod.FluidState(
        block_mod.FluidState.LAVA).getType() is block_mod.FluidState.LAVA)

    check(u"SoundType.WOOD 存在",
          block_mod.SoundType.WOOD.name() == u"WOOD")
    check(u"不同 SoundType 不等",
          block_mod.SoundType.WOOD is not block_mod.SoundType.STONE)

    # ------------------------------------------------------------
    section("BlockStateProperties 常量")
    # ------------------------------------------------------------
    check(u"HORIZONTAL_FACING 有 4 个朝向",
          BSP.HORIZONTAL_FACING.getValueCount() == 4,
          BSP.HORIZONTAL_FACING.getValueCount())
    check(u"FACING 有 6 个朝向", BSP.FACING.getValueCount() == 6)
    check(u"HORIZONTAL_FACING 不含 UP",
          raises(BSP.HORIZONTAL_FACING.getValue, u"up"))
    check(u"OPEN 是布尔属性", BSP.OPEN.getValueCount() == 2)
    check(u"AGE_0_25 是 26 个值", BSP.AGE_0_25.getValueCount() == 26,
          BSP.AGE_0_25.getValueCount())
    check(u"SLAB_TYPE 三个值", BSP.SLAB_TYPE.getValueCount() == 3)
    check(u"WATERLOGGED 存在", BSP.WATERLOGGED.getName() == u"waterlogged")

    # ------------------------------------------------------------
    section("Blocks 懒加载常量")
    # ------------------------------------------------------------
    block_mod.BLOCKS.clear()
    check(u"取 Blocks.STONE 得到 Block",
          isinstance(block_mod.BLOCKS.STONE, Block))
    check(u"同名始终同一对象",
          block_mod.BLOCKS.STONE is block_mod.BLOCKS.STONE)
    check(u"不同名是不同对象",
          block_mod.BLOCKS.STONE is not block_mod.BLOCKS.DIRT)
    check(u"Blocks.STONE 的 descriptionId 正确",
          block_mod.BLOCKS.STONE.getDescriptionId() == u"block.minecraft.stone",
          block_mod.BLOCKS.STONE.getDescriptionId())

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    expected = [
        "net.minecraft.world.level.block.Block",
        "net.minecraft.world.level.block.Blocks",
        "net.minecraft.world.level.block.state.BlockState",
        "net.minecraft.world.level.block.state.properties.Property",
        "net.minecraft.world.level.block.state.properties.BooleanProperty",
        "net.minecraft.world.level.block.state.properties.IntegerProperty",
        "net.minecraft.world.level.block.state.properties.EnumProperty",
        "net.minecraft.world.level.block.state.properties.BlockStateProperties",
        "net.minecraft.world.level.block.SoundType",
        "net.minecraft.world.level.material.FluidState",
    ]
    missing = [name for name in expected if name not in block_mod.JAVA_MAP]
    check(u"已实现的 θ 层方块类型都在映射表里", missing == [], missing)

    failures = []
    for java_name, impl in block_mod.JAVA_MAP.items():
        if not isinstance(impl, type) and not hasattr(impl, "__getattr__"):
            failures.append(u"{}: 映射目标不可用".format(java_name))
    check(u"映射目标都可用", failures == [], failures)

finally:
    mc.Component.clearTranslations()
    item_mod.ITEMS.clear()
    block_mod.BLOCKS.clear()

sys.exit(summary())

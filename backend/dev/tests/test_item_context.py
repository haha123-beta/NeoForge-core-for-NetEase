# -*- coding: utf-8 -*-
"""
θ/β 层自测：物品上下文 + 方块辅助类型 + ItemAbility

真实依据（逐字来自反编译源码）：

    // ItemAbility / ItemAbilities（共 13 个文件引用）
    public boolean canPerformAction(ItemStack stack, ItemAbility itemAbility) {
        return ItemAbilities.DEFAULT_AXE_ACTIONS.contains(itemAbility)
            || super.canPerformAction(stack, itemAbility);
    }
    BlockState.getToolModifiedState(UseOnContext, ItemAbilities.AXE_STRIP, false)

    // 物品上下文（引用次数：getLevel 21 / getPlayer 21 / getClickedPos 15 /
    //               getClickedFace 13 / getItemInHand 11 / canPlace 4 / getHand 2）
    public InteractionResult useOn(UseOnContext context)
    public BlockState getStateForPlacement(BlockPlaceContext context)
    BlockPos relative = blockpos.relative(blockplacecontext.getClickedFace());

    // 方块辅助类型
    return RenderShape.INVISIBLE;
    super(BlockTags.MINEABLE_WITH_AXE)
    state.is(BlockTags.MINEABLE_WITH_AXE)
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState>)

验证点：
  1. ItemAbility 的身份比较与集合 contains
  2. UseOnContext 的全部 getter
  3. BlockPlaceContext **继承** UseOnContext（类型检查要靠它）
  4. getClickedPos 的放置位置语义（可替换 vs 向外推一格）
  5. 三个枚举（RenderShape/Mirror/Rotation）的稳定性
  6. Rotation 的旋转运算
  7. StateDefinition.Builder
  8. TooltipFlag、BlockTags
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
block_mod = pkg.load("minecraft.block")
ctx_mod = pkg.load("minecraft.item_context")
extra = pkg.load("minecraft.block_extra")
common = pkg.load("neoforge.common")
access_mod = pkg.load("minecraft.level_access")
level_mod = pkg.load("minecraft.level")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    item_mod.ITEMS.clear()
    DIAMOND = item_mod.ITEMS.DIAMOND

    # ------------------------------------------------------------
    section("ItemAbility / ItemAbilities")
    # ------------------------------------------------------------
    Ability = common.ItemAbility
    Abilities = common.ItemAbilities

    check(u"AXE_STRIP 存在", Abilities.AXE_STRIP is not None)
    check(u"常量稳定", Abilities.AXE_STRIP is Abilities.AXE_STRIP)
    check(u"不同动作不同对象",
          Abilities.AXE_STRIP is not Abilities.AXE_SCRAPE)
    check(u"按身份比较",
          (Abilities.AXE_STRIP == Abilities.AXE_STRIP) is True)
    check(u"名字带命名空间",
          Abilities.AXE_STRIP.name() == u"neoforge:axe_strip",
          Abilities.AXE_STRIP.name())
    check(u"新建同名动作按名字相等",
          Ability(u"neoforge:axe_strip") == Abilities.AXE_STRIP)
    check(u"可作字典键",
          {Abilities.AXE_STRIP: 1}[Ability(u"neoforge:axe_strip")] == 1)

    # 真实用法：DEFAULT_AXE_ACTIONS.contains(itemAbility)
    axe_actions = Abilities.DEFAULT_AXE_ACTIONS
    check(u"DEFAULT_AXE_ACTIONS 有 4 项", axe_actions.size() == 4,
          axe_actions.size())
    check(u"contains 命中（剥皮）", axe_actions.contains(Abilities.AXE_STRIP))
    check(u"contains 命中（刮蜡）", axe_actions.contains(Abilities.AXE_WAX_OFF))
    check(u"contains 未命中（锄地）",
          axe_actions.contains(Abilities.HOE_TILL) is False)
    check(u"contains 未命中（铲平）",
          axe_actions.contains(Abilities.SHOVEL_FLATTEN) is False)
    check(u"支持 Python 的 in", Abilities.AXE_STRIP in axe_actions)
    check(u"可迭代", len(list(axe_actions)) == 4)

    # 模拟真实的 canPerformAction
    def can_perform_action(ability):
        return axe_actions.contains(ability)

    check(u"照真实写法判动作",
          can_perform_action(Abilities.AXE_STRIP) is True
          and can_perform_action(Abilities.HOE_TILL) is False)

    check(u"DEFAULT_SHOVEL_ACTIONS 有 2 项",
          Abilities.DEFAULT_SHOVEL_ACTIONS.size() == 2)
    check(u"DEFAULT_HOE_ACTIONS 有 2 项",
          Abilities.DEFAULT_HOE_ACTIONS.size() == 2)
    check(u"DEFAULT_SHEARS_ACTIONS 有 4 项",
          Abilities.DEFAULT_SHEARS_ACTIONS.size() == 4,
          Abilities.DEFAULT_SHEARS_ACTIONS.size())
    check(u"剪刀集合含 SHEARS_DIG",
          Abilities.DEFAULT_SHEARS_ACTIONS.contains(Abilities.SHEARS_DIG))
    check(u"各集合互不混淆",
          Abilities.DEFAULT_AXE_ACTIONS.contains(Abilities.SHEARS_DIG)
          is False)

    # ------------------------------------------------------------
    section("UseOnContext")
    # ------------------------------------------------------------
    UseOnContext = ctx_mod.UseOnContext
    BlockPlaceContext = ctx_mod.BlockPlaceContext

    access = access_mod.InMemoryLevelAccess()
    world = level_mod.Level.wrap(access)
    player = pkg.load("minecraft.entity").Player(access, name=u"测试玩家")
    held = item_mod.ItemStack(DIAMOND, 1)
    pos = mc.BlockPos(10, 64, 10)

    context = UseOnContext(
        level=world, player=player, hand=mc.InteractionHand.MAIN_HAND,
        item_in_hand=held, pos=pos, face=mc.Direction.UP,
        click_x=0.5, click_y=1.0, click_z=0.5)

    check(u"getLevel（真实 21 次）", context.getLevel() is world)
    check(u"getPlayer（真实 21 次）", context.getPlayer() is player)
    check(u"getClickedPos（真实 15 次）", context.getClickedPos() is pos)
    check(u"getClickedFace（真实 13 次）",
          context.getClickedFace() is mc.Direction.UP)
    check(u"getItemInHand（真实 11 次）", context.getItemInHand() is held)
    check(u"getHand（真实 2 次）",
          context.getHand() is mc.InteractionHand.MAIN_HAND)
    check(u"getClickLocation",
          context.getClickLocation() == (0.5, 1.0, 0.5),
          context.getClickLocation())

    # 默认值
    bare = UseOnContext()
    check(u"缺省手是主手", bare.getHand() is mc.InteractionHand.MAIN_HAND)
    check(u"缺省手持物是空栈", bare.getItemInHand().isEmpty() is True)
    check(u"缺省位置是原点", tuple(bare.getClickedPos()) == (0, 0, 0))
    check(u"缺省面是 UP", bare.getClickedFace() is mc.Direction.UP)
    check(u"getPlayer 可为 None", bare.getPlayer() is None)

    # 无玩家时的安全行为
    check(u"无玩家时 getHorizontalDirection 回退 NORTH",
          bare.getHorizontalDirection() is mc.Direction.NORTH)
    check(u"无玩家时 isSecondaryUseActive 为假",
          bare.isSecondaryUseActive() is False)

    # 潜行状态透传
    player.setShiftKeyDown(True)
    check(u"潜行时 isSecondaryUseActive 为真",
          context.isSecondaryUseActive() is True)
    player.setShiftKeyDown(False)

    # 水平朝向按 yaw 分段
    player.setYRot(0.0)
    check(u"yaw=0 朝南", context.getHorizontalDirection()
          is mc.Direction.SOUTH, context.getHorizontalDirection())
    player.setYRot(90.0)
    check(u"yaw=90 朝西", context.getHorizontalDirection()
          is mc.Direction.WEST, context.getHorizontalDirection())
    player.setYRot(0.0)

    check(u"toString 可读", u"UseOnContext" in context.toString(),
          context.toString())

    # ------------------------------------------------------------
    section("BlockPlaceContext：继承关系")
    # ------------------------------------------------------------
    # 关键：BlockPlaceContext **继承** UseOnContext ——
    # 真实代码把它传给形参是 UseOnContext 的方法，继承方向反了类型检查就不过。
    check(u"BlockPlaceContext 是 UseOnContext 的子类",
          issubclass(BlockPlaceContext, UseOnContext))
    place_context = BlockPlaceContext(level=world, player=player,
                                      item_in_hand=held, pos=pos,
                                      face=mc.Direction.UP)
    check(u"可以传给收 UseOnContext 的函数",
          isinstance(place_context, UseOnContext))
    check(u"继承来的 getLevel 可用", place_context.getLevel() is world)
    check(u"继承来的 getPlayer 可用", place_context.getPlayer() is player)
    check(u"继承来的 getClickedFace 可用",
          place_context.getClickedFace() is mc.Direction.UP)

    # ------------------------------------------------------------
    section("BlockPlaceContext：放置位置语义")
    # ------------------------------------------------------------
    # 点击的方块**不能**替换时，放置位置向外推一格
    check(u"不可替换时放置位置向外推一格",
          tuple(place_context.getClickedPos()) == (10, 65, 10),
          tuple(place_context.getClickedPos()))

    # 点击的方块**能**替换时，放置位置就是它本身
    place_context.setReplaceClicked(True)
    check(u"可替换时放置位置就是点击位置",
          tuple(place_context.getClickedPos()) == (10, 64, 10),
          tuple(place_context.getClickedPos()))
    check(u"canReplaceClicked 反映状态",
          place_context.canReplaceClicked() is True)
    check(u"replacingClickedOnBlock 同上",
          place_context.replacingClickedOnBlock() is True)

    # 直接指定放置位置
    place_context.setPlacementPos(mc.BlockPos(1, 2, 3))
    check(u"setPlacementPos 生效",
          tuple(place_context.getClickedPos()) == (1, 2, 3))

    # canPlace：按「放置位置是否为空」判断
    empty_context = BlockPlaceContext(level=world, player=player,
                                      item_in_hand=held,
                                      pos=mc.BlockPos(0, 0, 0),
                                      face=mc.Direction.UP)
    check(u"空位置 canPlace 为真", empty_context.canPlace() is True)

    stone = block_mod.Block(block_mod.BlockProperties()) \
        .setRegistryName(u"minecraft:stone")
    world.setBlock(mc.BlockPos(0, 1, 0), stone.defaultBlockState())
    check(u"目标位置有方块时 canPlace 为假（不可替换）",
          empty_context.canPlace() is False)

    empty_context.setReplaceClicked(True)
    check(u"标为可替换后 canPlace 为真", empty_context.canPlace() is True)

    check(u"没有世界时保守返回 True",
          BlockPlaceContext().canPlace() is True)

    # ------------------------------------------------------------
    section("RenderShape / Mirror / Rotation")
    # ------------------------------------------------------------
    RenderShape = extra.RenderShape
    check(u"MODEL 存在（真实代码用）", RenderShape.MODEL.name() == u"MODEL")
    check(u"INVISIBLE 存在", RenderShape.INVISIBLE.name() == u"INVISIBLE")
    check(u"常量稳定", RenderShape.MODEL is RenderShape.MODEL)
    check(u"不同形状不等", RenderShape.MODEL != RenderShape.INVISIBLE)
    check(u"values 有 3 个", len(RenderShape.values()) == 3)
    check(u"byName 命中", RenderShape.byName(u"model") is RenderShape.MODEL)
    check(u"byName 未命中抛异常", raises(RenderShape.byName, u"NOPE"))
    check(u"可作字典键", {RenderShape.MODEL: 1}[RenderShape.MODEL] == 1)

    Mirror = extra.Mirror
    check(u"Mirror 有 3 个", len(Mirror.values()) == 3)
    check(u"NONE/LEFT_RIGHT/FRONT_BACK 齐备",
          all(getattr(Mirror, n) is not None
              for n in (u"NONE", u"LEFT_RIGHT", u"FRONT_BACK")))
    check(u"mirror 运算：NONE 保持",
          Mirror.mirror(Mirror.NONE, None) is Mirror.NONE)
    check(u"mirror 运算：LEFT_RIGHT 与 FRONT_BACK 互换",
          Mirror.mirror(Mirror.LEFT_RIGHT, None) is Mirror.FRONT_BACK
          and Mirror.mirror(Mirror.FRONT_BACK, None) is Mirror.LEFT_RIGHT)

    Rotation = extra.Rotation
    check(u"Rotation 有 4 个", len(Rotation.values()) == 4)
    check(u"add：90+90=180",
          Rotation.add(Rotation.CLOCKWISE_90, Rotation.CLOCKWISE_90)
          is Rotation.CLOCKWISE_180)
    check(u"add：180+180=360 回到 NONE",
          Rotation.add(Rotation.CLOCKWISE_180, Rotation.CLOCKWISE_180)
          is Rotation.NONE)
    check(u"add：90+270=NONE",
          Rotation.add(Rotation.CLOCKWISE_90, Rotation.COUNTERCLOCKWISE_90)
          is Rotation.NONE)
    check(u"rotate 重复旋转",
          Rotation.rotate(Rotation.CLOCKWISE_90, 2)
          is Rotation.CLOCKWISE_180)
    check(u"rotate 0 次是 NONE",
          Rotation.rotate(Rotation.CLOCKWISE_90, 0) is Rotation.NONE)
    check(u"getRotated 等价于再转 90",
          Rotation.getRotated(Rotation.NONE) is Rotation.CLOCKWISE_90)

    # ------------------------------------------------------------
    section("DirectionProperty / StateDefinition")
    # ------------------------------------------------------------
    DirectionProperty = extra.DirectionProperty
    facing = DirectionProperty.create(u"facing")
    check(u"默认 4 个水平朝向", facing.getValueCount() == 4,
          facing.getValueCount())
    check(u"不含 UP", raises(facing.getValue, u"up"))
    check(u"含 NORTH", facing.getValue(u"north") is mc.Direction.NORTH)

    custom_facing = DirectionProperty.create(
        u"facing", mc.Direction.UP, mc.Direction.DOWN)
    check(u"可指定取值", custom_facing.getValueCount() == 2)

    builder = extra.StateDefinitionBuilder.of(u"某方块")
    returned = builder.add(facing)
    check(u"add 返回自身（可链式）", returned is builder)
    check(u"可加多个", builder.add(block_mod.BooleanProperty.create(u"open"))
          is builder)
    check(u"接受列表",
          extra.StateDefinitionBuilder().add(
              [block_mod.BooleanProperty.create(u"a"),
               block_mod.BooleanProperty.create(u"b")]) is not None)
    check(u"重复加同名属性报错",
          raises(extra.StateDefinitionBuilder().add(facing).add, facing))
    check(u"add(None) 报错", raises(extra.StateDefinitionBuilder().add, None))

    definition = builder.create()
    check(u"create 产出 StateDefinition",
          isinstance(definition, extra.StateDefinition))
    check(u"记录 2 个属性", definition.size() == 2, definition.size())
    check(u"按名字取属性", definition.getProperty(u"facing") is facing)
    check(u"hasProperty 判断",
          definition.hasProperty(u"open") is True
          and definition.hasProperty(u"lit") is False)
    check(u"getPropertyNames 排序",
          definition.getPropertyNames() == [u"facing", u"open"],
          definition.getPropertyNames())
    check(u"可迭代长度", len(definition) == 2)
    check(u"StateDefinition.Builder 内部类写法",
          extra.StateDefinition.Builder is extra.StateDefinitionBuilder)

    # ------------------------------------------------------------
    section("TooltipFlag")
    # ------------------------------------------------------------
    TooltipFlag = extra.TooltipFlag
    check(u"NORMAL 不是 advanced", TooltipFlag.NORMAL.isAdvanced() is False)
    check(u"ADVANCED 是 advanced", TooltipFlag.ADVANCED.isAdvanced() is True)
    check(u"of(True) 得到 advanced", TooltipFlag.of(True).isAdvanced() is True)
    check(u"名字正确", TooltipFlag.ADVANCED.name() == u"ADVANCED")
    check(u"相等语义",
          TooltipFlag.of(True) == TooltipFlag.ADVANCED
          and TooltipFlag.of(False) != TooltipFlag.ADVANCED)
    check(u"defaultValue 是 NORMAL",
          TooltipFlag.defaultValue().isAdvanced() is False)
    check(u"Default 内部枚举写法", TooltipFlag.Default is TooltipFlag)

    # ------------------------------------------------------------
    section("BlockTags")
    # ------------------------------------------------------------
    BlockTags = extra.BlockTags
    TagKey = pkg.load("minecraft.registries").TagKey

    check(u"MINEABLE_WITH_AXE 存在（真实代码用）",
          BlockTags.MINEABLE_WITH_AXE is not None)
    check(u"常量稳定",
          BlockTags.MINEABLE_WITH_AXE is BlockTags.MINEABLE_WITH_AXE)
    check(u"是 TagKey", isinstance(BlockTags.MINEABLE_WITH_AXE, TagKey))
    check(u"注册表是 block",
          BlockTags.MINEABLE_WITH_AXE.registry() == u"minecraft:block",
          BlockTags.MINEABLE_WITH_AXE.registry())
    check(u"位置名正确",
          BlockTags.MINEABLE_WITH_AXE.location()
          == u"minecraft:mineable/axe",
          BlockTags.MINEABLE_WITH_AXE.location())
    check(u"不同标签不等",
          BlockTags.MINEABLE_WITH_AXE != BlockTags.MINEABLE_WITH_HOE)
    check(u"INCORRECT_FOR_NETHERITE_TOOL 存在",
          BlockTags.INCORRECT_FOR_NETHERITE_TOOL is not None)
    check(u"LOGS 存在", BlockTags.LOGS is not None)

    # create：建**自定义**标签
    class FakeLocation(object):
        def toString(self):
            return u"manaita_plus_legacy:mineable"

    custom = BlockTags.create(FakeLocation())
    check(u"BlockTags.create 建自定义标签",
          custom.location() == u"manaita_plus_legacy:mineable",
          custom.location())
    check(u"自定义标签仍在 block 注册表",
          custom.registry() == u"minecraft:block")

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.world.item.context.UseOnContext",
        "net.minecraft.world.item.context.BlockPlaceContext",
    ):
        check(u"item_context 映射 {}".format(java_name),
              java_name in ctx_mod.JAVA_MAP)

    for java_name in (
        "net.minecraft.world.level.block.RenderShape",
        "net.minecraft.world.level.block.Mirror",
        "net.minecraft.world.level.block.Rotation",
        "net.minecraft.world.level.block.state.StateDefinition",
        "net.minecraft.world.level.block.state.StateDefinition$Builder",
        "net.minecraft.world.level.block.state.properties.DirectionProperty",
        "net.minecraft.world.item.TooltipFlag",
        "net.minecraft.tags.BlockTags",
    ):
        check(u"block_extra 映射 {}".format(java_name),
              java_name in extra.JAVA_MAP)

    for java_name in (
        "net.neoforged.neoforge.common.ItemAbility",
        "net.neoforged.neoforge.common.ItemAbilities",
    ):
        check(u"common 映射 {}".format(java_name), java_name in common.JAVA_MAP)

finally:
    item_mod.ITEMS.clear()
    block_mod.BLOCKS.clear()
    level_mod.Level.resetWrappers()

sys.exit(summary())

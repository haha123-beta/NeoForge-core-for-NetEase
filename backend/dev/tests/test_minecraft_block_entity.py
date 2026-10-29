# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/block_entity.py（方块实体与容器）

真实依据（逐字来自反编译源码）：
    // 注册
    BLOCK_ENTITY_TYPES.register("furnace_block_entity",
        () -> BlockEntityType.Builder.of(FurnaceBlockEntity::new,
                                         new Block[]{ FurnaceBlock.get() })
                                     .build(null));

    // 基类与接口
    public class ManaitaPlusBrewingStandBlockEntity
            extends BaseContainerBlockEntity implements WorldlyContainer {
        private NonNullList<ItemStack> items = NonNullList.withSize(5, ItemStack.EMPTY);
        public int getContainerSize() { return 5; }
        protected NonNullList<ItemStack> getItems() { return this.items; }
        protected void setItems(NonNullList<ItemStack> items) { this.items = items; }
        public boolean canPlaceItem(int index, ItemStack stack) {...}
        public int[] getSlotsForFace(Direction side) {...}
        protected AbstractContainerMenu createMenu(int id, Inventory player) {...}
        protected void loadAdditional(CompoundTag tag, HolderLookup.Provider r) {
            super.loadAdditional(tag, r);
            ContainerHelper.loadAllItems(tag, this.items, r);
        }
    }

    // 方块侧：客户端返回 null
    return level.isClientSide ? null : createTickerHelper(...);

验证点：
  1. NonNullList 的定长与越界
  2. Container 接口的默认实现（removeItem / clearContent）
  3. BaseContainerBlockEntity 的钩子分工（getItems/setItems）
  4. ContainerHelper 的存档往返（只存非空、越界跳过）
  5. BlockEntityType.Builder 与 isValid
  6. BlockEntityTicker
  7. 端到端：照真实写法做一个带 5 个槽位的酿造台方块实体
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
block_mod = pkg.load("minecraft.block")
be = pkg.load("minecraft.block_entity")
reg = pkg.load("minecraft.registries")
nbt = pkg.load("minecraft.nbt")

NonNullList = be.NonNullList
Container = be.Container
ItemStack = item_mod.ItemStack


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("NonNullList：定长槽位")
    # ------------------------------------------------------------
    slots = NonNullList.withSize(5, ItemStack.EMPTY)
    check(u"withSize 得到 5 个槽位", slots.size() == 5, slots.size())
    check(u"槽位默认是空栈", slots.get(0).isEmpty() is True)
    check(u"固定长度5的列表不是空列表", slots.isEmpty() is False)
    check(u"越界取值报错", raises(slots.get, 5))
    check(u"越界设值报错", raises(slots.set, 5, ItemStack()))
    check(u"负数索引报错", raises(slots.get, -1))

    item_mod.ITEMS.clear()
    diamond = item_mod.ITEMS.DIAMOND
    slots.set(2, ItemStack(diamond, 3))
    check(u"set 生效", slots.get(2).getCount() == 3, slots.get(2).getCount())
    check(u"不再为空", slots.isEmpty() is False)

    # clear 清空但**不改变长度** —— 槽位结构不能变
    slots.clear()
    check(u"clear 后长度不变", slots.size() == 5, slots.size())
    check(u"clear 后仍为非空列表", slots.isEmpty() is False)
    check(u"clear 后恢复默认空栈", slots.get(0) is ItemStack.EMPTY)

    check(u"create 得到空列表", NonNullList.create().size() == 0)
    check(u"可迭代", len(list(NonNullList.withSize(3, ItemStack.EMPTY))) == 3)
    check(u"toList 导出", len(NonNullList.withSize(3, ItemStack.EMPTY).toList()) == 3)

    # ------------------------------------------------------------
    section("Container：默认实现")
    # ------------------------------------------------------------
    class SimpleContainer(Container):
        def __init__(self, size=3):
            self._items = NonNullList.withSize(size, ItemStack())

        def getContainerSize(self):
            return self._items.size()

        def getItem(self, index):
            return self._items.get(index)

        def setItem(self, index, stack):
            self._items.set(index, stack)
            return None

        def isEmpty(self):
            return all(stack.isEmpty() for stack in self._items)

    container = SimpleContainer(3)
    check(u"初始为空", container.isEmpty() is True)

    container.setItem(0, ItemStack(diamond, 10))
    check(u"放入后非空", container.isEmpty() is False)
    check(u"getContainerSize", container.getContainerSize() == 3)

    # removeItem：取出并减少数量
    taken = container.removeItem(0, 4)
    check(u"removeItem 返回取出的栈", taken.getCount() == 4, taken.getCount())
    check(u"removeItem 减少原栈", container.getItem(0).getCount() == 6,
          container.getItem(0).getCount())
    check(u"取出的是同一个物品", taken.getItem() is diamond)

    # 取超过持有量只取现有的
    taken2 = container.removeItem(0, 100)
    check(u"超量取出只拿到现有的", taken2.getCount() == 6, taken2.getCount())
    check(u"原栈被清空", container.getItem(0).isEmpty() is True)

    # 从空槽取出得到空栈
    empty_taken = container.removeItem(1, 5)
    check(u"从空槽取出得到空栈", empty_taken.isEmpty() is True)

    container.setItem(0, ItemStack(diamond, 2))
    container.setItem(1, ItemStack(diamond, 3))
    container.clearContent()
    check(u"clearContent 清空所有槽位", container.isEmpty() is True)

    check(u"默认 canPlaceItem 为真",
          container.canPlaceItem(0, ItemStack(diamond, 1)) is True)
    check(u"默认 stillValid 为真", container.stillValid(u"玩家") is True)
    check(u"setChanged 不报错", container.setChanged() is None)
    check(u"startOpen/stopOpen 不报错",
          container.startOpen(u"玩家") is None
          and container.stopOpen(u"玩家") is None)

    # 抽象方法必须由子类实现
    check(u"未实现 getContainerSize 抛 NotImplementedError",
          raises(Container().getContainerSize))

    # ------------------------------------------------------------
    section("WorldlyContainer：按面限制")
    # ------------------------------------------------------------
    class FacedContainer(SimpleContainer, be.WorldlyContainer):
        SLOTS_FOR_UP = (3,)
        SLOTS_FOR_DOWN = (0, 1, 2, 3)
        SLOTS_FOR_SIDES = (0, 1, 2, 4)

        def __init__(self):
            SimpleContainer.__init__(self, 5)

        def getSlotsForFace(self, side):
            name = side.name() if hasattr(side, "name") else u"?"
            if name == u"UP":
                return list(self.SLOTS_FOR_UP)
            if name == u"DOWN":
                return list(self.SLOTS_FOR_DOWN)
            return list(self.SLOTS_FOR_SIDES)

    faced = FacedContainer()
    check(u"UP 面只能进第 3 格",
          faced.getSlotsForFace(mc.Direction.UP) == [3],
          faced.getSlotsForFace(mc.Direction.UP))
    check(u"DOWN 面有 4 格",
          faced.getSlotsForFace(mc.Direction.DOWN) == [0, 1, 2, 3])
    check(u"侧面有 4 格（不含 3）",
          faced.getSlotsForFace(mc.Direction.NORTH) == [0, 1, 2, 4],
          faced.getSlotsForFace(mc.Direction.NORTH))

    # ------------------------------------------------------------
    section("BaseContainerBlockEntity：钩子分工")
    # ------------------------------------------------------------
    class BrewingEntity(be.BaseContainerBlockEntity):
        """照真实代码的形态：只管物品列表，其余交给基类。"""

        SIZE = 5
        INGREDIENT_SLOT = 3
        FUEL_SLOT = 4

        def __init__(self, pos=None, state=None):
            be.BaseContainerBlockEntity.__init__(self, None, pos, state)
            self._items = NonNullList.withSize(self.SIZE, ItemStack())
            self.data = [0]

        def getItems(self):
            return self._items

        def setItems(self, items):
            self._items = items
            return None

        def getContainerSize(self):
            return self.SIZE

        def getDefaultName(self):
            return mc.Component.literal(u"酿造台")

        def canPlaceItem(self, index, stack):
            # 真实代码：燃料槽只收燃料、原料槽只收原料
            if index == self.FUEL_SLOT:
                return stack.isItem(item_mod.ITEMS.BLAZE_POWDER)
            if index == self.INGREDIENT_SLOT:
                return not stack.isItem(item_mod.ITEMS.DIAMOND)
            return True

    entity = BrewingEntity(mc.BlockPos(1, 2, 3))
    check(u"getContainerSize", entity.getContainerSize() == 5)
    check(u"getItem 走基类", entity.getItem(0).isEmpty() is True)
    check(u"isEmpty 走基类", entity.isEmpty() is True)
    check(u"getDisplayName 用 getDefaultName",
          entity.getDisplayName().getString() == u"酿造台",
          entity.getDisplayName().getString())

    entity.setItem(0, ItemStack(diamond, 7))
    check(u"setItem 写进物品列表", entity.getItems().get(0).getCount() == 7,
          entity.getItems().get(0).getCount())
    check(u"不再为空", entity.isEmpty() is False)

    check(u"canPlaceItem 燃料槽只收烈焰粉",
          entity.canPlaceItem(4, ItemStack(item_mod.ITEMS.BLAZE_POWDER, 1))
          is True
          and entity.canPlaceItem(4, ItemStack(diamond, 1)) is False)
    check(u"canPlaceItem 原料槽拒收钻石",
          entity.canPlaceItem(3, ItemStack(diamond, 1)) is False
          and entity.canPlaceItem(3, ItemStack(item_mod.ITEMS.EMERALD, 1))
          is True)
    check(u"其他槽位不限",
          entity.canPlaceItem(0, ItemStack(diamond, 1)) is True)

    # 方块实体基础行为
    check(u"getBlockPos", tuple(entity.getBlockPos()) == (1, 2, 3))
    check(u"初始未移除", entity.isRemoved() is False)
    entity.setRemoved()
    check(u"setRemoved 生效", entity.isRemoved() is True)
    entity.clearRemoved()
    check(u"clearRemoved 生效", entity.isRemoved() is False)
    check(u"getLevel 默认为 None", entity.getLevel() is None)
    check(u"setLevel 可设", entity.setLevel(u"某世界") is None)
    check(u"setChanged 不报错", entity.setChanged() is None)

    # 未实现钩子要报错
    bare = be.BaseContainerBlockEntity()
    check(u"未实现 getItems 抛异常", raises(bare.getItems))
    check(u"未实现 setItems 抛异常", raises(bare.setItems, None))

    # ------------------------------------------------------------
    section("ContainerHelper：存档往返")
    # ------------------------------------------------------------
    tag = nbt.CompoundTag()
    source = NonNullList.withSize(5, ItemStack())
    source.set(0, ItemStack(diamond, 12))
    source.set(3, ItemStack(item_mod.ITEMS.EMERALD, 4))

    be.ContainerHelper.saveAllItems(tag, source)
    entries = tag.getList(be.ContainerHelper.ITEMS_KEY)
    check(u"存进 Items 键", isinstance(entries, list), type(entries).__name__)
    # 只存非空槽位 —— 空槽存进去只会让存档变大
    check(u"只存了 2 个非空槽位", len(entries) == 2, len(entries))
    check(u"记录槽位号", entries[0][u"Slot"] == 0 and entries[1][u"Slot"] == 3,
          [e[u"Slot"] for e in entries])
    check(u"记录数量", entries[0][u"count"] == 12, entries[0])
    check(u"存的是 CompoundTag（真实类型）",
          isinstance(tag, nbt.CompoundTag), type(tag).__name__)

    restored = NonNullList.withSize(5, ItemStack())
    be.ContainerHelper.loadAllItems(tag, restored)
    check(u"读回后槽位 0 非空", restored.get(0).isEmpty() is False)
    check(u"读回后数量正确", restored.get(0).getCount() == 12,
          restored.get(0).getCount())
    check(u"读回后槽位 3 也有", restored.get(3).getCount() == 4)
    check(u"空槽位保持为空", restored.get(1).isEmpty() is True)
    check(u"未解析的栈能看出 id",
          restored.get(0).getRestoredId()
          == u"minecraft:diamond",
          restored.get(0).getRestoredId())

    # 越界槽位号要跳过而不是崩 —— 旧存档可能来自槽位更多的版本
    bad_tag = nbt.CompoundTag()
    bad_tag.putList(be.ContainerHelper.ITEMS_KEY, [
        {u"Slot": 99, u"id": u"minecraft:stone", u"count": 1},
        {u"Slot": 1, u"id": u"minecraft:dirt", u"count": 2},
    ])
    target = NonNullList.withSize(5, ItemStack())
    be.ContainerHelper.loadAllItems(bad_tag, target)
    check(u"越界槽位被跳过而不是抛异常",
          target.get(1).isEmpty() is False, target.get(1))
    check(u"跳过后没有污染别的槽位", target.get(0).isEmpty() is True)

    check(u"tag 为 None 时 saveAllItems 报错",
          raises(be.ContainerHelper.saveAllItems, None, source))
    check(u"tag 为 None 时 loadAllItems 安全",
          be.ContainerHelper.loadAllItems(None, source) is None)
    check(u"没有 Items 键时不动数据",
          be.ContainerHelper.loadAllItems(nbt.CompoundTag(), target) is None)

    # 方块实体级别的存档往返
    save_entity = BrewingEntity()
    save_entity.setItem(0, ItemStack(diamond, 5))
    save_entity.setItem(4, ItemStack(item_mod.ITEMS.BLAZE_POWDER, 2))
    save_tag = nbt.CompoundTag()
    save_entity.saveAdditional(save_tag)
    check(u"方块实体全部存下来",
          len(save_tag.getList(be.ContainerHelper.ITEMS_KEY)) == 2,
          len(save_tag.getList(be.ContainerHelper.ITEMS_KEY)))

    load_entity = BrewingEntity()
    load_entity.loadAdditional(save_tag)
    check(u"读回后数量一致", load_entity.getItem(0).getCount() == 5,
          load_entity.getItem(0).getCount())
    # 关键：读存档前要先把物品列表整成同样大小，否则旧存档会错位
    check(u"读回后槽位数与当前版本一致",
          load_entity.getItems().size() == 5,
          load_entity.getItems().size())

    update_tag = save_entity.getUpdateTag()
    check(u"getUpdateTag 返回 CompoundTag",
          isinstance(update_tag, nbt.CompoundTag), type(update_tag).__name__)
    check(u"getUpdateTag 含物品数据",
          update_tag.contains(be.ContainerHelper.ITEMS_KEY), update_tag)

    # ------------------------------------------------------------
    section("BlockEntityType")
    # ------------------------------------------------------------
    furnace_block = block_mod.Block(block_mod.BlockProperties()) \
        .setRegistryName(u"t:furnace")
    other_block = block_mod.Block(block_mod.BlockProperties()) \
        .setRegistryName(u"t:other")

    bet = be.BlockEntityType.Builder.of(
        lambda pos, state: BrewingEntity(pos, state),
        [furnace_block]).build(None)

    check(u"Builder.of + build 产出 BlockEntityType",
          isinstance(bet, be.BlockEntityType))
    check(u"记录绑定的方块",
          bet.getBlocks() == [furnace_block], bet.getBlocks())
    check(u"isValid 对绑定方块为真",
          bet.isValid(furnace_block.defaultBlockState()) is True)
    check(u"isValid 对其他方块为假",
          bet.isValid(other_block.defaultBlockState()) is False)

    created = bet.create(mc.BlockPos(4, 5, 6),
                         furnace_block.defaultBlockState())
    check(u"create 造出方块实体", isinstance(created, BrewingEntity))
    check(u"create 绑定了位置", tuple(created.getBlockPos()) == (4, 5, 6))
    check(u"create 绑定了状态",
          created.getBlockState() is not None)

    check(u"Builder.of 接受单个方块（不是列表）",
          len(be.BlockEntityType.Builder.of(lambda p, s: None,
                                            furnace_block).build().getBlocks())
          == 1)
    check(u"Builder.of 没有方块也可以",
          be.BlockEntityType.Builder.of(lambda p, s: None).build() is not None)
    check(u"BlockEntityType.Builder 内部类写法",
          be.BlockEntityType.Builder is be.BlockEntityTypeBuilder)
    check(u"缺工厂报错", raises(be.BlockEntityType, None))

    # ------------------------------------------------------------
    section("BlockEntityTicker")
    # ------------------------------------------------------------
    tick_log = []

    def server_tick(level, pos, state, block_entity):
        tick_log.append(tuple(pos))

    ticker = be.BlockEntityTicker(server_tick)
    ticker.tick(u"世界", mc.BlockPos(1, 1, 1), u"状态", entity)
    check(u"tick 调用被转发", tick_log == [(1, 1, 1)], tick_log)
    check(u"tick 次数被记录", ticker.tick_count == 1)
    check(u"of 工厂", isinstance(be.BlockEntityTicker.of(server_tick),
                                 be.BlockEntityTicker))
    check(u"缺函数报错", raises(be.BlockEntityTicker, None))

    # ------------------------------------------------------------
    section("端到端：注册一个方块实体类型（照真实写法）")
    # ------------------------------------------------------------
    # 对应 ManaitaPlusLegacyBlockEntityCore：
    #   BLOCK_ENTITY_TYPES.register("furnace_block_entity",
    #       () -> BlockEntityType.Builder.of(FurnaceBlockEntity::new,
    #                                        new Block[]{...}).build(null))
    bus = pkg.load("neoforge.event").IEventBus(u"manaita_plus_legacy")
    registries_mod = pkg.load("neoforge.registries")
    entity_register = registries_mod.DeferredRegister.create(
        registries_mod.BUILT_IN_REGISTRIES.BLOCK_ENTITY_TYPE,
        u"manaita_plus_legacy")

    holder = entity_register.register(
        u"furnace_block_entity",
        lambda: be.BlockEntityType.Builder.of(
            lambda pos, state: BrewingEntity(pos, state),
            [furnace_block]).build(None))

    check(u"注册得到 DeferredHolder", isinstance(holder,
                                                 registries_mod.DeferredHolder))
    check(u"Holder remains unbound before registration", not holder.isBound())
    entity_register.freeze_and_register(registries_mod.BUILT_IN_REGISTRIES.BLOCK_ENTITY_TYPE)

    created_type = holder.get()
    check(u"取到的是 BlockEntityType",
          isinstance(created_type, be.BlockEntityType))
    check(u"注册的类型认识它的方块",
          created_type.isValid(furnace_block.defaultBlockState()) is True)

    # 用刚注册的类型造方块实体（走完整链路）
    spawned = created_type.create(mc.BlockPos(0, 64, 0),
                                  furnace_block.defaultBlockState())
    check(u"用注册的类型造出方块实体", isinstance(spawned, BrewingEntity))

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.core.NonNullList",
        "net.minecraft.world.Container",
        "net.minecraft.world.level.block.entity.BlockEntity",
        "net.minecraft.world.level.block.entity.BaseContainerBlockEntity",
        "net.minecraft.world.level.block.entity.BlockEntityType",
        "net.minecraft.world.level.block.entity.BlockEntityType$Builder",
        "net.minecraft.world.level.block.entity.BlockEntityTicker",
        "net.minecraft.world.level.block.entity.ContainerHelper",
        "net.minecraft.world.WorldlyContainer",
    ):
        check(u"映射 {}".format(java_name), java_name in be.JAVA_MAP)

finally:
    item_mod.ITEMS.clear()
    block_mod.BLOCKS.clear()

sys.exit(summary())

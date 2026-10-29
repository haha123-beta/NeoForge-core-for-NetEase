# -*- coding: utf-8 -*-
"""
θ 层自测：nbt.py + menu.py + util.py

真实依据（逐字来自反编译源码）：
    // NBT（9 个文件引用）
    public PreventDropPacket(int current, CompoundTag tag)
    er.setTag(stack, (CompoundTag) payload.tag);
    protected void loadAdditional(CompoundTag tag, HolderLookup.Provider registries)

    // 菜单
    DeferredRegister.create(BuiltInRegistries.MENU, "manaita_plus_legacy")
    event.register(MENU_CRAFTING.get(), CraftingManaitaScreen::new);
    player.openMenu(state.getMenuProvider(level, pos));
    protected AbstractContainerMenu createMenu(int id, Inventory player)
    protected final ContainerData dataAccess = new ...;
    Containers.dropContents(level, pos, container);

    // 工具
    int l = Mth.clamp((18 * k + 20 - 1) / 20, 0, 18);
    int totalXp = Mth.floor(craftedCount * xpPerItem);
    float fractional = Mth.frac(craftedCount * xpPerItem);
    RandomSource randomsource = RandomSource.create(seed);
    if (hitResult.getType() != HitResult.Type.MISS)
    if (hitResult instanceof BlockHitResult) { ... }
    return InteractionResultHolder.pass(itemstack);
    Component.literal(I18n.get("block.brewing." + x));

验证点：
  1. CompoundTag 的类型保真（byte 与 int 分得清）
  2. CompoundTag 的嵌套读法不 NPE（getCompound 返回空表而不是 None）
  3. Mth.floor 与 int() 的区别（负数）、clamp 的参数顺序
  4. RandomSource 同种子同序列
  5. HitResult 的类型层次与 instanceof 等价
  6. InteractionResultHolder 的四个工厂（含避开 pass 关键字）
  7. I18n 与 Component 共用翻译表
  8. 菜单/槽位/ContainerData/Containers
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
nbt = pkg.load("minecraft.nbt")
menu_mod = pkg.load("minecraft.menu")
util = pkg.load("minecraft.util")
be = pkg.load("minecraft.block_entity")
access_mod = pkg.load("minecraft.level_access")
level_mod = pkg.load("minecraft.level")

CompoundTag = nbt.CompoundTag


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    item_mod.ITEMS.clear()
    DIAMOND = item_mod.ITEMS.DIAMOND
    DIRT = item_mod.ITEMS.DIRT

    # ------------------------------------------------------------
    section("CompoundTag：类型保真")
    # ------------------------------------------------------------
    tag = CompoundTag()
    check(u"初始为空", tag.isEmpty() is True)
    check(u"size 为 0", tag.size() == 0)

    tag.putByte(u"tiny", 5)
    tag.putInt(u"count", 5)
    # 关键：byte 与 int 的 Python 值都是 5，但 NBT 类型必须分得清
    check(u"byte 记录了类型", tag.getTagType(u"tiny") == nbt.TagType.BYTE,
          tag.getTagType(u"tiny"))
    check(u"int 记录了类型", tag.getTagType(u"count") == nbt.TagType.INT,
          tag.getTagType(u"count"))
    check(u"两者类型不同",
          tag.getTagType(u"tiny") != tag.getTagType(u"count"))
    check(u"但取值都是 5",
          tag.getByte(u"tiny") == 5 and tag.getInt(u"count") == 5)

    check(u"containsTyped 判定类型",
          tag.containsTyped(u"tiny", nbt.TagType.BYTE) is True
          and tag.containsTyped(u"tiny", nbt.TagType.INT) is False)
    check(u"contains 不看类型", tag.contains(u"tiny") is True)
    check(u"size 为 2", tag.size() == 2)

    # ------------------------------------------------------------
    section("CompoundTag：各类型读写")
    # ------------------------------------------------------------
    tag.putLong(u"big", 1234567890123)
    tag.putFloat(u"ratio", 1.5)
    tag.putDouble(u"precise", 2.25)
    tag.putString(u"name", u"砧板")
    tag.putBoolean(u"flag", True)
    tag.putIntArray(u"coords", [1, 2, 3])

    check(u"getLong", tag.getLong(u"big") == 1234567890123)
    check(u"getFloat", tag.getFloat(u"ratio") == 1.5)
    check(u"getDouble", tag.getDouble(u"precise") == 2.25)
    check(u"getString 支持非 ASCII", tag.getString(u"name") == u"砧板",
          tag.getString(u"name"))
    check(u"getBoolean", tag.getBoolean(u"flag") is True)
    check(u"getIntArray", tag.getIntArray(u"coords") == [1, 2, 3])
    check(u"布尔存成 byte",
          tag.getTagType(u"flag") == nbt.TagType.BYTE, tag.getTagType(u"flag"))

    # 缺键的默认值 —— 与 Java 一致：数值归 0、字符串归空串
    check(u"缺键 getInt 返回 0", tag.getInt(u"missing") == 0)
    check(u"缺键 getString 返回空串", tag.getString(u"missing") == u"")
    check(u"缺键 getBoolean 返回假", tag.getBoolean(u"missing") is False)
    check(u"缺键 get 返回 None", tag.get(u"missing") is None)

    # ------------------------------------------------------------
    section("CompoundTag：嵌套不 NPE")
    # ------------------------------------------------------------
    # 关键：getCompound 在缺键时返回**空 CompoundTag** 而不是 None，
    # 这样 `tag.getCompound("a").getInt("b")` 这种链式读法不会挂。
    check(u"缺键的 getCompound 返回空表而不是 None",
          isinstance(tag.getCompound(u"nothing"), CompoundTag))
    check(u"空表上的链式读法安全",
          tag.getCompound(u"nothing").getInt(u"deeper") == 0)

    inner = CompoundTag()
    inner.putInt(u"level", 3)
    tag.putCompound(u"nested", inner)
    check(u"嵌套读法", tag.getCompound(u"nested").getInt(u"level") == 3)
    check(u"嵌套类型是 compound",
          tag.getTagType(u"nested") == nbt.TagType.COMPOUND)
    check(u"putCompound 类型不对报错",
          raises(tag.putCompound, u"bad", u"not_a_tag"))

    # merge：嵌套递归合并
    other = CompoundTag()
    other.putInt(u"level", 9)
    other.putString(u"extra", u"新字段")
    tag.getCompound(u"nested").merge(other)
    check(u"merge 覆盖同名键",
          tag.getCompound(u"nested").getInt(u"level") == 9)
    check(u"merge 加入新键",
          tag.getCompound(u"nested").getString(u"extra") == u"新字段")
    check(u"merge 类型不对报错", raises(tag.merge, u"nope"))

    # copy 是深拷贝
    copied = tag.copy()
    check(u"copy 相等", copied.equals(tag))
    copied.getCompound(u"nested").putInt(u"level", 100)
    check(u"copy 是深拷贝（改副本不影响原本）",
          tag.getCompound(u"nested").getInt(u"level") == 9,
          tag.getCompound(u"nested").getInt(u"level"))

    # remove / 相等
    tag.remove(u"tiny")
    check(u"remove 生效", tag.contains(u"tiny") is False)
    check(u"remove 不存在的键不报错", tag.remove(u"never_existed") is None)
    check(u"相等语义",
          CompoundTag().equals(CompoundTag()) is True)
    a = CompoundTag()
    a.putByte(u"x", 1)
    b = CompoundTag()
    b.putInt(u"x", 1)
    check(u"值同类型不同则不等（类型保真的意义）", a == b is False or a != b)

    check(u"getAllKeys 保留插入顺序",
          tag.getAllKeys()[:2] == [u"count", u"big"],
          tag.getAllKeys()[:2])
    check(u"可直接当字典用",
          tag[u"name"] == u"砧板" and u"name" in tag and len(tag) > 0)
    tag[u"direct"] = 1
    check(u"下标赋值可用", tag.getInt(u"direct") == 1)
    check(u"toString 可读", u"name" in tag.toString(), tag.toString()[:60])

    check(u"类型推断：int", nbt.TagType.of(1) == nbt.TagType.INT)
    check(u"类型推断：float", nbt.TagType.of(1.0) == nbt.TagType.DOUBLE)
    check(u"类型推断：bool 归 byte",
          nbt.TagType.of(True) == nbt.TagType.BYTE)
    check(u"类型推断：str", nbt.TagType.of(u"x") == nbt.TagType.STRING)
    check(u"类型推断：list", nbt.TagType.of([1]) == nbt.TagType.LIST)

    # ListTag
    lt = nbt.ListTag([1, 2])
    lt.add(3)
    check(u"ListTag 的 Java 风格方法",
          lt.size() == 3 and lt.get(0) == 1 and len(list(lt)) == 3)

    # ------------------------------------------------------------
    section("与 ContainerHelper 的联动（真实类型）")
    # ------------------------------------------------------------
    source = be.NonNullList.withSize(3, item_mod.ItemStack())
    source.set(1, item_mod.ItemStack(DIAMOND, 7))
    real_tag = CompoundTag()
    be.ContainerHelper.saveAllItems(real_tag, source)
    check(u"存档进 CompoundTag",
          real_tag.contains(be.ContainerHelper.ITEMS_KEY))
    target = be.NonNullList.withSize(3, item_mod.ItemStack())
    be.ContainerHelper.loadAllItems(real_tag, target)
    check(u"从 CompoundTag 读回", target.get(1).getCount() == 7,
          target.get(1).getCount())

    # ------------------------------------------------------------
    section("Mth：负数取整与参数顺序")
    # ------------------------------------------------------------
    Mth = util.Mth
    # 关键：Mth.floor 是**向下**取整，与 Python 的 int() 不同
    check(u"floor 正数", Mth.floor(1.9) == 1)
    check(u"floor 负数向下（-0.5 -> -1）", Mth.floor(-0.5) == -1,
          Mth.floor(-0.5))
    check(u"与 int() 的区别", Mth.floor(-0.5) != int(-0.5),
          (Mth.floor(-0.5), int(-0.5)))
    check(u"ceil", Mth.ceil(1.1) == 2 and Mth.ceil(-1.1) == -1)

    # 关键：clamp 的参数顺序是 (值, 下限, 上限)
    check(u"clamp 正常", Mth.clamp(5, 0, 10) == 5)
    check(u"clamp 低于下限", Mth.clamp(-1, 0, 10) == 0)
    check(u"clamp 高于上限", Mth.clamp(99, 0, 10) == 10)
    check(u"clamp 上限小于下限时返回下限", Mth.clamp(5, 10, 0) == 10,
          Mth.clamp(5, 10, 0))
    check(u"clampInt", Mth.clampInt(3.7, 0, 3) == 3)

    # frac 与 floor 配对使用（真实代码拆整数+小数）
    value = 3.75
    check(u"frac 正数", abs(Mth.frac(value) - 0.75) < 1e-9)
    check(u"floor + frac 还原原值",
          abs(Mth.floor(value) + Mth.frac(value) - value) < 1e-9)
    check(u"frac 负数也是正的（-1.25 -> 0.75）",
          abs(Mth.frac(-1.25) - 0.75) < 1e-9, Mth.frac(-1.25))

    check(u"sin 参数是角度", abs(Mth.sin(90) - 1.0) < 1e-9, Mth.sin(90))
    check(u"cos 参数是角度", abs(Mth.cos(0) - 1.0) < 1e-9)
    check(u"atan2 返回角度", abs(Mth.atan2(1.0, 0.0) - 90.0) < 1e-9)
    check(u"lerp 的参数顺序是 (delta, start, end)",
          Mth.lerp(0.5, 0.0, 10.0) == 5.0)
    check(u"positiveModulo 结果非负",
          Mth.positiveModulo(-1, 5) == 4, Mth.positiveModulo(-1, 5))
    check(u"positiveModulo 正常情况", Mth.positiveModulo(7, 5) == 2)
    check(u"square", Mth.square(3) == 9)
    check(u"sqrt", Mth.sqrt(16.0) == 4.0)

    # ------------------------------------------------------------
    section("RandomSource：同种子同序列")
    # ------------------------------------------------------------
    RandomSource = util.RandomSource
    a = RandomSource.create(12345)
    b = RandomSource.create(12345)
    seq_a = [a.nextInt(100) for _index in range(5)]
    seq_b = [b.nextInt(100) for _index in range(5)]
    check(u"同种子序列一致", seq_a == seq_b, (seq_a, seq_b))
    check(u"值落在范围内",
          all(0 <= v < 100 for v in seq_a), seq_a)

    c = RandomSource.create(999)
    seq_c = [c.nextInt(100) for _index in range(5)]
    check(u"不同种子序列不同", seq_a != seq_c, (seq_a, seq_c))

    r = RandomSource.create(7)
    check(u"nextDouble 在 [0,1)", 0.0 <= r.nextDouble() < 1.0)
    check(u"nextFloat 在 [0,1)", 0.0 <= r.nextFloat() < 1.0)
    check(u"nextBoolean 是布尔", isinstance(r.nextBoolean(), bool))
    check(u"nextInt 无上界返回整数", isinstance(r.nextInt(), int))
    check(u"setSeed 后序列可复现",
          (lambda: (r.setSeed(12345),
                    [r.nextInt(100) for _index in range(3)])[1])() == seq_a[:3])
    check(u"fork 派生新随机源", isinstance(r.fork(), RandomSource))
    check(u"缺随机源时 Mth.nextInt 报错",
          raises(Mth.nextInt, None, 10))

    # ------------------------------------------------------------
    section("HitResult：类型层次")
    # ------------------------------------------------------------
    HitResult = util.HitResult
    miss = HitResult()
    check(u"MISS 类型", miss.getType() is HitResult.MISS)
    check(u"Type 常量稳定", HitResult.MISS is HitResult.MISS)
    check(u"三种类型互不相同",
          len(set([id(HitResult.MISS), id(HitResult.BLOCK),
                   id(HitResult.ENTITY)])) == 3)
    check(u"Type 名字", HitResult.BLOCK.name() == u"BLOCK")

    block_hit = util.BlockHitResult(mc.Vec3(1.5, 2.0, 3.5),
                                    mc.Direction.UP,
                                    mc.BlockPos(1, 2, 3))
    check(u"BlockHitResult 的 getType 是 BLOCK",
          block_hit.getType() is HitResult.BLOCK)
    # 关键：instanceof 等价语义 —— 真实代码用它分支
    check(u"BlockHitResult 是 HitResult（instanceof 等价）",
          isinstance(block_hit, HitResult))
    check(u"getBlockPos", tuple(block_hit.getBlockPos()) == (1, 2, 3))
    check(u"getDirection", block_hit.getDirection() is mc.Direction.UP)
    check(u"getLocation 保留浮点",
          block_hit.getLocation().toString() == u"(1.5, 2.0, 3.5)",
          block_hit.getLocation().toString())
    check(u"MISS 与 BLOCK 类型不同",
          miss.getType() is not block_hit.getType())

    entity_hit = util.EntityHitResult(u"某实体", mc.Vec3(0.0, 0.0, 0.0))
    check(u"EntityHitResult 的 getType 是 ENTITY",
          entity_hit.getType() is HitResult.ENTITY)
    check(u"getEntity", entity_hit.getEntity() == u"某实体")
    check(u"EntityHitResult 是 HitResult",
          isinstance(entity_hit, HitResult))

    # 从位置推方块坐标（用 BlockPos.containing，负数向下取整）
    derived = util.BlockHitResult(mc.Vec3(-0.5, 2.0, 3.5))
    check(u"从位置推方块坐标（负数向下取整）",
          tuple(derived.getBlockPos()) == (-1, 2, 3),
          tuple(derived.getBlockPos()))

    # ------------------------------------------------------------
    section("InteractionResultHolder")
    # ------------------------------------------------------------
    holder_mod = util.InteractionResultHolder
    stack = item_mod.ItemStack(DIAMOND, 1)

    ok = holder_mod.success(stack)
    check(u"success 的结果是 SUCCESS",
          ok.getResult() is mc.InteractionResult.SUCCESS)
    check(u"带上了物品栈", ok.getObject() is stack)

    consumed = holder_mod.consume(stack)
    check(u"consume 的结果是 CONSUME",
          consumed.getResult() is mc.InteractionResult.CONSUME)

    failed = holder_mod.fail(stack)
    check(u"fail 的结果是 FAIL",
          failed.getResult() is mc.InteractionResult.FAIL)

    # 关键：pass 是 Python 关键字，方法名只能改成 passResult
    passed = holder_mod.passResult(stack)
    check(u"passResult 的结果是 PASS",
          passed.getResult() is mc.InteractionResult.PASS)
    check(u"没有名为 pass 的方法（它是关键字）",
          not hasattr(holder_mod, "pass"))
    check(u"可用 getattr('passResult') 调用（翻译层入口）",
          getattr(holder_mod, u"passResult")(stack).getResult()
          is mc.InteractionResult.PASS)

    no_stack = holder_mod.success()
    check(u"不传物品栈时给空栈",
          no_stack.getObject().isEmpty() is True)

    # ------------------------------------------------------------
    section("I18n：与 Component 共用翻译表")
    # ------------------------------------------------------------
    I18n = util.I18n
    mc.Component.clearTranslations()
    check(u"未载入时 get 回退为键",
          I18n.get(u"block.brewing.test") == u"block.brewing.test",
          I18n.get(u"block.brewing.test"))
    check(u"exists 反映有无译文", I18n.exists(u"block.brewing.test") is False)
    check(u"getIfExists 无译文返回 None",
          I18n.getIfExists(u"block.brewing.test") is None)

    I18n.loadFromLangFile({
        u"block.brewing.test": u"测试酿造台",
        u"mode.doubling.name": u"%s 倍模式",
    })
    check(u"载入后有译文",
          I18n.get(u"block.brewing.test") == u"测试酿造台",
          I18n.get(u"block.brewing.test"))
    check(u"exists 变为真", I18n.exists(u"block.brewing.test") is True)
    check(u"getIfExists 有译文时返回它",
          I18n.getIfExists(u"block.brewing.test") == u"测试酿造台")
    check(u"带参数替换", I18n.get(u"mode.doubling.name", 64) == u"64 倍模式",
          I18n.get(u"mode.doubling.name", 64))
    # 关键：与 Component 共用同一份翻译表，不会两处不一致
    check(u"与 Component 一致",
          I18n.get(u"block.brewing.test")
          == mc.Component.translatable(u"block.brewing.test").getString())

    # ------------------------------------------------------------
    section("ContainerData / Slot / MenuType")
    # ------------------------------------------------------------
    data = menu_mod.ContainerData(4)
    check(u"默认 4 项全 0", data.toList() == [0, 0, 0, 0], data.toList())
    data.set(0, 18)
    check(u"set/get", data.get(0) == 18)
    check(u"getCount", data.getCount() == 4)
    check(u"越界报错", raises(data.get, 9) and raises(data.set, 9, 1))
    check(u"可按初值构造",
          menu_mod.ContainerData(values=[1, 2]).toList() == [1, 2])

    # Slot 需要一个容器
    class SimpleContainer(be.Container):
        def __init__(self, size=3):
            self._items = be.NonNullList.withSize(size, item_mod.ItemStack())

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
    slot = menu_mod.Slot(container, 1, 8, 16)
    check(u"getContainerSlot", slot.getContainerSlot() == 1)
    check(u"坐标 x/y", (slot.x, slot.y) == (8, 16))
    check(u"初始 hasItem 为假", slot.hasItem() is False)
    slot.set(item_mod.ItemStack(DIAMOND, 3))
    check(u"set 写进容器", container.getItem(1).getCount() == 3)
    check(u"hasItem 变为真", slot.hasItem() is True)
    check(u"getItem 读回", slot.getItem().getCount() == 3)
    check(u"mayPlace 默认真",
          slot.mayPlace(item_mod.ItemStack(DIRT, 1)) is True)
    check(u"remove 取出", slot.remove(2).getCount() == 2)
    check(u"容器里剩 1", container.getItem(1).getCount() == 1)

    # 没有容器的槽位不崩
    lonely = menu_mod.Slot(None, 0, 0, 0)
    check(u"无容器时 getItem 返回空栈", lonely.getItem().isEmpty() is True)
    check(u"无容器时 hasItem 为假", lonely.hasItem() is False)

    # MenuType
    MenuType = menu_mod.MenuType
    created_ids = []

    def factory(container_id, inventory):
        created_ids.append(container_id)
        return menu_mod.AbstractContainerMenu(None, inventory, u"标题")

    mtype = MenuType(factory, u"manaita_plus_legacy:crafting")
    menu = mtype.create(1, u"玩家背包")
    check(u"create 走工厂", isinstance(menu, menu_mod.AbstractContainerMenu))
    check(u"工厂收到 id", created_ids == [1], created_ids)
    check(u"标识", mtype.getIdentifier() == u"manaita_plus_legacy:crafting")
    check(u"没有界面构造器时 hasScreen 为假", mtype.hasScreen() is False)
    mtype.setScreenConstructor(lambda *a: None)
    check(u"登记后 hasScreen 为真", mtype.hasScreen() is True)
    try:
        MenuType().create(1, None)
        check(u"缺少菜单工厂必须报出未实现", False)
    except Exception as error:
        check(u"缺少菜单工厂明确报出", type(error).__name__ == "UnsupportedOperationException")

    # ------------------------------------------------------------
    section("AbstractContainerMenu / MenuProvider / Containers")
    # ------------------------------------------------------------
    amenu = menu_mod.AbstractContainerMenu(container, u"背包", u"合成台")
    check(u"记录容器与背包", amenu.getContainer() is container)
    check(u"getTitle", amenu.getTitle() == u"合成台")
    check(u"containerId 自增且唯一",
          menu_mod.AbstractContainerMenu().getContainerId()
          != amenu.getContainerId())

    check(u"addSlot 返回槽位并设置 index", amenu.addSlot(slot) is slot and slot.index == 0)
    check(u"再加一个 index 为 1", amenu.addSlot(menu_mod.Slot(container, 0)).index == 1)
    check(u"getSlotCount", amenu.getSlotCount() == 2)
    check(u"getSlot", amenu.getSlot(1) is not None)
    check(u"addSlot(None) 报错", raises(amenu.addSlot, None))

    amenu.addDataSlots(data)
    check(u"addDataSlots 计数", amenu.getDataSlotCount() == data.getCount())
    check(u"addDataSlots(None) 报错", raises(amenu.addDataSlots, None))

    check(u"quickMoveStack 未提供搬运规则时明确报错",
          raises(amenu.quickMoveStack, u"玩家", 0))
    check(u"stillValid 默认真", amenu.stillValid(u"玩家") is True)
    amenu.broadcastChanges()
    check(u"broadcastChanges 不报错", True)
    amenu.removed(u"玩家")
    check(u"removed 后标记", amenu.isRemoved() is True)
    check(u"toString 可读", u"槽位" in amenu.toString(), amenu.toString())

    # RecipeBookMenu
    rb = menu_mod.RecipeBookMenu(container, u"背包", u"合成台")
    check(u"RecipeBookMenu 是菜单",
          isinstance(rb, menu_mod.AbstractContainerMenu))
    rb.setRecipeBookType(u"crafting")
    check(u"配方书类型", rb.getRecipeBookType() == u"crafting")

    # MenuProvider
    class Provider(menu_mod.MenuProvider):
        def createMenu(self, container_id, inventory, player=None):
            return menu_mod.AbstractContainerMenu(container, inventory,
                                                  u"提供的界面")

        def getDisplayName(self):
            return mc.Component.literal(u"提供的界面")

    provider = Provider()
    provided = provider.createMenu(1, u"背包")
    check(u"createMenu 可用",
          isinstance(provided, menu_mod.AbstractContainerMenu))
    check(u"getDisplayName",
          provider.getDisplayName().getString() == u"提供的界面")
    check(u"默认会触发客户端关闭", 
          provider.shouldTriggerClientSideContainerClosingOnOpen() is True)
    check(u"基类 createMenu 未实现会报错",
          raises(menu_mod.MenuProvider().createMenu, 1, None))

    # Containers：掉落内容物
    drop_container = SimpleContainer(3)
    drop_container.setItem(0, item_mod.ItemStack(DIAMOND, 2))
    drop_container.setItem(2, item_mod.ItemStack(DIRT, 1))
    access = access_mod.InMemoryLevelAccess()
    world = level_mod.Level.wrap(access)
    dropped = menu_mod.Containers.dropContents(world, mc.BlockPos(1, 2, 3),
                                               drop_container)
    check(u"掉落 2 组物品", len(dropped) == 2, len(dropped))
    check(u"容器被清空", drop_container.isEmpty() is True)
    check(u"dropContents(None) 报错",
          raises(menu_mod.Containers.dropContents, world, mc.BlockPos(0, 0, 0),
                 None))
    check(u"dropItemStack 返回原栈",
          menu_mod.Containers.dropItemStack(world, 0.0, 0.0, 0.0,
                                            item_mod.ItemStack(DIAMOND, 1))
          is not None)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in ("net.minecraft.nbt.CompoundTag", "net.minecraft.nbt.Tag"):
        check(u"nbt 映射 {}".format(java_name), java_name in nbt.JAVA_MAP)
    for java_name in (
        "net.minecraft.world.inventory.AbstractContainerMenu",
        "net.minecraft.world.inventory.MenuType",
        "net.minecraft.world.inventory.Slot",
        "net.minecraft.world.inventory.ContainerData",
        "net.minecraft.world.MenuProvider",
        "net.minecraft.world.Containers",
    ):
        check(u"menu 映射 {}".format(java_name), java_name in menu_mod.JAVA_MAP)
    for java_name in (
        "net.minecraft.util.Mth",
        "net.minecraft.util.RandomSource",
        "net.minecraft.world.phys.HitResult",
        "net.minecraft.world.phys.BlockHitResult",
        "net.minecraft.world.phys.EntityHitResult",
        "net.minecraft.world.InteractionResultHolder",
        "net.minecraft.client.resources.language.I18n",
    ):
        check(u"util 映射 {}".format(java_name), java_name in util.JAVA_MAP)

finally:
    mc.Component.clearTranslations()
    item_mod.ITEMS.clear()
    level_mod.Level.resetWrappers()

sys.exit(summary())

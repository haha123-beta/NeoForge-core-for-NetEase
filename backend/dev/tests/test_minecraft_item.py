# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/item.py（物品）

真实依据（逐字来自反编译源码）：
    super(new Item.Properties().durability(-1).fireResistant());
    super(new Item.Properties().stacksTo(1).durability(-1).fireResistant());
    new ItemStack((ItemLike) ManaitaPlusLegacyBlockCore.CraftingBlockItem.get())

    实例方法引用次数：getItem 44、isEmpty 22、getCount 21、is 20、
    getDisplayName 14、copy 9、setCount 8、shrink 7、getMaxStackSize 7

验证点：
  1. Item.Properties 的链式调用（顺序不固定、每步返回自身）
  2. durability(-1) 的「不可损坏」语义
  3. ItemStack 的空栈判定（count<=0，不是 None）
  4. Java count赋值与空栈读取（不按常规最大堆叠数夹取）
  5. is / isSameItemSameComponents / matches 的比较语义
  6. grow / shrink / split / copy
  7. getPersistentData 的可直接读写
  8. getDisplayName 与翻译回退
  9. Items 懒加载常量、Rarity、名称映射表
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")

Item = item_mod.Item
ItemStack = item_mod.ItemStack
Properties = item_mod.ItemProperties


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("Item.Properties：链式调用")
    # ------------------------------------------------------------
    # 真实代码的两种链式顺序
    props_a = Properties().durability(-1).fireResistant()
    props_b = Properties().stacksTo(1).durability(-1).fireResistant()

    check(u"每个设置方法都返回自身（可链式）",
          Properties().stacksTo(1) is not None
          and isinstance(Properties().fireResistant(), Properties))
    check(u"链式后属性生效",
          props_a.getMaxDamage() == -1 and props_a.isFireResistant() is True,
          (props_a.getMaxDamage(), props_a.isFireResistant()))
    check(u"另一种顺序也正确",
          props_b.getMaxStackSize() == 1 and props_b.getMaxDamage() == -1
          and props_b.isFireResistant() is True,
          (props_b.getMaxStackSize(), props_b.getMaxDamage()))

    check(u"默认堆叠数是 64", Properties().getMaxStackSize() == 64)
    check(u"默认不可燃", Properties().isFireResistant() is False)
    check(u"stacksTo(1) 生效", Properties().stacksTo(1).getMaxStackSize() == 1)

    # ------------------------------------------------------------
    section("durability：官方损耗与堆叠设置")
    # ------------------------------------------------------------
    unbreakable_props = Properties().durability(-1)
    check(u"durability(-1) 不伪造 UNBREAKABLE 组件",
          unbreakable_props.isUnbreakable() is False)
    check(u"值本身保持 -1（哨兵值不被改写）",
          unbreakable_props.getMaxDamage() == -1,
          unbreakable_props.getMaxDamage())

    normal_props = Properties().durability(250)
    check(u"正耐久不算不可损坏",
          normal_props.isUnbreakable() is False)
    check(u"正耐久值正确", normal_props.getMaxDamage() == 250)

    unbreakable_item = Item(Properties().durability(-1))
    check(u"不可损坏物品 isDamageable 为假",
          unbreakable_item.isDamageable() is False)
    tool_item = Item(Properties().durability(100))
    check(u"有耐久的物品 isDamageable 为真",
          tool_item.isDamageable() is True)
    plain_item = Item(Properties())
    check(u"无耐久物品 isDamageable 为假",
          plain_item.isDamageable() is False)

    check(u"Item 构造参数类型不对时报错", raises(Item, u"not_properties"))

    # ------------------------------------------------------------
    section("ItemStack：空栈判定（最重要的语义）")
    # ------------------------------------------------------------
    # 模组代码到处写 if (stack.isEmpty())，
    # 把它当成「对象是否存在」会全错 —— 空栈是 count<=0，不是 None。
    empty = ItemStack()
    check(u"空构造得到空栈", empty.isEmpty() is True)
    check(u"空栈 count 是 0", empty.getCount() == 0, empty.getCount())
    check(u"空栈 getItem 返回 AIR", empty.getItem() is item_mod.ITEMS.AIR)
    check(u"EMPTY 常量存在", ItemStack.EMPTY.isEmpty() is True)

    real = ItemStack(plain_item)
    check(u"不带数量默认是 1", real.getCount() == 1, real.getCount())
    check(u"非空栈 isEmpty 为假", real.isEmpty() is False)

    zero = ItemStack(plain_item, 0)
    check(u"数量 0 的栈**也是空栈**（关键语义）", zero.isEmpty() is True,
          zero.isEmpty())
    check(u"数量0的栈 getItem 返回 AIR", zero.getItem() is item_mod.ITEMS.AIR)

    negative = ItemStack(plain_item, -5)
    check(u"负数数量仍是空栈", negative.isEmpty() is True)

    # ------------------------------------------------------------
    section("ItemStack：Java 数量语义")
    # ------------------------------------------------------------
    stack = ItemStack(plain_item, 10)
    stack.setCount(-1)
    check(u"setCount(-1) 得到 0（不是 -1）", stack.getCount() == 0,
          stack.getCount())

    stack.setCount(999)
    check(u"setCount 保留超常规堆叠数量",
          stack.getCount() == 999,
          (stack.getCount(), plain_item.getMaxStackSize()))

    single_item = Item(Properties().stacksTo(1))
    single_stack = ItemStack(single_item, 5)
    check(u"stacksTo(1) 不改变构造数量",
          single_stack.getCount() == 5, single_stack.getCount())

    # ------------------------------------------------------------
    section("ItemStack：构造的多种形态")
    # ------------------------------------------------------------
    from_like = ItemStack(plain_item)
    check(u"new ItemStack(ItemLike)", from_like.getItem() is plain_item)

    copied_stack = ItemStack(from_like)
    check(u"new ItemStack(ItemStack) 是拷贝",
          copied_stack.getItem() is from_like.getItem()
          and copied_stack is not from_like)
    check(u"拷贝后改数量不影响原栈",
          (copied_stack.setCount(9), from_like.getCount() == 1)[1],
          from_like.getCount())

    check(u"非物品参数报错", raises(ItemStack, u"not_an_item"))

    # ------------------------------------------------------------
    section("ItemStack：比较语义")
    # ------------------------------------------------------------
    other_item = Item(Properties())
    stack_a = ItemStack(plain_item, 1)
    stack_a2 = ItemStack(plain_item, 3)
    stack_b = ItemStack(other_item, 1)

    check(u"isItem(Item) 同类为真", stack_a.isItem(plain_item) is True)
    check(u"isItem(Item) 异类为假", stack_a.isItem(other_item) is False)
    check(u"isItem(ItemStack) 同类为真", stack_a.isItem(stack_a2) is True)
    check(u"isItem(ItemStack) 异类为假", stack_a.isItem(stack_b) is False)
    check(u"空栈不匹配普通非AIR物品", empty.isItem(plain_item) is False)
    # Preserve original Java name through getattr despite Python's keyword.
    check(u"原名 is 可用 getattr 取到（翻译层入口）",
          getattr(stack_a, u"is")(plain_item) is True)

    check(u"isSameItemSameComponents 同物品为真",
          stack_a.isSameItemSameComponents(stack_a2) is True)
    check(u"isSameItemSameComponents 异物品为假",
          stack_a.isSameItemSameComponents(stack_b) is False)
    check(u"matches 数量不同为假", stack_a.matches(stack_a2) is False)
    check(u"与空栈比较为假",
          stack_a.isSameItemSameComponents(empty) is False)

    # Original ItemStack inherits Object identity equality.
    check(u"equals 数量不同则不相等", stack_a.equals(stack_a2) is False)
    check(u"equals 相同内容的独立对象仍不相等",
          ItemStack(plain_item, 3).equals(stack_a2) is False)
    check(u"两个独立空栈不相等", ItemStack().equals(ItemStack()) is False)

    # ------------------------------------------------------------
    section("ItemStack：数量变更")
    # ------------------------------------------------------------
    grow_stack = ItemStack(plain_item, 10)
    grow_stack.grow(5)
    check(u"grow 增加数量", grow_stack.getCount() == 15, grow_stack.getCount())

    grow_stack.shrink(4)
    check(u"shrink 减少数量", grow_stack.getCount() == 11, grow_stack.getCount())

    grow_stack.shrink(100)
    check(u"shrink 不会低于 0", grow_stack.getCount() == 0,
          grow_stack.getCount())

    grow_stack.setCount(60)
    grow_stack.grow(100)
    check(u"grow 保留超常规堆叠数量",
          grow_stack.getCount() == 160,
          grow_stack.getCount())

    # split
    split_source = ItemStack(plain_item, 10)
    split_out = split_source.split(4)
    check(u"split 分出的是新栈", split_out.getCount() == 4, split_out.getCount())
    check(u"split 后原栈减少", split_source.getCount() == 6,
          split_source.getCount())
    check(u"split 出的与原栈同物品", split_out.getItem() is plain_item)
    check(u"split(0) 返回空栈", ItemStack(plain_item, 5).split(0).isEmpty() is True)
    check(u"split 超过持有量时只分出现有的",
          ItemStack(plain_item, 3).split(10).getCount() == 3)

    # copy
    original = ItemStack(plain_item, 7)
    original.getPersistentData()[u"k"] = u"v"
    clone = original.copy()
    check(u"copy 得到不同对象", clone is not original)
    check(u"copy 数量一致", clone.getCount() == 7)
    check(u"copy 物品一致", clone.getItem() is plain_item)
    check(u"copy 带上自定义数据",
          clone.getPersistentData().get(u"k") == u"v",
          clone.getPersistentData())
    clone.setCount(1)
    check(u"改 copy 不影响原栈", original.getCount() == 7)

    check(u"copyWithCount 指定数量",
          original.copyWithCount(2).getCount() == 2)

    # ------------------------------------------------------------
    section("ItemStack：自定义数据")
    # ------------------------------------------------------------
    data_stack = ItemStack(plain_item, 1)
    check(u"初始没有自定义数据", data_stack.hasCustomData() is False)
    data = data_stack.getPersistentData()
    check(u"getPersistentData 返回始终存在的字典",
          isinstance(data, dict), type(data).__name__)
    data[u"durability"] = 42
    check(u"可以直接写入",
          data_stack.getPersistentData()[u"durability"] == 42)
    check(u"写入后 hasCustomData 为真",
          data_stack.hasCustomData() is True)

    check(u"setCustomData 可整体替换",
          (data_stack.setCustomData({u"a": 1}),
           data_stack.getCustomData())[1] == {u"a": 1})
    check(u"setCustomData(None) 后 hasCustomData 为假",
          (data_stack.setCustomData(None),
           data_stack.hasCustomData())[1] is False)

    # ------------------------------------------------------------
    section("ItemStack：显示名与翻译回退")
    # ------------------------------------------------------------
    mc.Component.clearTranslations()
    named_item = Item(Properties()).setRegistryName(u"manaita:crafting_manaita")
    check(u"getDescriptionId 由注册名推导",
          named_item.getDescriptionId() == u"item.manaita.crafting_manaita",
          named_item.getDescriptionId())

    unnamed = Item(Properties())
    check(u"未注册物品也有可读的 descriptionId",
          unnamed.getDescriptionId().startswith(u"item.unregistered."),
          unnamed.getDescriptionId())

    display_stack = ItemStack(named_item, 1)
    check(u"无翻译时 getDisplayName 回退为键",
          display_stack.getDisplayName().getString()
          == u"item.manaita.crafting_manaita",
          display_stack.getDisplayName().getString())

    mc.Component.loadFromLangFile(
        {u"item.manaita.crafting_manaita": u"合成砧板"})
    check(u"有翻译时显示译文",
          display_stack.getDisplayName().getString() == u"合成砧板",
          display_stack.getDisplayName().getString())

    explicit = ItemStack(named_item, 1)
    explicit.setDisplayName(mc.Component.literal(u"自定义名字"))
    check(u"显式设置的名字优先",
          explicit.getDisplayName().getString() == u"自定义名字",
          explicit.getDisplayName().getString())

    check(u"空栈的显示名是空组件",
          empty.getDisplayName().getString() == u"",
          empty.getDisplayName().getString())
    check(u"getHoverName 与 getDisplayName 一致",
          display_stack.getHoverName().getString()
          == display_stack.getDisplayName().getString())

    check(u"toString 形态（空栈）", empty.toString() == u"0 x <empty>",
          empty.toString())
    check(u"toString 形态（非空）",
          u"3 x" in ItemStack(named_item, 3).toString(),
          ItemStack(named_item, 3).toString())

    # ------------------------------------------------------------
    section("Items 懒加载常量")
    # ------------------------------------------------------------
    item_mod.ITEMS.clear()
    check(u"取 Items.DIAMOND 得到 Item",
          isinstance(item_mod.ITEMS.DIAMOND, Item))
    check(u"同名始终同一对象",
          item_mod.ITEMS.DIAMOND is item_mod.ITEMS.DIAMOND)
    check(u"不同名是不同对象",
          item_mod.ITEMS.DIAMOND is not item_mod.ITEMS.EMERALD)
    check(u"Items.AIR 堆叠数为 0",
          item_mod.ITEMS.AIR.getMaxStackSize() == 0,
          item_mod.ITEMS.AIR.getMaxStackSize())

    # ------------------------------------------------------------
    section("Rarity")
    # ------------------------------------------------------------
    check(u"四级稀有度齐备",
          len([r for r in (item_mod.Rarity.COMMON, item_mod.Rarity.UNCOMMON,
                           item_mod.Rarity.RARE, item_mod.Rarity.EPIC)
               if r is not None]) == 4)
    check(u"按身份比较",
          (item_mod.Rarity.COMMON == item_mod.Rarity.COMMON) is True
          and (item_mod.Rarity.COMMON == item_mod.Rarity.RARE) is False)
    check(u"Properties 可设置稀有度",
          Properties().rarity(item_mod.Rarity.EPIC).getRarity()
          is item_mod.Rarity.EPIC)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    expected = [
        "net.minecraft.world.item.Item",
        "net.minecraft.world.item.Item$Properties",
        "net.minecraft.world.item.ItemStack",
        "net.minecraft.world.level.ItemLike",
        "net.minecraft.world.item.Items",
        "net.minecraft.world.item.Rarity",
    ]
    missing = [name for name in expected if name not in item_mod.JAVA_MAP]
    check(u"已实现的 θ 层物品类型都在映射表里", missing == [], missing)

    failures = []
    for java_name, impl in item_mod.JAVA_MAP.items():
        if not isinstance(impl, type) and not hasattr(impl, "__getattr__"):
            failures.append(u"{}: 映射目标不可用".format(java_name))
    check(u"映射目标都可用", failures == [], failures)

finally:
    mc.Component.clearTranslations()
    item_mod.ITEMS.clear()

sys.exit(summary())

# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/crafting.py（配方）

真实依据（逐字来自反编译源码）：

    // 注册配方序列化器
    DeferredRegister.create(BuiltInRegistries.RECIPE_SERIALIZER, "manaita_plus_legacy")

    // 真实调用链
    public static ItemStack assembleResult(RecipeHolder<?> recipe, ItemStack input,
                                           RegistryAccess registryAccess) {
        return ((AbstractCookingRecipe) recipe.value())
            .assemble(new SingleRecipeInput(input), (HolderLookup.Provider) registryAccess);
    }
    level.getRecipeManager().byKey(ResourceLocation).ifPresent(recipe -> {
        recipes.add((RecipeHolder<?>) recipe);
    });

    // 材料
    if (!potionBrewing.isIngredient(itemstack)) {...}
    public Ingredient getRepairIngredient()
    () -> Ingredient.EMPTY

    // 配方类型（JEI 插件）
    new RecipeType[]{RecipeTypes.CRAFTING}

验证点：
  1. Ingredient.test 是「材料是否匹配」而不是「相等」
  2. Ingredient.EMPTY 对任何东西都为假
  3. 输入类型（SingleRecipeInput / CraftingInput）
  4. 烧炼配方的 matches / assemble
  5. 有形状合成配方的尺寸与位置约束
  6. RecipeHolder 的 value() / id()
  7. RecipeManager 的 byKey / byType
  8. 端到端：注册序列化器 + 走完整调用链
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
item_mod = pkg.load("minecraft.item")
crafting = pkg.load("minecraft.crafting")
registries_mod = pkg.load("neoforge.registries")

Ingredient = crafting.Ingredient
ItemStack = item_mod.ItemStack


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
    EMERALD = item_mod.ITEMS.EMERALD

    # ------------------------------------------------------------
    section("Ingredient：材料匹配")
    # ------------------------------------------------------------
    # 关键：test 判的是「能不能当这个材料用」，不是「相等」。
    # 一个 Ingredient 可以包含多个物品。
    either = Ingredient.of(DIAMOND, EMERALD)
    check(u"包含 2 个物品", len(either.getItems()) == 2)
    check(u"匹配第一个物品", either.test(ItemStack(DIAMOND, 1)) is True)
    check(u"匹配第二个物品", either.test(ItemStack(EMERALD, 1)) is True)
    check(u"不匹配未列出的物品", either.test(ItemStack(DIRT, 1)) is False)
    check(u"空栈不匹配", either.test(ItemStack()) is False)
    check(u"None 不匹配", either.test(None) is False)
    check(u"非空", either.isEmpty() is False)

    # EMPTY 对任何东西都为假
    check(u"EMPTY 是空的", Ingredient.EMPTY.isEmpty() is True)
    check(u"EMPTY 不匹配任何物品",
          Ingredient.EMPTY.test(ItemStack(DIAMOND, 1)) is False)

    # 标签式材料
    tagged = Ingredient.ofTag(u"minecraft:logs")
    check(u"标签材料有 tag", tagged.getTag() == u"minecraft:logs")
    check(u"标签材料没有具体物品", tagged.getItems() == [])
    check(u"标签材料不算空", tagged.isEmpty() is False)

    # 嵌套 Ingredient 也能匹配
    nested = Ingredient.of(Ingredient.of(DIAMOND), EMERALD)
    check(u"嵌套 Ingredient 可匹配", nested.test(ItemStack(DIAMOND, 1)) is True)

    check(u"of 接受列表", len(Ingredient.of([DIAMOND, DIRT]).getItems()) == 2)
    check(u"toString 可读", u"EMPTY" in Ingredient.EMPTY.toString(),
          Ingredient.EMPTY.toString())
    check(u"相等语义",
          Ingredient.of(DIAMOND) == Ingredient.of(DIAMOND))
    check(u"不同材料不等",
          Ingredient.of(DIAMOND) != Ingredient.of(DIRT))

    # ------------------------------------------------------------
    section("输入类型")
    # ------------------------------------------------------------
    single = crafting.SingleRecipeInput(ItemStack(DIAMOND, 3))
    check(u"SingleRecipeInput 只有一个位置", single.size() == 1)
    check(u"getItem(0) 取到", single.getItem(0).getCount() == 3)
    check(u"越界报错", raises(single.getItem, 1))
    check(u"非空", single.isEmpty() is False)
    check(u"空输入 isEmpty 为真",
          crafting.SingleRecipeInput(ItemStack()).isEmpty() is True)
    check(u"None 当空栈处理",
          crafting.SingleRecipeInput(None).isEmpty() is True)

    grid = crafting.CraftingInput(3, 3)
    check(u"3x3 有 9 格", grid.size() == 9, grid.size())
    check(u"记录宽高", (grid.getWidth(), grid.getHeight()) == (3, 3))
    check(u"越界报错", raises(grid.getItem, 9))
    check(u"格子数不匹配报错", raises(crafting.CraftingInput, 2, 2, [None]))

    filled = crafting.CraftingInput(1, 1, [ItemStack(DIAMOND, 1)])
    check(u"1x1 有一个物品", filled.getItem(0).getCount() == 1)

    # ------------------------------------------------------------
    section("烧炼配方")
    # ------------------------------------------------------------
    smelt = crafting.AbstractCookingRecipe(
        Ingredient.of(DIAMOND), ItemStack(EMERALD, 1),
        cooking_time=200, experience=0.5,
        recipe_type=crafting.RecipeTypes.SMELTING)

    check(u"匹配对的输入",
          smelt.matches(crafting.SingleRecipeInput(ItemStack(DIAMOND, 1)))
          is True)
    check(u"不匹配错的输入",
          smelt.matches(crafting.SingleRecipeInput(ItemStack(DIRT, 1)))
          is False)
    check(u"空输入不匹配",
          smelt.matches(crafting.SingleRecipeInput(ItemStack())) is False)
    check(u"None 输入不匹配", smelt.matches(None) is False)

    result = smelt.assemble(crafting.SingleRecipeInput(ItemStack(DIAMOND, 5)))
    check(u"产出结果", result.getItem() is EMERALD)
    # 关键：烧炼一次产出**一份**，不是按输入数量翻倍
    check(u"产出一份（不按输入数量翻倍）", result.getCount() == 1,
          result.getCount())

    check(u"getCookingTime", smelt.getCookingTime() == 200)
    check(u"getExperience", smelt.getExperience() == 0.5)
    check(u"getIngredient",
          smelt.getIngredient().test(ItemStack(DIAMOND, 1)) is True)
    check(u"getResultItem 可预览",
          smelt.getResultItem().getItem() is EMERALD)
    check(u"配方类型正确",
          smelt.getType() is crafting.RecipeTypes.SMELTING)

    # 无结果的配方产出空栈而不是崩
    empty_result = crafting.AbstractCookingRecipe(Ingredient.of(DIAMOND), None)
    check(u"无结果时产出空栈",
          empty_result.assemble(None).isEmpty() is True)

    # ------------------------------------------------------------
    section("合成配方：有形状的尺寸约束")
    # ------------------------------------------------------------
    shaped = crafting.CraftingRecipe(
        ingredients=[Ingredient.of(DIAMOND), Ingredient.of(DIAMOND),
                     Ingredient.of(DIAMOND), Ingredient.of(DIAMOND)],
        result=ItemStack(EMERALD, 1), shaped=True, width=2, height=2)

    match_input = crafting.CraftingInput(2, 2, [ItemStack(DIAMOND, 1)] * 4)
    check(u"2x2 同形状匹配", shaped.matches(match_input) is True)

    # 关键：Minecraft 的有形状配方要求尺寸一致 ——
    # 3x3 的配方不能靠 1x1 的输入做出来。
    wrong_size = crafting.CraftingInput(1, 1, [ItemStack(DIAMOND, 1)])
    check(u"尺寸不一致时不匹配", shaped.matches(wrong_size) is False)

    wrong_ingredient = crafting.CraftingInput(
        2, 2, [ItemStack(DIAMOND, 1), ItemStack(DIAMOND, 1),
               ItemStack(DIAMOND, 1), ItemStack(DIRT, 1)])
    check(u"有一个格子材料不对就不匹配",
          shaped.matches(wrong_ingredient) is False)

    empty_slot = crafting.CraftingInput(
        2, 2, [ItemStack(DIAMOND, 1), ItemStack(DIAMOND, 1),
               ItemStack(DIAMOND, 1), ItemStack()])
    check(u"不该空的格子空着就不匹配",
          shaped.matches(empty_slot) is False)

    check(u"产出结果",
          shaped.assemble(match_input).getItem() is EMERALD)
    check(u"getIngredients 返回材料表", len(shaped.getIngredients()) == 4)

    # 无形状配方不校验尺寸
    shapeless = crafting.CraftingRecipe(
        ingredients=[Ingredient.of(DIAMOND), Ingredient.of(EMERALD)],
        result=ItemStack(DIRT, 1), shaped=False)
    check(u"无形状配方不看尺寸",
          shapeless.matches(crafting.CraftingInput(
              2, 1, [ItemStack(DIAMOND, 1), ItemStack(EMERALD, 1)])) is True)

    # ------------------------------------------------------------
    section("RecipeType / RecipeSerializer")
    # ------------------------------------------------------------
    check(u"CRAFTING 常量",
          crafting.RecipeTypes.CRAFTING.toString() == u"minecraft:crafting")
    check(u"SMELTING 常量",
          crafting.RecipeTypes.SMELTING.toString() == u"minecraft:smelting")
    check(u"不同类型不相等",
          crafting.RecipeTypes.CRAFTING != crafting.RecipeTypes.SMELTING)
    check(u"同类型相等",
          crafting.RecipeType.of(u"minecraft:crafting")
          == crafting.RecipeTypes.CRAFTING)
    check(u"可作字典键",
          {crafting.RecipeTypes.CRAFTING: 1}[crafting.RecipeTypes.CRAFTING]
          == 1)

    class MySerializer(crafting.RecipeSerializer):
        def fromJson(self, data):
            return crafting.AbstractCookingRecipe(
                Ingredient.of(DIAMOND), ItemStack(EMERALD, 1))

        def toJson(self, recipe):
            return {u"type": u"my_recipe"}

    serializer = MySerializer(u"manaita_plus_legacy:my_recipe")
    check(u"序列化器带标识",
          serializer.getIdentifier() == u"manaita_plus_legacy:my_recipe",
          serializer.getIdentifier())
    check(u"fromJson 可建配方",
          isinstance(serializer.fromJson({}), crafting.AbstractCookingRecipe))
    check(u"toJson 可写出", serializer.toJson(None)[u"type"] == u"my_recipe")
    check(u"基类未实现 fromJson 报错",
          raises(crafting.RecipeSerializer().fromJson, {}))

    # ------------------------------------------------------------
    section("RecipeHolder：value() 与 id()")
    # ------------------------------------------------------------
    holder = crafting.RecipeHolder(u"manaita_plus_legacy:smelt_diamond", smelt)
    check(u"id() 取配方 ID",
          holder.id() == u"manaita_plus_legacy:smelt_diamond", holder.id())
    # 关键：value() 是访问配方本体的标准入口
    check(u"value() 取配方本体", holder.value() is smelt)
    check(u"可以用 value() 直接调 assemble",
          holder.value().assemble(
              crafting.SingleRecipeInput(ItemStack(DIAMOND, 1))).getItem()
          is EMERALD)
    check(u"缺配方本体报错", raises(crafting.RecipeHolder, u"t:x", None))
    check(u"同 ID 相等",
          holder == crafting.RecipeHolder(
              u"manaita_plus_legacy:smelt_diamond", smelt))
    check(u"可作字典键",
          {holder: 1}[crafting.RecipeHolder(
              u"manaita_plus_legacy:smelt_diamond", smelt)] == 1)

    # ------------------------------------------------------------
    section("RecipeManager")
    # ------------------------------------------------------------
    manager = crafting.RecipeManager()
    check(u"初始为空", manager.size() == 0)
    manager.add(holder)
    check(u"登记后有 1 个", manager.size() == 1)
    check(u"byKey 命中", manager.byKey(
        u"manaita_plus_legacy:smelt_diamond") is holder)
    check(u"byKey 未命中返回 None（对应 Optional 空）",
          manager.byKey(u"nope") is None)
    check(u"byKeyOrNone 同上",
          manager.byKeyOrNone(u"nope") is None)
    check(u"getRecipeIds", manager.getRecipeIds()
          == [u"manaita_plus_legacy:smelt_diamond"], manager.getRecipeIds())

    crafting_holder = crafting.RecipeHolder(
        u"t:crafting", crafting.CraftingRecipe(
            [Ingredient.of(DIAMOND)], ItemStack(EMERALD, 1),
            shaped=False, recipe_type=crafting.RecipeTypes.CRAFTING))
    manager.add(crafting_holder)
    check(u"按类型筛选",
          manager.byType(crafting.RecipeTypes.CRAFTING) == [crafting_holder],
          manager.byType(crafting.RecipeTypes.CRAFTING))
    check(u"按类型筛选（另一个类型）",
          manager.byType(crafting.RecipeTypes.SMELTING) == [holder])
    check(u"未登记的类型返回空",
          manager.byType(crafting.RecipeTypes.BREWING) == [])

    check(u"add 非 RecipeHolder 报错", raises(manager.add, smelt))
    # 注意：clear 之后 manager 就空了，所以**放到最后**测 ——
    # 放这里会把后面的端到端用例清掉（实测踩到）。
    manager.clear()
    check(u"clear 清空", manager.size() == 0)
    manager.add(holder)
    manager.add(crafting_holder)
    check(u"可以重新登记", manager.size() == 2)

    # ------------------------------------------------------------
    section("端到端：注册序列化器 + 完整调用链")
    # ------------------------------------------------------------
    # 对应 ManaitaPlusLegacy.RECIPE_SERIALIZER_DEFERRED_REGISTER
    serializer_register = registries_mod.DeferredRegister.create(
        registries_mod.BUILT_IN_REGISTRIES.RECIPE_SERIALIZER,
        u"manaita_plus_legacy")

    serializer_holder = serializer_register.register(
        u"my_recipe", lambda: MySerializer(
            u"manaita_plus_legacy:my_recipe"))
    check(u"序列化器注册成 DeferredHolder",
          isinstance(serializer_holder, registries_mod.DeferredHolder))
    serializer_register.freeze_and_register(registries_mod.BUILT_IN_REGISTRIES.RECIPE_SERIALIZER)
    check(u"取到序列化器",
          isinstance(serializer_holder.get(), crafting.RecipeSerializer))

    # 对应 ManaitaPlusBlocksHandler.assembleResult 的调用链：
    #   ((AbstractCookingRecipe) recipe.value())
    #       .assemble(new SingleRecipeInput(input), (HolderLookup.Provider) registryAccess)
    lookup = pkg.load("minecraft.registries").HolderLookup()
    registry_access = pkg.load("minecraft.registries").RegistryAccess(lookup)

    def assemble_result(recipe_holder, input_stack, registry_access):
        single_input = crafting.SingleRecipeInput(input_stack)
        return recipe_holder.value().assemble(
            single_input, registry_access.getLookup())

    assembled = assemble_result(holder, ItemStack(DIAMOND, 9), registry_access)
    check(u"完整链路产出正确结果", assembled.getItem() is EMERALD)
    check(u"只产出一份", assembled.getCount() == 1, assembled.getCount())

    # 对应 byKey(...).ifPresent(recipe -> recipes.add(recipe))
    found = manager.byKey(u"manaita_plus_legacy:smelt_diamond")
    collected = []
    if found is not None:
        collected.append(found)
    check(u"按 ID 查回配方并收集", collected == [holder], collected)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.world.item.crafting.Ingredient",
        "net.minecraft.world.item.crafting.Recipe",
        "net.minecraft.world.item.crafting.RecipeInput",
        "net.minecraft.world.item.crafting.SingleRecipeInput",
        "net.minecraft.world.item.crafting.CraftingInput",
        "net.minecraft.world.item.crafting.AbstractCookingRecipe",
        "net.minecraft.world.item.crafting.CraftingRecipe",
        "net.minecraft.world.item.crafting.RecipeType",
        "net.minecraft.world.item.crafting.RecipeTypes",
        "net.minecraft.world.item.crafting.RecipeSerializer",
        "net.minecraft.world.item.crafting.RecipeHolder",
        "net.minecraft.world.item.crafting.RecipeManager",
    ):
        check(u"映射 {}".format(java_name), java_name in crafting.JAVA_MAP)

finally:
    item_mod.ITEMS.clear()

sys.exit(summary())

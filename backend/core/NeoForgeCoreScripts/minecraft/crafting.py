# -*- coding: utf-8 -*-
# minecraft/crafting.py
# θ 层：配方
#
# 真实用法（逐字来自反编译源码）：
#
#   // 注册配方序列化器
#   public static final DeferredRegister<RecipeSerializer<?>> RECIPE_SERIALIZER_DEFERRED_REGISTER =
#       DeferredRegister.create(BuiltInRegistries.RECIPE_SERIALIZER, "manaita_plus_legacy");
#
#   // 配方类型常量（JEI 插件里用来声明支持的配方类别）
#   new RecipeType[]{RecipeTypes.CRAFTING}
#   new RecipeType[]{RecipeTypes.SMELTING}
#
#   // 真实调用链（ManaitaPlusBlocksHandler）
#   public static ItemStack assembleResult(RecipeHolder<?> recipe, ItemStack input,
#                                          RegistryAccess registryAccess) {
#       return ((AbstractCookingRecipe) recipe.value())
#           .assemble(new SingleRecipeInput(input), (HolderLookup.Provider) registryAccess);
#   }
#   level.getRecipeManager().byKey(ResourceLocation).ifPresent(recipe -> {
#       recipes.add((RecipeHolder<?>) recipe);
#   });
#
#   // 材料匹配
#   if (!potionBrewing.isIngredient(itemstack)) {...}
#   public Ingredient getRepairIngredient()
#   () -> Ingredient.EMPTY
#
# 三个容易搞错的语义：
#   1. `Ingredient.test(stack)` 是**材料是否匹配**，不是「相等」——
#      标签（Tag）或多物品都能匹配同一个 Ingredient。
#   2. `RecipeHolder.value()` 取的是配方本体，`id()` 取的是配方 ID；
#      真实代码两个都要用（拿配方 + 记录「玩家做过什么」）。
#   3. `assemble(...)` 的第二个参数是 **HolderLookup.Provider** ——
#      因为合成结果可能需要查注册表（例如带附魔的成品）。
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
    from minecraft.item import ItemStack
    from minecraft.registries import HolderLookup
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from item import ItemStack  # type: ignore
    from registries import HolderLookup  # type: ignore


# ============================================================
# Ingredient
# ============================================================

class Ingredient(object):
    """
    对应 net.minecraft.world.item.crafting.Ingredient。

    它是「一组可接受的物品」。真实代码：
        () -> Ingredient.EMPTY
        public Ingredient getRepairIngredient()
        if (!potionBrewing.isIngredient(itemstack)) {...}

    **关键语义**：`test(stack)` 判的是「这个物品能不能当这个材料用」，
    而不是「两者相等」—— Ingredient 可以包含多个物品，也可以由标签定义。
    """

    EMPTY = None

    def __init__(self, items=None, tag=None):
        self._items = list(items) if items else []
        self._tag = tag

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def of(*items):
        """对应 Ingredient.of(ItemLike...)：由若干物品构成。"""
        flattened = []
        for item in items:
            from java_stdlib.java_arrays import JavaArray
            if isinstance(item, (list, tuple,JavaArray)):
                flattened.extend(item)
            else:
                flattened.append(item)
        return Ingredient(flattened)

    @staticmethod
    def ofItems(*items):
        return Ingredient.of(*items)

    @staticmethod
    def ofTag(tag):
        """对应 Ingredient.of(TagKey)：由标签定义。"""
        return Ingredient([], tag)

    # ---------------- 匹配 ----------------

    def test(self, stack):
        """
        对应 test(ItemStack)：这个物品能不能当本材料用。

        空材料（EMPTY）对任何东西都为假 —— 与 Java 一致，
        这样 `if (!ingredient.test(x))` 的写法在空材料下会走「不支持」分支。
        """
        if stack is None:
            return False
        if self.isEmpty():
            return False
        if hasattr(stack, "isEmpty") and stack.isEmpty():
            return False

        for candidate in self._items:
            if isinstance(candidate, Ingredient):
                if candidate.test(stack):
                    return True
            elif hasattr(stack, "isItem"):
                if stack.isItem(candidate):
                    return True
            elif stack == candidate:
                return True
        return False

    def isEmpty(self):
        """对应 isEmpty()：没有物品也没有标签。"""
        return len(self._items) == 0 and self._tag is None

    def getItems(self):
        return list(self._items)

    def getTag(self):
        return self._tag

    # ---------------- 展示与比较 ----------------

    def toString(self):
        if self.isEmpty():
            return u"Ingredient[EMPTY]"
        if self._tag is not None:
            return u"Ingredient[tag={}]".format(self._tag)
        return u"Ingredient[{} 项]".format(len(self._items))

    def equals(self, other):
        if not isinstance(other, Ingredient):
            return False
        return self._items == other._items and self._tag == other._tag

    def hashCode(self):
        return hash_code(u"{}|{}".format(len(self._items), self._tag))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


Ingredient.EMPTY = Ingredient()


# ============================================================
# 配方输入
# ============================================================

from minecraft.official_interfaces import RecipeInput


class SingleRecipeInput(RecipeInput):
    """
    对应 SingleRecipeInput：只有一个物品的输入。

    真实代码：`assemble(new SingleRecipeInput(input), registryAccess)`
    —— 熔炉这类「烧一个东西」的配方用它。
    """

    def __init__(self, stack):
        self._stack = stack if stack is not None else ItemStack()

    def getItem(self, index):
        if int(index) != 0:
            raise IllegalArgumentException(
                u"SingleRecipeInput 只有第 0 个位置")
        return self._stack

    def size(self):
        return 1

    def __repr__(self):
        return u"<SingleRecipeInput {}>".format(self._stack)


class CraftingInput(RecipeInput):
    """
    对应 CraftingInput：合成网格（例如 3x3）。

    它按行主序存物品，`ingredientToSlotsMap` 之类的辅助结构本实现不做 ——
    本层只需要「能按格子取物品」。
    """

    def __init__(self, width, height, items=None):
        self.width = int(width)
        self.height = int(height)
        expected = self.width * self.height
        if items is None:
            self._items = [ItemStack() for _index in range(expected)]
        else:
            self._items = list(items)
            if len(self._items) != expected:
                raise IllegalArgumentException(
                    u"CraftingInput {}x{} 需要 {} 个物品，收到 {}".format(
                        self.width, self.height, expected, len(self._items)))

    def size(self):
        return len(self._items)

    def getItem(self, index):
        index = int(index)
        if index < 0 or index >= len(self._items):
            raise IllegalArgumentException(
                u"合成网格越界: {}（共 {} 格）".format(index, len(self._items)))
        return self._items[index]

    def getWidth(self):
        return self.width

    def getHeight(self):
        return self.height

    def __repr__(self):
        return u"<CraftingInput {}x{}>".format(self.width, self.height)


# ============================================================
# 配方
# ============================================================

class Recipe(object):
    """
    对应 net.minecraft.world.item.crafting.Recipe。

    三类配方的共同点：匹配输入 + 产出结果。
    """

    def __init__(self, recipe_type=None):
        self._type = recipe_type

    def getType(self):
        """对应 getType()：配方类型（用于分类）。"""
        return self._type

    def matches(self, input, level=None):
        """对应 matches(RecipeInput, Level)：输入能不能做出这个配方。"""
        raise NotImplementedError()

    def assemble(self, input, registries=None):
        """
        对应 assemble(RecipeInput, HolderLookup.Provider)：产出结果。

        第二个参数是注册表上下文 —— 因为成品可能需要查注册表
        （例如带附件的物品）。本实现接受它但多数配方用不到。
        """
        raise NotImplementedError()

    def getResultItem(self, registries=None):
        """对应 getResultItem(...)：预览用结果（JEI 靠它显示）。"""
        return ItemStack()

    def getSerializer(self):
        return None

    def isSpecial(self):
        """对应 isSpecial()：特殊配方（不显示在配方书里）。"""
        return False

    def __repr__(self):
        return u"<{} {}>".format(type(self).__name__,
                                 java_to_string(self._type))


class AbstractCookingRecipe(Recipe):
    """
    对应 net.minecraft.world.item.crafting.AbstractCookingRecipe。

    熔炉/烟熏炉/高炉配方的基类。真实代码就是这样用的：
        ((AbstractCookingRecipe) recipe.value())
            .assemble(new SingleRecipeInput(input), registryAccess)
    """

    def __init__(self, ingredient, result, cooking_time=200,
                 experience=0.1, recipe_type=None):
        Recipe.__init__(self, recipe_type)
        self.ingredient = ingredient
        self.result = result
        self.cooking_time = int(cooking_time)
        self.experience = float(experience)

    def matches(self, input, level=None):
        """对应 matches：输入的物品要落在 ingredient 里。"""
        if input is None or input.size() < 1:
            return False
        return self.ingredient.test(input.getItem(0))

    def assemble(self, input, registries=None):
        """
        对应 assemble(...)：产出**一份**结果。

        注意不是产出 input 的数量份 —— Minecraft 的烧炼一次出一份，
        数量由调用方按需要叠加（真实代码里就是自己加的）。
        """
        if self.result is None:
            return ItemStack()
        return ItemStack(self.result.getItem(), self.result.getCount())

    def getResultItem(self, registries=None):
        return self.assemble(None, registries)

    def getCookingTime(self):
        return self.cooking_time

    def getExperience(self):
        return self.experience

    def getIngredient(self):
        return self.ingredient

    def __repr__(self):
        return u"<AbstractCookingRecipe {} -> {}>".format(
            self.ingredient, self.result)


class CraftingRecipe(Recipe):
    """
    对应 net.minecraft.world.item.crafting.CraftingRecipe。

    合成配方：按形状（shaped）或无形状（shapeless）匹配网格。
    """

    def __init__(self, ingredients, result, shaped=True, width=0, height=0,
                 recipe_type=None):
        Recipe.__init__(self, recipe_type)
        self.ingredients = list(ingredients)
        self.result = result
        self.shaped = bool(shaped)
        self.width = int(width)
        self.height = int(height)

    def matches(self, input, level=None):
        """
        对应 matches：网格里的每个非空格子都要能被对应材料接受。

        有形状配方还要求**尺寸与位置一致**（这是 Minecraft 的关键行为：
        3x3 的配方不能靠 1x1 的输入做出来）。
        """
        if self.shaped:
            if input.getWidth() != self.width \
                    or input.getHeight() != self.height:
                return False

        if input.size() != len(self.ingredients):
            return False

        for index in range(input.size()):
            stack = input.getItem(index)
            ingredient = self.ingredients[index]
            if stack is None or stack.isEmpty():
                # 空格子对应的材料也必须允许空
                if ingredient is not None and not ingredient.isEmpty():
                    return False
                continue
            if ingredient is None or not ingredient.test(stack):
                return False
        return True

    def assemble(self, input, registries=None):
        if self.result is None:
            return ItemStack()
        return ItemStack(self.result.getItem(), self.result.getCount())

    def getResultItem(self, registries=None):
        return self.assemble(None, registries)

    def getIngredients(self):
        return list(self.ingredients)

    def __repr__(self):
        return u"<CraftingRecipe {} -> {}>".format(
            u"shaped" if self.shaped else u"shapeless", self.result)


# ============================================================
# 配方类型与序列化器
# ============================================================

class RecipeType(object):
    """
    对应 net.minecraft.world.item.crafting.RecipeType。

    真实代码里用常量声明支持的类别：
        new RecipeType[]{RecipeTypes.CRAFTING}
    """

    def __init__(self, identifier):
        self._identifier = java_to_string(identifier)

    @staticmethod
    def of(identifier):
        return RecipeType(identifier)

    def toString(self):
        return self._identifier

    def equals(self, other):
        return isinstance(other, RecipeType) \
            and other._identifier == self._identifier

    def hashCode(self):
        return hash_code(self._identifier)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._identifier

    def __repr__(self):
        return u"<RecipeType {}>".format(self._identifier)


class RecipeSerializer(object):
    """
    对应 net.minecraft.world.item.crafting.RecipeSerializer。

    负责「配方怎么读写成数据」。真实代码把它注册进
    `BuiltInRegistries.RECIPE_SERIALIZER`：

        DeferredRegister.create(BuiltInRegistries.RECIPE_SERIALIZER, "modid")
    """

    def __init__(self, identifier=None, codec=None):
        self._identifier = java_to_string(identifier) \
            if identifier is not None else None
        self._codec = codec

    def setIdentifier(self, value):
        self._identifier = java_to_string(value)
        return self

    def getIdentifier(self):
        return self._identifier

    def fromJson(self, data):
        """对应 fromJson(...)：从数据建配方。子类覆盖。"""
        raise NotImplementedError()

    def toJson(self, recipe):
        """对应 toJson(...)：配方写回数据。子类覆盖。"""
        raise NotImplementedError()

    def __repr__(self):
        return u"<RecipeSerializer {}>".format(self._identifier or u"未注册")


class RecipeHolder(object):
    """
    对应 net.minecraft.world.item.crafting.RecipeHolder。

    它是「配方 + 它的 ID」。真实代码两个都要用：

        recipes.add((RecipeHolder<?>) recipe);          // 拿配方
        player.awardRecipes((Collection) recipes);      // 记录玩家做过什么
        byKey(ResourceLocation).ifPresent(recipe -> ...) // 按 ID 查

    所以 `value()` 与 `id()` 必须都能取到。
    """

    def __init__(self, recipe_id, recipe):
        if recipe is None:
            raise IllegalArgumentException(u"RecipeHolder 需要配方本体")
        self._id = recipe_id
        self._recipe = recipe

    def id(self):
        """对应 id()：配方 ID。"""
        return self._id

    def value(self):
        """
        对应 value()：配方本体。

        **这是访问配方的标准入口** —— 真实代码到处是
        `recipe.value()).assemble(...)`。
        """
        return self._recipe

    def equals(self, other):
        if not isinstance(other, RecipeHolder):
            return False
        return other._id == self._id

    def hashCode(self):
        return hash_code(java_to_string(self._id))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __repr__(self):
        return u"<RecipeHolder {}>".format(java_to_string(self._id))


# ============================================================
# RecipeManager
# ============================================================

class RecipeManager(object):
    """
    对应 net.minecraft.world.item.crafting.RecipeManager。

    真实代码：`level.getRecipeManager().byKey(ResourceLocation)`
    返回的是 Optional（Java 里 `.ifPresent(...)`）。
    本实现用「有 / 没有」两态表示，调用方通过 has 判断。
    """

    def __init__(self):
        self._by_id = {}
        self._by_type = {}

    def add(self, holder):
        """登记一个配方。"""
        if not isinstance(holder, RecipeHolder):
            raise IllegalArgumentException(
                u"RecipeManager.add 需要 RecipeHolder")
        key = java_to_string(holder.id())
        self._by_id[key] = holder
        recipe_type = holder.value().getType()
        if recipe_type is not None:
            self._by_type.setdefault(java_to_string(recipe_type), []).append(
                holder)
        return None

    def byKey(self, recipe_id):
        """
        对应 byKey(ResourceLocation)：按 ID 取配方。

        Java 返回 Optional<RecipeHolder<?>>；这里返回 holder 或 None，
        调用方按真假判断 —— 下面的 byKeyOrNone 明确表达这个语义。
        """
        return self._by_id.get(java_to_string(recipe_id))

    def byKeyOrNone(self, recipe_id):
        """明确版的 byKey（返回 None 表示没有）。"""
        return self._by_id.get(java_to_string(recipe_id))

    def byType(self, recipe_type):
        """按类型取所有配方。"""
        return list(self._by_type.get(java_to_string(recipe_type), []))

    def getRecipeIds(self):
        return sorted(self._by_id.keys())

    def size(self):
        return len(self._by_id)

    def clear(self):
        self._by_id = {}
        self._by_type = {}
        return None

    def __repr__(self):
        return u"<RecipeManager {} 个配方>".format(len(self._by_id))


class RecipeTypes(object):
    """
    对应原版的 RecipeTypes 常量表。

    真实代码在 JEI 插件里用：
        new RecipeType[]{RecipeTypes.CRAFTING}
        new RecipeType[]{RecipeTypes.SMELTING}
    """

    CRAFTING = RecipeType(u"minecraft:crafting")
    SMELTING = RecipeType(u"minecraft:smelting")
    BLASTING = RecipeType(u"minecraft:blasting")
    SMOKING = RecipeType(u"minecraft:smoking")
    CAMPFIRE_COOKING = RecipeType(u"minecraft:campfire_cooking")
    STONECUTTING = RecipeType(u"minecraft:stonecutting")
    SMITHING = RecipeType(u"minecraft:smithing")
    BREWING = RecipeType(u"minecraft:brewing")


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.item.crafting.Ingredient": Ingredient,
    "net.minecraft.world.item.crafting.Recipe": Recipe,
    "net.minecraft.world.item.crafting.RecipeInput": RecipeInput,
    "net.minecraft.world.item.crafting.SingleRecipeInput": SingleRecipeInput,
    "net.minecraft.world.item.crafting.CraftingInput": CraftingInput,
    "net.minecraft.world.item.crafting.AbstractCookingRecipe":
        AbstractCookingRecipe,
    "net.minecraft.world.item.crafting.CraftingRecipe": CraftingRecipe,
    "net.minecraft.world.item.crafting.RecipeType": RecipeType,
    "net.minecraft.world.item.crafting.RecipeTypes": RecipeTypes,
    "net.minecraft.world.item.crafting.RecipeSerializer": RecipeSerializer,
    "net.minecraft.world.item.crafting.RecipeHolder": RecipeHolder,
    "net.minecraft.world.item.crafting.RecipeManager": RecipeManager,
}


__all__ = [
    "Ingredient", "RecipeInput", "SingleRecipeInput", "CraftingInput",
    "Recipe", "AbstractCookingRecipe", "CraftingRecipe",
    "RecipeType", "RecipeTypes", "RecipeSerializer",
    "RecipeHolder", "RecipeManager",
    "JAVA_MAP",
]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)

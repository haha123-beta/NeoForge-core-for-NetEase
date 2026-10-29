# -*- coding: utf-8 -*-
# minecraft/advancement.py
# θ 层：进度触发、统计、战利品参数
#
# 真实用法（逐字来自反编译源码）：
#
#   // 进度触发 —— 玩家做出「可被进度识别」的动作时上报
#   CriteriaTriggers.PLACED_BLOCK.trigger((ServerPlayer) player, pos, stack);
#   CriteriaTriggers.ITEM_USED_ON_BLOCK.trigger((ServerPlayer) player, pos, stack);
#
#   // 统计 —— 玩家的计数器
#   player.awardStat(Stats.INTERACT_WITH_BREWINGSTAND);
#   player.awardStat(Stats.INTERACT_WITH_CRAFTING_TABLE);
#   player.awardStat(Stats.INTERACT_WITH_FURNACE);
#   player.awardStat(Stats.BLOCK_MINED.get(block));
#   player.awardStat(Stats.ITEM_USED.get(stack.getItem()));
#
#   // 战利品表参数
#   public List<ItemStack> getDrops(BlockState state, LootParams.Builder builder)
#   ...LootTableProviderEntry(ManaitaLoot::new, LootContextParamSets.CHEST)...
#
# 三者的共同点：**都是「向引擎报告发生了什么」**，
# 所以它们不需要真正的逻辑，只需要「记下来」。
# 但**必须真的记下来** —— 否则进度/统计既不会报错也不会生效，
# 玩家做完了却拿不到成就，这种 bug 最难查。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore


# ============================================================
# CriteriaTriggers
# ============================================================

class CriterionTrigger(object):
    """
    对应 net.minecraft.advancements.CriterionTrigger 的一个实例。

    真实代码只做一件事：`trigger(player, ...)` 上报「玩家做了这个动作」。
    引擎拿它去比对该玩家所有进度的条件。

    **为什么不能做成空操作**：`trigger` 不报错但也不记录的话，
    进度永远不会解锁，而且没有任何提示 —— 属于最难排查的一类问题。
    所以这里把每次触发都记进日志，便于自测与排查。
    """

    def __init__(self, trigger_id):
        self._id = java_to_string(trigger_id)
        self._triggers = []

    def getId(self):
        """对应 getId()：触发器的注册名。"""
        return self._id

    def trigger(self, player, *args):
        """
        对应 trigger(ServerPlayer, ...)：上报一次触发。

        返回是否记录成功。真实代码不检查返回值（Java 里是 void），
        这里返回 `self` 以便链式写法，同时把记录留在 `getHistory()` 里。
        """
        self._triggers.append({
            u"player": player,
            u"args": list(args),
        })
        return self

    def getHistory(self):
        """本实现新增：取触发历史（自测与排查用）。"""
        return list(self._triggers)

    def getTriggerCount(self):
        return len(self._triggers)

    def clear(self):
        """清空历史（自测隔离用）。"""
        self._triggers = []
        return None

    def toString(self):
        return u"CriterionTrigger[{}]".format(self._id)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{} 触发 {} 次>".format(self._id, len(self._triggers))


class CriteriaTriggers(object):
    """
    对应 net.minecraft.advancements.CriteriaTriggers。

    一个**静态常量表**，每个成员都是一个 `CriterionTrigger`。
    真实模组用到 `PLACED_BLOCK` 与 `ITEM_USED_ON_BLOCK`。

    这里把原版常用的都列出来 —— 列出多余的无害，
    缺一个就会让用了它的代码 AttributeError。
    """

    # 真实模组用到的两个
    PLACED_BLOCK = None
    ITEM_USED_ON_BLOCK = None

    # 原版常用的
    CONSUME_ITEM = None
    INVENTORY_CHANGED = None
    ENTER_BLOCK = None
    TICK = None
    LOCATION = None
    PLAYER_KILLED_ENTITY = None
    ENTITY_KILLED_PLAYER = None
    SUMMONED_ENTITY = None
    BRED_ANIMALS = None
    CURED_ZOMBIE_VILLAGER = None
    VILLAGER_TRADE = None
    TRADE = None
    ITEM_DURABILITY_CHANGED = None
    ENCHANTED_ITEM = None
    FILLED_BUCKET = None
    USED_ENDER_EYE = None
    BREWED_POTION = None
    CONSTRUCT_BEACON = None
    USED_TOTEM = None
    NETHER_TRAVEL = None
    EFFECTS_CHANGED = None
    SHOT_CROSSBOW = None
    KILLED_BY_CROSSBOW = None
    TARGET_BLOCK_HIT = None
    RECIPE_UNLOCKED = None
    RECIPE_CRAFTED = None
    FISHING_ROD_HOOKED = None
    CHANNELED_LIGHTNING = None
    SLEPT_IN_BED = None
    RAISED_ANIMAL = None
    USING_ITEM = None
    FALL_FROM_HEIGHT = None
    RIDE_ENTITY_IN_LAVA_TRIGGER = None
    LEVITATION = None
    DISTANCE = None
    ADVENTURE = None
    HERO_OF_THE_VILLAGE = None
    VOLUNTARY_EXILE = None
    SLIDE_DOWN_BLOCK = None
    BEE_NEST_DESTROYED = None
    ITEM_USED_ON_BLOCK_2 = None      # 占位：保持名字空间稳定

    @staticmethod
    def allTriggers():
        """列出所有已注册的触发器（诊断用）。"""
        found = {}
        for name in dir(CriteriaTriggers):
            if name.startswith(u"_") or name == u"allTriggers" \
                    or name == u"clearAll" or name == u"byId":
                continue
            value = getattr(CriteriaTriggers, name)
            if isinstance(value, CriterionTrigger):
                found[name] = value
        return found

    @staticmethod
    def byId(trigger_id):
        """按注册名找触发器（找不到返回 None）。"""
        wanted = java_to_string(trigger_id)
        for trigger in CriteriaTriggers.allTriggers().values():
            if trigger.getId() == wanted:
                return trigger
        return None

    @staticmethod
    def clearAll():
        """清空所有触发历史（自测隔离用）。"""
        for trigger in CriteriaTriggers.allTriggers().values():
            trigger.clear()
        return None


# 建出所有成员。用循环而不是一个个赋值 ——
# 少写一个就少一个 AttributeError 的坑，而且以后加成员只要往上面补名字。
#
# **必须用 setattr，不能写 `Cls.__dict__[名字] = ...`**：
# 类的 `__dict__` 是 mappingproxy，**只读**。
# 用下标赋值会报 `TypeError: 'mappingproxy' object does not support
# item assignment`，而且是在 import 期炸，一挂一大片
# （实测：17 个模块全部加载失败）。
def _install_triggers():
    for name in list(dir(CriteriaTriggers)):
        if name.startswith(u"_") or getattr(CriteriaTriggers, name) is not None:
            continue
        if name in (u"allTriggers", u"clearAll", u"byId"):
            continue
        setattr(CriteriaTriggers, name, CriterionTrigger(
            u"minecraft:{}".format(_camel_to_snake(name))))
    return None


def _camel_to_snake(name):
    """CONSUME_ITEM -> consume_item；用于生成注册名。"""
    return name.lower()


_install_triggers()


# ============================================================
# Stats
# ============================================================

class Stat(object):
    """
    对应 net.minecraft.stats.Stat。

    一条统计项。真实代码里 `Stats.INTERACT_WITH_FURNACE` 直接就是 Stat，
    而 `Stats.BLOCK_MINED.get(block)` 会按方块生成一条 Stat。
    """

    def __init__(self, stat_id, value=None):
        self._id = java_to_string(stat_id)
        self._value = value

    def getId(self):
        return self._id

    def getValue(self):
        """泛型参数（方块 / 物品 / 实体）。"""
        return self._value

    def equals(self, other):
        if not isinstance(other, Stat):
            return False
        return other._id == self._id

    def hashCode(self):
        return hash(self._id)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self._id

    def __repr__(self):
        return u"<Stat {}>".format(self._id)


class StatType(object):
    """
    对应 net.minecraft.stats.StatType。

    「一类统计」——`Stats.BLOCK_MINED` / `Stats.ITEM_USED` 都是它。
    `get(value)` 按参数生成（并缓存）一条具体 Stat。

    **必须缓存**：真实代码在热路径上反复 `Stats.ITEM_USED.get(item)`，
    每次新建对象会让「按对象身份聚合统计」失效
    （同注册表缓存那个教训）。
    """

    def __init__(self, stat_type_id):
        self._id = java_to_string(stat_type_id)
        self._cache = {}

    def getId(self):
        return self._id

    def get(self, value):
        """
        对应 get(T value)：按参数取统计项。

        缓存键用参数本身 —— 方块/物品都实现了 `__hash__`。
        参数为 None 时返回一个不缓存的临时项（Java 会 NPE，
        但这里选择宽容：宁可统计不准也不要让整个流程崩）。
        """
        if value is None:
            return Stat(u"{}:None".format(self._id))
        key = id(value)
        existing = self._cache.get(key)
        if existing is None or existing.getValue() is not value:
            existing = Stat(
                u"{}:{}".format(self._id, _describe(value)), value)
            self._cache[key] = existing
        return existing

    def clearCache(self):
        """清空缓存（自测隔离用）。"""
        self._cache = {}
        return None

    def __repr__(self):
        return u"<StatType {} 缓存 {}>".format(self._id, len(self._cache))


def _describe(value):
    """给统计项起个可读的名字（优先用方块/物品自己的标识）。"""
    for method_name in ("getDescriptionId", "getName", "toString"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return java_to_string(method())
            except Exception:
                continue
    return java_to_string(value)


class Stats(object):
    """
    对应 net.minecraft.stats.Stats。

    真实用法：
        player.awardStat(Stats.INTERACT_WITH_BREWINGSTAND);
        player.awardStat(Stats.BLOCK_MINED.get(block));
        player.awardStat(Stats.ITEM_USED.get(stack.getItem()));

    注意两类成员的**形式不同**：
        交互类      直接是 Stat（`INTERACT_WITH_*`）
        按参数类    是 StatType，要 `.get(x)`
    写错形式（对着 StatType 直接 awardStat）会静默统计不到，
    所以下面 `isStat` / `isStatType` 两个判定留着自测用。
    """

    # ---- 交互类：直接是 Stat ----
    INTERACT_WITH_BREWINGSTAND = None
    INTERACT_WITH_CRAFTING_TABLE = None
    INTERACT_WITH_FURNACE = None
    INTERACT_WITH_ANVIL = None
    INTERACT_WITH_BEACON = None
    INTERACT_WITH_BLAST_FURNACE = None
    INTERACT_WITH_SMOKER = None
    INTERACT_WITH_CAMPFIRE = None
    INTERACT_WITH_CARTOGRAPHY_TABLE = None
    INTERACT_WITH_GRINDSTONE = None
    INTERACT_WITH_LECTERN = None
    INTERACT_WITH_LOOM = None
    INTERACT_WITH_SMITHING_TABLE = None
    INTERACT_WITH_STONECUTTER = None
    INTERACT_WITH_SHULKER_BOX = None
    INTERACT_WITH_BELL = None
    OPEN_BARREL = None
    OPEN_CHEST = None
    OPEN_ENDERCHEST = None
    OPEN_SHULKER_BOX = None
    OPEN_HOPPER = None
    OPEN_DISPENSER = None
    OPEN_DROPPER = None
    PLAY_NOTEBLOCK = None
    TUNE_NOTEBLOCK = None
    TRIGGER_TRAPPED_CHEST = None

    # ---- 按参数类：是 StatType ----
    BLOCK_MINED = None
    ITEM_USED = None
    ITEM_BROKEN = None
    ITEM_CRAFTED = None
    ITEM_PICKED_UP = None
    ITEM_DROPPED = None
    ENTITY_KILLED = None
    ENTITY_KILLED_BY = None
    BLOCK_PLACED = None

    # ---- 简单计数类：直接是 Stat ----
    DEATHS = None
    MOB_KILLS = None
    PLAYER_KILLS = None
    FISH_CAUGHT = None
    ANIMALS_BRED = None
    LEAVE_GAME = None
    JUMP = None
    DROP = None
    DAMAGE_DEALT = None
    DAMAGE_TAKEN = None
    WALK_ONE_CM = None
    SPRINT_ONE_CM = None
    SWIM_ONE_CM = None
    FALL_ONE_CM = None
    FLY_ONE_CM = None
    TIME_SINCE_DEATH = None
    TIME_SINCE_REST = None
    SNEAK_TIME = None
    PLAY_ONE_MINUTE = None

    @staticmethod
    def isStat(value):
        """这个成员是不是可直接 awardStat 的 Stat。"""
        return isinstance(value, Stat)

    @staticmethod
    def isStatType(value):
        """这个成员是不是需要 `.get(x)` 的 StatType。"""
        return isinstance(value, StatType)

    @staticmethod
    def clearCaches():
        """清空所有 StatType 的缓存（自测隔离用）。"""
        for name in dir(Stats):
            value = getattr(Stats, name)
            if isinstance(value, StatType):
                value.clearCache()
        return None


def _install_stats():
    """
    建出 Stats 的所有成员。

    规则（照 Java 的命名分类）：
        INTERACT_WITH_* / OPEN_* / PLAY_* / TUNE_* / TRIGGER_*  -> Stat
        BLOCK_* / ITEM_* / ENTITY_*                             -> StatType
        其余                                                    -> Stat

    用规则而不是手写清单：手写容易把某个成员漏成 None，
    而 `Stats.XXX` 是 None 时 `awardStat(None)` 不会报错、只是统计不上。

    同 `_install_triggers`：**用 setattr**，类的 `__dict__` 是只读的。
    """
    for name in list(dir(Stats)):
        if getattr(Stats, name) is not None:
            continue
        if name.startswith(u"_") or name in (u"isStat", u"isStatType",
                                             u"clearCaches"):
            continue
        if not name.isupper():
            continue
        stat_id = u"minecraft:{}".format(name.lower())
        if name.startswith(u"BLOCK_") or name.startswith(u"ITEM_") \
                or name.startswith(u"ENTITY_"):
            setattr(Stats, name, StatType(stat_id))
        else:
            setattr(Stats, name, Stat(stat_id))
    return None


_install_stats()


# ============================================================
# LootParams
# ============================================================

class LootContextParamSet(object):
    """
    对应 net.minecraft.world.level.storage.loot.parameters.LootContextParamSet。

    「这套战利品表需要哪些上下文参数」——真实代码用
    `LootContextParamSets.CHEST` 之类来声明。
    """

    def __init__(self, param_set_id, required=None, optional=None):
        self._id = java_to_string(param_set_id)
        self._required = set(required or ())
        self._optional = set(optional or ())

    def getId(self):
        return self._id

    def getRequired(self):
        return set(self._required)

    def getOptional(self):
        return set(self._optional)

    def getAll(self):
        return self._required | self._optional

    def validate(self, params):
        """
        对应 validate(...)：检查参数够不够。

        缺必需参数时**报错而不是继续** —— 缺少上下文会让战利品表
        产出错误结果（例如本该有附魔的掉落没有），比直接失败更难查。
        """
        missing = []
        for name in sorted(self._required):
            if name not in params:
                missing.append(name)
        if missing:
            raise IllegalArgumentException(
                u"战利品上下文 {} 缺少必需参数: {}".format(
                    self._id, u", ".join(missing)))
        return True

    def __repr__(self):
        return u"<LootContextParamSet {}>".format(self._id)


class LootContextParamSets(object):
    """
    对应 net.minecraft.world.level.storage.loot.parameters.LootContextParamSets。

    真实代码用到 `LootContextParamSets.CHEST`。
    """

    CHEST = LootContextParamSet(
        u"minecraft:chest",
        required=(u"origin", u"this_entity"))
    BLOCK = LootContextParamSet(
        u"minecraft:block",
        required=(u"origin", u"block_state", u"tool"))
    ENTITY = LootContextParamSet(
        u"minecraft:entity",
        required=(u"origin", u"this_entity", u"damage_source"))
    FISHING = LootContextParamSet(
        u"minecraft:fishing",
        required=(u"origin", u"tool"))
    GIFT = LootContextParamSet(
        u"minecraft:gift",
        required=(u"origin", u"this_entity"))
    ADVANCEMENT_REWARD = LootContextParamSet(
        u"minecraft:advancement_reward",
        required=(u"origin", u"this_entity"))
    ADVANCEMENT_ENTITY = LootContextParamSet(
        u"minecraft:advancement_entity",
        required=(u"this_entity"))
    ARCHAEOLOGY = LootContextParamSet(
        u"minecraft:archaeology",
        required=(u"origin", u"tool"))
    PIGLIN_BARTER = LootContextParamSet(
        u"minecraft:piglin_barter",
        required=(u"origin", u"this_entity"))
    SELECTOR = LootContextParamSet(
        u"minecraft:selector",
        required=(u"origin",))

    @staticmethod
    def allParamSets():
        """列出全部参数集。"""
        found = {}
        for name in dir(LootContextParamSets):
            if name.startswith(u"_") or name in (u"allParamSets",):
                continue
            value = getattr(LootContextParamSets, name)
            if isinstance(value, LootContextParamSet):
                found[name] = value
        return found


class LootParams(object):
    """
    对应 net.minecraft.world.level.storage.loot.LootParams。

    「生成战利品时能用到的上下文」——掉落位置、工具、击杀者等等。
    真实代码用它的内部类 `Builder` 逐步收集：

        public List<ItemStack> getDrops(BlockState state, LootParams.Builder builder)

    **为什么要有 validate**：战利品表声明了它需要哪些参数
    （`LootContextParamSet`），参数不全时 Java 会抛异常。
    照抄这个行为很重要 —— 少了必需参数还继续跑的话，
    产出的是「看起来正常但内容错」的战利品，玩家只会觉得掉率诡异。
    """

    def __init__(self, param_set, params=None):
        if param_set is None:
            raise IllegalArgumentException(u"LootParams 需要 param_set")
        self._param_set = param_set
        self._params = dict(params or {})
        param_set.validate(self._params)

    def getParameter(self, name):
        """对应 getParameter(LootContextParam)。"""
        return self._params.get(java_to_string(name))

    def hasParameter(self, name):
        return java_to_string(name) in self._params

    def getParamSet(self):
        return self._param_set

    def toDict(self):
        return dict(self._params)

    def withParameter(self, name, value):
        """返回带额外参数的新实例（不修改自身）。"""
        merged = dict(self._params)
        merged[java_to_string(name)] = value
        return LootParams(self._param_set, merged)

    def __repr__(self):
        return u"<LootParams {} {} 项>".format(self._param_set.getId(),
                                               len(self._params))


class LootParamsBuilder(object):
    """
    对应 net.minecraft.world.level.storage.loot.LootParams.Builder。

    真实用法：`LootParams.Builder` 作为 `getDrops` 的形参出现。
    链式调用（每个 with* 都返回自身），最后 `create(...)` 出 LootParams。
    """

    def __init__(self, level=None, param_set=None):
        self._level = level
        self._param_set = param_set
        self._params = {}

    def withParameter(self, name, value):
        self._params[java_to_string(name)] = value
        return self

    def withLuck(self, luck):
        """对应 withLuck(float)：幸运值影响掉落数量。"""
        self._params[u"luck"] = float(luck)
        return self

    def withOptionalParameter(self, name, value):
        """对应 withOptionalParameter：给了就用，None 就跳过。"""
        if value is not None:
            self._params[java_to_string(name)] = value
        return self

    def getLevel(self):
        return self._level

    def getParameter(self, name):
        return self._params.get(java_to_string(name))

    def create(self, param_set=None):
        """对应 create(LootContextParamSet)：造出 LootParams。"""
        target = param_set if param_set is not None else self._param_set
        if target is None:
            raise IllegalArgumentException(
                u"create 需要 LootContextParamSet（构造 Builder 时给或这里给）")
        return LootParams(target, self._params)

    def __repr__(self):
        return u"<LootParams.Builder {} 项>".format(len(self._params))


# `LootParams.Builder` 在 Java 里是内部类，翻译层会找这个名字
LootParams.Builder = LootParamsBuilder


# ============================================================
# 名称映射表
# ============================================================

_P = "net.minecraft.world.level.storage.loot."
_PARAM_P = _P + "parameters."

JAVA_MAP = {
    "net.minecraft.advancements.CriteriaTriggers": CriteriaTriggers,
    "net.minecraft.advancements.CriterionTrigger": CriterionTrigger,
    "net.minecraft.stats.Stats": Stats,
    "net.minecraft.stats.Stat": Stat,
    "net.minecraft.stats.StatType": StatType,
    _P + "LootParams": LootParams,
    _P + "LootParams$Builder": LootParamsBuilder,
    _PARAM_P + "LootContextParamSet": LootContextParamSet,
    _PARAM_P + "LootContextParamSets": LootContextParamSets,
}


__all__ = [
    "CriterionTrigger", "CriteriaTriggers",
    "Stat", "StatType", "Stats",
    "LootContextParamSet", "LootContextParamSets",
    "LootParams", "LootParamsBuilder",
    "JAVA_MAP",
]

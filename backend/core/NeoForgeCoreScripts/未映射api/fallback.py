# -*- coding: utf-8 -*-
# 未映射api/fallback.py
# ω 层：未映射 API 的兜底处理
#
# 要解决的问题
# ------------
# 核心包不可能把 NeoForge + Minecraft 的每一个类都实现完
# （当前覆盖 19.7%，缺口 278 种）。那么遇到没实现的 API 时该怎么办？
#
# 这个选择直接决定模组是「跑不起来」还是「崩掉」，三种做法的取舍：
#
#   raise  —— 立刻暴露问题，但可能因为一个纯视觉方法让整个模组崩掉
#   noop   —— 模组能跑起来，但会掩盖真问题（方块没了却不报错）
#   stub   —— 返回一个中性替身，让上层逻辑继续走
#
# **没有一种做法能通用**，所以按 API 的**类别**分别定策略：
#
#   注册/数据   → raise   跳了会让方块物品静默消失，绝不能忍
#   世界写入    → raise   写不进去还继续跑，状态会越错越离谱
#   网络        → raise   包发不出去，联机功能等于坏的
#   渲染/音效   → noop    只影响观感；让模组因为一个粒子效果崩掉不值得
#   翻译/客户端 → stub    返回键本身或空串，界面上还能看出问题
#
# 另一个关键点：**兜底必须留痕**。所有走到兜底的调用都记进
# `FallbackStats`，并可通过 `report_lines()` 导出一份清单 ——
# 这就是「等引擎确认后要补哪些接口」的待办列表。
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
# 处理策略
# ============================================================

class Severity(object):
    """
    未映射 API 的处理方式。取值是字符串常量，便于跨层传递与打印。
    """

    RAISE = u"raise"    # 抛异常（问题严重，不能悄悄过）
    WARN = u"warn"      # 记一条警告后返回 None
    NOOP = u"noop"      # 静默返回 None（只影响观感）
    STUB = u"stub"      # 返回中性替身对象
    NULL = u"null"      # 返回 None（与 NOOP 同义，语义上强调「没有值」）

    ALL = (RAISE, WARN, NOOP, STUB, NULL)


class Policy(object):
    """一条策略：某个类别下的未映射 API 怎么处理。"""

    def __init__(self, severity, category, reason):
        if severity not in Severity.ALL:
            raise IllegalArgumentException(
                u"未知的处理方式: {}（应为 {}）".format(
                    severity, u"/".join(Severity.ALL)))
        self.severity = severity
        self.category = category
        self.reason = reason

    def __repr__(self):
        return u"<Policy {} [{}] {}>".format(self.severity, self.category,
                                             self.reason)


# ============================================================
# 默认策略表
# ============================================================
#
# 键是「API 类别」，值是 Policy。
# 类别的判定见 classify_api()。

DEFAULT_POLICIES = {
    u"registry": Policy(
        Severity.RAISE, u"registry",
        u"注册缺失会让方块/物品静默消失，必须立刻暴露"),

    u"data": Policy(
        Severity.RAISE, u"data",
        u"数据读写缺失会让世界状态越错越离谱，必须立刻暴露"),

    u"world-write": Policy(
        Severity.WARN, u"world-write",
        u"方块写入缺失会影响游戏逻辑，但先记录再说 —— "
        u"让模组整个崩掉比少放一个方块更糟"),

    u"network": Policy(
        Severity.RAISE, u"network",
        u"网络包发不出去，联机功能等于坏的，必须立刻暴露"),

    u"render": Policy(
        Severity.NOOP, u"render",
        u"渲染只影响观感；因为一个粒子效果让模组崩掉不值得"),

    u"sound": Policy(
        Severity.NOOP, u"sound",
        u"音效只影响观感"),

    u"translation": Policy(
        Severity.STUB, u"translation",
        u"翻译键缺失时回退为键本身，界面上还能看出问题"),

    u"client-ui": Policy(
        Severity.NOOP, u"client-ui",
        u"客户端界面在基岩版是另一套体系，跳过后模组仍可运行"),

    u"event": Policy(
        Severity.WARN, u"event",
        u"事件类型缺失会影响功能，但不该让启动失败"),

    u"item": Policy(
        Severity.WARN, u"item",
        u"物品/方块/实体类缺失会影响游戏内容，但不该让模组整个起不来"),

    u"util": Policy(
        Severity.RAISE, u"util",
        u"工具类（数学、字符串、容器）缺失说明基础层有洞，必须暴露"),

    u"unknown": Policy(
        Severity.WARN, u"unknown",
        u"无法归类时记录警告后继续 —— "
        u"拿不准就不要让模组崩，但必须留下痕迹以便后续补"),
}

# 关键词 -> 类别。
#
# 判定方式是**子串匹配**（`keyword in 类名与上一段包名`），
# 所以这个元组的顺序是判定优先级的唯一依据：
# 一个名字同时含多个类别的关键词时，排前面的赢。
#
# 为什么 sound 必须排在 event 前面：
#   `SoundEvent` 里既有 "sound" 也有 "event"。
#   按「更具体的语义」排，sound 只影响观感（可 noop），
#   event 缺失会警告 —— 前者对模组更宽容，是对的。
# 为什么 data 必须排在 translation 前面：
#   `DataComponentType` 里含子串 "component"，
#   会被翻译规则误吞成 translation（实测踩到）。
#   它是数据组件，缺失要 raise，不能降级成「回退为键」。
#   （Minecraft 的 Component 是文本，DataComponent 是数据，只差一个词。）
CLASSIFY_RULES = (
    ("registry", (u"registry", u"deferredregister", u"deferredholder")),
    ("network", (u"network", u"payload", u"packet", u"streamcodec")),
    ("data", (u"datacomponent", u"compoundtag", u"nbt", u"saveddata",
              u"attachment", u"capability", u"serializ")),
    ("translation", (u"i18n", u"translation", u"language", u"component")),
    ("client-ui", (u"screen", u"gui", u"menu", u"container")),
    ("render", (u"render", u"buffer", u"model", u"texture", u"shader",
                u"pose", u"matrix", u"vertex", u"font", u"draw")),
    ("sound", (u"sound", u"audio")),
    ("world-write", (u"level", u"world", u"chunk", u"biome", u"dimension")),
    ("item", (u"item", u"block", u"entity", u"inventory", u"recipe")),
    ("event", (u"event",)),
    ("util", (u"util", u"math", u"mth", u"string", u"list", u"map",
              u"set", u"stream", u"optional", u"pair", u"triple")),
)


def classify_api(java_name):
    """
    给一个 Java 全限定名归类，用于选策略。

    取**全名的最后两段**参与匹配，避免包名里的 `world` 之类干扰
    （例如 `net.minecraft.world.item.ItemStack` 应该归 util/item，
    而不是因为包名里有 world 就被当成 world-write）。
    """
    if not java_name:
        return u"unknown"
    name = java_to_string(java_name)
    parts = name.split(u".")
    # 类名 + 上一段包名，例如 "block.BlockState"
    tail = u".".join(parts[-2:]) if len(parts) >= 2 else name
    lowered = tail.lower()

    for category, keywords in CLASSIFY_RULES:
        for keyword in keywords:
            if keyword.lower() in lowered:
                return category
    return u"unknown"


def policy_for(java_name, policies=None):
    """取某个 Java 名对应的策略。"""
    table = policies if policies is not None else DEFAULT_POLICIES
    category = classify_api(java_name)
    policy = table.get(category)
    if policy is None:
        policy = table[u"unknown"]
    return policy


# ============================================================
# 统计：兜底必须留痕
# ============================================================

class FallbackStats(object):
    """
    记录所有走到兜底的调用。

    这是 ω 层最有价值的产出：一份「还缺哪些接口」的真实清单，
    按出现次数排序就是补齐的优先级。
    """

    def __init__(self):
        self.entries = []       # [(java_name, member, severity, category)]

    def note(self, java_name, member=None, severity=None, category=None):
        self.entries.append((java_name, member, severity, category))
        return None

    def count(self):
        return len(self.entries)

    def isClean(self):
        return len(self.entries) == 0

    def byJavaName(self):
        """按 Java 名聚合，返回 {名字: 次数}。"""
        grouped = {}
        for java_name, _member, _severity, _category in self.entries:
            grouped[java_name] = grouped.get(java_name, 0) + 1
        return grouped

    def bySeverity(self):
        grouped = {}
        for _java_name, _member, severity, _category in self.entries:
            key = severity or u"?"
            grouped[key] = grouped.get(key, 0) + 1
        return grouped

    def report_lines(self, limit=30):
        """生成待办清单（按出现次数排序）。"""
        lines = []
        if self.isClean():
            lines.append(u"没有走到任何兜底 —— 覆盖完整")
            return lines

        lines.append(u"共 {} 次调用走到了兜底".format(self.count()))
        severity_counts = self.bySeverity()
        for severity in sorted(severity_counts):
            lines.append(u"  {}: {} 次".format(severity,
                                               severity_counts[severity]))

        lines.append(u"  按缺失的 API 排序（次数多的优先补）:")
        grouped = self.byJavaName()
        ordered = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
        for java_name, times in ordered[:limit]:
            lines.append(u"    {:>3} 次  {}".format(times, java_name))
        if len(ordered) > limit:
            lines.append(u"    …还有 {} 种".format(len(ordered) - limit))
        return lines

    def clear(self):
        self.entries = []
        return None

    def __repr__(self):
        return u"<FallbackStats {} 条>".format(self.count())


# 全局统计（真机上一个进程一份）
STATS = FallbackStats()


# ============================================================
# 中性替身
# ============================================================

class UnmappedClass(object):
    """
    未映射类的替身 —— **链式调用友好**版。

    行为：
      - 任何属性访问返回一个可调用对象；
      - 该可调用对象**返回替身自身**，所以 `a().b().c()` 能一路走完
        （实测踩到：原本返回 None，`delegate.a().b()` 立刻 AttributeError，
        正是替身本该防住的那种崩溃）；
      - 每次访问都记进统计。

    什么时候用它：调用方主要是「做一件事」（播放音效、发个包、记个日志），
    结果值不被使用。这类 API 缺失时让链路走完是最优解。

    什么时候**不要**用它：调用方需要真实返回值（例如取方块状态再判断）。
    那种情况应该用 `ChainableUnmapped` 之外的策略（raise / stub），
    否则会拿到一个「看起来像对象但什么都不是」的东西，
    比直接报错更难查。
    """

    def __init__(self, java_name=u"<unknown>", return_self=True):
        # 用 object.__setattr__ 避免重写的 __setattr__ 干扰
        object.__setattr__(self, "_java_name", java_to_string(java_name))
        object.__setattr__(self, "_accessed", [])
        object.__setattr__(self, "_return_self", bool(return_self))

    def __getattr__(self, name):
        # 私有属性不拦截：否则 hasattr(obj, "_x") 永远为真，
        # 会干扰 copy / pickle / 调试器之类的内省。
        if name.startswith(u"_"):
            raise AttributeError(name)

        java_name = object.__getattribute__(self, "_java_name")
        accessed = object.__getattribute__(self, "_accessed")
        accessed.append(java_name + u"." + name)

        STATS.note(java_name, name, Severity.NOOP, u"noop-member")

        if object.__getattribute__(self, "_return_self"):
            # 返回「可调用且返回自身」的对象 —— 两种写法都支持：
            #   obj.thing()      取属性后调用
            #   obj.thing.method() 取属性后继续取属性（少见但真实代码有）
            return _SelfReturning(self)

        def _noop(*args, **kwargs):
            return None

        _noop.__name__ = str(name)
        return _noop

    def __call__(self, *args, **kwargs):
        java_name = object.__getattribute__(self, "_java_name")
        STATS.note(java_name, u"__call__", Severity.NOOP, u"noop-call")
        return None

    # 常见协议方法给安全实现，避免 isinstance / 打印 / 遍历时出问题
    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    # Python 2 用 __nonzero__，两个都定义
    __nonzero__ = __bool__

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)

    def getJavaName(self):
        return object.__getattribute__(self, "_java_name")

    def accessedMembers(self):
        return list(object.__getattribute__(self, "_accessed"))

    # dunder 必须真实定义，不能靠 __getattr__ 兜：
    # Python 对 `str(obj)` 走的是类型槽位，不会经过 __getattr__。
    # （实测踩到：只定义了 __repr__，调用方 .toString() 拿到 None。）
    def __str__(self):
        return u"<未映射 {}>".format(
            object.__getattribute__(self, "_java_name"))

    def toString(self):
        return self.__str__()

    def __repr__(self):
        return self.__str__()


class _SelfReturning(object):
    """
    `UnmappedClass` 取属性后拿到的对象：可调用，且**返回原替身**。

    这样 `delegate.a().b().c()` 里的每一个环节
    既完成了「调用」，又把链路交回给替身继续往下走。
    """

    def __init__(self, owner):
        self._owner = owner

    def __call__(self, *args, **kwargs):
        return self._owner

    def __getattr__(self, name):
        if name.startswith(u"_"):
            raise AttributeError(name)
        # 继续取属性也交回替身（真实代码里有 `obj.a.b.c()` 这种）
        return getattr(self._owner, name)

    def __repr__(self):
        return u"<未映射调用 {}>".format(self._owner.getJavaName())


# ============================================================
# 兜底处理器
# ============================================================

class FallbackHandler(object):
    """
    统一的兜底入口。

    所有「找不到实现」的地方都调 `handle(java_name)`，
    由它按策略决定抛异常 / 记录 / 返回替身。
    """

    def __init__(self, policies=None, stats=None, logger=None):
        self.policies = policies if policies is not None else DEFAULT_POLICIES
        self.stats = stats if stats is not None else STATS
        self._logger = logger

    # ---------------- 主入口 ----------------

    def handle(self, java_name, member=None):
        """
        处理一次「未映射」访问。

        按策略返回替身或抛异常；无论哪种都会先记进统计 ——
        连 raise 也记，因为「崩了」同样是需要知道的信息。
        """
        policy = policy_for(java_name, self.policies)
        self.stats.note(java_name, member, policy.severity, policy.category)

        if policy.severity == Severity.RAISE:
            raise NotImplementedError(
                u"未实现的 API: {}{}（类别 {}）—— {}".format(
                    java_name,
                    u"." + java_to_string(member) if member else u"",
                    policy.category, policy.reason))

        if policy.severity == Severity.STUB:
            # 翻译类的替身就是「键本身」，见 Component 的处理
            return java_to_string(java_name)

        if policy.severity == Severity.WARN:
            self._log(u"[兜底] 未映射的 API: {}（类别 {}）—— {}".format(
                java_name, policy.category, policy.reason))
            return None

        # NOOP / NULL
        return None

    def handleClass(self, java_name):
        """
        处理「整个类都没有映射」的情况。

        与 handle 的区别：返回的是**类替身**而不是实例 ——
        调用方通常要拿它去 `new`，所以给一个能构造的类。
        """
        policy = policy_for(java_name, self.policies)
        self.stats.note(java_name, None, policy.severity, policy.category)

        if policy.severity == Severity.RAISE:
            raise NotImplementedError(
                u"未实现的类: {}（类别 {}）—— {}".format(
                    java_name, policy.category, policy.reason))

        if policy.severity == Severity.STUB:
            return _string_stub_class(java_name)

        if policy.severity == Severity.WARN:
            self._log(u"[兜底] 未映射的类: {}（类别 {}）—— {}".format(
                java_name, policy.category, policy.reason))

        return _unmapped_class_for(java_name)

    # ---------------- 内部 ----------------

    def _log(self, text):
        if self._logger is not None:
            self._logger(text)
        else:
            print(text)

    def reportLines(self, limit=30):
        return self.stats.report_lines(limit)

    def __repr__(self):
        return u"<FallbackHandler {} 条记录>".format(self.stats.count())


def _unmapped_class_for(java_name):
    """造一个能 `new` 的替身类（把 java_name 绑进实例）。"""

    class _Generated(object):
        def __init__(self, *args, **kwargs):
            # 直接存，不用 __setattr__ 转发 —— 属性名带下划线，
            # 委托对象的 __getattr__ 会拒绝下划线开头的名字。
            object.__setattr__(
                self, "_delegate", UnmappedClass(java_name))

        def __getattr__(self, name):
            if name.startswith(u"_"):
                raise AttributeError(name)
            return getattr(object.__getattribute__(self, "_delegate"), name)

        def __call__(self, *args, **kwargs):
            java_name_text = java_to_string(java_name)
            STATS.note(java_name_text, u"__call__", Severity.NOOP,
                       u"noop-call")
            return None

        def getJavaName(self):
            return java_to_string(java_name)

        def __str__(self):
            return u"<未映射类 {}>".format(java_to_string(java_name))

        def __repr__(self):
            return self.__str__()

    _Generated.__name__ = str(java_to_string(java_name).split(u".")[-1])
    return _Generated


def _string_stub_class(java_name):
    """翻译类没有实现时，退化成「原样返回键」的替身。"""

    class _StringStub(object):
        def __init__(self, key=None, *args, **kwargs):
            self._key = java_to_string(key) if key is not None \
                else java_to_string(java_name)

        def getString(self):
            return self._key

        def toString(self):
            return self._key

        def __str__(self):
            return self._key

        def __repr__(self):
            return u"<翻译替身 {}>".format(self._key)

    return _StringStub


# ============================================================
# 一个统一的模块级入口
# ============================================================

DEFAULT_HANDLER = FallbackHandler()


def resolve_or_fallback(java_name, implementation=None, member=None):
    """
    取实现；没有就走兜底。

    翻译层或核心包的入口用这个函数，而不是自己写 if/else ——
    策略集中在一处才可能保持一致。
    """
    if implementation is not None:
        return implementation
    return DEFAULT_HANDLER.handle(java_name, member)


__all__ = [
    "Severity", "Policy", "DEFAULT_POLICIES", "CLASSIFY_RULES",
    "classify_api", "policy_for",
    "FallbackStats", "STATS",
    "UnmappedClass", "FallbackHandler", "DEFAULT_HANDLER",
    "resolve_or_fallback",
]

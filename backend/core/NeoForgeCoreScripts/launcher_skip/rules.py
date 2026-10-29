# -*- coding: utf-8 -*-
# launcher_skip/rules.py
# δ 层：启动层跳过规则
#
# Legacy decision table for old launcher_skip.sequence only.
# The current independent content loader does not use these skip decisions.
# A skip here is NOT proof of equivalence or permission to discard a mod feature.
# Current lifecycle stages run in core.translated_loader.activate; unported Mixin
# requirements block in core.alpha_neoforge / translated_loader.
# enqueueWork runs synchronously in the old event implementation and is NOT
# equivalent to NeoForge's queued Future / parallel loading ordering.

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib.lang import java_to_string
except ImportError:
    from lang import java_to_string  # type: ignore


# ============================================================
# 决策
# ============================================================

class Decision(object):
    """一次跳过判定的结果。"""

    def __init__(self, action, reason, category=None):
        self.action = action          # "skip" / "run" / "defer"
        self.reason = reason
        self.category = category

    def isSkip(self):
        return self.action == u"skip"

    def isRun(self):
        return self.action == u"run"

    def isDefer(self):
        return self.action == u"defer"

    def toString(self):
        return u"{}: {}".format(self.action, self.reason)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Decision {}>".format(self.toString())


# ============================================================
# 规则分类
# ============================================================

# 「跳过」的类别及理由。每一项都要有具体理由 ——
# 无声地跳过等于埋雷，将来没人知道为什么某个功能不见了。
SKIP_REASONS = {
    u"loader-client-lifecycle":
        u"客户端专属的加载器阶段，基岩版没有对应的客户端初始化时机",
    u"loader-internal":
        u"加载器内部流程（加载完成、跨模组通信排队），基岩版没有这些阶段",
    u"client-render":
        u"客户端渲染管线，基岩版是另一套体系",
    u"client-screen":
        u"客户端界面，基岩版用网易的 UI 体系",
    u"client-input":
        u"客户端输入映射，基岩版按键由引擎管理",
    u"client-extension":
        u"客户端扩展注册（物品外观扩展之类），基岩版无对应物",
    u"loader-metadata":
        u"加载器元数据（mods.toml / 版本约束），由核心包自己的清单替代",
}

# 「改为直接执行」的类别及理由。
#
# 为什么单列一类而不是也跳过：
#   `enqueueWork` 本身**不是客户端行为**，它只是「把任务排到主线程」。
#   基岩版脚本就在主线程，所以正确做法是**立刻执行**（语义不等价，需审查顺序依赖），
#   而不是丢掉任务。能执行就不要跳过 —— 跳过是不可逆的信息丢失。
DEFER_REASONS = {
    u"thread-handoff":
        u"原本是把任务排到主线程；基岩版已在主线程，改为直接执行"
        u"（排队会因无人排空而永不执行）",
    u"chunk-sync":
        u"原本是等待区块同步；基岩版无此阶段，改为直接执行",
}

# 「必须执行」的类别及理由。
# 列出来是为了让「不能跳」这件事在代码里有据可查，而不是靠记忆。
RUN_REASONS = {
    u"registry":
        u"注册：跳过会让方块/物品全部消失，而且不报错",
    u"config":
        u"配置：跳过会让模组读到默认值，用户改了配置也不生效",
    u"data":
        u"数据/资源：跳过会让模型、配方、语言文件加载不到",
    u"core-init":
        u"核心初始化：模组的 *_Core.init() 负责建立注册项本身",
    u"network":
        u"网络：跳过会让联机包收发失效",
    u"event":
        u"游戏事件：这是模组的实际功能，必须跑",
    u"common-setup":
        u"双端通用的初始化：里面的副作用（建立派生对象、注册表补齐）"
        u"在基岩版同样需要，不该跳",
}


# ============================================================
# 跳过名单：按 Java 类名
# ============================================================

# **客户端专属**的加载器阶段事件 —— 这些跳过。
#
# 注意与下面「双端通用」的区别：
#   FMLClientSetupEvent   只在客户端跑 → 跳过
#   FMLCommonSetupEvent   双端都跑，副作用有意义 → **执行**
# 最初我把它们整类当「加载器生命周期」跳过，等于悄悄丢掉了
# 模组的通用初始化（自测抓到了这个设计错误）。
CLIENT_ONLY_LIFECYCLE_EVENTS = (
    "net.neoforged.fml.event.lifecycle.FMLClientSetupEvent",
)

# 加载器**内部**流程事件 —— 基岩版没有这些阶段，跳过。
#
#   FMLLoadCompleteEvent    加载器跑完了（基岩版无此概念）
#   InterModEnqueueEvent    跨模组通信的排队阶段
#   InterModProcessEvent    跨模组通信的处理阶段
LOADER_INTERNAL_EVENTS = (
    "net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent",
    "net.neoforged.fml.event.lifecycle.InterModEnqueueEvent",
    "net.neoforged.fml.event.lifecycle.InterModProcessEvent",
)

# 双端通用的初始化事件 —— **必须执行**（不要跳）。
COMMON_SETUP_EVENTS = (
    "net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent",
    "net.neoforged.fml.event.lifecycle.FMLDedicatedServerSetupEvent",
)

# 客户端事件：整类跳过。
# 真实模组用到的：
#   RegisterShadersEvent            7 次
#   RegisterKeyMappingsEvent        3 次
#   RegisterMenuScreensEvent        3 次
#   RegisterClientExtensionsEvent   3 次
#
# 注意结尾都有点：漏了点会让 `client.extensions.common` 这类
# 更深的包名匹配不上（实测踩到）。
CLIENT_EVENT_PREFIXES = (
    "net.neoforged.neoforge.client.",
    "net.minecraft.client.",
)

# 「必须执行」的事件：即使名字里带 Register 也不能跳。
#
# 为什么单列：`RegisterPayloadHandlersEvent` 和 `RegisterClientExtensionsEvent`
# 长得几乎一样，但前者是联机收发的必要注册，后者纯客户端外观。
# 靠前缀匹配会一起跳掉，所以必须显式白名单。
MUST_RUN_EVENTS = (
    "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent",
    "net.neoforged.neoforge.registries.RegisterEvent",
    "net.neoforged.neoforge.registries.NewRegistryEvent",
    "net.neoforged.fml.event.config.ModConfigEvent",
    "net.neoforged.fml.event.config.ModConfigEvent$Loading",
    "net.neoforged.fml.event.config.ModConfigEvent$Reloading",
)

# 需要「改为直接执行」的方法（而不是跳过）。
#
# `enqueueWork` 是唯一需要这一档的：它只是线程交接，不是客户端行为。
DEFER_METHODS = {
    "net.neoforged.fml.event.lifecycle.ParallelDispatchEvent": {
        "enqueueWork": u"thread-handoff",
    },
}

# 加载器元数据相关（mods.toml 等）。核心包用自己的清单替代，不读这些。
LOADER_METADATA_CLASSES = (
    "net.neoforged.fml.loading.FMLPaths",
    "net.neoforged.fml.loading.FMLLoader",
    "net.neoforged.neoforge.internal.versions.neoforge.NeoForgeVersion",
)

# 方法级别的必须执行规则：{类名: [方法名]}
#
# 注意 FMLEnvironment 不在 LOADER_METADATA_CLASSES 里：
# 它的 `dist` 字段被 `getEnvSpecific(...)` 用来在双端之间选择实现，
# 属于**必须执行**的运行时判断，不是可丢的元数据。
METHOD_RULES = {
    "net.neoforged.fml.ModContainer": {
        "registerConfig": u"run",
        "getModId": u"run",
        "getModEventBus": u"run",
    },
    "net.neoforged.neoforge.registries.DeferredRegister": {
        "register": u"run",
    },
}


# ============================================================
# 判定
# ============================================================

def classify(java_name):
    """
    给一个 Java 类名分类，返回类别字符串；无法归类返回 None。

    顺序很重要：**先判必须执行，再判跳过** ——
    否则 `RegisterPayloadHandlersEvent` 会被客户端前缀规则吃掉。
    """
    if java_name is None:
        return None
    name = java_to_string(java_name)

    for must_run in MUST_RUN_EVENTS:
        if name == must_run or name.startswith(must_run + "$"):
            return u"must-run-event"

    # 双端通用初始化：必须执行，不能按「加载器事件」一刀切跳过
    for common in COMMON_SETUP_EVENTS:
        if name == common or name.startswith(common + "$"):
            return u"common-setup"

    for client_only in CLIENT_ONLY_LIFECYCLE_EVENTS:
        if name == client_only or name.startswith(client_only + "$"):
            return u"loader-client-lifecycle"

    for internal in LOADER_INTERNAL_EVENTS:
        if name == internal or name.startswith(internal + "$"):
            return u"loader-internal"

    if name in LOADER_METADATA_CLASSES:
        return u"loader-metadata"

    for prefix in CLIENT_EVENT_PREFIXES:
        if name.startswith(prefix):
            # 子类别的判断必须**放在兜底之前** ——
            # 最初先 return client-render，导致 client-screen / client-input /
            # client-extension 三个分支永远不可达（自测抓到）。
            lowered = name.lower()
            if u".gui." in lowered or u".screens." in lowered \
                    or u"screen" in lowered:
                return u"client-screen"
            if u"keymapping" in lowered or u".input." in lowered:
                return u"client-input"
            if u"extensions" in lowered:
                return u"client-extension"
            return u"client-render"

    return None


def decide(java_name, method_name=None):
    """
    判定某个类（或类 + 方法）该跳过还是执行。

    返回 Decision，action 是 "skip" / "run" / "defer"。

    **默认执行是刻意的**：漏跳只是多做了一点无用功，
    错跳会让功能静默消失，后者严重得多。
    """
    name = java_to_string(java_name) if java_name is not None else u""

    # 1. 方法级「必须执行」优先于一切
    if method_name is not None:
        method = java_to_string(method_name)
        for class_name in METHOD_RULES:
            if name == class_name or name.startswith(class_name + "$"):
                if METHOD_RULES[class_name].get(method) == u"run":
                    return Decision(u"run", u"方法级规则：{} 必须执行".format(
                        method), u"method-rule")

    category = classify(name)

    if category == u"must-run-event":
        return Decision(u"run", RUN_REASONS[u"event"], category)
    if category == u"common-setup":
        return Decision(u"run", RUN_REASONS[u"common-setup"], category)
    if category in SKIP_REASONS:
        return Decision(u"skip", SKIP_REASONS[category], category)

    # 2. 方法级「改为直接执行」
    if method_name is not None:
        method = java_to_string(method_name)
        for class_name in DEFER_METHODS:
            if name == class_name or name.startswith(class_name + "$"):
                defer_category = DEFER_METHODS[class_name].get(method)
                if defer_category is not None:
                    return Decision(u"defer", DEFER_REASONS[defer_category],
                                    defer_category)

    return Decision(u"run", u"未命中任何跳过规则，默认执行", None)


# ============================================================
# 统计与报告
# ============================================================

def summarize(java_names):
    """
    对一组 Java 类名做批量判定，返回统计结果。

    返回 {action: [名字...]}，便于打印「跳过了什么、为什么」。
    """
    result = {u"skip": [], u"run": [], u"defer": []}
    for java_name in java_names:
        decision = decide(java_name)
        result[decision.action].append((java_name, decision.reason))
    return result


def report_lines(java_names):
    """生成人类可读的报告行（真机核对用）。"""
    stats = summarize(java_names)
    lines = []
    lines.append(u"跳过 {} 项，执行 {} 项，改为直接执行 {} 项".format(
        len(stats[u"skip"]), len(stats[u"run"]), len(stats[u"defer"])))
    for action, label in ((u"skip", u"跳过"),
                          (u"defer", u"改为直接执行"),
                          (u"run", u"执行")):
        for java_name, reason in stats[action]:
            lines.append(u"  [{}] {} —— {}".format(label, java_name, reason))
    return lines


__all__ = [
    "Decision", "decide", "classify", "summarize", "report_lines",
    "SKIP_REASONS", "RUN_REASONS", "LOADER_LIFECYCLE_EVENTS",
    "CLIENT_EVENT_PREFIXES", "MUST_RUN_EVENTS", "LOADER_METADATA_CLASSES",
    "METHOD_RULES",
]

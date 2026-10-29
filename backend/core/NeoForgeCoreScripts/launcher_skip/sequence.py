# -*- coding: utf-8 -*-
# launcher_skip/sequence.py
# δ 层：启动流程执行器
#
# 它把真实模组的启动入口跑起来：
#
#   @Mod(value="manaita_plus_legacy")
#   public class ManaitaPlusLegacy {
#       public ManaitaPlusLegacy(IEventBus modEventBus, ModContainer modContainer) {
#           ManaitaPlusLegacyAttributeCore.init();   // 核心初始化
#           ...
#           BLOCKS.register(modEventBus);            // 注册
#           modContainer.registerConfig(ModConfig.Type.COMMON, SPEC);
#       }
#   }
#
# 具体做三件事：
#   1. 找到 @Mod 标注的入口类，按真实签名（IEventBus + ModContainer）构造它；
#   2. 构造过程中所有注册/配置调用都**照常执行**（见 rules.py 的说明：
#      跳注册会让方块物品全消失且不报错）；
#   3. 客户端 / 加载器专属的处理器按 rules.py 的判定跳过，
#      并留下一份「跳过了什么、为什么」的凭据。
#
# 第 3 点尤其重要：跳过必须**可审计**。模组作者看到「某个功能没生效」时，
# 应该能直接查到「它在 δ 层被跳过了，理由是客户端渲染」，
# 而不是对着一堆静默缺失的代码发呆。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
    from launcher_skip.rules import decide, classify
    # FML 生命周期事件**从 β 层导入**，不在这里另定义一套。
    #
    # 为什么：如果这里自己定义 FMLCommonSetupEvent，
    # 那么 `bus.subscribe(cb, FMLCommonSetupEvent)` 订阅的是本模块的类，
    # 而派发时用的可能是另一处的类，isinstance 匹配不上，
    # 处理器会**静默不执行**（自测抓到了：派发返回 0）。
    # 事件类的唯一来源是 neoforge/event.py。
    from neoforge.event import (
        FMLClientSetupEvent,
        FMLCommonSetupEvent,
        FMLDedicatedServerSetupEvent,
        FMLLoadCompleteEvent,
        InterModEnqueueEvent,
        InterModProcessEvent,
        ParallelDispatchEvent,
    )
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore
    from rules import decide, classify  # type: ignore
    # 同 network.py：不能写 `from event import ...`，
    # 那会命中 `neoforge/event/` 包而解析不到 `event.base`。
    from neoforge.event.fml.lifecycle import (  # type: ignore
        FMLClientSetupEvent,
        FMLCommonSetupEvent,
        FMLDedicatedServerSetupEvent,
        FMLLoadCompleteEvent,
        InterModEnqueueEvent,
        InterModProcessEvent,
        ParallelDispatchEvent,
    )


# ============================================================
# @Mod 注解
# ============================================================

class Mod(object):
    """
    对应 net.neoforged.fml.common.Mod。

    Java 里它是纯注解；Python 里当成装饰器用，把 modid 记在类上：

        @Mod(value="manaita_plus_legacy")
        class ManaitaPlusLegacy(object):
            def __init__(self, mod_event_bus, mod_container):
                ...

    支持两种写法（真实代码只用第一种，但翻译层可能产出第二种）：
        @Mod           装饰器直接接收类
        @Mod(value="x") 带参数
    """

    def __new__(cls, value=None, **kwargs):
        # 直接用类做装饰器时，Python 传进来的第一个参数就是那个类。
        # 这里必须覆盖 __new__ 并**返回类本身** ——
        # 否则 `@Mod` 会把类替换成 Mod 实例
        # （与 neoforge/event.py 的 SubscribeEvent 同一个坑，已踩过两次）。
        if isinstance(value, type):
            return cls._mark(value, kwargs.get("modid"))
        return object.__new__(cls)

    def __init__(self, value=None, **kwargs):
        if isinstance(value, type):
            self.modid = kwargs.get("modid")
            return
        self.modid = value if value is not None else kwargs.get("modid")

    def __call__(self, target):
        return Mod._mark(target, self.modid)

    @staticmethod
    def _mark(target, modid):
        target.__neoforge_mod__ = True
        if modid is not None:
            target.__neoforge_modid__ = java_to_string(modid)
        return target


def get_modid(mod_class):
    """取一个 @Mod 类的 modid；没有则返回 None。"""
    return getattr(mod_class, "__neoforge_modid__", None)


def is_mod_class(candidate):
    """判断一个类是不是 @Mod 入口。"""
    return bool(getattr(candidate, "__neoforge_mod__", False))


# ============================================================
# 启动记录
# ============================================================

class LaunchRecord(object):
    """
    启动过程的记录。**这是本层最有价值的产出** ——
    它回答「哪些代码被跳过了、为什么」。
    """

    def __init__(self, modid=None):
        self.modid = modid
        self.ran = []            # 执行过的步骤
        self.skipped = []        # [(名字, 理由, 类别)]
        self.deferred = []       # [(名字, 理由)]
        self.errors = []         # [(步骤, 异常)]

    def note_run(self, name, detail=None):
        self.ran.append((name, detail))
        return None

    def note_skip(self, name, reason, category=None):
        self.skipped.append((name, reason, category))
        return None

    def note_defer(self, name, reason):
        self.deferred.append((name, reason))
        return None

    def note_error(self, step, error):
        self.errors.append((step, error))
        return None

    # ---------------- 汇总 ----------------

    def skipReasons(self):
        """按类别汇总跳过项，便于回答「为什么某个功能没生效」。"""
        grouped = {}
        for name, reason, category in self.skipped:
            grouped.setdefault(category or u"未分类", []).append(name)
        return grouped

    def summary_lines(self):
        lines = []
        lines.append(u"模组 {} 启动：执行 {} 步，跳过 {} 步，"
                     u"改为直接执行 {} 次，出错 {} 次".format(
                         self.modid or u"<未知>", len(self.ran),
                         len(self.skipped), len(self.deferred),
                         len(self.errors)))

        if self.ran:
            lines.append(u"  已执行:")
            for name, detail in self.ran:
                suffix = u" ({})".format(detail) if detail else u""
                lines.append(u"    + {}{}".format(name, suffix))

        if self.skipped:
            lines.append(u"  已跳过（按类别）:")
            grouped = self.skipReasons()
            for category in sorted(grouped):
                lines.append(u"    - [{}] {} 项".format(category,
                                                        len(grouped[category])))
                for name in grouped[category]:
                    lines.append(u"        {}".format(name))

        if self.deferred:
            lines.append(u"  改为直接执行:")
            for name, reason in self.deferred:
                lines.append(u"    ~ {} —— {}".format(name, reason))

        if self.errors:
            lines.append(u"  出错:")
            for step, error in self.errors:
                lines.append(u"    ! {} —— {}: {}".format(
                    step, type(error).__name__, error))

        return lines

    def hasErrors(self):
        return len(self.errors) > 0

    def __repr__(self):
        return u"<LaunchRecord {} 执行{} 跳过{}>".format(
            self.modid or u"?", len(self.ran), len(self.skipped))


# ============================================================
# 启动执行器
# ============================================================

# 需要按 @EventBusSubscriber 收集的处理器里，哪些方法属于启动阶段
SETUP_EVENT_TYPES = (FMLClientSetupEvent, FMLCommonSetupEvent,
                     FMLLoadCompleteEvent)


class LaunchSequence(object):
    """
    按真实顺序执行一次模组启动。

    顺序（与 NeoForge 一致）：
      1. 构造 @Mod 入口类（IEventBus + ModContainer）—— 期间完成注册与配置
      2. 触发启动期事件（FMLClientSetupEvent 等）给已注册的处理器
      3. 记录全部跳过项

    第 1 步**不会**因为要跳过什么而省略 ——
    注册和配置都在构造函数里，跳过它们等于模组不存在。
    """

    def __init__(self, event_bus, mod_container, record=None):
        if event_bus is None:
            raise IllegalArgumentException(u"LaunchSequence 需要事件总线")
        self._bus = event_bus
        self._container = mod_container
        self.record = record if record is not None else LaunchRecord(
            getattr(mod_container, "modid", None))

    # ---------------- 第 1 步：构造入口类 ----------------

    def construct_mod(self, mod_class):
        """
        按真实签名构造 @Mod 入口类。

        Java 的构造函数是 (IEventBus, ModContainer)；Python 翻译后
        通常写成 `def __init__(self, mod_event_bus, mod_container)`。
        这里按位置传，与 Java 一致。

        构造过程中的异常**不吞掉** —— 注册失败必须让模组启动失败，
        否则会得到「加载成功但功能全无」这种最难查的状态。
        """
        if mod_class is None:
            raise IllegalArgumentException(u"construct_mod 收到 None")

        # 就地补上 modid，**不重建 record** ——
        # 重建会把已经记下的跳过项（例如 audit_handlers 的结果）冲掉，
        # 而那份凭据正是本层最有价值的产出。
        modid = get_modid(mod_class)
        if modid is not None:
            self.record.modid = modid
        self.record.note_run(u"构造入口类", getattr(mod_class, "__name__",
                                                    str(mod_class)))

        try:
            instance = mod_class(self._bus, self._container)
        except Exception as error:
            self.record.note_error(u"构造入口类", error)
            raise

        registry_count = 0
        if hasattr(self._bus, "getRegistries"):
            registry_count = len(self._bus.getRegistries())
        self.record.note_run(u"注册器已挂到事件总线",
                             u"{} 个".format(registry_count))
        return instance

    # ---------------- 第 2 步：启动期事件 ----------------

    def dispatch_setup_events(self, setup_event=None, side=None):
        """
        把启动期事件派发给已订阅的处理器。

        客户端专属的处理器按 rules.py 判定跳过；跳过项记进 record，
        这样「某个客户端功能没生效」有据可查。
        """
        if setup_event is None:
            setup_event = FMLClientSetupEvent()

        class_name = type(setup_event).__name__
        full_name = _java_name_of_event_class(class_name)
        decision = decide(full_name)

        if decision.isSkip():
            self.record.note_skip(full_name, decision.reason,
                                  decision.category)
            return 0

        # 派发（事件总线按类型匹配）
        handled = self._bus._dispatch(setup_event)
        setup_event.drainWork()
        self.record.note_run(u"派发 " + class_name,
                             u"{} 个处理器".format(handled))

        if setup_event.enqueue_calls:
            self.record.note_defer(
                class_name + u".enqueueWork",
                u"处理器结束后在主线程排空任务"
                u"（共 {} 次）".format(
                    setup_event.enqueue_calls))

        return handled

    # ---------------- 第 3 步：审计客户端处理器 ----------------

    def audit_handlers(self, handler_classes):
        """
        预先审查一批处理器类，把会被跳过的记下来。

        真机调试时先跑这个：一眼看出「这个模组的哪些客户端功能不会生效」，
        不用等运行时逐个发现。

        判断依据是 `@SubscribeEvent` 装饰时记下的**事件参数名**
        （见 neoforge/event.py 的 _mark_listener）——
        真实代码的参数名就是事件类名的小写，是翻译后唯一可靠的线索。
        """
        skipped_count = 0
        for handler in handler_classes or []:
            handler_name = getattr(handler, "__name__", str(handler))
            for attr in dir(handler):
                if attr.startswith(u"_"):
                    continue
                member = getattr(handler, attr, None)
                meta = getattr(member, "__neoforge_subscribe__", None)
                if not meta:
                    continue

                event_arg = meta.get("event_arg") or u""
                full_name = _java_name_of_event_arg(event_arg)
                decision = decide(full_name) if full_name else None

                if decision is not None and decision.isSkip():
                    self.record.note_skip(
                        u"{}.{}".format(handler_name, attr),
                        decision.reason,
                        decision.category)
                    skipped_count += 1
                elif _looks_like_client_arg(event_arg):
                    # 参数名能看出是客户端，但没登记进 Java 名单 ——
                    # 仍然要跳过，但理由要说清「是按名字判断的」，
                    # 免得将来有人以为它经过了正规判定。
                    self.record.note_skip(
                        u"{}.{}".format(handler_name, attr),
                        u"按事件参数名 `{}` 判断为客户端处理器"
                        u"（未登记在 Java 名单里）".format(event_arg),
                        u"client-render")
                    skipped_count += 1

        return skipped_count

    # ---------------- 一步到位 ----------------

    def run(self, mod_class, handler_classes=None, setup_event=None):
        """
        完整跑一次启动：构造入口 → 审查处理器 → 派发启动事件。
        返回 (实例, 启动记录)。
        """
        instance = self.construct_mod(mod_class)
        self.audit_handlers(handler_classes)
        self.dispatch_setup_events(setup_event)
        return instance, self.record


# ============================================================
# 事件参数名 -> Java 类名
# ============================================================

# FML 生命周期事件的参数名 -> Java 全限定名
_SETUP_EVENT_JAVA_NAMES = {
    u"paralleldispatchevent":
        u"net.neoforged.fml.event.lifecycle.ParallelDispatchEvent",
    u"fmlcommonsetupevent":
        u"net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent",
    u"fmlclientsetupevent":
        u"net.neoforged.fml.event.lifecycle.FMLClientSetupEvent",
    u"fmldicatedserversetupevent":
        u"net.neoforged.fml.event.lifecycle.FMLDedicatedServerSetupEvent",
    u"fmlloadcompleteevent":
        u"net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent",
    u"intermodenqueueevent":
        u"net.neoforged.fml.event.lifecycle.InterModEnqueueEvent",
    u"intermodprocessevent":
        u"net.neoforged.fml.event.lifecycle.InterModProcessEvent",
}

# 参数名里出现这些词就认为是客户端专属
_CLIENT_HINTS = (u"client", u"render", u"shader", u"keymapping",
                 u"screen", u"gui", u"input")


def _java_name_of_event_class(class_name):
    """按 Python 类名反查 FML 事件的 Java 全限定名。"""
    key = java_to_string(class_name).lower()
    found = _SETUP_EVENT_JAVA_NAMES.get(key)
    if found:
        return found
    return u"net.neoforged.fml.event.lifecycle." + java_to_string(class_name)


def _java_name_of_event_arg(arg_name):
    """
    按参数名反查 Java 类名。

    真实代码里参数名就是事件类名的小写（`fmlClientSetupEvent`、
    `registerShadersEvent`），所以能直接对上。
    对不上时返回 None，由调用方决定怎么处理。
    """
    if not arg_name:
        return None
    key = java_to_string(arg_name).lower()
    found = _SETUP_EVENT_JAVA_NAMES.get(key)
    if found:
        return found
    return None


def _looks_like_client_arg(arg_name):
    """参数名看起来是不是客户端相关的。"""
    if not arg_name:
        return False
    lowered = java_to_string(arg_name).lower()
    for hint in _CLIENT_HINTS:
        if hint in lowered:
            return True
    return False


__all__ = [
    "Mod", "get_modid", "is_mod_class",
    "ParallelDispatchEvent", "FMLCommonSetupEvent", "FMLClientSetupEvent",
    "FMLDedicatedServerSetupEvent", "FMLLoadCompleteEvent",
    "InterModEnqueueEvent", "InterModProcessEvent",
    "LaunchRecord", "LaunchSequence",
]

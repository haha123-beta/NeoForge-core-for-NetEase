# -*- coding: utf-8 -*-
# neoforge/event/base.py
# β 层：事件系统基础（环境判断 / 事件基类 / 注解 / 事件总线）
#
# 这一层原来在 neoforge/event.py 里，与各类具体事件混在一个文件。
# 现在按真实 Java 包拆开（见 neoforge/event/__init__.py 的说明），
# 这里只留「与具体事件无关」的部分：
#
#     Dist / OnlyIn / FMLEnvironment   对应 net.neoforged.api.distmarker 与 fml.loading
#     Event / CancelableEvent          对应 net.neoforged.bus.api.Event
#     SubscribeEvent / EventBusSubscriber   对应 bus.api 与 fml.common
#     IEventBus                        对应 net.neoforged.bus.api.IEventBus
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
# 执行环境
# ============================================================

class _Side(object):
    """枚举成员：只认身份，不认值（与 Java 枚举语义一致）。"""

    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def ordinal(self):
        return 0 if self._name == u"CLIENT" else 1

    def toString(self):
        return self._name

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<Dist.{}>".format(self._name)


class Dist(object):
    """
    对应 net.neoforged.api.distmarker.Dist。

    Java 里是枚举，只有 CLIENT / SERVER 两个单例。
    """

    CLIENT = _Side(u"CLIENT")
    DEDICATED_SERVER = _Side(u"DEDICATED_SERVER")
    SERVER = DEDICATED_SERVER


class FMLEnvironment(object):
    """
    对应 net.neoforged.fml.loading.FMLEnvironment。

    真实代码用它判断跑在哪一端：
        if (FMLEnvironment.dist == Dist.CLIENT) { ... }

    默认按 CLIENT 算 —— 基岩版模组跑在客户端上，
    而且要能承载客户端专属的事件处理器。需要时可改写 dist。
    """

    dist = Dist.CLIENT
    production = False

    @staticmethod
    def getDist():
        return FMLEnvironment.dist

    @staticmethod
    def setDist(side):
        FMLEnvironment.dist = side
        return None


def OnlyIn(side):
    """
    对应 net.neoforged.api.distmarker.OnlyIn 注解。

    Java 里它只是标记，实际生效靠 FML 的类加载过滤。
    这里做成装饰器：记下允许的端，装配时据此过滤，效果等价
    （客户端专属代码不会在服务端被注册）。
    """
    def decorator(target):
        target.__neoforge_only_in__ = side
        return target
    return decorator


def is_side_allowed(allowed_sides, current=None):
    """判断当前环境是否落在允许的端集合里（空集合视为不限制）。"""
    if not allowed_sides:
        return True
    if current is None:
        current = FMLEnvironment.getDist()
    for side in allowed_sides:
        if side is current or side == current:
            return True
    return False




# ============================================================
# 事件基类
# ============================================================

class Event(object):
    """
    对应 net.neoforged.bus.api.Event。

    所有事件对象的基类。真实模组用的事件都是它子类
    （ClientTickEvent.Post、RenderFrameEvent.Pre、InputEvent.Key …）。

    扫描结果显示模组没用可取消事件，这里仍提供 cancel/isCanceled：
    它们是 NeoForge 事件基类的公共契约，
    而且翻译后的代码可能在意「事件是否被别处取消了」。
    """

    def __init__(self):
        self._canceled = False

    def isCancelable(self):
        """基类事件不可取消；可取消事件子类应覆盖为 True。"""
        return False

    def isCanceled(self):
        return self._canceled

    def setCanceled(self, canceled=True):
        if not self.isCancelable():
            raise IllegalArgumentException(
                u"{} 不是可取消事件".format(type(self).__name__))
        self._canceled = bool(canceled)
        return None

    def cancel(self):
        self.setCanceled(True)
        return None


class CancelableEvent(Event):
    """可取消事件的基类，方便按需派生。"""

    def isCancelable(self):
        return True




# ============================================================
# 注解
# ============================================================

def _validate_listener(method):
    """
    检查事件监听函数的签名。

    为什么值得单独做：
      监听函数是被事件总线用「一个事件参数」调用的。
      如果翻译时漏写或多写了参数，会在事件触发时抛 TypeError，
      而那时调用栈已看不出是哪个监听器的问题。装饰阶段报错，定位成本几乎为零。

    Java 与 Python 的参数差异（实测踩到）：
      Java 里事件监听是 `static void onTick(Event e)`，只有 1 个参数；
      Python 里写在类中的是**实例方法**，签名是 `def onTick(self, e)`，
      co_argcount == 2。所以不能一刀切要求 1，
      否则所有正常的实例方法写法都会被误判为「参数过多」。
    """
    code = getattr(method, "func_code", None) or getattr(method, "__code__", None)
    if code is None:
        return  # 内建或不可反射的可调用对象，跳过检查

    argcount = code.co_argcount
    if argcount in (1, 2):
        # 1 = 普通函数（或已绑定的方法）
        # 2 = 实例方法（self + event）
        return

    raise IllegalArgumentException(
        u"事件监听函数 {} 应接受一个事件参数（实例方法再加 self），"
        u"实际有 {} 个参数".format(getattr(method, "__name__", method), argcount))


class SubscribeEvent(object):
    """
    对应 net.neoforged.bus.api.SubscribeEvent。

    支持两种写法（真实代码与翻译后的代码都会出现）：
        @SubscribeEvent            # 直接装饰
        @SubscribeEvent()          # 带括号（需要传 priority 等参数时）

    **关键实现细节（踩过的坑）**：
      用「类」做装饰器时，Python 取的是 `SubscribeEvent(func)` 这个**实例**，
      而不是 `__init__` 的返回值。所以直接写
          @SubscribeEvent
          def onTick(e): ...
      会把函数替换成一个 SubscribeEvent 实例（实测 type(f1) 就是 SubscribeEvent），
      函数本身与它的标记全都丢了，表现就是「监听器一个都不生效」。

      正确做法是覆盖 `__new__`：
        - 直接装饰（method 是函数）→ 返回打过标记的**函数本身**；
        - 带括号（method 是 None）→ 返回装饰器实例，实例再被调用来装饰。

    除了打标记，它还校验签名（见 _validate_listener），
    让参数写错在**装饰那一刻**就报错，而不是等事件触发时才炸。
    """

    def __new__(cls, method=None, priority=None, receive_canceled=False):
        if method is not None and callable(method):
            # 直接装饰：只打标记，返回原函数
            return _mark_listener(method, priority, receive_canceled)
        return object.__new__(cls)

    def __init__(self, method=None, priority=None, receive_canceled=False):
        self.priority = priority
        self.receive_canceled = receive_canceled

    def __call__(self, method):
        # 带括号的用法：装饰器实例被调用来装饰函数
        return _mark_listener(method, self.priority, self.receive_canceled)


def _mark_listener(method, priority=None, receive_canceled=False):
    """校验并标记监听函数，返回函数本身。"""
    _validate_listener(method)
    method.__neoforge_subscribe__ = {
        "priority": priority,
        "receive_canceled": receive_canceled,
        # 记下事件参数的**参数名**。
        #
        # 为什么需要：翻译后的代码没有可靠的类型标注，
        # 但 δ 层要判断「这个处理器是不是客户端专属的」才能决定跳不跳。
        # 真实代码的参数名就是事件类名的小写（`clientTickEvent`、
        # `registerShadersEvent`），所以参数名是这里唯一可靠的线索。
        # 装饰阶段顺手记下来，比事后 dir() 反射猜要准。
        "event_arg": _listener_arg_name(method),
    }
    return method


def _listener_arg_name(method):
    """取监听函数最后一个参数的**名字**（约定上就是事件对象）。"""
    code = getattr(method, "func_code", None) or getattr(method, "__code__", None)
    if code is None:
        return None
    names = list(code.co_varnames[:code.co_argcount])
    if not names:
        return None
    return names[-1]


class EventBusSubscriber(object):
    """
    对应 net.neoforged.fml.common.EventBusSubscriber。

    Java 里 FML 会自动扫描带这个注解的类，把里面 @SubscribeEvent
    标记的静态方法挂上总线。Python 没有类加载器扫描，
    所以改成「登记 + 显式装配」：
      - 装饰时把类记进待装配清单，并记下 modid 与允许的端；
      - 核心包启动时调 register_all(bus) 一次性挂上去。

    保留了声明式写法，又把「什么时候生效」变成可控的一步。
    """

    _pending = []

    def __init__(self, modid=None, value=None, bus=None):
        self.modid = java_to_string(modid) if modid is not None else None

        # Java 的 value 是 Dist 数组；Python 里允许传单个或列表
        if value is None:
            self.sides = []
        elif isinstance(value, (list, tuple, set)):
            self.sides = list(value)
        else:
            self.sides = [value]

        self.bus = bus

    def __call__(self, target):
        target.__neoforge_subscriber__ = {
            "modid": self.modid,
            "sides": list(self.sides),
        }
        EventBusSubscriber._pending.append(
            (target, self.modid, list(self.sides)))
        return target

    # ---------------- 装配 ----------------

    @staticmethod
    def pending():
        return list(EventBusSubscriber._pending)

    @staticmethod
    def clear_pending():
        EventBusSubscriber._pending = []

    @staticmethod
    def register_all(event_bus, current_side=None):
        """
        把清单里所有监听器挂到事件总线上。

        返回 (装配数, 跳过数)：
          - 端不匹配的跳过（等价 Java 的 Dist 过滤）；
          - 没有任何 @SubscribeEvent 方法也跳过，
            但那通常是写错了，所以同时打印提醒。
        """
        registered = 0
        skipped = 0

        for target_class, _modid, sides in EventBusSubscriber._pending:
            if not is_side_allowed(sides, current_side):
                skipped += 1
                continue

            listeners = collect_listeners(target_class)
            if not listeners:
                print(u"[事件] 类 {} 带 @EventBusSubscriber 但没有 "
                      u"@SubscribeEvent 方法，已跳过".format(target_class.__name__))
                skipped += 1
                continue

            for method, meta in listeners:
                event_bus.subscribe(method,
                                    priority=meta.get("priority"),
                                    receive_canceled=meta.get("receive_canceled",
                                                              False))
                registered += 1

        return registered, skipped


def collect_listeners(target_class):
    """
    收集一个类里所有 @SubscribeEvent 方法。

    兼容两种写法：普通方法（翻译后的 Python 代码多半这样）与 staticmethod。
    """
    listeners = []

    for name in sorted(dir(target_class)):
        if name.startswith(u"__"):
            continue
        try:
            attribute = getattr(target_class, name)
        except Exception:
            continue

        meta = getattr(attribute, "__neoforge_subscribe__", None)
        if meta is None:
            continue

        listeners.append((attribute, meta))

    return listeners




# ============================================================
# 事件总线
# ============================================================

class _Priority(object):
    def __init__(self, name, rank):
        self._name, self._rank = name, rank

    def name(self):
        return self._name

    def ordinal(self):
        return self._rank

    def toString(self):
        return self._name


class EventPriority(object):
    HIGHEST = _Priority("HIGHEST", 0)
    HIGH = _Priority("HIGH", 1)
    NORMAL = _Priority("NORMAL", 2)
    LOW = _Priority("LOW", 3)
    LOWEST = _Priority("LOWEST", 4)

    @staticmethod
    def values():
        return [EventPriority.HIGHEST, EventPriority.HIGH, EventPriority.NORMAL,
                EventPriority.LOW, EventPriority.LOWEST]

    @staticmethod
    def valueOf(name):
        for value in EventPriority.values():
            if value.name() == name:
                return value
        raise IllegalArgumentException("Unknown event priority: " + str(name))


class IEventBus(object):
    """
    对应 net.neoforged.bus.api.IEventBus。

    真实代码里它由 @Mod 构造函数注入，用途有三：
      1. 挂 DeferredRegister：BLOCKS.register(modEventBus)
      2. 订阅事件：addListener / register
      3. 触发事件：post(event)
    """

    def __init__(self, name=u"mod"):
        self.name = java_to_string(name)
        self._listeners = []
        self._registries = []
        self.posted = []

    # ---------------- 订阅 ----------------

    def subscribe(self, listener, event_type=None, priority=None,
                  receive_canceled=False):
        """
        订阅事件。

        event_type 省略时订阅「所有事件」，派发时再做类型匹配 ——
        因为 Python 的监听函数没有静态类型可推断。
        """
        if not callable(listener):
            raise IllegalArgumentException("Event listener must be callable")
        priority = EventPriority.NORMAL if priority is None else priority
        if not isinstance(priority, _Priority):
            raise IllegalArgumentException("Expected EventPriority")
        entry = {
            "owner": listener,
            "callback": listener,
            "event_type": event_type,
            "priority": priority,
            "receive_canceled": receive_canceled,
            "name": getattr(listener, "__name__", java_to_string(listener)),
        }
        self._listeners.append(entry)
        return entry

    def addListener(self, *args):
        """Java overload order; erased event types must be supplied or tagged explicitly."""
        values = list(args)
        priority, receive_canceled = EventPriority.NORMAL, False
        if values and isinstance(values[0], _Priority):
            priority = values.pop(0)
        if values and isinstance(values[0], bool):
            receive_canceled = values.pop(0)
        if len(values) == 2:
            event_type, listener = values
        elif len(values) == 1:
            listener = values[0]
            event_type = getattr(listener, "__neocore_event_type__", None)
        else:
            raise IllegalArgumentException("Invalid addListener overload")
        if not isinstance(event_type, type) or not issubclass(event_type, Event):
            raise IllegalArgumentException("Translation must preserve event type: addListener(EventClass, listener)")
        return self.subscribe(listener, event_type, priority, receive_canceled)

    def register(self, target):
        """
        对应 Java 的 addListener / register(Object)。

        target 可以是带 @SubscribeEvent 方法的类或实例，或一个可调用对象。
        """
        cls = target if isinstance(target, type) else type(target)
        if any('_nc_event_handlers' in parent.__dict__ for parent in cls.__mro__):
            from neoforge.mod_entrypoints import ModEntrypoints
            return ModEntrypoints.registerAnnotated(self, target)
        if callable(target) and not isinstance(target, type):
            return self.subscribe(target)

        listeners = collect_listeners(target)
        if not listeners:
            raise IllegalArgumentException(
                u"{} 里没有 @SubscribeEvent 方法，无法注册".format(target))
        for method, meta in listeners:
            entry = self.subscribe(method, priority=meta.get("priority"),
                                   receive_canceled=meta.get("receive_canceled", False))
            entry["owner"] = target
        return target

    def unregister(self, target):
        """Remove this callback/registered owner, without matching unrelated names."""
        before = len(self._listeners)
        self._listeners = [entry for entry in self._listeners
                           if entry["owner"] is not target and entry["callback"] != target]
        return before - len(self._listeners)

    # ---------------- 注册器 ----------------

    def register_registry(self, deferred_register):
        """挂一个 DeferredRegister（对应 Java 的 X.register(modEventBus)）。"""
        if deferred_register not in self._registries:
            self._registries.append(deferred_register)
        return deferred_register

    def getRegistries(self):
        """按挂载顺序返回注册器 —— 注册流程按这个顺序执行。"""
        return list(self._registries)

    def freeze_registries(self, registry_lookup=None):
        """
        执行所有挂载注册器的注册动作。

        registry_lookup 是可选函数：给注册表名，返回对应 Registry（写表用）。
        返回 {注册器: {路径: 值}}。
        """
        results = {}
        for deferred in self._registries:
            key = deferred.registry_key.registry()
            registry = None
            if registry_lookup is not None:
                registry = registry_lookup(key)
            results[deferred] = deferred.freeze_and_register(registry)
        return results

    # ---------------- 派发 ----------------

    def post(self, event, strict=False):
        """NeoForge-compatible return value: the same event instance."""
        if isinstance(event, _Priority):
            raise NotImplementedError("Per-priority post requires a configured phase-aware bus")
        owner=getattr(self,'_mod_context',None)
        if owner is None:self._dispatch(event,strict)
        else:
            from neoforge.mod_entrypoints import ModEntryScope
            with ModEntryScope(owner):self._dispatch(event,strict)
        return event

    def _dispatch(self,event,strict=False):
        owner=getattr(self,'_mod_context',None)
        if owner is None:return self._dispatch_in_scope(event,strict)
        from neoforge.mod_entrypoints import ModEntryScope
        with ModEntryScope(owner):return self._dispatch_in_scope(event,strict)

    def _dispatch_in_scope(self, event, strict=False):
        """
        对应 Java 的 eventBus.post(event)。

        按类型匹配监听器依次调用。单个监听器抛异常**不会中断**其它监听器
        —— 一个处理器出错不该让整条事件链停摆，但错误必须打印出来，不能吞。
        """
        event_type = type(event)
        self.posted.append(event)
        if len(self.posted) > 256:
            del self.posted[:-256]

        candidates = []
        for entry in self._listeners:
            wanted = entry["event_type"]
            if wanted is None or wanted is event_type or wanted is event:
                candidates.append(entry)
            elif isinstance(wanted, type) and isinstance(event, wanted):
                # 按**父类**订阅也要能收到子类事件：
                # 订阅 ClientTickEvent 应当收到 ClientTickEvent.Post。
                # 注意 isinstance 的方向 —— 事件是实例，wanted 是类。
                candidates.append(entry)
            elif isinstance(wanted, (list, tuple, set)) and event_type in wanted:
                candidates.append(entry)

        candidates.sort(key=lambda entry: entry["priority"].ordinal())
        handled = 0
        for entry in candidates:
            if getattr(event, "isCanceled", lambda: False)() and not entry["receive_canceled"]:
                continue
            try:
                entry["callback"](event)
                handled += 1
            except Exception as error:
                if strict:
                    raise
                print(u"[事件] 监听器 {} 处理 {} 时出错: {}: {}".format(
                    entry["name"], event_type.__name__,
                    type(error).__name__, error))

        return handled

    def listenerCount(self):
        return len(self._listeners)

    def clear(self):
        self._listeners = []
        self._registries = []
        self.posted = []

    def __repr__(self):
        return u"<IEventBus {} 监听器={} 注册器={}>".format(
            self.name, len(self._listeners), len(self._registries))

# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.neoforged.bus.api.IEventBus": IEventBus,
    "net.neoforged.bus.api.EventPriority": EventPriority,
    "net.neoforged.bus.api.Event": Event,
    "net.neoforged.bus.api.CancelableEvent": CancelableEvent,
    "net.neoforged.bus.api.SubscribeEvent": SubscribeEvent,
    "net.neoforged.fml.common.EventBusSubscriber": EventBusSubscriber,
    "net.neoforged.api.distmarker.Dist": Dist,
    "net.neoforged.api.distmarker.OnlyIn": OnlyIn,
    "net.neoforged.fml.loading.FMLEnvironment": FMLEnvironment,
}


__all__ = [
    "Dist", "FMLEnvironment", "OnlyIn", "is_side_allowed",
    "Event", "CancelableEvent",
    "SubscribeEvent", "EventBusSubscriber", "collect_listeners",
    "IEventBus", "EventPriority",
    "JAVA_MAP",
]

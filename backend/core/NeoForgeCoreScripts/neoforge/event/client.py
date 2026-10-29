# -*- coding: utf-8 -*-
# neoforge/event/client.py
# β 层：客户端事件（net.neoforged.neoforge.client.event）
#
# 真实用法（逐字来自反编译源码）：
#     @EventBusSubscriber(modid="manaita_plus_legacy", value={Dist.CLIENT})
#     public static void clientTick(ClientTickEvent.Post event) { ... }
#     public static void renderTick(RenderFrameEvent.Pre event) { ... }
#     public static void onKeyInput(InputEvent.Key event) { ... }
#
# 注意：这些事件的**派发**在 δ 层被跳过（客户端专属），
# 但**类本身必须存在** —— 否则翻译层在导入阶段就报错
# （类不存在 ≠ 不派发，两者是不同的问题，见 shader/__init__.py 的同类说明）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    # 包内相对导入：本模块住在 neoforge/event/ 下
    from neoforge.event.base import Event
    from java_stdlib.lang import java_to_string
except ImportError:
    from base import Event  # type: ignore
    from lang import java_to_string  # type: ignore


class ClientTickEvent(Event):
    """
    对应 net.neoforged.neoforge.client.event.ClientTickEvent。

    注意内部类的继承关系：Java 里 `ClientTickEvent.Pre extends ClientTickEvent`，
    所以按**父类**订阅（subscribe(cb, ClientTickEvent)）也能收到 Pre/Post。
    曾经让 Pre/Post 直接继承 Event，导致「按父类订阅收不到子类事件」——
    自测抓到了这个错。
    """

    class Pre(Event):
        pass

    class Post(Event):
        pass


# 让内部类真正继承外层类（Java 的 nested class 语义）。
# 不能写在类体里写 `class Pre(ClientTickEvent)` —— 类体执行时 ClientTickEvent 还不存在。
ClientTickEvent.Pre.__bases__ = (ClientTickEvent,)
ClientTickEvent.Post.__bases__ = (ClientTickEvent,)


class RenderFrameEvent(Event):
    """对应 net.neoforged.neoforge.client.event.RenderFrameEvent。"""

    class Pre(Event):
        pass

    class Post(Event):
        pass


RenderFrameEvent.Pre.__bases__ = (RenderFrameEvent,)
RenderFrameEvent.Post.__bases__ = (RenderFrameEvent,)


class InputEvent(Event):
    """对应 net.neoforged.neoforge.client.event.InputEvent。"""

    class Key(Event):
        pass

    class InteractionKeyMappingTriggered(Event):
        pass


InputEvent.Key.__bases__ = (InputEvent,)
InputEvent.InteractionKeyMappingTriggered.__bases__ = (InputEvent,)


class RegisterShadersEvent(Event):
    """
    对应 net.neoforged.neoforge.client.event.RegisterShadersEvent（真实 7 次）。

    真实用法：
        event.registerShader(CCShaderInstance.create(rp, loc, format),
                             shader -> { ... 取 uniform ... });
    其中第二个参数是 `Consumer<ShaderInstance>` 回调。

    注意：本事件在 δ 层的跳过规则里是**跳过**的
    （`net.neoforged.neoforge.client.event.` 前缀）。
    但这个类仍要存在 —— 因为「跳过派发」和「类不存在」是两回事：
    后者会让翻译层在导入阶段就报错。见 rules.py 与 event.py 的分工。
    """

    def __init__(self, resource_provider=None):
        from shader.material import ResourceProvider
        Event.__init__(self)
        self._provider = resource_provider if resource_provider is not None \
            else ResourceProvider()
        self.registered = []        # [(名字, ShaderInstance)]
        self._results = []

    def getResourceProvider(self):
        """对应 getResourceProvider()。"""
        return self._provider

    def setResourceProvider(self, provider):
        self._provider = provider
        return None

    def registerShader(self, shader, consumer=None):
        """
        对应 registerShader(ShaderInstance, Consumer<ShaderInstance>)。

        与 Java 的差别：Java 里回调是在**真正编译完 GLSL 之后**才调；
        这边没有 GLSL 阶段，所以**立即调用** —— 否则回调永不执行，
        真实代码里 `cosmicShader` / `cosmicTime` 这些静态字段会一直是 null，
        后面的渲染逻辑全线 NPE。
        """
        if shader is None:
            from java_stdlib._base import IllegalArgumentException
            raise IllegalArgumentException(u"registerShader 收到 None")

        location = shader.getLocation() if hasattr(shader, "getLocation") \
            else u"<unknown>"
        self.registered.append((java_to_string(location), shader))

        if consumer is not None:
            consumer(shader)
            self._results.append(shader)
        return None

    def getRegisteredShaders(self):
        return list(self.registered)

    def size(self):
        return len(self.registered)

    def getCompiledShaders(self):
        """已完成回调的着色器（对应 Java 的 getCompiledShaders）。"""
        return list(self._results)

    def __repr__(self):
        return u"<RegisterShadersEvent 已注册 {} 个>".format(
            len(self.registered))


# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.neoforge.client.event."

JAVA_MAP = {
    _PREFIX + "ClientTickEvent": ClientTickEvent,
    _PREFIX + "ClientTickEvent$Pre": ClientTickEvent.Pre,
    _PREFIX + "ClientTickEvent$Post": ClientTickEvent.Post,
    _PREFIX + "RenderFrameEvent": RenderFrameEvent,
    _PREFIX + "RenderFrameEvent$Pre": RenderFrameEvent.Pre,
    _PREFIX + "RenderFrameEvent$Post": RenderFrameEvent.Post,
    _PREFIX + "InputEvent": InputEvent,
    _PREFIX + "InputEvent$Key": InputEvent.Key,
    _PREFIX + "RegisterShadersEvent": RegisterShadersEvent,
}


__all__ = [
    "ClientTickEvent", "RenderFrameEvent", "InputEvent", "RegisterShadersEvent",
    "JAVA_MAP",
]

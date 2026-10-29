# -*- coding: utf-8 -*-
# neoforge/event/fml/lifecycle.py
# β 层：FML 加载器生命周期事件（net.neoforged.fml.event.lifecycle）
#
# 真实用法（逐字来自反编译源码）：
#     @SubscribeEvent
#     public static void onClientSetup(FMLClientSetupEvent event) {
#         event.enqueueWork(() -> { ... });
#     }
#
# **这些类必须住在这里，不能由 δ 层另起一套** ——
# 否则 `bus.subscribe(cb, FMLCommonSetupEvent)` 用的是 δ 层的类、
# 派发时用的可能是另一处的类，isinstance 匹配不上，处理器静默不执行。
# （这个坑实测踩过，见 launcher_skip/sequence.py 的说明。）
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    # 包内相对导入：本模块住在 neoforge/event/fml/ 下
    from neoforge.event.base import Event
    from java_stdlib._base import IllegalArgumentException
except ImportError:
    # 平坦导入兜底（真机上脚本根被挂进 sys.path 时用这条）
    from base import Event  # type: ignore
    from _base import IllegalArgumentException  # type: ignore


#
# 这些类**必须住在这一层**，不能由 δ 层另起一套 ——
# 否则 `bus.subscribe(cb, FMLCommonSetupEvent)` 用的是 δ 层的类，
# 而派发时用的是另一个类，isinstance 匹配不上，处理器静默不执行。
# （自测抓到了这个：派发返回 0，处理器一次没跑。）
#
# 它们的 `enqueueWork` 语义与 NeoForge 不同，见下面的说明。

class _LifecycleWorkResult(object):
    """Finite lifecycle result, not a complete Java CompletableFuture implementation."""
    def __init__(self):self.done=False;self.value=None;self.error=None
    def isDone(self):return self.done
    def join(self):
        from java_stdlib.lang import UnsupportedOperationException
        if not self.done:raise UnsupportedOperationException("Blocking lifecycle future waits are not implemented")
        if self.error is not None:raise UnsupportedOperationException("Java future failure wrapping is not implemented")
        return self.value
    def get(self):return self.join()


class ParallelDispatchEvent(Event):
    """Queue work until the host lifecycle barrier; no JVM parallel threads are claimed."""
    def __init__(self):
        Event.__init__(self)
        self.executed=[];self.enqueue_calls=0;self._work=[]
    def enqueueWork(self,work):
        if work is None or not callable(work):raise IllegalArgumentException("enqueueWork requires a callable")
        result=_LifecycleWorkResult()
        self._work.append((work,result));self.enqueue_calls+=1
        return result
    def drainWork(self):
        count=0
        while self._work:
            work,result=self._work.pop(0)
            try:result.value=work()
            except Exception as error:
                result.error=error;result.done=True
                self.cancelWork()
                raise
            result.done=True;self.executed.append(work);count+=1
        return count
    def cancelWork(self):
        from java_stdlib.lang import UnsupportedOperationException
        for work,result in self._work:
            result.error=UnsupportedOperationException("Owning lifecycle stage was abandoned")
            result.done=True
        self._work=[]
    def drainedCount(self):return len(self.executed)
    def isComplete(self):return not self._work


class FMLCommonSetupEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent。"""


class FMLClientSetupEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.FMLClientSetupEvent（真实 4 次）。"""


class FMLDedicatedServerSetupEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.FMLDedicatedServerSetupEvent。"""


class FMLLoadCompleteEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent。"""


class InterModEnqueueEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.InterModEnqueueEvent。"""


class InterModProcessEvent(ParallelDispatchEvent):
    """对应 net.neoforged.fml.event.lifecycle.InterModProcessEvent。"""

# ============================================================
# 名称映射表
# ============================================================

_PREFIX = "net.neoforged.fml.event.lifecycle."

JAVA_MAP = {
    _PREFIX + "ParallelDispatchEvent": ParallelDispatchEvent,
    _PREFIX + "FMLCommonSetupEvent": FMLCommonSetupEvent,
    _PREFIX + "FMLClientSetupEvent": FMLClientSetupEvent,
    _PREFIX + "FMLDedicatedServerSetupEvent": FMLDedicatedServerSetupEvent,
    _PREFIX + "FMLLoadCompleteEvent": FMLLoadCompleteEvent,
    _PREFIX + "InterModEnqueueEvent": InterModEnqueueEvent,
    _PREFIX + "InterModProcessEvent": InterModProcessEvent,
}


__all__ = [
    "ParallelDispatchEvent", "FMLCommonSetupEvent", "FMLClientSetupEvent",
    "FMLDedicatedServerSetupEvent", "FMLLoadCompleteEvent",
    "InterModEnqueueEvent", "InterModProcessEvent",
    "JAVA_MAP",
]

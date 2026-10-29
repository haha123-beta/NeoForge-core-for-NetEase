# -*- coding: utf-8 -*-
"""Callback state for reviewed source weaving; no native/JVM injection engine."""
from __future__ import absolute_import
from java_stdlib.lang import Integer,Boolean,RuntimeException

class CancellationException(RuntimeException):
    pass

class CallbackInfo(object):
    def __init__(self,identifier,cancellable=False):
        self._id=identifier;self._cancellable=bool(cancellable);self._cancelled=False
    def getId(self):return self._id
    def isCancellable(self):return self._cancellable
    def isCancelled(self):return self._cancelled
    def cancel(self):
        if not self._cancellable:raise CancellationException("The call %s is not cancellable." % self._id)
        self._cancelled=True

class CallbackInfoReturnable(CallbackInfo):
    def __init__(self,identifier,cancellable=False,value=None):
        CallbackInfo.__init__(self,identifier,cancellable)
        self._value=Boolean(value) if type(value) is bool else Integer(value) if type(value) is int else value
    def getReturnValue(self):return self._value
    def getReturnValueI(self):return 0 if self._value is None else self._value.intValue()
    def getReturnValueZ(self):return False if self._value is None else self._value.booleanValue()
    def setReturnValue(self,value):
        if type(value) is bool:value=Boolean(value)
        if value is not None and not isinstance(value,(Integer,Boolean)):raise TypeError("Only Integer/Boolean return callbacks are reviewed")
        self.cancel();self._value=value

class MixinCallbacks(object):
    ABI_VERSION=2

JAVA_MAP={'org.spongepowered.asm.mixin.injection.callback.CancellationException':CancellationException,
 'org.spongepowered.asm.mixin.injection.callback.CallbackInfo':CallbackInfo,
 'org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable':CallbackInfoReturnable,
 'neocore.runtime.MixinCallbacks':MixinCallbacks}

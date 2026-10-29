# -*- coding: utf-8 -*-
"""Explicit hooks for Python functions owned by NeoCore or translated mods.

This is not Sponge Mixin: no JVM bytecode, native-engine hooks, locals, slices,
ordinals, INVOKE redirects, automatic class patching, or annotation translation.
"""
from __future__ import absolute_import
import functools


class CallbackInfo(object):
    def __init__(self, identifier, cancellable=False):
        self._id = identifier
        self._cancellable = bool(cancellable)
        self._cancelled = False

    def getId(self):
        return self._id

    def isCancellable(self):
        return self._cancellable

    def isCancelled(self):
        return self._cancelled

    def cancel(self):
        if not self._cancellable:
            raise ValueError("This Python hook is not cancellable")
        self._cancelled = True


class CallbackInfoReturnable(CallbackInfo):
    def __init__(self, identifier, cancellable=False, return_value=None):
        CallbackInfo.__init__(self, identifier, cancellable)
        self._return_value = return_value

    def getReturnValue(self):
        return self._return_value

    def setReturnValue(self, value):
        self.cancel()
        self._return_value = value


class PythonHookRegistry(object):
    def __init__(self):
        self._targets = {}
        self._hooks = {}
        self._serial = 0

    def target(self, identifier):
        """Decorator applied explicitly where a Python function is defined."""
        def decorate(function):
            if identifier in self._targets:
                raise ValueError("Duplicate Python hook target: " + identifier)
            if not callable(function):
                raise ValueError("Hook target must be callable")
            self._targets[identifier] = function
            self._hooks[identifier] = []
            @functools.wraps(function)
            def wrapped(*args, **kwargs):
                return self.invoke(identifier, *args, **kwargs)
            return wrapped
        return decorate

    def inject(self, identifier, handler, at="HEAD", cancellable=False, priority=1000):
        if identifier not in self._targets:
            raise ValueError("Unregistered Python hook target: " + identifier)
        if at not in ("HEAD", "RETURN"):
            raise ValueError("Unsupported Python injection point: " + str(at))
        if not callable(handler):
            raise ValueError("Hook handler must be callable")
        self._serial += 1
        entry = (int(priority), self._serial, at, bool(cancellable), handler)
        self._hooks[identifier].append(entry)
        self._hooks[identifier].sort(key=lambda row: (-row[0], row[1]))
        def remove():
            if entry in self._hooks[identifier]:
                self._hooks[identifier].remove(entry)
        return remove

    def invoke(self, identifier, *args, **kwargs):
        if identifier not in self._targets:
            raise ValueError("Unregistered Python hook target: " + identifier)
        hooks = list(self._hooks[identifier])
        for priority, serial, at, cancellable, handler in hooks:
            if at != "HEAD":
                continue
            callback = CallbackInfoReturnable(identifier, cancellable)
            # Explicit bridge signature; an automatic Java injector adapter is not implied.
            handler(callback, args, dict(kwargs))
            if callback.isCancelled():
                return callback.getReturnValue()
        result = self._targets[identifier](*args, **kwargs)
        for priority, serial, at, cancellable, handler in hooks:
            if at != "RETURN":
                continue
            callback = CallbackInfoReturnable(identifier, cancellable, result)
            handler(callback, args, dict(kwargs))
            if callback.isCancelled():
                return callback.getReturnValue()
        return result

    def clear(self):
        """Remove injections without invalidating wrappers used by another owner."""
        for identifier in self._hooks:
            self._hooks[identifier] = []

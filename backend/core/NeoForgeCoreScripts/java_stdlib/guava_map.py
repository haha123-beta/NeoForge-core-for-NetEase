# -*- coding: utf-8 -*-
"""Reviewed Guava immutable map construction/data, an ordinary MC runtime library.

No third-party mod APIs or reflective dependency loading are supplied here.
"""
from __future__ import absolute_import
from java_stdlib.util import JavaMap,UnmodifiableMap
from java_stdlib.lang import NullPointerException,IllegalArgumentException

def _entries(source):
    if source is None:raise NullPointerException()
    if isinstance(source,JavaMap):return [(e.getKey(),e.getValue()) for e in source.entrySet()]
    if isinstance(source,dict):return list(source.items())
    raise TypeError('ImmutableMap.copyOf requires a reviewed map')

class ImmutableMap(UnmodifiableMap):
    def __init__(self,entries):
        values=JavaMap()
        for key,value in entries:
            if key is None or value is None:raise NullPointerException()
            if values.containsKey(key):raise IllegalArgumentException('Multiple entries with same key')
            values.put(key,value)
        UnmodifiableMap.__init__(self,values)
    @staticmethod
    def of(*args):
        if not args:return _EMPTY
        if len(args)%2 or len(args)>20:raise TypeError('Unreviewed ImmutableMap.of signature')
        return ImmutableMap([(args[i],args[i+1]) for i in range(0,len(args),2)])
    @staticmethod
    def copyOf(source):
        if isinstance(source,ImmutableMap):return source
        entries=_entries(source)
        return _EMPTY if not entries else ImmutableMap(entries)
    @staticmethod
    def builder():return Builder()

class Builder(object):
    def __init__(self):self._entries=[]
    def put(self,key,value):
        if key is None or value is None:raise NullPointerException()
        self._entries.append((key,value));return self
    def putAll(self,source):
        for key,value in _entries(source):self.put(key,value)
        return self
    def build(self):return _EMPTY if not self._entries else ImmutableMap(self._entries)
    def buildOrThrow(self):return self.build()

_EMPTY=ImmutableMap([])
ImmutableMap.Builder=Builder
JAVA_MAP={'com.google.common.collect.ImmutableMap':ImmutableMap,'com.google.common.collect.ImmutableMap$Builder':Builder}

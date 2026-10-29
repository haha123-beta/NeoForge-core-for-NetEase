# -*- coding: utf-8 -*-
"""Holder-set data used by official tool rules. Named sets are live bindings."""
from __future__ import absolute_import
from java_stdlib.lang import NullPointerException,System
from java_stdlib.util import ImmutableList,JavaSet,Optional,JavaStream

class HolderSet(object):
    def __init__(self):raise TypeError('HolderSet is an interface')
    @staticmethod
    def empty():return _EMPTY
    @staticmethod
    def direct(*values):
        return Direct(ImmutableList(values,reject_null=True))
    @staticmethod
    def _direct_list(values):return Direct(ImmutableList(values,reject_null=True))
    def size(self):return self._contents.size()
    def get(self,index):return self._contents.get(index)
    def iterator(self):return self._contents.iterator()
    def stream(self):return JavaStream(self._contents)
    def getRandomElement(self,random):
        if self.size()==0:return Optional.empty()
        if random is None:raise NullPointerException()
        return Optional.of(self.get(random.nextInt(self.size())))
    def __iter__(self):return iter(self._contents)

class Direct(HolderSet):
    def __init__(self,contents):self._contents=contents;self._set=None
    def contains(self,holder):
        if self._set is None:self._set=JavaSet(self._contents)
        if holder is None:raise NullPointerException()
        return self._set.contains(holder)
    def unwrapKey(self):return Optional.empty()
    def canSerializeIn(self,owner):return True
    def equals(self,other):return isinstance(other,Direct) and self._contents.equals(other._contents)
    def hashCode(self):return self._contents.hashCode()
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()

class Named(HolderSet):
    def __init__(self,owner,key):self._owner=owner;self._key=key;self._contents=ImmutableList([])
    def bind(self,contents):self._contents=ImmutableList(contents,reject_null=True)
    def key(self):return self._key
    def contains(self,holder):
        if holder is None:raise NullPointerException()
        return holder.isTag(self._key)
    def unwrapKey(self):return Optional.of(self._key)
    def canSerializeIn(self,owner):
        if self._owner is None:raise NullPointerException()
        return self._owner.canSerializeIn(owner)
    def equals(self,other):return self is other
    def hashCode(self):return System.identityHashCode(self)

_EMPTY=Direct(ImmutableList([]))
HolderSet.Direct=Direct
HolderSet.Named=Named
JAVA_MAP={'net.minecraft.core.HolderSet':HolderSet,'net.minecraft.core.HolderSet$Direct':Direct,'net.minecraft.core.HolderSet$Named':Named}

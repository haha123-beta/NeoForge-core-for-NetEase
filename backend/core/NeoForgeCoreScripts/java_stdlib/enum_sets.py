# -*- coding: utf-8 -*-
"""Typed enum sets; JDK21 EnumSet/RegularEnumSet/JumboEnumSet behavior."""
from __future__ import absolute_import
from java_stdlib._base import JavaCollection, JavaIterator, MISSING, hash_code, NoSuchElementException
from java_stdlib.lang import (Enum, JavaString, NullPointerException, ClassCastException,
    IllegalArgumentException, IllegalStateException)


def _values(collection):
    if collection is None:
        raise NullPointerException()
    iterator = getattr(collection, 'iterator', None)
    if callable(iterator):
        cursor = iterator()
        while cursor.hasNext():
            yield cursor.next()
    else:
        for value in collection:
            yield value


def _declaring(value):
    if value is None:
        raise NullPointerException()
    if not isinstance(value, Enum):
        raise ClassCastException('EnumSet requires enum constants')
    return value.getDeclaringClass()


class _EnumSetIterator(JavaIterator):
    _nc_JavaCollectionsABI = 1
    def __init__(self, owner):
        self.owner = owner
        self.index = 0
        self.unseen = owner._word(0)
        self.last = None

    def hasNext(self):
        while not self.unseen and self.index < self.owner._word_count - 1:
            self.index += 1
            self.unseen = self.owner._word(self.index)
        return bool(self.unseen)

    def next(self):
        if not self.hasNext():
            raise NoSuchElementException()
        bit = self.unseen & -self.unseen
        self.unseen -= bit
        ordinal = self.index * 64 + bit.bit_length() - 1
        self.last = ordinal
        return self.owner._universe[ordinal]

    def remove(self):
        if self.last is None:
            raise IllegalStateException()
        self.owner._bits &= ~(1 << self.last)
        self.last = None

    def forEachRemaining(self, action):
        if action is None:
            raise NullPointerException()
        invoke = getattr(action, 'accept', action)
        while self.hasNext():
            invoke(self.next())

    def __iter__(self):
        while self.hasNext():yield self.next()
    def __repr__(self):return "<EnumSetIterator>"
    def __next__(self):
        if not self.hasNext():raise StopIteration()
        return self.next()


class EnumSet(JavaCollection):
    _nc_JavaCollectionsABI = 1
    def __init__(self, element_type):
        if element_type is None:
            raise NullPointerException()
        if not isinstance(element_type, type) or not issubclass(element_type, Enum) or element_type is Enum:
            raise ClassCastException('EnumSet element type is not an enum')
        self._element_type = element_type
        self._universe = tuple(element_type._values)
        self._word_count = max(1, (len(self._universe) + 63) // 64)
        self._bits = 0

    @staticmethod
    def noneOf(element_type):return EnumSet(element_type)

    @staticmethod
    def allOf(element_type):
        result = EnumSet(element_type)
        result._bits = (1 << len(result._universe)) - 1
        return result

    @staticmethod
    def of(first, *rest):
        result = EnumSet(_declaring(first))
        result.add(first)
        # Java varargs arrays retain their declared shape; do not flatten a single enum.
        if len(rest) == 1:
            from java_stdlib.java_arrays import JavaArray
            if isinstance(rest[0], JavaArray):rest = tuple(rest[0])
        for value in rest:result.add(value)
        return result

    @staticmethod
    def copyOf(collection):
        if collection is None:raise NullPointerException()
        if isinstance(collection, EnumSet):return collection.clone()
        is_empty = getattr(collection, 'isEmpty', None)
        if is_empty() if callable(is_empty) else len(collection) == 0:
            raise IllegalArgumentException('Collection is empty')
        factory = getattr(collection, 'iterator', None)
        if callable(factory):
            iterator = factory()
            result = EnumSet.of(iterator.next())
            while iterator.hasNext():result.add(iterator.next())
        else:
            iterator = iter(collection)
            result = EnumSet.of(next(iterator))
            for value in iterator:result.add(value)
        return result

    @staticmethod
    def complementOf(collection):
        if collection is None:raise NullPointerException()
        if not isinstance(collection, EnumSet):raise ClassCastException('Expected EnumSet')
        result = collection.clone()
        result._bits = ((1 << len(result._universe)) - 1) ^ result._bits
        return result

    @staticmethod
    def range(first, last):
        owner = _declaring(first)
        if first.compareTo(last) > 0:raise IllegalArgumentException('Reversed enum range')
        result = EnumSet(owner)
        result._bits = ((1 << (last.ordinal() - first.ordinal() + 1)) - 1) << first.ordinal()
        return result

    def _word(self, index):return (self._bits >> (64 * index)) & ((1 << 64) - 1)
    def size(self):return bin(self._bits).count('1')
    def clear(self):self._bits = 0
    def _compatible(self, value):
        return isinstance(value, Enum) and value.getDeclaringClass() is self._element_type
    def contains(self, value):
        return self._compatible(value) and bool(self._bits & (1 << value.ordinal()))
    def add(self, value):
        if value is None:raise NullPointerException()
        if not self._compatible(value):raise ClassCastException('Wrong EnumSet element type')
        old = self._bits
        self._bits |= 1 << value.ordinal()
        return self._bits != old
    def remove(self, value):
        if not self._compatible(value):return False
        old = self._bits
        self._bits &= ~(1 << value.ordinal())
        return self._bits != old
    def iterator(self):return _EnumSetIterator(self)
    def __iter__(self):return iter(self.iterator())
    def _iter_raw(self):return list(self.iterator())
    def clone(self):
        result = EnumSet(self._element_type)
        result._bits = self._bits
        return result
    def addAll(self, collection):
        if isinstance(collection, EnumSet):
            if collection._element_type is not self._element_type:
                if collection.isEmpty():return False
                raise ClassCastException('Wrong EnumSet element type')
            old = self._bits;self._bits |= collection._bits
            return self._bits != old
        changed = False
        for value in _values(collection):
            if self.add(value):changed = True
        return changed
    def containsAll(self, collection):
        if isinstance(collection, EnumSet):
            if collection._element_type is not self._element_type:return collection.isEmpty()
            return not bool(collection._bits & ~self._bits)
        for value in _values(collection):
            if not self.contains(value):return False
        return True
    def removeAll(self, collection):
        if isinstance(collection, EnumSet):
            if collection._element_type is not self._element_type:return False
            old = self._bits;self._bits &= ~collection._bits
            return self._bits != old
        if collection is None:raise NullPointerException()
        old = self._bits
        # AbstractSet.removeAll chooses iteration by the smaller collection.
        size = collection.size() if callable(getattr(collection, 'size', None)) else len(collection)
        if self.size() > size:
            for value in _values(collection):self.remove(value)
        else:
            contains = getattr(collection, 'contains', None)
            for value in list(self):
                if (contains(value) if callable(contains) else value in collection):self.remove(value)
        return self._bits != old
    def retainAll(self, collection):
        if collection is None:raise NullPointerException()
        old = self._bits
        if isinstance(collection, EnumSet):
            self._bits &= collection._bits if collection._element_type is self._element_type else 0
        else:
            contains = getattr(collection, 'contains', None)
            for value in list(self):
                if not (contains(value) if callable(contains) else value in collection):self.remove(value)
        return self._bits != old
    def forEach(self, action):
        if action is None:raise NullPointerException()
        invoke=getattr(action,'accept',action)
        for value in self:invoke(value)
    def removeIf(self, predicate):
        if predicate is None:raise NullPointerException()
        test=getattr(predicate,'test',predicate)
        iterator=self.iterator();changed=False
        while iterator.hasNext():
            if test(iterator.next()):iterator.remove();changed=True
        return changed
    def equals(self, other):
        if other is self:return True
        if isinstance(other, EnumSet):
            if self._element_type is other._element_type:return self._bits == other._bits
            return self.isEmpty() and other.isEmpty()
        from java_stdlib.util import JavaSet
        if not isinstance(other, (JavaSet, set, frozenset)):return False
        return len(other) == self.size() and self.containsAll(other)
    def hashCode(self):
        result = sum(hash_code(value) for value in self)
        return int((result + 2147483648) % 4294967296 - 2147483648)
    def toString(self):return JavaString(u'[' + u', '.join(value.toString() for value in self) + u']')
    def __and__(self, other):return set(value for value in self if value in other)
    def __eq__(self, other):return self.equals(other)
    def __ne__(self, other):return not self.equals(other)
    def __hash__(self):return self.hashCode()
    def __str__(self):
        value = self.toString()
        return value if isinstance(value, str) else value.encode('utf-8')


class EnumSets(object):
    ABI_VERSION = 1

    @staticmethod
    def requireEnum(java_name, cls, constants):
        if not isinstance(cls, type) or not issubclass(cls, Enum) or cls is Enum:
            raise RuntimeError('NeoCore typed enum required: ' + java_name)
        actual = tuple(cls._values)
        if (tuple(value.name() for value in actual) != tuple(constants) or
                any(value.ordinal() != index or value.getDeclaringClass() is not cls
                    for index, value in enumerate(actual))):
            raise RuntimeError('NeoCore enum constants changed: ' + java_name)
        return cls


JAVA_MAP = {'java.util.EnumSet':EnumSet, 'neocore.runtime.EnumSets':EnumSets}

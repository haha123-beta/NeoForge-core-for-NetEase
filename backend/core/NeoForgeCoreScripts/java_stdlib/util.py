# -*- coding: utf-8 -*-
# java_stdlib/util.py
# Σ 层：java.util 的 Python 复刻
#
# 覆盖真实模组引用到的：List / ArrayList / LinkedList / Map / HashMap /
# LinkedHashMap / Set / HashSet / EnumSet / Collection / Iterator /
# ListIterator / Optional / OptionalInt / Objects / Arrays / Collections /
# UUID / Random / Stream。
#
# 一条必须守住的原则：
#   **方法名与语义跟着 Java 走，不跟着 Python 走。**
#   预翻译后的模组代码写的是 list.get(0)、map.put(k, v)、set.add(x)，
#   所以这里实现 get/put/add/size/isEmpty，而不是 __getitem__/append/len。
#   同时补上 Python 侧的对应方法，让两边代码可以混用，便于逐步替换。
#
# 引用统计来自真实模组 184 个 .class 的常量池：
#   List 170、Map 76、Iterator 60、Set 55、Optional 50、Arrays 8、EnumMap 7。
#   这些是「不能直接把 Java 类型映射成 Python 原生类型」的直接证据 ——
#   Python 的 list/dict 没有 get/put/isPresent 这些方法。

from __future__ import print_function
from __future__ import absolute_import

from java_stdlib.java_arrays import JavaArray, JavaArrays
from java_stdlib.lang import UnsupportedOperationException, RuntimeException, IndexOutOfBoundsException, NullPointerException as JavaNullPointerException, ClassCastException
import functools
import random as _random
import uuid as _uuid

try:
    from java_stdlib._base import (
        MISSING,
        JavaCollection,
        JavaIterator,
        ListIterator,
        IllegalStateException,
        IllegalArgumentException,
        NoSuchElementException,
        equals,
        hash_code,
        is_missing,
        to_python_list,
    )
    from java_stdlib import _base as _base_module
except ImportError:
    from _base import (  # type: ignore
        MISSING,
        JavaCollection,
        JavaIterator,
        ListIterator,
        IllegalStateException,
        IllegalArgumentException,
        NoSuchElementException,
        equals,
        hash_code,
        is_missing,
        to_python_list,
    )
    import _base as _base_module  # type: ignore


# ============================================================
# List
# ============================================================

class JavaList(JavaCollection):
    _nc_JavaCollectionsABI = 1
    """
    java.util.List 的实现（等价于 ArrayList）。

    需要偏移量的方法都按 Java 语义实现：
      set 返回旧值、remove 返回被删元素、indexOf 未命中返回 -1、
      subList 的 to 端点不含。
    """

    def __init__(self, items=MISSING):
        if items is MISSING:self._items=[]
        elif isinstance(items,int) and not isinstance(items,bool):
            if items<0:raise IllegalArgumentException("Negative ArrayList capacity")
            self._items=[]
        elif items is None:raise NullPointerException("ArrayList collection is null")
        else:self._items=list(items)
        self._mod_count=0

    def _version(self):return self._mod_count
    def _position(self,index):
        index=_to_int(index)
        if index<0 or index>self.size():raise IndexOutOfBoundsException("List insertion index out of bounds")
        return index
    def clear(self):
        self._items[:]=[]
        self._mod_count+=1
    def addAll(self,*args):
        if len(args) not in (1,2):raise TypeError("List.addAll requires collection or index/collection")
        index=self.size() if len(args)==1 else self._position(args[0])
        if args[-1] is None:raise NullPointerException("List.addAll collection is null")
        items=to_python_list(args[-1])
        self._items[index:index]=items
        self._mod_count+=1
        return bool(items)

    def removeAll(self,values):
        if values is None:raise NullPointerException("List.removeAll source is null")
        targets=to_python_list(values)
        changed=False
        for index in range(self.size()-1,-1,-1):
            if any(equals(self.get(index),target) for target in targets):
                self.remove(index,_nc_remove_mode='index');changed=True
        return changed
    def retainAll(self,values):
        if values is None:raise NullPointerException("List.retainAll source is null")
        targets=to_python_list(values);changed=False
        for index in range(self.size()-1,-1,-1):
            if not any(equals(self.get(index),target) for target in targets):
                self.remove(index,_nc_remove_mode='index');changed=True
        return changed

    # ---------------- 读取 ----------------

    def size(self):
        return len(self._items)

    def get(self, index):
        return self._items[self._check_index(index)]

    def _check_index(self, index):
        """Java list bounds reject negative indexes."""
        index = _to_int(index)
        if index < 0 or index >= len(self._items):
            raise IndexOutOfBoundsException(
                u"索引越界: {} (size={})".format(index, len(self._items)))
        return index

    def indexOf(self, value):
        for index, item in enumerate(self._items):
            if equals(item, value):
                return index
        return -1

    def lastIndexOf(self, value):
        for index in range(len(self._items) - 1, -1, -1):
            if equals(self._items[index], value):
                return index
        return -1

    # ---------------- 写入 ----------------

    def add(self,value,element=MISSING):
        if element is MISSING:
            self._items.append(value)
            self._mod_count+=1
            return True
        index=self._position(value)
        self._items.insert(index,element)
        self._mod_count+=1
        return None

    def set(self, index, value):
        """返回被替换掉的旧值（Java 语义）。"""
        index = self._check_index(index)
        previous = self._items[index]
        self._items[index] = value
        return previous

    def remove(self,target,_nc_remove_mode=None):
        by_index=_nc_remove_mode=='index' or (_nc_remove_mode is None and isinstance(target,int) and not isinstance(target,bool))
        if by_index:
            index=self._check_index(target)
            value=self._items.pop(index)
            self._mod_count+=1
            return value
        index=_find_index(self._items,target)
        if index is None:return False
        del self._items[index]
        self._mod_count+=1
        return True

    # ---------------- 视图 ----------------

    def subList(self, from_index, to_index):
        """Java 的 subList(from, to) 是左闭右开区间。"""
        from_index = _to_int(from_index)
        to_index = _to_int(to_index)
        if from_index < 0 or to_index > len(self._items):
            raise IndexOutOfBoundsException("Sublist range out of bounds")
        if from_index > to_index:
            raise IllegalArgumentException(
                u"区间非法: [{}, {}) size={}".format(
                    from_index, to_index, len(self._items)))
        return JavaSubList(self,from_index,to_index)

    def iterator(self):
        return LiveListIterator(self)

    def listIterator(self, index=0):
        return LiveListIterator(self,index)

    def _iter_raw(self):
        return self._items

    def sort(self, comparator=None):
        if comparator is None:
            self._items.sort()
        else:
            # Java 的 Comparator 约定返回负数/0/正数，cmp_to_key 正好对应
            self._items.sort(key=functools.cmp_to_key(comparator))
        self._mod_count+=1
        return None

    def reverse(self):
        self._items.reverse()
        return None

    def clone(self):
        return JavaList(self._items)

    # ---------------- 相等与哈希 ----------------

    def equals(self, other):
        if other is self:
            return True
        if isinstance(other, JavaList):
            other_items = other._items
        elif isinstance(other, (list, tuple)):
            other_items = list(other)
        else:
            return False

        if len(other_items) != len(self._items):
            return False
        for left, right in zip(self._items, other_items):
            if not equals(left, right):
                return False
        return True

    def hashCode(self):
        """Java List.hashCode 是按元素累加的（31*h + e），不是 Python 的 hash。"""
        result = 1
        for item in self._items:
            result = (31 * result + hash_code(item)) & 0xFFFFFFFF
        return (result & 0x7FFFFFFF) - (result & 0x80000000)

    def toString(self):
        return u"[" + u", ".join([_to_display(item) for item in self._items]) + u"]"

    # ---------------- 静态工厂（Java 9 的 List.of） ----------------

    @staticmethod
    def of(*values):
        if len(values)==1 and isinstance(values[0],JavaArray) and not (values[0].rank==1 and values[0].component in JavaArrays.PRIMITIVES):
            values=list(values[0])
        elif len(values)==1 and isinstance(values[0],(list,tuple)):
            values=values[0]
        return ImmutableList(values,reject_null=True)

    @staticmethod
    def copyOf(values):
        return ImmutableList(values,reject_null=True)

    # ---------------- Python 侧别名 ----------------

    def append(self,value):return self.add(value)
    def extend(self,values):return self.addAll(values)
    def pop(self,index=-1):return self.remove(self.size()-1 if index==-1 else index,_nc_remove_mode='index')

    def copy(self):
        return JavaList(self._items)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return JavaList(self._items[index])
        return self._items[index]

    def __setitem__(self,index,value):
        if isinstance(index,slice):raise UnsupportedOperationException("Use explicit Java list operations")
        self.set(index,value)
    def __delitem__(self,index):self.remove(index,_nc_remove_mode='index')

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<JavaList {}>".format(self.toString())


# ============================================================
# Set
# ============================================================


class JavaCollections(object):
    ABI_VERSION = 5
    @staticmethod
    def require(value, minimum=1):
        if value is None:raise NullPointerException("Collection receiver is null")
        if getattr(value,'_nc_JavaCollectionsABI',0)<minimum:
            raise UnsupportedOperationException("Collection implementation lacks NeoCore JavaCollections ABI1")
        return value


class ConcurrentModificationException(RuntimeException):
    _nc_java_name='java.util.ConcurrentModificationException'
    pass


class LiveListIterator(ListIterator):
    _nc_JavaCollectionsABI = 1
    """List iterator whose own edits update the original list and expected version."""
    def __init__(self,owner,index=0):
        self._owner=owner
        self._index=owner._position(index)
        self._last=-1
        self._expected=owner._version()
    def _check(self):
        if self._owner._version()!=self._expected:
            raise ConcurrentModificationException("List modified outside iterator")
    def hasNext(self):
        return self._index!=self._owner.size()
    def next(self):
        self._check()
        if self._index>=self._owner.size():raise NoSuchElementException("List iterator exhausted")
        self._last=self._index
        value=self._owner.get(self._index)
        self._index+=1
        return value
    def hasPrevious(self):
        return self._index>0
    def previous(self):
        self._check()
        if self._index<=0:raise NoSuchElementException("List iterator at start")
        self._index-=1
        self._last=self._index
        return self._owner.get(self._index)
    def nextIndex(self):return self._index
    def previousIndex(self):return self._index-1
    def remove(self):
        if self._last<0:raise IllegalStateException("Iterator has no current element")
        self._check()
        self._owner.remove(self._last,_nc_remove_mode='index')
        if self._last<self._index:self._index-=1
        self._last=-1
        self._expected=self._owner._version()
    def set(self,value):
        if self._last<0:raise IllegalStateException("Iterator has no current element")
        self._check()
        self._owner.set(self._last,value)
    def add(self,value):
        self._check()
        self._owner.add(self._index,value)
        self._index+=1
        self._last=-1
        self._expected=self._owner._version()
    def __iter__(self):
        while self.hasNext():yield self.next()


class ListWindow(object):
    """Private sequence facade; every access validates the source view."""
    def __init__(self,view):self.view=view
    def __len__(self):return self.view.size()
    def __iter__(self):
        for index in range(self.view.size()):yield self.view.get(index)
    def __getitem__(self,index):
        if isinstance(index,slice):return list(self)[index]
        return self.view.get(index)
    def __setitem__(self,index,value):
        if isinstance(index,slice):raise UnsupportedOperationException("List view slice assignment requires explicit Java operations")
        self.view.set(index,value)
    def __delitem__(self,index):self.view.remove(index,_nc_remove_mode='index')
    def append(self,value):self.view.add(value)
    def extend(self,values):self.view.addAll(values)
    def insert(self,index,value):self.view.add(index,value)
    def pop(self,index=-1):return self.view.remove(len(self)-1 if index==-1 else index,_nc_remove_mode='index')
    def reverse(self):
        values=list(self);values.reverse()
        for index,value in enumerate(values):self.view.set(index,value)
    def sort(self,key=None):
        values=sorted(list(self),key=key)
        for index,value in enumerate(values):self.view.set(index,value)


class JavaSubList(JavaList):
    def __init__(self,parent,start,end):
        self._parent=parent
        self._root=parent._root if isinstance(parent,JavaSubList) else parent
        self._offset=(parent._offset if isinstance(parent,JavaSubList) else 0)+start
        self._size=end-start
        self._expected=self._root._version()
        self._items=ListWindow(self)
    def _version(self):
        if self._root._version()!=self._expected:
            raise ConcurrentModificationException("Sublist source structurally modified")
        return self._expected
    def size(self):
        self._version()
        return self._size
    def get(self,index):return self._root.get(self._offset+self._check_index(index))
    def set(self,index,value):return self._root.set(self._offset+self._check_index(index),value)
    def sort(self,comparator=None):
        key=functools.cmp_to_key(comparator) if comparator is not None else None
        self._items.sort(key=key)
    def _updated(self,delta):
        view=self
        while isinstance(view,JavaSubList):
            view._size+=delta
            view._expected=self._root._version()
            view=view._parent
    def add(self,value,element=MISSING):
        index=self.size() if element is MISSING else self._position(value)
        item=value if element is MISSING else element
        result=self._root.add(self._offset+index,item)
        self._updated(1)
        return True if element is MISSING else result
    def remove(self,target,_nc_remove_mode=None):
        by_index=_nc_remove_mode=='index' or (_nc_remove_mode is None and isinstance(target,int) and not isinstance(target,bool))
        if by_index:index=self._check_index(target)
        else:
            index=self.indexOf(target)
            if index<0:return False
        value=self._root.remove(self._offset+index,_nc_remove_mode='index')
        self._updated(-1)
        return value if by_index else True
    def clear(self):
        for index in range(self.size()-1,-1,-1):self.remove(index,_nc_remove_mode='index')
    def addAll(self,*args):
        index=self.size() if len(args)==1 else self._position(args[0])
        if args[-1] is None:raise NullPointerException("Sublist.addAll source is null")
        values=to_python_list(args[-1])
        for offset,value in enumerate(values):self.add(index+offset,value)
        return bool(values)


class ImmutableList(JavaList):
    """Snapshot factory list or read-only live wrapper; no silent mutable fallback."""
    def __init__(self,values,live=False,reject_null=False):
        if values is None:raise NullPointerException("List source is null")
        self._owner=values if live and isinstance(values,JavaList) else None
        items=to_python_list(values)
        if reject_null and any(item is None for item in items):raise NullPointerException("Immutable factory list rejects null")
        self._items=self._owner._items if self._owner is not None else items
        self._mod_count=0
    def _version(self):return self._owner._version() if self._owner is not None else self._mod_count
    def add(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def addAll(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def set(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def remove(self,*args,**kwargs):raise UnsupportedOperationException("List is unmodifiable")
    def removeAll(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def retainAll(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def clear(self):raise UnsupportedOperationException("List is unmodifiable")
    def sort(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def reverse(self):
        # Collections.reverse may read/write nothing for an empty/singleton list.
        if self.size()>1:raise UnsupportedOperationException("List is unmodifiable")
    def __setitem__(self,*args):raise UnsupportedOperationException("List is unmodifiable")
    def __delitem__(self,*args):raise UnsupportedOperationException("List is unmodifiable")


class CollectionsEmptyList(ImmutableList):
    def __init__(self):ImmutableList.__init__(self,[])
    def clear(self):return None
    def sort(self,*args):return None
    def remove(self,target,_nc_remove_mode=None):
        if _nc_remove_mode=='index' or (_nc_remove_mode is None and isinstance(target,int) and not isinstance(target,bool)):
            raise UnsupportedOperationException("Empty list cannot remove by index")
        return False
    def removeAll(self,values):
        if values is None:raise NullPointerException("EmptyList.removeAll source is null")
        return False
    def retainAll(self,values):
        if values is None:raise NullPointerException("EmptyList.retainAll source is null")
        return False


class CollectionsSingletonList(ImmutableList):
    def __init__(self,value):ImmutableList.__init__(self,[value])
    def sort(self,*args):return None


class JavaSet(JavaCollection):
    """Hash/equality membership with insertion order and live removable cursors.

    LinkedHashSet insertion order is preserved. HashSet bucket order, sorted
    and concurrent sets require their own implementations.
    """
    _nc_JavaCollectionsABI = 3

    def __init__(self, items=MISSING):
        self._map = JavaMap()
        if items is MISSING:
            return
        if items is None:
            raise NullPointerException('Set source is null')
        if isinstance(items, int) and not isinstance(items, bool):
            if items < 0:
                raise IllegalArgumentException('Negative set capacity')
            return
        self.addAll(items)

    def size(self):
        return self._map.size()

    def add(self, value):
        return self._map.put(value, True) is None

    def contains(self, value):
        return self._map.containsKey(value)

    def remove(self, value):
        return self._map.remove(value) is not None

    def clear(self):
        self._map.clear()

    def iterator(self):
        return self._map.keySet().iterator()

    def __iter__(self):
        iterator = self.iterator()
        while iterator.hasNext():
            yield iterator.next()

    def _iter_raw(self):
        return list(self)

    def toArray(self, destination=MISSING):
        return JavaCollection.toArray(self, destination)

    def addAll(self, values):
        if values is None:
            raise NullPointerException('Set source is null')
        changed = False
        for value in values:
            changed = self.add(value) or changed
        return changed

    def containsAll(self, values):
        if values is None:
            raise NullPointerException('Set source is null')
        return all(self.contains(value) for value in values)

    def removeAll(self, values):
        if values is None:
            raise NullPointerException('Set source is null')
        if self.size() > len(values):
            changed = False
            for value in values:
                changed = self.remove(value) or changed
            return changed
        return self._filter(values, False)

    def _filter(self, values, retain):
        if values is None:
            raise NullPointerException('Set source is null')
        changed, iterator = False, self.iterator()
        while iterator.hasNext():
            value = iterator.next()
            found = values.contains(value) if hasattr(values, 'contains') else any(_map_equals(value, v) for v in values)
            if found != retain:
                iterator.remove()
                changed = True
        return changed

    def retainAll(self, values):
        return self._filter(values, True)

    def removeIf(self, predicate):
        if predicate is None:
            raise NullPointerException('Set predicate is null')
        iterator, changed = self.iterator(), False
        while iterator.hasNext():
            if _collection_call(predicate, 'test', iterator.next()):
                iterator.remove()
                changed = True
        return changed

    def forEach(self, action):
        if action is None:
            raise NullPointerException('Set action is null')
        for value in self:
            _collection_call(action, 'accept', value)

    def clone(self):
        return JavaSet(self)

    @staticmethod
    def of(*values):
        result = JavaSet()
        for value in values:
            if value is None:
                raise NullPointerException('Set.of rejects null')
            if not result.add(value):
                raise IllegalArgumentException('Duplicate Set.of element')
        return UnmodifiableSet(result)

    @staticmethod
    def ofArray(values):
        if values is None:
            raise NullPointerException('Set.of varargs array is null')
        return JavaSet.of(*list(values))

    @staticmethod
    def copyOf(values):
        if values is None:
            raise NullPointerException('Set.copyOf source is null')
        result = JavaSet(values)
        if result.contains(None):
            raise NullPointerException('Set.copyOf rejects null')
        return UnmodifiableSet(result)

    def equals(self, other):
        if other is self:
            return True
        if not isinstance(other, (JavaSet, EnumSet, set, frozenset)):
            return False
        if len(other) != self.size():
            return False
        try:
            return self.containsAll(other)
        except (JavaNullPointerException, ClassCastException):
            return False

    def hashCode(self):
        total = sum(_map_hash(value) for value in self)
        return int((total & 0x7fffffff) - (total & 0x80000000))

    def toString(self):
        return u'[' + u', '.join(u'(this Collection)' if value is self else _to_display(value) for value in self) + u']'

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()




# ============================================================
# Map
# ============================================================

class MapEntry(object):
    """A mutable map node; replacement values remain visible to existing iterators."""
    _nc_JavaCollectionsABI = 2

    def __init__(self, key, value):
        self.key, self.value = key, value

    def getKey(self):
        return self.key

    def getValue(self):
        return self.value

    def setValue(self, value):
        previous, self.value = self.value, value
        return previous

    def equals(self, other):
        return (isinstance(other, MapEntry) and
                _map_equals(self.getKey(), other.getKey()) and
                _map_equals(self.getValue(), other.getValue()))

    def hashCode(self):
        value = _map_hash(self.getKey()) ^ _map_hash(self.getValue())
        return (value & 0x7fffffff) - (value & 0x80000000)

    def __iter__(self):
        return iter((self.getKey(), self.getValue()))

    def __getitem__(self, index):
        return (self.getKey(), self.getValue())[index]

    def __repr__(self):
        return u"<MapEntry {}={}>".format(_to_display(self.getKey()), _to_display(self.getValue()))

    def toString(self):
        return u'{}={}'.format(_to_display(self.getKey()), _to_display(self.getValue()))

    def __str__(self):
        return self.toString()


def _map_equals(query, stored):
    if query is stored:
        return True
    if query is None:
        return False
    method = getattr(query, 'equals', None)
    return bool(method(stored)) if callable(method) else equals(query, stored)


def _map_hash(value):
    try:
        text_types = (basestring,)
    except NameError:
        text_types = (str, bytes)
    if isinstance(value, text_types):
        # Native and JavaString text must share the same hash in both interpreters.
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        result = 0
        for character in value:
            unit = ord(character)
            if unit > 0xffff:
                unit -= 0x10000
                result = (31 * result + 0xd800 + (unit >> 10)) & 0xffffffff
                unit = 0xdc00 + (unit & 1023)
            result = (31 * result + unit) & 0xffffffff
        return int(result if result < 0x80000000 else result - 0x100000000)
    method = getattr(value, 'hashCode', None)
    return method() if callable(method) else hash_code(value)


class _MapKey(object):
    def __init__(self, value):
        self.value, self.code = value, _map_hash(value)

    def __hash__(self):
        return self.code

    def __eq__(self, query):
        return isinstance(query, _MapKey) and _map_equals(query.value, self.value)


def _collection_call(callback, method, *args):
    if callback is None:
        raise NullPointerException('Collection callback is null')
    target = getattr(callback, method, callback)
    return target(*args)


class JavaMap(JavaCollection):
    """Insertion-order map data, live views and structural-change detection.

    This is not a JVM HashMap bucket layout, sorted map or concurrent map.
    """
    _nc_JavaCollectionsABI = 4

    def __init__(self, initial=MISSING, load_factor=MISSING):
        from collections import OrderedDict
        if load_factor is not MISSING:
            if not isinstance(initial, int) or isinstance(initial, bool):
                raise TypeError('Capacity/load-factor constructor needs int capacity')
            if load_factor <= 0 or load_factor != load_factor:
                raise IllegalArgumentException('Nonpositive or NaN map load factor')
        self._data = OrderedDict()
        self._mod_count = 0
        self._views = {}
        self._head = self._tail = None
        if initial is MISSING:
            return
        if initial is None:
            raise NullPointerException('Map source is null')
        if isinstance(initial, int) and not isinstance(initial, bool):
            if initial < 0:
                raise IllegalArgumentException('Negative map capacity')
            return
        self.putAll(initial)

    def size(self):
        return len(self._data)

    def put(self, key, value):
        token = _MapKey(key)
        entry = self._data.get(token)
        if entry is not None:
            previous = entry.setValue(value)
            self._after_access(entry)
            return previous
        node = MapEntry(key, value)
        node._map_token = token
        node._before, node._after = self._tail, None
        if self._tail is None:
            self._head = node
        else:
            self._tail._after = node
        self._tail = node
        self._data[token] = node
        self._mod_count += 1
        return None

    def get(self, key):
        return self.getOrDefault(key, None)

    def getOrDefault(self, key, default):
        entry = self._data.get(_MapKey(key))
        if entry is None:
            return default
        self._after_access(entry)
        return entry.getValue()

    def _after_access(self, entry):
        return None

    def containsKey(self, key):
        return _MapKey(key) in self._data

    def containsValue(self, value):
        return any(_map_equals(value, entry.getValue()) for entry in self._data.values())

    def remove(self, key, value=MISSING):
        token = _MapKey(key)
        entry = self._data.get(token)
        if entry is None or (value is not MISSING and not _map_equals(value, entry.getValue())):
            return None if value is MISSING else False
        self._remove_entry(entry)
        return entry.getValue() if value is MISSING else True

    def _remove_entry(self, entry):
        del self._data[entry._map_token]
        if entry._before is None:
            self._head = entry._after
        else:
            entry._before._after = entry._after
        if entry._after is None:
            self._tail = entry._before
        else:
            entry._after._before = entry._before
        entry._before = entry._after = None
        self._mod_count += 1

    def putIfAbsent(self, key, value):
        previous = self.get(key)
        if previous is None:
            self.put(key, value)
        return previous

    def computeIfAbsent(self, key, factory):
        if factory is None:
            raise NullPointerException('Map function is null')
        entry = self._data.get(_MapKey(key))
        if entry is not None and entry.getValue() is not None:
            self._after_access(entry)
            return entry.getValue()
        version = self._mod_count
        result = _collection_call(factory, 'apply', key)
        if version != self._mod_count:
            raise ConcurrentModificationException('Map changed during mapping callback')
        if result is not None:
            if entry is None:
                self.put(key, result)
            else:
                entry.setValue(result)
                self._after_access(entry)
        return result

    def replace(self, key, *values):
        if len(values) not in (1, 2):
            raise TypeError('Map.replace needs value or old/new values')
        entry = self._data.get(_MapKey(key))
        if entry is None:
            return None if len(values) == 1 else False
        if len(values) == 1:
            previous = entry.setValue(values[0])
            self._after_access(entry)
            return previous
        if not _map_equals(values[0], entry.getValue()):
            return False
        entry.setValue(values[1])
        self._after_access(entry)
        return True

    def computeIfPresent(self, key, function):
        if function is None:
            raise NullPointerException('Map function is null')
        entry = self._data.get(_MapKey(key))
        if entry is None or entry.getValue() is None:
            return None
        version = self._mod_count
        result = _collection_call(function, 'apply', key, entry.getValue())
        if version != self._mod_count:
            raise ConcurrentModificationException('Map changed during remapping callback')
        if result is None:
            self.remove(key)
        else:
            entry.setValue(result)
            self._after_access(entry)
        return result

    def compute(self, key, function):
        if function is None:
            raise NullPointerException('Map function is null')
        entry = self._data.get(_MapKey(key))
        version = self._mod_count
        result = _collection_call(function, 'apply', key, None if entry is None else entry.getValue())
        if version != self._mod_count:
            raise ConcurrentModificationException('Map changed during remapping callback')
        if result is None:
            if entry is not None:
                self.remove(key)
        elif entry is not None:
            entry.setValue(result)
            self._after_access(entry)
        else:
            self.put(key, result)
        return result

    def merge(self, key, value, function):
        if value is None or function is None:
            raise NullPointerException('Map merge value/function is null')
        entry = self._data.get(_MapKey(key))
        if entry is None:
            self.put(key, value)
            return value
        if entry.getValue() is None:
            result = value
        else:
            version = self._mod_count
            result = _collection_call(function, 'apply', entry.getValue(), value)
            if version != self._mod_count:
                raise ConcurrentModificationException('Map changed during merge callback')
        if result is None:
            self.remove(key)
        else:
            entry.setValue(result)
            self._after_access(entry)
        return result

    def replaceAll(self, function):
        if function is None:
            raise NullPointerException('Map function is null')
        version, node = self._mod_count, self._head
        while node is not None:
            node.setValue(_collection_call(function, 'apply', node.getKey(), node.getValue()))
            node = node._after
        if version != self._mod_count:
            raise ConcurrentModificationException('Map changed during replaceAll')


    def putAll(self, values):
        if values is None:
            raise NullPointerException('Map source is null')
        pairs = values.items() if isinstance(values, dict) else [(e.getKey(), e.getValue()) for e in values.entrySet()]
        for key, value in pairs:
            self.put(key, value)

    def clear(self):
        self._data.clear()
        self._head = self._tail = None
        self._mod_count += 1

    def forEach(self, action):
        if action is None:
            raise NullPointerException('Map action is null')
        version, node = self._mod_count, self._head
        while node is not None:
            _collection_call(action, 'accept', node.getKey(), node.getValue())
            node = node._after
        if version != self._mod_count:
            raise ConcurrentModificationException('Map changed during forEach')

    def clone(self):
        return JavaMap(self)

    @staticmethod
    def of(*pairs):
        if len(pairs) % 2:
            raise IllegalArgumentException('Map.of requires key/value pairs')
        result = JavaMap()
        for index in range(0, len(pairs), 2):
            key, value = pairs[index:index + 2]
            if key is None or value is None:
                raise NullPointerException('Map.of rejects null')
            if result.containsKey(key):
                raise IllegalArgumentException('Duplicate Map.of key')
            result.put(key, value)
        return UnmodifiableMap(result)

    @staticmethod
    def copyOf(values):
        copied = JavaMap(values)
        for entry in copied.entrySet():
            if entry.getKey() is None or entry.getValue() is None:
                raise NullPointerException('Map.copyOf rejects null')
        return UnmodifiableMap(copied)

    def _view(self, kind):
        if kind not in self._views:
            self._views[kind] = _MapValues(self, kind) if kind == 'values' else _MapSet(self, kind)
        return self._views[kind]

    def keySet(self):
        return self._view('keys')

    def values(self):
        return self._view('values')

    def entrySet(self):
        return self._view('entries')

    def _iter_raw(self):
        return list(self._data.values())

    def iterator(self):
        return self.entrySet().iterator()

    def contains(self, value):
        return self.containsKey(value)

    def equals(self, other):
        if other is self:
            return True
        if isinstance(other, dict):
            other = JavaMap(other)
        if not isinstance(other, JavaMap) or self.size() != other.size():
            return False
        for entry in self.entrySet():
            value = other.get(entry.getKey())
            if not _map_equals(entry.getValue(), value):
                return False
            if value is None and not other.containsKey(entry.getKey()):
                return False
        return True

    def hashCode(self):
        total = sum(entry.hashCode() for entry in self.entrySet())
        return int((total & 0x7fffffff) - (total & 0x80000000))

    def toString(self):
        return u'{' + u', '.join(u'{}={}'.format(_to_display(e.getKey()), _to_display(e.getValue())) for e in self.entrySet()) + u'}'

    def keys(self):
        return list(self.keySet())

    def items(self):
        return [(e.getKey(), e.getValue()) for e in self.entrySet()]

    def update(self, other):
        return self.putAll(other)

    def copy(self):
        return JavaMap(self)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.put(key, value)

    def __delitem__(self, key):
        self.remove(key)

    def __contains__(self, key):
        return self.containsKey(key)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()


class JavaLinkedHashMap(JavaMap):
    """Reviewed insertion/access order; sequenced and eviction APIs stay separate."""
    _nc_JavaCollectionsABI = 5

    def __init__(self, initial=MISSING, load_factor=MISSING, access_order=MISSING):
        self._access_order = False if access_order is MISSING else bool(access_order)
        if access_order is not MISSING and load_factor is MISSING:
            raise TypeError('LinkedHashMap access order needs capacity and load factor')
        JavaMap.__init__(self, initial, load_factor)

    def _after_access(self, node):
        if not self._access_order or node is self._tail:
            return
        before, after = node._before, node._after
        if before is None:
            self._head = after
        else:
            before._after = after
        if after is not None:
            after._before = before
        node._before, node._after = self._tail, None
        self._tail._after = node
        self._tail = node
        self._mod_count += 1

    def clone(self):
        result = JavaLinkedHashMap(self)
        result._access_order = self._access_order
        return result

    def containsValue(self, value):
        node = self._head
        while node is not None:
            if _map_equals(value, node.getValue()):
                return True
            node = node._after
        return False

    def copy(self):
        return self.clone()




class _MapIterator(object):
    _nc_JavaCollectionsABI = 2

    def __init__(self, view):
        self._view = view
        self._next = view._owner._head
        self._version = view._owner._mod_count
        self._last = None

    def _check(self):
        if self._version != self._view._owner._mod_count:
            raise ConcurrentModificationException('Map structurally changed outside iterator')

    def hasNext(self):
        return self._next is not None

    def next(self):
        self._check()
        if not self.hasNext():
            raise NoSuchElementException('Map iterator exhausted')
        node = self._next
        self._next = node._after
        self._last = node
        return self._view._element(node)

    def remove(self):
        if self._last is None:
            raise IllegalStateException('Iterator.remove requires next')
        self._check()
        self._view._owner._remove_entry(self._last)
        self._version = self._view._owner._mod_count
        self._last = None

    def forEachRemaining(self, action):
        if action is None:
            raise NullPointerException('Iterator action is null')
        while self.hasNext():
            _collection_call(action, 'accept', self.next())

    def __iter__(self):
        return self

    def __next__(self):
        if not self.hasNext():
            raise StopIteration()
        return self.next()


class _MapValues(JavaCollection):
    _nc_JavaCollectionsABI = 3

    def __init__(self, owner, kind):
        self._owner, self._kind = owner, kind

    def size(self):
        return self._owner.size()

    def _element(self, node):
        return node.getKey() if self._kind == 'keys' else node.getValue() if self._kind == 'values' else node

    def iterator(self):
        return _MapIterator(self)

    def __iter__(self):
        iterator = self.iterator()
        while iterator.hasNext():
            yield iterator.next()

    def _iter_raw(self):
        return list(self)

    def toString(self):
        return u'[' + u', '.join(_to_display(value) for value in self) + u']'

    def __str__(self):
        return self.toString()

    def contains(self, value):
        return any(_map_equals(value, element) for element in self)

    def containsAll(self, values):
        if values is None:
            raise NullPointerException('Map view source is null')
        return all(self.contains(value) for value in values)

    def add(self, value):
        raise UnsupportedOperationException('Map views do not support add')

    def addAll(self, values):
        if values is None:
            raise NullPointerException('Map view source is null')
        changed = False
        for value in values:
            changed = self.add(value) or changed
        return changed

    def remove(self, value):
        iterator = self.iterator()
        while iterator.hasNext():
            if _map_equals(value, iterator.next()):
                iterator.remove()
                return True
        return False

    def _filter(self, values, retain):
        if values is None:
            raise NullPointerException('Map view source is null')
        changed = False
        iterator = self.iterator()
        while iterator.hasNext():
            value = iterator.next()
            found = values.contains(value) if hasattr(values, 'contains') else any(_map_equals(value, v) for v in values)
            if found != retain:
                iterator.remove()
                changed = True
        return changed

    def removeAll(self, values):
        return self._filter(values, False)

    def retainAll(self, values):
        return self._filter(values, True)

    def removeIf(self, predicate):
        if predicate is None:
            raise NullPointerException('Predicate is null')
        iterator, changed = self.iterator(), False
        while iterator.hasNext():
            if _collection_call(predicate, 'test', iterator.next()):
                iterator.remove()
                changed = True
        return changed

    def forEach(self, action):
        if action is None:
            raise NullPointerException('Collection action is null')
        version, node = self._owner._mod_count, self._owner._head
        while node is not None:
            _collection_call(action, 'accept', self._element(node))
            node = node._after
        if self._owner._mod_count != version:
            raise ConcurrentModificationException('Map changed during forEach')

    def clear(self):
        self._owner.clear()


class _MapSet(_MapValues, JavaSet):
    def contains(self, value):
        if self._kind == 'keys':
            return self._owner.containsKey(value)
        if not isinstance(value, MapEntry):
            return False
        node = self._owner._data.get(_MapKey(value.getKey()))
        return node is not None and node.equals(value)

    def remove(self, value):
        if self._kind == 'keys':
            node = self._owner._data.get(_MapKey(value))
            if node is None:
                return False
            self._owner._remove_entry(node)
            return True
        return isinstance(value, MapEntry) and self._owner.remove(value.getKey(), value.getValue())

    def removeAll(self, values):
        if values is None:
            raise NullPointerException('Map view source is null')
        if self.size() > len(values):
            changed = False
            for value in values:
                changed = self.remove(value) or changed
            return changed
        return self._filter(values, False)

    def hashCode(self):
        total = sum(_map_hash(value) for value in self)
        return int((total & 0x7fffffff) - (total & 0x80000000))

    def toArray(self, destination=MISSING):
        return JavaCollection.toArray(self, destination)

    def toString(self):
        return u'[' + u', '.join(_to_display(value) for value in self) + u']'


class _ReadOnlyEntry(MapEntry):
    def __init__(self, entry):
        self._entry = entry

    def getKey(self):
        return self._entry.getKey()

    def getValue(self):
        return self._entry.getValue()

    key = property(getKey)
    value = property(getValue)

    def setValue(self, value):
        raise UnsupportedOperationException('Unmodifiable entry')


class _ReadOnlyIterator(object):
    _nc_JavaCollectionsABI = 2

    def __init__(self, iterator, entries=False):
        self._iterator, self._entries = iterator, entries

    def hasNext(self):
        return self._iterator.hasNext()

    def next(self):
        value = self._iterator.next()
        return _ReadOnlyEntry(value) if self._entries else value

    def remove(self):
        raise UnsupportedOperationException('Unmodifiable iterator')

    def forEachRemaining(self, action):
        if action is None:
            raise NullPointerException('Iterator action is null')
        while self.hasNext():
            _collection_call(action, 'accept', self.next())


class _UnmodifiableCollection(JavaCollection):
    _nc_JavaCollectionsABI = 3

    def __init__(self, values, entries=False):
        if values is None:
            raise NullPointerException('Unmodifiable collection source is null')
        self._values, self._entries = values, entries

    def size(self):
        return self._values.size()

    def iterator(self):
        return _ReadOnlyIterator(self._values.iterator(), self._entries)

    def __iter__(self):
        iterator = self.iterator()
        while iterator.hasNext():
            yield iterator.next()

    def _iter_raw(self):
        return list(self)

    def toString(self):
        return u'[' + u', '.join(_to_display(value) for value in self) + u']'

    def __str__(self):
        return self.toString()

    def contains(self, value):
        return any(_map_equals(element, value) for element in self) if self._entries else self._values.contains(value)

    def containsAll(self, values):
        if values is None:
            raise NullPointerException('Collection source is null')
        return all(self.contains(value) for value in values)

    def _reject(self, *args, **kwargs):
        raise UnsupportedOperationException('Unmodifiable collection')

    add = addAll = remove = removeAll = retainAll = clear = removeIf = _reject

    def forEach(self, action):
        if action is None:
            raise NullPointerException('Collection action is null')
        if callable(getattr(self._values, 'forEach', None)):
            self._values.forEach(lambda value: _collection_call(action, 'accept', _ReadOnlyEntry(value) if self._entries else value))
        else:
            for value in self:
                _collection_call(action, 'accept', value)


class UnmodifiableSet(_UnmodifiableCollection, JavaSet):
    def toArray(self, destination=MISSING):
        return JavaCollection.toArray(self, destination)

    def hashCode(self):
        total = sum(_map_hash(value) for value in self)
        return int((total & 0x7fffffff) - (total & 0x80000000))

    def toString(self):
        return u'[' + u', '.join(_to_display(value) for value in self) + u']'


class UnmodifiableMap(JavaMap):
    def __init__(self, values):
        if values is None:
            raise NullPointerException('Unmodifiable map source is null')
        self._map, self._views = values, {}

    def size(self):
        return self._map.size()

    def get(self, key):
        return self._map.get(key)

    def getOrDefault(self, key, default):
        return self._map.getOrDefault(key, default)

    def containsKey(self, key):
        return self._map.containsKey(key)

    def containsValue(self, value):
        return self._map.containsValue(value)

    def forEach(self, action):
        return self._map.forEach(action)

    def _view(self, kind):
        if kind not in self._views:
            original = getattr(self._map, {'keys': 'keySet', 'values': 'values', 'entries': 'entrySet'}[kind])()
            self._views[kind] = (_UnmodifiableCollection(original) if kind == 'values' else
                                 UnmodifiableSet(original, entries=kind == 'entries'))
        return self._views[kind]

    def _iter_raw(self):
        return list(self.entrySet())

    def _reject(self, *args, **kwargs):
        raise UnsupportedOperationException('Unmodifiable map')

    put = putAll = remove = clear = putIfAbsent = computeIfAbsent = computeIfPresent = compute = merge = replace = replaceAll = _reject




class CollectionsEmptySet(JavaSet):
    def add(self, value):
        raise UnsupportedOperationException('Empty set')

    def clear(self):
        return None

    def contains(self, value):
        return False

    def remove(self, value):
        return False

    def forEach(self, action):
        if action is None:
            raise NullPointerException('Empty set action is null')

    def removeIf(self, predicate):
        if predicate is None:
            raise NullPointerException('Empty set predicate is null')
        return False


class CollectionsEmptyMap(UnmodifiableMap):
    def __init__(self):
        UnmodifiableMap.__init__(self, JavaMap())

    def clear(self):
        return None

    def get(self, key):
        return None

    def getOrDefault(self, key, default):
        return default

    def containsKey(self, key):
        return False

    def containsValue(self, value):
        return False

    def remove(self, key, value=MISSING):
        if value is not MISSING:
            return self._reject()
        return None

    def putAll(self, values):
        if values is None:
            raise NullPointerException('Empty map source is null')
        if len(values):
            self._reject()

    def replaceAll(self, function):
        if function is None:
            raise NullPointerException('Empty map function is null')

    def keySet(self):
        return Collections.emptySet()

    values = entrySet = keySet




# ============================================================
# Optional
# ============================================================

class JavaOptional(object):
    """
    java.util.Optional（真实模组引用 50 次，属高频）。

    Java 的 get() 在空值时会抛 NoSuchElementException，
    这里保持同样行为 —— 静默返回 None 会把 bug 藏起来。
    """

    def __init__(self, value, present=True):
        self._value = value
        self._present = bool(present)

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def of(value):
        if value is None:
            raise IllegalArgumentException(u"Optional.of 不接受 null，请用 ofNullable")
        return JavaOptional(value, True)

    @staticmethod
    def ofNullable(value):
        if value is None:
            return JavaOptional(None, False)
        return JavaOptional(value, True)

    @staticmethod
    def empty():
        return JavaOptional(None, False)

    # ---------------- 查询 ----------------

    def isPresent(self):
        return self._present

    def isEmpty(self):
        return not self._present

    def get(self):
        if not self._present:
            raise NoSuchElementException(u"Optional 为空时不能取值")
        return self._value

    def orElse(self, other):
        return self._value if self._present else other

    def orElseGet(self, supplier):
        if self._present:
            return self._value
        return supplier()

    def orElseThrow(self, exception_factory=None):
        if self._present:
            return self._value
        if exception_factory is None:
            raise NoSuchElementException(u"Optional 为空")
        raise exception_factory()

    def filter(self, predicate):
        if self._present and predicate(self._value):
            return self
        return JavaOptional.empty()

    def map(self, mapper):
        if not self._present:
            return JavaOptional.empty()
        return JavaOptional.ofNullable(mapper(self._value))

    def flatMap(self, mapper):
        if not self._present:
            return JavaOptional.empty()
        return mapper(self._value)

    def ifPresent(self, consumer):
        if self._present:
            consumer(self._value)
        return None

    def ifPresentOrElse(self, consumer, empty_action):
        if self._present:
            consumer(self._value)
        else:
            empty_action()
        return None

    # ---------------- 与 Python 互操作 ----------------

    def orNull(self):
        """Python 侧便利方法：直接取或 None。"""
        return self._value if self._present else None

    def equals(self, other):
        if not isinstance(other, JavaOptional):
            return False
        if self._present != other._present:
            return False
        if not self._present:
            return True
        return equals(self._value, other._value)

    def hashCode(self):
        return 0 if not self._present else hash_code(self._value)

    def toString(self):
        if not self._present:
            return u"Optional.empty"
        return u"Optional[{}]".format(_to_display(self._value))

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


class JavaOptionalInt(object):
    """
    java.util.OptionalInt。

    与 Optional 的差别是「空」不能用 0 表示（0 是合法值），
    所以用显式的 present 标志，不靠取值猜测。
    """

    def __init__(self, value=0, present=True):
        self._value = _to_int(value)
        self._present = bool(present)

    @staticmethod
    def of(value):
        return JavaOptionalInt(value, True)

    @staticmethod
    def empty():
        return JavaOptionalInt(0, False)

    def isPresent(self):
        return self._present

    def isEmpty(self):
        return not self._present

    def getAsInt(self):
        if not self._present:
            raise NoSuchElementException(u"OptionalInt 为空时不能取值")
        return self._value

    def orElse(self, other):
        return self._value if self._present else _to_int(other)

    def __int__(self):
        return self.getAsInt()

    def __repr__(self):
        if not self._present:
            return u"<OptionalInt.empty>"
        return u"<OptionalInt[{}]>".format(self._value)


# ============================================================
# 工具类
# ============================================================

class Objects(object):
    """java.util.Objects 的静态方法集合。"""

    @staticmethod
    def isNull(value):
        return value is None

    @staticmethod
    def nonNull(value):
        return value is not None

    @staticmethod
    def equals(left, right):
        return equals(left, right)

    @staticmethod
    def deepEquals(left, right):
        return equals(left, right)

    @staticmethod
    def requireNonNull(value, message=None):
        if value is None:
            raise NullPointerException(message)
        return value

    @staticmethod
    def hash(*values):
        return hash_code(list(values))

    @staticmethod
    def hashCode(value):
        return hash_code(value)

    @staticmethod
    def toString(value, default=u""):
        return default if value is None else _to_display(value)

    @staticmethod
    def compare(left, right, comparator=None):
        if comparator is not None:
            return comparator(left, right)
        if left is None and right is None:
            return 0
        if left is None:
            return -1
        if right is None:
            return 1
        return -1 if left < right else (0 if left == right else 1)


class ArrayListView(JavaList):
    """Arrays.asList fixed-size list backed by the original reference array."""
    def __init__(self,array):
        self._array=array
        self._items=array._values
        self._mod_count=0
    def set(self,index,value):
        old=JavaArrays.get(self._array,index)
        JavaArrays.set(self._array,index,value)
        return old
    def sort(self,comparator=None):
        self._items.sort(key=functools.cmp_to_key(comparator) if comparator is not None else None)
    def addAll(self,*args):
        if len(args) not in (1,2):raise TypeError("List.addAll arity invalid")
        if len(args)==2:self._position(args[0])
        if args[-1] is None:raise NullPointerException("List.addAll source is null")
        if to_python_list(args[-1]):raise UnsupportedOperationException("Fixed array-backed list cannot grow")
        return False
    def add(self,*args):
        raise UnsupportedOperationException("Fixed array-backed list cannot add")
    def remove(self,*args,**kwargs):
        raise UnsupportedOperationException("Fixed array-backed list cannot remove")
    def clear(self):
        if self._items:
            raise UnsupportedOperationException("Fixed array-backed list cannot clear")
    def append(self,value):
        return self.add(value)
    def extend(self,values):
        raise UnsupportedOperationException("Fixed array-backed list cannot extend")
    def pop(self,*args):
        return self.remove(*args)
    def iterator(self):
        return ArrayListViewIterator(self)
    def __setitem__(self,index,value):
        self.set(index,value)
    def __delitem__(self,index):
        self.remove(index)


class ArrayListViewIterator(object):
    _nc_JavaCollectionsABI = 1
    def __init__(self,view):
        self._view,self._index=view,0
    def hasNext(self):
        return self._index<self._view.size()
    def next(self):
        if not self.hasNext():raise NoSuchElementException("Array-backed iterator exhausted")
        value=self._view.get(self._index)
        self._index+=1
        return value
    def remove(self):
        raise UnsupportedOperationException("Fixed array-backed iterator cannot remove")


class Arrays(object):
    """java.util.Arrays 的静态方法集合。"""

    @staticmethod
    def asList(*values):
        """
        Java 的 asList 有两种调用形态：asList(a, b, c) 与 asList(array)。

        翻译后的代码两种都可能出现，所以这里做兼容：
        只有一个参数且是可迭代对象时，展开它。
        """
        if len(values)==1 and isinstance(values[0],JavaArray):
            array=values[0]
            if array.rank==1 and array.component in JavaArrays.PRIMITIVES:
                array=JavaArrays.initialized('java.lang.Object',1,[array],object)
            return ArrayListView(array)
        if len(values) == 1:
            only = values[0]
            if isinstance(only, JavaList):
                return JavaList(only.toArray())
            if isinstance(only, JavaCollection):
                return JavaList(only.toArray())
            if isinstance(only, (list, tuple, set, frozenset)):
                return JavaList(list(only))
        return JavaList(list(values))

    @staticmethod
    def stream(values):
        return JavaStream(to_python_list(values))

    @staticmethod
    def sort(values):
        """Java 的 Arrays.sort 是原地排序。"""
        if isinstance(values, JavaList):
            values.sort()
            return None
        if isinstance(values,JavaArray):
            values._values.sort()
            return None
        values.sort()
        return None

    @staticmethod
    def toString(values):
        return u"[" + u", ".join(
            [_to_display(item) for item in to_python_list(values)]) + u"]"

    @staticmethod
    def copyOf(values, length=None):
        if isinstance(values,JavaArray):
            return JavaArrays.copy(values,len(values) if length is None else length)
        items = to_python_list(values)
        if length is None:
            return JavaList(items)
        length = _to_int(length)
        if length <= len(items):
            return JavaList(items[:length])
        padded = list(items)
        while len(padded) < length:
            padded.append(None)
        return JavaList(padded)

    @staticmethod
    def copyOfRange(values, from_index, to_index):
        """
        对应 java.util.Arrays.copyOfRange（真实模组用了 3 次）。

        语义：左闭右开；to_index 超出长度时用 null 补齐，
        与 copyOf 的超长补 null 行为一致。
        """
        if isinstance(values,JavaArray):
            return JavaArrays.copyRange(values,from_index,to_index)
        items = to_python_list(values)
        from_index = _to_int(from_index)
        to_index = _to_int(to_index)

        if from_index < 0 or from_index > len(items):
            raise IllegalArgumentException(
                u"fromIndex {} out of range (length={})".format(
                    from_index, len(items)))
        if to_index < from_index:
            raise IllegalArgumentException(
                u"toIndex {} < fromIndex {}".format(to_index, from_index))

        chunk = items[from_index:to_index]
        if to_index > len(items):
            while len(chunk) < to_index - from_index:
                chunk.append(None)
        return JavaList(chunk)

    @staticmethod
    def equals(left, right):
        """
        对应 java.util.Arrays.equals（真实模组用了 1 次）。

        按元素逐个比较（不是比对象身份），长度不同即为假。
        """
        left_items = to_python_list(left)
        right_items = to_python_list(right)
        if len(left_items) != len(right_items):
            return False
        for index in range(len(left_items)):
            if not equals(left_items[index], right_items[index]):
                return False
        return True

    @staticmethod
    def fill(values, value):
        if isinstance(values, JavaList):
            for index in range(values.size()):
                values.set(index, value)
            return None
        for index in range(len(values)):
            values[index] = value
        return None


class Collections(object):
    """java.util.Collections 的静态方法集合（只做常用部分）。"""

    _EMPTY_LIST = None
    _EMPTY_MAP = None
    _EMPTY_SET = None

    @staticmethod
    def emptyList():
        if Collections._EMPTY_LIST is None:
            Collections._EMPTY_LIST = CollectionsEmptyList()
        return Collections._EMPTY_LIST

    @staticmethod
    def emptyMap():
        if Collections._EMPTY_MAP is None:
            Collections._EMPTY_MAP = CollectionsEmptyMap()
        return Collections._EMPTY_MAP

    @staticmethod
    def emptySet():
        if Collections._EMPTY_SET is None:
            Collections._EMPTY_SET = CollectionsEmptySet()
        return Collections._EMPTY_SET

    @staticmethod
    def singletonList(value):
        return CollectionsSingletonList(value)

    @staticmethod
    def unmodifiableList(values):
        return ImmutableList(values,live=True)

    @staticmethod
    def unmodifiableMap(values):
        return UnmodifiableMap(values)

    @staticmethod
    def unmodifiableSet(values):
        return UnmodifiableSet(values)

    @staticmethod
    def sort(values, comparator=None):
        if isinstance(values, JavaList):
            values.sort(comparator)
        else:
            values.sort()
        return None

    @staticmethod
    def reverse(values):
        if isinstance(values, JavaList):
            values.reverse()
        else:
            values.reverse()
        return None

    @staticmethod
    def addAll(collection, *values):
        changed = False
        for value in values:
            if collection.add(value):
                changed = True
        return changed

    @staticmethod
    def frequency(collection, value):
        count = 0
        for item in to_python_list(collection):
            if equals(item, value):
                count += 1
        return count


class UUID(object):
    """
    java.util.UUID。

    通过 __str__ / __eq__ 让行为贴近字符串，
    这样日志、比较、拼接都不会出问题。
    """

    def __init__(self,most,least=None):
        if least is not None:
            self._bits=((int(most)&0xffffffffffffffff)<<64)|(int(least)&0xffffffffffffffff)
        else:
            if most is None:raise JavaNullPointerException()
            text=u'{}'.format(most);parts=text.split('-')
            if len(text)>36 or len(parts)!=5 or any(not p for p in parts):raise IllegalArgumentException('Invalid UUID string')
            numbers=[]
            for p in parts:
                if p.startswith('+'):p=p[1:]
                if not p or any(c not in '0123456789abcdefABCDEF' for c in p):raise IllegalArgumentException('Invalid UUID string')
                n=int(p,16)
                if n>0x7fffffffffffffff:raise IllegalArgumentException('UUID segment overflow')
                numbers.append(n)
            a,b,c,d,e=numbers
            self._bits=((a&0xffffffff)<<96)|((b&0xffff)<<80)|((c&0xffff)<<64)|((d&0xffff)<<48)|(e&0xffffffffffff)
        h='%032x'%self._bits;self._text=h[:8]+'-'+h[8:12]+'-'+h[12:16]+'-'+h[16:20]+'-'+h[20:]
    @staticmethod
    def fromString(text):return UUID(text)
    @staticmethod
    def randomUUID():return UUID(u'{}'.format(_uuid.uuid4()))
    def toString(self):
        from java_stdlib.lang import JavaString
        return JavaString(self._text)
    def getMostSignificantBits(self):
        n=self._bits>>64;return n-(1<<64) if n&(1<<63) else n
    def getLeastSignificantBits(self):
        n=self._bits&0xffffffffffffffff;return n-(1<<64) if n&(1<<63) else n
    def equals(self,other):return isinstance(other,UUID) and self._bits==other._bits
    def hashCode(self):
        n=(self._bits>>64)^(self._bits&0xffffffffffffffff);n=((n>>32)^n)&0xffffffff
        return n-(1<<32) if n&(1<<31) else n

    def __str__(self):
        return self._text

    def __repr__(self):
        return u"<UUID {}>".format(self._text)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()


class JavaRandom(object):
    """java.util.Random：把 Python 的 random 包成方法名一致的形态。"""

    def __init__(self, seed=None):
        if seed is None:
            self._random = _random.Random()
        else:
            self._random = _random.Random(_to_int(seed))

    def nextInt(self, bound=None):
        if bound is None:
            return self._random.randint(-2147483648, 2147483647)
        bound = _to_int(bound)
        if bound <= 0:
            raise IllegalArgumentException(u"nextInt 的 bound 必须为正数")
        return self._random.randrange(bound)

    def nextLong(self):
        return self._random.randint(-9223372036854775808, 9223372036854775807)

    def nextDouble(self):
        return self._random.random()

    def nextFloat(self):
        return self._random.random()

    def nextBoolean(self):
        return self._random.random() < 0.5

    def setSeed(self, seed):
        self._random.seed(_to_int(seed))
        return None

    def __repr__(self):
        return u"<JavaRandom>"


# ============================================================
# Stream
# ============================================================

class JavaStream(object):
    """
    java.util.stream.Stream 的轻量实现（真实模组引用 23 次）。

    以链式调用为主：
        list.stream().filter(p).map(m).collect(Collectors.toList())
    中间操作先记成待执行的函数序列，遇到终止操作才真正跑，
    与 Java 的惰性求值一致，也避免产生无谓的中间列表。
    """

    def __init__(self, items=None):
        self._items = list(items) if items is not None else []
        self._pipeline = []

    def _chain(self, operation):
        stream = JavaStream(self._items)
        stream._pipeline = self._pipeline + [operation]
        return stream

    def _materialize(self):
        result = list(self._items)
        for operation in self._pipeline:
            result = operation(result)
        return result

    # ---------------- 中间操作 ----------------

    def filter(self, predicate):
        return self._chain(lambda items: [x for x in items if predicate(x)])

    def map(self, mapper):
        return self._chain(lambda items: [mapper(x) for x in items])

    def flatMap(self, mapper):
        def flatten(items):
            out = []
            for item in items:
                out.extend(to_python_list(mapper(item)))
            return out
        return self._chain(flatten)

    def distinct(self):
        def dedupe(items):
            seen = JavaSet()
            out = []
            for item in items:
                if seen.add(item):
                    out.append(item)
            return out
        return self._chain(dedupe)

    def sorted(self, comparator=None):
        if comparator is None:
            return self._chain(lambda items: sorted(items))
        return self._chain(
            lambda items: sorted(items, key=functools.cmp_to_key(comparator)))

    def limit(self, count):
        count = _to_int(count)
        return self._chain(lambda items: items[:count])

    def skip(self, count):
        count = _to_int(count)
        return self._chain(lambda items: items[count:])

    # ---------------- 终止操作 ----------------

    def collect(self, collector=None):
        return JavaList(self._materialize())

    def toList(self):
        return JavaList(self._materialize())

    def forEach(self, consumer):
        for item in self._materialize():
            consumer(item)
        return None

    def count(self):
        return len(self._materialize())

    def findFirst(self):
        items = self._materialize()
        if items:
            return JavaOptional.ofNullable(items[0])
        return JavaOptional.empty()

    def anyMatch(self, predicate):
        for item in self._materialize():
            if predicate(item):
                return True
        return False

    def allMatch(self, predicate):
        for item in self._materialize():
            if not predicate(item):
                return False
        return True

    def noneMatch(self, predicate):
        return not self.anyMatch(predicate)

    def reduce(self, identity_or_accumulator, accumulator=None):
        items = self._materialize()
        if accumulator is None:
            if not items:
                return JavaOptional.empty()
            result = items[0]
            for item in items[1:]:
                result = identity_or_accumulator(result, item)
            return JavaOptional.ofNullable(result)

        result = identity_or_accumulator
        for item in items:
            result = accumulator(result, item)
        return result

    def toArray(self):
        return self._materialize()

    def iterator(self):
        return JavaIterator(self._materialize())

    def __iter__(self):
        return iter(self._materialize())

    def __repr__(self):
        return u"<JavaStream>"


# ============================================================
# 异常
# ============================================================

NullPointerException = JavaNullPointerException


# ============================================================
# 内部辅助
# ============================================================

def _to_int(value):
    """把 Java 的数值盒子或字符串转成 int。"""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise IllegalArgumentException(u"无法转成整数: {!r}".format(value))


def _hash_key(value, depth=0):
    """
    把任意值转成可做 dict 键的稳定键。

    为什么不能直接拿元素当键：
      Java 的 equals/hashCode 语义与 Python 不同 ——
      例如 JavaList 按内容相等，而 Python 对象默认按身份。

    为什么复杂对象必须**递归按内容**构键，而不能只用 hashCode()：
      曾有真实 bug —— MapEntry.hashCode() 是 key ^ value，
      对 "z"/"Z"、"a"/"A" 这类键值，异或结果恰好都是 0，
      于是三条不同的 Entry 得到同一个键，在 entrySet() 里被去重成一条。
      所以这里对集合与 Entry 递归展开内容，保证不同内容 → 不同键。

    depth 用于防御自引用结构导致的无限递归。
    """
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (str, bytes, int, float)):
        return (type(value).__name__, value)

    if depth > 8:
        # 嵌套过深：退化成「类型 + 哈希」，不再继续展开
        return ("deep", type(value).__name__, hash_code(value))

    if isinstance(value, MapEntry):
        return ("MapEntry",
                _hash_key(value.key, depth + 1),
                _hash_key(value.value, depth + 1))

    if isinstance(value, JavaList):
        return ("JavaList", tuple([_hash_key(item, depth + 1)
                                   for item in value._iter_raw()]))

    if isinstance(value, JavaSet):
        # Set 无序，所以把元素的键排序后再拼，保证同内容得到同键
        keys = [_hash_key(item, depth + 1) for item in value._iter_raw()]
        keys.sort(key=lambda item: u"{}".format(item))
        return ("JavaSet", tuple(keys))

    if isinstance(value, JavaMap):
        keys = []
        for entry in value._iter_raw():
            keys.append((_hash_key(entry.key, depth + 1),
                         _hash_key(entry.value, depth + 1)))
        keys.sort(key=lambda item: u"{}".format(item))
        return ("JavaMap", tuple(keys))

    if value is MISSING:
        return ("missing",)

    # 其它对象：用 hashCode + 类型名，保证 Java 相等语义下键一致
    return ("object", type(value).__name__, hash_code(value))


def _find_index(items, value):
    """按 Java 相等语义在列表里找下标，找不到返回 None。"""
    for index, item in enumerate(items):
        if equals(item, value):
            return index
    return None


def _to_display(value):
    """Java 的字符串拼接语义：null 拼出来是字面量 null。"""
    if value is None:
        return u"null"
    if isinstance(value, bool):
        return u"true" if value else u"false"
    return u"{}".format(value)


# ============================================================
# 兼容别名
# ============================================================

# 把本模块的 List 实现交给基座，供 to_java_list() 使用。
# 放在这里是因为 JavaList 已经定义完毕；基座靠它避免反向 import util。
_base_module.bind_java_list(JavaList)

# Java 的接口名与实现类名都要能解析到具体实现
ArrayList = JavaList
LinkedList = JavaList
List = JavaList
Collection = JavaCollection
HashMap = JavaMap
LinkedHashMap = JavaLinkedHashMap
TreeMap = JavaMap
Map = JavaMap
HashSet = JavaSet
LinkedHashSet = JavaSet
TreeSet = JavaSet
from java_stdlib.enum_sets import EnumSet
Set = JavaSet
Optional = JavaOptional
OptionalInt = JavaOptionalInt
Iterator = JavaIterator
Random = JavaRandom
Stream = JavaStream


# ============================================================
# 名称映射表：供翻译层 / 未映射 api 兜底层查询
# ============================================================

JAVA_MAP = {
    # List
    "neocore.runtime.JavaCollections": JavaCollections,
    "java.util.NoSuchElementException": NoSuchElementException,
    "java.util.ConcurrentModificationException": ConcurrentModificationException,
    "java.util.List": JavaList,
    "java.util.ArrayList": JavaList,
    "java.util.LinkedList": JavaList,
    "java.util.Vector": JavaList,
    "java.util.Stack": JavaList,
    "java.util.AbstractList": JavaList,

    # Set
    "java.util.Set": JavaSet,
    "java.util.HashSet": JavaSet,
    "java.util.LinkedHashSet": JavaSet,
    "java.util.TreeSet": JavaSet,
    "java.util.EnumSet": EnumSet,
    "java.util.AbstractSet": JavaSet,

    # Map
    "java.util.Map": JavaMap,
    "java.util.HashMap": JavaMap,
    "java.util.LinkedHashMap": JavaLinkedHashMap,
    "java.util.TreeMap": JavaMap,
    "java.util.EnumMap": JavaMap,
    "java.util.WeakHashMap": JavaMap,
    "java.util.concurrent.ConcurrentHashMap": JavaMap,
    "java.util.AbstractMap": JavaMap,
    "java.util.Map$Entry": MapEntry,
    "java.util.Map.Entry": MapEntry,

    # 集合接口
    "java.util.Collection": JavaCollection,
    "java.lang.Iterable": JavaCollection,
    "java.util.Iterator": JavaIterator,
    "java.util.ListIterator": ListIterator,

    # Optional
    "java.util.Optional": JavaOptional,
    "java.util.OptionalInt": JavaOptionalInt,

    # 工具类
    "java.util.Objects": Objects,
    "java.util.Arrays": Arrays,
    "java.util.Collections": Collections,
    "java.util.UUID": UUID,
    "java.util.Random": JavaRandom,

    # Stream
    "java.util.stream.Stream": JavaStream,
    "java.util.stream.LongStream": JavaStream,
    "java.util.stream.StreamSupport": JavaStream,
}


__all__ = [
    "JavaList",
    "JavaSet",
    "JavaMap",
    "JavaOptional",
    "JavaOptionalInt",
    "JavaIterator",
    "ListIterator",
    "MapEntry",
    "JavaStream",
    "Objects",
    "Arrays",
    "Collections",
    "UUID",
    "JavaRandom",
    "NullPointerException",
    "ArrayList",
    "LinkedList",
    "List",
    "Collection",
    "HashMap",
    "LinkedHashMap",
    "TreeMap",
    "Map",
    "HashSet",
    "LinkedHashSet",
    "TreeSet",
    "EnumSet",
    "Set",
    "Optional",
    "OptionalInt",
    "Iterator",
    "Random",
    "Stream",
    "JAVA_MAP",
]

# -*- coding: utf-8 -*-
# java_stdlib/_base.py
# Σ 层基座：Java 与 Python 之间的转换约定
#
# 本层要解决的问题：
#   Java 模组的代码被预翻译成 Python 之后，里面仍然是 Java 的写法 ——
#   list.get(0)、map.put(k, v)、optional.isPresent()、str.length()。
#   这些方法名 Python 原生类型（list / dict / str）全都没有，
#   所以不能把 java.util.List 直接映射成 Python 的 list，必须复刻 Java 语义。
#
#   真实模组的引用统计印证了这一点：
#     java/util/List 170 次、java/util/Map 76 次、java/util/Iterator 60 次、
#     java/util/Set 55 次、java/util/Optional 50 次。
#
# 编码约定（与核心包一致）：只用 Python 2 与 Python 3 语义完全一致的语法。
# 因此不用枚举、不用 f-string、不用 dict/set 推导式，也不写非 ASCII 标识符。

from __future__ import print_function
from __future__ import absolute_import



# ============================================================
# 空值约定
# ============================================================

class _Missing(object):
    """
    表示「键不存在」。

    为什么不能用 None 当默认值：
      Java 的 Map 里「键不存在」和「键存在但值为 null」是两件事，
      get() 都返回 null 无法区分；而 Python 的 dict.get 需要靠哨兵值
      才能真正判断。用 None 当哨兵会把两种情况混成一种。

    这个哨兵还刻意实现成「假值」，这样 `if missing:` 会走 else 分支，
    不会因为哨兵对象本身为真而误判。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    # Python 2 里的布尔语义
    __nonzero__ = __bool__

    def __repr__(self):
        return u"<MISSING>"

    def __str__(self):
        return u"<MISSING>"


MISSING = _Missing()


def is_null(value):
    """Java 的 == null 判断。"""
    return value is None


def is_missing(value):
    """是否是「键不存在」哨兵。"""
    return value is MISSING


# ============================================================
# 跨版本基础工具
# ============================================================

# Python 2 里 chr() 只接受 0-255，非 ASCII 码位要用 unichr()；
# Python 3 把 unichr() 去掉了，chr() 直接支持全部码位。
# 两版语义不一致，所以在这里统一收口，其它模块一律调 to_char()。
try:
    _unichr = unichr  # noqa: F821  (Python 2)
except NameError:
    _unichr = chr     # Python 3


def to_char(code_point):
    """把码位转成单字符，同时兼容 Python 2 与 Python 3。"""
    return _unichr(code_point)


# ============================================================
# 相等与哈希
# ============================================================

def equals(left, right):
    """
    Java 的 Objects.equals / Object.equals 语义。

    与 Python 的 == 的差别：这里把「同为 null」视为相等（Java 的语义），
    并且优先尊重对象自己实现的 equals 方法。
    """
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    custom = getattr(left, "equals", None)
    if custom is not None and not isinstance(left, (int, float, bool, str)):
        try:
            return bool(custom(right))
        except Exception:
            pass

    try:
        return bool(left == right)
    except Exception:
        return left is right


def hash_code(value):
    """
    Java 的 Object.hashCode 语义。

    约定：同一次运行内，相等的对象必须有相同的 hashCode；
    Java 与 Python 的哈希算法并不相同，所以这里只保证「自洽」，
    不保证与 JVM 给出同一个数值 —— 依赖具体数值的代码本身就不该存在。
    """
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1231 if value else 1237
    if isinstance(value, int):
        # 收敛到 32 位有符号范围，贴近 Java 的 int
        return (value & 0x7FFFFFFF) - (value & 0x80000000)
    if isinstance(value, float):
        return int(value) if value == int(value) else hash(value)

    custom = getattr(value, "hashCode", None)
    if custom is not None and not isinstance(value, (str, bytes)):
        try:
            return custom()
        except Exception:
            pass

    if isinstance(value, bytes):
        value = value.decode("latin-1")

    if isinstance(value, str):
        # Java String.hashCode 的算法：s[0]*31^(n-1) + ... + s[n-1]
        result = 0
        for char in value:
            result = (result * 31 + ord(char)) & 0xFFFFFFFF
        return (result & 0x7FFFFFFF) - (result & 0x80000000)

    return hash(value)


# ============================================================
# 类型转换
# ============================================================

def is_java_collection(value):
    """
    判断是不是 Java 集合。

    用鸭子类型而不是 isinstance：util.py 里的具体类要 import _base，
    如果 _base 反向 import util 就成循环导入了。
    判定条件是「有 Java 集合的三件套」（size / isEmpty / toArray）。
    """
    return (hasattr(value, "size") and hasattr(value, "isEmpty")
            and hasattr(value, "toArray"))


def to_python_list(value):
    """
    把 Java 集合转成 Python 列表（拷贝）。

    不认识的对象当作单元素列表，避免调用方还要判类型。
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if is_java_collection(value):
        return list(value.toArray())

    iterator = getattr(value, "iterator", None)
    if iterator is not None:
        try:
            return list(iterator())
        except Exception:
            pass

    return [value]


def to_java_list(value):
    """
    把 Python 列表（或可迭代对象）包成 Java 的 List。

    具体实现由 util.py 在加载时注入（见本文件末尾的 bind_java_list），
    这样 _base 不需要 import util，避免循环导入。
    """
    if value is None:
        return _java_list_factory([])
    if is_java_collection(value) and hasattr(value, "get"):
        # 有 get(index) 说明已经是 List 语义，不必再包一层
        return value
    return _java_list_factory(list(value))


# JavaList 的构造器由 util.py 注入。
# 为什么不直接 import：util.py 需要 import _base，反向 import 会成环。
_java_list_factory = None


def bind_java_list(factory):
    """由 util.py 调用，把自己实现的 List 构造器交给基座。"""
    global _java_list_factory
    _java_list_factory = factory


def get_java_list_factory():
    """取已注入的 List 构造器；未注入时明确报错，而不是静默返回 None。"""
    if _java_list_factory is None:
        raise IllegalStateException(
            u"JavaList 构造器尚未注入，请先 import java_stdlib.util")
    return _java_list_factory


def as_int(value, default=0):
    """按 Java 的数值语义取整数：布尔转 0/1，字符串尽量解析。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value, default=0.0):
    """按 Java 的数值语义取浮点。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# 迭代器
# ============================================================

class JavaIterator(object):
    """
    Java 的 Iterator<T>。

    Java 的迭代器接口是 hasNext() / next()，
    不是 Python 的 __next__/StopIteration 协议，所以必须包一层。
    """

    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def hasNext(self):
        return self._index < len(self._items)

    def next(self):
        if self._index >= len(self._items):
            raise StopIteration()
        value = self._items[self._index]
        self._index += 1
        return value

    def remove(self):
        """
        Java 的 Iterator.remove 会删除「刚刚 next 返回的那个元素」。

        这里只支持删除最近返回的一个，超出范围时报错，
        与 Java 抛 IllegalStateException 的时机一致。
        """
        if self._index == 0:
            raise IllegalStateException(u"Iterator.remove 之前没有调用 next")
        self._index -= 1
        del self._items[self._index]

    # 让 Python 的 for 也能直接遍历，方便自测与混用
    def __iter__(self):
        while self.hasNext():
            yield self.next()

    def forEachRemaining(self, action):
        if action is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException()
        invoke = getattr(action, 'accept', action)
        while self.hasNext():invoke(self.next())

    def __repr__(self):
        return u"<JavaIterator at {} of {}>".format(self._index, len(self._items))


class ListIterator(JavaIterator):
    """Java 的 ListIterator：比 Iterator 多了反向遍历。"""

    def hasPrevious(self):
        return self._index > 0

    def previous(self):
        if self._index <= 0:
            raise StopIteration()
        self._index -= 1
        return self._items[self._index]

    def nextIndex(self):
        return self._index

    def previousIndex(self):
        return self._index - 1


# ============================================================
# 异常
# ============================================================

class JavaThrowable(Exception):
    """Common Java throwable identity, separate from Java Exception and Error."""
    _nc_java_name='java.lang.Throwable'
    def getMessage(self):
        from java_stdlib.lang import JavaString, _TEXT_TYPES
        message=self._nc_message if hasattr(self,'_nc_message') else self.args[0] if self.args else None
        if message is None:return None
        if not isinstance(message,_TEXT_TYPES):raise UnsupportedOperationException("Native throwable message constructor has no reviewed Java semantics")
        return JavaString(message)
    def getLocalizedMessage(self):return self.getMessage()
    def getCause(self):
        if not hasattr(self,'_nc_cause_initialized') and (len(self.args)>1 or self.args and isinstance(self.args[0],JavaThrowable)):
            raise UnsupportedOperationException("Native cause constructor requires JavaExceptions typed constructor ABI")
        return getattr(self,'_nc_cause',None)
    def initCause(self,cause):
        self.getCause()
        if getattr(self,'_nc_cause_initialized',False):raise IllegalStateException("Cause has already been initialized")
        if cause is self:raise IllegalArgumentException("Self-causation is not permitted")
        if cause is not None and not isinstance(cause,JavaThrowable):raise UnsupportedOperationException("Cause is not a Java throwable")
        self._nc_cause=cause;self._nc_cause_initialized=True
        return self
    def toString(self):
        from java_stdlib.lang import JavaString
        name=self.__dict__.get('_nc_java_name') or self.__class__.__dict__.get('_nc_java_name') or 'java.lang.'+self.__class__.__name__
        message=self.getLocalizedMessage()
        return JavaString(name if message is None else name+u': '+message)
    def getStackTrace(self):
        raise UnsupportedOperationException("Java stack frames are not implemented; Python frames are not JVM frames")
    def setStackTrace(self,*args):
        raise UnsupportedOperationException("Java stack frames are not implemented")
    def fillInStackTrace(self):
        raise UnsupportedOperationException("Java stack frames are not implemented")
    def printStackTrace(self,*args):
        raise UnsupportedOperationException("Java stack rendering is not implemented")
    def addSuppressed(self,exception):
        from java_stdlib.lang import NullPointerException
        if exception is self:raise IllegalArgumentException("Self-suppression is not permitted")
        if exception is None:raise NullPointerException("Suppressed throwable is null")
        if not isinstance(exception,JavaThrowable):raise UnsupportedOperationException("Suppressed value is not a Java throwable")
        if not hasattr(self,'_nc_suppressed'):self._nc_suppressed=[]
        self._nc_suppressed.append(exception)
    def getSuppressed(self):
        from java_stdlib.java_arrays import JavaArrays
        return JavaArrays.initialized('java.lang.Throwable',1,list(getattr(self,'_nc_suppressed',[])),JavaThrowable)



class JavaError(JavaThrowable):
    _nc_java_name='java.lang.Error'
    """java.lang.Error; it must not match catch(java.lang.Exception)."""


class JavaException(JavaThrowable):
    _nc_java_name='java.lang.Exception'
    """java.lang.Exception identity for checked and runtime exceptions."""


class RuntimeException(JavaException):
    """Shared java.lang.RuntimeException identity for all standard-library layers."""


class IllegalStateException(RuntimeException):
    """对应 java.lang.IllegalStateException。"""


class NoSuchElementException(RuntimeException):
    _nc_java_name='java.util.NoSuchElementException'
    """对应 java.util.NoSuchElementException，next() 越界时抛出。"""


class UnsupportedOperationException(RuntimeException):
    """对应 java.lang.UnsupportedOperationException，用于不可变视图。"""


class IllegalArgumentException(RuntimeException):
    """对应 java.lang.IllegalArgumentException，参数越界或非法。"""


# ============================================================
# 集合基类
# ============================================================

class JavaCollection(object):
    """
    Java 集合的公共行为。

    真实模组里 java/util/Collection 被引用 25 次，说明不少方法
    是按 Collection 接口调用的（contains / size / isEmpty / iterator），
    所以把这些放在共同基类上，而不是每个实现各写一遍。
    """

    def size(self):
        raise NotImplementedError()

    def isEmpty(self):
        return self.size() == 0

    def __len__(self):
        """让 Python 的 len() 与真值判断也能用。"""
        return self.size()

    def __nonzero__(self):
        return not self.isEmpty()

    def __bool__(self):
        return not self.isEmpty()

    def contains(self, value):
        for item in self._iter_raw():
            if equals(item, value):
                return True
        return False

    def containsAll(self, other):
        for item in to_python_list(other):
            if not self.contains(item):
                return False
        return True

    def iterator(self):
        return JavaIterator(self._iter_raw())

    def _iter_raw(self):
        raise NotImplementedError()

    def toArray(self, destination=MISSING):
        from java_stdlib.java_arrays import JavaArray, JavaArrays, ArrayStoreException
        items = list(self._iter_raw())
        if destination is MISSING:
            return JavaArrays.initialized('java.lang.Object', 1, items, object)
        destination = JavaArrays._array(destination)
        if destination.rank == 1 and destination.component in JavaArrays.PRIMITIVES:
            raise ArrayStoreException("Collection.toArray requires a reference array")
        result = destination if len(destination) >= len(items) else JavaArrays.copy(destination,len(items))
        for index, item in enumerate(items):
            JavaArrays.set(result,index,item)
        if len(result)>len(items):
            JavaArrays.set(result,len(items),None)
        return result

    def addAll(self, other):
        changed = False
        for item in to_python_list(other):
            if self.add(item):
                changed = True
        return changed

    def removeAll(self, other):
        targets = to_python_list(other)
        changed = False
        for item in list(self._iter_raw()):
            for target in targets:
                if equals(item, target):
                    if self.remove(item):
                        changed = True
                    break
        return changed

    def clear(self):
        for item in list(self._iter_raw()):
            self.remove(item)

    def __contains__(self, value):
        return self.contains(value)

    def __iter__(self):
        return iter(self._iter_raw())

    def __repr__(self):
        return u"<{} size={}>".format(type(self).__name__, self.size())


# 说明：JavaList / JavaSet / JavaMap 的具体实现定义在 util.py 里。
# 本文件**不**为它们保留同名占位符 —— 留一个 `JavaList = None`
# 会让 isinstance 判断永远为假（曾经的坑），
# 所以统一改成鸭子类型判断（见 is_java_collection）
# 与构造器注入（见 bind_java_list）。

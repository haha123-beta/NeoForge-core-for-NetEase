# -*- coding: utf-8 -*-
# java_stdlib/lang.py
# Σ 层：java.lang 的 Python 复刻
#
# 引用统计（真实模组 184 个 .class 常量池）决定了实现优先级：
#   String 883、Object 748、Integer 72、Class 70、Runnable 37、Boolean 30、
#   Comparable 27、StringBuilder 25、Enum 19、Math 13、Float 11 …
#
# 原包名 java.lang.String 映射到 JavaString 文本对象，保留原实例方法名。
# StringOps 与模块级 String 静态工具保留供旧代码使用；不做内建类型方法注入。
# JavaString 使用 Python2 unicode / Python3 str 文本基类。
# 已实现的 UTF-16 索引入口包括 length/charAt/substring/toCharArray/hashCode。
# 其他方法、构造重载、locale/正则/默认字符集等仍有兼容缺口。

from __future__ import print_function
from __future__ import absolute_import

import math as _math
import struct as _struct
import re as _re
import threading as _threading
import time as _time

try:
    from java_stdlib._base import (
        JavaException,
        JavaThrowable,
        JavaError,
        RuntimeException,
        UnsupportedOperationException,
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
        to_char,
    )
except ImportError:
    from _base import (  # type: ignore
        JavaException,
        JavaThrowable,
        JavaError,
        RuntimeException,
        UnsupportedOperationException,
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
        to_char,
    )


# ============================================================
# 类型探测
# ============================================================

# Python 2 里文本有两种类型：str（字节）与 unicode；Python 3 只有 str。
try:
    _TEXT_TYPES = (str, unicode)          # noqa: F821  (Python 2)
except NameError:
    _TEXT_TYPES = (str,)                   # Python 3


def is_string(value):
    """是不是字符串（任意文本类型）。"""
    return isinstance(value, _TEXT_TYPES)


def is_number(value):
    """Java 把 bool 当独立类型，Python 的 bool 却是 int 的子类，故显式排除。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ============================================================
# Java 的 String.valueOf 语义
# ============================================================

def java_to_string(value):
    """
    对应 Java 的 String.valueOf(Object)，也是 StringOps 的统一入口。

    关键语义：**null 变成字面量 "null"**，而不是 Python 的报错或空串。
    Java 代码到处依赖这一点（字符串拼接 "+" 也走同样规则）。
    """
    if value is None:
        return u"null"
    if isinstance(value, bool):
        return u"true" if value else u"false"
    if isinstance(value, JavaThrowable):
        return value.toString()
    return u"{}".format(value)


# ============================================================
# StringOps：Java String 实例方法的函数式实现
# ============================================================
#
# 为什么是静态函数而不是方法：
#   见文件头的三条路对比 —— 注入在 Py3 上不可行，包装又会破坏原生字符串语义。
#   静态函数接受**任意值**，内部先 java_to_string 再算，
#   所以引擎给的原始字符串、字面量、包装类型都能直接传进来。

try:
    _STRING_BASE = unicode
    _CHAR_FROM_CODE = unichr
except NameError:
    _STRING_BASE = str
    _CHAR_FROM_CODE = chr
_STRING_DEFAULT = object()


def _utf16_units(value):
    result = []
    for character in java_to_string(value):
        code = ord(character)
        if code > 65535:
            code -= 65536
            result.extend((_CHAR_FROM_CODE(55296 + (code >> 10)), _CHAR_FROM_CODE(56320 + (code & 1023))))
        else:
            result.append(character)
    return u"".join(result)


def _utf16_text(units):
    result, index = [], 0
    while index < len(units):
        code = ord(units[index])
        if 55296 <= code <= 56319 and index + 1 < len(units) and 56320 <= ord(units[index + 1]) <= 57343:
            value = 65536 + ((code - 55296) << 10) + ord(units[index + 1]) - 56320
            try:
                result.append(_CHAR_FROM_CODE(value))
            except ValueError:
                result.extend((units[index], units[index + 1]))
            index += 2
        else:
            result.append(units[index])
            index += 1
    return u"".join(result)


class StringOps(object):
    """java.lang.String 实例方法的语义实现（全部为静态方法）。"""

    # ---------------- 长度与取值 ----------------

    @staticmethod
    def length(value):
        """Java String.length：返回 UTF-16 code unit 数。"""
        return len(_utf16_units(value))

    @staticmethod
    def isEmpty(value):
        return len(java_to_string(value)) == 0

    @staticmethod
    def charAt(value, index):
        """越界抛 StringIndexOutOfBoundsException（Java 语义）。"""
        text = _utf16_units(value)
        index = _to_java_int(index)
        if index < 0 or index >= len(text):
            raise StringIndexOutOfBoundsException(
                u"String index out of range: {}".format(index))
        return text[index]

    @staticmethod
    def toCharArray(value):
        return list(_utf16_units(value))

    # ---------------- 截取 ----------------

    @staticmethod
    def substring(value, begin, end=None):
        """
        Java 的 substring：**左闭右开**区间。

        substring(1, 3) 取下标 1、2 两个字符 —— 与 Python 切片一致，
        但很多人误以为是闭区间，所以保持 Java 语义并写清楚。
        """
        text = _utf16_units(value)
        begin = _to_java_int(begin)

        if end is None:
            if begin < 0 or begin > len(text):
                raise StringIndexOutOfBoundsException(
                    u"String index out of range: {}".format(begin))
            return _utf16_text(text[begin:])

        end = _to_java_int(end)
        if begin < 0 or end > len(text) or begin > end:
            raise StringIndexOutOfBoundsException(
                u"begin {}, end {}, length {}".format(begin, end, len(text)))
        return _utf16_text(text[begin:end])

    @staticmethod
    def subSequence(value, begin, end):
        return StringOps.substring(value, begin, end)

    # ---------------- 查找 ----------------

    @staticmethod
    def indexOf(value, target, from_index=0):
        """Java 的 indexOf：**未命中返回 -1**（不是抛异常，也不是 None）。"""
        if from_index is None:
            from_index = 0
        return java_to_string(value).find(
            java_to_string(target), _to_java_int(from_index))

    @staticmethod
    def lastIndexOf(value, target, from_index=None):
        text = java_to_string(value)
        target_text = java_to_string(target)
        if from_index is None:
            return text.rfind(target_text)
        return text.rfind(target_text, 0, _to_java_int(from_index) + 1)

    @staticmethod
    def contains(value, target):
        return java_to_string(target) in java_to_string(value)

    @staticmethod
    def startsWith(value, prefix, offset=0):
        return java_to_string(value).startswith(
            java_to_string(prefix), _to_java_int(offset))

    @staticmethod
    def endsWith(value, suffix):
        return java_to_string(value).endswith(java_to_string(suffix))

    @staticmethod
    def matches(value, pattern):
        return _re.match(pattern, java_to_string(value)) is not None

    # ---------------- 比较 ----------------

    @staticmethod
    def equals(value, other):
        """Java 的 String.equals 按内容比较；null 与任何值都不相等。"""
        if other is None or not is_string(other) and not isinstance(other,
                                                                   JavaString):
            return False
        return java_to_string(value) == java_to_string(other)

    @staticmethod
    def equalsIgnoreCase(value, other):
        if other is None:
            return False
        if not (is_string(other) or isinstance(other, JavaString)):
            return False
        return java_to_string(value).lower() == java_to_string(other).lower()

    @staticmethod
    def compareTo(value, other):
        """
        Java 的 compareTo：返回负/0/正，**不是布尔**。

        Python 的比较运算符给的是布尔，语义不同，所以必须单独实现。
        """
        left = java_to_string(value)
        right = java_to_string(other)
        if left < right:
            return -1
        if left > right:
            return 1
        return 0

    @staticmethod
    def compareToIgnoreCase(value, other):
        return StringOps.compareTo(java_to_string(value).lower(),
                                   java_to_string(other).lower())

    # ---------------- 变换 ----------------

    @staticmethod
    def toLowerCase(value):
        return java_to_string(value).lower()

    @staticmethod
    def toUpperCase(value):
        return java_to_string(value).upper()

    @staticmethod
    def trim(value):
        """
        Java 的 trim：只去**码位 <= U+0020** 的首尾字符。

        与 Python 的 strip() 不同（后者会去掉更多 Unicode 空白），
        所以按 Java 语义实现，避免行为差异。
        """
        text = java_to_string(value)
        start = 0
        end = len(text)
        while start < end and ord(text[start]) <= 0x20:
            start += 1
        while end > start and ord(text[end - 1]) <= 0x20:
            end -= 1
        return text[start:end]

    @staticmethod
    def replace(value, old, new):
        """Java 的 replace 是**字面量**替换（replaceAll 才用正则）。"""
        return java_to_string(value).replace(java_to_string(old),
                                            java_to_string(new))

    @staticmethod
    def replaceAll(value, pattern, new):
        """Java 的 replaceAll 用**正则**。"""
        return _re.sub(pattern, java_to_string(new), java_to_string(value))

    @staticmethod
    def replaceFirst(value, pattern, new):
        return _re.sub(pattern, java_to_string(new), java_to_string(value), count=1)

    @staticmethod
    def split(value, pattern, limit=0):
        """
        Java 的 split：参数是**正则**，且默认 limit=0 会**丢掉末尾空串**。

        Python 的 str.split 用字面量且不丢空串，语义不同，故单独实现。
        """
        text = java_to_string(value)
        limit = _to_java_int(limit) if limit is not None else 0

        if limit > 0:
            parts = _re.split(pattern, text, maxsplit=limit - 1)
        else:
            parts = _re.split(pattern, text)

        if limit == 0:
            while parts and parts[-1] == u"":
                parts.pop()
        return parts

    @staticmethod
    def concat(value, other):
        return java_to_string(value) + java_to_string(other)

    @staticmethod
    def intern(value):
        return java_to_string(value)

    @staticmethod
    def hashCode(value):
        return hash_code(java_to_string(value))

    @staticmethod
    def toString(value):
        return java_to_string(value)


# ============================================================
# JavaString：带 Java 方法的字符串类型
# ============================================================

class JavaString(_STRING_BASE):
    """
    java.lang.String 的可调用形态：文本基类的子类，带目前已实现的 Java 方法。

    什么时候用：
      翻译层需要**以方法形式**调用 Java API 时（例如原码写 s.length()），
      把值包成 JavaString 即可保留方法调用形式：
          JavaString(s).length()

    为什么默认不用：
      isinstance(JavaString("a"), str) 为真，但 **type 不是 str**，
      有些引擎接口可能对类型敏感；而且引擎返回的字符串是原生 str。
      所以核心内部一律用原生字符串 + StringOps 静态函数，
      只有需要方法形式的场合才显式构造 JavaString。
    """

    # ---------------- 长度与取值 ----------------

    def __new__(cls, value=_STRING_DEFAULT, *args):
        if args:
            raise NotImplementedError("String constructor overload requires explicit implementation")
        if value is _STRING_DEFAULT:
            value = u""
        if value is None:
            raise NullPointerException("String original is null")
        if not isinstance(value, _TEXT_TYPES):
            raise NotImplementedError("String byte/char/builder constructor overload is not integrated")
        if not isinstance(value, _STRING_BASE):
            value = value.decode("utf-8")
        return _STRING_BASE.__new__(cls, value)

    def length(self):
        return StringOps.length(self)

    def isEmpty(self):
        return StringOps.isEmpty(self)

    def charAt(self, index):
        return StringOps.charAt(self, index)

    def toCharArray(self):
        return StringOps.toCharArray(self)

    # ---------------- 截取 ----------------

    def substring(self, begin, end=None):
        return JavaString(StringOps.substring(self, begin, end))

    def subSequence(self, begin, end):
        return JavaString(StringOps.subSequence(self, begin, end))

    # ---------------- 查找 ----------------

    def indexOf(self, target, from_index=0):
        return StringOps.indexOf(self, target, from_index)

    def lastIndexOf(self, target, from_index=None):
        return StringOps.lastIndexOf(self, target, from_index)

    def contains(self, target):
        return StringOps.contains(self, target)

    def startsWith(self, prefix, offset=0):
        return StringOps.startsWith(self, prefix, offset)

    def endsWith(self, suffix):
        return StringOps.endsWith(self, suffix)

    def matches(self, pattern):
        return StringOps.matches(self, pattern)

    # ---------------- 比较 ----------------

    def equals(self, other):
        return is_string(other) and _utf16_units(self) == _utf16_units(other)

    def equalsIgnoreCase(self, other):
        return StringOps.equalsIgnoreCase(self, other)

    def compareTo(self, other):
        return StringOps.compareTo(self, other)

    def compareToIgnoreCase(self, other):
        return StringOps.compareToIgnoreCase(self, other)

    # ---------------- 变换 ----------------

    def toLowerCase(self):
        return JavaString(StringOps.toLowerCase(self))

    def toUpperCase(self):
        return JavaString(StringOps.toUpperCase(self))

    def trim(self):
        return JavaString(StringOps.trim(self))

    def replace(self, old, new):
        return JavaString(StringOps.replace(self, old, new))

    def replaceAll(self, pattern, new):
        return JavaString(StringOps.replaceAll(self, pattern, new))

    def replaceFirst(self, pattern, new):
        return JavaString(StringOps.replaceFirst(self, pattern, new))

    def split(self, pattern, limit=0):
        return [JavaString(part) for part in StringOps.split(self, pattern, limit)]

    def concat(self, other):
        return JavaString(StringOps.concat(self, other))

    def intern(self):
        return JavaString(StringOps.intern(self))

    def hashCode(self):
        value = 0
        for unit in _utf16_units(self):
            value = (31 * value + ord(unit)) & 4294967295
        return value - 4294967296 if value >= 2147483648 else value

    def toString(self):
        return u"{}".format(self)

    def __repr__(self):
        return u"JavaString({})".format(u"{}".format(self))


def to_java_string(value):
    """把任意值转成方法形式可用的字符串（JavaString）。"""
    return JavaString(java_to_string(value))


def injection_report():
    """
    保留此接口以免调用方断裂，但**如实返回 0**。

    原因：Python 3 不允许给 str 这类不可变内建类型加方法
    （实测 TypeError: cannot set 'length' attribute of immutable type 'str'），
    所以本层不采用「方法注入」方案，改用 StringOps 静态函数 + JavaString 子类。
    返回 0 是为了让「注入没生效」这件事一眼可见，而不是假装成功。
    """
    return [(u"str", 0), (u"JavaString", len([
        name for name in dir(JavaString) if not name.startswith(u"_")
    ]))]



# ============================================================
# String（静态工具）
# ============================================================

class String(object):
    """
    java.lang.String 的静态方法入口。

    为旧调用保留的静态工具；公共 Java 类型映射使用 JavaString。
    不向 Python 内建字符串注入方法。
    """

    @staticmethod
    def valueOf(value):
        return java_to_string(value)

    @staticmethod
    def copyValueOf(char_array):
        return u"".join([java_to_string(c) for c in char_array])

    @staticmethod
    def join(separator, *elements):
        """Java 8 的 String.join。"""
        if len(elements) == 1 and isinstance(elements[0], (list, tuple)):
            elements = elements[0]
        return java_to_string(separator).join(
            [java_to_string(item) for item in elements])

    @staticmethod
    def format(template, *args):
        """
        对应 Java 的 String.format。

        只支持最常用的 %s / %d / %f / %b / %%，
        不实现完整格式语法（如 %1$s 位置参数、宽度精度）。
        遇到不认识的占位符时**按原样保留**，而不是抛异常 ——
        宁可输出略有差异，也不要让模组在运行期崩掉。
        """
        result = []
        arg_index = 0
        index = 0
        length = len(template)

        while index < length:
            char = template[index]
            if char != u"%":
                result.append(char)
                index += 1
                continue

            if index + 1 >= length:
                result.append(char)
                break

            spec = template[index + 1]

            if spec == u"%":
                result.append(u"%")
                index += 2
                continue

            if spec in (u"b", u"B"):
                value = args[arg_index] if arg_index < len(args) else None
                arg_index += 1
                result.append(u"true" if value else u"false")
                index += 2
                continue

            if spec in (u"s", u"S"):
                value = args[arg_index] if arg_index < len(args) else None
                arg_index += 1
                result.append(java_to_string(value))
                index += 2
                continue

            if spec in (u"d", u"o", u"x", u"X"):
                value = args[arg_index] if arg_index < len(args) else 0
                arg_index += 1
                number = _to_java_int(value)
                if spec == u"d":
                    result.append(u"{}".format(number))
                elif spec == u"o":
                    result.append(u"{:o}".format(number))
                elif spec == u"x":
                    result.append(u"{:x}".format(number))
                else:
                    result.append(u"{:X}".format(number))
                index += 2
                continue

            if spec in (u"f", u"e", u"g"):
                value = args[arg_index] if arg_index < len(args) else 0.0
                arg_index += 1
                number = _to_java_float(value)
                if spec == u"f":
                    result.append(u"{:.6f}".format(number))
                elif spec == u"e":
                    result.append(u"{:e}".format(number))
                else:
                    result.append(u"{:g}".format(number))
                index += 2
                continue

            # 不认识的占位符：原样保留，不猜
            result.append(char)
            result.append(spec)
            index += 2

        return u"".join(result)

    @staticmethod
    def hashCode(value):
        return hash_code(java_to_string(value))

    @staticmethod
    def equals(left, right):
        return java_to_string(left) == java_to_string(right)


# ============================================================
# StringBuilder / StringBuffer
# ============================================================

class StringBuilder(object):
    """
    java.lang.StringBuilder（引用 25 次）。

    两个必须照 Java 来的点：
      1. append 返回 this，以支持 builder.append(a).append(b) 链式写法；
      2. append(null) 得到字符串 "null"。
    """

    def __init__(self, initial=None):
        self._parts = []
        if initial is not None:
            self._parts.append(java_to_string(initial))

    def append(self, value):
        """返回自身以支持链式调用。"""
        self._parts.append(java_to_string(value))
        return self

    def appendCodePoint(self, code_point):
        self._parts.append(to_char(_to_java_int(code_point)))
        return self

    def insert(self, offset, value):
        current = self.toString()
        text = java_to_string(value)
        offset = _to_java_int(offset)
        if offset < 0 or offset > len(current):
            raise StringIndexOutOfBoundsException(
                u"offset {}, length {}".format(offset, len(current)))
        self._parts = [current[:offset], text, current[offset:]]
        return self

    def deleteCharAt(self, index):
        current = self.toString()
        index = _to_java_int(index)
        if index < 0 or index >= len(current):
            raise StringIndexOutOfBoundsException(
                u"index {}, length {}".format(index, len(current)))
        self._parts = [current[:index] + current[index + 1:]]
        return self

    def delete(self, start, end):
        current = self.toString()
        start = _to_java_int(start)
        end = _to_java_int(end)
        if start < 0 or end > len(current) or start > end:
            raise StringIndexOutOfBoundsException(
                u"start {}, end {}, length {}".format(start, end, len(current)))
        self._parts = [current[:start] + current[end:]]
        return self

    def replace(self, start, end, value):
        current = self.toString()
        start = _to_java_int(start)
        end = _to_java_int(end)
        if start < 0 or end > len(current) or start > end:
            raise StringIndexOutOfBoundsException(
                u"start {}, end {}, length {}".format(start, end, len(current)))
        self._parts = [current[:start] + java_to_string(value) + current[end:]]
        return self

    def reverse(self):
        self._parts = [self.toString()[::-1]]
        return self

    def setLength(self, new_length):
        current = self.toString()
        new_length = _to_java_int(new_length)
        if new_length < 0:
            raise IllegalArgumentException(
                u"Negative length: {}".format(new_length))
        if new_length <= len(current):
            self._parts = [current[:new_length]]
        else:
            self._parts = [current + u"\u0000" * (new_length - len(current))]
        return self

    def length(self):
        return len(self.toString())

    def isEmpty(self):
        return self.length() == 0

    def charAt(self, index):
        return StringOps.charAt(self.toString(), index)

    def indexOf(self, target, from_index=0):
        return StringOps.indexOf(self.toString(), target, from_index)

    def substring(self, begin, end=None):
        return StringOps.substring(self.toString(), begin, end)

    def toString(self):
        return u"".join(self._parts)

    def clear(self):
        self._parts = []
        return self

    def __len__(self):
        return self.length()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<StringBuilder {}>".format(self.toString())

    def __eq__(self, other):
        if isinstance(other, StringBuilder):
            return self.toString() == other.toString()
        if is_string(other):
            return self.toString() == u"{}".format(other)
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash_code(self.toString())


# Java 的 StringBuffer 语义与 StringBuilder 相同（只是线程安全）。
# 模组代码不会依赖真正的并发语义，故复用同一实现。
StringBuffer = StringBuilder


# ============================================================
# 数值包装类型
# ============================================================

class Integer(object):
    """
    java.lang.Integer —— 数值包装类型（引用 72 次）。

    为什么不能直接用 int：
      Java 代码写的是 Integer.parseInt(s)、Integer.valueOf(i)、
      Integer.MAX_VALUE、Integer.compare(a, b)，Python 的 int 全都没有。
    """

    MAX_VALUE = 2147483647
    MIN_VALUE = -2147483648
    SIZE = 32
    BYTES = 4

    def __init__(self, value=0):
        self._value = _to_java_int(value)

    # ---------------- 静态方法 ----------------

    @staticmethod
    def parseInt(text, radix=10):
        """解析失败抛 NumberFormatException（不是 Python 的 ValueError）。"""
        try:
            return int(u"{}".format(text).strip(), _to_java_int(radix))
        except (ValueError, TypeError):
            raise NumberFormatException(u'For input string: "{}"'.format(text))

    @staticmethod
    def valueOf(text_or_value, radix=10):
        from java_stdlib._boxing import box
        if is_string(text_or_value):
            return box('int', Integer.parseInt(text_or_value, radix))
        return box('int', text_or_value)

    @staticmethod
    def compare(left, right):
        left = _to_java_int(_unwrap(left))
        right = _to_java_int(_unwrap(right))
        return -1 if left < right else (0 if left == right else 1)

    @staticmethod
    def compareUnsigned(left, right):
        return Integer.compare(_to_unsigned_int(left), _to_unsigned_int(right))

    @staticmethod
    def toBinaryString(value):
        return _to_base_string(_to_unsigned_int(value), 2)

    @staticmethod
    def toHexString(value):
        return _to_base_string(_to_unsigned_int(value), 16)

    @staticmethod
    def toOctalString(value):
        return _to_base_string(_to_unsigned_int(value), 8)

    @staticmethod
    def toStringRadix(value, radix=10):
        """
        按指定进制输出（对应 Java 的 Integer.toString(int, int)）。

        为什么不直接叫 toString：
          类里已经有一个同名的**实例方法** toString(self)，
          定义在后面的实例方法会覆盖先定义的静态方法，
          导致 Integer.toString(255, 16) 报「多给了一个参数」。
          这是实测踩到的坑，所以带进制的那个改用独立名字。
        """
        return _to_base_string(_to_java_int(value), _to_java_int(radix))

    @staticmethod
    def bitCount(value):
        return bin(_to_unsigned_int(value)).count(u"1")

    @staticmethod
    def max(left, right):
        return max(_to_java_int(left), _to_java_int(right))

    @staticmethod
    def min(left, right):
        return min(_to_java_int(left), _to_java_int(right))

    @staticmethod
    def sum(left, right):
        return _to_java_int(left) + _to_java_int(right)

    @staticmethod
    def hashCode(value):
        return _to_unsigned_int(value)

    # ---------------- 实例方法 ----------------

    def intValue(self):
        return self._value

    def longValue(self):
        return self._value

    def doubleValue(self):
        return float(self._value)

    def floatValue(self):
        return float(self._value)

    def shortValue(self):
        """Java 的窄化转换：按 16 位有符号回绕。"""
        value = self._value & 0xFFFF
        return value - 0x10000 if value >= 0x8000 else value

    def byteValue(self):
        value = self._value & 0xFF
        return value - 0x100 if value >= 0x80 else value

    def equals(self, other):
        if isinstance(other, Integer):
            return type(self) is type(other) and self._value == other._value
        if is_number(other):
            return self._value == int(other)
        return False

    def hashCode(self):
        value = _to_unsigned_int(self._value)
        return value if value < 2147483648 else value - 4294967296

    def compareTo(self, other):
        return Integer.compare(self._value, _unwrap(other))

    def toString(self):
        return u"{}".format(self._value)

    def __int__(self):
        return self._value

    def __index__(self):
        """让 Integer 能当列表下标与切片参数用。"""
        return self._value

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Integer {}>".format(self._value)

    # ---- 算术：让包装类型能直接参与计算（Java 的自动拆箱） ----

    def __add__(self, other):
        return self._value + _to_java_int(_unwrap(other))

    def __radd__(self, other):
        return _to_java_int(_unwrap(other)) + self._value

    def __sub__(self, other):
        return self._value - _to_java_int(_unwrap(other))

    def __rsub__(self, other):
        return _to_java_int(_unwrap(other)) - self._value

    def __mul__(self, other):
        return self._value * _to_java_int(_unwrap(other))

    def __rmul__(self, other):
        return _to_java_int(_unwrap(other)) * self._value

    def __lt__(self, other):
        return self._value < _to_java_int(_unwrap(other))

    def __le__(self, other):
        return self._value <= _to_java_int(_unwrap(other))

    def __gt__(self, other):
        return self._value > _to_java_int(_unwrap(other))

    def __ge__(self, other):
        return self._value >= _to_java_int(_unwrap(other))


class Long(object):
    """java.lang.Long（引用 4 次）。"""

    MAX_VALUE = 9223372036854775807
    MIN_VALUE = -9223372036854775808
    SIZE = 64
    BYTES = 8

    def __init__(self, value=0):
        self._value = _to_java_int(value)

    @staticmethod
    def parseLong(text, radix=10):
        return Integer.parseInt(text, radix)

    @staticmethod
    def valueOf(text_or_value, radix=10):
        from java_stdlib._boxing import box
        if is_string(text_or_value):
            return box('long', Long.parseLong(text_or_value, radix))
        return box('long', text_or_value)

    @staticmethod
    def compare(left, right):
        return Integer.compare(_unwrap(left), _unwrap(right))

    @staticmethod
    def toStringValue(value):
        """
        对应 java.lang.Long.toString(long)。

        命名约定（全层统一）：Java 类同时有静态 toString(x) 与实例 toString() 时，
        Python 里实例方法会覆盖静态方法，所以静态入口改叫 xxxValue，
        实例方法委托给它，两边共用一份逻辑。详见 Boolean 处的说明。
        """
        if isinstance(value, Long):
            return u"{}".format(value.longValue())
        return u"{}".format(_to_java_int(value))

    @staticmethod
    def toHexString(value):
        return _to_base_string(_to_unsigned_int(value), 16)

    def longValue(self):
        return self._value

    def intValue(self):
        return self._value

    def doubleValue(self):
        return float(self._value)

    def equals(self, other):
        if isinstance(other, Long):
            return self._value == other._value
        if is_number(other):
            return self._value == int(other)
        return False

    def hashCode(self):
        value = self._value & 18446744073709551615
        value = (value ^ (value >> 32)) & 4294967295
        return value if value < 2147483648 else value - 4294967296

    def compareTo(self, other):
        return Integer.compare(self._value, _unwrap(other))

    def toString(self):
        return Long.toStringValue(self._value)

    def __int__(self):
        return self._value

    def __index__(self):
        return self._value

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Long {}>".format(self._value)


class _FloatingPointBase(object):
    """Float / Double 的公共部分。"""

    _type_name = u"Float"

    def __init__(self, value=0.0):
        self._value = _to_java_float(value)

    def floatValue(self):
        return self._value

    def doubleValue(self):
        return self._value

    def intValue(self):
        """Java 的 (int) 转换是**向零截断**，不是四舍五入。"""
        if self._value != self._value or self._value in (float(u"inf"),
                                                         float(u"-inf")):
            return 0
        return int(self._value)

    def longValue(self):
        return self.intValue()

    def isNaN(self):
        return self._value != self._value

    def isInfinite(self):
        return self._value in (float(u"inf"), float(u"-inf"))

    def equals(self, other):
        if isinstance(other, _FloatingPointBase):
            if type(self) is not type(other):
                return False
            if _math.isnan(self._value) and _math.isnan(other._value):
                return True
            if self._value == other._value == 0.0:
                return _math.copysign(1.0,self._value) == _math.copysign(1.0,other._value)
            return self._value == other._value
        if is_number(other):
            return self._value == float(other)
        return False

    def hashCode(self):
        if isinstance(self, Float):
            bits = 2143289344 if _math.isnan(self._value) else _struct.unpack('>I',_struct.pack('>f',self._value))[0]
        else:
            bits = 9221120237041090560 if _math.isnan(self._value) else _struct.unpack('>Q',_struct.pack('>d',self._value))[0]
            bits = (bits ^ (bits >> 32)) & 4294967295
        return bits if bits < 2147483648 else bits - 4294967296

    def compareTo(self, other):
        return _compare_float(self._value, _to_java_float(_unwrap(other)))

    def toString(self):
        return _float_to_string(self._value)

    def __float__(self):
        return self._value

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{} {}>".format(self._type_name, self._value)


class Float(_FloatingPointBase):
    """java.lang.Float（引用 11 次）。"""

    MAX_VALUE = 3.4028234663852886e+38
    MIN_VALUE = 1.401298464324817e-45
    NaN = float(u"nan")
    POSITIVE_INFINITY = float(u"inf")
    NEGATIVE_INFINITY = float(u"-inf")
    SIZE = 32

    _type_name = u"Float"

    def __init__(self, value=0.0):
        from java_stdlib.function import Functional
        self._value = Functional.float32(_to_java_float(value))

    @staticmethod
    def parseFloat(text):
        try:
            return float(u"{}".format(text).strip())
        except (ValueError, TypeError):
            raise NumberFormatException(u'For input string: "{}"'.format(text))

    @staticmethod
    def valueOf(text_or_value):
        if is_string(text_or_value):
            return Float(Float.parseFloat(text_or_value))
        return Float(text_or_value)

    @staticmethod
    def compare(left, right):
        return _compare_float(_to_java_float(left), _to_java_float(right))

    @staticmethod
    def isNaN(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number != number

    @staticmethod
    def isInfinite(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number in (float(u"inf"), float(u"-inf"))


class Double(_FloatingPointBase):
    """java.lang.Double（引用 5 次）。"""

    MAX_VALUE = 1.7976931348623157e+308
    MIN_VALUE = 4.9e-324
    NaN = float(u"nan")
    POSITIVE_INFINITY = float(u"inf")
    NEGATIVE_INFINITY = float(u"-inf")
    SIZE = 64

    _type_name = u"Double"

    @staticmethod
    def toStringValue(value):
        """静态入口（对应 java.lang.Double.toString(double)）。

        约定同 Boolean：实例方法 toString 会覆盖同名静态方法，
        所以静态入口用不冲突的名字，并自行处理「已经是本类实例」的情况。
        """
        if isinstance(value, _FloatingPointBase):
            return _float_to_string(value.doubleValue())
        return _float_to_string(_to_java_float(value))

    @staticmethod
    def parseDouble(text):
        try:
            return float(u"{}".format(text).strip())
        except (ValueError, TypeError):
            raise NumberFormatException(u'For input string: "{}"'.format(text))

    @staticmethod
    def valueOf(text_or_value):
        if is_string(text_or_value):
            return Double(Double.parseDouble(text_or_value))
        return Double(text_or_value)

    @staticmethod
    def compare(left, right):
        return _compare_float(_to_java_float(left), _to_java_float(right))

    @staticmethod
    def isNaN(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number != number

    @staticmethod
    def isInfinite(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number in (float(u"inf"), float(u"-inf"))


class Boolean(object):
    """java.lang.Boolean（引用 30 次）。"""

    TRUE = True
    FALSE = False

    def __init__(self, value=False):
        self._value = _to_java_bool(value)

    @staticmethod
    def parseBoolean(text):
        """Java 语义：**只有**忽略大小写等于 "true" 才是真，其余一律假。"""
        if text is None:
            return False
        return java_to_string(text).lower() == u"true"

    @staticmethod
    def valueOf(text_or_value):
        if is_string(text_or_value):
            text_or_value = Boolean.parseBoolean(text_or_value)
        from java_stdlib._boxing import box
        return box('boolean', text_or_value)

    @staticmethod
    def compare(left, right):
        left = 1 if _to_java_bool(left) else 0
        right = 1 if _to_java_bool(right) else 0
        return -1 if left < right else (0 if left == right else 1)

    @staticmethod
    def logicalAnd(left, right):
        return _to_java_bool(left) and _to_java_bool(right)

    @staticmethod
    def logicalOr(left, right):
        return _to_java_bool(left) or _to_java_bool(right)

    @staticmethod
    def logicalXor(left, right):
        return _to_java_bool(left) != _to_java_bool(right)

    @staticmethod
    def toStringValue(value):
        """
        对应 java.lang.Boolean.toString(boolean)。

        为什么不叫 toString：
          Python 没有重载，类里同名的**实例方法会覆盖静态方法**
          （实测踩过：Boolean.toString(True) 走进了实例方法，
          报「bool 对象没有 _value」）。所以静态入口用不冲突的名字，
          实例方法再委托过来，两边共用一份逻辑。
        """
        if isinstance(value, Boolean):
            return u"true" if value.booleanValue() else u"false"
        return u"true" if _to_java_bool(value) else u"false"

    @staticmethod
    def hashCodeValue(value):
        """同上：与实例方法同名会冲突，故用独立名字。"""
        if isinstance(value, Boolean):
            return 1231 if value.booleanValue() else 1237
        return 1231 if _to_java_bool(value) else 1237

    def booleanValue(self):
        return self._value

    def equals(self, other):
        if isinstance(other, Boolean):
            return self._value == other._value
        if isinstance(other, bool):
            return self._value == other
        return False

    def hashCode(self):
        return Boolean.hashCodeValue(self._value)

    def compareTo(self, other):
        return Boolean.compare(self._value, _unwrap(other))

    def toString(self):
        return Boolean.toStringValue(self._value)

    def __bool__(self):
        return self._value

    __nonzero__ = __bool__

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Boolean {}>".format(self.toString())


class Character(object):
    """java.lang.Character（引用 3 次）。"""

    MAX_VALUE = 0xFFFF
    MIN_VALUE = 0x0000

    def __init__(self, value=u"\u0000"):
        text = java_to_string(value)
        self._value = text[0] if text else u"\u0000"

    @staticmethod
    def isDigit(char):
        text = java_to_string(char)
        return len(text) == 1 and text.isdigit()

    @staticmethod
    def isLetter(char):
        text = java_to_string(char)
        return len(text) == 1 and text.isalpha()

    @staticmethod
    def isLetterOrDigit(char):
        text = java_to_string(char)
        return len(text) == 1 and text.isalnum()

    @staticmethod
    def isWhitespace(char):
        text = java_to_string(char)
        return len(text) == 1 and text.isspace()

    @staticmethod
    def isUpperCase(char):
        text = java_to_string(char)
        return len(text) == 1 and text.isupper()

    @staticmethod
    def isLowerCase(char):
        text = java_to_string(char)
        return len(text) == 1 and text.islower()

    @staticmethod
    def toUpperCase(char):
        return java_to_string(char).upper()

    @staticmethod
    def toLowerCase(char):
        return java_to_string(char).lower()

    @staticmethod
    def getNumericValue(char):
        """Java 语义：不是数字字符时返回 -1（不抛异常）。"""
        text = java_to_string(char)
        if len(text) == 1 and text.isdigit():
            return int(text)
        return -1

    @staticmethod
    def digit(char, radix=10):
        try:
            return int(java_to_string(char), _to_java_int(radix))
        except (ValueError, TypeError):
            return -1

    @staticmethod
    def toStringValue(value):
        """静态入口；同名实例方法会覆盖静态方法，故用独立名字。"""
        if isinstance(value, Character):
            return value.charValue()
        return java_to_string(value)

    @staticmethod
    def valueOf(char):
        from java_stdlib._boxing import box
        return box('char', char)

    @staticmethod
    def compare(left, right):
        left = ord(java_to_string(left)[0])
        right = ord(java_to_string(right)[0])
        return -1 if left < right else (0 if left == right else 1)

    def charValue(self):
        return self._value

    def equals(self, other):
        if isinstance(other, Character):
            return self._value == other._value
        if is_string(other):
            return self._value == u"{}".format(other)
        return False

    def hashCode(self):
        return ord(self._value)

    def toString(self):
        return self._value

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Character {}>".format(self._value)


class Byte(Integer):
    """java.lang.Byte（引用 3 次）：数值语义同 Integer，取值范围不同。"""

    MAX_VALUE = 127
    MIN_VALUE = -128
    SIZE = 8
    BYTES = 1

    @staticmethod
    def valueOf(value, radix=10):
        from java_stdlib._boxing import box
        return box('byte', Integer.parseInt(value, radix) if is_string(value) else value)

    @staticmethod
    def parseByte(text, radix=10):
        return Integer.parseInt(text, radix)


class Short(Integer):
    """java.lang.Short（引用 3 次）。"""

    MAX_VALUE = 32767
    MIN_VALUE = -32768
    SIZE = 16
    BYTES = 2

    @staticmethod
    def valueOf(value, radix=10):
        from java_stdlib._boxing import box
        return box('short', Integer.parseInt(value, radix) if is_string(value) else value)

    @staticmethod
    def parseShort(text, radix=10):
        return Integer.parseInt(text, radix)


class Number(object):
    """
    java.lang.Number —— 数值包装类型的抽象基类。

    模组里常用来做统一接收（例如方法参数声明为 Number）。
    方法签名与 Java 一致，子类实现 doubleValue 即可。
    """

    def intValue(self):
        return int(self.doubleValue())

    def longValue(self):
        return int(self.doubleValue())

    def floatValue(self):
        return float(self.doubleValue())

    def doubleValue(self):
        raise NotImplementedError()


# ============================================================
# Math
# ============================================================

class Math(object):
    """
    java.lang.Math（引用 13 次）。

    必须按 Java 语义实现的几个（与 Python 内建行为不同）：
      - Math.round / Math.floor / Math.ceil 返回**整数**，不是浮点
      - Math.round 是四舍五入（Python 的 round 是银行家舍入）
      - Math.floorDiv / floorMod 是向下取整，除零抛 ArithmeticException
    """

    PI = _math.pi
    E = _math.e

    @staticmethod
    def abs(value):
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, Integer):
            return abs(value.intValue())
        return abs(value)

    @staticmethod
    def max(left, right):
        return left if left >= right else right

    @staticmethod
    def min(left, right):
        return left if left <= right else right

    @staticmethod
    def round(value):
        """
        Java 的 Math.round：四舍五入到最近整数（.5 向上）。

        与 Python 不同：Python 用银行家舍入，round(2.5) == 2；
        Java 的 Math.round(2.5) == 3。模组里算坐标时常踩这个坑。
        """
        number = _to_java_float(value)
        if number != number:
            return 0
        if number in (float(u"inf"), float(u"-inf")):
            return 0
        return int(_math.floor(number + 0.5))

    @staticmethod
    def floor(value):
        return int(_math.floor(_to_java_float(value)))

    @staticmethod
    def ceil(value):
        return int(_math.ceil(_to_java_float(value)))

    @staticmethod
    def floorDiv(left, right):
        """Java 的 floorDiv：结果向下取整（-7 // 2 == -4，与 C 的截断不同）。"""
        left = _to_java_int(_unwrap(left))
        right = _to_java_int(_unwrap(right))
        if right == 0:
            raise ArithmeticException(u"/ by zero")
        return left // right

    @staticmethod
    def floorMod(left, right):
        left = _to_java_int(_unwrap(left))
        right = _to_java_int(_unwrap(right))
        if right == 0:
            raise ArithmeticException(u"/ by zero")
        return left % right

    @staticmethod
    def sqrt(value):
        return _math.sqrt(_to_java_float(value))

    @staticmethod
    def cbrt(value):
        number = _to_java_float(value)
        if number < 0:
            return -((-number) ** (1.0 / 3.0))
        return number ** (1.0 / 3.0)

    @staticmethod
    def pow(base, exponent):
        return _math.pow(_to_java_float(base), _to_java_float(exponent))

    @staticmethod
    def sin(value):
        return _math.sin(_to_java_float(value))

    @staticmethod
    def cos(value):
        return _math.cos(_to_java_float(value))

    @staticmethod
    def tan(value):
        return _math.tan(_to_java_float(value))

    @staticmethod
    def asin(value):
        return _math.asin(_to_java_float(value))

    @staticmethod
    def acos(value):
        return _math.acos(_to_java_float(value))

    @staticmethod
    def atan(value):
        return _math.atan(_to_java_float(value))

    @staticmethod
    def atan2(y, x):
        return _math.atan2(_to_java_float(y), _to_java_float(x))

    @staticmethod
    def log(value):
        return _math.log(_to_java_float(value))

    @staticmethod
    def log10(value):
        return _math.log10(_to_java_float(value))

    @staticmethod
    def exp(value):
        return _math.exp(_to_java_float(value))

    @staticmethod
    def toRadians(degrees):
        return _to_java_float(degrees) * _math.pi / 180.0

    @staticmethod
    def toDegrees(radians):
        return _to_java_float(radians) * 180.0 / _math.pi

    @staticmethod
    def signum(value):
        number = _to_java_float(value)
        if number > 0:
            return 1.0
        if number < 0:
            return -1.0
        return 0.0

    @staticmethod
    def hypot(x, y):
        return _math.hypot(_to_java_float(x), _to_java_float(y))

    @staticmethod
    def random():
        import random as _py_random
        return _py_random.random()


# ============================================================
# 其它 java.lang 类型
# ============================================================

class ThreadLocal(object):
    """
    java.lang.ThreadLocal（引用 6 次）。

    按线程 id 分桶实现，语义与 Java 一致：不同线程看到各自的副本。
    单线程场景下等价于普通变量。
    """

    def __init__(self):
        self._values = {}
        self._lock = _threading.RLock()

    def _key(self):
        return _threading.current_thread().ident

    def get(self):
        with self._lock:
            value = self._values.get(self._key())
        if value is None:
            return self.initialValue()
        return value

    def set(self, value):
        with self._lock:
            self._values[self._key()] = value
        return None

    def remove(self):
        with self._lock:
            self._values.pop(self._key(), None)
        return None

    def initialValue(self):
        """子类可覆盖，用于提供初值（Java 的 initialValue）。"""
        return None

    def getOrCreate(self, factory):
        """Python 侧便利方法：取不到就用工厂造一个并存入。"""
        with self._lock:
            key = self._key()
            if self._values.get(key) is None:
                self._values[key] = factory()
            return self._values[key]


class Runnable(object):
    """
    java.lang.Runnable（引用 37 次）。

    Python 里任何可调用对象就能当 Runnable 用，所以不强制继承；
    这个类只是给直译过来的代码一个显式落点。
    """

    def __init__(self, func=None):
        self._func = func

    def run(self):
        if self._func is None:
            raise IllegalStateException(u"Runnable 没有绑定函数")
        return self._func()

    def __call__(self):
        return self.run()


class Comparable(object):
    """
    java.lang.Comparable（引用 27 次）。

    显式接口标记；实际比较靠 compareTo（返回负/0/正，不是布尔）。
    """

    def compareTo(self, other):
        raise NotImplementedError()


class Enum(object):
    """
    java.lang.Enum（引用 19 次）。

    Java 的枚举是**单例常量对象**，不是整数。
    模组代码常写 MyEnum.VALUE.name() / .ordinal() / MyEnum.values()。
    这里提供基类，具体枚举由翻译层按需生成子类并填 _values / _name / _ordinal。
    """

    _name = u""
    _ordinal = 0
    _values = ()

    def name(self):
        if not isinstance(self._name, JavaString):self._name = JavaString(self._name)
        return self._name

    def ordinal(self):
        return self._ordinal

    def toString(self):
        return self.name()

    @classmethod
    def values(cls):
        return list(cls._values)

    @classmethod
    def valueOf(cls, name):
        if name is None:raise NullPointerException()
        target = java_to_string(name)
        for item in cls._values:
            if item._name == target:
                return item
        raise IllegalArgumentException(u"No enum constant {}.".format(target))

    def getDeclaringClass(self):
        cls = type(self)
        return cls if cls.__bases__[0] is Enum else cls.__bases__[0]

    def compareTo(self, other):
        if other is None:raise NullPointerException()
        if not isinstance(other, Enum) or self.getDeclaringClass() is not other.getDeclaringClass():
            raise ClassCastException("Cannot compare different enum types")
        return self._ordinal - other._ordinal

    def equals(self, other):
        """枚举按**身份**比较（Java 语义），不是按值。"""
        return self is other

    def hashCode(self):
        return System.identityHashCode(self)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        value = self.toString()
        return value if isinstance(value, str) else value.encode("utf-8")

    def __repr__(self):
        return u"<{} {}>".format(type(self).__name__, self._name)


class Object(object):
    """
    java.lang.Object（引用 748 次，最高频）。

    Java 里所有类的根，提供 equals / hashCode / toString / getClass。
    这里作为**显式**基类提供；Python 的 object 是隐式根，
    所以不继承它也能工作，翻译层可按需选择。
    """

    def equals(self, other):
        return self is other

    def hashCode(self):
        return System.identityHashCode(self)

    def toString(self):
        return u"{}@{}".format(type(self).__name__, hex(id(self)))

    def getClass(self):
        return type(self)

    def clone(self):
        raise CloneNotSupportedException(u"clone 未实现")

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()


class System(object):
    """
    java.lang.System —— 只做与游戏环境无关的部分。

    currentTimeMillis / nanoTime / arraycopy / identityHashCode 都是纯逻辑，
    可以安全实现。

    **刻意不实现** System.out / System.err / System.exit：
      - 输出应走引擎日志（mod_log），不是标准输出；
      - 在游戏里调用 exit 是灾难。
    """

    @staticmethod
    def currentTimeMillis():
        return int(_time.time() * 1000)

    @staticmethod
    def nanoTime():
        return int(_time.time() * 1000000000)

    @staticmethod
    def identityHashCode(value):
        if value is None:return 0
        return int((id(value) + 2147483648) % 4294967296 - 2147483648)

    @staticmethod
    def arraycopy(source, source_pos, dest, dest_pos, length):
        """Java 的 System.arraycopy：原地复制；先取快照，允许区间重叠。"""
        from java_stdlib.java_arrays import JavaArray, JavaArrays
        if isinstance(source,JavaArray) or isinstance(dest,JavaArray):
            return JavaArrays.arraycopy(source,source_pos,dest,dest_pos,length)
        source_pos = _to_java_int(source_pos)
        dest_pos = _to_java_int(dest_pos)
        length = _to_java_int(length)
        chunk = list(source[source_pos:source_pos + length])

        if isinstance(dest, list):
            for offset in range(length):
                if dest_pos + offset < len(dest):
                    dest[dest_pos + offset] = chunk[offset]
                else:
                    dest.append(chunk[offset])
            return None

        # 目标是 JavaList 之类：用 set 逐项写
        for offset in range(length):
            dest.set(dest_pos + offset, chunk[offset])
        return None

    @staticmethod
    def lineSeparator():
        return u"\n"

    @staticmethod
    def getProperty(name, default=None):
        """Java 系统属性在游戏里没有意义，一律返回默认值。"""
        return default

    @staticmethod
    def getenv(name, default=None):
        return default


# ============================================================
# 异常
# ============================================================

class NumberFormatException(IllegalArgumentException):
    """对应 java.lang.NumberFormatException。"""


class ArithmeticException(RuntimeException):
    """对应 java.lang.ArithmeticException（除零）。"""


class NullPointerException(RuntimeException):
    """对应 java.lang.NullPointerException。"""


class CloneNotSupportedException(JavaException):
    """对应 java.lang.CloneNotSupportedException。"""


class IndexOutOfBoundsException(RuntimeException):
    """Corresponds to java.lang.IndexOutOfBoundsException."""


class ArrayIndexOutOfBoundsException(IndexOutOfBoundsException):
    """Corresponds to java.lang.ArrayIndexOutOfBoundsException."""


class StringIndexOutOfBoundsException(IndexOutOfBoundsException):
    """Corresponds to java.lang.StringIndexOutOfBoundsException."""


class AssertionError(JavaError):
    """对应 java.lang.AssertionError。"""


class ClassCastException(RuntimeException):
    """对应 java.lang.ClassCastException。"""


# ============================================================
# 内部辅助
# ============================================================

def _to_java_int(value):
    """
    转成 Java 的 int 值。

    注意：这里保留 Python 的大整数语义，不做 32 位回绕 ——
    回绕只在显式的窄化方法与位运算里做（shortValue / toHexString 等）。
    """
    if value is None:
        raise NumberFormatException(u"cannot convert null to int")
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, Integer):
        return value.intValue()
    if isinstance(value, _FloatingPointBase):
        return value.intValue()
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(u"{}".format(value))
    except (ValueError, TypeError):
        raise NumberFormatException(u'For input string: "{}"'.format(value))


def _to_unsigned_int(value):
    """按 32 位无符号语义取值（Python 的位运算不会自动回绕，这里显式做）。"""
    return _to_java_int(_unwrap(value)) & 0xFFFFFFFF


def _to_java_float(value):
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    # 包装类型的判断必须放在 float() 之前：
    # 否则 float(包装实例) 会去找实例方法 toString 并报错。
    if isinstance(value, _FloatingPointBase):
        return value.doubleValue()
    if isinstance(value, Integer):
        return float(value.intValue())
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _to_java_bool(value):
    """Java 的布尔转换：字符串不做隐式解析（parseBoolean 才解析）。"""
    if value is None:
        return False
    if isinstance(value, Boolean):
        return value.booleanValue()
    if isinstance(value, bool):
        return value
    return bool(value)


def _unwrap(value):
    """把包装类型拆成 Python 原生值。"""
    if isinstance(value, Integer):
        return value.intValue()
    if isinstance(value, _FloatingPointBase):
        return value.doubleValue()
    if isinstance(value, Boolean):
        return value.booleanValue()
    return value


def _compare_float(left, right):
    """Java 的 Float.compare / Double.compare：NaN 视为最大。"""
    left_nan = left != left
    right_nan = right != right
    if left_nan and right_nan:
        return 0
    if left_nan:
        return 1
    if right_nan:
        return -1
    return -1 if left < right else (0 if left == right else 1)


def _float_to_string(value):
    """Java 浮点转字符串的形态：整数值显示为 x.0。"""
    if value != value:
        return u"NaN"
    if value == float(u"inf"):
        return u"Infinity"
    if value == float(u"-inf"):
        return u"-Infinity"
    if value == int(value) and abs(value) < 1e16:
        return u"{:.1f}".format(value)
    return u"{}".format(value)


def _to_base_string(value, radix):
    """按进制输出；负数单独加负号（Python 的格式化不认负数加进制）。"""
    radix = _to_java_int(radix)
    if radix < 2 or radix > 36:
        raise IllegalArgumentException(
            u"radix {} out of range: 2..36".format(radix))
    if value < 0:
        return u"-" + _to_base_string(-value, radix)

    digits = u"0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return u"0"
    out = []
    while value > 0:
        out.append(digits[value % radix])
        value //= radix
    out.reverse()
    return u"".join(out)


# ============================================================
# 名称映射表：供翻译层 / 未映射 api 兜底层查询
# ============================================================

def _string_static_adapter(function):
    def call(*args, **kwargs):
        return JavaString(function(*args, **kwargs))
    return staticmethod(call)


for _string_method, _string_descriptor in list(String.__dict__.items()):
    if isinstance(_string_descriptor, staticmethod) and _string_method not in JavaString.__dict__:
        setattr(JavaString, _string_method, _string_static_adapter(getattr(String, _string_method)))


JAVA_MAP = {
    # 字符串
    "java.lang.String": JavaString,
    "java.lang.CharSequence": JavaString,
    "java.lang.StringBuilder": StringBuilder,
    "java.lang.StringBuffer": StringBuffer,

    # 包装类型
    "java.lang.Integer": Integer,
    "java.lang.Long": Long,
    "java.lang.Float": Float,
    "java.lang.Double": Double,
    "java.lang.Boolean": Boolean,
    "java.lang.Byte": Byte,
    "java.lang.Short": Short,
    "java.lang.Character": Character,
    "java.lang.Number": Number,

    # 工具与基础
    "java.lang.Math": Math,
    "java.lang.Object": Object,
    "java.lang.System": System,
    "java.lang.ThreadLocal": ThreadLocal,
    "java.lang.Runnable": Runnable,
    "java.lang.Comparable": Comparable,
    "java.lang.Enum": Enum,

    # 异常
    "java.lang.Exception": JavaException,
    "java.lang.RuntimeException": RuntimeException,
    "java.lang.Throwable": JavaThrowable,
    "java.lang.Error": JavaError,
    "java.lang.IllegalArgumentException": IllegalArgumentException,
    "java.lang.IllegalStateException": IllegalStateException,
    "java.lang.NumberFormatException": NumberFormatException,
    "java.lang.ArithmeticException": ArithmeticException,
    "java.lang.NullPointerException": NullPointerException,
    "java.lang.IndexOutOfBoundsException": IndexOutOfBoundsException,
    "java.lang.ArrayIndexOutOfBoundsException": ArrayIndexOutOfBoundsException,
    "java.lang.StringIndexOutOfBoundsException": StringIndexOutOfBoundsException,
    "java.lang.UnsupportedOperationException": UnsupportedOperationException,
    "java.lang.AssertionError": AssertionError,
    "java.lang.CloneNotSupportedException": CloneNotSupportedException,
    "java.lang.ClassCastException": ClassCastException,
}


__all__ = [
    "String", "StringOps", "JavaString", "StringBuilder", "StringBuffer",
    "Integer", "Long", "Float", "Double", "Boolean", "Byte", "Short",
    "Character", "Number", "Math", "Object", "System", "ThreadLocal",
    "Runnable", "Comparable", "Enum",
    "RuntimeException", "NumberFormatException", "ArithmeticException",
    "NullPointerException", "CloneNotSupportedException",
    "ArrayIndexOutOfBoundsException", "StringIndexOutOfBoundsException",
    "IndexOutOfBoundsException", "UnsupportedOperationException",
    "AssertionError", "ClassCastException",
    "java_to_string", "to_java_string", "is_string", "is_number",
    "injection_report", "JAVA_MAP",
]

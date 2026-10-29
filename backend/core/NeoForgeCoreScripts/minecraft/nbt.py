# -*- coding: utf-8 -*-
# minecraft/nbt.py
# θ 层：NBT 数据标签
#
# 真实用法（逐字来自反编译源码）：
#
#   // 网络包里带一段 NBT
#   public PreventDropPacket(int current, CompoundTag tag) { this.tag = tag; }
#   public CompoundTag tag() { return this.tag; }
#   ... er.setTag(stack, (CompoundTag) payload.tag);
#
#   // 方块实体存档（配合 ContainerHelper）
#   protected void loadAdditional(CompoundTag tag, HolderLookup.Provider registries)
#   protected void saveAdditional(CompoundTag tag, HolderLookup.Provider registries)
#
# NBT 是 Minecraft 的数据格式：一棵「带类型的树」。
# 一个 CompoundTag 就是一张 {名字: 带类型的值} 表，值可以是数字、字符串、
# 列表，也可以是另一个 CompoundTag（所以能嵌套）。
#
# **必须保留类型**：NBT 里 1（byte）与 1（int）是不同的东西。
# 用普通 Python 字典的话，写进去 1 再读出来就分不清原来是哪种 ——
# 而真实代码大量按具体类型取值（getInt / getByte / getString），
# 类型错了要么取不到，要么静默转成别的值。
#
# 所以这里：**存原始 Python 值 + 记住它的 NBT 类型**。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore


# ============================================================
# 标签类型
# ============================================================

class TagType(object):
    """
    对应 NBT 的标签类型（Tag.Types）。

    用字符串常量而不是数字 —— 打印出来直接能看懂，
    而且自测里断言也好写。
    """

    BYTE = u"byte"
    SHORT = u"short"
    INT = u"int"
    LONG = u"long"
    FLOAT = u"float"
    DOUBLE = u"double"
    STRING = u"string"
    LIST = u"list"
    COMPOUND = u"compound"
    BYTE_ARRAY = u"byte_array"
    INT_ARRAY = u"int_array"
    LONG_ARRAY = u"long_array"
    END = u"end"

    @staticmethod
    def of(value):
        """按 Python 值推断标签类型。"""
        if isinstance(value, TagValue):
            return value.tag_type
        if isinstance(value, bool):
            # NBT 里没有布尔，布尔就是 byte 0/1
            return TagType.BYTE
        if isinstance(value, int):
            return TagType.INT
        if isinstance(value, float):
            return TagType.DOUBLE
        if isinstance(value, CompoundTag):
            return TagType.COMPOUND
        if isinstance(value, (list, tuple)):
            return TagType.LIST
        return TagType.STRING


# ============================================================
# 带类型的值
# ============================================================

class TagValue(object):
    """
    一个带 NBT 类型的值。

    为什么不直接存 Python 值：见文件头的说明 ——
    NBT 的 byte/short/int/long 都是整数，光看 Python 值分不出来。
    记下类型才能让 `getInt` / `getByte` 各取各的。
    """

    def __init__(self, value, tag_type=None):
        self.value = value
        self.tag_type = tag_type if tag_type is not None else TagType.of(value)

    def __int__(self):
        return self.asInt()

    def __float__(self):
        return self.asFloat()

    def asInt(self):
        """按整数读（byte/short/int/long 都能读）。"""
        try:
            return int(self.value)
        except (TypeError, ValueError):
            raise IllegalArgumentException(
                u"标签类型 {} 的值 {!r} 不是整数".format(self.tag_type,
                                                        self.value))

    def asFloat(self):
        """按浮点读。"""
        try:
            return float(self.value)
        except (TypeError, ValueError):
            raise IllegalArgumentException(
                u"标签类型 {} 的值 {!r} 不是数字".format(self.tag_type,
                                                        self.value))

    def asString(self):
        """按字符串读。compound / list 也能转成可读文本。"""
        if isinstance(self.value, CompoundTag):
            return self.value.toString()
        return java_to_string(self.value)

    def toString(self):
        return u"{}:{}".format(self.tag_type, self.value)

    def __repr__(self):
        return u"<TagValue {}>".format(self.toString())


# ============================================================
# CompoundTag
# ============================================================

class IntTag(TagValue):
    def __init__(self, value):
        value = int(value)
        value = ((value + 2147483648) % 4294967296) - 2147483648
        TagValue.__init__(self, value, TagType.INT)

    @staticmethod
    def valueOf(value):
        return IntTag(value)

    def getAsInt(self):
        return self.value

    def copy(self):
        return self


class CompoundTag(object):
    """
    对应 net.minecraft.nbt.CompoundTag。

    一张 {名字: 带类型的值} 表，可以嵌套。
    真实代码里到处是 `tag.getInt("x")` / `tag.putInt("x", 1)`。

    **键的顺序按插入顺序保留**（Python 字典本来就保证）——
    NBT 写盘时的顺序在 Minecraft 里是稳定的，
    若换成无序结构，同一份数据两次写出的字节会不同，比对/去重会失效。
    """

    TYPE = TagType.COMPOUND

    def __init__(self, initial=None):
        self._entries = {}
        if initial:
            for key in initial:
                self.put(key, initial[key])

    # ---------------- 写 ----------------

    def put(self, key, value):
        """
        对应 put(String, Tag) / putInt / putString 等的通用入口。

        值的类型按 Python 类型推断（详见 TagType.of）。
        需要精确控制类型时用下面的 putByte / putInt 等。
        """
        name = java_to_string(key)
        self._entries[name] = TagValue(value)
        return None

    def putTyped(self, key, value, tag_type):
        """写入并**显式指定** NBT 类型（用于 byte/short/long 这类）。"""
        name = java_to_string(key)
        self._entries[name] = TagValue(value, tag_type)
        return None

    def putByte(self, key, value):
        """对应 putByte(String, byte)。"""
        return self.putTyped(key, int(value), TagType.BYTE)

    def putShort(self, key, value):
        return self.putTyped(key, int(value), TagType.SHORT)

    def putInt(self, key, value):
        return self.putTyped(key, int(value), TagType.INT)

    def putLong(self, key, value):
        return self.putTyped(key, int(value), TagType.LONG)

    def putFloat(self, key, value):
        return self.putTyped(key, float(value), TagType.FLOAT)

    def putDouble(self, key, value):
        return self.putTyped(key, float(value), TagType.DOUBLE)

    def putString(self, key, value):
        return self.putTyped(key, java_to_string(value), TagType.STRING)

    def putBoolean(self, key, value):
        """对应 putBoolean：NBT 里存成 byte 0/1。"""
        return self.putByte(key, 1 if value else 0)

    def putCompound(self, key, value):
        if not isinstance(value, CompoundTag):
            raise IllegalArgumentException(
                u"putCompound 需要 CompoundTag，收到 {}".format(
                    type(value).__name__))
        return self.putTyped(key, value, TagType.COMPOUND)

    def putList(self, key, values):
        return self.putTyped(key, list(values), TagType.LIST)

    def putIntArray(self, key, values):
        return self.putTyped(key, [int(v) for v in values], TagType.INT_ARRAY)

    # ---------------- 读 ----------------

    def _entry(self, key):
        return self._entries.get(java_to_string(key))

    def contains(self, key):
        """对应 contains(String)：键是否存在。"""
        return java_to_string(key) in self._entries

    def containsTyped(self, key, tag_type):
        """对应 contains(String, int)：键存在**且类型匹配**。"""
        entry = self._entry(key)
        return entry is not None and entry.tag_type == tag_type

    def get(self, key):
        """
        对应 get(String)：取原始值；不存在返回 None。

        注意 Java 里返回的是 Tag 对象，这里返回底层的 Python 值 ——
        翻译后的代码多数直接用 getInt/getString 这类方法，
        需要原始值时用这个方法。
        """
        entry = self._entry(key)
        return entry.value if entry is not None else None

    def getTagType(self, key):
        """取某个键的 NBT 类型（不存在返回 None）。"""
        entry = self._entry(key)
        return entry.tag_type if entry is not None else None

    def getAllKeys(self):
        """对应 getAllKeys()：所有键（插入顺序）。"""
        return list(self._entries.keys())

    def size(self):
        return len(self._entries)

    def isEmpty(self):
        return len(self._entries) == 0

    def _intOr(self, key, default):
        entry = self._entry(key)
        if entry is None:
            return default
        return entry.asInt()

    def _floatOr(self, key, default):
        entry = self._entry(key)
        if entry is None:
            return default
        return entry.asFloat()

    def getByte(self, key):
        """对应 getByte(String)：不存在返回 0（**不是抛异常**，与 Java 一致）。"""
        return self._intOr(key, 0)

    def getShort(self, key):
        return self._intOr(key, 0)

    def getInt(self, key):
        return self._intOr(key, 0)

    def getLong(self, key):
        return self._intOr(key, 0)

    def getFloat(self, key):
        return self._floatOr(key, 0.0)

    def getDouble(self, key):
        return self._floatOr(key, 0.0)

    def getString(self, key):
        """对应 getString(String)：不存在返回空串。"""
        entry = self._entry(key)
        if entry is None:
            return u""
        return entry.asString()

    def getBoolean(self, key):
        """对应 getBoolean(String)：非 0 即为真。"""
        return self.getByte(key) != 0

    def getCompound(self, key):
        """
        对应 getCompound(String)：取嵌套的 CompoundTag。

        不存在时返回**空 CompoundTag** 而不是 None —— 与 Java 一致，
        这样 `tag.getCompound("a").getInt("b")` 这种链式读法不会 NPE。
        """
        entry = self._entry(key)
        if entry is None or not isinstance(entry.value, CompoundTag):
            return CompoundTag()
        return entry.value

    def getList(self, key):
        """对应 getList(String, int)：取列表；不存在返回空列表。"""
        entry = self._entry(key)
        if entry is None or not isinstance(entry.value, (list, tuple)):
            return []
        return list(entry.value)

    def getIntArray(self, key):
        entry = self._entry(key)
        if entry is None or not isinstance(entry.value, (list, tuple)):
            return []
        return [int(v) for v in entry.value]

    def getUUID(self, key):
        """对应 getUUID(String)：本实现里 UUID 就是字符串。"""
        return self.getString(key)

    # ---------------- 删除 ----------------

    def remove(self, key):
        """对应 remove(String)。"""
        self._entries.pop(java_to_string(key), None)
        return None

    def merge(self, other):
        """
        对应 merge(CompoundTag)：把另一份的键合并进来（同名覆盖）。

        嵌套的 CompoundTag 会递归合并 —— 与 Java 的行为一致。
        """
        if not isinstance(other, CompoundTag):
            raise IllegalArgumentException(
                u"merge 需要 CompoundTag，收到 {}".format(type(other).__name__))
        for key in other.getAllKeys():
            incoming = other.get(key)
            existing = self.get(key)
            if isinstance(incoming, CompoundTag):
                if not isinstance(existing, CompoundTag):
                    existing = CompoundTag()
                    self.putCompound(key, existing)
                existing.merge(incoming)
            else:
                self._entries[key] = TagValue(
                    incoming, other.getTagType(key))
        return None

    def copy(self):
        """对应 copy()：深拷贝一份。"""
        clone = CompoundTag()
        for key in self._entries:
            entry = self._entries[key]
            if isinstance(entry.value, CompoundTag):
                clone._entries[key] = TagValue(entry.value.copy(),
                                               entry.tag_type)
            elif isinstance(entry.value, list):
                clone._entries[key] = TagValue(list(entry.value),
                                               entry.tag_type)
            else:
                clone._entries[key] = TagValue(entry.value, entry.tag_type)
        return clone

    # ---------------- 展示与比较 ----------------

    def toString(self):
        parts = []
        for key in self._entries:
            parts.append(u"{}:{}".format(key, self._entries[key].toString()))
        return u"{{{}}}".format(u", ".join(parts))

    def equals(self, other):
        if not isinstance(other, CompoundTag):
            return False
        if len(other._entries) != len(self._entries):
            return False
        for key in self._entries:
            if key not in other._entries:
                return False
            if other._entries[key].tag_type != self._entries[key].tag_type:
                return False
            if other._entries[key].value != self._entries[key].value:
                return False
        return True

    def hashCode(self):
        return hash_code(self.toString())

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __contains__(self, key):
        return self.contains(key)

    def __getitem__(self, key):
        entry = self._entry(key)
        if entry is None:
            raise KeyError(key)
        return entry.value

    def __setitem__(self, key, value):
        self.put(key, value)

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<CompoundTag {}>".format(self.toString())


# ============================================================
# ListTag
# ============================================================

class ListTag(object):
    """
    对应 net.minecraft.nbt.ListTag。

    真实代码里它多用于「一串同类型元素」。本实现就用普通列表承担，
    这个类提供 Java 风格的方法名（size / get / add）。
    """

    def __init__(self, values=None):
        self.values = list(values) if values else []

    def add(self, value):
        self.values.append(value)
        return None

    def size(self):
        return len(self.values)

    def get(self, index):
        return self.values[int(index)]

    def isEmpty(self):
        return len(self.values) == 0

    def toList(self):
        return list(self.values)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return u"<ListTag {} 项>".format(len(self.values))


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.nbt.IntTag": IntTag,
    "net.minecraft.nbt.CompoundTag": CompoundTag,
    "net.minecraft.nbt.ListTag": ListTag,
    "net.minecraft.nbt.Tag": TagValue,
    "net.minecraft.nbt.TagTypes": TagType,
    "net.minecraft.nbt.CompoundTag$1": TagType,
}


__all__ = ["TagType", "TagValue", "CompoundTag", "ListTag", "JAVA_MAP"]

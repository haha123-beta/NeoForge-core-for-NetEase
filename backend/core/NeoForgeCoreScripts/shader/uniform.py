# -*- coding: utf-8 -*-
# shader/uniform.py
# ζ 层：着色器 uniform
#
# 真实用法（逐字来自反编译源码 CosmicShaderEventHandler.java:84-91）：
#
#     cosmicTime = Objects.requireNonNull(cosmicShader.getUniform("time"));
#     cosmicYaw  = Objects.requireNonNull(cosmicShader.getUniform("yaw"));
#     cosmicPitch = Objects.requireNonNull(cosmicShader.getUniform("pitch"));
#     cosmicTime.set((float)renderTime + renderFrame);
#     cosmicShader.onApply(() -> cosmicTime.set((float)renderTime + renderFrame));
#
# **这里有一个硬约束**：真实代码对 getUniform 的结果做了
# `Objects.requireNonNull(...)` —— 返回 null 会直接让着色器注册回调崩掉。
# 所以本层必须给出能正常应答的 uniform 对象，
# 而不是「反正基岩版不渲染，返回 None 算了」。
# 这不是观感问题，是**功能性失败**。
#
# 本层的定位：**保留接口、不真的渲染**。
# 基岩版的渲染管线与 Java 版（OpenGL/GLSL）完全不同，
# 着色器无法照搬；但 uniform 的读写接口必须完整，
# 否则上层依赖它的逻辑（时间推进、界面状态）会连带崩掉。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore


# ============================================================
# UniformType
# ============================================================

class UniformType(object):
    """
    对应真实代码里的 UniformType 枚举（CCShaderInstance 用到）。

    Java 版支持全部原版 GLSL 类型。这里列出常见的那批，
    并保留 `parse()` —— 真实代码用 `UniformType.parse(typeStr)`
    从着色器 JSON 里读类型名，解析失败返回 None 由调用方抛异常。
    """

    INT = u"int"
    FLOAT = u"float"
    DOUBLE = u"double"
    VEC2 = u"vec2"
    VEC3 = u"vec3"
    VEC4 = u"vec4"
    I_VEC2 = u"ivec2"
    I_VEC3 = u"ivec3"
    I_VEC4 = u"ivec4"
    U_VEC2 = u"uvec2"
    U_VEC3 = u"uvec3"
    U_VEC4 = u"uvec4"
    MAT2 = u"mat2"
    MAT3 = u"mat3"
    MAT4 = u"mat4"

    # 每个类型需要几个分量
    SIZES = {
        u"int": 1, u"float": 1, u"double": 1,
        u"vec2": 2, u"vec3": 3, u"vec4": 4,
        u"ivec2": 2, u"ivec3": 3, u"ivec4": 4,
        u"uvec2": 2, u"uvec3": 3, u"uvec4": 4,
        u"mat2": 4, u"mat3": 9, u"mat4": 16,
    }

    # 整数类类型（决定分量用 int 还是 float 存）
    INTEGER_TYPES = (u"int", u"ivec2", u"ivec3", u"ivec4",
                     u"uvec2", u"uvec3", u"uvec4")

    @staticmethod
    def values():
        return [UniformType.INT, UniformType.FLOAT, UniformType.DOUBLE,
                UniformType.VEC2, UniformType.VEC3, UniformType.VEC4,
                UniformType.I_VEC2, UniformType.I_VEC3, UniformType.I_VEC4,
                UniformType.U_VEC2, UniformType.U_VEC3, UniformType.U_VEC4,
                UniformType.MAT2, UniformType.MAT3, UniformType.MAT4]

    @staticmethod
    def parse(name):
        """
        对应 UniformType.parse(String)。

        解析失败返回 None —— 真实代码就是这么用的：
            UniformType type = UniformType.parse(typeStr);
            if (type == null) throw new ChainedJsonException(...)
        """
        if name is None:
            return None
        text = java_to_string(name).strip().lower()
        for candidate in UniformType.values():
            if candidate == text:
                return candidate
        return None

    @staticmethod
    def sizeOf(uniform_type):
        """该类型的分量个数。"""
        return UniformType.SIZES.get(uniform_type, 1)

    @staticmethod
    def isInteger(uniform_type):
        return uniform_type in UniformType.INTEGER_TYPES


# ============================================================
# UniformData
# ============================================================

class UniformData(object):
    """
    对应 sen.manaita_plus_legacy.client.shander.comis.UniformData。

    真实代码里它继承 `com.mojang.blaze3d.shaders.Uniform`，把值写进 OpenGL。
    基岩版没有这条管线，所以这里**只存值不写 GL**：

      - `set(value)` / `glUniformF` / `glUniformI` / `glUniformD` 都记录值；
      - `getValues()` 取回最后一次写入的值（自测与诊断用）。

    为什么不干脆做成 no-op：上层会读回 uniform 值做逻辑
    （例如按时间推进做动画），值丢了行为就会不对。
    存下来至少让依赖它的逻辑保持一致。
    """

    def __init__(self, name, uniform_type=None, count=1, shader=None):
        self.name = java_to_string(name)
        self.uniform_type = uniform_type if uniform_type is not None \
            else UniformType.FLOAT
        self.count = int(count)
        self.shader = shader

        # 初始值按类型给（与 GLSL 的零值一致）
        size = max(UniformType.sizeOf(self.uniform_type), 1)
        if UniformType.isInteger(self.uniform_type):
            self._values = [0] * size
        else:
            self._values = [0.0] * size

        self.gl_location = -1      # 真实 GL 里的位置；这里没有 GL，固定 -1
        self.write_count = 0

    # ---------------- 构造 ----------------

    @staticmethod
    def makeUniform(name, uniform_type, count, shader=None):
        """
        对应 UniformData.makeUniform(name, type, count, shader)。

        它还会按 count 把类型细化（`float` + count=3 → `vec3`），
        与 CCShaderInstance.parseUniformNode 的逻辑一致。
        """
        refined = UniformData._refine_type(uniform_type, count)
        return UniformData(name, refined, count, shader)

    @staticmethod
    def _refine_type(uniform_type, count):
        """按分量数把标量类型细化成向量类型（同真实代码的 switch）。"""
        count = int(count)
        if uniform_type == UniformType.FLOAT:
            if count == 2:
                return UniformType.VEC2
            if count == 3:
                return UniformType.VEC3
            if count == 4:
                return UniformType.VEC4
        elif uniform_type == UniformType.INT:
            if count == 2:
                return UniformType.I_VEC2
            if count == 3:
                return UniformType.I_VEC3
            if count == 4:
                return UniformType.I_VEC4
        return uniform_type

    # ---------------- 写值 ----------------

    def set(self, *values):
        """
        设置值。真实代码最常见的调用：`cosmicTime.set(someFloat)`。

        支持一次传多个分量（`set(x, y, z)`），也支持传一个序列。
        """
        if len(values) == 1 and isinstance(values[0], (list, tuple)):
            values = tuple(values[0])
        if not values:
            raise IllegalArgumentException(
                u"uniform {} 的 set 没有收到值".format(self.name))

        self._values = [self._coerce(value) for value in values]
        self.write_count += 1
        return None

    def _coerce(self, value):
        if UniformType.isInteger(self.uniform_type):
            try:
                return int(value)
            except (TypeError, ValueError):
                raise IllegalArgumentException(
                    u"uniform {} 需要整数分量，收到 {!r}".format(self.name,
                                                                 value))
        try:
            return float(value)
        except (TypeError, ValueError):
            raise IllegalArgumentException(
                u"uniform {} 需要浮点分量，收到 {!r}".format(self.name, value))

    # 真实代码里的三个 GL 写入入口（名字照抄，语义改为只存值）
    def glUniformF(self, boolean, *values):
        """对应 glUniformF(boolean, float...)。"""
        return self.set(*values)

    def glUniformI(self, *values):
        """对应 glUniformI(int...)。"""
        return self.set(*values)

    def glUniformD(self, boolean, *values):
        """对应 glUniformD(boolean, double...)。"""
        return self.set(*values)

    def setSafe(self, x, y=0.0, z=0.0, w=1.0):
        """
        对应 setSafe(float, float, float, float)。

        真实代码用它「安全地写四个分量」：分量多的 uniform 取前几个，
        分量少的也能接受同样的调用而不报错。
        """
        size = max(UniformType.sizeOf(self.uniform_type), 1)
        all_values = (x, y, z, w)
        return self.set(*all_values[:size])

    # ---------------- 读值 ----------------

    def getValues(self):
        return list(self._values)

    def getFloat(self, index=0):
        """取第 index 个分量（越界抛异常，与 Java 的数组行为一致）。"""
        if index < 0 or index >= len(self._values):
            raise IllegalArgumentException(
                u"uniform {} 只有 {} 个分量，取不到第 {} 个".format(
                    self.name, len(self._values), index))
        return float(self._values[index])

    def getInt(self, index=0):
        if index < 0 or index >= len(self._values):
            raise IllegalArgumentException(
                u"uniform {} 只有 {} 个分量，取不到第 {} 个".format(
                    self.name, len(self._values), index))
        return int(self._values[index])

    def getLocation(self):
        """对应 getLocation()：GL 位置。本实现没有 GL，固定 -1。"""
        return self.gl_location

    def getName(self):
        return self.name

    def getType(self):
        return self.uniform_type

    def setLocation(self, location):
        """对应 setLocation(int)：真实代码里由 GL 反射填位置。"""
        self.gl_location = int(location)
        return None

    def close(self):
        """对应 close()：释放 GL 资源。本实现无事可做。"""
        return None

    # ---------------- 展示 ----------------

    def toString(self):
        return u"{}:{}={}".format(self.name, self.uniform_type, self._values)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Uniform {}>".format(self.toString())


# ============================================================
# Uniform 集合
# ============================================================

class UniformList(object):
    """
    着色器的 uniform 集合。

    真实代码里 `ShaderInstance.uniforms` 是个 List，parseUniformNode 往里 add。
    这里保持 List 的行为，另外维护一份按名字的索引 ——
    因为注册回调里会反复 `getUniform(name)`，线性查找太浪费。
    """

    def __init__(self):
        self._items = []
        self._by_name = {}

    def add(self, uniform):
        """对应 List.add(uniform)。"""
        if uniform is None:
            raise IllegalArgumentException(u"add 收到 None")
        self._items.append(uniform)
        self._by_name[uniform.getName()] = uniform
        return None

    def get(self, name):
        """按名字取；没有返回 None（真实代码用 requireNonNull 兜）。"""
        return self._by_name.get(java_to_string(name))

    def size(self):
        return len(self._items)

    def toList(self):
        return list(self._items)

    def names(self):
        return sorted(self._by_name.keys())

    def clear(self):
        self._items = []
        self._by_name = {}
        return None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return u"<UniformList {} 个>".format(len(self._items))


__all__ = ["UniformType", "UniformData", "UniformList"]

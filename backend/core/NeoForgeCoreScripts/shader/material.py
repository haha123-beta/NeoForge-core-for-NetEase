# -*- coding: utf-8 -*-
# shader/material.py
# ζ 层：着色器实例与注册
#
# 真实用法（逐字来自反编译源码）：
#
#   // CosmicShaderEventHandler.java:82-92
#   public static void onRegisterShaders(RegisterShadersEvent event) {
#       event.registerShader(
#           CCShaderInstance.create(event.getResourceProvider(),
#                                   ManaitaPlusLegacy.rl("cosmic_neo_no_mask"),
#                                   DefaultVertexFormat.BLOCK),
#           e -> {
#               cosmicShader = (CCShaderInstance) e;
#               cosmicTime = Objects.requireNonNull(cosmicShader.getUniform("time"));
#               ... cosmicTime.set((float)renderTime + renderFrame);
#               cosmicShader.onApply(() -> cosmicTime.set(...));
#           });
#   }
#
#   // CCShaderInstance.java:50-73
#   public static CCShaderInstance create(ResourceProvider rp, ResourceLocation loc,
#                                         VertexFormat format) {
#       try { return new CCShaderInstance(rp, loc, format); }
#       catch (IOException ex) { throw new RuntimeException("Failed to initialize shader.", ex); }
#   }
#   public void onApply(Runnable callback) { this.applyCallbacks.add(callback); }
#   public void apply() { for (Runnable cb : applyCallbacks) cb.run(); super.apply(); }
#   public UniformData getUniform(String name) { return (UniformData) super.getUniform(name); }
#
#   // CCShaderInstance.java:75-155  —— 从着色器 JSON 的 uniform 节点建 uniform
#   protected void parseUniformNode(JsonElement json) {
#       JsonObject obj = GsonHelper.convertToJsonObject(json, "uniform");
#       String name = GsonHelper.getAsString(obj, "name");
#       String typeStr = GsonHelper.getAsString(obj, "type");
#       UniformType type = UniformType.parse(typeStr);
#       if (type == null) throw new ChainedJsonException(...);
#       int count = GsonHelper.getAsInt(obj, "count");
#       ... 按 count 细化类型 ...
#       UniformData uniform = UniformData.makeUniform(name, type, count, this);
#       JsonArray jsonValues = GsonHelper.getAsJsonArray(obj, "values");
#       if (jsonValues.size() != count && jsonValues.size() > 1) throw ...;
#       ... 按 carrier 写 glUniformI / glUniformF / glUniformD ...
#       this.uniforms.add(uniform);
#   }
#
# 本层的定位：**保留接口、不真的渲染**。
# 基岩版的渲染管线与 Java 版（OpenGL/GLSL）完全不同，着色器无法照搬。
# 但 uniform 的解析与读写必须完整 —— 尤其是 `getUniform` 不能返回 None，
# 因为真实代码对它做了 `Objects.requireNonNull`（见 uniform.py 的说明）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

import json as _json

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
    from shader.uniform import UniformData, UniformList, UniformType
    from shader.opengl import RenderStateShard, RenderStateShardAccess
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    # 同目录下走包内相对导入（harness 与真机都是这种）
    from shader.uniform import UniformData, UniformList, UniformType  # type: ignore
    from shader.opengl import RenderStateShard, RenderStateShardAccess  # type: ignore


# ============================================================
# 顶点格式
# ============================================================

# Official layout identity is shared with the renderer data module.
from minecraft.vertex_format import VertexFormat, DefaultVertexFormat


# ============================================================
# ResourceProvider / ResourceLocation
# ============================================================

class ResourceProvider(object):
    """
    对应 net.minecraft.server.packs.resources.ResourceProvider。

    真实代码把它传给 ShaderInstance 的构造函数，由它去读着色器 JSON。
    本实现支持两种来源：
      - `add(location, data)` 显式塞数据（自测用）；
      - 交给外部 loader 回调去读（真机接入引擎时用）。
    """

    def __init__(self, loader=None):
        self._resources = {}
        self._loader = loader
        self.missing = []           # 记录取不到的资源，便于诊断

    def add(self, location, data):
        """登记一份资源。data 可以是 dict（已解析）或字符串（JSON 文本）。"""
        key = java_to_string(location)
        # 字符串判断用 `isinstance(data, type(u""))`：
        # Py2 里 u"" 是 unicode、Py3 里是 str，两边都成立。
        # 不要写 `unicode` —— Py3 里没有这个名字（Py2 里也不是这样判的）。
        if isinstance(data, type(u"")):
            try:
                data = _json.loads(data)
            except ValueError as error:
                raise IllegalArgumentException(
                    u"资源 {} 不是合法 JSON: {}".format(key, error))
        self._resources[key] = data
        return None

    def getResource(self, location):
        """
        对应 getResource(ResourceLocation)。

        取不到时返回 None 并记录 —— 真实代码会因为拿不到着色器 JSON 抛
        IOException，而这里让调用方自己决定（ShaderInstance 构造时会抛）。
        """
        key = java_to_string(location)
        if key in self._resources:
            return self._resources[key]
        if self._loader is not None:
            data = self._loader(key)
            if data is not None:
                if isinstance(data, type(u"")):
                    data = _json.loads(data)
                self._resources[key] = data
                return data
        self.missing.append(key)
        return None

    def hasResource(self, location):
        return java_to_string(location) in self._resources

    def missingCount(self):
        return len(self.missing)

    def __repr__(self):
        return u"<ResourceProvider {} 份资源，{} 次未命中>".format(
            len(self._resources), len(self.missing))


# ============================================================
# ShaderInstance
# ============================================================

class ShaderInstance(object):
    """
    对应 net.minecraft.client.renderer.ShaderInstance。

    **关键语义**：构造时就先把着色器 JSON 里的 uniform 全部解析出来，
    这样后续 `getUniform("time")` 才能拿到东西。
    真实代码正是依赖这一点（见文件头的 requireNonNull）。
    """

    def __init__(self, resource_provider, location, vertex_format=None):
        if resource_provider is None:
            raise IllegalArgumentException(u"ShaderInstance 需要 ResourceProvider")
        self._provider = resource_provider
        self._location = java_to_string(location)
        self._format = vertex_format
        self.uniforms = UniformList()
        self.apply_callbacks = []
        self.apply_count = 0
        self._closed = False

        # 对应真实代码：构造时读 JSON 并解析 uniform 节点
        self._parse()

    # ---------------- 解析 ----------------

    def _parse(self):
        data = self._provider.getResource(self._location)
        if data is None:
            # 真实代码在这里抛 IOException（"Failed to initialize shader."）
            raise IllegalStateException(
                u"找不到着色器资源: {}（已登记的资源: {}）".format(
                    self._location, self._provider.hasResource(self._location)))

        if not isinstance(data, dict):
            raise IllegalArgumentException(
                u"着色器 {} 的 JSON 顶层应是对象，收到 {}".format(
                    self._location, type(data).__name__))

        nodes = data.get(u"uniforms")
        if nodes is None:
            return
        if not isinstance(nodes, (list, tuple)):
            raise IllegalArgumentException(
                u"着色器 {} 的 uniforms 应是数组".format(self._location))

        for node in nodes:
            self.parseUniformNode(node)
        return None

    def parseUniformNode(self, node):
        """
        对应 parseUniformNode(JsonElement)。

        真实代码的全部校验都照搬：
          - name / type / count 必填；
          - type 解析失败要抛；
          - values 的个数与 count 不符（且大于 1）要抛；
          - 只有 1 个值时复制铺满（`Arrays.fill(values, 1, len, values[0])`）。
        """
        if not isinstance(node, dict):
            raise IllegalArgumentException(
                u"uniform 节点应是对象，收到 {}".format(type(node).__name__))

        if u"name" not in node:
            raise IllegalArgumentException(u"uniform 节点缺少 name")
        if u"type" not in node:
            raise IllegalArgumentException(u"uniform 节点缺少 type")

        name = java_to_string(node[u"name"])
        type_str = java_to_string(node[u"type"])
        uniform_type = UniformType.parse(type_str)
        if uniform_type is None:
            raise IllegalArgumentException(
                u"未知的 uniform 类型 {!r}（见 UniformType）".format(type_str))

        count = int(node.get(u"count", 1))
        uniform = UniformData.makeUniform(name, uniform_type, count, self)

        values = node.get(u"values")
        if values is None:
            values = []
        if not isinstance(values, (list, tuple)):
            raise IllegalArgumentException(
                u"uniform {} 的 values 应是数组".format(name))

        # 单个值铺满所有分量（与真实代码的 Arrays.fill 一致）
        if count > 1 and len(values) == 1:
            values = [values[0]] * count

        if len(values) != count and len(values) > 1:
            raise IllegalArgumentException(
                u"uniform {} 的 values 个数不对（期望 {}，实际 {}）".format(
                    name, count, len(values)))

        if values:
            if UniformType.isInteger(uniform.getType()):
                uniform.glUniformI(*values)
            else:
                uniform.glUniformF(False, *values)

        self.uniforms.add(uniform)
        return uniform

    # ---------------- 查询 ----------------

    def getUniform(self, name):
        """
        对应 getUniform(String)：**可能返回 None**（真实代码自己 requireNonNull）。

        这是本层最关键的接口 —— 返回 None 会让真实代码的注册回调直接崩。
        """
        return self.uniforms.get(name)

    def hasUniform(self, name):
        return self.uniforms.get(name) is not None

    def getUniformNames(self):
        return self.uniforms.names()

    def getLocation(self):
        return self._location

    def getVertexFormat(self):
        return self._format

    # ---------------- 应用 ----------------

    def onApply(self, callback):
        """
        对应 onApply(Runnable)：登记一个「每次应用前执行」的回调。

        真实代码用它推进时间：`cosmicShader.onApply(() -> cosmicTime.set(...))`。
        """
        if callback is None:
            raise IllegalArgumentException(u"onApply 收到 None")
        self.apply_callbacks.append(callback)
        return None

    def apply(self):
        """
        对应 apply()：先跑回调，再应用着色器。

        基岩版没有 GL 可应用，所以「应用」这一步只记数 ——
        但**回调必须真的执行**，因为上层的时间推进逻辑依赖它。
        """
        if self._closed:
            raise IllegalStateException(
                u"着色器 {} 已关闭，不能再 apply".format(self._location))
        for callback in self.apply_callbacks:
            callback()
        self.apply_count += 1
        return None

    def callbackCount(self):
        return len(self.apply_callbacks)

    def getApplyCount(self):
        return self.apply_count

    def clear(self):
        """对应 clear()：清空 uniform 与回调。"""
        self.uniforms.clear()
        self.apply_callbacks = []
        return None

    def close(self):
        """对应 close()：释放 GL 资源。本实现标记关闭。"""
        self._closed = True
        return None

    def isClosed(self):
        return self._closed

    # ---------------- 展示 ----------------

    def toString(self):
        return u"{}[{}]".format(self._location,
                                u",".join(self.uniforms.names()))

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<ShaderInstance {}>".format(self.toString())


# ============================================================
# 注册事件
# ============================================================

from neoforge.event.client import RegisterShadersEvent


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.client.renderer.ShaderInstance": ShaderInstance,
    "net.minecraft.client.renderer.RenderStateShard": RenderStateShard,
    "net.neoforged.neoforge.client.event.RegisterShadersEvent":
        RegisterShadersEvent,
    "com.mojang.blaze3d.vertex.VertexFormat": VertexFormat,
    "com.mojang.blaze3d.vertex.DefaultVertexFormat": DefaultVertexFormat,
    "net.minecraft.server.packs.resources.ResourceProvider": ResourceProvider,
}


__all__ = [
    "VertexFormat", "DefaultVertexFormat",
    "ResourceProvider",
    "ShaderInstance", "RegisterShadersEvent",
    "JAVA_MAP",
]

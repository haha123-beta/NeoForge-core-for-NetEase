# -*- coding: utf-8 -*-
# shader/__init__.py
# ζ 层：着色器处理
#
# 这一层面对的现实：**基岩版的渲染管线与 Java 版（OpenGL/GLSL）完全不同**，
# 着色器无法照搬。所以本层不追求「把着色器跑起来」，而是：
#
#   1. **保留接口**：uniform 解析、注册事件、渲染状态对象都要能用，
#      否则翻译后的代码在导入或初始化阶段就崩了；
#   2. **不真的渲染**：所有 GL 操作退化为「记值 / 记数」，不产生画面效果；
#   3. **留痕**：走到这一层说明有视觉功能不会生效，必须可查。
#
# 为什么「保留接口」比「直接跳过」重要
# ------------------------------------
# 真实代码里有这样一段（CosmicShaderEventHandler.java:82-92）：
#
#     event.registerShader(CCShaderInstance.create(rp, loc, format), e -> {
#         cosmicShader = (CCShaderInstance) e;
#         cosmicTime = Objects.requireNonNull(cosmicShader.getUniform("time"));
#         cosmicTime.set((float)renderTime + renderFrame);
#         cosmicShader.onApply(() -> cosmicTime.set(...));
#     });
#
# 如果 `getUniform` 返回 None，`Objects.requireNonNull` 立刻抛异常 ——
# **着色器注册回调崩掉**，连带 `cosmicShader` 这些静态字段永远是 null，
# 后面的渲染逻辑全线报错。
#
# 所以这不是「观感问题」，是**功能性失败**：本层必须给出能正常应答的
# uniform 对象，哪怕它不产生任何画面效果。
#
# 与 δ 层跳过规则的分工
# --------------------
#   δ 层决定「RegisterShadersEvent 这个**事件**要不要派发」→ 跳过；
#   ζ 层保证「RegisterShadersEvent 这个**类**存在且接口完整」→ 必须有。
# 两者不矛盾：类不存在会让翻译层在导入阶段就报错，
# 而「不派发」只是不执行它的副作用。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

from shader.uniform import (  # noqa: F401
    UniformType,
    UniformData,
    UniformList,
)

from shader.opengl import (  # noqa: F401
    RenderStateShard,
    ShaderStateShard,
    EmptyTextureStateShard,
    TextureStateShard,
    RenderStateShardAccess,
)


# `shader.material` **不在这里导入**。
#
# 原因：它构成一个经典循环 —— `material` 属于 `shader` 包，
# 而包的 `__init__.py` 又反过来导入 `material`。
# 真机（原生 Python）靠「部分初始化模块」容忍这种环，但
# 核心包的模块是「转译后再执行」的，环里拿到的是还没填内容的半成品，
# `from shader.material import VertexFormat` 会直接 ImportError
# （实测踩到，harness 那边怎么调顺序都不稳）。
#
# 所以在 `material` 上挂一个 `_PACKAGE_EXPORTS`，由核心包入口在
# 全部模块就位后再调用 `install_exports()` 补上顶层导出。
# 需要这些名字的地方直接 `from shader.material import ...` 即可。
def install_exports():
    """
    把 `shader.material` 的公开名字挂到本包上（由入口调用）。

    为什么做成显式调用而不是模块级导入：见上面的说明，
    模块级导入会与 `material` 形成循环。
    """
    from shader.material import (  # noqa: F401
        VertexFormat,
        DefaultVertexFormat,
        ResourceProvider,
        ShaderInstance,
        RegisterShadersEvent,
    )

    namespace = globals()
    for name in ("VertexFormat", "DefaultVertexFormat", "ResourceProvider",
                 "ShaderInstance", "RegisterShadersEvent"):
        namespace[name] = _material_attribute(name)

    # JAVA_MAP 是三个子模块合并出来的
    namespace["JAVA_MAP"] = _merged_java_map()
    return None


def _material_attribute(name):
    """按名字取 `shader.material` 上的对象。"""
    from shader import material as _material
    return getattr(_material, name)


def _merged_java_map():
    """合并三个子模块的名称映射表。"""
    from shader import material as _material
    from shader import opengl as _opengl
    from shader import uniform as _uniform

    merged = {}
    for module in (_uniform, _opengl, _material):
        java_map = getattr(module, "JAVA_MAP", None)
        if java_map:
            merged.update(java_map)
    return merged


# 顶层导出名（install_exports 会把它们填上）
VertexFormat = None
DefaultVertexFormat = None
ResourceProvider = None
ShaderInstance = None
RegisterShadersEvent = None
JAVA_MAP = {}


__all__ = [
    # uniform
    "UniformType", "UniformData", "UniformList",
    # 渲染状态
    "RenderStateShard", "ShaderStateShard", "EmptyTextureStateShard",
    "TextureStateShard", "RenderStateShardAccess",
    # 着色器实例与注册（需先调 install_exports）
    "VertexFormat", "DefaultVertexFormat", "ResourceProvider",
    "ShaderInstance", "RegisterShadersEvent",
    "install_exports",
    "JAVA_MAP",
]


# -*- coding: utf-8 -*-
# shader/opengl.py
# ζ 层：渲染状态（OpenGL 概念）
#
# 真实代码（CosmicShaderEventHandler extends RenderStateShard）用到的成员：
#
#     RenderStateShardAccess.EQUAL_DEPTH_TEST          深度测试
#     RenderStateShardAccess.LIGHT_MAP                 光照贴图
#     RenderStateShardAccess.TRANSLUCENT_TRANSPARENCY  半透明
#     RenderStateShardAccess.COSMIC_TEXTURE_ISOLATED   纹理隔离
#     new RenderStateShard.ShaderStateShard(() -> cosmicShader)
#     new RenderStateShard.EmptyTextureStateShard(...)
#
# 这些都是 OpenGL 状态开关，基岩版没有对应物。
# 本实现只保留**身份与名字** —— 真实代码会把它们塞进
# `RenderType.CompositeState.builder().setDepthTestState(...)...`
# 的链式调用里，所以需要能传、能比、能打印，但不产生任何 GL 效果。
#
# 为什么单独一个文件而不是塞进 uniform.py：
#   uniform 是「着色器参数」，渲染状态是「管线开关」，两者语义无关。
#   混在一起会让 material.py 的依赖变得不清晰。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib.lang import java_to_string
except ImportError:
    from lang import java_to_string  # type: ignore


class RenderStateShard(object):
    """
    对应 net.minecraft.client.renderer.RenderStateShard。

    真实模组的主类 `CosmicShaderEventHandler extends RenderStateShard`，
    说明它需要访问父类的受保护状态字段。
    """

    def __init__(self, name=u"RenderStateShard", setup_state=None,
                 clear_state=None):
        self._name = java_to_string(name)
        self._setup_state = setup_state
        self._clear_state = clear_state
        # 真实代码用这两个字段表达「每种状态的开关次数」，便于调试
        self.setup_count = 0
        self.clear_count = 0

    # ---------------- 身份 ----------------

    def name(self):
        return self._name

    def getName(self):
        return self._name

    # ---------------- 状态开关 ----------------

    def setupRenderState(self):
        """
        对应 setupRenderState()：真实代码在这里开关 GL 状态。

        本实现只记数并执行可选回调 —— 没有 GL 可开关，
        但记数能让「这条渲染路径有没有被走到」变得可查。
        """
        self.setup_count += 1
        if self._setup_state is not None:
            self._setup_state()
        return None

    def clearRenderState(self):
        self.clear_count += 1
        if self._clear_state is not None:
            self._clear_state()
        return None

    # ---------------- 展示与比较 ----------------

    def toString(self):
        return self._name

    def equals(self, other):
        return isinstance(other, RenderStateShard) \
            and other._name == self._name

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return hash(self._name)

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<RenderStateShard {}>".format(self._name)


class ShaderStateShard(RenderStateShard):
    """
    对应 RenderStateShard.ShaderStateShard。

    真实代码：`new RenderStateShard.ShaderStateShard(() -> cosmicShader)`

    参数是 **Supplier 而不是着色器本身**，这点很关键：
    着色器要等注册回调执行完才有值，写成固定引用会永远拿到 null。
    """

    def __init__(self, shader_supplier=None):
        RenderStateShard.__init__(self, u"ShaderStateShard")
        self._supplier = shader_supplier

    def getShader(self):
        """取当前着色器（尚未注册时返回 None）。"""
        if self._supplier is None:
            return None
        return self._supplier()


class EmptyTextureStateShard(RenderStateShard):
    """对应 RenderStateShard.EmptyTextureStateShard。"""

    def __init__(self, name=u"EmptyTextureStateShard"):
        RenderStateShard.__init__(self, name)


class TextureStateShard(RenderStateShard):
    """对应 RenderStateShard.TextureStateShard（带纹理位置）。"""

    def __init__(self, texture=None):
        RenderStateShard.__init__(self, u"TextureStateShard")
        self._texture = texture

    def getTexture(self):
        return self._texture


# 挂成内部类，对应 `RenderStateShard.ShaderStateShard` 的写法
RenderStateShard.ShaderStateShard = ShaderStateShard
RenderStateShard.EmptyTextureStateShard = EmptyTextureStateShard
RenderStateShard.TextureStateShard = TextureStateShard


def _make_access_states():
    """构造原版渲染状态常量（拆成函数只是为了命名短一点）。"""
    return {
        u"EQUAL_DEPTH_TEST": RenderStateShard(u"EQUAL_DEPTH_TEST"),
        u"LEQUAL_DEPTH_TEST": RenderStateShard(u"LEQUAL_DEPTH_TEST"),
        u"LIGHT_MAP": RenderStateShard(u"LIGHT_MAP"),
        u"TRANSLUCENT_TRANSPARENCY":
            RenderStateShard(u"TRANSLUCENT_TRANSPARENCY"),
        u"NO_TRANSPARENCY": RenderStateShard(u"NO_TRANSPARENCY"),
        u"COSMIC_TEXTURE_ISOLATED":
            RenderStateShard(u"COSMIC_TEXTURE_ISOLATED"),
        u"DEFAULT_TEXTURE": RenderStateShard(u"DEFAULT_TEXTURE"),
        u"CULL": RenderStateShard(u"CULL"),
        u"NO_CULL": RenderStateShard(u"NO_CULL"),
    }


class RenderStateShardAccess(object):
    """
    对应真实模组里的 RenderStateShardAccess。

    模组用 Access Widener 拿原版私有字段，包成这个类对外暴露。
    本实现给出同名同身份的对象，让 `CompositeState.builder()...`
    的链式调用能走完。

    **这些常量必须是稳定对象**：真实代码用它们做
    `setDepthTestState(RenderStateShardAccess.EQUAL_DEPTH_TEST)`
    之类的调用，如果每次访问都造新对象，后续的身份比较就会失败。
    所以在类定义之后一次性挂上去（见下方），而不是写 property。
    """

    pass


# 一次性挂上常量（比在类体里逐个写更短，也便于将来扩充）
_ACCESS_STATES = _make_access_states()
for _state_name in _ACCESS_STATES:
    setattr(RenderStateShardAccess, _state_name, _ACCESS_STATES[_state_name])


__all__ = [
    "RenderStateShard", "ShaderStateShard", "EmptyTextureStateShard",
    "TextureStateShard", "RenderStateShardAccess",
]

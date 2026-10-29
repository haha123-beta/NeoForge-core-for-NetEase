# -*- coding: utf-8 -*-
# core/keyword_renames.py
# Python 关键字冲突的改名映射（翻译层与核心包的共同约定）
#
# 问题：
#   Java 里 `itemStack.is(other)` / `EventResult.pass()` / `Shapes.or(a, b)`
#   都是合法调用；翻译成 Python 后：
#       itemStack.is(other)      -> SyntaxError（is 是关键字）
#       EventResult.pass()       -> SyntaxError（pass 是关键字）
#       Shapes.or(a, b)          -> SyntaxError（or 是关键字）
#   这不是运行时问题，是**解析**问题 —— 函数体里写任何兼容代码都绕不过去，
#   调用语法必须转换；可使用 getattr(obj, "is") 保留原属性名。
#
# 实测统计（dev/keyword_lint.py 扫反编译源码）：
#   .is()   28 处    .pass()  7 处    .or()  4 处
#   （Python 2 有 31 个关键字，Python 3 另有 6 个，共 37 个）
#
# 命名约定：统一在关键字后面加语义后缀，**不用下划线前缀** ——
#   下划线开头的名字在 Java 侧看起来像私有成员，容易被误读。
#
# 用法：
#   翻译层在把 Java 方法名转成 Python 名字时查这张表；
#   旧代码继续使用此表；core.java_names 为已实现方法提供原名属性。
#   新翻译可用 getattr 保留 Java 名称，不要求人工改成语义后缀。

from __future__ import absolute_import


# Java 类名 -> {Java 方法名: Python 方法名}
#
# 键用 Java 全限定名，因为不同类可能有同名方法而需要不同的改名策略。
METHOD_RENAMES = {
    "net.minecraft.world.item.ItemStack": {
        "is": "isItem",
    },
    "net.minecraft.world.level.block.state.BlockState": {
        "is": "isBlock",
    },
    "net.minecraft.world.level.block.Block": {
        "is": "isBlock",
    },
    "net.minecraft.world.level.material.FluidState": {
        "is": "isFluid",
    },
    "net.minecraft.world.level.ItemLike": {
        "is": "isItem",
    },
    "net.minecraft.world.item.Item": {
        "is": "isItem",
    },
    "net.minecraft.world.item.crafting.Ingredient": {
        "is": "isItem",
    },
    "net.neoforged.neoforge.common.util.EventResult": {
        "pass": "passResult",
    },
    "net.neoforged.neoforge.common.util.TriState": {
        "pass": "passResult",
    },
    "net.minecraft.world.item.context.UseOnContext": {
        "pass": "passResult",
    },
    "net.minecraft.world.phys.shapes.Shapes": {
        "or": "orShapes",
        "not": "notShapes",
        "and": "andShapes",
    },
}

# Java 方法名 -> Python 方法名（不区分类时用的宽松映射）
#
# 只放「几乎所有出现场景都要同样改名」的项。
# 如果一个名字在不同类里要改成不同的名字，就**不要**放进来 ——
# 放进来会造成误改名，比不改还糟。
GLOBAL_RENAMES = {
    "is": "isItem",
    "pass": "passResult",
    "or": "orShapes",
    "not": "notValue",
    "in": "inValue",
    "and": "andValue",
    "import": "importValue",
    "print": "printValue",
}


def rename_method(java_class, java_method):
    """
    按「类 + 方法名」查改名。

    先查精确的类映射，再退回全局映射，都没有就原样返回。
    这样精确映射优先，避免全局规则误伤。
    """
    class_map = METHOD_RENAMES.get(java_class)
    if class_map is not None and java_method in class_map:
        return class_map[java_method]
    return GLOBAL_RENAMES.get(java_method, java_method)


def is_keyword(name):
    """判断一个名字是否撞上 Python 2 或 Python 3 的关键字。"""
    import keyword
    if keyword.iskeyword(name):
        return True
    # Python 3 独有关键字：本机是 Py3 时 iskeyword 已覆盖，
    # 但为了在 Py2 上也能正确判断，这里再补一遍。
    return name in (u"nonlocal", u"async", u"await",
                    u"False", u"None", u"True")


def describe():
    """返回人类可读的改名清单（供文档与自检输出用）。"""
    lines = []
    for java_class in sorted(METHOD_RENAMES):
        for java_method in sorted(METHOD_RENAMES[java_class]):
            python_name = METHOD_RENAMES[java_class][java_method]
            lines.append(u"{}.{}() -> .{}()".format(java_class, java_method,
                                                    python_name))
    return lines


__all__ = ["METHOD_RENAMES", "GLOBAL_RENAMES", "rename_method",
           "is_keyword", "describe"]

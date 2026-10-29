# -*- coding: utf-8 -*-
"""
api_coverage —— 度量「核心包覆盖了多少真实用到的 API」

思路
----
每个核心包模块都导出一张 `JAVA_MAP`：{Java 全限定名: Python 实现}。
反编译源码里的 import 就是「这个模组真实需要的 Java 类」清单。
两者一比对，就得到覆盖率 —— 不用凭感觉判断进度。

为什么值得单独做：
  分层实现最怕「做了一堆没人用的类，真正要用的却没做」。
  这个工具把「还差哪些类」变成一份可排序的清单：
  按引用次数排，就知道下一步该做哪个。

用法
----
    python dev/api_coverage.py            # 摘要 + 缺口前 30
    python dev/api_coverage.py --detail   # 全部缺口
"""

import io
import os
import re
import sys
import collections

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)
SCRIPTS_ROOT = os.path.join(PACK_ROOT, "NeoForgeCoreScripts")
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(PACK_ROOT))
DECOMPILED_ROOT = os.path.join(WORKSPACE_ROOT, "refs", "decompiled")

_IMPORT_RE = re.compile(r'^\s*import\s+([\w\.\$]+)\s*;', re.MULTILINE)

# 核心包里带 JAVA_MAP 的模块（相对脚本根的模块路径）
#
# 注意：写了新模块就要加进来，否则它的 JAVA_MAP 不会计入覆盖率，
# 数字会偏低（同 layers.py 的教训 —— 列表漂移过两次）。
MAP_MODULES = (
    "java_stdlib.util",
    "java_stdlib.lang",
    "neoforge.registries",
    "neoforge.event",
    "neoforge.config",
    "neoforge.network",
    "neoforge.common",
    "minecraft.core",
    "minecraft.item",
    "minecraft.block",
    "minecraft.shapes",
    "minecraft.entity",
    "minecraft.attributes",
    "minecraft.goals",
    "minecraft.navigation",
    "minecraft.combat",
    "minecraft.synched_entity_data",
    "minecraft.common_goals",
    "minecraft.level",
    "minecraft.level_access",
    "minecraft.registries",
    "minecraft.sound",
    "minecraft.block_entity",
    "minecraft.crafting",
    "minecraft.item_context",
    "minecraft.block_extra",
    "minecraft.nbt",
    "minecraft.menu",
    "minecraft.util",
    "shader.material",
    "shader.uniform",
    "shader.opengl",
    "shader",
)
# 不在覆盖范围内的命名空间：这些属于原版游戏内部实现、第三方库，
# 或者**模组自己的代码**，核心包不应该去实现它们。
EXCLUDED_PREFIXES = (
    "java.",
    "javax.",
    "io.netty",
    "it.unimi",
    "org.slf4j",
    "org.apache",
    "com.google",
    "org.jetbrains.annotations",   # 只是编译期注解，运行时不需要
    "com.mojang.blaze3d",          # 渲染底层，基岩版管线完全不同
    "com.mojang.datafixers",
    "com.mojang.serialization",
    # 注意：**不排除** net.minecraft.client ——
    # 客户端类（KeyMapping / ItemProperties / RegisterKeyMappingsEvent 等）
    # 确实是核心包要做的活，排除掉等于把真实工作量藏起来。
    # 模组自己的包：这些是被翻译的对象，不是要实现的 API。
    # 不排除掉的话缺口清单里全是模组类，真正的 API 缺口会被淹没
    # （实测：前 30 个缺口里有 11 个是 sen.manaita_plus_legacy.*）。
    "sen.",
)

# 已明确「不做」的项及理由。列出来是为了让报告诚实，而不是假装覆盖率高。
DELIBERATELY_SKIPPED = {
    "net.minecraft.client.gui.screens.inventory.AbstractContainerScreen":
        u"客户端界面，基岩版用另一套 UI 体系",
    "net.minecraft.client.gui.GuiGraphics":
        u"客户端渲染，基岩版无此类",
    "net.minecraft.client.Minecraft":
        u"客户端主类，基岩版无对应物",
}


def find_decompiled_root():
    if not os.path.isdir(DECOMPILED_ROOT):
        return None
    for name in sorted(os.listdir(DECOMPILED_ROOT)):
        candidate = os.path.join(DECOMPILED_ROOT, name)
        if os.path.isdir(candidate):
            return candidate
    return None


def collect_imports(root):
    """返回 {Java 全限定名: 引用文件数}。"""
    imports = collections.Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            if not name.endswith(".java"):
                continue
            path = os.path.join(dirpath, name)
            text = io.open(path, "r", encoding="utf-8", errors="replace").read()
            for imported in set(_IMPORT_RE.findall(text)):
                imports[imported] += 1
    return imports


def collect_provided():
    """
    从核心包各模块的 JAVA_MAP 收集「已提供的 Java 名」。

    用 harness 的 Package 加载模块（它会处理 Py2 语法转译），
    而不是手动解析源码 —— 这样 JAVA_MAP 是**真的能被导入**的那份。
    """
    sys.path.insert(0, DEV_ROOT)
    from harness import Package

    pkg = Package()
    provided = {}
    modules_loaded = []
    failures = []

    for module_name in MAP_MODULES:
        try:
            module = pkg.load(module_name)
        except Exception as error:  # noqa: B902 —— dev/ 工具跑在本机 Py3 上，
            # 必须用 as 语法；只有核心包源码（NeoForgeCoreScripts/）才写 Py2 风格。
            failures.append((module_name, u"{}: {}".format(
                type(error).__name__, error)))
            continue
        modules_loaded.append(module_name)

        # 有些包把导出做成显式调用（因为模块级导入会形成循环）。
        # shader 就是这种情况：`shader/__init__.py` 不导入 `shader.material`，
        # 否则「包导入子模块、子模块又属于该包」会成环。
        install = getattr(module, "install_exports", None)
        if callable(install):
            try:
                install()
            except Exception as error:
                failures.append((module_name, u"install_exports: {}".format(
                    error)))
                continue

        java_map = getattr(module, "JAVA_MAP", None)
        if java_map is None:
            continue
        for java_name in java_map:
            provided[java_name] = module_name

    return provided, modules_loaded, failures


def is_excluded(java_name):
    for prefix in EXCLUDED_PREFIXES:
        if java_name.startswith(prefix):
            return True
    return False


def main():
    detail = "--detail" in sys.argv

    root = find_decompiled_root()
    if root is None:
        print(u"找不到反编译结果，请先运行：python dev/decompile_mod.py")
        return 1

    imports = collect_imports(root)
    provided, modules_loaded, failures = collect_provided()

    print(u"=" * 60)
    print(u">>> API 覆盖率")
    print(u"=" * 60)
    print(u"反编译目录: {}".format(root))
    print(u"Java import 种类: {}".format(len(imports)))
    print(u"核心包模块: {} 个已加载，共提供 {} 个 Java 名".format(
        len(modules_loaded), len(provided)))

    if failures:
        print(u"")
        print(u"  [严重] 以下模块无法加载，其 JAVA_MAP 未被计入：")
        for module_name, reason in failures:
            print(u"    {}: {}".format(module_name, reason))

    # 需要覆盖的：排除掉不该由核心包实现的命名空间
    needed = {}
    excluded = {}
    for java_name, count in imports.items():
        if is_excluded(java_name):
            excluded[java_name] = count
        else:
            needed[java_name] = count

    covered = {}
    skipped = {}
    missing = {}
    for java_name, count in needed.items():
        if java_name in provided:
            covered[java_name] = count
        elif java_name in DELIBERATELY_SKIPPED:
            skipped[java_name] = count
        else:
            missing[java_name] = count

    total = len(needed)
    covered_count = len(covered)
    skipped_count = len(skipped)
    missing_count = len(missing)

    print(u"")
    print(u"--- 统计 ---")
    print(u"  范围内需要覆盖: {} 种".format(total))
    print(u"  已提供:         {} 种 ({:.1f}%)".format(
        covered_count, 100.0 * covered_count / total if total else 0.0))
    print(u"  明确不做:       {} 种 ({:.1f}%)".format(
        skipped_count, 100.0 * skipped_count / total if total else 0.0))
    effective = covered_count + skipped_count
    print(u"  有效覆盖:       {} 种 ({:.1f}%)".format(
        effective, 100.0 * effective / total if total else 0.0))
    print(u"  仍缺:           {} 种".format(missing_count))
    print(u"")
    print(u"  （范围外未计入: {} 种 —— java.* / 渲染底层 / 第三方库）".format(
        len(excluded)))

    # 缺口中引用最多的就是下一步该做的
    print(u"")
    print(u"--- 缺口按引用次数排序（引用越多越该先做）---")
    limit = len(missing) if detail else 30
    for java_name, count in sorted(missing.items(),
                                   key=lambda item: (-item[1], item[0]))[:limit]:
        print(u"  {:>3} 个文件引用   {}".format(count, java_name))
    if not detail and len(missing) > limit:
        print(u"  …还有 {} 种（用 --detail 看全部）".format(len(missing) - limit))

    if skipped:
        print(u"")
        print(u"--- 明确不做的 ---")
        for java_name in sorted(skipped):
            print(u"  {}".format(java_name))
            print(u"      {}".format(DELIBERATELY_SKIPPED[java_name]))

    exit_code = 0
    if failures:
        print(u"")
        print(u"有模块加载失败，覆盖率不完整")
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

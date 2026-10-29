# -*- coding: utf-8 -*-
"""
把违反官方「mod 内不得使用中文文件名」的文件/目录改成英文名。

官方原文（见 ModSDK技术事实核查报告.md 第 78 行引的《Mod开发BUG解决方案》）：
    "mod 内不得使用中文文件名"

涉及的只有两处：
    core/接口.py        -> core/api.py
    未映射api/          -> unmapped/

**为什么必须改**：中文文件名不是"风格问题"，而是会导致打包/加载异常，
属于会直接让 mod 跑不起来的硬性违规。

本脚本会一并改掉所有**代码引用**（import 语句、模块名字符串、
测试里的加载路径、层目录清单）。散文/注释里的中文措辞不动 ——
那些是给人看的说明，不是标识符。

用法：
    python dev/rename_cjk_paths.py            # 只报告要改什么
    python dev/rename_cjk_paths.py --apply    # 实际改名
"""

import io
import os
import re
import sys

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)
SCRIPTS_ROOT = os.path.join(PACK_ROOT, "NeoForgeCoreScripts")
UNMAPPED_DIR = os.path.join(SCRIPTS_ROOT, u"未映射api")

# 需要重命名的路径（源 -> 目标），按「先文件后目录」的顺序处理
RENAMES = [
    (os.path.join(SCRIPTS_ROOT, "core", u"接口.py"),
     os.path.join(SCRIPTS_ROOT, "core", "api.py")),
    (UNMAPPED_DIR,
     os.path.join(SCRIPTS_ROOT, "unmapped")),
]

# 文本替换规则：只改**标识符位置**的引用，不动散文。
#
# 每条是 (正则, 替换)。这些模式都锚定在会真正参与 import / 加载的位置：
#   from 未映射api.x import ...      -> from unmapped.x import ...
#   pkg.load("未映射api.fallback")    -> pkg.load("unmapped.fallback")
#   "core.接口"                       -> "core.api"
#   u"未映射api"（层目录清单）          -> u"unmapped"
TEXT_RULES = [
    # 点分导入路径里的包名
    (re.compile(u'(from\\s+)未映射api(\\.)'), u'\\1unmapped\\2'),
    (re.compile(u'(import\\s+)未映射api(\\.|\\s|$)'), u'\\1unmapped\\2'),
    # 字符串字面量里的点分路径（pkg.load / 模块名列表 / clsPath）
    (re.compile(u'(["\'])未映射api\\.'), u'\\1unmapped.'),
    (re.compile(u'(["\'])未映射api(["\'])'), u'\\1unmapped\\2'),
    (re.compile(u'(["\'])core\\.接口'), u'\\1core.api'),
    # 层目录清单里的裸名字（dev/layers.py、harness.py）
    (re.compile(u'(u?)"未映射api"'), u'\\1"unmapped"'),
    (re.compile(u"(u?)'未映射api'"), u"\\1'unmapped'"),
    # 测试里的加载路径
    (re.compile(u'(["\'])core\\.接口(["\'])'), u'\\1core.api\\2'),
]

# 要扫描的文件后缀
SCAN_SUFFIXES = (".py", ".md")


def iter_text_files():
    """
    遍历工程里需要扫描的文本文件（跳过 __pycache__）。

    **必须跳过本脚本自己**：它正文里就写着那些待替换的模式
    （`未映射api` 等），不改的话会把自己的规则改坏，
    第二次运行就再也不匹配了。
    """
    self_path = os.path.abspath(__file__)
    for root in (SCRIPTS_ROOT, DEV_ROOT):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git")]
            for filename in sorted(filenames):
                if not filename.endswith(SCAN_SUFFIXES):
                    continue
                full = os.path.join(dirpath, filename)
                if os.path.abspath(full) == self_path:
                    continue
                yield full


def rewrite_text(path, apply_changes):
    """改写一个文件里的引用；返回改动条数。"""
    try:
        with io.open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
    except (IOError, OSError, UnicodeDecodeError):
        return 0

    new_source = source
    count = 0
    for pattern, replacement in TEXT_RULES:
        new_source, hits = pattern.subn(replacement, new_source)
        count += hits

    if count and apply_changes:
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(new_source)
    return count


def main():
    apply_changes = "--apply" in sys.argv

    # ---- 第一步：改文本引用 ----
    total_hits = 0
    touched = []
    for path in iter_text_files():
        hits = rewrite_text(path, apply_changes)
        if hits:
            total_hits += hits
            touched.append((os.path.relpath(path, PACK_ROOT), hits))

    if touched:
        verb = u"已改写" if apply_changes else u"将改写"
        print(u"{} {} 个文件，共 {} 处引用：".format(verb, len(touched),
                                                    total_hits))
        for relative, hits in touched:
            print(u"  {:>3} 处  {}".format(hits, relative))
    else:
        print(u"文本引用：无需改动")

    # ---- 第二步：改文件名 / 目录名 ----
    print()
    pending = []
    for source, target in RENAMES:
        if os.path.exists(source):
            pending.append((source, target))
        elif os.path.exists(target):
            print(u"  （已改名）{}".format(os.path.relpath(target, PACK_ROOT)))

    if not pending:
        print(u"路径重命名：无需改动")
        return 0

    for source, target in pending:
        kind = u"目录" if os.path.isdir(source) else u"文件"
        if apply_changes:
            os.rename(source, target)
            print(u"  已改名 {} {} -> {}".format(
                kind, os.path.relpath(source, PACK_ROOT),
                os.path.relpath(target, PACK_ROOT)))
        else:
            print(u"  将改名 {} {} -> {}".format(
                kind, os.path.relpath(source, PACK_ROOT),
                os.path.relpath(target, PACK_ROOT)))

    if not apply_changes:
        print()
        print(u"（加 --apply 生效）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

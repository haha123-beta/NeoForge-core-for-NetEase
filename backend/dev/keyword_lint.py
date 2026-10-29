# -*- coding: utf-8 -*-
"""
keyword_lint —— 找出「Java 方法名撞上 Python 关键字」的情况

为什么需要这个检查：
  Java 里 `itemStack.is(other)` 是完全合法的；翻译成 Python 后
  `itemStack.is(other)` 是**语法错误** —— 连解析都过不去，不是运行时问题。
  这类问题无法通过在函数体里写兼容代码绕过，只能在**命名层**解决。

实测踩到：`ItemStack.is(...)`（真实模组用了 20 次），
这也是 Python 2 与 Python 3 共有的限制（两个版本的关键字集合不同，
所以关键字表要把两边都收进来）。

本工具做两件事：
  1. 扫描反编译的 Java 源码，列出所有被调用的「关键字方法名」；
  2. 扫描核心包自己的源码，确认没有定义关键字方法名
     （定义了也没法调用，而且可能让整个模块解析失败）。
"""

import io
import keyword
import os
import re
import sys

# Python 2 与 Python 3 的关键字合集。
# 只取其中「可能当方法名」的那部分（True/False/None 之类不太可能，
# 但一并列出没有坏处，报出来才知道要不要处理）。
PY2_KEYWORDS = frozenset([
    "and", "as", "assert", "break", "class", "continue", "def", "del",
    "elif", "else", "except", "exec", "finally", "for", "from", "global",
    "if", "import", "in", "is", "lambda", "not", "or", "pass", "print",
    "raise", "return", "try", "while", "with", "yield",
])

PY3_ONLY_KEYWORDS = frozenset([
    "nonlocal", "async", "await", "False", "None", "True",
])

ALL_KEYWORDS = PY2_KEYWORDS | PY3_ONLY_KEYWORDS

# 明确「不构成问题」的名字：这些不会被当作方法调用，或者已经改名处理过。
# 每一项都要写清理由 —— 无声地豁免等于没有检查。
BENIGN = {
    "if": u"Java 里没有名为 if 的方法；出现在代码里必然不是方法调用",
    "for": u"同上",
    "while": u"同上",
    "new": u"不是 Python 关键字，Java 里也不是方法名",
}

# 已知的撞名方法及其处理方式：{Java 方法名: 核心包里的实现位置}
RENAMED = {
    "is": u"isItem / isBlock / isFluid（按类区分，见 core/keyword_renames.py；真实 28 处）",
    "pass": u"passResult（neoforge/common.py EventResult/TriState；真实 7 处）",
    "or": u"orShapes（minecraft/shapes.py Shapes；真实 4 处）",
    "not": u"notValue / notShapes（预留：Java 的 Predicate.not、Shapes.not）",
    "in": u"inValue（预留）",
    "and": u"andValue / andShapes（预留：Shapes.and）",
    "import": u"importValue（预留）",
    "print": u"printValue（预留）",
}

# 方法调用形态：`变量.方法名(` 或 `类.方法名(`
_CALL_RE = re.compile(r'\.\s*([a-zA-Z_]\w*)\s*\(')
# 方法定义形态（核心包自己的 Python 源码）
_DEF_RE = re.compile(r'^\s*def\s+([a-zA-Z_]\w*)\s*\(', re.MULTILINE)


def scan_java_for_keywords(root):
    """
    扫描 Java 源码里被调用的关键字方法名。

    返回 {方法名: [(文件名, 行号, 源码行)]}。
    """
    found = {}

    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            if not filename.endswith(".java"):
                continue
            path = os.path.join(dirpath, filename)
            text = io.open(path, "r", encoding="utf-8", errors="replace").read()
            for line_no, line in enumerate(text.split("\n"), 1):
                stripped = line.strip()
                # 跳过注释（CFR 的「Could not load」块里全是 import）
                if stripped.startswith("*") or stripped.startswith("//") \
                        or stripped.startswith("import "):
                    continue
                for match in _CALL_RE.finditer(line):
                    name = match.group(1)
                    if name in ALL_KEYWORDS and name not in BENIGN:
                        found.setdefault(name, []).append(
                            (filename, line_no, stripped[:100]))
    return found


def scan_python_for_keyword_defs(root):
    """
    扫描核心包 Python 源码里定义的函数名是否撞关键字。

    返回 [(相对路径, 行号, 名字)]。
    这种定义本身会让语法解析失败，所以能扫到就说明文件根本导入不了。
    """
    problems = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            text = io.open(path, "r", encoding="utf-8", errors="replace").read()
            for match in _DEF_RE.finditer(text):
                name = match.group(1)
                if name in ALL_KEYWORDS:
                    line_no = text.count("\n", 0, match.start()) + 1
                    problems.append((os.path.relpath(path, root), line_no, name))
    return problems


def main():
    dev_root = os.path.dirname(os.path.abspath(__file__))
    pack_root = os.path.dirname(dev_root)
    scripts_root = os.path.join(pack_root, "NeoForgeCoreScripts")

    # 反编译源码在 AddOn/refs/decompiled/ 下（核心包的上上层）
    addon_root = os.path.dirname(os.path.dirname(pack_root))
    decompiled_root = os.path.join(addon_root, "refs", "decompiled")

    print(u"=" * 60)
    print(u">>> Java 方法名与 Python 关键字的冲突扫描")
    print(u"=" * 60)
    print(u"（Python 2 关键字 {} 个 + Python 3 独有 {} 个，共 {} 个）".format(
        len(PY2_KEYWORDS), len(PY3_ONLY_KEYWORDS), len(ALL_KEYWORDS)))

    exit_code = 0

    # ---- 1. 核心包自己不能定义关键字方法名 ----
    print(u"")
    print(u"--- 核心包 Python 源码 ---")
    defs = scan_python_for_keyword_defs(scripts_root)
    if defs:
        print(u"  [严重] 定义了关键字方法名（本文件无法被解析）：")
        for rel, line_no, name in defs:
            print(u"    {}:{}  def {}(".format(rel, line_no, name))
        exit_code = 1
    else:
        print(u"  未定义任何关键字方法名")

    # ---- 2. 反编译源码里的关键字方法调用 ----
    print(u"")
    if not os.path.isdir(decompiled_root):
        print(u"  未找到反编译源码目录：{}".format(decompiled_root))
        print(u"  跳过（先跑 dev/decompile_mod.py）")
        return exit_code

    print(u"--- 反编译 Java 源码里被调用的关键字方法名 ---")
    found = scan_java_for_keywords(decompiled_root)

    if not found:
        print(u"  没有发现关键字方法调用")
        return exit_code

    for name in sorted(found, key=lambda n: -len(found[n])):
        entries = found[name]
        handled = RENAMED.get(name)
        marker = u"[已处理]" if handled else u"[待处理]"
        print(u"  {} .{}()  共 {} 处".format(marker, name, len(entries)))
        if handled:
            print(u"        处理方式: {}".format(handled))
        else:
            print(u"        处理方式: **未定** —— 翻译后会是语法错误，必须先改名")
        for filename, line_no, snippet in entries[:3]:
            print(u"        {}:{}  {}".format(filename, line_no, snippet))
        if len(entries) > 3:
            print(u"        …还有 {} 处".format(len(entries) - 3))

    unhandled = [n for n in found if n not in RENAMED]
    print(u"")
    if unhandled:
        print(u"有 {} 个关键字方法名尚未处理：{}".format(
            len(unhandled), u"、".join(sorted(unhandled))))
        print(u"这些方法在 Python 里无法用 `obj.名字(...)` 调用，")
        print(u"必须在核心包里改名，并在翻译层做映射。")
        return 1

    print(u"所有发现的关键字方法名都已有对应处理")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

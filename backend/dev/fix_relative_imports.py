# -*- coding: utf-8 -*-
"""
把 neoforge/event/ 包内所有相对导入改成绝对导入。

为什么必须改
------------
harness 的 compile_module 会把 Py2 源码**转译后**再编译，
但**相对导入（from .x import / from ..x import）走的是真 import 机制**，
绕过转译器直接读 Py2 源码 —— 遇到 `except Foo, e:` 立刻 SyntaxError。
compile_module 的文档早就写了「新代码请用绝对导入」，这次踩到了。

绝对导入（`from neoforge.event.base import ...`）会被 harness 的
依赖预加载捕获，走转译路径，所以是安全的。

用法：
    python dev/fix_relative_imports.py            # 只报告
    python dev/fix_relative_imports.py --apply    # 实际改写
"""

import io
import os
import re
import sys

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)
SCRIPTS_ROOT = os.path.join(PACK_ROOT, "NeoForgeCoreScripts")

# from .x import / from ..x import / from . import
REL_IMPORT = re.compile(r'^(\s*)from (\.+)([\w\.]*)\s+import', re.MULTILINE)


def package_of(path):
    """算出这个文件所属包的点分名。"""
    rel = os.path.relpath(path, SCRIPTS_ROOT).replace(os.sep, "/")
    if rel.endswith("/__init__.py"):
        rel = rel[:-len("/__init__.py")]
    else:
        rel = rel.rsplit("/", 1)[0]
    return rel.replace("/", ".")


def rewrite_source(path, source):
    """返回改写后的源码（不改动则原样返回）。"""
    package = package_of(path)

    def fix(match):
        indent, dots, module = match.group(1), match.group(2), match.group(3)
        levels = len(dots)
        parts = package.split(".")
        # 一个点 = 当前包；两个点 = 上一级
        keep = max(1, len(parts) - (levels - 1))
        prefix = ".".join(parts[:keep])
        target = prefix + ("." + module if module else "")
        return u"{}from {} import".format(indent, target)

    return REL_IMPORT.sub(fix, source)


def main():
    apply_changes = "--apply" in sys.argv
    target_root = (sys.argv[sys.argv.index("--root") + 1]
                   if "--root" in sys.argv
                   else os.path.join(SCRIPTS_ROOT, "neoforge", "event"))

    if not os.path.isdir(target_root):
        print(u"目录不存在: {}".format(target_root))
        return 1

    changed = []
    for dirpath, dirnames, filenames in os.walk(target_root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with io.open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            new_source = rewrite_source(path, source)
            if new_source == source:
                continue
            changed.append(os.path.relpath(path, SCRIPTS_ROOT))
            if apply_changes:
                with io.open(path, "w", encoding="utf-8") as handle:
                    handle.write(new_source)

    if not changed:
        print(u"没有需要改写的文件")
        return 0

    header = u"已改写" if apply_changes else u"需要改写（加 --apply 生效）"
    print(u"{} {} 个文件：".format(header, len(changed)))
    for item in changed:
        print(u"  {}".format(item))
    return 0


if __name__ == "__main__":
    sys.exit(main())

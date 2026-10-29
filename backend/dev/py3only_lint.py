# -*- coding: utf-8 -*-
"""
py3only_lint —— 扫描核心包源码里「Python 2 跑不了」的写法

背景
----
游戏内 ModSDK 是 Python 2.7，本机是 Python 3。我的自测流程是
「Py2 源码 -> 转译成 Py3 -> 在本机跑」，方向是 Py2 到 Py3，
所以本机测试全绿**不能**证明游戏里能加载。

已纠正：except Exception as error 是 Python 2.7 与 Python 3 共有语法。
官方依据：https://github.com/python/cpython/blob/2.7/Grammar/Grammar
不得再把 except-as 判为 Py3 专有语法。

为什么不直接用语法分析器
------------------------
试过两条路，都不可靠：
  1. lib2to3 的 python_grammar —— 在 Python 3.10+ 上是**混合语法表**，
     Py2/Py3 写法都收（实测 f-string、keyword-only
     参数全部通过），拿它做版本判别等于没查；
  2. typed_ast / typed-ast —— 需要第三方包，本机与游戏环境都没有。
本机也没有任何 Python 2 解释器可以直接编译验证。

所以本模块只是一道**启发式防线**，不是权威结论：
它把已知的 Py3 专有写法揪出来给人看，漏报是可能的。
核心代码因此遵守一条编码约定：
    **只用 Python 2 与 Python 3 语义完全一致的那部分语法。**
"""

import os
import re
import sys


# 每条规则：(规则名, 正则, 说明)
# 正则故意写得偏严 —— 宁可多报一条让人看一眼，也不要漏掉真问题。
_RULES = [
    (
        u"f-string",
        # 前面必须是行首或非标识符字符，避免把 `xxf"..."` 这种误判
        re.compile(r'(?:^|[^A-Za-z0-9_.])[fF](?=["\'])'),
        u"f-string 是 Py3.6+ 语法",
    ),
    (
        u"keyword-only",
        re.compile(r'def[ \t]+\w+[ \t]*\([^)\n]*\*[ \t]*,[ \t]*\w'),
        u"keyword-only 参数（* 后面接逗号再接参数名）是 Py3 语法",
    ),
    (
        u"yield-from",
        re.compile(r'^[ \t]*yield[ \t]+from\b', re.MULTILINE),
        u"yield from 是 Py3 语法",
    ),
    (
        u"nonlocal",
        re.compile(r'^[ \t]*nonlocal[ \t]+\w+', re.MULTILINE),
        u"nonlocal 是 Py3 语法",
    ),
    (
        u"async-def",
        re.compile(r'^[ \t]*async[ \t]+(def|with|for)\b', re.MULTILINE),
        u"async/await 是 Py3.5+ 语法",
    ),
    (
        u"annotations",
        re.compile(r'^[ \t]*(def[ \t]+\w+[ \t]*\([^)\n]*\)[ \t]*->|def[ \t]+\w+[ \t]*\([^)\n]*:\s*\w+\s*[,)])',
                   re.MULTILINE),
        u"函数注解（-> 或参数带类型）是 Py3 语法",
    ),
    (
        u"raise-from",
        re.compile(r'^[ \t]*raise\b[^\n]*\bfrom\b', re.MULTILINE),
        u"raise ... from ... 是 Py3 语法",
    ),
    (
        u"py3-metaclass",
        re.compile(r'class[ \t]+\w+[ \t]*\([^)\n]*metaclass[ \t]*='),
        u"class 的 metaclass= 关键字是 Py3 语法",
    ),
    (
        u"starred-assignment",
        re.compile(r'^[ \t]*\*[ \t]*\w+[ \t]*,[^\n=]*=', re.MULTILINE),
        u"星号解包赋值是 Py3 语法",
    ),
    (
        u"print-stmt-guard",
        re.compile(r'^[ \t]*print[ \t]+(?!\()\S', re.MULTILINE),
        u"print 语句（而非函数调用）在 Py3 里是语法错误",
    ),
    (
        u"unicode-literal-prefix-ok",
        None,  # 占位：u"" 在 Py2/Py3 都合法，无需检查
        u"",
    ),
]


_SKIP_DIRS = (".cache", "__pycache__", ".git")


def _strip_strings(source):
    """
    把字符串/字符字面量的**内容**替换成空格，但**保留引号本身**。

    为什么要保留引号：
      f-string 的特征恰恰是「f 紧贴引号」（f"..."）。
      如果把引号也一起抹掉，`x = f"{a}"` 会被抹成 `x =   {a} `，
      前缀 f 就再也认不出来了 —— 这是个真实的漏报，踩过一次。

    只做单行判断，不求完备 —— 这是启发式扫描，不是解析器。
    """
    out = []
    for line in source.split(u"\n"):
        quote = None
        result = []
        index = 0
        length = len(line)
        while index < length:
            char = line[index]
            if quote:
                if char == u"\\":
                    result.append(u"  ")
                    index += 2
                    continue
                if char == quote:
                    quote = None
                    result.append(char)   # 保留收尾引号
                else:
                    result.append(u" ")
            elif char in (u'"', u"'"):
                quote = char
                result.append(char)       # 保留起始引号
            else:
                result.append(char)
            index += 1
        out.append(u"".join(result))
    return u"\n".join(out)


def check_source(source, filename=u"<memory>"):
    """
    检查一段源码，返回命中的问题列表。

    每项形如 (行号, 规则名, 说明, 原始行内容)。
    """
    if isinstance(source, bytes):
        source = source.decode("utf-8")

    normalized = source.replace(u"\r\n", u"\n").replace(u"\r", u"\n")
    # 注释与字符串不参与匹配：先按行去掉注释行，再屏蔽字符串内容
    kept_lines = []
    for line in normalized.split(u"\n"):
        stripped = line.strip()
        kept_lines.append(u"" if stripped.startswith(u"#") else line)
    masked = _strip_strings(u"\n".join(kept_lines))

    original_lines = normalized.split(u"\n")
    problems = []

    for name, pattern, description in _RULES:
        if pattern is None:
            continue
        for match in pattern.finditer(masked):
            line_no = masked.count(u"\n", 0, match.start()) + 1
            original = original_lines[line_no - 1].strip() if line_no <= len(original_lines) else u""
            problems.append((filename, line_no, name, description, original))

    return problems


def check_file(path):
    """检查单个文件，返回问题列表。"""
    try:
        with open(path, "rb") as fp:
            raw = fp.read()
    except IOError:
        return []
    return check_source(raw, os.path.basename(path))


def check_tree(pack_root, layer_dirs):
    """检查整个核心包，返回 (检查文件数, 问题列表)。"""
    checked = 0
    problems = []

    for layer in layer_dirs:
        layer_path = os.path.join(pack_root, *layer.split("/"))
        if not os.path.isdir(layer_path):
            continue

        for root, dirs, files in os.walk(layer_path):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
            for filename in sorted(files):
                if not filename.endswith(".py"):
                    continue
                checked += 1
                problems.extend(check_file(os.path.join(root, filename)))

    # 包根目录直接放置的 .py 也必须检查。
    # 尤其是入口 modMain.py —— 它是游戏加载的第一个文件，
    # 漏检它等于漏检最要命的一处（曾因只查各层目录而漏掉它）。
    if os.path.isdir(pack_root):
        for filename in sorted(os.listdir(pack_root)):
            full = os.path.join(pack_root, filename)
            if filename.endswith(".py") and os.path.isfile(full):
                checked += 1
                problems.extend(check_file(full))

    return checked, problems


def main():
    # 源码根 = 脚本文件夹（官方要求脚本放在 Scripts 子文件夹下）
    dev_root = os.path.dirname(os.path.abspath(__file__))
    pack_root = os.path.dirname(dev_root)
    scripts_root = os.path.join(pack_root, "NeoForgeCoreScripts")
    if not os.path.isdir(scripts_root):
        scripts_root = pack_root

    # 分层目录的单一来源在 dev/layers.py，避免三处列表漂移导致漏检
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from layers import LAYER_DIRS as layers

    checked, problems = check_tree(scripts_root, layers)

    print(u"Py3 专有写法扫描：检查了 {} 个文件".format(checked))
    print(u"（启发式检查，非权威结论；目的是挡住 f-string 等已知不兼容语法）")

    if problems:
        print(u"")
        for filename, line_no, name, description, original in problems:
            print(u"  [命中] {}:{} [{}]".format(filename, line_no, name))
            print(u"         {}".format(description))
            print(u"         源码: {}".format(original))
        print(u"")
        print(u"共 {} 处需要人工确认".format(len(problems)))
        return 1

    print(u"未发现已知的 Py3 专有写法")
    return 0


if __name__ == "__main__":
    sys.exit(main())

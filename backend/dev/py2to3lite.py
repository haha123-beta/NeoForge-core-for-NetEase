# -*- coding: utf-8 -*-
"""
py2to3lite —— 极简 Python 2 源码适配器（仅用于本机自测）

背景
----
网易我的世界 ModSDK 运行的是 Python 2.7，所以核心包（behavior_pack_7k1k1i4l）
里的代码全部用 Python 2 语法编写，例如：

    except ImportError, e:      # Py2 专有
    d.iteritems()               # Py2 专有

而本机的验证环境是 Python 3，无法直接 import 这些文件。
本模块在**内存中**把 Py2 源码做最小改写后送进 compile()，
从而让同一份源码既能被游戏加载，也能在本机被测试。

它只处理核心包实际用到的少数几个 Py2 特性，
不追求完整、不做 AST 级重写，遇到不认识的写法就报错，绝不静默猜。

重要
----
本文件只服务于 `dev/` 下的自测脚本，**不要**被游戏引用。
"""

import __future__
import os
import re


class Py2To3Error(Exception):
    """源码里出现了适配器不认识、且确定无法在 Py3 下解析的写法。"""
    pass


# ============================================================
# 静态检查：这些写法只存在于 Python 2，必须点名报错
# ============================================================

# `print u"..."` / `print "..."` 这种 Py2 语句在 Py3 下是语法错误。
# 核心包的新代码一律要求写 print(...) 函数形式，
# alpha_neoforge.py 里的旧代码用管道写法 print(u"...".format(x)) 是合法的，
# 这里只拦「print 不是函数调用」的形式。
_PRINT_STMT = re.compile(r'^[ \t]*print[ \t]+(?!\()(?P<rest>\S.*)$', re.MULTILINE)


def _check_no_py2_only_syntax(source, filename):
    """点名报告无法机械改写的 Py2 专有语法。"""
    problems = []

    for match in _PRINT_STMT.finditer(source):
        line_no = source.count("\n", 0, match.start()) + 1
        problems.append(
            u"第 {} 行用了 Py2 的 print 语句，请改成 print(...) 函数调用：{}"
            .format(line_no, match.group("rest").strip())
        )

    if problems:
        raise Py2To3Error(
            u"{} 无法在 Python 3 下解析：\n  - {}".format(filename, u"\n  - ".join(problems))
        )


# ============================================================
# 机械改写：Py2 与 Py3 语义等价的常见写法
# ============================================================

# except Foo, e:   ->  except Foo as e:
#
# 注意负向前瞻 (?!as\b)：必须排除 Py2/Py3 都合法的
# `except Foo as e:`，否则会把正确的写法改坏成
# `except Foo as as e:`。
_EXCEPT_AS = re.compile(
    r'^([ \t]*)except([ \t]+)(.+?),(?!as\b)([ \t]*)(\w+)[ \t]*:',
    re.MULTILINE,
)

# x.iteritems() 等 ->  x.items() 等
_ITER_METHODS = re.compile(r'\.(iteritems|itervalues|iterkeys)\(\)')

_ITER_RENAMES = {
    "iteritems": "items",
    "itervalues": "values",
    "iterkeys": "keys",
}


def _rewrite(source):
    """对源码做与语义等价的机械化改写，返回 Py3 可编译的源码。"""
    source = _EXCEPT_AS.sub(r'\1except\2\3 as \5:', source)

    source = _ITER_METHODS.sub(
        lambda match: u".{}()".format(_ITER_RENAMES[match.group(1)]),
        source,
    )

    return source


# ============================================================
# 对外接口
# ============================================================

def adapt_source(source, filename=u"<memory>"):
    """把一段 Py2 源码改写为 Py3 可编译的源码。"""
    if isinstance(source, bytes):
        source = source.decode("utf-8-sig")
    # A leading BOM is an encoding signature, not a source character.
    # Text callers may already have decoded UTF-8 without removing it.
    if source.startswith(u"\ufeff"):
        source = source[1:]
    _check_no_py2_only_syntax(source, filename)
    return _rewrite(source)


def compile_module(path, module_name, register_in_sys_modules=True,
                   module=None):
    """
    把磁盘上的 Py2 文件编译成 Py3 模块对象。

    path               源码路径
    module_name        模块名（决定它在 sys.modules 里的键）
    register_in_sys_modules
                       True 时写入 sys.modules，使 `import module_name` 可用。
                       注意：Py3 真实模块的包内相对导入（from .x import y）
                       无法指向这些伪造模块，因此新代码请用绝对导入。
    module             复用一个既有的模块对象（例如 `_ensure_package`
                       造的包空壳）。**必须复用而不是新建** ——
                       `sys.modules[name]` 是别人拿着的引用，
                       换成新对象会让两边分叉（见 harness 里的说明）。
    """
    import os
    import sys
    import types

    path = os.path.abspath(path)
    with open(path, "rb") as fp:
        raw = fp.read()

    adapted = adapt_source(raw, filename=os.path.basename(path))

    if module is None:
        module = types.ModuleType(module_name)
    else:
        # 复用既有模块对象时，**只清掉它自己的内容，保留 dunder**。
        #
        # 不能直接 `module.__dict__.clear()`：那会把 `__spec__` / `__loader__`
        # 一起清掉，之后 Python 的 import 机制在给父包挂子模块时
        # 会报 `module has no attribute '__spec__'`（实测踩到，
        # 一次挂了 18 个测试文件）。
        keep = {}
        for key in module.__dict__:
            if key.startswith("__") and key.endswith("__"):
                keep[key] = module.__dict__[key]
        module.__dict__.clear()
        module.__dict__.update(keep)

    module.__file__ = path
    module.__name__ = module_name
    # 包的 __init__.py 必须带 __path__，否则 Python 不认为它是包，
    # 里面的 `from .base import ...`（相对导入）会失败
    # （实测报 "No module named 'neoforge.event.base';
    #   'neoforge.event' is not a package"）。
    if os.path.basename(path) == "__init__.py":
        module.__path__ = [os.path.dirname(path)]
        module.__package__ = module_name
    else:
        parent = module_name.rsplit(".", 1)[0] if "." in module_name else ""
        module.__package__ = parent
    if register_in_sys_modules:
        sys.modules[module_name] = module

    try:
        code = compile(adapted, path, "exec", dont_inherit=True)
    except SyntaxError as exc:
        # 兜底：把改写后的源码落盘，便于定位
        raise Py2To3Error(
            u"改写后仍在第 {} 行解析失败：{}\n（源文件：{}）".format(exc.lineno, exc.msg, path)
        )

    # __future__ 特性：让 print_function / absolute_import / unicode_literals 生效
    code = compile(
        adapted,
        path,
        "exec",
        flags=__future__.print_function.compiler_flag
        | __future__.absolute_import.compiler_flag
        | __future__.unicode_literals.compiler_flag,
        dont_inherit=True,
    )

    exec(code, module.__dict__)
    return module

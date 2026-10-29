# -*- coding: utf-8 -*-
# alpha_neoforge.py
# NeoForge 核心包 - α 层：模组发现
#
# 只负责三件事：
#   1. 解析 neoforge.mods.toml（不引入第三方 TOML 库，纯正则 + 逐行）
#   2. 在 resources 目录里递归找到模组包
#   3. 把解析结果登记到全局注册表，供后续层使用
#
# 本层不做任何游戏 API 调用，因此可以脱离游戏单独自测。

from __future__ import print_function
from __future__ import absolute_import

import io
import json
import os
import re


# ============================================================
# 1. 全局存储
# ============================================================

_registered_modpacks = {}


# ============================================================
# 2. 错误码
# ============================================================

ERR_BAD_PATH = u"bad_path"        # 路径不存在或不是目录
ERR_NO_TOML = u"no_toml"          # 没找到 neoforge.mods.toml
ERR_BAD_TOML = u"bad_toml"        # 找到了但读不动
ERR_NO_MOD_ID = u"no_mod_id"      # 读到了但没有 modId

ERR_MESSAGES = {
    ERR_BAD_PATH: u"路径不存在或不是目录",
    ERR_NO_TOML: u"未找到 neoforge.mods.toml",
    ERR_BAD_TOML: u"neoforge.mods.toml 读取失败",
    ERR_NO_MOD_ID: u"neoforge.mods.toml 中未声明 modId",
}


# ============================================================
# 3. TOML 解析
# ============================================================
#
# 为什么不用第三方 toml 库：网易 ModSDK 只保证标准库，
# 多一个依赖就多一个装不上的风险。neoforge.mods.toml 用到的
# TOML 子集很小，手写解析器足够，且解析逻辑可被自测完全覆盖。
#
# 支持：
#   - [table] / [[array-of-tables]] 节
#   - 基础字符串 "..."（含 \n \t \" \\ 转义）与字面字符串 '...'
#   - 多行字符串 """...""" 与 '''...'''（真实模组的 description 就长这样）
#   - 整数、浮点、布尔、内联数组
#   - 点号键（如 neoforge.mods.toml 里偶尔出现的 a.b = 1）
#   - # 注释（含行尾注释，但字符串内的 # 不会被误伤）

_SECTION_RE = re.compile(r'^\[\[?\s*([^\]\s]+)\s*\]\]?$')
_KEY_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.\-]*$')

_INT_RE = re.compile(r'^[+-]?\d+$')
_FLOAT_RE = re.compile(r'^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$')

# 单引号 / 双引号内的转义
_ESCAPES = {
    "n": u"\n", "t": u"\t", "r": u"\r",
    '"': u'"', "'": u"'", "\\": u"\\",
}

# TOML 的 \uXXXX 转义。
#
# 注意：解码码位时 Py2 要用 unichr()、Py3 要用 chr()，
# 而 `if PY2: unichr` 这种写法在 Py2 下解析没问题、在 Py3 下会因为
# 引用了不存在的名字而报错。这里改用**只依赖两版共有函数**的写法：
# chr() 在 Py2 对 >255 的码位会抛异常，而那正是 ASCII 之外的字符 ——
# 抛异常时回退到一个纯 ASCII 表示，代价是极少见的转义字符显示不完美，
# 但绝不会让整个模块加载失败。
def _code_point_to_char(code):
    try:
        return chr(code)
    except (ValueError, OverflowError):
        return u"\\u{:04x}".format(code)


def _unescape(text):
    """处理双引号字符串里的转义序列。"""
    def replace_unicode(match):
        try:
            code = int(match.group(1), 16)
        except ValueError:
            return match.group(0)
        return _code_point_to_char(code)

    text = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, text)

    out = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == u"\\" and index + 1 < length:
            nxt = text[index + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                index += 2
                continue
        out.append(char)
        index += 1
    return u"".join(out)


def _try_decode_multiline(opening, lines, line_index, quote):
    """
    解析一个多行字符串。

    opening     `=` 之后、这一行剩余的值文本，例如 "'''" 或 "'''inline"
    lines       全部行
    line_index  opening 所在的行号
    quote       引号字符，' 或 "

    返回 (值, 下一行下标)。

    不变量：返回的下标**一定大于** line_index。
    调用方靠这个不变量推进主循环，一旦返回原地就会死循环，
    所以宁可多跳一行，也不能原地返回。
    """
    marker = quote * 3
    floor = line_index + 1

    # 单行形式：'''text'''
    if opening.endswith(marker) and len(opening) >= 6:
        return opening[3:-3], floor

    parts = []
    rest = opening[3:]
    if rest:
        parts.append(rest)

    cursor = floor
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        if stripped.endswith(marker):
            body = lines[cursor].rstrip()
            parts.append(body[:-3])
            return u"\n".join(parts), cursor + 1
        parts.append(lines[cursor])
        cursor += 1

    # 没有闭合标记：把剩下的都当内容，交给上层记一条解析问题
    return u"\n".join(parts), max(cursor, floor)


def _has_closing_marker(opening, lines, line_index, quote):
    """判断多行字符串是否闭合（仅用于记一条解析问题，不参与取值）。"""
    marker = quote * 3
    if opening.endswith(marker) and len(opening) >= 6:
        return True
    cursor = line_index + 1
    while cursor < len(lines):
        if lines[cursor].strip().endswith(marker):
            return True
        cursor += 1
    return False


def _strip_inline_comment(text):
    """
    去掉行尾注释。

    引号内的 # 不算注释；双引号内的转义 \\" 也不算字符串结束。
    注意：不认识 TOML 的 ''' / \"\"\" 多行标记 —— 那是值的性质，
    由调用方通过 find 定位多行标记来避开，不靠本函数。
    """
    quote = None
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if quote:
            if char == u"\\" and quote == u'"':
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in (u'"', u"'"):
            quote = char
        elif char == u"#":
            return text[:index].rstrip()
        index += 1
    return text.rstrip()


def _value_text(text):
    """
    从 `key = value` 这一行里取出值的文本。

    先剥行尾注释再取，这样 `modId="x" # 注释` 与
    `type="required" #mandatory` 都能正确解析。
    """
    equals_pos = text.find(u"=")
    if equals_pos < 0:
        return u""
    value = _strip_inline_comment(text[equals_pos + 1:])
    return value.strip()


def _strip_quotes(text):
    """去掉一层引号，双引号处理转义，单引号原样保留。"""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1]:
        if text[0] == u'"':
            return _unescape(text[1:-1])
        if text[0] == u"'":
            return text[1:-1]
    return text


def _parse_scalar(text):
    """把 TOML 值文本转成 Python 值。"""
    text = text.strip()
    if not text:
        return u""

    if len(text) >= 2 and text[0] == text[-1] and text[0] in (u'"', u"'"):
        return _strip_quotes(text)

    if text.startswith(u"[") and text.endswith(u"]"):
        return _split_array(text[1:-1])

    lowered = text.lower()
    if lowered == u"true":
        return True
    if lowered == u"false":
        return False

    if _INT_RE.match(text):
        try:
            return int(text)
        except ValueError:
            return text

    if _FLOAT_RE.match(text):
        try:
            return float(text)
        except ValueError:
            return text

    return text


def _split_array(body):
    """切分内联数组，逗号在引号内的不切。"""
    items = []
    current = []
    quote = None
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if quote:
            current.append(char)
            if char == u"\\" and quote == u'"' and index + 1 < length:
                current.append(body[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in (u'"', u"'"):
            quote = char
            current.append(char)
        elif char == u",":
            items.append(u"".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1

    tail = u"".join(current).strip()
    if tail:
        items.append(tail)

    return [_parse_scalar(item) for item in items if item != u""]


def _as_text(value):
    """把解析出的值统一成文本，供 modId 等字段使用。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return u"true" if value else u"false"
    return u"{}".format(value)


def _split_authors(value):
    """authors 既可能是逗号分隔的字符串，也可能是数组。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [u"{}".format(item).strip() for item in value if u"{}".format(item).strip()]
    return [part.strip() for part in u"{}".format(value).split(u",") if part.strip()]


def read_text_file(path):
    """
    按 UTF-8 读取文本文件。

    必须显式指定编码：中文 Windows 上 open() 默认走 GBK，
    而 neoforge.mods.toml 是 UTF-8（description 里常有中文），
    用默认编码读会直接乱码。

    读不动时回退到 latin-1 —— 它不会抛异常，
    至少能把 modId 这类纯 ASCII 字段取出来，
    总比整个模组包因为一个中文描述而加载失败强。
    """
    try:
        with io.open(path, "r", encoding="utf-8") as fp:
            return fp.read()
    except UnicodeDecodeError:
        with io.open(path, "r", encoding="latin-1") as fp:
            return fp.read()


def parse_toml(content):
    """
    解析 neoforge.mods.toml 内容。

    返回字典：
        modId / version / displayName / description / license  —— 顶层字段，可能为 None
        authors                                                —— 列表，可能为空
        mods                                                   —— [[mods]] 块列表
        tomlModIds                                             —— 各 [[mods]] 块的 modId（保序）
        errors                                                 —— 解析过程中发现的问题（字符串列表）

    注意：真实模组包会把 modId / version / displayName / description
    写在 [[mods]] 块里，顶层往往是空的。因此下面的 modId 等字段
    在「顶层没有、块里有」时会从第一个块补齐，
    保证调用方读 result["modId"] 总能拿到东西。
    """
    result = {
        "modId": None,
        "version": None,
        "displayName": None,
        "description": None,
        "license": None,
        "authors": [],
        "mods": [],
        "dependencies": {},
        "mixins": [],
        "tomlModIds": [],
        "errors": [],
    }

    if content is None:
        result["errors"].append(u"内容为空")
        return result

    if isinstance(content, bytes):
        content = content.decode("utf-8", "replace")

    lines = content.splitlines()

    top = {}
    mods = []
    current = None      # None 表示在顶层，字典表示在某个 [[mods]] 块内
    cursor = 0

    while cursor < len(lines):
        trimmed = lines[cursor].strip()

        if not trimmed or trimmed.startswith(u"#"):
            cursor += 1
            continue

        # ---- 节头 ----
        # 先剥行尾注释：真实模组写的是 `[[mods]] #mandatory`，
        # 不剥就匹配不上节头，整个 [[mods]] 块会被无声跳过。
        if trimmed.startswith(u"["):
            header = _strip_inline_comment(trimmed)
            section = _SECTION_RE.match(header)
            if section:
                name = section.group(1)
                if header.startswith(u"[[") and name == u"mods":
                    # 只有 [[mods]] 才是模组声明块。
                    # 真实模组包末尾还有 [[dependencies.<modid>]]，
                    # 不按名字判断就会把它也当成模组块，modId 会变成依赖名。
                    block = {}
                    mods.append(block)
                    current = block
                elif header.startswith(u"[[") and name == u"mixins":
                    current = {}
                    result["mixins"].append(current)
                elif header.startswith(u"[[") and name.startswith(u"dependencies."):
                    owner = name[len(u"dependencies."):]
                    current = {}
                    result["dependencies"].setdefault(owner, []).append(current)
                else:
                    # 其它节（[library]、[features.x]、[[dependencies.x]]…）
                    # 其下的键归自己那一节，不进顶层，也不进模组块
                    current = None
                cursor += 1
                continue
            result["errors"].append(
                u"第 {} 行节头写法无法识别: {}".format(cursor + 1, trimmed)
            )
            cursor += 1
            continue

        # ---- key = value ----
        # 先切出 `=` 左边当键名，再交给正则校验，
        # 比「用正则吞整行」抗造：值里带引号、方括号、# 都不会让匹配整体失败。
        eq_index = trimmed.find(u"=")
        if eq_index <= 0:
            result["errors"].append(
                u"第 {} 行不是合法的 key = value: {}".format(cursor + 1, trimmed)
            )
            cursor += 1
            continue

        key = trimmed[:eq_index].strip()
        if not _KEY_NAME_RE.match(key):
            result["errors"].append(
                u"第 {} 行键名不合法: {}".format(cursor + 1, trimmed)
            )
            cursor += 1
            continue

        value_text = _value_text(trimmed)
        line_no = cursor
        target = current if current is not None else top

        # 多行字符串：值可能延续到后面若干行
        if value_text.startswith(u'"""') or value_text.startswith(u"'''"):
            value, next_cursor = _try_decode_multiline(
                value_text, lines, cursor, value_text[0])
            if next_cursor <= cursor:
                # 兜底：解析器必须向前推进，否则主循环会死循环
                next_cursor = cursor + 1
            cursor = next_cursor
            if not _has_closing_marker(value_text, lines, line_no, value_text[0]):
                result["errors"].append(
                    u"第 {} 行的多行字符串没有闭合标记".format(line_no + 1)
                )
        else:
            value = _parse_scalar(value_text)
            cursor += 1

        # 点号键在 TOML 里是嵌套表；这里只取最后一段，够用且不会丢值
        target[key.split(u".")[-1]] = value

    result["mods"] = mods

    # 合并优先级（从高到低）：
    #   1. [[mods]] 块   —— 模组自己的声明，最权威
    #   2. 顶层字段      —— 只在块里没写时补位
    #
    # 必须先把块的结果落进 result，再让顶层补空位。
    # 反过来的话，真实模组末尾的 [dependencies.<modid>] 节里也有 modId，
    # 它会先占住 modId，块就再也写不进去，modId 会变成依赖名 "minecraft"。
    for block in mods:
        if block.get("modId"):
            result["tomlModIds"].append(_as_text(block["modId"]))
        for key in ("modId", "version", "displayName", "description"):
            if result.get(key) is None and block.get(key) is not None:
                result[key] = block[key]

    for key, value in top.items():
        if key in result and result[key] is None:
            result[key] = value

    if not result["authors"]:
        # authors 可能写在顶层，也可能写在 [[mods]] 块里，两处都认
        if top.get("authors"):
            result["authors"] = top["authors"]
        else:
            for block in mods:
                if block.get("authors"):
                    result["authors"] = block["authors"]
                    break

    for key in ("modId", "version", "displayName", "description", "license"):
        if result[key] is not None:
            result[key] = _as_text(result[key])

    result["authors"] = _split_authors(result["authors"])

    return result


# ============================================================
# 4. 扫描 resources 文件夹（递归）
# ============================================================

def find_toml_path(resources_path):
    """
    在 resources_path 下递归查找 neoforge.mods.toml。

    返回 (toml_path, error_code)：
        找到    -> (路径, None)
        没找到  -> (None, ERR_BAD_PATH / ERR_NO_TOML)
    """
    if not resources_path:
        return None, ERR_BAD_PATH

    if not os.path.exists(resources_path):
        return None, ERR_BAD_PATH

    if not os.path.isdir(resources_path):
        return None, ERR_BAD_PATH

    for root, dirs, files in os.walk(resources_path):
        # 稳定顺序：同一目录里多变体时，结果不随文件系统顺序漂移
        dirs.sort()
        if "neoforge.mods.toml" in files:
            return os.path.join(root, "neoforge.mods.toml"), None

    return None, ERR_NO_TOML


def scan_resources_folder(resources_path):
    """
    递归扫描 resources 文件夹，解析出模组元数据。

    返回 (mod_info, error_code)：
        成功    -> (info 字典, None)
        失败    -> (None, 错误码)

    与旧版的关键差别：这里把「找不到 toml」和「找到了但没 modId」
    区分成两个错误码返回，而不是一律 None，否则调用方无从排查。
    """
    toml_path, error = find_toml_path(resources_path)
    if error:
        return None, error

    print(u"[NeoForge] 找到 neoforge.mods.toml: {}".format(toml_path))

    try:
        content = read_text_file(toml_path)
    except Exception as e:
        print(u"[NeoForge] 读取 toml 失败: {}".format(e))
        return None, ERR_BAD_TOML

    mod_info = parse_toml(content)

    # modId 以 [[mods]] 块为准；顶层 modId 只作为兜底
    toml_mod_ids = mod_info.get("tomlModIds") or []
    mod_id = mod_info.get("modId")
    if toml_mod_ids:
        mod_id = toml_mod_ids[0]
    if not mod_id:
        print(u"[NeoForge] toml 中未声明 modId: {}".format(toml_path))
        return None, ERR_NO_MOD_ID
    mod_info["modId"] = mod_id

    if len(toml_mod_ids) > 1:
        mod_info["errors"].append(
            u"声明了 {} 个模组，本次只加载第一个：{}".format(len(toml_mod_ids), mod_id)
        )

    mod_info["resourcesPath"] = resources_path
    mod_info["tomlPath"] = toml_path
    mod_info["packDir"] = os.path.dirname(os.path.dirname(toml_path))

    print(u"[NeoForge] 成功解析: {}".format(toml_path))
    print(u"[NeoForge]    模组 ID: {}".format(mod_id))
    print(u"[NeoForge]    版本: {}".format(mod_info.get("version") or u"未指定"))
    print(u"[NeoForge]    名称: {}".format(mod_info.get("displayName") or u"未指定"))

    return mod_info, None


# ============================================================
# 5. 注册模组包
# ============================================================

def _failure(error_code, resources_path, message=None):
    """构造统一的失败返回值。"""
    return {
        "success": False,
        "modId": None,
        "error": error_code,
        "message": message or ERR_MESSAGES.get(error_code, u"未知错误"),
        "path": resources_path,
        "info": None,
    }


def register_modpack(resources_path):
    """
    对外公开的注册接口。

    返回字典：
        success  布尔
        modId    成功时的模组 ID
        error    失败时的错误码（见 ERR_*）
        message  人类可读的说明
        path     传入的路径（原样回传，便于调用方对应）
        info     成功时的完整元数据
    """
    print(u"[NeoForge] 收到注册请求: {}".format(resources_path))

    if not resources_path:
        return _failure(ERR_BAD_PATH, resources_path)

    mod_info, error = scan_resources_folder(resources_path)

    if error:
        return _failure(error, resources_path)

    mod_id = mod_info["modId"]

    if mod_id in _registered_modpacks:
        print(u"[NeoForge] 模组 '{}' 已存在，将被覆盖".format(mod_id))

    _registered_modpacks[mod_id] = mod_info

    print(u"\n[NeoForge] ======================================")
    print(u"[NeoForge] 模组注册成功！")
    print(u"[NeoForge]    ID: {}".format(mod_id))
    print(u"[NeoForge]    版本: {}".format(mod_info.get("version") or u"未指定"))
    print(u"[NeoForge]    名称: {}".format(mod_info.get("displayName") or u"未指定"))
    print(u"[NeoForge]    描述: {}".format(mod_info.get("description") or u"无描述"))
    print(u"[NeoForge]    作者: {}".format(u", ".join(mod_info.get("authors") or [u"未知"])))
    print(u"[NeoForge]    许可: {}".format(mod_info.get("license") or u"未指定"))
    print(u"[NeoForge]    路径: {}".format(mod_info.get("resourcesPath")))

    sub_mods = mod_info.get("mods") or []
    if len(sub_mods) > 1:
        print(u"[NeoForge]    子模组: {} 个".format(len(sub_mods)))
        index = 1
        for sub in sub_mods:
            name = sub.get("displayName") or sub.get("modId") or u"未命名"
            print(u"[NeoForge]      {}. {}".format(index, name))
            index += 1

    for warning in mod_info.get("errors") or []:
        print(u"[NeoForge]    注意: {}".format(warning))

    print(u"[NeoForge] ======================================\n")

    return {
        "success": True,
        "modId": mod_id,
        "error": None,
        "message": u"模组 '{}' 注册成功".format(mod_id),
        "path": resources_path,
        "info": mod_info,
    }


# ============================================================
# 6. 查询接口
# ============================================================

def get_registered_modpacks():
    """获取所有已注册的模组包（返回浅拷贝，外部改不动内部结构）。"""
    return _registered_modpacks.copy()


def find_modpack_by_id(mod_id):
    """根据模组 ID 查找已注册的模组信息。"""
    return _registered_modpacks.get(mod_id)


def list_all_modpacks():
    """在控制台列出所有已注册的模组包。"""
    if not _registered_modpacks:
        print(u"[NeoForge] 当前没有已注册的模组包")
        return

    print(u"\n[NeoForge] ======================================")
    print(u"[NeoForge] 已注册的模组包 (共 {} 个):".format(len(_registered_modpacks)))

    index = 1
    for mod_id in sorted(_registered_modpacks):
        info = _registered_modpacks[mod_id]
        print(u"[NeoForge] {}. {}".format(index, mod_id))
        print(u"[NeoForge]    版本: {}".format(info.get("version") or u"未指定"))
        print(u"[NeoForge]    名称: {}".format(info.get("displayName") or u"未指定"))
        index += 1

    print(u"[NeoForge] ======================================\n")


def get_mod_count():
    """已注册的模组数量。"""
    return len(_registered_modpacks)


def clear_registry():
    """清空注册表（自测与重载用）。"""
    _registered_modpacks.clear()


# ============================================================
# 7. 自测
# ============================================================

if __name__ == "__main__":
    print(u"\n[NeoForge] 自测模式")
    test_path = os.path.join(os.path.dirname(__file__), "..", "resources")
    test_path = os.path.normpath(test_path)
    print(u"[NeoForge] 测试路径: {}".format(test_path))
    result = register_modpack(test_path)
    print(u"\n[NeoForge] 注册结果: {}".format(result))
    list_all_modpacks()


def extracted_mod_index(folder, entrypoints, side="BOTH"):
    """Read an unpacked mod in place; entrypoints keep the original package paths."""
    folder = os.path.realpath(folder)
    path = os.path.join(folder, "META-INF", "neoforge.mods.toml")
    if not os.path.isfile(path):
        raise ValueError("Missing META-INF/neoforge.mods.toml in " + folder)
    metadata = parse_toml(read_text_file(path))
    if metadata["errors"]:
        raise ValueError("; ".join(metadata["errors"]))
    declared = metadata["mods"]
    ids = [row.get("modId") for row in declared]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Missing or duplicate mod IDs in folder metadata")
    if set(entrypoints) != set(ids):
        raise ValueError("Provide one entrypoint for every declared mod ID")
    issues = inspect_bytecode_requirements(folder, metadata)
    rows = []
    for mod in declared:
        mod_id = mod["modId"]
        rows.append({
            "mod_id": mod_id, "version": mod.get("version", ""),
            "entrypoint": entrypoints[mod_id], "source_folder": folder,
            "side": side, "requires": [],
            "dependency_constraints": metadata["dependencies"].get(mod_id, []),
            "compatibility_issues": issues,
        })
    return {"schema_version": 1, "mods": rows}


def inspect_bytecode_requirements(folder, metadata):
    """Conservative declaration detection, not proof that absent declarations mean compatible."""
    configs = set()
    issues = []
    for entry in metadata.get("mixins", []):
        config = entry.get("config")
        if not isinstance(config, type(u"")) and not isinstance(config, str):
            issues.append({"kind": "mixin", "source": "META-INF/neoforge.mods.toml",
                           "message": "Malformed Mixin config declaration"})
        elif config:
            configs.add(config)
        else:
            issues.append({"kind": "mixin", "source": "META-INF/neoforge.mods.toml",
                           "message": "Empty Mixin config declaration"})
    for root, directories, files in os.walk(folder):
        directories[:] = [name for name in directories if name != "__pycache__"]
        for filename in files:
            # Filename fallback is only a convention. Explicit TOML/manifest
            # declarations below/above remain authoritative for every filename.
            # In particular, recipe names containing "mixing" are not Mixins.
            if filename.lower().endswith(".json") and re.search(r"mixins?(?:[._-]|$)", filename.lower()[:-5]):
                configs.add(os.path.relpath(os.path.join(root, filename), folder).replace(os.sep, "/"))
    manifest = os.path.join(folder, "META-INF", "MANIFEST.MF")
    if os.path.isfile(manifest):
        # Manifest continuation lines start with a single space.
        text = read_text_file(manifest).replace("\r\n", "\n").replace("\n ", "")
        for line in text.splitlines():
            if line.lower().startswith("mixinconfigs:"):
                configs.update(value.strip() for value in line.split(":", 1)[1].split(",") if value.strip())
    for config in sorted(configs):
        target = os.path.realpath(os.path.join(folder, config))
        if not os.path.normcase(target).startswith(os.path.normcase(os.path.realpath(folder)) + os.sep):
            message = "Mixin config path escapes the content folder"
        elif not os.path.isfile(target):
            message = "Declared Mixin config is missing"
        else:
            try:
                payload = json.loads(read_text_file(target))
                if not isinstance(payload, dict):
                    raise ValueError("Expected a JSON object")
                message = "Mixin configuration requires an explicit port; JVM injection is unavailable"
            except Exception as error:
                message = "Unreadable Mixin configuration: " + str(error)
        issues.append({"kind": "mixin", "source": config, "message": message})
    services = os.path.join(folder, "META-INF", "services")
    for name in ("cpw.mods.modlauncher.serviceapi.ILaunchPluginService",
                 "cpw.mods.modlauncher.api.ITransformationService"):
        if os.path.isfile(os.path.join(services, name)):
            issues.append({"kind": "bytecode_transformer", "source": "META-INF/services/" + name,
                           "message": "JVM transformation service requires an explicit port"})
    return issues

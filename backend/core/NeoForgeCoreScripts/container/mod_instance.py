# -*- coding: utf-8 -*-
# container/mod_instance.py
# 运行时容器 - 模组实例
#
# 一个 ModInstance 代表「一个模组包在内存里的样子」：
# 它是谁（元数据）、它在哪（路径）、它的资源有哪些、它现在走到哪一步（状态）。
#
# 本层不碰游戏 API、不改磁盘，因此可以脱离游戏单独自测。
# 生命周期推进由 lifecycle.py 负责，这里只提供数据与状态。

from __future__ import print_function
from __future__ import absolute_import

import os


# ============================================================
# 状态
# ============================================================

class ModState(object):
    """模组实例的状态。取值是普通字符串，方便直接打印与比较。"""

    DISCOVERED = u"discovered"   # 已发现：元数据解析完成
    ACTIVATING = u"activating"   # 激活中：正在跑各阶段的校验
    LOADED = u"loaded"           # 已加载：各阶段都过了
    FAILED = u"failed"           # 失败：某个阶段判定为致命
    UNLOADED = u"unloaded"       # 已卸载：被显式清理

    NAMES = {
        DISCOVERED: u"已发现",
        ACTIVATING: u"激活中",
        LOADED: u"已加载",
        FAILED: u"失败",
        UNLOADED: u"已卸载",
    }

    @classmethod
    def describe(cls, state):
        return cls.NAMES.get(state, state)


class StageState(object):
    """单个阶段的执行结果。"""

    PENDING = u"pending"
    DONE = u"done"
    WARNED = u"warned"     # 有告警但仍算通过
    FAILED = u"failed"
    SKIPPED = u"skipped"

    NAMES = {
        PENDING: u"待执行",
        DONE: u"通过",
        WARNED: u"有告警",
        FAILED: u"失败",
        SKIPPED: u"跳过",
    }

    @classmethod
    def describe(cls, state):
        return cls.NAMES.get(state, state)


class StageRecord(object):
    """一个阶段的执行记录，用于诊断「到底卡在哪一步」。"""

    def __init__(self, key, title):
        self.key = key
        self.title = title
        self.state = StageState.PENDING
        self.messages = []

    def done(self, message=None):
        self.state = StageState.DONE
        if message:
            self.messages.append(message)
        return self

    def warn(self, message):
        if self.state != StageState.FAILED:
            self.state = StageState.WARNED
        self.messages.append(message)
        return self

    def fail(self, message):
        self.state = StageState.FAILED
        self.messages.append(message)
        return self

    def skip(self, message=None):
        self.state = StageState.SKIPPED
        if message:
            self.messages.append(message)
        return self

    @property
    def ok(self):
        """只要不是 FAILED，就算这一步过了。"""
        return self.state != StageState.FAILED

    def describe(self):
        text = u"{} [{}]".format(self.title, StageState.describe(self.state))
        if self.messages:
            text = u"{}: {}".format(text, u"; ".join(self.messages))
        return text


# ============================================================
# 资源清单
# ============================================================

# 模组包里这几类目录最关键，分开统计便于判断「能不能被引擎认出来」
RESOURCE_KINDS = (
    ("assets", u"资源（模型/贴图/语言）"),
    ("data", u"数据（配方/标签）"),
    ("META-INF", u"元数据（mods.toml）"),
    ("sen", u"代码（翻译后的 .py）"),
)

RESOURCE_KIND_LABELS = dict(RESOURCE_KINDS)


class ResourceIndex(object):
    """模组包里的文件清单。只读，不修改任何东西。"""

    def __init__(self):
        self.by_kind = {}      # 顶层目录名 -> 文件数
        self.extensions = {}   # 扩展名 -> 文件数
        self.total_files = 0
        self.missing_kinds = []

    def count(self, kind):
        return self.by_kind.get(kind, 0)

    def has(self, kind):
        return self.by_kind.get(kind, 0) > 0

    def describe(self):
        parts = []
        for kind, label in RESOURCE_KINDS:
            parts.append(u"{} {} 个".format(label, self.count(kind)))
        return u"，".join(parts)

    def summary_lines(self):
        lines = [u"共 {} 个文件".format(self.total_files)]
        for kind, label in RESOURCE_KINDS:
            lines.append(u"  {}: {}".format(label, self.count(kind)))
        if self.extensions:
            top = sorted(self.extensions.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
            lines.append(u"  主要类型: " + u", ".join(
                u"{} x{}".format(ext or u"(无扩展名)", count) for ext, count in top
            ))
        if self.missing_kinds:
            lines.append(u"  缺少: " + u", ".join(self.missing_kinds))
        return lines


# 扫描时跳过的目录：缓存与版本控制目录不属于模组内容
_SKIP_DIRS = (".cache", ".git", "__pycache__")


def scan_resources(mod_dir):
    """
    扫描模组包目录，生成 ResourceIndex。

    只统计，不读取文件内容，不修改磁盘。
    mod_dir 不存在时返回一个空清单，由调用方决定这算不算致命。
    """
    index = ResourceIndex()

    if not mod_dir or not os.path.isdir(mod_dir):
        return index

    for root, dirs, files in os.walk(mod_dir):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)

        for filename in files:
            index.total_files += 1

            relative = os.path.relpath(os.path.join(root, filename), mod_dir)
            segments = relative.split(os.sep)

            # 只统计模组包根部的那几类目录，
            # 避免 assets 下嵌套的同名目录被重复计数
            if len(segments) > 1 and segments[0] in RESOURCE_KIND_LABELS:
                head = segments[0]
                index.by_kind[head] = index.by_kind.get(head, 0) + 1

            extension = os.path.splitext(filename)[1].lower()
            index.extensions[extension] = index.extensions.get(extension, 0) + 1

    for kind, label in RESOURCE_KINDS:
        if not index.has(kind):
            index.missing_kinds.append(label)

    return index


# ============================================================
# 模组实例
# ============================================================

class ModInstance(object):
    """
    一个模组包的运行时实例。

    mod_info 直接来自 α 层的扫描结果，这里不做二次解析，
    只做「归类 + 状态跟踪 + 查询便利方法」。
    """

    def __init__(self, mod_info, mod_dir=None):
        self.info = mod_info
        self.mod_id = mod_info.get("modId") or u"unknown"
        self.version = mod_info.get("version") or u"未指定"
        self.display_name = mod_info.get("displayName") or self.mod_id
        self.description = mod_info.get("description") or u""
        self.authors = mod_info.get("authors") or []
        self.license = mod_info.get("license") or u"未指定"
        self.sub_mods = mod_info.get("mods") or []

        self.toml_path = mod_info.get("tomlPath")
        self.resources_path = mod_info.get("resourcesPath")
        self.mod_dir = mod_dir or mod_info.get("packDir") or self._guess_mod_dir()

        self.state = ModState.DISCOVERED
        self.stages = []
        self.notes = list(mod_info.get("errors") or [])

        self._resource_index = None

    # ---------------- 路径 ----------------

    def _guess_mod_dir(self):
        """packDir 缺失时，从 tomlPath 往上退两级（…/模组包/META-INF/xxx.toml）。"""
        if not self.toml_path:
            return None
        return os.path.dirname(os.path.dirname(self.toml_path))

    @property
    def resources(self):
        """资源清单（惰性扫描并缓存）。"""
        if self._resource_index is None:
            self._resource_index = scan_resources(self.mod_dir)
        return self._resource_index

    def invalidate_resources(self):
        """资源目录内容变了之后手动失效缓存。"""
        self._resource_index = None

    def path_of(self, *parts):
        """取模组包内的某个路径。"""
        if not self.mod_dir:
            return None
        return os.path.join(self.mod_dir, *parts)

    def sub_path(self, relative):
        """按 assets/... 这种斜杠写法取路径。"""
        if not self.mod_dir:
            return None
        segments = [seg for seg in relative.replace(u"\\", u"/").split(u"/") if seg]
        return os.path.join(self.mod_dir, *segments)

    # ---------------- 状态 ----------------

    def begin_activation(self):
        self.state = ModState.ACTIVATING

    def mark_loaded(self):
        self.state = ModState.LOADED

    def mark_failed(self, reason=None):
        self.state = ModState.FAILED
        if reason:
            self.notes.append(reason)

    def mark_unloaded(self):
        self.state = ModState.UNLOADED

    def add_stage(self, key, title):
        record = StageRecord(key, title)
        self.stages.append(record)
        return record

    @property
    def is_loaded(self):
        return self.state == ModState.LOADED

    @property
    def failed_stages(self):
        return [stage for stage in self.stages if not stage.ok]

    @property
    def warnings(self):
        return [stage for stage in self.stages if stage.state == StageState.WARNED]

    # ---------------- 展示 ----------------

    def label(self):
        if self.display_name and self.display_name != self.mod_id:
            return u"{} ({})".format(self.display_name, self.mod_id)
        return self.mod_id

    def status_lines(self):
        """多行状态报告，给控制台诊断用。"""
        lines = [
            u"模组: {}  v{}".format(self.label(), self.version),
            u"状态: {}".format(ModState.describe(self.state)),
            u"目录: {}".format(self.mod_dir or u"未知"),
        ]
        if self.authors:
            lines.append(u"作者: {}".format(u", ".join(self.authors)))
        lines.append(u"许可: {}".format(self.license))
        if self.sub_mods:
            lines.append(u"子模组: {} 个".format(len(self.sub_mods)))
        lines.append(u"资源: " + self.resources.describe())
        for stage in self.stages:
            lines.append(u"  - " + stage.describe())
        for note in self.notes:
            lines.append(u"  注意: " + u"{}".format(note))
        return lines

    def __repr__(self):
        return u"<ModInstance {} v{} {}>".format(
            self.mod_id, self.version, ModState.describe(self.state))


# ============================================================
# 工厂
# ============================================================

def create_instance(mod_info):
    """由 α 层的扫描结果造一个实例。"""
    return ModInstance(mod_info)


def create_instances(mod_infos):
    """批量造实例，返回 (实例列表, 跳过数)。"""
    instances = []
    skipped = 0
    for mod_info in mod_infos or []:
        if not mod_info or not mod_info.get("modId"):
            skipped += 1
            continue
        instances.append(ModInstance(mod_info))
    return instances, skipped


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    demo = {
        "modId": "demo_mod",
        "version": "1.0.0",
        "displayName": "DemoMod",
        "authors": ["tester"],
        "license": "MIT",
    }
    instance = ModInstance(demo)
    print(u"[容器] 自测实例: {}".format(instance))
    for line in instance.status_lines():
        print(u"[容器]   {}".format(line))

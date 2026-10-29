# -*- coding: utf-8 -*-
# injector.py
# NeoForge 核心包 - γ 层：数据注入
#
# 文件名沿用 injector；先前声称 inject 属于 Python 2 __future__ 是错误的，已移除。
#
# 职责：把模组包里的资源「整理成一份注入计划」，再交给引擎适配器去落地。
#
# 为什么拆成「计划」与「落地」两步：
#   1. 计划完全依赖文件系统，可以脱离游戏自测 —— 本文件就是这么写的；
#   2. 落地要调网易引擎的接口，而接口名必须以官方文档/实际 SDK 为准。
#      在没有确证之前，本层**不写任何具体引擎调用**，只暴露适配器钩子，
#      避免编造出不存在的 API 导致运行期 AttributeError。
#
# 编码约定：本文件是纯 Python，同时兼容 Python 2.7（游戏内）与 Python 3（本机自测）。
# 因此不用枚举、不用 f-string、不用 dict/set 推导式、不用非 ASCII 标识符。

from __future__ import print_function
from __future__ import absolute_import

import os


# ============================================================
# 资源类型
# ============================================================

KIND_TEXTURE = u"texture"
KIND_MODEL = u"model"
KIND_BLOCKSTATE = u"blockstate"
KIND_LANG = u"lang"
KIND_RECIPE = u"recipe"
KIND_TAG = u"tag"
KIND_SHADER = u"shader"
KIND_META = u"meta"
KIND_CODE = u"code"
KIND_OTHER = u"other"

KIND_TITLES = {
    KIND_TEXTURE: u"贴图",
    KIND_MODEL: u"模型",
    KIND_BLOCKSTATE: u"方块状态",
    KIND_LANG: u"语言文件",
    KIND_RECIPE: u"配方",
    KIND_TAG: u"标签",
    KIND_SHADER: u"着色器",
    KIND_META: u"元数据",
    KIND_CODE: u"代码",
    KIND_OTHER: u"其它",
}

# 处理方式：这一步只是「判断能不能直接用」，真正的格式转换属于后续工作
REUSE_AS_IS = u"直接复用"
NEEDS_CONVERSION = u"需要格式转换"
NEEDS_RUNTIME = u"需要运行时映射"
IGNORED = u"本版忽略"

KIND_POLICY = {
    KIND_TEXTURE: REUSE_AS_IS,
    KIND_LANG: NEEDS_CONVERSION,
    KIND_MODEL: NEEDS_CONVERSION,
    KIND_BLOCKSTATE: NEEDS_CONVERSION,
    KIND_RECIPE: NEEDS_CONVERSION,
    KIND_TAG: NEEDS_CONVERSION,
    KIND_SHADER: IGNORED,
    KIND_META: REUSE_AS_IS,
    KIND_CODE: NEEDS_RUNTIME,
    KIND_OTHER: IGNORED,
}

KIND_ORDER = (
    KIND_TEXTURE,
    KIND_LANG,
    KIND_MODEL,
    KIND_BLOCKSTATE,
    KIND_RECIPE,
    KIND_TAG,
    KIND_CODE,
    KIND_META,
    KIND_SHADER,
    KIND_OTHER,
)


# ============================================================
# 单个资源条目
# ============================================================

class InjectEntry(object):
    """一个待注入的资源文件。"""

    def __init__(self, kind, relative_path, absolute_path, size=0):
        self.kind = kind
        self.relative_path = relative_path
        self.absolute_path = absolute_path
        self.size = size

    @property
    def policy(self):
        return KIND_POLICY.get(self.kind, IGNORED)

    def describe(self):
        return u"[{}] {} ({})".format(
            KIND_TITLES.get(self.kind, self.kind), self.relative_path, self.policy)

    def __repr__(self):
        return u"<InjectEntry {} {}>".format(self.kind, self.relative_path)


# ============================================================
# 注入计划
# ============================================================

class InjectPlan(object):
    """一个模组的完整注入计划。只描述「有什么、怎么处理」，不执行。"""

    def __init__(self, mod_id, mod_dir=None):
        self.mod_id = mod_id
        self.mod_dir = mod_dir
        self.entries = []
        self.warnings = []
        self.skipped_dirs = []

    def add(self, entry):
        self.entries.append(entry)
        return entry

    def warn(self, message):
        self.warnings.append(message)

    def count(self, kind):
        total = 0
        for entry in self.entries:
            if entry.kind == kind:
                total += 1
        return total

    def entries_of(self, kind):
        return [entry for entry in self.entries if entry.kind == kind]

    def kinds(self):
        """返回已在计划里的类型，按 KIND_ORDER 排序。"""
        present = {}
        for entry in self.entries:
            present[entry.kind] = True
        return [kind for kind in KIND_ORDER if kind in present]

    def count_by_policy(self, policy):
        total = 0
        for entry in self.entries:
            if entry.policy == policy:
                total += 1
        return total

    @property
    def total_files(self):
        return len(self.entries)

    @property
    def total_bytes(self):
        return sum([entry.size for entry in self.entries])

    def summary_lines(self):
        lines = [u"模组 {}: 共 {} 个资源文件，{} 字节".format(
            self.mod_id, self.total_files, self.total_bytes)]
        for kind in self.kinds():
            lines.append(u"  {}: {} 个（{}）".format(
                KIND_TITLES.get(kind, kind), self.count(kind), KIND_POLICY.get(kind)))
        if self.skipped_dirs:
            lines.append(u"  跳过的目录: " + u", ".join(self.skipped_dirs))
        for note in self.warnings:
            lines.append(u"  注意: " + u"{}".format(note))
        return lines

    def __repr__(self):
        return u"<InjectPlan {} {} 个文件>".format(self.mod_id, self.total_files)


# ============================================================
# 资源归类
# ============================================================

# 扫描时跳过的目录
_SKIP_DIRS = (".cache", ".git", "__pycache__")

_SHADER_EXTS = (".fsh", ".vsh", ".glsl", ".program")


def classify(relative_path):
    """
    按相对路径判断资源类型。

    只依赖路径，不读文件内容 —— 这样扫描大模组包也很快。
    """
    normalized = relative_path.replace(u"\\", u"/")
    segments = [seg for seg in normalized.split(u"/") if seg]
    if not segments:
        return KIND_OTHER

    name = segments[-1]
    lowered = name.lower()
    extension = os.path.splitext(lowered)[1]
    head = segments[0]

    if head == u"assets":
        # assets/<namespace>/<类别>/...
        if len(segments) >= 3:
            category = segments[2]
            if category == u"textures":
                return KIND_TEXTURE
            if category == u"blockstates":
                return KIND_BLOCKSTATE
            if category == u"models":
                return KIND_MODEL
            if category == u"lang":
                return KIND_LANG
            if category == u"shaders":
                return KIND_SHADER
        if extension in _SHADER_EXTS:
            return KIND_SHADER
        return KIND_OTHER

    if head == u"data":
        # data/<namespace>/<类别>/...
        if len(segments) >= 3:
            category = segments[2]
            if category in (u"recipe", u"recipes"):
                return KIND_RECIPE
            if category == u"tags":
                return KIND_TAG
        return KIND_OTHER

    if head == u"META-INF":
        return KIND_META

    if head == u"sen":
        if extension == u".py":
            return KIND_CODE
        return KIND_CODE

    if extension in _SHADER_EXTS:
        return KIND_SHADER

    return KIND_OTHER


# ============================================================
# 生成计划
# ============================================================

def build_plan(mod_id, mod_dir, max_entries=None):
    """
    扫描模组目录，生成注入计划。

    mod_dir 不存在时返回一个「空计划 + 一条告警」，
    由调用方（生命周期）决定这算不算致命。
    """
    plan = InjectPlan(mod_id, mod_dir)

    if not mod_dir or not os.path.isdir(mod_dir):
        plan.warn(u"模组目录不存在: {}".format(mod_dir))
        return plan

    for root, dirs, files in os.walk(mod_dir):
        skipped = [d for d in dirs if d in _SKIP_DIRS]
        for name in skipped:
            plan.skipped_dirs.append(name)
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)

        for filename in sorted(files):
            absolute = os.path.join(root, filename)
            relative = os.path.relpath(absolute, mod_dir)

            try:
                size = os.path.getsize(absolute)
            except OSError:
                size = 0

            plan.add(InjectEntry(classify(relative), relative, absolute, size))

            if max_entries is not None and len(plan.entries) >= max_entries:
                plan.warn(u"条目数达到上限 {}，未继续扫描".format(max_entries))
                return plan

    if plan.total_files == 0:
        plan.warn(u"模组目录里没有任何文件")

    for kind in (KIND_TEXTURE, KIND_MODEL):
        if plan.count(kind) == 0:
            plan.warn(u"没有{}文件，模组在游戏里可能不可见".format(
                KIND_TITLES.get(kind, kind)))

    if plan.count(KIND_SHADER):
        plan.warn(u"有 {} 个着色器文件，本版按「忽略」处理".format(
            plan.count(KIND_SHADER)))

    return plan


# ============================================================
# 引擎适配器
# ============================================================

class EngineAdapter(object):
    """
    引擎适配器基类。

    真正的网易引擎调用必须写在子类里，并且只使用**经过确认**的接口。
    本层不预设任何具体接口名。
    """

    name = u"abstract"

    def is_available(self):
        """当前环境能否真正落地注入。"""
        return False

    def begin(self, plan):
        """计划开始时调用一次。"""
        return True

    def inject(self, entry):
        """
        注入单个条目。

        返回 True 表示成功，False 表示失败。
        基类实现只记录，不调用任何引擎接口。
        """
        return False

    def end(self, plan, results):
        """计划结束时调用一次。"""
        return True


class NullAdapter(EngineAdapter):
    """
    空适配器：只统计，不做任何实际动作。

    用途：
      - 未接入真实引擎时让整条链路能跑通；
      - 自测时断言「计划内容」而不是「引擎副作用」。
    """

    name = u"null"

    def __init__(self):
        self.begun = []
        self.injected = []
        self.ended = []

    def is_available(self):
        return True

    def begin(self, plan):
        self.begun.append(plan.mod_id)
        return True

    def inject(self, entry):
        self.injected.append(entry)
        return True

    def end(self, plan, results):
        self.ended.append((plan.mod_id, len(results)))
        return True


class LoggingAdapter(EngineAdapter):
    """
    打印适配器：把「本来会做什么」打到控制台，便于人肉核对。

    真机上先跑这个，确认计划正确了，再换真实适配器。
    """

    name = u"logging"

    def __init__(self, logger=None):
        self._logger = logger or (lambda text: print(text))

    def is_available(self):
        return True

    def begin(self, plan):
        self._logger(u"[注入] ===== {} =====".format(plan.mod_id))
        for line in plan.summary_lines():
            self._logger(u"[注入] " + line)
        return True

    def inject(self, entry):
        self._logger(u"[注入] {}".format(entry.describe()))
        return True

    def end(self, plan, results):
        self._logger(u"[注入] {} 完成，处理 {} 个条目".format(
            plan.mod_id, results.attempted))
        return True


class InjectResult(object):
    """一次注入的统计结果。"""

    def __init__(self, mod_id, adapter_name):
        self.mod_id = mod_id
        self.adapter_name = adapter_name
        self.attempted = 0
        self.succeeded = 0
        self.failed = []
        self.available = False

    def __len__(self):
        """让适配器可以写 len(results) 拿到条目数。"""
        return self.attempted

    @property
    def ok(self):
        return self.available and not self.failed

    def describe(self):
        return u"模组 {} 经适配器 {} 注入 {} 个，成功 {} 个，失败 {} 个（可用: {}）".format(
            self.mod_id, self.adapter_name, self.attempted,
            self.succeeded, len(self.failed), self.available)


def apply_plan(plan, adapter):
    """
    用给定适配器落地一个注入计划。

    适配器不可用时，直接返回「未注入」的结果，不抛异常 ——
    引擎接口缺失不该让整个模组加载流程崩掉。
    """
    result = InjectResult(plan.mod_id, getattr(adapter, "name", u"unknown"))
    result.available = bool(adapter.is_available())

    if not result.available:
        return result

    adapter.begin(plan)

    for entry in plan.entries:
        result.attempted += 1
        try:
            if adapter.inject(entry):
                result.succeeded += 1
            else:
                result.failed.append(entry.relative_path)
        except Exception as error:
            # 单个资源失败不该中断整个计划，记下来继续
            result.failed.append(u"{}（异常: {}）".format(entry.relative_path, error))

    adapter.end(plan, result)

    return result


# ============================================================
# 便捷入口
# ============================================================

def plan_for_instance(instance, max_entries=None):
    """由容器层的 ModInstance 生成注入计划。"""
    return build_plan(instance.mod_id, instance.mod_dir, max_entries=max_entries)


def inject_instance(instance, adapter=None):
    """
    规划并落地一个模组实例的资源注入。

    adapter 为 None 时用空适配器，保证链路可跑但不产生副作用。
    """
    plan = plan_for_instance(instance)
    return apply_plan(plan, adapter or NullAdapter())


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print(u"[注入] 自测模式：需要一个模组目录路径")
    print(u"[注入] 用法: build_plan(modId, 目录) -> apply_plan(计划, 适配器)")

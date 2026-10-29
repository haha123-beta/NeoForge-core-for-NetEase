# -*- coding: utf-8 -*-
# container/lifecycle.py
# 运行时容器 - 生命周期
#
# 职责：把一个「已发现」的模组实例，按固定顺序推过若干阶段，走到「已加载」或「失败」。
#
# 设计要点：
#   1. 每个阶段独立、可单独调用，便于定位问题；
#   2. 致命问题（fail）才终止流程，缺失的可选项只记告警（warn）继续走；
#   3. 阶段名与顺序集中在一张表里，加新阶段只需改一处。
#
# 本层不碰游戏 API，因此可以脱离游戏单独自测。

from __future__ import print_function
from __future__ import absolute_import

import os
import sys

# 导入方式对齐官方约定：RegisterSystem 的 clsPath 要求「路径从脚本的第一层算起」，
# 官方示例是 "tutorialScripts.tutorialServerSystem.TutorialServerSystem"，
# 也就是把脚本根目录当作 sys.path 的根，用「文件夹.模块.类」的点分路径导入。
# 因此这里统一用 core.xxx 包导入，而不是平坦的 import xxx。
#
# 兜底：某些加载方式下脚本根目录可能不在 sys.path 上，
# 那种情况下退回平坦导入，保证核心仍能起来而不是直接 ImportError。
_PACK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PACK_ROOT not in sys.path:
    sys.path.insert(0, _PACK_ROOT)

try:
    from core.mod_instance import (  # noqa: E402
        ModInstance,
        ModState,
        StageState,
        create_instance,
    )
except ImportError:
    # 脚本根不在 sys.path 时的退路
    sys.path.append(os.path.join(_PACK_ROOT, "core"))
    from mod_instance import (  # type: ignore # noqa: E402
        ModInstance,
        ModState,
        StageState,
        create_instance,
    )

try:
    from core import alpha_neoforge  # noqa: E402
except ImportError:
    sys.path.append(os.path.join(_PACK_ROOT, "core"))
    import alpha_neoforge  # type: ignore # noqa: E402

try:
    # 模块名用 injector 而非 inject：后者容易与 __future__ 等撞名
    from core import injector as inject_layer  # noqa: E402
except ImportError:
    try:
        import injector as inject_layer  # type: ignore # noqa: E402
    except ImportError:
        inject_layer = None


# ============================================================
# 阶段表
# ============================================================

STAGE_DIR = u"dir"            # 模组目录存在
STAGE_MANIFEST = u"manifest"  # neoforge.mods.toml 可读且完整
STAGE_RESOURCES = u"resources"  # assets / data 结构可用
STAGE_CODE = u"code"          # 翻译后的代码是否就位
STAGE_INJECT = u"inject"      # 资源注入（γ 层，尚未实现，先记跳过）

STAGE_TITLES = {
    STAGE_DIR: u"检查模组目录",
    STAGE_MANIFEST: u"校验 mods.toml",
    STAGE_RESOURCES: u"检查资源结构",
    STAGE_CODE: u"检查翻译代码",
    STAGE_INJECT: u"注入资源路径",
}

STAGE_ORDER = (
    STAGE_DIR,
    STAGE_MANIFEST,
    STAGE_RESOURCES,
    STAGE_CODE,
    STAGE_INJECT,
)


# ============================================================
# 容器
# ============================================================

class ModContainer(object):
    """所有模组实例的汇总，以及它们的生命周期入口。"""

    def __init__(self):
        self._instances = {}   # mod_id -> ModInstance
        self.load_order = []   # 记录注册顺序，加载时按此顺序走

    # ---------------- 登记 ----------------

    def register_modpack(self, resources_path):
        """
        登记一个模组包（等于 α 层注册 + 建实例）。
        返回值与 alpha_neoforge.register_modpack 结构一致，另外加一个 instance 字段。
        """
        result = alpha_neoforge.register_modpack(resources_path)
        if not result.get("success"):
            return result

        instance = create_instance(result["info"])
        self._add(instance)

        result["instance"] = instance
        return result

    def register_mod_info(self, mod_info):
        """直接用一个已解析的元数据登记实例（自测与高级用法）。"""
        instance = create_instance(mod_info)
        self._add(instance)
        return instance

    def _add(self, instance):
        if instance.mod_id in self._instances:
            print(u"[容器] 模组 '{}' 已登记，替换为新实例".format(instance.mod_id))
            self.load_order = [mid for mid in self.load_order if mid != instance.mod_id]
        self._instances[instance.mod_id] = instance
        self.load_order.append(instance.mod_id)

    # ---------------- 查询 ----------------

    def get(self, mod_id):
        return self._instances.get(mod_id)

    def all(self):
        """按登记顺序返回实例列表。"""
        return [self._instances[mid] for mid in self.load_order
                if mid in self._instances]

    def loaded(self):
        return [inst for inst in self.all() if inst.state == ModState.LOADED]

    def failed(self):
        return [inst for inst in self.all() if inst.state == ModState.FAILED]

    def count(self):
        return len(self._instances)

    def clear(self):
        self._instances = {}
        self.load_order = []

    # ---------------- 加载 ----------------

    def load_one(self, mod_id, verbose=True):
        """把一个模组推过全部阶段。返回该实例。"""
        instance = self._instances.get(mod_id)
        if instance is None:
            print(u"[容器] 找不到模组 '{}'，无法加载".format(mod_id))
            return None

        if verbose:
            print(u"")
            print(u"[容器] ===== 加载 {} =====".format(instance.label()))

        _run_stages(instance, verbose=verbose)

        if verbose:
            for stage in instance.stages:
                marker = u"OK  " if stage.ok else u"FAIL"
                print(u"[容器]   [{}] {}".format(marker, stage.describe()))
            print(u"[容器] 结果: {}".format(ModState.describe(instance.state)))

        return instance

    def load_all(self, verbose=True):
        """按登记顺序加载全部模组，返回实例列表。"""
        for mod_id in list(self.load_order):
            self.load_one(mod_id, verbose=verbose)
        return self.all()

    def unload_all(self):
        """把已加载的实例标记为已卸载（真正的资源释放由后续层负责）。"""
        for instance in self.all():
            if instance.state == ModState.LOADED:
                instance.mark_unloaded()
        return self.load_order

    def summary_lines(self):
        """整体状态报告。"""
        lines = [u"已登记模组: {} 个（已加载 {}，失败 {}）".format(
            self.count(), len(self.loaded()), len(self.failed()))]
        for instance in self.all():
            lines.append(u"  [{}] {} v{}".format(
                ModState.describe(instance.state), instance.label(), instance.version))
        return lines

    def print_summary(self):
        for line in self.summary_lines():
            print(u"[容器] " + line)


# ============================================================
# 各阶段
# ============================================================

def stage_dir(instance, record):
    """
    模组目录必须存在。

    这是唯一的「硬前提」：目录都没了，后面所有检查都没有意义。
    """
    mod_dir = instance.mod_dir

    if not mod_dir:
        record.fail(u"无法确定模组目录")
        return record

    if not os.path.isdir(mod_dir):
        record.fail(u"目录不存在: {}".format(mod_dir))
        return record

    record.done()
    return record


def stage_manifest(instance, record):
    """
    neoforge.mods.toml 必须存在、可读、且声明了 modId。

    复用 α 层的读取与解析，避免两处解析逻辑不一致。
    """
    path = instance.toml_path
    if not path:
        path = instance.path_of("META-INF", "neoforge.mods.toml")

    if not path or not os.path.isfile(path):
        record.fail(u"找不到 neoforge.mods.toml")
        return record

    try:
        content = alpha_neoforge.read_text_file(path)
    except Exception as error:
        record.fail(u"读取失败: {}".format(error))
        return record

    parsed = alpha_neoforge.parse_toml(content)

    if not parsed.get("modId"):
        record.fail(u"未声明 modId")
        return record

    if parsed["modId"] != instance.mod_id:
        # 不是致命问题，但值得说出来：说明 α 层的结论和这里对不上
        record.warn(u"toml 里的 modId 是 '{}'，实例记录的是 '{}'".format(
            parsed["modId"], instance.mod_id))

    for problem in parsed.get("errors") or []:
        record.warn(problem)

    if record.state == StageState.PENDING:
        record.done()

    return record


def stage_resources(instance, record):
    """
    资源结构检查。

    这里刻意区分「致命」与「告警」：
      - assets 是模型/贴图/语言，缺了模组在游戏里就是隐形的 —— 告警
      - data 是配方/标签，缺了仍然能玩 —— 告警
      - 一个资源都没有才是致命的，因为那说明路径根本不对
    """
    index = instance.resources

    if index.total_files == 0:
        record.fail(u"模组包里没有任何文件，路径可能不对")
        return record

    assets = index.count("assets")
    data = index.count("data")

    if assets == 0:
        record.warn(u"没有 assets 目录，模型/贴图/语言不会被加载")
    if data == 0 and index.count("META-INF") == 0:
        record.warn(u"既没有 data 也没有 META-INF，不像是完整的模组包")

    if record.state == StageState.PENDING:
        record.done(u"共 {} 个文件".format(index.total_files))
    else:
        record.messages.append(u"共 {} 个文件".format(index.total_files))

    return record


def stage_code(instance, record):
    """
    翻译后的代码是否就位。

    按设计，Java 的 .class 预翻译成 .py 后放在 sen/ 下；
    没有 .py 说明这个模组还没翻译，属于「能发现但跑不起来」，
    记告警而不是失败 —— 资源注入仍然可以先做。
    """
    code_dir = instance.path_of("sen")

    if not code_dir or not os.path.isdir(code_dir):
        record.warn(u"没有 sen 目录，模组尚未翻译")
        return record

    py_count = 0
    class_count = 0
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = sorted(d for d in dirs if d not in (".cache", "__pycache__"))
        for filename in files:
            if filename.endswith(".py"):
                py_count += 1
            elif filename.endswith(".class"):
                class_count += 1

    if class_count and not py_count:
        record.warn(u"sen 下有 {} 个 .class 但还没有 .py，需要先翻译".format(class_count))
    elif class_count:
        record.warn(u"sen 下还有 {} 个未翻译的 .class".format(class_count))
    elif py_count == 0:
        record.warn(u"sen 目录存在但没有文件")
    else:
        record.done(u"{} 个 .py".format(py_count))

    return record


def stage_inject(instance, record):
    """
    γ 层：生成注入计划并落地。

    落地默认走「空适配器」——它只统计不产生副作用，
    因为在没有确证网易引擎接口名之前，本核心不调用任何具体引擎 API。
    若要在真机上核对计划，把 adapter 换成 inject.LoggingAdapter() 即可。
    """
    if inject_layer is None:
        record.skip(u"inject 模块未加载")
        return record

    plan = inject_layer.plan_for_instance(instance)
    instance.inject_plan = plan

    result = inject_layer.apply_plan(plan, inject_layer.NullAdapter())
    instance.inject_result = result

    if result.failed:
        record.warn(u"{} 个条目注入失败".format(len(result.failed)))

    record.done(u"{} 个资源条目（贴图 {}，模型 {}，语言 {}，配方 {}）".format(
        plan.total_files,
        plan.count(inject_layer.KIND_TEXTURE),
        plan.count(inject_layer.KIND_MODEL),
        plan.count(inject_layer.KIND_LANG),
        plan.count(inject_layer.KIND_RECIPE),
    ))

    for note in plan.warnings:
        record.warn(note)

    return record


_STAGE_HANDLERS = {
    STAGE_DIR: stage_dir,
    STAGE_MANIFEST: stage_manifest,
    STAGE_RESOURCES: stage_resources,
    STAGE_CODE: stage_code,
    STAGE_INJECT: stage_inject,
}


def _run_stages(instance, verbose=True):
    """按 STAGE_ORDER 依次跑阶段；遇到致命失败立刻停下。"""
    instance.begin_activation()
    instance.stages = []

    for key in STAGE_ORDER:
        handler = _STAGE_HANDLERS.get(key)
        record = instance.add_stage(key, STAGE_TITLES.get(key, key))

        if handler is None:
            record.skip(u"阶段未实现")
            continue

        try:
            handler(instance, record)
        except Exception as error:
            # 单个阶段崩了不该拖垮整个加载，记失败继续往下跑，
            # 这样一次就能看到所有问题，而不是修一个跑一次
            record.fail(u"阶段执行异常: {}".format(error))

        if record.state == StageState.PENDING:
            record.done()

        if not record.ok and key == STAGE_DIR:
            # 目录不存在时，后面的阶段没有可检查的对象，直接跳过更清晰
            for later in STAGE_ORDER[STAGE_ORDER.index(key) + 1:]:
                instance.add_stage(later, STAGE_TITLES.get(later, later)).skip(
                    u"前置检查未通过")
            break

    if instance.failed_stages:
        instance.mark_failed()
    else:
        instance.mark_loaded()

    return instance


# ============================================================
# 模块级便捷接口（接口.py 会转发到这里）
# ============================================================

_default_container = ModContainer()


def get_container():
    """取默认容器。整个游戏会话共用这一个。"""
    return _default_container


def register_modpack(resources_path):
    """登记一个模组包。"""
    return _default_container.register_modpack(resources_path)


def load_one(mod_id, verbose=True):
    """加载一个已登记的模组。"""
    return _default_container.load_one(mod_id, verbose=verbose)


def load_all(verbose=True):
    """加载全部已登记的模组。"""
    return _default_container.load_all(verbose=verbose)


def get_instance(mod_id):
    """按 modId 取实例。"""
    return _default_container.get(mod_id)


def list_instances():
    """按登记顺序列出实例。"""
    return _default_container.all()


def print_summary():
    """打印整体状态。"""
    _default_container.print_summary()


def clear():
    """清空容器（自测与重载用）。"""
    _default_container.clear()
    alpha_neoforge.clear_registry()


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print(u"[容器] 自测模式：需要一个真实模组包路径")
    print(u"[容器] 用法: register_modpack(路径) -> load_all()")

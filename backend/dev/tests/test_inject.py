# -*- coding: utf-8 -*-
"""
γ 层自测：core/injector.py（数据注入）

验证点：
  1. classify：按路径正确归类贴图/模型/方块状态/语言/配方/标签/着色器/代码/元数据
  2. build_plan：扫描出正确的条目数、字节数、跳过目录、告警
  3. 处理策略：复用 / 需转换 / 需运行时映射 / 忽略 四档归类正确
  4. 适配器：空适配器、打印适配器、失败的适配器
  5. apply_plan：不可用适配器不抛异常；单个条目失败不中断整体
  6. 与容器层联动：生命周期里的注入阶段真的产出了计划
  7. 真实模组包：计划与资源清单口径一致（只读）
"""

import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary, make_sample_modpack  # noqa: E402

pkg = Package()
inject = pkg.load("core.injector")
lifecycle = pkg.load("container.lifecycle")

workdir = pkg.temp_dir()


def write_bytes(path, payload):
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "wb") as fp:
        fp.write(payload)


def write_text(path, text):
    write_bytes(path, text.encode("utf-8"))


def make_full_modpack(root, mod_id=u"plan_mod"):
    """造一个结构完整的模组包，覆盖所有资源类型。"""
    base = os.path.join(root, "resources", "mod-1.0")
    write_text(os.path.join(base, "META-INF", "neoforge.mods.toml"),
               u'[[mods]]\nmodId="{}"\nversion="1.0"\n'.format(mod_id))

    # assets：贴图 3、模型 2、方块状态 1、语言 1、着色器 1
    for name in ("a", "b", "c"):
        write_bytes(os.path.join(base, "assets", "demo", "textures", "block",
                                 name + ".png"), b"PNGDATA")
    for name in ("m1", "m2"):
        write_text(os.path.join(base, "assets", "demo", "models", "item",
                                name + ".json"), u"{}")
    write_text(os.path.join(base, "assets", "demo", "blockstates", "bs.json"), u"{}")
    write_text(os.path.join(base, "assets", "demo", "lang", "zh_cn.json"), u"{}")
    write_text(os.path.join(base, "assets", "demo", "shaders", "core", "x.fsh"), u"//")

    # data：配方 3、标签 2
    for name in ("r1", "r2", "r3"):
        write_text(os.path.join(base, "data", "demo", "recipe", name + ".json"), u"{}")
    for name in ("t1", "t2"):
        write_text(os.path.join(base, "data", "demo", "tags", "item", name + ".json"),
                   u"{}")

    # sen：代码 2
    for name in ("Mod.py", "Helper.py"):
        write_text(os.path.join(base, "sen", "demo", name), u"# code\n")

    # .cache：必须被跳过
    write_bytes(os.path.join(base, ".cache", "junk.bin"), b"x" * 100)

    return base


try:
    # ------------------------------------------------------------
    section("资源归类")
    # ------------------------------------------------------------
    cases = [
        (u"assets/demo/textures/block/x.png", inject.KIND_TEXTURE),
        (u"assets\\demo\\textures\\item\\y.png", inject.KIND_TEXTURE),
        (u"assets/demo/models/item/m.json", inject.KIND_MODEL),
        (u"assets/demo/blockstates/bs.json", inject.KIND_BLOCKSTATE),
        (u"assets/demo/lang/zh_cn.json", inject.KIND_LANG),
        (u"assets/demo/shaders/core/s.fsh", inject.KIND_SHADER),
        (u"data/demo/recipe/r.json", inject.KIND_RECIPE),
        (u"data/demo/recipes/r.json", inject.KIND_RECIPE),
        (u"data/demo/tags/item/t.json", inject.KIND_TAG),
        (u"META-INF/neoforge.mods.toml", inject.KIND_META),
        (u"sen/demo/Mod.py", inject.KIND_CODE),
        (u"sen/demo/Thing.class", inject.KIND_CODE),
        (u"top_level.fsh", inject.KIND_SHADER),
        (u"whatever.txt", inject.KIND_OTHER),
    ]
    for path, expected in cases:
        actual = inject.classify(path)
        check(u"归类 {}".format(path), actual == expected,
              u"期望 {} 得到 {}".format(expected, actual))

    # ------------------------------------------------------------
    section("处理策略")
    # ------------------------------------------------------------
    check(u"贴图可直接复用",
          inject.KIND_POLICY[inject.KIND_TEXTURE] == inject.REUSE_AS_IS)
    check(u"模型需要格式转换",
          inject.KIND_POLICY[inject.KIND_MODEL] == inject.NEEDS_CONVERSION)
    check(u"配方需要格式转换",
          inject.KIND_POLICY[inject.KIND_RECIPE] == inject.NEEDS_CONVERSION)
    check(u"着色器本版忽略",
          inject.KIND_POLICY[inject.KIND_SHADER] == inject.IGNORED)
    check(u"代码需要运行时映射",
          inject.KIND_POLICY[inject.KIND_CODE] == inject.NEEDS_RUNTIME)

    # ------------------------------------------------------------
    section("生成注入计划")
    # ------------------------------------------------------------
    mod_dir = make_full_modpack(workdir, mod_id=u"plan_mod")
    plan = inject.build_plan("plan_mod", mod_dir)

    check(u"贴图 3 个", plan.count(inject.KIND_TEXTURE) == 3,
          plan.count(inject.KIND_TEXTURE))
    check(u"模型 2 个", plan.count(inject.KIND_MODEL) == 2, plan.count(inject.KIND_MODEL))
    check(u"方块状态 1 个", plan.count(inject.KIND_BLOCKSTATE) == 1,
          plan.count(inject.KIND_BLOCKSTATE))
    check(u"语言 1 个", plan.count(inject.KIND_LANG) == 1, plan.count(inject.KIND_LANG))
    check(u"着色器 1 个", plan.count(inject.KIND_SHADER) == 1,
          plan.count(inject.KIND_SHADER))
    check(u"配方 3 个", plan.count(inject.KIND_RECIPE) == 3, plan.count(inject.KIND_RECIPE))
    check(u"标签 2 个", plan.count(inject.KIND_TAG) == 2, plan.count(inject.KIND_TAG))
    check(u"代码 2 个", plan.count(inject.KIND_CODE) == 2, plan.count(inject.KIND_CODE))
    check(u"元数据 1 个", plan.count(inject.KIND_META) == 1, plan.count(inject.KIND_META))

    check(u"总条目 16 个", plan.total_files == 16, plan.total_files)
    check(u"字节数大于 0", plan.total_bytes > 0, plan.total_bytes)
    check(u".cache 被跳过并记录", u".cache" in plan.skipped_dirs, plan.skipped_dirs)
    check(u".cache 里的文件没进计划",
          all(u".cache" not in entry.relative_path for entry in plan.entries),
          [e.relative_path for e in plan.entries if u".cache" in e.relative_path])

    check(u"kinds 按 KIND_ORDER 排序",
          plan.kinds() == [k for k in inject.KIND_ORDER if plan.count(k) > 0],
          plan.kinds())
    check(u"有可复用条目", plan.count_by_policy(inject.REUSE_AS_IS) >= 4,
          plan.count_by_policy(inject.REUSE_AS_IS))
    check(u"有需转换条目", plan.count_by_policy(inject.NEEDS_CONVERSION) >= 7,
          plan.count_by_policy(inject.NEEDS_CONVERSION))
    check(u"着色器给出忽略告警",
          any(u"着色器" in w for w in plan.warnings), plan.warnings)

    check(u"entries_of 只返回该类",
          len(plan.entries_of(inject.KIND_TEXTURE)) == 3,
          len(plan.entries_of(inject.KIND_TEXTURE)))
    check(u"summary 行数合理", len(plan.summary_lines()) >= 5, plan.summary_lines())

    # ------------------------------------------------------------
    section("异常路径")
    # ------------------------------------------------------------
    missing_plan = inject.build_plan("ghost", os.path.join(workdir, "no_such_dir"))
    check(u"目录不存在 -> 空计划", missing_plan.total_files == 0, missing_plan.total_files)
    check(u"目录不存在 -> 有告警",
          any(u"不存在" in w for w in missing_plan.warnings), missing_plan.warnings)

    empty_dir = os.path.join(workdir, "empty_mod")
    os.makedirs(empty_dir)
    empty_plan = inject.build_plan("empty", empty_dir)
    check(u"空目录 -> 空计划且有告警",
          empty_plan.total_files == 0 and empty_plan.warnings, empty_plan.warnings)

    limited = inject.build_plan("plan_mod", mod_dir, max_entries=5)
    check(u"max_entries 生效", limited.total_files == 5, limited.total_files)
    check(u"max_entries 触发告警",
          any(u"上限" in w for w in limited.warnings), limited.warnings)

    only_texture_dir = os.path.join(workdir, "only_texture")
    write_bytes(os.path.join(only_texture_dir, "assets", "d", "textures", "a.png"), b"P")
    sparse_plan = inject.build_plan("sparse", only_texture_dir)
    check(u"缺模型时给出告警",
          any(u"模型" in w for w in sparse_plan.warnings), sparse_plan.warnings)

    # ------------------------------------------------------------
    section("适配器")
    # ------------------------------------------------------------
    null_adapter = inject.NullAdapter()
    check(u"空适配器可用", null_adapter.is_available() is True)

    result = inject.apply_plan(plan, null_adapter)
    check(u"空适配器统计全部成功", result.succeeded == plan.total_files, result.describe())
    check(u"空适配器记录 begin/end",
          null_adapter.begun == ["plan_mod"] and null_adapter.ended, null_adapter.ended)
    check(u"结果 ok", result.ok is True, result.describe())

    logged = []
    logging_adapter = inject.LoggingAdapter(logger=logged.append)
    logging_result = inject.apply_plan(plan, logging_adapter)
    check(u"打印适配器也全部成功",
          logging_result.succeeded == plan.total_files, logging_result.describe())
    check(u"打印适配器输出了计划摘要",
          any(u"个资源文件" in line for line in logged), logged[:3])
    check(u"打印适配器输出了每个条目",
          any(u"x.png" in line or u"a.png" in line for line in logged), logged[:5])

    class UnavailableAdapter(inject.EngineAdapter):
        name = u"unavailable"

        def is_available(self):
            return False

    unavailable = inject.apply_plan(plan, UnavailableAdapter())
    check(u"不可用适配器不抛异常", unavailable.available is False)
    check(u"不可用适配器没尝试注入", unavailable.attempted == 0, unavailable.attempted)
    check(u"不可用适配器结果不 ok", unavailable.ok is False)

    class GrumpyAdapter(inject.EngineAdapter):
        name = u"grumpy"

        def __init__(self, fail_on):
            self.fail_on = fail_on

        def is_available(self):
            return True

        def inject(self, entry):
            if self.fail_on in entry.relative_path:
                raise RuntimeError(u"模拟引擎报错")
            return True

    grumpy = inject.apply_plan(plan, GrumpyAdapter("b.png"))
    check(u"单个条目异常不中断整体",
          grumpy.succeeded == plan.total_files - 1, grumpy.describe())
    check(u"失败条目被记录", len(grumpy.failed) == 1, grumpy.failed)
    check(u"失败信息带异常原因",
          any(u"模拟引擎报错" in item for item in grumpy.failed), grumpy.failed)
    check(u"有失败时结果不 ok", grumpy.ok is False)

    class RefusingAdapter(inject.EngineAdapter):
        name = u"refusing"

        def is_available(self):
            return True

        def inject(self, entry):
            return False

    refusing = inject.apply_plan(plan, RefusingAdapter())
    check(u"适配器返回 False 记为失败",
          refusing.succeeded == 0 and len(refusing.failed) == plan.total_files,
          refusing.describe())

    # ------------------------------------------------------------
    section("与容器层联动")
    # ------------------------------------------------------------
    lifecycle.clear()
    registered = lifecycle.register_modpack(mod_dir)
    check(u"模组登记成功", registered.get("success") is True, registered)

    instance = lifecycle.load_one("plan_mod", verbose=False)
    check(u"实例加载成功", instance.state == "loaded", instance.state)
    check(u"生命周期里挂上了注入计划", getattr(instance, "inject_plan", None) is not None)
    check(u"注入计划的条目数与独立规划一致",
          instance.inject_plan.total_files == plan.total_files,
          u"{} vs {}".format(instance.inject_plan.total_files, plan.total_files))

    check(u"生命周期里挂上了注入结果",
          getattr(instance, "inject_result", None) is not None)
    check(u"注入结果全部成功",
          instance.inject_result.succeeded == plan.total_files,
          instance.inject_result.describe())

    inject_stage = [s for s in instance.stages if s.key == lifecycle.STAGE_INJECT][0]
    check(u"注入阶段不再是「跳过」", inject_stage.state != "skipped", inject_stage.state)
    check(u"注入阶段报出资源条目数",
          any(u"个资源条目" in m for m in inject_stage.messages), inject_stage.messages)

    check(u"plan_for_instance 与 build_plan 口径一致",
          inject.plan_for_instance(instance).total_files == plan.total_files)

    check(u"inject_instance 默认不产生副作用",
          inject.inject_instance(instance).succeeded == plan.total_files)

    # ------------------------------------------------------------
    section("端到端：真实模组包（只读）")
    # ------------------------------------------------------------
    real_root = os.path.join(
        r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn",
        u"801edd61a8a74ed8b67f24bc355f6ecc", "behavior_pack_aRJYws6C", "resources",
    )
    if os.path.isdir(real_root):
        lifecycle.clear()
        lifecycle.register_modpack(real_root)
        real = lifecycle.load_one("manaita_plus_legacy", verbose=False)
        real_plan = real.inject_plan

        check(u"真实包贴图数 > 100", real_plan.count(inject.KIND_TEXTURE) > 100,
              real_plan.count(inject.KIND_TEXTURE))
        check(u"真实包模型数 > 50", real_plan.count(inject.KIND_MODEL) > 50,
              real_plan.count(inject.KIND_MODEL))
        check(u"真实包配方数 > 50", real_plan.count(inject.KIND_RECIPE) > 50,
              real_plan.count(inject.KIND_RECIPE))
        check(u"真实包语言文件 3 个", real_plan.count(inject.KIND_LANG) == 3,
              real_plan.count(inject.KIND_LANG))
        check(u"真实包着色器被识别",
              real_plan.count(inject.KIND_SHADER) >= 1, real_plan.count(inject.KIND_SHADER))
        check(u"真实包 .cache 被跳过", u".cache" in real_plan.skipped_dirs,
              real_plan.skipped_dirs)

        # 两个口径必须一致：注入计划与资源清单都跳过 .cache
        check(u"计划条目数与资源清单总数一致（都跳过 .cache）",
              real_plan.total_files == real.resources.total_files,
              u"计划 {} vs 清单 {}".format(real_plan.total_files,
                                        real.resources.total_files))

        # 独立复核：手工排除 .cache 再数一遍，确认不是两边一起算错
        manual = 0
        for root, dirs, files in os.walk(real.mod_dir):
            dirs[:] = [d for d in dirs if d not in (".cache", ".git", "__pycache__")]
            manual += len(files)
        check(u"独立复核：计划条目数 = 手工排除 .cache 后的文件数",
              real_plan.total_files == manual,
              u"{} vs {}".format(real_plan.total_files, manual))

        print(u"")
        print(u"  --- 真实模组包注入计划 ---")
        for line in real_plan.summary_lines()[:12]:
            print(u"  " + line)
    else:
        print(u"  [SKIP] 真实模组包不在预期位置")

finally:
    shutil.rmtree(workdir, ignore_errors=True)

sys.exit(summary())

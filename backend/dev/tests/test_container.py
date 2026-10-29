# -*- coding: utf-8 -*-
"""
容器层自测：container/mod_instance.py + container/lifecycle.py

验证点：
  1. ModInstance：元数据归类、路径推导、资源清单统计
  2. 状态与阶段记录：ok / warn / fail / skip 的语义
  3. 生命周期：正常包走到「已加载」，坏包走到「失败」并指出卡在哪一步
  4. 告警不影响结论：没有 assets / 没有 sen 只记告警，仍算加载成功
  5. 批量加载、卸载、清空
  6. 真实模组包上的端到端校验（只读）
"""

import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary, make_sample_modpack  # noqa: E402

pkg = Package()

# 先加载容器层：它自己会把 core/ 放进 sys.path
lifecycle = pkg.load("container.lifecycle")
mod_instance = pkg.load("container.mod_instance")

ModInstance = mod_instance.ModInstance
ModState = mod_instance.ModState
StageState = mod_instance.StageState

workdir = pkg.temp_dir()


def write_text(path, text):
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as fp:
        fp.write(text)


def add_code(mod_dir, files):
    """在模组包里造出翻译后的代码文件。"""
    for rel in files:
        write_text(os.path.join(mod_dir, *rel.split(u"/")), u"# -*- coding: utf-8 -*-\n")


def add_texture(mod_dir, rel):
    """在模组包里造一个贴图文件（内容无所谓，只验证链路）。"""
    path = os.path.join(mod_dir, *rel.split(u"/"))
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "wb") as fp:
        fp.write(b"PNG")


try:
    # ------------------------------------------------------------
    section("模组实例：元数据与路径")
    # ------------------------------------------------------------
    pack = make_sample_modpack(workdir, mod_id=u"inst_demo")
    info, error = pkg.load("core.alpha_neoforge").scan_resources_folder(pack)
    check(u"前置：扫描成功", error is None, error)

    inst = ModInstance(info)
    check(u"mod_id 取自 modId", inst.mod_id == "inst_demo", inst.mod_id)
    check(u"初始状态为已发现", inst.state == ModState.DISCOVERED, inst.state)
    check(u"mod_dir 推导正确", inst.mod_dir == pack, inst.mod_dir)
    check(u"label 带显示名", u"DemoManaita" in inst.label(), inst.label())

    check(u"sub_path 用斜杠取路径",
          inst.sub_path("assets/demo/lang/zh_cn.json")
          == os.path.join(pack, "assets", "demo", "lang", "zh_cn.json"),
          inst.sub_path("assets/demo/lang/zh_cn.json"))
    check(u"path_of 用元组取路径",
          inst.path_of("META-INF", "neoforge.mods.toml")
          == os.path.join(pack, "META-INF", "neoforge.mods.toml"))

    # ------------------------------------------------------------
    section("资源清单统计")
    # ------------------------------------------------------------
    index = inst.resources
    check(u"统计到 assets 文件", index.count("assets") == 1, index.by_kind)
    check(u"统计到 data 文件", index.count("data") == 1, index.by_kind)
    check(u"统计到 META-INF 文件", index.count("META-INF") == 1, index.by_kind)
    check(u"没有 sen 时计数为 0", index.count("sen") == 0, index.by_kind)
    check(u"总文件数不为 0", index.total_files > 0, index.total_files)
    check(u"缺少项被记录", any(u"代码" in m for m in index.missing_kinds),
          index.missing_kinds)

    cached = inst.resources
    check(u"资源清单被缓存（同一对象）", cached is index)

    # .cache 目录必须被跳过
    write_text(os.path.join(pack, ".cache", "junk.bin"), u"x")
    inst.invalidate_resources()
    check(u".cache 目录不计入统计", inst.resources.total_files == index.total_files,
          u"{} -> {}".format(index.total_files, inst.resources.total_files))

    # ------------------------------------------------------------
    section("阶段记录语义")
    # ------------------------------------------------------------
    record_instance = ModInstance({"modId": "stage_demo"})
    ok_stage = record_instance.add_stage("a", u"阶段A")
    ok_stage.done(u"没问题")
    check(u"done 阶段 ok", ok_stage.ok is True)
    check(u"done 描述含通过", u"通过" in ok_stage.describe(), ok_stage.describe())

    warn_stage = record_instance.add_stage("b", u"阶段B")
    warn_stage.warn(u"缺东西")
    check(u"warn 阶段仍然 ok", warn_stage.ok is True, warn_stage.state)
    check(u"warn 状态是 warned", warn_stage.state == StageState.WARNED, warn_stage.state)

    fail_stage = record_instance.add_stage("c", u"阶段C")
    fail_stage.fail(u"坏了")
    check(u"fail 阶段不 ok", fail_stage.ok is False)
    check(u"failed_stages 抓到它", fail_stage in record_instance.failed_stages)
    check(u"warnings 抓到 warn 那条", warn_stage in record_instance.warnings)

    late_fail = record_instance.add_stage("d", u"阶段D")
    late_fail.fail(u"先失败")
    late_fail.warn(u"后告警")
    check(u"已失败的阶段不会被 warn 降级",
          late_fail.state == StageState.FAILED, late_fail.state)

    skip_stage = record_instance.add_stage("e", u"阶段E")
    skip_stage.skip(u"没实现")
    check(u"skip 阶段 ok", skip_stage.ok is True, skip_stage.state)

    # ------------------------------------------------------------
    section("生命周期：正常包")
    # ------------------------------------------------------------
    lifecycle.clear()

    good_pack = make_sample_modpack(os.path.join(workdir, "good"), mod_id=u"good_mod")
    add_code(good_pack, [u"sen/demo/ModMain.py", u"sen/demo/util/Helper.py"])
    add_texture(good_pack, u"assets/demo/textures/block/tex.png")

    result = lifecycle.register_modpack(good_pack)
    check(u"登记成功", result.get("success") is True, result)
    check(u"登记返回 instance", result.get("instance") is not None)
    check(u"容器计数为 1", lifecycle.get_container().count() == 1)

    loaded = lifecycle.load_one("good_mod", verbose=False)
    check(u"加载后状态为已加载", loaded.state == ModState.LOADED, loaded.state)
    check(u"is_loaded 为真", loaded.is_loaded is True)
    check(u"阶段数等于阶段表长度",
          len(loaded.stages) == len(lifecycle.STAGE_ORDER), len(loaded.stages))

    code_stage = [s for s in loaded.stages if s.key == lifecycle.STAGE_CODE][0]
    check(u"代码阶段通过并统计到 2 个 .py",
          code_stage.state == StageState.DONE and u"2 个 .py" in code_stage.messages[0],
          code_stage.describe())

    inject_stage = [s for s in loaded.stages if s.key == lifecycle.STAGE_INJECT][0]
    check(u"注入阶段产出了计划而不是跳过",
          inject_stage.state in (StageState.DONE, StageState.WARNED),
          inject_stage.describe())
    check(u"注入阶段报出了资源条目数",
          any(u"个资源条目" in m for m in inject_stage.messages), inject_stage.messages)

    # ------------------------------------------------------------
    section("生命周期：告警不致命")
    # ------------------------------------------------------------
    # 没有 sen、没有 data 的包，只该告警，仍然加载成功
    bare_root = os.path.join(workdir, "bare", "resources")
    write_text(os.path.join(bare_root, "META-INF", "neoforge.mods.toml"),
               u'[[mods]]\nmodId="bare_mod"\nversion="1.0"\n')
    write_text(os.path.join(bare_root, "assets", "x.json"), u"{}")

    bare_result = lifecycle.register_modpack(bare_root)
    bare = lifecycle.load_one("bare_mod", verbose=False)
    check(u"缺少 data / sen 仍然加载成功",
          bare.state == ModState.LOADED, bare.state)
    check(u"确实产生了告警", len(bare.warnings) >= 1,
          [s.describe() for s in bare.warnings])

    # ------------------------------------------------------------
    section("生命周期：坏包要指出卡在哪一步")
    # ------------------------------------------------------------
    # 情况一：登记的实例目录被删掉
    vanishing = make_sample_modpack(os.path.join(workdir, "vanish"), mod_id=u"vanish_mod")
    lifecycle.register_modpack(vanishing)
    shutil.rmtree(vanishing)
    vanished = lifecycle.load_one("vanish_mod", verbose=False)
    check(u"目录消失 -> 失败", vanished.state == ModState.FAILED, vanished.state)
    dir_stage = [s for s in vanished.stages if s.key == lifecycle.STAGE_DIR][0]
    check(u"失败点在「检查模组目录」", dir_stage.ok is False, dir_stage.describe())
    check(u"失败信息可读", any(u"不存在" in m for m in dir_stage.messages),
          dir_stage.messages)
    check(u"后续阶段被跳过而不是硬跑",
          all(s.state == StageState.SKIPPED for s in vanished.stages[1:]),
          [s.state for s in vanished.stages])
    check(u"失败的模组被 failed() 抓到", vanished in lifecycle.get_container().failed())

    # 情况二：toml 被改坏，modId 丢了
    broken_root = os.path.join(workdir, "broken", "resources")
    write_text(os.path.join(broken_root, "META-INF", "neoforge.mods.toml"),
               u'[[mods]]\nmodId="broken_mod"\n')
    lifecycle.register_modpack(broken_root)
    write_text(os.path.join(broken_root, "META-INF", "neoforge.mods.toml"),
               u'license="MIT"\n')
    broken = lifecycle.load_one("broken_mod", verbose=False)
    check(u"toml 丢掉 modId -> 失败", broken.state == ModState.FAILED, broken.state)
    manifest_stage = [s for s in broken.stages if s.key == lifecycle.STAGE_MANIFEST][0]
    check(u"失败点在「校验 mods.toml」", manifest_stage.ok is False,
          manifest_stage.describe())
    check(u"报出未声明 modId", any(u"modId" in m for m in manifest_stage.messages),
          manifest_stage.messages)

    # 情况三：目录在但没有 META-INF（路径指错了一层）
    empty_root = os.path.join(workdir, "empty_dir")
    os.makedirs(empty_root)
    inst_empty = ModInstance({"modId": "empty_mod", "packDir": empty_root,
                              "tomlPath": os.path.join(empty_root, "META-INF",
                                                       "neoforge.mods.toml")})
    record = inst_empty.add_stage(lifecycle.STAGE_DIR, u"检查模组目录")
    lifecycle.stage_dir(inst_empty, record)
    check(u"目录存在时该阶段通过", record.ok is True, record.describe())

    record2 = inst_empty.add_stage(lifecycle.STAGE_RESOURCES, u"检查资源结构")
    lifecycle.stage_resources(inst_empty, record2)
    check(u"空目录 -> 资源阶段失败", record2.ok is False, record2.describe())
    check(u"失败信息指出路径可疑",
          any(u"路径" in m for m in record2.messages), record2.messages)

    # ------------------------------------------------------------
    section("批量加载与清理")
    # ------------------------------------------------------------
    container = lifecycle.get_container()
    before = container.count()
    check(u"容器里已有多个模组", before >= 4, before)

    container.load_all(verbose=False)
    check(u"load_all 之后每个模组都有终态",
          all(inst.state in (ModState.LOADED, ModState.FAILED) for inst in container.all()),
          [inst.state for inst in container.all()])

    order = [inst.mod_id for inst in container.all()]
    check(u"保持登记顺序", order.index("good_mod") < order.index("bare_mod"), order)

    summary_lines = container.summary_lines()
    check(u"summary 至少一行", len(summary_lines) >= 1, summary_lines)

    container.unload_all()
    check(u"unload_all 后没有已加载的模组", container.loaded() == [],
          [inst.state for inst in container.all()])

    lifecycle.clear()
    check(u"clear 清空容器", container.count() == 0, container.count())
    check(u"clear 同时清空 α 层注册表",
          pkg.load("core.alpha_neoforge").get_mod_count() == 0)

    # ------------------------------------------------------------
    section("端到端：真实模组包（只读）")
    # ------------------------------------------------------------
    real_root = os.path.join(
        r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn",
        u"801edd61a8a74ed8b67f24bc355f6ecc", "behavior_pack_aRJYws6C", "resources",
    )
    if os.path.isdir(real_root):
        real_result = lifecycle.register_modpack(real_root)
        check(u"真实模组包登记成功", real_result.get("success") is True, real_result)

        real = lifecycle.load_one("manaita_plus_legacy", verbose=False)
        check(u"真实模组包走到已加载", real.state == ModState.LOADED, real.state)

        real_index = real.resources
        check(u"统计到真实 assets", real_index.count("assets") > 200, real_index.count("assets"))
        check(u"统计到真实 data", real_index.count("data") > 50, real_index.count("data"))
        check(u"统计到真实 sen 文件", real_index.count("sen") > 150, real_index.count("sen"))

        real_code = [s for s in real.stages if s.key == lifecycle.STAGE_CODE][0]
        check(u"真实包只有 .class，提示需要翻译",
              any(u"还没有 .py" in m for m in real_code.messages), real_code.messages)

        check(u"真实包版本正确", real.version == "0.1.0", real.version)

        print(u"")
        print(u"  --- 真实模组包状态报告 ---")
        for line in real.status_lines():
            print(u"  " + line)
    else:
        print(u"  [SKIP] 真实模组包不在预期位置")

finally:
    shutil.rmtree(workdir, ignore_errors=True)

sys.exit(summary())

# -*- coding: utf-8 -*-
"""
对外接口自测：core/接口.py

接口.py 是 α 层暴露给**其他附加包**的正式入口，
其他包只需要 `from 核心包.接口 import register_modpack` 就能用。
因此它的稳定性比内部函数更重要，必须单独验。

验证点：
  1. 模块能加载，且打印出的导入方式与实际链路一致
  2. 全部公开函数存在且被 __all__ 导出
  3. 接口转发到 α 层（注册、查询、计数、诊断）
  4. 转发不改变返回值语义（成功与各类失败的 error 码都能透出来）
  5. is_mod_loaded / get_mod_count 这类便利函数判断正确
  6. 失败路径不会抛异常（其他包拿到的永远是结构化返回值）
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary, make_sample_modpack  # noqa: E402

pkg = Package()

# 接口.py 位于 core/ 下，需要 core/ 在 sys.path 上才能被 import
pkg.load("core.alpha_neoforge")
api = pkg.load("core.接口")

workdir = pkg.temp_dir()

try:
    # ------------------------------------------------------------
    section("模块加载与导出")
    # ------------------------------------------------------------
    expected = [
        "register_modpack",
        "get_registered_modpacks",
        "find_modpack_by_id",
        "list_all_modpacks",
        "is_mod_loaded",
        "get_mod_count",
    ]

    for name in expected:
        check(u"接口导出 {}".format(name), hasattr(api, name))

    check(u"__all__ 与公开函数一致",
          sorted(api.__all__) == sorted(expected), api.__all__)

    # ------------------------------------------------------------
    section("注册：成功路径")
    # ------------------------------------------------------------
    api.register_modpack  # 触碰以确认是函数
    alpha = pkg.load("core.alpha_neoforge")
    alpha.clear_registry()

    pack = make_sample_modpack(workdir, mod_id=u"api_demo")
    result = api.register_modpack(pack)

    check(u"成功时 success=True", result["success"] is True, result)
    check(u"成功时 modId 正确", result["modId"] == "api_demo", result["modId"])
    check(u"成功时 error 为 None", result["error"] is None, result["error"])
    check(u"成功时带 path", result["path"] == pack, result["path"])

    # ------------------------------------------------------------
    section("注册：失败路径必须结构化返回")
    # ------------------------------------------------------------
    missing = api.register_modpack(os.path.join(workdir, "nope"))
    check(u"路径不存在不抛异常，返回字典", isinstance(missing, dict), type(missing))
    check(u"错误码透出 bad_path", missing["error"] == alpha.ERR_BAD_PATH, missing["error"])

    empty_root = os.path.join(workdir, "no_toml")
    os.makedirs(empty_root)
    no_toml = api.register_modpack(empty_root)
    check(u"无 toml 错误码透出 no_toml",
          no_toml["error"] == alpha.ERR_NO_TOML, no_toml["error"])

    broken_root = os.path.join(workdir, "broken")
    meta = os.path.join(broken_root, "META-INF")
    os.makedirs(meta)
    with open(os.path.join(meta, "neoforge.mods.toml"), "wb") as fp:
        fp.write(b'license="MIT"\n')
    broken = api.register_modpack(broken_root)
    check(u"无 modId 错误码透出 no_mod_id",
          broken["error"] == alpha.ERR_NO_MOD_ID, broken["error"])

    check(u"空路径也走结构化返回",
          api.register_modpack("").get("error") == alpha.ERR_BAD_PATH)

    # ------------------------------------------------------------
    section("查询接口")
    # ------------------------------------------------------------
    packs = api.get_registered_modpacks()
    check(u"get_registered_modpacks 拿到已注册项", "api_demo" in packs, sorted(packs))

    found = api.find_modpack_by_id("api_demo")
    check(u"find_modpack_by_id 命中", found is not None and found["modId"] == "api_demo")
    check(u"find_modpack_by_id 未命中返回 None",
          api.find_modpack_by_id("ghost") is None)

    check(u"is_mod_loaded 对已注册返回 True", api.is_mod_loaded("api_demo") is True)
    check(u"is_mod_loaded 对未注册返回 False",
          api.is_mod_loaded("ghost") is False)

    check(u"get_mod_count 计数正确", api.get_mod_count() == 1, api.get_mod_count())

    # 复制语义：外部改动不影响内部
    packs["injected"] = {"modId": "injected"}
    check(u"get_registered_modpacks 返回副本",
          "injected" not in api.get_registered_modpacks())

    # ------------------------------------------------------------
    section("诊断：list_all_modpacks 不抛异常")
    # ------------------------------------------------------------
    # 自测脚本跑在本机 Python 3 上，一律用 `except X as e` 写法；
    # 核心包源码才需要 Py2 的 `except X, e`
    try:
        api.list_all_modpacks()
        listed = True
        list_error = None
    except Exception as error:
        listed = False
        list_error = error
    check(u"list_all_modpacks 对已注册模组不抛异常", listed, list_error)

    alpha.clear_registry()
    try:
        api.list_all_modpacks()
        empty_listed = True
        empty_error = None
    except Exception as error:
        empty_listed = False
        empty_error = error
    check(u"list_all_modpacks 对空注册表不抛异常", empty_listed, empty_error)

    check(u"清空后计数为 0", api.get_mod_count() == 0, api.get_mod_count())

    # ------------------------------------------------------------
    section("多模组场景")
    # ------------------------------------------------------------
    first = make_sample_modpack(os.path.join(workdir, "m1"), mod_id=u"mod_one")
    second = make_sample_modpack(os.path.join(workdir, "m2"), mod_id=u"mod_two")

    api.register_modpack(first)
    api.register_modpack(second)

    check(u"两个模组都注册成功", api.get_mod_count() == 2, api.get_mod_count())
    check(u"第一个可查到", api.is_mod_loaded("mod_one") is True)
    check(u"第二个可查到", api.is_mod_loaded("mod_two") is True)
    check(u"两个 ID 都能取到元数据",
          api.find_modpack_by_id("mod_one") is not None
          and api.find_modpack_by_id("mod_two") is not None)

    # 覆盖注册不该让计数增长
    api.register_modpack(first)
    check(u"重复注册不增加计数", api.get_mod_count() == 2, api.get_mod_count())

    # ------------------------------------------------------------
    section("真实模组包（只读）")
    # ------------------------------------------------------------
    real_root = os.path.join(
        r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn",
        u"801edd61a8a74ed8b67f24bc355f6ecc", "behavior_pack_aRJYws6C", "resources",
    )
    if os.path.isdir(real_root):
        alpha.clear_registry()
        real = api.register_modpack(real_root)
        check(u"真实模组包经接口注册成功", real["success"] is True, real)
        check(u"真实模组包 modId 正确",
              real["modId"] == "manaita_plus_legacy", real["modId"])
        check(u"真实模组包 is_mod_loaded 为真",
              api.is_mod_loaded("manaita_plus_legacy") is True)
        check(u"真实模组包版本可从接口取到",
              api.find_modpack_by_id("manaita_plus_legacy")["version"] == "0.1.0")
    else:
        print(u"  [SKIP] 真实模组包不在预期位置")

finally:
    shutil.rmtree(workdir, ignore_errors=True)

sys.exit(summary())

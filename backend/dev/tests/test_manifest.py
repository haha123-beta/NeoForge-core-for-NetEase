# -*- coding: utf-8 -*-
"""NetEase Python package checks.

Primary reference: installed MCStudio data/demo/UIDemoMod/uidemoBehaviorPack
and PresetAwesomeMod/awesomeBehaviorPack_bd89fc3d manifests use data only.
Python entry discovery uses the Scripts package and Mod.Binding; do not
encode an international Bedrock JavaScript runtime declaration for Python.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (  # noqa: E402
    Package, section, check, summary, PACK_ROOT, SCRIPTS_ROOT, SCRIPT_FOLDER_NAME,
)

pkg = Package()
manifest_path = os.path.join(PACK_ROOT, "manifest.json")
entry_path = os.path.join(SCRIPTS_ROOT, "modMain.py")


def load_manifest(path):
    with io.open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


try:
    # ------------------------------------------------------------
    section("清单文件存在且合法")
    # ------------------------------------------------------------
    check(u"manifest.json 存在", os.path.isfile(manifest_path), manifest_path)

    data = None
    parse_error = None
    try:
        data = load_manifest(manifest_path)
    except Exception as error:
        parse_error = error
    check(u"manifest.json 是合法 JSON", data is not None, parse_error)

    if data:
        header = data.get("header") or {}

        check(u"format_version 存在", "format_version" in data, list(data.keys()))
        for field in ("name", "uuid", "version", "min_engine_version"):
            check(u"header.{} 存在".format(field), field in header, list(header.keys()))

        check(u"header.name 是中文可读的",
              isinstance(header.get("name"), type(u"")),
              repr(header.get("name")))

        # ------------------------------------------------------------
        section("NetEase Python discovery")
        modules = data.get("modules") or []
        types = [module.get("type") for module in modules]
        check(u"存在 data 模块", "data" in types, types)
        check(u"Python 不声明国际版 script runtime", "script" not in types, types)
        check(u"Scripts/modMain.py 存在", os.path.isfile(entry_path), entry_path)
        init_path = os.path.join(SCRIPTS_ROOT, "__init__.py")
        if os.path.isfile(init_path):
            with open(init_path, "rb") as init_file:
                check(u"包入口没有空字节", b"\x00" not in init_file.read())

        # ------------------------------------------------------------
        section("uuid 唯一性")
        # ------------------------------------------------------------
        uuids = [header.get("uuid")] + [m.get("uuid") for m in modules]
        uuids = [u for u in uuids if u]
        lowered = [u.lower() for u in uuids]
        check(u"所有 uuid 互不重复", len(lowered) == len(set(lowered)), uuids)
        check(u"每个模块都有 uuid",
              all(m.get("uuid") for m in modules), modules)

    # ------------------------------------------------------------
    section("官方要求：脚本必须在 Scripts 子文件夹里")
    # ------------------------------------------------------------
    # 官方原文：「该文件必须放在 Scripts（脚本）文件夹下，否则会导致 Mod 在手机端失效」
    check(u"存在脚本文件夹 {}".format(SCRIPT_FOLDER_NAME),
          os.path.isdir(SCRIPTS_ROOT), SCRIPTS_ROOT)
    check(u"modMain.py 在脚本文件夹内", os.path.isfile(entry_path), entry_path)
    check(u"脚本文件夹有 __init__.py（是包的标识）",
          os.path.isfile(os.path.join(SCRIPTS_ROOT, "__init__.py")))
    check(u"包根不再直接放 modMain.py（避免旧布局残留）",
          not os.path.isfile(os.path.join(PACK_ROOT, "modMain.py")))

    # ------------------------------------------------------------
    section("入口脚本与核心包结构")
    # ------------------------------------------------------------
    # 引擎把脚本文件夹放进 sys.path，所以 core/xxx.py 要能以 core.xxx 导入
    for name, rel in (
        ("core 目录", "core"),
        ("container 目录", "container"),
        ("java_stdlib 目录", "java_stdlib"),
        ("alpha_neoforge.py", "core/alpha_neoforge.py"),
        ("injector.py", "core/injector.py"),
        ("接口.py", "core/接口.py"),
        ("mod_instance.py", "container/mod_instance.py"),
        ("lifecycle.py", "container/lifecycle.py"),
    ):
        check(u"{} 存在于脚本文件夹内".format(name),
              os.path.exists(os.path.join(SCRIPTS_ROOT, rel)), rel)

    # 各层都要能点分导入（脚本文件夹是 import 根）
    check(u"core.alpha_neoforge 可导入", pkg.locate("core.alpha_neoforge") is not None)
    check(u"container.mod_instance 可导入",
          pkg.locate("container.mod_instance") is not None)

    # ------------------------------------------------------------
    section("测试附加包（另一个包）的清单")
    # ------------------------------------------------------------
    test_pack = os.path.join(
        r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn",
        u"801edd61a8a74ed8b67f24bc355f6ecc", "behavior_pack_aRJYws6C", "manifest.json",
    )
    if os.path.isfile(test_pack):
        test_data = load_manifest(test_pack)
        test_types = [m.get("type") for m in test_data.get("modules") or []]
        check(u"测试包 manifest 合法", isinstance(test_data, dict))
        check(u"网易测试包不声明国际版 script runtime",
              "script" not in test_types, test_types)
    else:
        print(u"  [SKIP] 测试附加包不在预期位置")

finally:
    pass

sys.exit(summary())

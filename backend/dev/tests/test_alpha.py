# -*- coding: utf-8 -*-
"""
α 层自测：core/alpha_neoforge.py（模组发现）

验证点：
  1. TOML 解析：modId / version / displayName / description / authors / license / [[mods]]
  2. 递归扫描：META-INF 藏在子目录里也能找到
  3. 注册成功：返回值结构、全局存储
  4. 异常路径：路径不存在、没有 toml、toml 里没有 modId —— 且错误码必须分得开
  5. 重复注册：同 modId 覆盖而不是报错
  6. 查询接口：find / list / copy 语义（返回副本，外部改动不影响内部）
  7. 真实场景：含中文与空格的模组包路径
"""

import io
import os
import shutil
import sys

# 允许直接 `python dev/tests/test_*.py` 单跑：把 dev/ 放进 sys.path 才能 import harness
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary, make_sample_modpack, SAMPLE_TOML  # noqa: E402

pkg = Package()
alpha = pkg.load("core.alpha_neoforge")

workdir = pkg.temp_dir()


def write_text(path, text):
    """按 UTF-8 写文件，必要时建父目录。"""
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as fp:
        fp.write(text)


try:
    # ------------------------------------------------------------
    section("TOML 解析")
    # ------------------------------------------------------------
    info = alpha.parse_toml(SAMPLE_TOML)
    check(u"modId 解析正确", info["modId"] == "demo_manaita", info["modId"])
    check(u"version 解析正确", info["version"] == "0.1.0", info["version"])
    check(u"displayName 解析正确", info["displayName"] == "DemoManaita", info["displayName"])
    check(u"description 解析正确",
          info["description"] == "A tiny fixture mod used by the local self-test.",
          info["description"])
    check(u"authors 拆成列表", info["authors"] == ["tester"], info["authors"])
    check(u"license 解析正确", info["license"] == "MIT License", info["license"])
    check(u"[[mods]] 解析出 1 个子模组", len(info["mods"]) == 1, len(info["mods"]))
    check(u"tomlModIds 保序记录",
          info["tomlModIds"] == ["demo_manaita"], info["tomlModIds"])
    check(u"无解析错误", info["errors"] == [], info["errors"])

    quote_info = alpha.parse_toml(u"[[mods]]\nmodId='single_quote'\n")
    check(u"单引号值也能解析", quote_info["modId"] == "single_quote", quote_info["modId"])

    comment_info = alpha.parse_toml(u'# modId="ghost"\n' + SAMPLE_TOML)
    check(u"整行注释不参与解析", comment_info["modId"] == "demo_manaita", comment_info["modId"])

    inline_comment = alpha.parse_toml(
        u'[[mods]]\nmodId="live" # 这是行尾注释\nversion="1.0" # 注释\n'
    )
    check(u"行尾注释被剥掉", inline_comment["modId"] == "live", inline_comment["modId"])
    check(u"行尾注释不影响后续字段", inline_comment["version"] == "1.0", inline_comment["version"])

    multi = alpha.parse_toml(
        u'[[mods]]\nmodId="first"\nversion="1.0"\n\n[[mods]]\nmodId="second"\nversion="2.0"\n'
    )
    check(u"多个 [[mods]] 块全部解析", len(multi["mods"]) == 2, len(multi["mods"]))
    check(u"tomlModIds 记录两个 ID",
          multi["tomlModIds"] == ["first", "second"], multi["tomlModIds"])

    # ------------------------------------------------------------
    section("多行字符串与其它 TOML 值类型")
    # ------------------------------------------------------------
    triple = alpha.parse_toml(
        u'[[mods]]\n'
        u'modId="triple"\n'
        u"description='''\n"
        u"A replica mod that makes a manaita_plus\n"
        u"from 1.7.10 into 1.20.1.\n"
        u"'''\n"
        u'\n'
        u'# 下面是无关节，不应污染顶层\n'
        u'[library]\n'
        u'modId="library_ghost"\n'
    )
    check(u"三引号单引号多行字符串可解析",
          triple["description"] is not None
          and u"replica mod" in triple["description"],
          repr(triple["description"]))
    check(u"多行字符串保留换行",
          triple["description"] is not None and u"\n" in triple["description"],
          repr(triple["description"]))
    check(u"多行字符串不吞掉 [[mods]] 的 modId",
          triple["modId"] == "triple", triple["modId"])
    check(u"[library] 节里的同名键不污染顶层 modId",
          triple["modId"] != "library_ghost", triple["modId"])

    triple_dq = alpha.parse_toml(
        u'[[mods]]\nmodId="dq"\ndescription="""line1\nline2"""\n'
    )
    check(u'三引号双引号多行字符串可解析',
          triple_dq["description"] == u"line1\nline2", repr(triple_dq["description"]))

    typed = alpha.parse_toml(
        u'[[mods]]\n'
        u'modId="typed"\n'
        u'order=7\n'
        u'ratio=1.5\n'
        u'enabled=true\n'
        u'authors=["a", "b"]\n'
    )
    check(u"整数解析", typed["mods"][0]["order"] == 7, repr(typed["mods"][0].get("order")))
    check(u"浮点解析", typed["mods"][0]["ratio"] == 1.5, repr(typed["mods"][0].get("ratio")))
    check(u"布尔解析", typed["mods"][0]["enabled"] is True,
          repr(typed["mods"][0].get("enabled")))
    check(u"authors 支持数组写法", typed["authors"] == ["a", "b"], typed["authors"])

    dots = alpha.parse_toml(u'[[mods]]\nmodId="dotted"\ndep.modId="neoforge"\n')
    check(u"点号键取最后一段",
          dots["mods"][0].get("modId") == "neoforge", repr(dots["mods"][0]))

    # 真实模组的行尾注释形态：节头带注释、值带注释
    commented = alpha.parse_toml(
        u'[[mods]] #mandatory\n'
        u'modId="commented" #mandatory\n'
        u'version="0.1.0" # optional\n'
        u'    type="required" #mandatory\n'
    )
    check(u"节头带行尾注释仍能识别",
          commented["modId"] == "commented", commented["modId"])
    check(u"值带行尾注释仍能解析",
          commented["version"] == "0.1.0", repr(commented["version"]))
    check(u"带注释的 toml 无解析错误", commented["errors"] == [], commented["errors"])

    # authors 写在 [[mods]] 块里（真实模组常见写法）也要能读到
    block_authors = alpha.parse_toml(
        u'[[mods]]\nmodId="ba"\nauthors="alice, bob"\n'
    )
    check(u"[[mods]] 块内的 authors 也能读出",
          block_authors["authors"] == ["alice", "bob"], block_authors["authors"])

    comment_hash = alpha.parse_toml(u'[[mods]]\nmodId="hash" # 带#的注释\ndisplayName="x"\n')
    check(u"行尾注释不误伤后续行",
          comment_hash["mods"][0].get("displayName") == "x", repr(comment_hash["mods"][0]))

    hash_in_string = alpha.parse_toml(u'[[mods]]\nmodId="ok"\ndisplayName="a#b"\n')
    check(u"字符串内的 # 不当注释",
          hash_in_string["mods"][0].get("displayName") == "a#b",
          repr(hash_in_string["mods"][0]))

    # 真实模组包的坑：末尾的 [dependencies.<modid>] 里也有 modId，
    # 且 [[mods]] 块在 [dependencies] 之前 —— 块必须赢
    dep_toml = (
        u'license="MIT License"\n'
        u'\n'
        u'[[mods]]\n'
        u'modId="real_mod"\n'
        u'version="0.1.0"\n'
        u'displayName="RealMod"\n'
        u'\n'
        u'[[dependencies.real_mod]]\n'
        u'    modId="neoforge"\n'
        u'    type="required"\n'
        u'\n'
        u'[[dependencies.real_mod]]\n'
        u'    modId="minecraft"\n'
        u'    type="required"\n'
    )
    dep_info = alpha.parse_toml(dep_toml)
    check(u"[[mods]] 块的 modId 胜过 [dependencies] 里的同名键",
          dep_info["modId"] == "real_mod", dep_info["modId"])
    check(u"[dependencies] 不会新增 [[mods]] 块",
          len(dep_info["mods"]) == 1, len(dep_info["mods"]))
    check(u"tomlModIds 只记模组自己的 ID",
          dep_info["tomlModIds"] == ["real_mod"], dep_info["tomlModIds"])
    check(u"dep_toml 的顶层 license 仍可读",
          dep_info["license"] == "MIT License", dep_info["license"])

    # ------------------------------------------------------------
    section("递归扫描")
    # ------------------------------------------------------------
    pack_root = make_sample_modpack(workdir, nested=True)
    check(u"fixture 的 toml 在子目录里",
          os.path.isfile(os.path.join(pack_root, "META-INF", "neoforge.mods.toml")))

    scan_info, scan_error = alpha.scan_resources_folder(pack_root)
    check(u"递归扫到 toml（非顶层目录）", scan_error is None, scan_error)
    check(u"扫描结果带 resourcesPath",
          scan_info and scan_info["resourcesPath"] == pack_root,
          scan_info and scan_info.get("resourcesPath"))
    check(u"扫描结果带 tomlPath",
          scan_info and scan_info["tomlPath"].endswith("neoforge.mods.toml"))
    check(u"扫描结果带 packDir（toml 的上两级）",
          scan_info and scan_info["packDir"] == pack_root,
          scan_info and scan_info.get("packDir"))

    # ------------------------------------------------------------
    section("注册")
    # ------------------------------------------------------------
    result = alpha.register_modpack(pack_root)
    check(u"注册返回 success=True", result["success"] is True, result)
    check(u"注册返回的 modId 正确", result["modId"] == "demo_manaita", result["modId"])
    check(u"注册成功时 error 为 None", result["error"] is None, result["error"])
    check(u"注册返回原样回传 path", result["path"] == pack_root, result["path"])
    check(u"info 里带上 resourcesPath",
          result["info"]["resourcesPath"] == pack_root, result["info"].get("resourcesPath"))

    stored = alpha.get_registered_modpacks()
    check(u"全局存储已记录该模组", "demo_manaita" in stored, sorted(stored))
    check(u"get_mod_count 计数正确", alpha.get_mod_count() == 1, alpha.get_mod_count())

    # ------------------------------------------------------------
    section("查询接口")
    # ------------------------------------------------------------
    found = alpha.find_modpack_by_id("demo_manaita")
    check(u"find_modpack_by_id 命中", found is not None and found["modId"] == "demo_manaita")
    check(u"find_modpack_by_id 未命中返回 None",
          alpha.find_modpack_by_id("not_exist") is None)

    snapshot = alpha.get_registered_modpacks()
    snapshot["injected"] = {"modId": "injected"}
    check(u"get_registered_modpacks 返回副本",
          "injected" not in alpha.get_registered_modpacks())

    # ------------------------------------------------------------
    section("异常路径（错误码必须分得开）")
    # ------------------------------------------------------------
    missing = alpha.register_modpack(os.path.join(workdir, "no_such_dir"))
    check(u"路径不存在 -> success=False", missing["success"] is False, missing)
    check(u"路径不存在 -> error=bad_path", missing["error"] == alpha.ERR_BAD_PATH, missing["error"])

    check(u"空路径 -> error=bad_path",
          alpha.register_modpack("")["error"] == alpha.ERR_BAD_PATH)

    a_file = os.path.join(workdir, "a_file.txt")
    write_text(a_file, u"not a directory")
    check(u"路径是文件 -> error=bad_path",
          alpha.register_modpack(a_file)["error"] == alpha.ERR_BAD_PATH)

    empty_dir = os.path.join(workdir, "empty_pack")
    os.makedirs(empty_dir)
    no_toml = alpha.register_modpack(empty_dir)
    check(u"没有 neoforge.mods.toml -> error=no_toml",
          no_toml["error"] == alpha.ERR_NO_TOML, no_toml["error"])
    check(u"没有 toml 时 message 可读",
          u"neoforge.mods.toml" in no_toml["message"], no_toml["message"])

    broken_root = os.path.join(workdir, "broken_pack")
    write_text(os.path.join(broken_root, "META-INF", "neoforge.mods.toml"),
               u'license="MIT"\ndisplayName="Nameless"\n')
    broken = alpha.register_modpack(broken_root)
    check(u"toml 里没有 modId -> error=no_mod_id",
          broken["error"] == alpha.ERR_NO_MOD_ID, broken["error"])
    check(u"与 no_toml 是不同的错误码",
          broken["error"] != no_toml["error"], broken["error"])
    check(u"失败时 info 为 None", broken["info"] is None, broken["info"])

    check(u"失败请求不污染注册表", alpha.get_mod_count() == 1, alpha.get_mod_count())

    # ------------------------------------------------------------
    section("重复注册与多模组")
    # ------------------------------------------------------------
    again = make_sample_modpack(os.path.join(workdir, "second"), mod_id=u"demo_manaita")
    before = alpha.get_mod_count()
    alpha.register_modpack(again)
    check(u"同 modId 重复注册是覆盖，不新增条目",
          alpha.get_mod_count() == before, u"{} -> {}".format(before, alpha.get_mod_count()))
    check(u"覆盖后指向新路径",
          alpha.find_modpack_by_id("demo_manaita")["resourcesPath"] == again)

    two_root = os.path.join(workdir, "two_mods")
    write_text(os.path.join(two_root, "META-INF", "neoforge.mods.toml"),
               u'[[mods]]\nmodId="alpha_mod"\nversion="1.0"\n\n'
               u'[[mods]]\nmodId="beta_mod"\nversion="2.0"\n')
    two = alpha.register_modpack(two_root)
    check(u"多模组包取第一个 modId", two["modId"] == "alpha_mod", two["modId"])
    check(u"多模组包给出提示", any(u"个模组" in w for w in two["info"]["errors"]),
          two["info"]["errors"])

    # ------------------------------------------------------------
    section("真实场景：中文与空格的模组包路径")
    # ------------------------------------------------------------
    # 关键：必须独占一个 resources 目录，
    # 否则 os.walk 可能先扫到别的包，测的就不是中文路径了
    cn_resources = os.path.join(workdir, "cn_case", "resources")
    cn_dir = os.path.join(cn_resources, u"【砧板传承】[NeoForge]ManaitaPlus Legacy-0.1.0")
    write_text(
        os.path.join(cn_dir, "META-INF", "neoforge.mods.toml"),
        u'modLoader="javafml"\n'
        u'license="MIT License"\n'
        u'[[mods]]\n'
        u'modId="manaita_plus_legacy"\n'
        u'version="0.1.0"\n'
        u'displayName="ManaitaPlusLegacy"\n'
        u'description="\u7827\u677f\u4f20\u627f"\n'
    )

    cn_result = alpha.register_modpack(cn_resources)
    check(u"含中文与空格的路径可注册", cn_result["success"] is True, cn_result)
    check(u"中文路径下解析出正确 modId",
          cn_result["modId"] == "manaita_plus_legacy", cn_result["modId"])
    check(u"中文 description 不乱码",
          cn_result["info"]["description"] == u"\u7827\u677f\u4f20\u627f",
          cn_result["info"]["description"])

    toml_path, err = alpha.find_toml_path(cn_resources)
    check(u"find_toml_path 能处理中文路径", err is None and toml_path is not None, err)

    # ------------------------------------------------------------
    section("编码：必须按 UTF-8 读，不能跟着系统默认编码走")
    # ------------------------------------------------------------
    cn_toml = os.path.join(cn_dir, "META-INF", "neoforge.mods.toml")
    raw_text = alpha.read_text_file(cn_toml)
    check(u"read_text_file 取出正确的中文", u"\u7827\u677f\u4f20\u627f" in raw_text,
          repr(raw_text))

    # 真实模组包（另一个附加包里的 砧板传承）——只读校验，不修改
    real_toml = os.path.join(
        r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn",
        u"801edd61a8a74ed8b67f24bc355f6ecc", "behavior_pack_aRJYws6C", "resources",
        u"【砧板传承】[NeoForge]ManaitaPlus Legacy-0.1.0", "META-INF", "neoforge.mods.toml",
    )
    if os.path.isfile(real_toml):
        real_info = alpha.parse_toml(alpha.read_text_file(real_toml))
        check(u"真实模组包解析出 modId",
              real_info["modId"] == "manaita_plus_legacy", real_info["modId"])
        check(u"真实模组包解析出版本", real_info["version"] == "0.1.0", real_info["version"])
        check(u"真实模组包解析出 displayName",
              real_info["displayName"] == "ManaitaPlusLegacy", real_info["displayName"])
        # 真实 toml 的 description 是多行字符串，且含重音字符 é
        check(u"真实模组包的三引号 description 被读到",
              real_info["description"] is not None
              and u"1.7.10" in real_info["description"],
              repr(real_info["description"])[:80])
        check(u"真实模组包解析出 license",
              real_info["license"] == "MIT License", real_info["license"])
        check(u"真实模组包的 modId 不是依赖名 minecraft",
              real_info["modId"] != "minecraft", real_info["modId"])
    else:
        print(u"  [SKIP] 真实模组包不在预期位置，跳过只读校验")

    # ------------------------------------------------------------
    section("清空注册表")
    # ------------------------------------------------------------
    alpha.clear_registry()
    check(u"clear_registry 清空", alpha.get_mod_count() == 0, alpha.get_mod_count())
    check(u"清空后查不到", alpha.find_modpack_by_id("demo_manaita") is None)

finally:
    shutil.rmtree(workdir, ignore_errors=True)

sys.exit(summary())

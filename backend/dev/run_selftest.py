# -*- coding: utf-8 -*-
"""
核心包本地自测入口。

在 behavior_pack_7k1k1i4l 目录下执行：

    python dev/run_selftest.py

流程：
  1. Py2 静态兼容性扫描（真实 Python 2.7 行为探针另行运行）
  2. 官方模块白名单扫描（只把核心路径的违规算作失败）
  3. 依次运行 dev/tests/ 下的每个 test_*.py 子进程
  4. 汇总结果，全部通过时退出码为 0

为什么用子进程：每个测试都会往 sys.modules 里塞伪造模块、
改动全局注册表，隔离执行才能保证先后顺序互不影响。
"""

import os
import subprocess
import sys
from validation_report import source_fingerprint, write_report

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_ROOT = os.path.join(DEV_ROOT, "tests")
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)

# 源码根 = 脚本文件夹（官方要求脚本放在 Scripts 子文件夹下）
SCRIPTS_ROOT = os.path.join(PACK_ROOT, "NeoForgeCoreScripts")
if not os.path.isdir(SCRIPTS_ROOT):
    SCRIPTS_ROOT = PACK_ROOT

# 核心包的分层目录：单一来源在 dev/layers.py。
# 以前这里、py3only_lint、whitelist_lint 各写一份，漂移过两次导致漏检
# （漏掉 modMain.py 里的 Py2 不兼容写法、漏掉 neoforge/ 的新代码）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layers import LAYER_DIRS  # noqa: E402


def run_py3only_lint():
    """Py2 兼容性扫描。返回问题列表（字符串）。"""
    sys.path.insert(0, DEV_ROOT)
    import py3only_lint

    print(u"=" * 60)
    print(u">>> Py2 兼容性扫描（Py3 专有写法）")
    print(u"=" * 60)

    checked, problems = py3only_lint.check_tree(SCRIPTS_ROOT, LAYER_DIRS)
    print(u"检查了 {} 个文件".format(checked))

    if not problems:
        print(u"未发现已知的 Py3 专有写法")
        return []

    for filename, line_no, name, description, original in problems:
        print(u"  [命中] {}:{} [{}] {}".format(filename, line_no, name,
                                              description))
        print(u"         源码: {}".format(original))

    return [u"{}:{} [{}]".format(item[0], item[1], item[2]) for item in problems]


def run_whitelist_lint():
    """
    官方模块白名单扫描。

    只有**新增**违规才算失败：存量违规（α 层必需的 os 等）在白名单口径
    确认之前无法消除，一直判失败等于让这个检查失去意义。
    可选功能（标记 neocore:optional-io）单独报告，不阻断。
    """
    sys.path.insert(0, DEV_ROOT)
    import whitelist_lint

    print(u"=" * 60)
    print(u">>> 官方模块白名单扫描（只看新增违规）")
    print(u"=" * 60)

    checked, violations, optional_violations = whitelist_lint.check_tree(
        SCRIPTS_ROOT, LAYER_DIRS)
    known_debt, new_violations = whitelist_lint.split_by_debt(violations)

    print(u"检查了 {} 个文件".format(checked))
    print(u"已知债务 {} 处，新增违规 {} 处，可选功能 {} 处".format(
        len(known_debt), len(new_violations), len(optional_violations)))

    for rel, line_no, module, _note in new_violations:
        print(u"  [新增] {}:{} 使用 {}".format(rel, line_no, module))
    for rel, line_no, module, _note in optional_violations:
        print(u"  [可选] {}:{} 使用 {}".format(rel, line_no, module))

    if not new_violations:
        print(u"没有新增白名单违规")

    return [u"{}:{} 使用 {}".format(item[0], item[1], item[2])
            for item in new_violations]


def run_keyword_lint():
    """
    Java 方法名与 Python 关键字的冲突扫描。

    这类冲突会让翻译后的代码**无法解析**（`stack.is(x)` 是语法错误），
    属于最硬的约束，必须单列一项检查。
    """
    sys.path.insert(0, DEV_ROOT)
    import keyword_lint

    print(u"=" * 60)
    print(u">>> Java 方法名 / Python 关键字冲突扫描")
    print(u"=" * 60)

    # 核心包自己不能定义关键字函数名（会让文件无法解析）
    defs = keyword_lint.scan_python_for_keyword_defs(SCRIPTS_ROOT)
    if defs:
        print(u"  [严重] 核心包定义了关键字函数名：")
        for rel, line_no, name in defs:
            print(u"    {}:{}  def {}(".format(rel, line_no, name))
    else:
        print(u"  核心包未定义关键字函数名")

    # 反编译源码里的关键字方法调用
    addon_root = os.path.dirname(PACK_ROOT)
    decompiled_root = os.path.join(addon_root, "refs", "decompiled")
    unhandled = []
    if os.path.isdir(decompiled_root):
        found = keyword_lint.scan_java_for_keywords(decompiled_root)
        for name in sorted(found, key=lambda n: -len(found[n])):
            entries = found[name]
            handled = keyword_lint.RENAMED.get(name)
            print(u"  {} .{}()  {} 处".format(
                u"[已处理]" if handled else u"[待处理]", name, len(entries)))
            if handled:
                print(u"          {}".format(handled))
            else:
                unhandled.append(name)
    else:
        print(u"  未找到反编译源码，跳过 Java 侧扫描")

    return [u".{}() 尚未处理".format(name) for name in unhandled]


def run_api_coverage():
    """
    API 覆盖率度量。

    **只报告，不阻断** —— 覆盖率是进度指标，不是合格线。
    让它失败会变成「一直红着的检查」，反而失去意义。
    但模块加载失败是真问题（说明 JAVA_MAP 拿不到），那要阻断。
    """
    sys.path.insert(0, DEV_ROOT)
    import api_coverage

    print(u"=" * 60)
    print(u">>> API 覆盖率（只报告，不阻断）")
    print(u"=" * 60)

    root = api_coverage.find_decompiled_root()
    if root is None:
        print(u"  未找到反编译源码，跳过")
        return []

    imports = api_coverage.collect_imports(root)
    provided, modules_loaded, failures = api_coverage.collect_provided()

    needed = {}
    for java_name, count in imports.items():
        if not api_coverage.is_excluded(java_name):
            needed[java_name] = count

    covered = [n for n in needed if n in provided]
    skipped = [n for n in needed
               if n not in provided and n in api_coverage.DELIBERATELY_SKIPPED]
    missing = [n for n in needed
               if n not in provided
               and n not in api_coverage.DELIBERATELY_SKIPPED]

    total = len(needed)
    effective = len(covered) + len(skipped)
    print(u"  核心包 {} 个模块提供 {} 个 Java 名".format(len(modules_loaded),
                                                       len(provided)))
    print(u"  范围内需要 {} 种，已提供 {} 种，明确不做 {} 种".format(
        total, len(covered), len(skipped)))
    print(u"  有效覆盖 {:.1f}%，仍缺 {} 种".format(
        100.0 * effective / total if total else 0.0, len(missing)))

    print(u"  缺口前 5（下一步该做的）:")
    for java_name in sorted(missing,
                            key=lambda n: (-needed[n], n))[:5]:
        print(u"    {:>3} 个文件引用   {}".format(needed[java_name], java_name))

    if failures:
        for module_name, reason in failures:
            print(u"  [严重] 模块加载失败 {}: {}".format(module_name, reason))

    return [u"{} 加载失败: {}".format(name, reason)
            for name, reason in failures]


def discover():
    if not os.path.isdir(TESTS_ROOT):
        return []
    names = [n for n in sorted(os.listdir(TESTS_ROOT))
             if n.startswith("test_") and n.endswith(".py")]
    return [os.path.join(TESTS_ROOT, n) for n in names]


def main():
    tests = discover()
    report_path = os.path.join(DEV_ROOT, "validation_latest.json")
    before = source_fingerprint(PACK_ROOT)
    report = {"status": "RUNNING", "validation_modes": ["LOCAL_TESTED", "SIMULATED"],
        "engine_verified": False, "engine_verification_owner": "user",
        "python_version": sys.version, "python2_executed": sys.version_info[0] == 2,
        "test_files": [], "source_sha256": before,
        "fingerprint_scope": "Runtime/dev Python, tests/templates/examples/fixtures code and JSON/TOML, Java import index/parser pins and vendor Python/native binaries.",
        "limits": ["Static Python 2 scan and Python 3 harness do not prove Python 2 engine execution.",
            "Whitelist check allows recorded legacy debt; test count is not API completeness.",
            "Generated builds and external reference archives are outside this fingerprint."]}
    write_report(report_path, report)
    if not tests:
        report["status"] = "FAILED_NO_TESTS"
        write_report(report_path, report)
        print(u"没有找到任何测试：{}".format(TESTS_ROOT))
        return 1

    print(u"核心包自测 —— 共 {} 个测试文件".format(len(tests)))

    py2_problems = run_py3only_lint()
    whitelist_problems = run_whitelist_lint()
    keyword_problems = run_keyword_lint()
    coverage_problems = run_api_coverage()

    failed_files = []
    for path in tests:
        rel = os.path.relpath(path, DEV_ROOT)
        print(u"")
        print(u"=" * 60)
        print(u">>> {}".format(rel))
        print(u"=" * 60)
        proc = subprocess.Popen([sys.executable, path])
        proc.communicate()
        report["test_files"].append({"file": rel.replace("\\", "/"), "exit_code": proc.returncode})
        write_report(report_path, report)
        if proc.returncode != 0:
            failed_files.append(rel)

    after = source_fingerprint(PACK_ROOT)
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    report["changed_during_run"] = changed
    report["static_issues"] = {"python2_scan": [str(p) for p in py2_problems],
        "whitelist_new_violations": [str(p) for p in whitelist_problems],
        "keywords": [str(p) for p in keyword_problems],
        "coverage": [str(p) for p in coverage_problems]}
    report["status"] = "FAILED" if failed_files or any(report["static_issues"].values()) or changed else "PASSED"
    write_report(report_path, report)
    print(u"")
    print(u"=" * 60)
    if failed_files or py2_problems or whitelist_problems or keyword_problems \
            or coverage_problems or changed:
        print(u"自测失败（{} / {} 个测试文件）".format(len(failed_files),
                                                    len(tests)))
        for name in changed:
            print(u"  x Source changed during validation: " + name)
        for rel in failed_files:
            print(u"  x {}".format(rel))
        for problem in py2_problems:
            print(u"  x Py2 兼容性: {}".format(problem))
        for problem in whitelist_problems:
            print(u"  x 白名单（新增违规）: {}".format(problem))
        for problem in keyword_problems:
            print(u"  x 关键字冲突: {}".format(problem))
        for problem in coverage_problems:
            print(u"  x 覆盖率模块: {}".format(problem))
        print(u"=" * 60)
        return 1

    print(u"自测全部通过（{} 个测试文件）".format(len(tests)))
    print(u"=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

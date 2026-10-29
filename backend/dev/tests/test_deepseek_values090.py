# -*- coding: utf-8 -*-
"""DS-16 验收测试（第三轮允许新增：DEV/tests/test_deepseek_values090.py）。

覆盖：0.9.0 通用值语义接口（Functional ABI 9）的 JDK21 ↔ 真实 Python 2 对照矩阵、
上下文夹具（字段/局部/返回/参数/求值次数/异常顺序）、显式 unsupported/已知边界差异、
以及一次“活实现”复跑（不只读旧 JSON）。

运行：F:\\python.exe -B .\\tests\\test_deepseek_values090.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
WORK = DEV / "builds" / "deepseek_collaboration"
DS16 = WORK / "DS-16"
RUNNER = DS16 / "run_ds16.py"
IMPL = {
    "CORE/java_stdlib/_boxing.py":
        Path(r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn"
             r"\6b3fe067f88f49eab6964e94a9100d58\behavior_pack_7k1k1i4l"
             r"\NeoForgeCoreScripts\java_stdlib\_boxing.py"),
    "CORE/java_stdlib/function.py":
        Path(r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn"
             r"\6b3fe067f88f49eab6964e94a9100d58\behavior_pack_7k1k1i4l"
             r"\NeoForgeCoreScripts\java_stdlib\function.py"),
    "CORE/java_stdlib/lang.py":
        Path(r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn"
             r"\6b3fe067f88f49eab6964e94a9100d58\behavior_pack_7k1k1i4l"
             r"\NeoForgeCoreScripts\java_stdlib\lang.py"),
    "DEV/java_value_types.py": DEV / "java_value_types.py",
}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Values090Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = subprocess.run(
            [sys.executable, "-B", str(RUNNER), "validate"],
            cwd=str(DS16), capture_output=True, text=True, encoding="utf-8",
            errors="replace")

    def test_validate_passes(self):
        self.assertEqual(self.validate.returncode, 0,
                         self.validate.stdout + self.validate.stderr)

    def test_versions_and_implementation_sha_recorded(self):
        matrix = load_json(DS16 / "matrix.json")
        self.assertIn("21", matrix["jdk"]["version"])
        self.assertNotIn("error", matrix["jdk"]["version"].lower())
        self.assertTrue(str(matrix["python2"]["version"]).startswith("2.7"))
        self.assertTrue(matrix["python2"]["executed"])
        for name, path in IMPL.items():
            with self.subTest(name=name):
                self.assertEqual(matrix["implementation_sha256"][name],
                                 sha256_file(path))

    def test_documented_boundary_differences_explicit(self):
        matrix = load_json(DS16 / "matrix.json")
        self.assertTrue(matrix["all_classified"])
        self.assertEqual(matrix["unresolved_differences"], [])
        cases = {row["case"] for row in matrix["documented_differences"]}
        self.assertEqual(cases, {"cast.double_to_float.NaN",
                                 "cast.float_to_double.NaN"})
        for row in matrix["documented_differences"]:
            self.assertTrue(row["reason"])

    def test_context_generation_and_unsupported_explicit(self):
        matrix = load_json(DS16 / "contexts" / "matrix_context.json")
        self.assertTrue(matrix["all_classified"])
        self.assertEqual(matrix["unresolved"], [])
        unsupported = [row["case"] for row in matrix["case_results"]
                       if row["classification"] == "unsupported_generation"]
        self.assertEqual(sorted(unsupported),
                         ["ctx.box.equals.128", "ctx.box.identity.127",
                          "ctx.box.identity.128"])
        translate = load_json(DS16 / "logs" / "context_translate.json")
        self.assertEqual(translate["generated_for_review"], 3)
        self.assertEqual(translate["manual_review"], 1)
        self.assertIn("BoxIdentity.java",
                      [row["file"] for row in translate["results"]
                       if row["status"] == "MANUAL_REVIEW"])

    def test_live_python2_subset_matches_jdk(self):
        matrix = load_json(DS16 / "matrix.json")
        jdk = load_json(DS16 / "jdk" / "jdk_results.json")
        subset = {"box.Integer.127.identity", "box.Integer.128.identity",
                  "unbox.Integer.null", "cast.int_to_byte.-129",
                  "cast.float_to_int.NaN", "castRef.Integer.fromLong",
                  "isInstance.null.false", "cast.double_to_long.NaN"}
        with tempfile.TemporaryDirectory(prefix="ds16_live_") as folder:
            output = Path(folder) / "py2_subset.json"
            process = subprocess.run(
                [r"D:\NeoCore工具\python27_validation\runtime\python.exe",
                 "-B", str(DS16 / "tools" / "py2_api_probe.py"),
                 str(DS16 / "jdk" / "jdk_results.json"), str(output),
                 str(matrix["core_root"] if "core_root" in matrix else Path(
                     r"E:\MCStudioDownload\work\YOUR_ACCOUNT\Cpp\AddOn"
                     r"\6b3fe067f88f49eab6964e94a9100d58\behavior_pack_7k1k1i4l"
                     r"\NeoForgeCoreScripts"))],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(process.returncode, 0, process.stderr[-800:])
            live = load_json(output)
        for case in subset:
            expected = jdk["cases"][case]
            actual = live["cases"][case]
            with self.subTest(case=case):
                if case == "cast.float_to_int.NaN":
                    self.assertEqual(actual["value"], 0)
                    continue
                if expected["status"] == "EXC":
                    self.assertEqual(actual["value"], expected["value"])
                else:
                    self.assertEqual(str(actual["value"]), str(expected["value"]))

    def test_fixture_and_driver_sha_stable(self):
        baseline = load_json(DS16 / "baseline.json")
        self.assertEqual(baseline["context_driver_sha256"],
                         sha256_file(DS16 / "jdk" / "ContextDriver.java"))
        for name, sha in baseline["fixtures"].items():
            with self.subTest(fixture=name):
                self.assertEqual(sha, sha256_file(DS16 / "fixtures" / name))


if __name__ == "__main__":
    unittest.main(verbosity=2)


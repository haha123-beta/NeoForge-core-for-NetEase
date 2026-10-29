# -*- coding: utf-8 -*-
"""DS-11 静态签名验收测试（第 2 版 A11 允许新增的测试文件）。

覆盖：java.lang.System.nanoTime/currentTimeMillis 带 static_owner、零参数接受、
非零参数显式拒绝、其它 System 方法不变；DS-03 官方证据交叉核对。

运行：F:\\python.exe -B .\\tests\\test_deepseek_v2_static_signatures.py
"""
import json
import sys
import unittest
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
WORK = DEV / "builds" / "deepseek_collaboration"
sys.path.insert(0, str(DEV))

from java_world_signatures import resolve  # noqa: E402

DS03 = WORK / "DS-03"


class StaticSignatureTests(unittest.TestCase):
    def test_system_time_static_owner_and_zero_args(self):
        for name in ("nanoTime", "currentTimeMillis"):
            with self.subTest(name=name):
                row = resolve("java.lang.System", name, 0, [])
                self.assertIsNotNone(row)
                self.assertEqual(row["return_type"], "long")
                self.assertEqual(row["parameters"], [])
                self.assertEqual(row["receiver_kind"], "game_api")
                self.assertEqual(row["static_owner"], "java.lang.System")

    def test_system_time_nonzero_arity_rejected(self):
        for name in ("nanoTime", "currentTimeMillis"):
            for arity in (1, 2):
                with self.subTest(name=name, arity=arity):
                    with self.assertRaises(ValueError) as caught:
                        resolve("java.lang.System", name, arity, ["int"] * arity)
                    self.assertIn("System time API requires zero arguments", str(caught.exception))

    def test_other_system_methods_unchanged(self):
        for name in ("gc", "exit", "arraycopy", "getProperty", "currentTimeMillis2"):
            with self.subTest(name=name):
                self.assertIsNone(resolve("java.lang.System", name, 0, []))

    def test_ds03_official_evidence_cross_check(self):
        evidence = json.loads((DS03 / "official_evidence.json").read_text(encoding="utf-8"))
        for name in ("nanoTime", "currentTimeMillis"):
            row = evidence["methods"][name]
            self.assertEqual(row["descriptor"], "()J")
            self.assertTrue(row["static"])
            self.assertEqual(row["visibility"], "public")
            self.assertEqual(row["return_type"], "long")
            resolved = resolve("java.lang.System", name, 0, [])
            self.assertEqual(resolved["return_type"], row["return_type"])
            self.assertEqual(resolved["static_owner"], "java.lang.System")


if __name__ == "__main__":
    unittest.main(verbosity=2)

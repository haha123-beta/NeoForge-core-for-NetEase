# -*- coding: utf-8 -*-
"""DS-10 签名验收测试（第 2 版 A10 允许新增的测试文件）。

覆盖：UseOnContext 六个 getter 的官方 descriptor；BlockPlaceContext 通过已有继承关系
解析同名方法（不重复父子规则）；错误参数数量/错误 owner/未知方法拒绝。

运行：F:\\python.exe -B .\\tests\\test_deepseek_v2_context_signatures.py
"""
import json
import sys
import unittest
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
WORK = DEV / "builds" / "deepseek_collaboration"
sys.path.insert(0, str(DEV))

from java_official_type_hierarchy import PARENTS  # noqa: E402
from java_world_signatures import CONTEXT_GETTERS, resolve  # noqa: E402

USE_ON = "net.minecraft.world.item.context.UseOnContext"
BLOCK_PLACE = "net.minecraft.world.item.context.BlockPlaceContext"
DS10 = WORK / "DS-10"
OFFICIAL = DS10 / "official_evidence.json"
DESCRIPTORS = {
    "getLevel": "()Ldcw;",
    "getPlayer": "()Lcmx;",
    "getClickedPos": "()Ljd;",
    "getClickedFace": "()Lji;",
    "getItemInHand": "()Lcuq;",
    "getHand": "()Lbqq;",
}


def resolved(base, name, arity=0, actual=None):
    return resolve(base, name, arity, actual if actual is not None else [])


class ContextSignatureTests(unittest.TestCase):
    def test_inheritance_relation_present(self):
        self.assertEqual(PARENTS.get(BLOCK_PLACE), [USE_ON])

    def test_use_on_context_getters(self):
        for name, expected_return in CONTEXT_GETTERS.items():
            with self.subTest(name=name):
                row = resolved(USE_ON, name)
                self.assertIsNotNone(row)
                self.assertEqual(row["return_type"], expected_return)
                self.assertEqual(row["parameters"], [])
                self.assertEqual(row["receiver_kind"], "game_api")

    def test_block_place_context_inherits_same_getters(self):
        for name, expected_return in CONTEXT_GETTERS.items():
            with self.subTest(name=name):
                row = resolved(BLOCK_PLACE, name)
                self.assertIsNotNone(row)
                self.assertEqual(row["return_type"], expected_return)

    def test_wrong_arity_rejected(self):
        for name in CONTEXT_GETTERS:
            with self.subTest(name=name):
                # None means "unresolved" and permits the generic dynamic-call
                # fallback. A known API with wrong arity must fail explicitly.
                with self.assertRaises(ValueError):
                    resolved(USE_ON, name, arity=1)
                with self.assertRaises(ValueError):
                    resolved(BLOCK_PLACE, name, arity=2)

    def test_wrong_owner_rejected(self):
        for owner in ("net.minecraft.world.item.Item",
                      "net.minecraft.world.level.Level",
                      "net.minecraft.world.item.context.UseOnContext.Extra"):
            for name in CONTEXT_GETTERS:
                with self.subTest(owner=owner, name=name):
                    self.assertIsNone(resolved(owner, name))

    def test_unknown_method_rejected(self):
        for name in ("getClickLocation", "getHorizontalDirection", "getRotation",
                     "getHitResult", "isSecondaryUseActive", "getModId"):
            with self.subTest(name=name):
                self.assertIsNone(resolved(USE_ON, name))
                self.assertIsNone(resolved(BLOCK_PLACE, name))

    def test_official_evidence_matches_resolver(self):
        evidence = json.loads(OFFICIAL.read_text(encoding="utf-8"))
        self.assertTrue(evidence["reference"]["manifest_matches"])
        self.assertTrue(evidence["summary"]["all_expectations_ok"])
        self.assertEqual(sorted(evidence["summary"]["declared_in_UseOnContext"]),
                         sorted(CONTEXT_GETTERS))
        self.assertEqual(evidence["summary"]["overridden_in_BlockPlaceContext"],
                         ["getClickedPos"])
        for name, descriptor in DESCRIPTORS.items():
            with self.subTest(name=name):
                row = evidence["getters"][name][USE_ON]
                self.assertTrue(row["declared"])
                self.assertTrue(row["instance"])
                self.assertTrue(row["public"])
                self.assertTrue(row["zero_parameters"])
                self.assertEqual(row["descriptor"], descriptor)
                self.assertTrue(row["matches_expected_return"])
                self.assertEqual(resolved(USE_ON, name)["return_type"],
                                 CONTEXT_GETTERS[name])


if __name__ == "__main__":
    unittest.main(verbosity=2)


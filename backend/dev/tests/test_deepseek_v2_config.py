# -*- coding: utf-8 -*-
"""DS-07 配置化验收测试（第 2 版 A07 允许新增的测试文件）。

覆盖：
  * 默认配置使用正式路径（不静默退回其他项目副本）；
  * 从约定目录与任意临时目录运行，都使用明确配置的 DEV，且报告实际导入路径/参数来源；
  * 错误目录、缺解释器、Python 3 冒充 Python 2、配置指纹失配 → 显式失败；
  * 启动测试真正使用配置的 Python 2（不读取历史 python2_executed）；
  * 配置文件和 DS_* 环境变量覆盖被记录来源。

运行：F:\\python.exe -B .\\tests\\test_deepseek_v2_config.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
WORK = DEV / "builds" / "deepseek_collaboration"
sys.path.insert(0, str(WORK))

from ds_config import (ConfigError, DEFAULTS, load_config)  # noqa: E402

CONFIG_CLI = WORK / "ds_config.py"
ENV_KEYS = [name for name in os.environ if name.startswith("DS_")]


def clean_env(overrides=None):
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("DS_"):
            env.pop(name)
    env["PYTHONIOENCODING"] = "utf-8"
    if overrides:
        env.update(overrides)
    return env


def run_cli(cwd, env_overrides=None, extra_args=()):
    process = subprocess.run(
        [sys.executable, "-B", str(CONFIG_CLI), "--json"] + list(extra_args),
        cwd=str(cwd), env=clean_env(env_overrides), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return process


class ConfigSurfaceTests(unittest.TestCase):
    def test_defaults_are_formal_paths(self):
        config = load_config().validate()
        self.assertEqual(config.dev_root, r"D:\NeoCore工具\dev")
        self.assertEqual(config.python2, r"D:\NeoCore工具\python27_validation\runtime\python.exe")
        self.assertEqual(config.core_root, DEFAULTS["core_root"])
        for value in config.values.values():
            self.assertNotIn("副本", str(value),
                             "default config must not point at another project copy")
        self.assertEqual(set(config.sources.values()), {"default"})

    def test_cli_reports_sources_imports_and_python2_probe(self):
        process = run_cli(WORK)
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        for key in ("values", "sources", "python2_version", "python3_version",
                    "source_sha256", "fingerprint", "imports", "python2_probe"):
            self.assertIn(key, report)
        self.assertTrue(report["python2_probe"]["python2"])
        self.assertTrue(report["python2_probe"]["version"].startswith("2.7"))
        self.assertEqual(Path(report["imports"]["dev_root"]),
                         Path(DEFAULTS["dev_root"]))
        for name, path in report["imports"]["modules"].items():
            self.assertTrue(Path(path).is_relative_to(Path(DEFAULTS["dev_root"])),
                            "%s imported from %s" % (name, path))

    def test_run_from_any_temp_directory_uses_configured_dev(self):
        agreed = run_cli(WORK)
        self.assertEqual(agreed.returncode, 0, agreed.stderr)
        with tempfile.TemporaryDirectory(prefix="ds07_cwd_") as folder:
            elsewhere = run_cli(folder)
        self.assertEqual(elsewhere.returncode, 0, elsewhere.stderr)
        agreed_report = json.loads(agreed.stdout)
        elsewhere_report = json.loads(elsewhere.stdout)
        self.assertEqual(agreed_report["values"], elsewhere_report["values"])
        self.assertEqual(elsewhere_report["imports"]["dev_root"],
                         str(Path(DEFAULTS["dev_root"]).resolve()))
        self.assertFalse(elsewhere_report["imports"]["foreign_dev_entries"])

    def test_import_paths_are_explicit(self):
        config = load_config().validate()
        report = config.import_report()
        self.assertEqual(Path(report["dev_root"]), Path(DEFAULTS["dev_root"]))
        for name, path in report["modules"].items():
            with self.subTest(module=name):
                self.assertTrue(Path(path).is_relative_to(Path(config.dev_root)))

    def test_foreign_dev_copy_in_sys_path_is_rejected(self):
        foreign = Path(r"D:\NeoCore工具 - 副本\dev")
        config = load_config().validate()
        sys.path.insert(0, str(foreign))
        try:
            with self.assertRaises(ConfigError):
                config.import_report()
        finally:
            sys.path.remove(str(foreign))


class ConfigFailureTests(unittest.TestCase):
    def test_wrong_dev_directory_fails(self):
        with tempfile.TemporaryDirectory(prefix="ds07_wrong_") as folder:
            with self.assertRaises(ConfigError):
                load_config(overrides={"dev_root": folder}).validate()

    def test_missing_interpreter_fails(self):
        with tempfile.TemporaryDirectory(prefix="ds07_py_") as folder:
            missing = Path(folder) / "python.exe"
            with self.assertRaises(ConfigError):
                load_config(overrides={"python2": str(missing)}).validate()

    def test_python3_disguised_as_python2_fails(self):
        with self.assertRaises(ConfigError) as caught:
            load_config(overrides={"python2": sys.executable}).validate()
        self.assertIn("not Python 2.7", str(caught.exception))

    def test_python2_disguised_as_python3_fails(self):
        config = load_config().validate()
        with self.assertRaises(ConfigError) as caught:
            load_config(overrides={"python3": config.python2}).validate()
        self.assertIn("not Python 3", str(caught.exception))

    def test_missing_jdk_fails(self):
        with tempfile.TemporaryDirectory(prefix="ds07_jdk_") as folder:
            with self.assertRaises(ConfigError):
                load_config(overrides={"jdk_home": folder}).validate()

    def test_config_fingerprint_mismatch_fails(self):
        config = load_config().validate()
        fingerprint = config.fingerprint()
        tampered = ("0" if fingerprint[0] != "0" else "1") + fingerprint[1:]
        with self.assertRaises(ConfigError) as caught:
            config.verify_fingerprint(tampered)
        self.assertIn("fingerprint mismatch", str(caught.exception))
        self.assertEqual(config.verify_fingerprint(fingerprint), fingerprint)

    def test_cli_fails_on_wrong_dev_root(self):
        with tempfile.TemporaryDirectory(prefix="ds07_cli_") as folder:
            process = run_cli(WORK, {"DS_DEV_ROOT": folder})
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("CONFIG ERROR", process.stderr)
        self.assertNotIn("\"values\"", process.stdout)

    def test_cli_fails_on_python3_disguised_as_python2(self):
        process = run_cli(WORK, {"DS_PYTHON2": sys.executable})
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("not Python 2.7", process.stderr)


class ConfigSourceTests(unittest.TestCase):
    def test_config_file_overrides_are_recorded(self):
        with tempfile.TemporaryDirectory(prefix="ds07_file_") as folder:
            workspace = Path(folder) / "backend"
            config_path = Path(folder) / "config.json"
            config_path.write_text(json.dumps({"backend_workspace": str(workspace)}),
                                   encoding="utf-8")
            config = load_config(config_path=str(config_path)).validate()
        self.assertEqual(str(config.backend_workspace), str(workspace))
        self.assertTrue(config.sources["backend_workspace"].startswith("config-file:"))
        self.assertEqual(config.sources["dev_root"], "default")

    def test_unknown_config_key_fails(self):
        with tempfile.TemporaryDirectory(prefix="ds07_key_") as folder:
            config_path = Path(folder) / "config.json"
            config_path.write_text(json.dumps({"not_a_key": "x"}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(config_path=str(config_path))

    def test_env_override_is_recorded(self):
        with tempfile.TemporaryDirectory(prefix="ds07_env_") as folder:
            workspace = Path(folder) / "backend"
            os.environ["DS_BACKEND_WORKSPACE"] = str(workspace)
            try:
                config = load_config().validate()
            finally:
                os.environ.pop("DS_BACKEND_WORKSPACE", None)
        self.assertEqual(str(config.backend_workspace), str(workspace))
        self.assertEqual(config.sources["backend_workspace"],
                         "env:DS_BACKEND_WORKSPACE")

    def test_startup_probe_executes_configured_python2(self):
        config = load_config().validate()
        probe = config.python2_probe()
        self.assertTrue(probe["python2"])
        self.assertTrue(probe["version"].startswith("2.7"))
        direct = subprocess.run(
            [config.python2, "-B", "-c",
             "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(probe["version"], direct.stdout.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)

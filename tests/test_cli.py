"""CLI 测试（M3）：命令框架、读写、预设、备份恢复、诊断、启动与日志。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from totk_frontend import __version__, cli

DEFAULT_INI = """# 手写合成样本（不含游戏数据）
[frame rate]
fps_limit = 60
realtime = 1

[audio]
volume = 100
"""

COMMANDS = (
    "detect",
    "list",
    "get",
    "set",
    "unset",
    "preset",
    "apply",
    "backup",
    "restore",
    "doctor",
    "launch",
    "log",
    "version",
)

BACKUP_PATTERN = re.compile(r"^totk\.ini\.bak-\d{8}-\d{6}(-\d+)?$")


class CliTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.install = self.root / "TotK Recomp"
        self.install.mkdir()
        (self.install / "totk.exe").write_text("", encoding="utf-8")
        self.ini = self.install / "totk.ini"
        self.ini.write_text(DEFAULT_INI, encoding="utf-8")

    # ------------------------------------------------------------ 运行辅助
    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def run_exit(self, *argv: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                cli.main(list(argv))
        return int(caught.exception.code or 0), stdout.getvalue(), stderr.getvalue()

    def write_ini(self, text: str) -> None:
        self.ini.write_text(text, encoding="utf-8")

    def backups(self) -> list[Path]:
        return sorted(self.install.glob("totk.ini.bak-*"))

    def chdir(self, path: Path) -> None:
        previous = Path.cwd()
        os.chdir(path)
        self.addCleanup(os.chdir, previous)


class HelpTest(CliTestBase):
    def test_every_command_has_help(self) -> None:
        for command in COMMANDS:
            code, output, _ = self.run_exit(command, "--help")
            self.assertEqual(code, 0, command)
            self.assertIn("usage", output.lower(), command)

    def test_top_level_help_and_version(self) -> None:
        code, output, _ = self.run_exit("--help")
        self.assertEqual(code, 0)
        self.assertIn("TotK Frontend", output)
        code, output, _ = self.run_exit("--version")
        self.assertEqual(code, 0)
        self.assertIn(__version__, output)

    def test_missing_command_is_usage_error(self) -> None:
        code, _, _ = self.run_exit()
        self.assertEqual(code, 2)


class DetectCommandTest(CliTestBase):
    def test_complete_install(self) -> None:
        for name in ("totk-install.json",):
            (self.install / name).write_text("{}", encoding="utf-8")
        (self.install / "exefs").mkdir()
        (self.install / "romfs").mkdir()
        code, output, _ = self.run_cli("detect", "--dir", str(self.install))
        self.assertEqual(code, 0)
        self.assertIn("检测通过", output)
        self.assertIn("存在  totk.exe", output)
        self.assertIn("存在  exefs", output)

    def test_missing_markers(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, output, _ = self.run_cli("detect", "--dir", str(empty))
        self.assertEqual(code, 1)
        self.assertIn("缺失  totk.exe", output)
        self.assertIn("缺少必要标记", output)

    def test_auto_detects_from_install_directory(self) -> None:
        self.chdir(self.install)
        code, output, _ = self.run_cli("detect")
        self.assertEqual(code, 0)
        self.assertIn("检测通过", output)

    def test_no_install_directory(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        self.chdir(empty)
        code, output, _ = self.run_cli("detect")
        self.assertEqual(code, 1)
        self.assertIn("未检测到", output)


class ListCommandTest(CliTestBase):
    def test_lists_all_settings_with_source(self) -> None:
        code, output, _ = self.run_cli("list", "--dir", str(self.install))
        self.assertEqual(code, 0)
        self.assertIn("[frame rate] fps_limit = 60  (文件", output)
        self.assertIn("[audio] volume = 100  (文件", output)
        self.assertIn("[display] fov = 100  (默认", output)

    def test_section_filter(self) -> None:
        code, output, _ = self.run_cli("list", "--dir", str(self.install), "--section", "audio")
        self.assertEqual(code, 0)
        self.assertIn("[audio] volume", output)
        self.assertNotIn("[frame rate]", output)

    def test_unknown_section(self) -> None:
        code, _, stderr = self.run_cli("list", "--dir", str(self.install), "--section", "bogus")
        self.assertEqual(code, 1)
        self.assertIn("未知节", stderr)

    def test_missing_ini_uses_defaults(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, output, _ = self.run_cli("list", "--dir", str(empty))
        self.assertEqual(code, 0)
        self.assertIn("不存在，以下为默认值", output)
        self.assertIn("fps_limit = 60  (默认", output)


class GetCommandTest(CliTestBase):
    def test_get_from_file(self) -> None:
        code, output, _ = self.run_cli("get", "--dir", str(self.install), "volume")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "100")

    def test_get_default_value(self) -> None:
        code, output, _ = self.run_cli("get", "--dir", str(self.install), "fov")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "100")

    def test_get_case_insensitive(self) -> None:
        code, output, _ = self.run_cli("get", "--dir", str(self.install), "VOLUME")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "100")

    def test_unknown_key(self) -> None:
        code, _, stderr = self.run_cli("get", "--dir", str(self.install), "unknown_future_key")
        self.assertEqual(code, 1)
        self.assertIn("未知键", stderr)

    def test_missing_ini_falls_back_to_default(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, output, _ = self.run_cli("get", "--dir", str(empty), "volume")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "100")


class SetUnsetCommandTest(CliTestBase):
    def test_set_existing_key_creates_backup(self) -> None:
        code, output, _ = self.run_cli("set", "--dir", str(self.install), "volume", "80")
        self.assertEqual(code, 0)
        self.assertIn("已设置 volume = 80", output)
        self.assertIn("备份：", output)
        self.assertIn("volume = 80", self.ini.read_text(encoding="utf-8"))
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertRegex(backups[0].name, BACKUP_PATTERN)

    def test_set_rejects_invalid_value(self) -> None:
        before = self.ini.read_bytes()
        code, _, stderr = self.run_cli("set", "--dir", str(self.install), "volume", "200")
        self.assertEqual(code, 1)
        self.assertIn("错误", stderr)
        self.assertEqual(self.ini.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_set_rejects_unknown_key(self) -> None:
        code, _, stderr = self.run_cli("set", "--dir", str(self.install), "not_a_key", "1")
        self.assertEqual(code, 1)
        self.assertIn("未知键", stderr)

    def test_set_creates_missing_ini(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, output, _ = self.run_cli("set", "--dir", str(empty), "volume", "50")
        self.assertEqual(code, 0)
        created = empty / "totk.ini"
        self.assertTrue(created.exists())
        self.assertEqual(created.read_text(encoding="utf-8"), "[audio]\nvolume = 50\n")
        self.assertNotIn("备份：", output)

    def test_set_same_value_does_not_write(self) -> None:
        before = self.ini.read_bytes()
        code, output, _ = self.run_cli("set", "--dir", str(self.install), "volume", "100")
        self.assertEqual(code, 0)
        self.assertIn("值未变化", output)
        self.assertEqual(self.ini.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_unset_restores_default(self) -> None:
        code, output, _ = self.run_cli("unset", "--dir", str(self.install), "fps_limit")
        self.assertEqual(code, 0)
        self.assertIn("已恢复默认", output)
        self.assertNotIn("fps_limit", self.ini.read_text(encoding="utf-8"))
        code, output, _ = self.run_cli("get", "--dir", str(self.install), "fps_limit")
        self.assertEqual(output.strip(), "60")

    def test_unset_without_active_line(self) -> None:
        code, output, _ = self.run_cli("unset", "--dir", str(self.install), "fps_limit")
        self.assertEqual(code, 0)
        code, output, _ = self.run_cli("unset", "--dir", str(self.install), "fps_limit")
        self.assertEqual(code, 0)
        self.assertIn("无需改动", output)
        self.assertEqual(len(self.backups()), 1)

    def test_unset_requires_existing_ini(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, _, stderr = self.run_cli("unset", "--dir", str(empty), "volume")
        self.assertEqual(code, 1)
        self.assertIn("未找到", stderr)


class PresetCommandTest(CliTestBase):
    def test_lists_presets(self) -> None:
        code, output, _ = self.run_cli("preset")
        self.assertEqual(code, 0)
        for name in ("savage-wind", "controller", "performance", "quality"):
            self.assertIn(name, output)

    def test_apply_dry_run_does_not_write(self) -> None:
        self.write_ini("[input]\nprompts = nintendo\n")
        before = self.ini.read_bytes()
        code, output, _ = self.run_cli(
            "apply", "--dir", str(self.install), "savage-wind", "--dry-run", "--version", "1.4.3"
        )
        self.assertEqual(code, 0)
        self.assertIn("prompts: nintendo -> pc", output)
        self.assertIn("dry-run", output)
        self.assertEqual(self.ini.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_apply_writes_and_is_idempotent(self) -> None:
        self.write_ini("[input]\nprompts = nintendo\n[fps]\nfps_limit = 30\n")
        code, output, _ = self.run_cli(
            "apply", "--dir", str(self.install), "savage-wind", "--version", "1.4.3"
        )
        self.assertEqual(code, 0)
        self.assertIn("已应用预设 savage-wind", output)
        text = self.ini.read_text(encoding="utf-8")
        self.assertIn("prompts = pc", text)
        self.assertIn("fps_limit = 60", text)
        self.assertEqual(len(self.backups()), 1)
        code, output, _ = self.run_cli(
            "apply", "--dir", str(self.install), "savage-wind", "--version", "1.4.3"
        )
        self.assertEqual(code, 0)
        self.assertIn("已是目标值", output)
        self.assertEqual(len(self.backups()), 1)

    def test_apply_version_filter(self) -> None:
        self.write_ini("[input]\nmenu_cursor = 0\n")
        code, output, _ = self.run_cli(
            "apply", "--dir", str(self.install), "savage-wind", "--dry-run", "--version", "1.2.1"
        )
        self.assertEqual(code, 0)
        self.assertIn("跳过 menu_cursor", output)

    def test_unknown_preset(self) -> None:
        code, _, stderr = self.run_cli("apply", "--dir", str(self.install), "no-such-preset")
        self.assertEqual(code, 1)
        self.assertIn("未知预设", stderr)


class BackupRestoreCommandTest(CliTestBase):
    def test_backup_command(self) -> None:
        code, output, _ = self.run_cli("backup", "--dir", str(self.install))
        self.assertEqual(code, 0)
        created = Path(output.strip())
        self.assertTrue(created.exists())
        self.assertRegex(created.name, BACKUP_PATTERN)
        self.assertEqual(created.read_bytes(), self.ini.read_bytes())

    def test_backup_requires_ini(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, _, stderr = self.run_cli("backup", "--dir", str(empty))
        self.assertEqual(code, 1)
        self.assertIn("未找到", stderr)

    def test_restore_from_backup(self) -> None:
        original = self.ini.read_bytes()
        code, output, _ = self.run_cli("backup", "--dir", str(self.install))
        self.assertEqual(code, 0)
        backup = Path(output.strip())
        self.ini.write_text("[audio]\nvolume = 1\n", encoding="utf-8")
        code, output, _ = self.run_cli("restore", str(backup))
        self.assertEqual(code, 0)
        self.assertIn("已从", output)
        self.assertIn("恢复前备份", output)
        self.assertEqual(self.ini.read_bytes(), original)

    def test_restore_to_explicit_ini(self) -> None:
        original = self.ini.read_bytes()
        backup = self.install / "totk.ini.bak-20260101-000000"
        backup.write_bytes(original)
        target = self.root / "other.ini"
        target.write_text("[audio]\nvolume = 1\n", encoding="utf-8")
        code, _, _ = self.run_cli("restore", "--ini", str(target), str(backup))
        self.assertEqual(code, 0)
        self.assertEqual(target.read_bytes(), original)

    def test_restore_missing_backup(self) -> None:
        code, _, stderr = self.run_cli("restore", str(self.root / "missing.bak"))
        self.assertEqual(code, 1)
        self.assertIn("备份文件不存在", stderr)


class DoctorCommandTest(CliTestBase):
    def test_clean_config(self) -> None:
        code, output, _ = self.run_cli("doctor", "--dir", str(self.install))
        self.assertEqual(code, 0)
        self.assertIn("未发现需要处理的问题", output)

    def test_error_config(self) -> None:
        self.write_ini("[performance]\nfree_cores = 1\n")
        code, output, _ = self.run_cli("doctor", "--dir", str(self.install))
        self.assertEqual(code, 1)
        self.assertIn("[错误]", output)
        self.assertIn("建议：", output)

    def test_missing_ini(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        code, output, _ = self.run_cli("doctor", "--dir", str(empty))
        self.assertEqual(code, 0)
        self.assertIn("按默认值诊断", output)

    def test_version_is_passed_through(self) -> None:
        self.write_ini("[display]\nfov = 110\n")
        code, output, _ = self.run_cli("doctor", "--dir", str(self.install), "--version", "1.4.3")
        self.assertEqual(code, 0)
        self.assertIn("TotK Recomp 版本：1.4.3", output)


class LaunchLogCommandTest(CliTestBase):
    def test_launch_dry_run(self) -> None:
        code, output, _ = self.run_cli("launch", "--dir", str(self.install), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("将运行：", output)
        self.assertIn("totk.exe", output)

    def test_launch_dry_run_with_extra_arguments(self) -> None:
        code, output, _ = self.run_cli(
            "launch", "--dir", str(self.install), "--dry-run", "extra_arg"
        )
        self.assertEqual(code, 0)
        self.assertIn("extra_arg", output)

    def test_launch_without_executable(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        (empty / "totk.ini").write_text("", encoding="utf-8")
        code, _, stderr = self.run_cli("launch", "--dir", str(empty), "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("未在", stderr)

    def test_launch_without_install_directory(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        self.chdir(empty)
        code, _, stderr = self.run_cli("launch", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("未检测到", stderr)

    def test_log_tail(self) -> None:
        log = self.install / "totk.log"
        log.write_text("line1\nline2\nline3\n", encoding="utf-8")
        code, output, _ = self.run_cli("log", "--dir", str(self.install), "--tail", "2")
        self.assertEqual(code, 0)
        self.assertIn("共 3 行，显示最后 2 行", output)
        self.assertIn("line3", output)
        self.assertNotIn("line1", output)

    def test_log_explicit_path(self) -> None:
        log = self.root / "custom.log"
        log.write_text("only line\n", encoding="utf-8")
        code, output, _ = self.run_cli("log", "--path", str(log))
        self.assertEqual(code, 0)
        self.assertIn("only line", output)

    def test_log_missing(self) -> None:
        code, _, stderr = self.run_cli("log", "--dir", str(self.install))
        self.assertEqual(code, 1)
        self.assertIn("未在", stderr)

    def test_log_negative_tail(self) -> None:
        log = self.root / "custom.log"
        log.write_text("x\n", encoding="utf-8")
        code, _, stderr = self.run_cli("log", "--path", str(log), "--tail", "-1")
        self.assertEqual(code, 1)
        self.assertIn("--tail", stderr)

    def test_log_auto_detection(self) -> None:
        (self.install / "totk.log").write_text("a\nb\n", encoding="utf-8")
        self.chdir(self.install)
        code, output, _ = self.run_cli("log", "--tail", "1")
        self.assertEqual(code, 0)
        self.assertIn("b", output)


class ExplicitPathTest(CliTestBase):
    def test_get_with_explicit_ini(self) -> None:
        code, output, _ = self.run_cli("get", "--ini", str(self.ini), "volume")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "100")

    def test_set_with_explicit_ini(self) -> None:
        code, _, _ = self.run_cli("set", "--ini", str(self.ini), "volume", "40")
        self.assertEqual(code, 0)
        self.assertIn("volume = 40", self.ini.read_text(encoding="utf-8"))

    def test_unset_unknown_key(self) -> None:
        code, _, stderr = self.run_cli("unset", "--dir", str(self.install), "not_a_key")
        self.assertEqual(code, 1)
        self.assertIn("未知键", stderr)


class RestoreVariantsTest(CliTestBase):
    def test_restore_uses_dir_target(self) -> None:
        original = self.ini.read_bytes()
        backup = self.install / "totk.ini.bak-20260101-000000"
        backup.write_bytes(original)
        self.ini.write_text("[audio]\nvolume = 1\n", encoding="utf-8")
        code, _, _ = self.run_cli("restore", "--dir", str(self.install), str(backup))
        self.assertEqual(code, 0)
        self.assertEqual(self.ini.read_bytes(), original)

    def test_restore_defaults_to_sibling_totk_ini(self) -> None:
        snapshot = self.root / "snapshot.ini"
        snapshot.write_text("[audio]\nvolume = 7\n", encoding="utf-8")
        code, _, _ = self.run_cli("restore", str(snapshot))
        self.assertEqual(code, 0)
        self.assertEqual(
            (self.root / "totk.ini").read_text(encoding="utf-8"), "[audio]\nvolume = 7\n"
        )

    def test_restore_same_content_is_noop(self) -> None:
        original = self.ini.read_bytes()
        backup = self.install / "totk.ini.bak-20260101-000000"
        backup.write_bytes(original)
        code, output, _ = self.run_cli("restore", str(backup))
        self.assertEqual(code, 0)
        self.assertIn("内容与备份相同", output)

    def test_restore_invalid_backup(self) -> None:
        backup = self.root / "broken.bak"
        backup.write_bytes(b"\xff\xfe broken")
        code, _, stderr = self.run_cli("restore", str(backup))
        self.assertEqual(code, 1)
        self.assertIn("无法解析", stderr)


@unittest.skipUnless(os.name == "posix", "需要可执行的假 totk 脚本")
class LaunchRealProcessTest(CliTestBase):
    def test_launch_runs_fake_executable(self) -> None:
        (self.install / "totk.exe").unlink()
        script = self.install / "totk"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)
        code, output, _ = self.run_cli("launch", "--dir", str(self.install))
        self.assertEqual(code, 0)
        self.assertIn("游戏退出码：0", output)


class LogErrorTest(CliTestBase):
    def test_log_path_missing(self) -> None:
        code, _, stderr = self.run_cli("log", "--path", str(self.root / "missing.log"))
        self.assertEqual(code, 1)
        self.assertIn("日志文件不存在", stderr)

    def test_log_path_is_directory(self) -> None:
        directory = self.root / "logdir"
        directory.mkdir()
        code, _, stderr = self.run_cli("log", "--path", str(directory))
        self.assertEqual(code, 1)
        self.assertIn("读取日志失败", stderr)


class VersionCommandTest(CliTestBase):
    def test_version_command(self) -> None:
        code, output, _ = self.run_cli("version")
        self.assertEqual(code, 0)
        self.assertIn(f"totk-frontend {__version__}", output)
        self.assertIn("设置注册表", output)


class ErrorHandlingTest(CliTestBase):
    def test_invalid_utf8_ini_reports_error(self) -> None:
        self.ini.write_bytes(b"\xff\xfe[frame rate]\nfps_limit = 60\n")
        code, _, stderr = self.run_cli("list", "--dir", str(self.install))
        self.assertEqual(code, 1)
        self.assertIn("错误", stderr)


if __name__ == "__main__":
    unittest.main()

"""首次引导测试（M5-T2）：只读、可解释、不代跑安装器。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import os
import tempfile
import unittest
from pathlib import Path

from totk_frontend.ini import IniDocument, write_ini
from totk_frontend.onboarding import (
    GuideState,
    GuideStep,
    build_guide,
    format_guide,
    needs_guidance,
)

CLEAN_INI = """[frame rate]
fps_limit = 60
realtime = 1

[display]
output_res = 1920x1080
"""


class GuideBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def make_install(self, *, ini: str | None = CLEAN_INI, version: str | None = "1.4.3") -> None:
        (self.dir / "totk.exe").write_text("", encoding="utf-8")
        (self.dir / "exefs").mkdir()
        (self.dir / "romfs").mkdir()
        if version is not None:
            (self.dir / "totk-install.json").write_text(
                f'{{"version": "{version}"}}', encoding="utf-8"
            )
        if ini is not None:
            (self.dir / "totk.ini").write_text(ini, encoding="utf-8")

    def snapshot(self) -> dict[str, tuple[int, int, bytes]]:
        """记录目录内每个条目的字节与修改时间，用于证明引导只读。"""
        result: dict[str, tuple[int, int, bytes]] = {}
        for entry in sorted(self.dir.iterdir()):
            if entry.is_file():
                stat = entry.stat()
                result[entry.name] = (stat.st_size, stat.st_mtime_ns, entry.read_bytes())
            else:
                result[entry.name] = (-1, 0, b"")
        return result


class BuildGuideTest(GuideBase):
    def test_complete_install_is_ready(self) -> None:
        self.make_install()
        state = build_guide(self.dir)
        self.assertIsInstance(state, GuideState)
        self.assertTrue(state.detected)
        self.assertTrue(state.ok)
        self.assertEqual(state.config_errors, ())
        self.assertEqual([step.number for step in state.steps], [1, 2, 3, 4, 5])
        self.assertIsNone(state.next_step)
        self.assertEqual(len(state.actionable_steps), 4)

    def test_empty_directory_needs_directory_step(self) -> None:
        state = build_guide(self.dir)
        self.assertFalse(state.detected)
        self.assertFalse(state.ok)
        self.assertTrue(needs_guidance(self.dir))
        self.assertFalse(state.steps[0].done)
        self.assertEqual(state.next_step.title, "选择 TotK Recomp 安装目录")
        self.assertTrue(state.findings)
        self.assertIn("错误", state.findings[0])

    def test_missing_ini_is_step_two(self) -> None:
        self.make_install(ini=None)
        state = build_guide(self.dir)
        self.assertTrue(state.steps[0].done)
        self.assertFalse(state.steps[1].done)
        self.assertIn("首次启动游戏", state.steps[1].detail)
        self.assertIn("按默认值继续", state.steps[1].detail)

    def test_ini_is_counted_without_double_read(self) -> None:
        self.make_install()
        state = build_guide(self.dir)
        self.assertTrue(state.steps[1].done)
        self.assertIn("共 6 行", state.steps[1].detail)

    def test_version_detected(self) -> None:
        self.make_install()
        state = build_guide(self.dir)
        self.assertEqual(state.version.version, "1.4.3")
        self.assertTrue(state.steps[2].done)
        self.assertIn("TotK Recomp 1.4.3", state.steps[2].detail)
        self.assertIn("1.4.3", state.steps[2].detail)

    def test_version_not_detected(self) -> None:
        self.make_install(version=None)
        state = build_guide(self.dir)
        self.assertIsNone(state.version.version)
        self.assertFalse(state.steps[2].done)
        self.assertIn("尚未识别版本", state.steps[2].detail)

    def test_unknown_version_is_explained(self) -> None:
        self.make_install(version="9.9.9")
        state = build_guide(self.dir)
        self.assertTrue(state.steps[2].done)
        self.assertIn("未记录的版本 9.9.9", state.steps[2].detail)
        self.assertIn("fov", state.steps[2].detail)

    def test_explicit_version_overrides_detection(self) -> None:
        self.make_install(version="1.4.3")
        state = build_guide(self.dir, version="1.2.1")
        self.assertIn("TotK Recomp 1.2.1", state.steps[2].detail)

    def test_config_errors_block_step_four(self) -> None:
        self.make_install(ini="[performance]\nfree_cores = 1\n")
        state = build_guide(self.dir)
        self.assertFalse(state.ok)
        self.assertFalse(state.steps[3].done)
        self.assertTrue(state.config_errors)
        self.assertIn("必须修正", state.steps[3].detail)
        self.assertIn("free_cores", state.steps[3].detail)

    def test_config_without_errors(self) -> None:
        self.make_install(ini="[display]\nupscaler = fsr\nsharpness = 0\n")
        state = build_guide(self.dir)
        self.assertTrue(state.steps[3].done)
        self.assertIn("没有必须修正的问题", state.steps[3].detail)

    def test_unreadable_ini_is_reported(self) -> None:
        self.make_install(ini=None)
        (self.dir / "totk.ini").write_bytes(b"\xff\xfe broken")
        state = build_guide(self.dir)
        self.assertFalse(state.steps[1].done)
        self.assertIn("无法解析", state.steps[1].detail)
        self.assertTrue(any("无法读取" in finding for finding in state.findings))

    def test_version_restriction_checked(self) -> None:
        self.make_install(ini="[display]\nfov = 110\n", version="1.2.1")
        state = build_guide(self.dir)
        codes = [issue.code for issue in state.config_issues]
        self.assertIn("rule.version_unsupported", codes)

    def test_requires_path(self) -> None:
        state = build_guide(self.dir / "missing")
        self.assertFalse(state.detected)

    def test_guide_is_read_only(self) -> None:
        self.make_install(ini="[performance]\nfree_cores = 1\n")
        before = self.snapshot()
        build_guide(self.dir)
        format_guide(build_guide(self.dir))
        self.assertEqual(self.snapshot(), before)

    def test_guide_does_not_create_files(self) -> None:
        empty = self.dir / "empty"
        empty.mkdir()
        build_guide(empty)
        self.assertEqual(list(empty.iterdir()), [])

    def test_step_marker(self) -> None:
        self.assertEqual(GuideStep(1, "t", "d", True).marker, "已完成")
        self.assertEqual(GuideStep(1, "t", "d", False).marker, "待完成")
        self.assertEqual(GuideStep(1, "t", "d", False, informational=True).marker, "说明")


class FormatGuideTest(GuideBase):
    def test_format_includes_report_and_steps(self) -> None:
        self.make_install()
        text = format_guide(build_guide(self.dir))
        self.assertIn("TotK Frontend 首次引导", text)
        self.assertIn("安装目录：", text)
        self.assertIn("步骤：", text)
        for step in ("选择 TotK Recomp 安装目录", "确认 totk.ini", "确认游戏版本", "检查配置", "开始游戏"):
            self.assertIn(step, text)
        self.assertIn("下一步：可以直接开始游戏", text)
        self.assertIn("[说明] 开始游戏", text)

    def test_format_can_skip_report(self) -> None:
        self.make_install()
        text = format_guide(build_guide(self.dir), include_report=False)
        self.assertNotIn("安装目录：", text)
        self.assertIn("步骤：", text)

    def test_format_empty_directory_points_to_step_one(self) -> None:
        text = format_guide(build_guide(self.dir))
        self.assertIn("下一步：选择 TotK Recomp 安装目录", text)

    def test_format_requires_state(self) -> None:
        with self.assertRaises(TypeError):
            format_guide("not a state")  # type: ignore[arg-type]

    def test_no_installer_or_download_wording(self) -> None:
        # 引导只提示，不代跑安装器、不下载任何内容。
        text = format_guide(build_guide(self.dir))
        for forbidden in ("http://", "https://", "下载安装", "自动安装"):
            self.assertNotIn(forbidden, text)

    def test_module_has_no_network_or_subprocess(self) -> None:
        source = Path(__file__).resolve().parents[1] / "src" / "totk_frontend" / "onboarding.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import requests", "import subprocess", "socket"):
            self.assertNotIn(forbidden, text)


class NeedsGuidanceTest(GuideBase):
    def test_needs_guidance_true_without_install(self) -> None:
        self.assertTrue(needs_guidance(self.dir))

    def test_needs_guidance_false_for_ready_install(self) -> None:
        self.make_install()
        self.assertFalse(needs_guidance(self.dir))

    def test_needs_guidance_true_for_config_errors(self) -> None:
        self.make_install(ini="[performance]\nfree_cores = 1\n")
        self.assertTrue(needs_guidance(self.dir))


@unittest.skipUnless(os.name == "posix", "权限语义依赖 POSIX")
class GuideOnReadOnlyInstallTest(GuideBase):
    def test_guide_works_when_install_is_read_only(self) -> None:
        self.make_install()
        for entry in self.dir.iterdir():
            entry.chmod(0o444 if entry.is_file() else 0o555)
        self.addCleanup(lambda: [entry.chmod(0o755) for entry in self.dir.iterdir()])
        state = build_guide(self.dir)
        self.assertTrue(state.detected)
        self.assertTrue(state.steps[1].done)


if __name__ == "__main__":
    unittest.main()

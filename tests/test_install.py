"""安装目录检测测试（M3-T1 的检测部分）。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import tempfile
import unittest
from pathlib import Path

from totk_frontend.install import (
    ALL_MARKERS,
    FindingLevel,
    InstallFinding,
    InstallInfo,
    detect_install,
    detect_version,
    find_install,
    format_install_report,
    install_findings,
)


class DetectInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_complete_install(self) -> None:
        (self.dir / "totk.exe").write_text("", encoding="utf-8")
        (self.dir / "totk.ini").write_text("", encoding="utf-8")
        (self.dir / "totk-install.json").write_text("{}", encoding="utf-8")
        (self.dir / "exefs").mkdir()
        (self.dir / "romfs").mkdir()
        info = detect_install(self.dir)
        self.assertEqual(set(info.present), set(ALL_MARKERS) - {"totk"})
        self.assertEqual(info.missing, ("totk",))
        self.assertTrue(info.looks_like_install)
        self.assertEqual(info.executable, self.dir / "totk.exe")
        self.assertEqual(info.ini_path, self.dir / "totk.ini")

    def test_linux_executable_name(self) -> None:
        (self.dir / "totk").write_text("", encoding="utf-8")
        (self.dir / "totk.ini").write_text("", encoding="utf-8")
        info = detect_install(self.dir)
        self.assertEqual(info.executable, self.dir / "totk")
        self.assertTrue(info.looks_like_install)

    def test_ini_only_is_not_an_install(self) -> None:
        (self.dir / "totk.ini").write_text("", encoding="utf-8")
        info = detect_install(self.dir)
        self.assertIsNone(info.executable)
        self.assertFalse(info.looks_like_install)
        self.assertIn("totk.exe", info.missing)

    def test_executable_without_config_is_not_an_install(self) -> None:
        (self.dir / "totk.exe").write_text("", encoding="utf-8")
        info = detect_install(self.dir)
        self.assertFalse(info.looks_like_install)

    def test_install_file_alone_is_enough(self) -> None:
        (self.dir / "totk-install.json").write_text("{}", encoding="utf-8")
        (self.dir / "romfs").mkdir()
        info = detect_install(self.dir)
        self.assertIsNone(info.executable)
        self.assertTrue(info.looks_like_install)

    def test_empty_directory(self) -> None:
        info = detect_install(self.dir)
        self.assertEqual(info.present, ())
        self.assertEqual(set(info.missing), set(ALL_MARKERS))
        self.assertFalse(info.looks_like_install)

    def test_missing_directory_is_treated_as_empty(self) -> None:
        info = detect_install(self.dir / "missing")
        self.assertFalse(info.looks_like_install)
        self.assertEqual(info.executable, None)


class FindInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.install = self.root / "TotK Recomp"
        self.install.mkdir()
        (self.install / "totk.exe").write_text("", encoding="utf-8")
        (self.install / "totk.ini").write_text("", encoding="utf-8")

    def test_finds_current_directory(self) -> None:
        self.assertEqual(find_install(self.install), self.install)

    def test_finds_parent_directory(self) -> None:
        nested = self.install / "mods" / "some-mod"
        nested.mkdir(parents=True)
        self.assertEqual(find_install(nested), self.install)

    def test_returns_none_without_markers(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        self.assertIsNone(find_install(empty))


def codes(findings) -> list[str]:
    return [finding.code for finding in findings]


class InstallFindingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def make_install(self, *, exe: bool = True) -> None:
        if exe:
            (self.dir / "totk.exe").write_text("", encoding="utf-8")
        (self.dir / "totk.ini").write_text("", encoding="utf-8")
        (self.dir / "totk-install.json").write_text("{}", encoding="utf-8")
        (self.dir / "exefs").mkdir()
        (self.dir / "romfs").mkdir()

    def test_complete_install_has_no_findings(self) -> None:
        self.make_install()
        self.assertEqual(install_findings(detect_install(self.dir)), ())

    def test_missing_executable_is_error(self) -> None:
        self.make_install(exe=False)
        findings = install_findings(detect_install(self.dir))
        self.assertIn("install.executable_missing", codes(findings))
        self.assertEqual(findings[0].level, FindingLevel.ERROR)

    def test_empty_directory_explains_each_missing_marker(self) -> None:
        findings = install_findings(detect_install(self.dir))
        self.assertIn("install.not_an_install", codes(findings))
        self.assertIn("install.marker.totk.ini", codes(findings))
        self.assertIn("install.marker.exefs", codes(findings))
        self.assertIn("install.marker.romfs", codes(findings))
        self.assertIn("install.marker.totk-install.json", codes(findings))
        for finding in findings:
            if finding.level is not FindingLevel.INFO:
                self.assertTrue(finding.suggestion.strip(), finding.code)

    def test_ini_missing_is_warning_not_error(self) -> None:
        self.make_install()
        (self.dir / "totk.ini").unlink()
        findings = install_findings(detect_install(self.dir))
        codes_ = codes(findings)
        self.assertIn("install.marker.totk.ini", codes_)
        ini_finding = next(item for item in findings if item.code == "install.marker.totk.ini")
        self.assertEqual(ini_finding.level, FindingLevel.WARNING)
        self.assertNotIn("install.not_an_install", codes_)

    def test_install_record_missing_is_info(self) -> None:
        self.make_install()
        (self.dir / "totk-install.json").unlink()
        finding = next(
            item
            for item in install_findings(detect_install(self.dir))
            if item.code == "install.marker.totk-install.json"
        )
        self.assertEqual(finding.level, FindingLevel.INFO)

    def test_findings_are_ordered_errors_first(self) -> None:
        findings = install_findings(detect_install(self.dir))
        levels = [finding.level for finding in findings]
        self.assertEqual(levels[0], FindingLevel.ERROR)
        self.assertIn(FindingLevel.WARNING, levels)
        self.assertIn(FindingLevel.INFO, levels)

    def test_finding_str(self) -> None:
        self.assertEqual(str(InstallFinding(FindingLevel.ERROR, "x", "出错了")), "[错误] 出错了")
        self.assertEqual(str(InstallFinding(FindingLevel.WARNING, "x", "注意")), "[警告] 注意")
        self.assertEqual(str(InstallFinding(FindingLevel.INFO, "x", "说明")), "[提示] 说明")

    def test_requires_install_info(self) -> None:
        with self.assertRaises(TypeError):
            install_findings("not info")  # type: ignore[arg-type]


class DetectVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write_record(self, text: str) -> None:
        (self.dir / "totk-install.json").write_text(text, encoding="utf-8")

    def test_no_install_file(self) -> None:
        result = detect_version(self.dir)
        self.assertIsNone(result.version)
        self.assertFalse(result.known)
        self.assertIn("未找到", result.detail)

    def test_top_level_version(self) -> None:
        self.write_record('{"version": "1.4.3"}')
        result = detect_version(self.dir)
        self.assertEqual(result.version, "1.4.3")
        self.assertTrue(result.known)
        self.assertIn("1.4.3", result.detail)

    def test_alternative_field_name(self) -> None:
        self.write_record('{"game_version": "1.2.1"}')
        self.assertEqual(detect_version(self.dir).version, "1.2.1")

    def test_nested_version(self) -> None:
        self.write_record('{"game": {"build": {"version": "1.1.0"}}}')
        result = detect_version(self.dir)
        self.assertEqual(result.version, "1.1.0")
        self.assertTrue(result.known)

    def test_version_in_list(self) -> None:
        self.write_record('{"entries": [{"name": "x"}, {"version": "1.4.3"}]}')
        self.assertEqual(detect_version(self.dir).version, "1.4.3")

    def test_unknown_version_is_reported_not_guessed(self) -> None:
        self.write_record('{"version": "9.9.9"}')
        result = detect_version(self.dir)
        self.assertEqual(result.version, "9.9.9")
        self.assertFalse(result.known)
        self.assertIn("未见文档记录", result.detail)

    def test_non_semver_value_is_ignored(self) -> None:
        self.write_record('{"version": "1.4"}')
        result = detect_version(self.dir)
        self.assertIsNone(result.version)
        self.assertIn("没有可识别的版本字段", result.detail)

    def test_number_value_is_ignored(self) -> None:
        self.write_record('{"version": 143}')
        self.assertIsNone(detect_version(self.dir).version)

    def test_invalid_json(self) -> None:
        self.write_record("not json")
        result = detect_version(self.dir)
        self.assertIsNone(result.version)
        self.assertIn("不是有效 JSON", result.detail)

    def test_missing_version_field(self) -> None:
        self.write_record('{"name": "TotK Recomp", "files": []}')
        self.assertIsNone(detect_version(self.dir).version)

    def test_deep_nesting_is_bounded(self) -> None:
        payload = '"1.4.3"'
        for _ in range(8):
            payload = '{"nested": ' + payload + "}"
        self.write_record('{"deep": ' + payload + "}")
        self.assertIsNone(detect_version(self.dir).version)

    def test_unreadable_record(self) -> None:
        record = self.dir / "totk-install.json"
        record.mkdir()  # 目录而非文件，读取会失败
        result = detect_version(self.dir)
        self.assertIsNone(result.version)
        self.assertIn("无法读取", result.detail)


class FormatInstallReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_report_for_complete_install(self) -> None:
        (self.dir / "totk.exe").write_text("", encoding="utf-8")
        (self.dir / "totk.ini").write_text("", encoding="utf-8")
        (self.dir / "totk-install.json").write_text('{"version": "1.4.3"}', encoding="utf-8")
        (self.dir / "exefs").mkdir()
        (self.dir / "romfs").mkdir()
        report = format_install_report(self.dir)
        self.assertIn("安装目录：", report)
        self.assertIn("存在  totk.exe", report)
        self.assertIn("结果：检测通过。", report)
        self.assertIn("识别到 TotK Recomp 1.4.3", report)

    def test_report_for_empty_directory_lists_findings(self) -> None:
        report = format_install_report(self.dir)
        self.assertIn("结果：缺少必要标记", report)
        self.assertIn("[错误]", report)
        self.assertIn("建议：", report)
        self.assertIn("无法识别版本", report)

    def test_report_accepts_explicit_version(self) -> None:
        from totk_frontend.install import VersionDetection

        detection = VersionDetection("1.2.1", "manual", True, "用户指定 1.2.1")
        report = format_install_report(self.dir, version=detection)
        self.assertIn("用户指定 1.2.1", report)

    def test_report_truncates_findings(self) -> None:
        report = format_install_report(self.dir, max_findings=1)
        self.assertIn("条结论", report)


if __name__ == "__main__":
    unittest.main()

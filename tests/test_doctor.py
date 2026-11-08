"""``doctor`` 诊断测试（M2-T3）：规则表覆盖 docs/settings.md 第 8 节。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import re
import unittest
from pathlib import Path

from totk_frontend.doctor import (
    RULE_CATALOG,
    RULES_BY_CODE,
    diagnose,
    format_report,
    rule_for_code,
)
from totk_frontend.ini import IniDocument
from totk_frontend.validate import Severity

DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "settings.md"

CLEAN_DOC = """# 手写合成样本
[frame rate]
fps_limit = 60
realtime = 1

[display]
window_size = 1920x1080
output_res = 1920x1080
upscaler = fsr
sharpness = 80

[input]
prompts = nintendo
mouse_mode = direct
mouse_sens = 1

[audio]
volume = 100
"""

# 第 8 节每条规则的最小触发样本：(文档, diagnose 额外参数, 期望严重级别)
RULE_TRIGGERS: dict[str, tuple[str, dict, Severity]] = {
    "rule.fps_limit_realtime": (
        "[frame rate]\nfps_limit = 120\nrealtime = 0\n",
        {},
        Severity.ERROR,
    ),
    "rule.free_cores": ("[performance]\nfree_cores = 1\n", {}, Severity.ERROR),
    "rule.mouse_sens_off": (
        "[input]\nmouse_mode = direct\nmouse_sens = 0\n",
        {},
        Severity.WARNING,
    ),
    "rule.prompts_aspect": (
        "[display]\noutput_res = 3440x1440\n[input]\nprompts = pc\n",
        {},
        Severity.WARNING,
    ),
    "rule.pad_layout_detected": (
        "[input]\npad_layout = nintendo\n",
        {"detected_pad_layout": "xbox"},
        Severity.INFO,
    ),
    "rule.window_size_display": (
        "[display]\nwindow_size = 2560x1440\n",
        {"display_size": (1920, 1080)},
        Severity.WARNING,
    ),
    "rule.upscaler_sharpness": (
        "[display]\nupscaler = fsr\nsharpness = 0\n",
        {},
        Severity.INFO,
    ),
    "rule.duplicate_key": (
        "[frame rate]\nfps_limit = 60\nfps_limit = 120\n",
        {},
        Severity.WARNING,
    ),
}


def make_doc(text: str) -> IniDocument:
    return IniDocument.from_text(text)


def count_doc_rule_rows() -> int:
    """统计 docs/settings.md 第 8 节表格的规则行数。"""
    inside = False
    count = 0
    for line in DOC_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 8."):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside or not line.startswith("| "):
            continue
        if line.startswith("| 规则 |") or re.match(r"^\|\s*-+", line):
            continue
        count += 1
    return count


class RuleCatalogTest(unittest.TestCase):
    def test_catalog_covers_all_documented_rules(self) -> None:
        self.assertEqual(count_doc_rule_rows(), 8)
        self.assertEqual(len(RULE_CATALOG), 8)
        self.assertEqual(set(RULES_BY_CODE), set(RULE_TRIGGERS))
        self.assertEqual([rule.code for rule in RULE_CATALOG], list(RULE_TRIGGERS))
        for rule in RULE_CATALOG:
            self.assertTrue(rule.title.strip(), rule.code)
            self.assertTrue(rule.reference.strip(), rule.code)

    def test_every_catalog_rule_can_be_triggered(self) -> None:
        for code, (text, kwargs, expected_severity) in RULE_TRIGGERS.items():
            report = diagnose(make_doc(text), **kwargs)
            matched = [issue for issue in report.issues if issue.code == code]
            self.assertTrue(matched, f"规则 {code} 未被触发")
            self.assertEqual(matched[0].severity, expected_severity, code)
            rule = rule_for_code(code)
            self.assertIsNotNone(rule, code)
            assert rule is not None
            self.assertEqual(rule.code, code)

    def test_unknown_rule_code(self) -> None:
        self.assertIsNone(rule_for_code("rule.not_a_rule"))


class DiagnoseTest(unittest.TestCase):
    def test_clean_document_has_no_issues(self) -> None:
        report = diagnose(make_doc(CLEAN_DOC))
        self.assertTrue(report.ok)
        self.assertEqual(report.issues, ())
        self.assertEqual(report.unknown_keys, ())
        self.assertIn("fps_limit", report.checked_keys)
        self.assertIn("volume", report.checked_keys)
        self.assertIsNone(report.version)

    def test_unknown_keys_are_summarized_not_validated(self) -> None:
        doc = make_doc("[performance]\nbind_skip = 1\n[display]\nunknown_future_key = x\n")
        report = diagnose(doc)
        self.assertEqual(report.unknown_keys, ("bind_skip", "unknown_future_key"))
        self.assertEqual(report.checked_keys, ())
        self.assertEqual(report.issues, ())
        self.assertTrue(report.ok)

    def test_bind_keys_are_checked(self) -> None:
        report = diagnose(make_doc("[input]\nbind_A = pad:east, key:E\n"))
        self.assertIn("bind_a", report.checked_keys)
        self.assertEqual(report.unknown_keys, ())

    def test_duplicates_are_reported(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = 60\nfps_limit = 120\n")
        report = diagnose(doc)
        self.assertEqual([item.key for item in report.duplicates], ["fps_limit"])
        self.assertEqual(report.duplicates[0].count, 2)
        self.assertIn("rule.duplicate_key", [issue.code for issue in report.issues])

    def test_version_restrictions_reported(self) -> None:
        doc = make_doc("[display]\nfov = 110\n")
        report = diagnose(doc, version="1.2.1")
        self.assertEqual(report.version, "1.2.1")
        self.assertIn("rule.version_unsupported", [issue.code for issue in report.issues])
        self.assertIsNone(rule_for_code("rule.version_unsupported"))

    def test_issues_are_sorted_by_severity(self) -> None:
        doc = make_doc(
            "[performance]\nfree_cores = 1\n[display]\nupscaler = fsr\nsharpness = 0\n"
        )
        report = diagnose(doc)
        severities = [issue.severity for issue in report.issues]
        self.assertEqual(severities[0], Severity.ERROR)
        self.assertEqual(severities[-1], Severity.INFO)
        self.assertEqual(severities, sorted(severities, key=lambda item: (item is Severity.INFO, item is Severity.WARNING)))

    def test_report_groups_by_severity(self) -> None:
        doc = make_doc(
            "[performance]\nfree_cores = 1\n"
            "[display]\nupscaler = fsr\nsharpness = 0\noutput_res = 3440x1440\n"
            "[input]\nprompts = pc\n"
        )
        report = diagnose(doc)
        self.assertEqual(len(report.errors), 1)
        self.assertTrue(report.warnings)
        self.assertTrue(report.infos)

    def test_diagnose_requires_document(self) -> None:
        with self.assertRaises(TypeError):
            diagnose("not a document")  # type: ignore[arg-type]


class FormatReportTest(unittest.TestCase):
    def test_clean_report_conclusion(self) -> None:
        text = format_report(diagnose(make_doc(CLEAN_DOC)))
        self.assertIn("配置诊断（TotK Frontend doctor）", text)
        self.assertIn("TotK Recomp 版本：未指定", text)
        self.assertIn("结论：未发现需要处理的问题。", text)

    def test_error_report_includes_suggestion(self) -> None:
        text = format_report(diagnose(make_doc("[performance]\nfree_cores = 1\n")))
        self.assertIn("[错误]", text)
        self.assertIn("建议：", text)
        self.assertIn("free_cores", text)
        self.assertIn("结论：发现 1 个必须修正的问题。", text)

    def test_warning_report_conclusion(self) -> None:
        doc = make_doc("[display]\noutput_res = 3440x1440\n[input]\nprompts = pc\n")
        text = format_report(diagnose(doc))
        self.assertIn("[警告]", text)
        self.assertIn("没有错误；有 1 条警告建议处理。", text)

    def test_version_and_unknown_keys_are_shown(self) -> None:
        doc = make_doc(
            "[display]\nfov = 110\n[performance]\nbind_skip = 1\nu1 = 1\nu2 = 1\n"
        )
        text = format_report(diagnose(doc, version="1.2.1"))
        self.assertIn("TotK Recomp 版本：1.2.1", text)
        self.assertIn("未知键（保留，不校验）", text)
        self.assertIn("bind_skip", text)

    def test_unknown_keys_are_truncated(self) -> None:
        keys = "\n".join(f"u{index} = 1" for index in range(10))
        doc = make_doc(f"[custom]\n{keys}\n")
        text = format_report(diagnose(doc), max_unknown=3)
        self.assertIn("…（共 10 个）", text)
        self.assertNotIn("u4", text)

    def test_duplicate_summary(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = 60\nfps_limit = 120\n")
        text = format_report(diagnose(doc))
        self.assertIn("重复键：fps_limit", text)

    def test_format_requires_report(self) -> None:
        with self.assertRaises(TypeError):
            format_report("not a report")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

"""``totk_frontend.ini`` 解析测试（M1-T1）。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import unittest
from pathlib import Path

from totk_frontend.ini import (
    BOM_CHAR,
    IniDocument,
    IniParseError,
    LineKind,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = fixture_text("sample.ini")
        self.doc = IniDocument.from_text(self.text)

    # ------------------------------------------------------------ 节与键
    def test_sections_keep_file_order_and_spelling(self) -> None:
        self.assertEqual(
            self.doc.sections(),
            ("frame rate", "display", "input", "audio", "custom section"),
        )

    def test_keys_in_file_order(self) -> None:
        self.assertEqual(
            self.doc.keys("display"),
            ("window_size", "fullscreen", "unknown_future_key", "output_res", "upscaler", "sharpness", "aspect"),
        )

    def test_key_names_are_case_insensitive(self) -> None:
        self.assertEqual(self.doc.get("FPS_LIMIT"), "60")
        self.assertEqual(self.doc.get("Fps_Limit"), "60")

    def test_section_names_are_case_insensitive(self) -> None:
        self.assertEqual(self.doc.get("window_size", "DISPLAY"), "1920x1080")
        self.assertEqual(self.doc.get("volume", "Audio"), "100")

    def test_missing_key_returns_default(self) -> None:
        self.assertIsNone(self.doc.get("fov"))
        self.assertEqual(self.doc.get("fov", default="100"), "100")
        self.assertFalse(self.doc.has("fov"))

    def test_get_all_returns_every_active_line(self) -> None:
        doc = IniDocument.from_text(fixture_text("duplicates.ini"))
        self.assertEqual(doc.get_all("fps_limit"), ["60", "120"])
        self.assertEqual(doc.get_all("fps_limit", "frame rate"), ["60", "120"])
        self.assertEqual(doc.get_all("fps_limit", "display"), [])

    def test_duplicates_last_wins(self) -> None:
        doc = IniDocument.from_text(fixture_text("duplicates.ini"))
        self.assertEqual(doc.get("fps_limit"), "120")
        self.assertEqual(doc.get("realtime"), "0")
        duplicates = {(item.section, item.key): item.count for item in doc.duplicates()}
        self.assertEqual(duplicates, {("frame rate", "fps_limit"): 2, ("frame rate", "realtime"): 2})

    def test_unknown_keys_and_sections_are_preserved(self) -> None:
        self.assertEqual(self.doc.get("unknown_future_key", "display"), "keep-me")
        self.assertEqual(self.doc.get("custom_key", "custom section"), "foo")

    def test_global_keys_before_first_section(self) -> None:
        doc = IniDocument.from_text(fixture_text("global.ini"))
        self.assertEqual(doc.get("fps_limit"), "30")
        self.assertEqual(doc.keys("display"), ("fullscreen",))
        self.assertEqual(doc.sections(), ("display",))

    # ------------------------------------------------------------ 行类型
    def test_line_kinds(self) -> None:
        kinds = [line.kind for line in self.doc.lines]
        self.assertIn(LineKind.COMMENT, kinds)
        self.assertIn(LineKind.BLANK, kinds)
        self.assertIn(LineKind.SECTION, kinds)
        self.assertIn(LineKind.KEY_VALUE, kinds)

    def test_commented_lines_are_not_active(self) -> None:
        text = "# fps_limit = 120\n; realtime = 0\n[fps]\n"
        doc = IniDocument.from_text(text)
        self.assertIsNone(doc.get("fps_limit"))
        self.assertIsNone(doc.get("realtime"))
        self.assertEqual(doc.keys(), ())

    def test_commented_lookalike_section_is_not_section(self) -> None:
        doc = IniDocument.from_text("# [display]\nfps_limit = 60\n")
        self.assertEqual(doc.sections(), ())
        self.assertEqual(doc.get("fps_limit"), "60")

    def test_value_keeps_inner_equals_and_hash(self) -> None:
        doc = IniDocument.from_text("bind_A = pad:east, key:E\naudio = Foo # Bar\n")
        self.assertEqual(doc.get("bind_a"), "pad:east, key:E")
        self.assertEqual(doc.get("audio"), "Foo # Bar")

    def test_malformed_lines_are_other_and_preserved(self) -> None:
        text = "[display\nfullscreen = 0\nnot a kv line\n[ok]\n"
        doc = IniDocument.from_text(text)
        kinds = [line.kind for line in doc.lines]
        self.assertEqual(kinds[0], LineKind.OTHER)
        self.assertEqual(kinds[2], LineKind.OTHER)
        self.assertEqual(doc.get("fullscreen"), "0")
        self.assertEqual(doc.render(), text)

    def test_section_assignment_of_blank_and_comment_lines(self) -> None:
        doc = IniDocument.from_text("[a]\n\n# comment\n[b]\n")
        self.assertEqual(doc.lines[1].section, "a")
        self.assertEqual(doc.lines[2].section, "a")
        self.assertEqual(doc.lines[3].section, "b")

    # ------------------------------------------------------------ 编码与换行
    def test_render_roundtrip_is_byte_exact(self) -> None:
        self.assertEqual(self.doc.render(), self.text)
        self.assertEqual(self.doc.to_bytes(), self.text.encode("utf-8"))

    def test_utf8_bom_preserved(self) -> None:
        data = "\ufeff[fps]\nfps_limit = 60\n".encode("utf-8")
        doc = IniDocument.from_bytes(data)
        self.assertTrue(doc.bom)
        self.assertEqual(doc.get("fps_limit"), "60")
        self.assertEqual(doc.to_bytes(), data)
        self.assertEqual(doc.render()[0], BOM_CHAR)

    def test_invalid_utf8_raises_parse_error(self) -> None:
        with self.assertRaises(IniParseError):
            IniDocument.from_bytes(b"\xff\xfe[fps]\n")

    def test_crlf_is_preserved_per_line(self) -> None:
        text = "[display]\r\nfullscreen = 1\r\n"
        doc = IniDocument.from_text(text)
        self.assertEqual(doc.render(), text)
        self.assertTrue(all(line.eol == "\r\n" for line in doc.lines))

    def test_mixed_newlines_are_preserved(self) -> None:
        text = "a = 1\r\nb = 2\nc = 3\r\n"
        doc = IniDocument.from_text(text)
        self.assertEqual(doc.render(), text)

    def test_missing_final_newline_is_preserved(self) -> None:
        text = "[display]\nfullscreen = 1"
        doc = IniDocument.from_text(text)
        self.assertEqual(doc.lines[-1].eol, "")
        self.assertEqual(doc.render(), text)

    def test_empty_document(self) -> None:
        doc = IniDocument.from_text("")
        self.assertEqual(doc.lines, [])
        self.assertEqual(doc.sections(), ())
        self.assertEqual(doc.keys(), ())
        self.assertEqual(doc.render(), "")

    def test_from_path_reports_missing_file(self) -> None:
        with self.assertRaises(IniParseError):
            IniDocument.from_path(FIXTURES / "does-not-exist.ini")

    def test_newline_detection_for_inserted_lines(self) -> None:
        crlf = IniDocument.from_text("[a]\r\nx = 1\r\n")
        self.assertEqual(crlf.newline, "\r\n")
        lf = IniDocument.from_text("[a]\nx = 1\n")
        self.assertEqual(lf.newline, "\n")


if __name__ == "__main__":
    unittest.main()

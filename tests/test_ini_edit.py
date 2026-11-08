"""``totk_frontend.ini`` 修改测试（M1-T1，只改目标行、保持其余字节）。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import os
import unittest
from pathlib import Path

from totk_frontend.ini import ChangeOp, IniDocument

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def changed_line_indices(before: str, after: str) -> list[int]:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if len(before_lines) != len(after_lines):
        raise AssertionError("行数发生变化，不能按行比较")
    return [index for index, (a, b) in enumerate(zip(before_lines, after_lines)) if a != b]


class SetExistingKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = fixture_text("sample.ini")
        self.doc = IniDocument.from_text(self.text)

    def test_only_target_line_changes(self) -> None:
        self.doc.set("fps_limit", "120", "frame rate")
        after = self.doc.render()
        self.assertEqual(changed_line_indices(self.text, after), [5])
        self.assertEqual(after.splitlines()[5], "fps_limit = 120")
        self.assertEqual(self.doc.get("fps_limit"), "120")

    def test_other_lines_stay_byte_identical(self) -> None:
        self.doc.set("sharpness", "50", "display")
        before_lines = self.text.splitlines(keepends=True)
        after_lines = self.doc.render().splitlines(keepends=True)
        for index, (before, after) in enumerate(zip(before_lines, after_lines)):
            if index == 15:
                continue
            self.assertEqual(before, after, f"第 {index + 1} 行不应变化")
        self.assertEqual(after_lines[15], "sharpness = 50\n")

    def test_key_spelling_and_spacing_are_kept(self) -> None:
        text = "FPS_LIMIT   =   60  \n"
        doc = IniDocument.from_text(text)
        doc.set("fps_limit", "144")
        self.assertEqual(doc.render(), "FPS_LIMIT   =   144  \n")

    def test_no_space_around_equals_is_kept(self) -> None:
        doc = IniDocument.from_text("fps_limit=60\n")
        doc.set("fps_limit", "90")
        self.assertEqual(doc.render(), "fps_limit=90\n")

    def test_value_is_stripped(self) -> None:
        doc = IniDocument.from_text("fps_limit = 60\n")
        doc.set("fps_limit", "  120  ")
        self.assertEqual(doc.render(), "fps_limit = 120\n")
        self.assertEqual(doc.get("fps_limit"), "120")

    def test_duplicate_keys_update_last_active_line(self) -> None:
        doc = IniDocument.from_text(fixture_text("duplicates.ini"))
        original = doc.render()
        doc.set("fps_limit", "90")
        self.assertEqual(doc.get("fps_limit"), "90")
        self.assertEqual(doc.get_all("fps_limit"), ["60", "90"])
        self.assertEqual(changed_line_indices(original, doc.render()), [5])

    def test_chinese_value(self) -> None:
        doc = IniDocument.from_text("[audio]\naudio = default\n")
        doc.set("audio", "内置扬声器")
        self.assertEqual(doc.get("audio"), "内置扬声器")
        self.assertIn("内置扬声器", doc.render())

    def test_changes_are_recorded(self) -> None:
        self.doc.set("volume", "80", "audio")
        self.doc.unset("motion", "input")
        self.assertEqual(len(self.doc.changes), 2)
        self.assertEqual(self.doc.changes[0].op, ChangeOp.SET)
        self.assertEqual(self.doc.changes[0].key, "volume")
        self.assertEqual(self.doc.changes[0].section, "audio")
        self.assertEqual(self.doc.changes[0].value, "80")
        self.assertEqual(self.doc.changes[1].op, ChangeOp.UNSET)


class SetMissingKeyTest(unittest.TestCase):
    def test_inserted_after_last_key_of_its_section(self) -> None:
        text = fixture_text("sample.ini")
        doc = IniDocument.from_text(text)
        doc.set("fov", "110", "display")
        lines = doc.render().splitlines(keepends=True)
        aspect_index = lines.index("aspect = fit\n")
        self.assertEqual(lines[aspect_index + 1], "fov = 110\n")
        self.assertEqual(doc.get("fov"), "110")

    def test_existing_bytes_keep_their_order(self) -> None:
        text = fixture_text("sample.ini")
        doc = IniDocument.from_text(text)
        doc.set("fov", "110", "display")
        after = doc.render().splitlines(keepends=True)
        filtered = [line for line in after if line != "fov = 110\n"]
        self.assertEqual(filtered, text.splitlines(keepends=True))

    def test_insert_into_section_without_keys(self) -> None:
        doc = IniDocument.from_text("# 头\n[empty]\n\n[other]\na = 1\n")
        doc.set("b", "2", "empty")
        lines = doc.render().splitlines()
        self.assertIn("[empty]", lines)
        self.assertIn("b = 2", lines)
        self.assertEqual(doc.get("b", "empty"), "2")
        self.assertEqual(doc.get("a", "other"), "1")

    def test_missing_section_is_appended_at_end(self) -> None:
        text = fixture_text("sample.ini")
        doc = IniDocument.from_text(text)
        doc.set("replay_async", "1", "performance")
        rendered = doc.render()
        self.assertTrue(rendered.startswith(text))
        self.assertIn("\n[performance]\nreplay_async = 1\n", rendered)
        self.assertEqual(doc.get("replay_async", "performance"), "1")

    def test_appending_keeps_single_blank_line_separator(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n")
        doc.set("b", "2", "b-section")
        self.assertEqual(doc.render(), "[a]\na = 1\n\n[b-section]\nb = 2\n")

    def test_appending_after_missing_final_newline(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1")
        doc.set("b", "2", "b-section")
        self.assertEqual(doc.render(), "[a]\na = 1\n\n[b-section]\nb = 2\n")
        self.assertEqual(doc.lines[-1].eol, "\n")

    def test_insert_without_final_newline_after_key(self) -> None:
        doc = IniDocument.from_text("[audio]\nvolume = 100")
        doc.set("audio_prefill_ms", "20", "audio")
        self.assertEqual(doc.render(), "[audio]\nvolume = 100\naudio_prefill_ms = 20\n")
        self.assertEqual(doc.get("audio_prefill_ms"), "20")

    def test_insert_without_final_newline_after_header(self) -> None:
        doc = IniDocument.from_text("[audio]")
        doc.set("volume", "100", "audio")
        # 源文本没有任何换行时，无法推断文件风格，插入行使用平台默认换行（design I3）。
        nl = os.linesep
        self.assertEqual(doc.render(), f"[audio]{nl}volume = 100{nl}")

    def test_insert_without_final_newline_after_comment(self) -> None:
        doc = IniDocument.from_text("[audio]\n# 说明")
        doc.set("volume", "100", "audio")
        self.assertEqual(doc.render(), "[audio]\n# 说明\nvolume = 100\n")

    def test_insert_without_final_newline_crlf(self) -> None:
        doc = IniDocument.from_text("[audio]\r\nvolume = 100")
        doc.set("audio_prefill_ms", "20", "audio")
        self.assertEqual(doc.render(), "[audio]\r\nvolume = 100\r\naudio_prefill_ms = 20\r\n")

    def test_insert_uses_detected_crlf(self) -> None:
        doc = IniDocument.from_text("[a]\r\na = 1\r\n")
        doc.set("b", "2", "a")
        self.assertEqual(doc.render(), "[a]\r\na = 1\r\nb = 2\r\n")

    def test_global_key_cannot_be_appended_without_section(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n")
        with self.assertRaises(ValueError):
            doc.set("b", "2")

    def test_global_key_can_be_updated(self) -> None:
        doc = IniDocument.from_text(fixture_text("global.ini"))
        doc.set("fps_limit", "144")
        self.assertEqual(doc.get("fps_limit"), "144")
        self.assertTrue(doc.render().startswith("# 节之前的全局键测试样本（手写合成）。\nfps_limit = 144\n"))

    def test_insert_in_comment_only_section_goes_after_comments(self) -> None:
        doc = IniDocument.from_text("[a]\n# 说明一\n# 说明二\n\n[b]\nx = 1\n")
        doc.set("y", "2", "a")
        self.assertEqual(doc.render(), "[a]\n# 说明一\n# 说明二\ny = 2\n\n[b]\nx = 1\n")

    def test_insert_into_last_section_before_trailing_comments(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n# 说明\n")
        doc.set("b", "2", "a")
        self.assertEqual(doc.render(), "[a]\na = 1\nb = 2\n# 说明\n")


class SetValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = IniDocument.from_text("[a]\na = 1\n")

    def test_rejects_non_string_value(self) -> None:
        with self.assertRaises(TypeError):
            self.doc.set("a", 1)  # type: ignore[arg-type]

    def test_rejects_value_with_newline(self) -> None:
        with self.assertRaises(ValueError):
            self.doc.set("a", "1\n2")

    def test_rejects_empty_key(self) -> None:
        with self.assertRaises(ValueError):
            self.doc.set("  ", "1")

    def test_rejects_invalid_key_name(self) -> None:
        with self.assertRaises(ValueError):
            self.doc.set("bad key", "1")

    def test_rejects_empty_section_name(self) -> None:
        with self.assertRaises(ValueError):
            self.doc.set("b", "1", "  ")

    def test_rejects_section_name_with_brackets(self) -> None:
        with self.assertRaises(ValueError):
            self.doc.set("b", "1", "bad]name")


class UnsetTest(unittest.TestCase):
    def test_unset_removes_all_active_lines_and_keeps_comments(self) -> None:
        text = "# fps_limit = 60\n[frame rate]\nfps_limit = 60\nfps_limit = 120\nrealtime = 1\n"
        doc = IniDocument.from_text(text)
        self.assertEqual(doc.unset("fps_limit"), 2)
        self.assertIsNone(doc.get("fps_limit"))
        self.assertIn("# fps_limit = 60\n", doc.render())
        self.assertIn("realtime = 1\n", doc.render())

    def test_unset_is_scoped_to_section(self) -> None:
        text = "[a]\nx = 1\n[b]\nx = 2\n"
        doc = IniDocument.from_text(text)
        self.assertEqual(doc.unset("x", "a"), 1)
        self.assertEqual(doc.get("x"), "2")
        self.assertEqual(doc.get("x", "a"), None)

    def test_unset_missing_key_returns_zero_and_adds_no_change(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n")
        self.assertEqual(doc.unset("b"), 0)
        self.assertEqual(doc.changes, ())

    def test_unset_then_set_records_both(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n")
        doc.unset("a", "a")
        doc.set("a", "2", "a")
        self.assertEqual(doc.get("a"), "2")
        self.assertEqual([change.op for change in doc.changes], [ChangeOp.UNSET, ChangeOp.SET])

    def test_unset_does_not_remove_section_header(self) -> None:
        doc = IniDocument.from_text("[a]\na = 1\n")
        doc.unset("a")
        self.assertEqual(doc.sections(), ("a",))
        self.assertEqual(doc.render(), "[a]\n")



class DocumentHelpersTest(unittest.TestCase):
    def test_len_and_repr(self) -> None:
        doc = IniDocument.from_text("[a]\nx = 1\n")
        self.assertEqual(len(doc), 2)
        self.assertIn("IniDocument", repr(doc))
        self.assertIn("lines=2", repr(doc))

    def test_set_creates_key_in_requested_section_only(self) -> None:
        doc = IniDocument.from_text("[a]\nx = 1\n\n[b]\ny = 2\n")
        doc.set("x", "9", "b")
        self.assertEqual(doc.get("x", "a"), "1")
        self.assertEqual(doc.get("x", "b"), "9")
        self.assertEqual(doc.get("x"), "9")

if __name__ == "__main__":
    unittest.main()

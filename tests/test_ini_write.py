"""``totk_frontend.ini`` 安全写入测试（M1-T2）。

覆盖：备份、原子替换、只改目标行、回读校验、失败回滚、只读目录、CRLF/BOM、中文路径、
备份重名、临时文件清理、新建文件等边界。
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import os
import re
import stat
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from totk_frontend.ini import (
    IniDocument,
    IniWriteError,
    read_ini,
    write_ini,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BACKUP_PATTERN = re.compile(r"^totk\.ini\.bak-\d{8}-\d{6}(-\d+)?$")


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixed_clock() -> datetime:
    return datetime(2026, 11, 8, 21, 56, 53)


def changed_line_indices(before: bytes, after: bytes) -> list[int]:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if len(before_lines) != len(after_lines):
        raise AssertionError("行数发生变化，不能按行比较")
    return [index for index, (a, b) in enumerate(zip(before_lines, after_lines)) if a != b]


class WriteTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "totk.ini"

    def write_sample(self, name: str = "sample.ini") -> IniDocument:
        text = fixture_text(name)
        self.path.write_text(text, encoding="utf-8")
        return IniDocument.from_path(self.path)

    def list_temp_files(self) -> list[str]:
        return [entry.name for entry in self.dir.iterdir() if ".tmp-" in entry.name]

    def list_backups(self) -> list[Path]:
        return sorted(entry for entry in self.dir.iterdir() if ".bak-" in entry.name)


class BackupTest(WriteTestBase):
    def test_backup_created_before_write_with_original_bytes(self) -> None:
        self.path.write_bytes(fixture_text("sample.ini").encode("utf-8"))
        before = self.path.read_bytes()
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120", "frame rate")
        result = write_ini(self.path, doc, clock=fixed_clock)
        self.assertTrue(result.changed)
        self.assertIsNotNone(result.backup_path)
        backup = result.backup_path
        assert backup is not None
        self.assertRegex(backup.name, BACKUP_PATTERN)
        self.assertTrue(backup.parent == self.path.parent)
        self.assertEqual(backup.read_bytes(), before)

    def test_backup_is_kept_after_success(self) -> None:
        doc = self.write_sample()
        doc.set("volume", "80", "audio")
        write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(len(self.list_backups()), 1)

    def test_backup_name_collision_gets_suffix(self) -> None:
        self.path.write_text("[a]\na = 1\n", encoding="utf-8")
        first = IniDocument.from_path(self.path)
        first.set("a", "2")
        result_one = write_ini(self.path, first, clock=fixed_clock)
        second = IniDocument.from_path(self.path)
        second.set("a", "3")
        result_two = write_ini(self.path, second, clock=fixed_clock)
        self.assertIsNotNone(result_one.backup_path)
        self.assertIsNotNone(result_two.backup_path)
        assert result_one.backup_path is not None and result_two.backup_path is not None
        self.assertTrue(result_one.backup_path.name.endswith("215653"))
        self.assertTrue(result_two.backup_path.name.endswith("-2"))
        self.assertEqual(len(self.list_backups()), 2)
        self.assertEqual(result_two.backup_path.read_bytes(), b"[a]\na = 2\n")

    def test_no_change_skips_backup_and_write(self) -> None:
        doc = self.write_sample()
        before = self.path.read_bytes()
        result = write_ini(self.path, doc, clock=fixed_clock)
        self.assertFalse(result.changed)
        self.assertIsNone(result.backup_path)
        self.assertEqual(result.bytes_written, 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.list_backups(), [])

    def test_backup_can_be_disabled(self) -> None:
        self.path.write_text("[a]\na = 1\n", encoding="utf-8")
        doc = IniDocument.from_path(self.path)
        doc.set("a", "2")
        result = write_ini(self.path, doc, backup=False, clock=fixed_clock)
        self.assertIsNone(result.backup_path)
        self.assertEqual(self.list_backups(), [])


class AtomicWriteTest(WriteTestBase):
    def test_only_target_line_changes_on_sample(self) -> None:
        self.path.write_bytes(fixture_text("sample.ini").encode("utf-8"))
        before = self.path.read_bytes()
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120", "frame rate")
        write_ini(self.path, doc, clock=fixed_clock)
        after = self.path.read_bytes()
        indices = changed_line_indices(before, after)
        self.assertEqual(len(indices), 1)
        self.assertEqual(after.splitlines()[indices[0]], b"fps_limit = 120")
        for index, (old, new) in enumerate(zip(before.splitlines(keepends=True), after.splitlines(keepends=True))):
            if index == indices[0]:
                continue
            self.assertEqual(old, new)

    def test_backup_equals_original_and_written_file_equals_render(self) -> None:
        doc = self.write_sample()
        doc.set("sharpness", "50", "display")
        result = write_ini(self.path, doc, clock=fixed_clock)
        assert result.backup_path is not None
        self.assertEqual(result.backup_path.read_bytes(), fixture_text("sample.ini").encode("utf-8"))
        self.assertEqual(self.path.read_bytes(), doc.to_bytes())

    def test_crlf_preserved(self) -> None:
        original = fixture_text("sample.ini").replace("\n", "\r\n").encode("utf-8")
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120", "frame rate")
        write_ini(self.path, doc, clock=fixed_clock)
        after = self.path.read_bytes()
        self.assertEqual(after.count(b"\r\n"), original.count(b"\r\n"))
        self.assertEqual(after.count(b"\n"), original.count(b"\n"))
        self.assertEqual(changed_line_indices(original, after), [5])

    def test_bom_preserved(self) -> None:
        original = "\ufeff[fps]\nfps_limit = 60\n".encode("utf-8")
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "90")
        write_ini(self.path, doc, clock=fixed_clock)
        after = self.path.read_bytes()
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(after, "\ufeff[fps]\nfps_limit = 90\n".encode("utf-8"))

    def test_missing_final_newline_preserved_for_existing_key(self) -> None:
        self.path.write_bytes(b"[fps]\nfps_limit = 60")
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "90")
        write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(self.path.read_bytes(), b"[fps]\nfps_limit = 90")

    def test_insert_without_final_newline_writes_valid_ini(self) -> None:
        self.path.write_bytes(b"[audio]\nvolume = 100")
        doc = IniDocument.from_path(self.path)
        doc.set("audio_prefill_ms", "20", "audio")
        write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(
            self.path.read_bytes(),
            b"[audio]\nvolume = 100\naudio_prefill_ms = 20\n",
        )
        reparsed = IniDocument.from_bytes(self.path.read_bytes())
        self.assertEqual(reparsed.get("volume"), "100")
        self.assertEqual(reparsed.get("audio_prefill_ms"), "20")

    def test_chinese_path_is_supported(self) -> None:
        directory = self.dir / "测试 目录"
        directory.mkdir()
        target = directory / "totk.ini"
        target.write_text("[audio]\nvolume = 100\n", encoding="utf-8")
        doc = IniDocument.from_path(target)
        doc.set("volume", "80", "audio")
        result = write_ini(target, doc, clock=fixed_clock)
        self.assertTrue(result.changed)
        self.assertEqual(target.read_bytes(), "[audio]\nvolume = 80\n".encode("utf-8"))
        assert result.backup_path is not None
        self.assertEqual(result.backup_path.read_bytes(), "[audio]\nvolume = 100\n".encode("utf-8"))

    def test_new_file_is_created_without_backup(self) -> None:
        doc = IniDocument.from_text("[display]\nfullscreen = 1\n")
        result = write_ini(self.path, doc, clock=fixed_clock)
        self.assertTrue(result.changed)
        self.assertIsNone(result.backup_path)
        self.assertEqual(self.path.read_bytes(), b"[display]\nfullscreen = 1\n")
        self.assertEqual(self.list_backups(), [])

    def test_missing_parent_directory_raises(self) -> None:
        doc = IniDocument.from_text("[display]\nfullscreen = 1\n")
        with self.assertRaises(IniWriteError):
            write_ini(self.dir / "missing" / "totk.ini", doc, clock=fixed_clock)

    def test_no_temp_files_left_after_success(self) -> None:
        doc = self.write_sample()
        doc.set("volume", "80", "audio")
        write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(self.list_temp_files(), [])

    def test_read_ini_reads_written_file(self) -> None:
        self.path.write_text("[fps]\nfps_limit = 60\n", encoding="utf-8")
        doc = read_ini(self.path)
        self.assertEqual(doc.get("fps_limit"), "60")

    def test_write_requires_document(self) -> None:
        with self.assertRaises(TypeError):
            write_ini(self.path, "not a document")  # type: ignore[arg-type]

    def test_unset_is_written_and_verified(self) -> None:
        self.path.write_text("[input]\nmotion = 1\nrumble = 1\n", encoding="utf-8")
        doc = IniDocument.from_path(self.path)
        doc.unset("motion", "input")
        write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(self.path.read_bytes(), b"[input]\nrumble = 1\n")


class RollbackTest(WriteTestBase):
    def test_verify_failure_restores_original_and_keeps_backup(self) -> None:
        original = b"[fps]\nfps_limit = 60\n"
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120")
        with mock.patch("totk_frontend.ini._read_back", return_value=b"corrupted"):
            with self.assertRaises(IniWriteError) as caught:
                write_ini(self.path, doc, clock=fixed_clock)
        self.assertIn("已恢复原文件内容", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), original)
        backups = self.list_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(self.list_temp_files(), [])

    def test_replace_failure_keeps_original_and_cleans_temp(self) -> None:
        original = b"[fps]\nfps_limit = 60\n"
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120")
        with mock.patch("totk_frontend.ini._atomic_replace", side_effect=OSError("模拟替换失败")):
            with self.assertRaises(IniWriteError) as caught:
                write_ini(self.path, doc, clock=fixed_clock)
        self.assertIn("模拟替换失败", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.list_temp_files(), [])
        self.assertEqual(len(self.list_backups()), 1)

    def test_verify_failure_on_new_file_removes_it(self) -> None:
        doc = IniDocument.from_text("[display]\nfullscreen = 1\n")
        with mock.patch("totk_frontend.ini._read_back", return_value=b"corrupted"):
            with self.assertRaises(IniWriteError) as caught:
                write_ini(self.path, doc, clock=fixed_clock)
        self.assertIn("已删除", str(caught.exception))
        self.assertFalse(self.path.exists())
        self.assertEqual(self.list_temp_files(), [])

    @unittest.skipUnless(os.name == "posix", "文件权限位语义依赖 POSIX")
    def test_restore_keeps_file_mode(self) -> None:
        original = b"[fps]\nfps_limit = 60\n"
        self.path.write_bytes(original)
        os.chmod(self.path, 0o600)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120")
        with mock.patch("totk_frontend.ini._read_back", return_value=b"corrupted"):
            with self.assertRaises(IniWriteError):
                write_ini(self.path, doc, clock=fixed_clock)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(self.path.read_bytes(), original)


@unittest.skipUnless(os.name == "posix", "只读目录测试依赖 POSIX 权限语义")
class ReadOnlyDirectoryTest(WriteTestBase):
    def test_readonly_directory_fails_without_touching_original(self) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 用户不受目录权限限制")
        original = b"[fps]\nfps_limit = 60\n"
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120")
        os.chmod(self.dir, 0o500)
        self.addCleanup(os.chmod, self.dir, 0o700)
        with self.assertRaises(IniWriteError):
            write_ini(self.path, doc, clock=fixed_clock)
        os.chmod(self.dir, 0o700)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.list_temp_files(), [])
        self.assertEqual(self.list_backups(), [])



class WriterEdgeCaseTest(WriteTestBase):
    def test_create_backup_requires_existing_file(self) -> None:
        from totk_frontend.ini import create_backup

        with self.assertRaises(IniWriteError):
            create_backup(self.path, clock=fixed_clock)

    def test_write_to_directory_path_fails(self) -> None:
        directory = self.dir / "totk.ini"
        directory.mkdir()
        doc = IniDocument.from_text("[a]\na = 1\n")
        with self.assertRaises(IniWriteError):
            write_ini(directory, doc, clock=fixed_clock)

    def test_write_bytes_atomic_requires_bytes(self) -> None:
        from totk_frontend.ini import write_bytes_atomic

        with self.assertRaises(TypeError):
            write_bytes_atomic(self.path, "text")  # type: ignore[arg-type]

    def test_restore_failure_is_reported(self) -> None:
        from totk_frontend import ini as ini_module

        original = b"[fps]\nfps_limit = 60\n"
        self.path.write_bytes(original)
        doc = IniDocument.from_path(self.path)
        doc.set("fps_limit", "120")
        real_write = ini_module.write_bytes_atomic
        calls = {"count": 0}

        def flaky_write(path, data, *, mode=None):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] == 1:
                real_write(path, data, mode=mode)
            else:
                raise OSError("模拟回滚失败")

        with mock.patch("totk_frontend.ini.write_bytes_atomic", side_effect=flaky_write), mock.patch(
            "totk_frontend.ini._read_back", return_value=b"corrupted"
        ):
            with self.assertRaises(IniWriteError) as caught:
                write_ini(self.path, doc, clock=fixed_clock)
        self.assertIn("回滚失败", str(caught.exception))

if __name__ == "__main__":
    unittest.main()

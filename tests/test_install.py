"""安装目录检测测试（M3-T1 的检测部分）。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import tempfile
import unittest
from pathlib import Path

from totk_frontend.install import (
    ALL_MARKERS,
    detect_install,
    find_install,
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


if __name__ == "__main__":
    unittest.main()

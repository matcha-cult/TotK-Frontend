"""版本感知测试（M5-T3）。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import unittest

from totk_frontend.settings import SETTINGS
from totk_frontend.versions import (
    DEFAULT_VERSION,
    KNOWN_VERSIONS,
    VERSION_NOTES,
    describe_version,
    get_version_note,
    is_known_version,
    key_supported_in,
    unsupported_keys,
    versions_for_key,
)


class VersionCatalogTest(unittest.TestCase):
    def test_known_versions_match_documentation(self) -> None:
        self.assertEqual(KNOWN_VERSIONS, ("1.1.0", "1.2.1", "1.4.3"))
        self.assertEqual(DEFAULT_VERSION, "1.4.3")
        self.assertEqual(set(VERSION_NOTES), set(KNOWN_VERSIONS))
        for version, note in VERSION_NOTES.items():
            self.assertEqual(note.version, version)
            self.assertTrue(note.label.startswith("TotK Recomp"))
            self.assertTrue(note.summary.strip())
            self.assertTrue(note.mouse_camera.strip())

    def test_version_capabilities_from_design_doc(self) -> None:
        self.assertFalse(VERSION_NOTES["1.1.0"].menu_cursor)
        self.assertFalse(VERSION_NOTES["1.1.0"].fov)
        self.assertIn("摇杆模拟", VERSION_NOTES["1.1.0"].mouse_camera)
        self.assertFalse(VERSION_NOTES["1.2.1"].menu_cursor)
        self.assertFalse(VERSION_NOTES["1.2.1"].fov)
        self.assertTrue(VERSION_NOTES["1.4.3"].menu_cursor)
        self.assertTrue(VERSION_NOTES["1.4.3"].fov)

    def test_is_known_version(self) -> None:
        self.assertTrue(is_known_version("1.4.3"))
        self.assertTrue(is_known_version(" 1.2.1 "))
        self.assertFalse(is_known_version("9.9.9"))
        self.assertFalse(is_known_version(""))
        self.assertFalse(is_known_version(143))  # type: ignore[arg-type]

    def test_get_version_note(self) -> None:
        note = get_version_note("1.4.3")
        self.assertIsNotNone(note)
        assert note is not None
        self.assertEqual(note.version, "1.4.3")
        self.assertIsNone(get_version_note("9.9.9"))
        with self.assertRaises(TypeError):
            get_version_note(143)  # type: ignore[arg-type]


class KeySupportTest(unittest.TestCase):
    def test_restricted_keys_are_documented(self) -> None:
        self.assertEqual(versions_for_key("menu_cursor"), ("1.4.3",))
        self.assertEqual(versions_for_key("fov"), ("1.4.3",))
        self.assertEqual(versions_for_key("volume"), ())

    def test_key_supported_in(self) -> None:
        for version in ("1.1.0", "1.2.1"):
            self.assertFalse(key_supported_in("menu_cursor", version), version)
            self.assertFalse(key_supported_in("fov", version), version)
            self.assertTrue(key_supported_in("volume", version), version)
        self.assertTrue(key_supported_in("menu_cursor", "1.4.3"))
        self.assertTrue(key_supported_in("fov", "1.4.3"))

    def test_unknown_key_and_bad_type(self) -> None:
        with self.assertRaises(ValueError):
            versions_for_key("not_a_key")
        with self.assertRaises(ValueError):
            key_supported_in("not_a_key", "1.4.3")
        with self.assertRaises(TypeError):
            key_supported_in("volume", 143)  # type: ignore[arg-type]

    def test_unsupported_keys_per_version(self) -> None:
        self.assertEqual(set(unsupported_keys("1.1.0")), {"fov", "menu_cursor"})
        self.assertEqual(set(unsupported_keys("1.2.1")), {"fov", "menu_cursor"})
        self.assertEqual(unsupported_keys("1.4.3"), ())
        self.assertEqual(unsupported_keys("9.9.9"), ("fov", "menu_cursor"))
        with self.assertRaises(TypeError):
            unsupported_keys(143)  # type: ignore[arg-type]

    def test_only_documented_keys_are_version_restricted(self) -> None:
        restricted = [setting.key for setting in SETTINGS if setting.versions]
        self.assertEqual(set(restricted), {"fov", "menu_cursor"})


class DescribeVersionTest(unittest.TestCase):
    def test_describe_known_version(self) -> None:
        text = describe_version("1.4.3")
        self.assertIn("TotK Recomp 1.4.3", text)
        self.assertIn("全部已注册版本限定键", text)
        old = describe_version("1.1.0")
        self.assertIn("摇杆模拟", old)
        self.assertIn("fov（仅 1.4.3）", old)
        self.assertIn("menu_cursor（仅 1.4.3）", old)

    def test_describe_unknown_version(self) -> None:
        text = describe_version("9.9.9")
        self.assertIn("未记录的 TotK Recomp 版本", text)
        self.assertIn("9.9.9", text)


if __name__ == "__main__":
    unittest.main()

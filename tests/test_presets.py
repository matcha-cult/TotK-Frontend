"""预设定义测试（M2-T1）：只使用注册表键、值合法、不含危险值。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import unittest

from totk_frontend.presets import (
    FORBIDDEN_VALUES,
    PRESETS,
    Preset,
    PresetEntry,
    get_preset,
    preset_names,
    validate_preset,
    validate_presets,
)
from totk_frontend.settings import get_setting
from totk_frontend.validate import Severity, validate_value

# docs/settings.md 第 9 节“必须包含”的键值。
REQUIRED_ENTRIES = {
    "savage-wind": {
        "prompts": "pc",
        "mouse_mode": "direct",
        "menu_cursor": "1",
        "fps_limit": "60",
        "realtime": "1",
        "sharpness": "80",
    },
    "controller": {
        "prompts": "nintendo",
        "pad_layout": "auto",
        "motion": "1",
        "rumble": "1",
    },
    "performance": {
        "fps_limit": "60",
        "aniso": "game",
        "shadow_scale": "1",
        "render_scale": "game",
        "replay_async": "1",
    },
    "quality": {
        "render_scale": "100",
        "aniso": "16",
        "shadow_scale": "2",
        "pcss": "50",
        "contact_shadows": "50",
    },
}


class PresetDefinitionTest(unittest.TestCase):
    def test_expected_presets_exist(self) -> None:
        self.assertEqual(
            preset_names(),
            ("savage-wind", "controller", "performance", "quality"),
        )
        for preset in PRESETS:
            self.assertTrue(preset.label.strip(), preset.name)
            self.assertTrue(preset.description.strip(), preset.name)
            self.assertTrue(preset.entries, preset.name)

    def test_lookup_is_case_insensitive(self) -> None:
        self.assertIs(get_preset("savage-wind"), get_preset("SAVAGE-WIND"))
        self.assertIsNotNone(get_preset(" Controller "))
        self.assertIsNone(get_preset("unknown-preset"))
        with self.assertRaises(TypeError):
            get_preset(123)  # type: ignore[arg-type]

    def test_entries_only_use_registered_keys(self) -> None:
        for preset in PRESETS:
            for entry in preset.entries:
                self.assertIsNotNone(
                    get_setting(entry.key),
                    f"{preset.name} 使用了未注册的键 {entry.key}",
                )

    def test_entry_values_pass_validation(self) -> None:
        for preset in PRESETS:
            for entry in preset.entries:
                setting = get_setting(entry.key)
                assert setting is not None
                errors = [
                    issue
                    for issue in validate_value(setting, entry.value, key=entry.key)
                    if issue.severity is Severity.ERROR
                ]
                self.assertEqual(errors, [], f"{preset.name}: {entry.key}={entry.value}")

    def test_no_forbidden_values(self) -> None:
        forbidden = set(FORBIDDEN_VALUES)
        for preset in PRESETS:
            for entry in preset.entries:
                self.assertNotIn(
                    (entry.key.strip().lower(), entry.value.strip().lower()),
                    forbidden,
                    f"{preset.name} 含危险值 {entry.key}={entry.value}",
                )

    def test_required_entries_from_settings_doc(self) -> None:
        for preset in PRESETS:
            values = {entry.key: entry.value for entry in preset.entries}
            expected = REQUIRED_ENTRIES[preset.name]
            for key, value in expected.items():
                self.assertEqual(values.get(key), value, f"{preset.name}.{key}")

    def test_definitions_are_valid(self) -> None:
        self.assertEqual(validate_presets(), [])

    def test_menu_cursor_is_version_restricted(self) -> None:
        savage = get_preset("savage-wind")
        assert savage is not None
        entry = next(item for item in savage.entries if item.key == "menu_cursor")
        self.assertEqual(entry.versions, ("1.4.3",))


class PresetValidationTest(unittest.TestCase):
    def test_unknown_key_is_rejected(self) -> None:
        preset = Preset(
            name="broken",
            label="测试",
            description="",
            entries=(PresetEntry("unknown_future_key", "1"),),
        )
        codes = [issue.code for issue in validate_preset(preset)]
        self.assertIn("preset.unknown_key", codes)

    def test_forbidden_value_is_rejected(self) -> None:
        for key, value in FORBIDDEN_VALUES:
            preset = Preset(
                name="broken",
                label="测试",
                description="",
                entries=(PresetEntry(key, value),),
            )
            codes = [issue.code for issue in validate_preset(preset)]
            self.assertIn("preset.forbidden_value", codes)

    def test_duplicate_key_is_rejected(self) -> None:
        preset = Preset(
            name="broken",
            label="测试",
            description="",
            entries=(PresetEntry("volume", "50"), PresetEntry("volume", "60")),
        )
        codes = [issue.code for issue in validate_preset(preset)]
        self.assertIn("preset.duplicate_key", codes)

    def test_invalid_value_is_rejected(self) -> None:
        preset = Preset(
            name="broken",
            label="测试",
            description="",
            entries=(PresetEntry("volume", "1000"),),
        )
        codes = [issue.code for issue in validate_preset(preset)]
        self.assertIn("value.range", codes)


if __name__ == "__main__":
    unittest.main()

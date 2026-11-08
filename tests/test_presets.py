"""预设定义测试（M2-T1）：只使用注册表键、值合法、不含危险值。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import unittest

from totk_frontend.ini import IniDocument
from totk_frontend.presets import (
    FORBIDDEN_VALUES,
    PRESETS,
    Preset,
    PresetEntry,
    apply_preset,
    format_plan,
    get_preset,
    plan_preset,
    preset_names,
    revert_plan,
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


DIFFERING_DOC = """[frame rate]
fps_limit = 30
realtime = 0
[input]
prompts = nintendo
mouse_mode = stick
menu_cursor = 0
[display]
sharpness = 0
"""

SAVAGE_KEYS = ("prompts", "mouse_mode", "menu_cursor", "fps_limit", "realtime", "sharpness")


class PresetPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = IniDocument.from_text(DIFFERING_DOC)

    def test_plan_is_the_diff_set_in_preset_order(self) -> None:
        plan = plan_preset(self.doc, "savage-wind", version="1.4.3")
        self.assertEqual([change.key for change in plan.changes], list(SAVAGE_KEYS))
        old_values = {change.key: change.old_value for change in plan.changes}
        self.assertEqual(old_values["fps_limit"], "30")
        self.assertEqual(old_values["realtime"], "0")
        self.assertEqual(old_values["prompts"], "nintendo")
        self.assertEqual(old_values["mouse_mode"], "stick")
        self.assertEqual(old_values["menu_cursor"], "0")
        self.assertEqual(old_values["sharpness"], "0")
        self.assertEqual(plan.warnings, ())

    def test_plan_does_not_modify_document(self) -> None:
        plan_preset(self.doc, "savage-wind", version="1.4.3")
        self.assertEqual(self.doc.render(), DIFFERING_DOC)

    def test_defaults_equal_target_count_as_unchanged(self) -> None:
        plan = plan_preset(IniDocument.from_text(""), "controller")
        self.assertTrue(plan.is_empty)
        self.assertEqual(set(plan.unchanged), {"prompts", "pad_layout", "motion", "rumble"})
        self.assertEqual(plan.skipped, ())

    def test_version_filter_skips_menu_cursor(self) -> None:
        plan = plan_preset(self.doc, "savage-wind", version="1.2.1")
        self.assertNotIn("menu_cursor", [change.key for change in plan.changes])
        self.assertEqual([key for key, _ in plan.skipped], ["menu_cursor"])
        include = plan_preset(self.doc, "savage-wind")
        self.assertIn("menu_cursor", [change.key for change in include.changes])

    def test_plan_accepts_preset_object(self) -> None:
        preset = get_preset("quality")
        assert preset is not None
        plan = plan_preset(self.doc, preset)
        self.assertEqual(plan.preset.name, "quality")

    def test_plan_rejects_unknown_preset_and_bad_types(self) -> None:
        with self.assertRaises(ValueError):
            plan_preset(self.doc, "no-such-preset")
        with self.assertRaises(TypeError):
            plan_preset(self.doc, 123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plan_preset("not a document", "controller")  # type: ignore[arg-type]

    def test_post_apply_warnings_are_previewed(self) -> None:
        doc = IniDocument.from_text("[display]\nupscaler = fsr\nsharpness = 0\n")
        plan = plan_preset(doc, "quality")
        self.assertTrue(any(issue.code == "rule.upscaler_sharpness" for issue in plan.warnings))


class PresetApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = IniDocument.from_text(DIFFERING_DOC)

    def test_apply_changes_only_target_keys(self) -> None:
        before = self.doc.render()
        plan = apply_preset(self.doc, "savage-wind", version="1.4.3")
        self.assertEqual(len(plan.changes), len(SAVAGE_KEYS))
        self.assertEqual(self.doc.render().count("\n"), before.count("\n"))
        for change in plan.changes:
            self.assertEqual(self.doc.get(change.key), change.new_value)
        # 其余行逐字节一致
        before_lines = before.splitlines(keepends=True)
        after_lines = self.doc.render().splitlines(keepends=True)
        for old, new in zip(before_lines, after_lines):
            if old != new:
                key = old.split("=")[0].strip()
                self.assertIn(key, SAVAGE_KEYS)

    def test_apply_is_idempotent(self) -> None:
        apply_preset(self.doc, "savage-wind", version="1.4.3")
        rendered = self.doc.render()
        plan = plan_preset(self.doc, "savage-wind", version="1.4.3")
        self.assertTrue(plan.is_empty)
        apply_preset(self.doc, "savage-wind", version="1.4.3")
        self.assertEqual(self.doc.render(), rendered)

    def test_apply_inserts_missing_keys_in_registry_sections(self) -> None:
        doc = IniDocument.from_text("[display]\nrender_scale = game\n")
        apply_preset(doc, "quality")
        self.assertEqual(doc.get("render_scale"), "100")
        self.assertEqual(doc.get("aniso"), "16")
        self.assertEqual(doc.get("shadow_scale"), "2")
        self.assertEqual(doc.get("pcss"), "50")
        self.assertEqual(doc.get("contact_shadows"), "50")
        self.assertIn("display", doc.sections())


class PresetRevertTest(unittest.TestCase):
    def test_revert_restores_previous_values_and_removes_added_keys(self) -> None:
        doc = IniDocument.from_text("[display]\nrender_scale = game\n[input]\nprompts = nintendo\n")
        before = doc.render()
        plan = apply_preset(doc, "quality")
        self.assertNotEqual(doc.render(), before)
        reverted = revert_plan(doc, plan)
        self.assertEqual(reverted, len(plan.changes))
        self.assertEqual(doc.render(), before)

    def test_revert_with_mixed_existing_and_missing_keys(self) -> None:
        doc = IniDocument.from_text("[frame rate]\nfps_limit = 30\n")
        before = doc.render()
        plan = apply_preset(doc, "savage-wind", version="1.4.3")
        revert_plan(doc, plan)
        self.assertEqual(doc.get("fps_limit"), "30")
        self.assertIsNone(doc.get("prompts"))
        # 应用时新建的空节头保留（与 design I5 一致），其余内容恢复原样。
        self.assertEqual(doc.render(), before + "\n[input]\n")

    def test_revert_keeps_section_created_by_apply(self) -> None:
        doc = IniDocument.from_text("")
        plan = apply_preset(doc, "quality")
        self.assertTrue(plan.changes)
        revert_plan(doc, plan)
        # 新建文件的换行按平台默认（design I3），因此按行比较而不是按字节比较。
        self.assertEqual(doc.render().splitlines(), ["[display]"])

    def test_revert_requires_plan(self) -> None:
        with self.assertRaises(TypeError):
            revert_plan(self.doc if hasattr(self, "doc") else IniDocument.from_text(""), "not a plan")  # type: ignore[arg-type]

    def test_rollback_through_write_ini(self) -> None:
        import tempfile
        from pathlib import Path as PathType

        from totk_frontend.ini import write_ini

        with tempfile.TemporaryDirectory() as directory:
            path = PathType(directory) / "totk.ini"
            path.write_text(DIFFERING_DOC, encoding="utf-8")
            original = path.read_bytes()
            document = IniDocument.from_path(path)
            plan = apply_preset(document, "savage-wind", version="1.4.3")
            write_ini(path, document)
            self.assertNotEqual(path.read_bytes(), original)
            reloaded = IniDocument.from_path(path)
            revert_plan(reloaded, plan)
            write_ini(path, reloaded)
            self.assertEqual(path.read_bytes(), original)


class PresetFormatTest(unittest.TestCase):
    def test_format_shows_changes_and_version(self) -> None:
        doc = IniDocument.from_text(DIFFERING_DOC)
        text = format_plan(plan_preset(doc, "savage-wind", version="1.4.3"))
        self.assertIn("Savage Wind 风格", text)
        self.assertIn("TotK Recomp 1.4.3", text)
        self.assertIn("将修改 6 项", text)
        self.assertIn("prompts: nintendo -> pc", text)

    def test_format_shows_skipped_and_empty_plan(self) -> None:
        doc = IniDocument.from_text(DIFFERING_DOC)
        skipped = format_plan(plan_preset(doc, "savage-wind", version="1.2.1"))
        self.assertIn("跳过 menu_cursor", skipped)
        empty = format_plan(plan_preset(IniDocument.from_text(""), "controller"))
        self.assertIn("无需改动", empty)

    def test_format_requires_plan(self) -> None:
        with self.assertRaises(TypeError):
            format_plan("not a plan")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

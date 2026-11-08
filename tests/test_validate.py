"""设置校验测试（M1-T4）：单键规则与 ``docs/settings.md`` 第 8 节跨字段规则。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import unittest

from totk_frontend.ini import IniDocument
from totk_frontend.settings import get_setting
from totk_frontend.validate import (
    Issue,
    Severity,
    effective_value,
    is_16_9,
    parse_resolution,
    validate_document,
    validate_value,
)


def make_doc(text: str) -> IniDocument:
    return IniDocument.from_text(text)


def setting(key: str):
    found = get_setting(key)
    assert found is not None, key
    return found


def errors(issues: list[Issue]) -> list[Issue]:
    return [issue for issue in issues if issue.severity is Severity.ERROR]


def codes(issues: list[Issue]) -> list[str]:
    return [issue.code for issue in issues]


class SingleValueTest(unittest.TestCase):
    def test_bool(self) -> None:
        realtime = setting("realtime")
        self.assertEqual(validate_value(realtime, "0"), [])
        self.assertEqual(validate_value(realtime, "1"), [])
        for bad in ("2", "true", "yes", "-1"):
            issues = validate_value(realtime, bad)
            self.assertEqual(codes(issues), ["value.type"])
            self.assertEqual(issues[0].keys, ("realtime",))

    def test_empty_value(self) -> None:
        issues = validate_value(setting("locale"), "")
        self.assertEqual(codes(issues), ["value.empty"])
        self.assertEqual(validate_value(setting("gpu_name"), ""), [])
        self.assertEqual(validate_value(setting("menu_lang"), ""), [])

    def test_integer_range_and_extra_choices(self) -> None:
        fps = setting("fps_limit")
        for value in ("30", "45", "60", "144", "240", "display"):
            self.assertEqual(validate_value(fps, value), [], value)
        for bad in ("29", "241", "0", "-60"):
            self.assertEqual(codes(validate_value(fps, bad)), ["value.range"], bad)
        for bad in ("60.5", "fast", ""):
            self.assertEqual(codes(validate_value(fps, bad)), ["value.type" if bad else "value.empty"], bad)

    def test_integer_negative_range(self) -> None:
        brightness = setting("color_brightness")
        self.assertEqual(validate_value(brightness, "-30"), [])
        self.assertEqual(validate_value(brightness, "30"), [])
        self.assertEqual(codes(validate_value(brightness, "-31")), ["value.range"])
        self.assertEqual(codes(validate_value(brightness, "31")), ["value.range"])

    def test_number(self) -> None:
        gamma = setting("color_gamma")
        for value in ("0.8", "1", "1.2"):
            self.assertEqual(validate_value(gamma, value), [], value)
        for bad in ("0.79", "1.21"):
            self.assertEqual(codes(validate_value(gamma, bad)), ["value.range"], bad)
        for bad in ("abc", "nan", "inf"):
            self.assertEqual(codes(validate_value(gamma, bad)), ["value.type"], bad)

    def test_enum_is_case_insensitive(self) -> None:
        upscaler = setting("upscaler")
        self.assertEqual(validate_value(upscaler, "fsr"), [])
        self.assertEqual(validate_value(upscaler, "BILINEAR"), [])
        issues = validate_value(upscaler, "lanczos")
        self.assertEqual(codes(issues), ["value.choice"])
        self.assertIn("fsr", issues[0].suggestion)

    def test_resolution(self) -> None:
        window = setting("window_size")
        for value in ("640x360", "1920x1080", "7680x4320", "1920X1080"):
            self.assertEqual(validate_value(window, value), [], value)
        self.assertEqual(codes(validate_value(window, "1280x720")), [])
        self.assertEqual(codes(validate_value(window, "639x360")), ["value.range"])
        self.assertEqual(codes(validate_value(window, "1920*1080")), ["value.resolution"])
        self.assertEqual(codes(validate_value(window, "big")), ["value.resolution"])
        output = setting("output_res")
        self.assertEqual(codes(validate_value(output, "1279x720")), ["value.range"])
        self.assertEqual(codes(validate_value(output, "1280x719")), ["value.range"])

    def test_keyname(self) -> None:
        walk = setting("walk_key")
        self.assertEqual(validate_value(walk, "lshift"), [])
        self.assertEqual(validate_value(walk, "none"), [])
        self.assertEqual(codes(validate_value(walk, "bad key")), ["value.keyname"])
        self.assertEqual(codes(validate_value(walk, "9lives")), ["value.keyname"])

    def test_binding(self) -> None:
        binding = setting("bind_A")
        self.assertEqual(validate_value(binding, "none"), [])
        self.assertEqual(validate_value(binding, "pad:east, key:E"), [])
        self.assertEqual(validate_value(binding, "pad:east,key:E"), [])
        self.assertEqual(validate_value(binding, "key:default"), [])
        for bad in ("bogus", "pad:", "pad:east, oops", ":key"):
            self.assertEqual(codes(validate_value(binding, bad, key="bind_a")), ["value.binding"], bad)

    def test_text(self) -> None:
        locale = setting("locale")
        self.assertEqual(validate_value(locale, "ja"), [])
        self.assertEqual(validate_value(locale, "zh-Hans"), [])


class CrossFieldRuleTest(unittest.TestCase):
    def test_fps_limit_needs_realtime(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = 120\nrealtime = 0\n")
        issues = errors(validate_document(doc))
        self.assertIn("rule.fps_limit_realtime", codes(issues))
        issue = next(item for item in issues if item.code == "rule.fps_limit_realtime")
        self.assertEqual(issue.keys, ("fps_limit", "realtime"))
        self.assertIn("realtime", issue.suggestion)

    def test_fps_limit_boundaries(self) -> None:
        self.assertEqual(errors(validate_document(make_doc("[frame rate]\nfps_limit = 60\nrealtime = 0\n"))), [])
        self.assertEqual(errors(validate_document(make_doc("[frame rate]\nfps_limit = 61\nrealtime = 1\n"))), [])
        self.assertEqual(errors(validate_document(make_doc("[frame rate]\nfps_limit = 61\n"))), [])

    def test_fps_limit_display_value_is_skipped(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = display\nrealtime = 0\n")
        self.assertEqual(errors(validate_document(doc)), [])

    def test_free_cores_crash(self) -> None:
        doc = make_doc("[performance]\nfree_cores = 1\n")
        issues = errors(validate_document(doc))
        self.assertEqual(codes(issues), ["rule.free_cores"])
        self.assertEqual(issues[0].keys, ("free_cores",))
        self.assertEqual(errors(validate_document(make_doc("[performance]\nfree_cores = 0\n"))), [])

    def test_mouse_sens_zero(self) -> None:
        doc = make_doc("[input]\nmouse_mode = direct\nmouse_sens = 0\n")
        issues = validate_document(doc)
        self.assertIn("rule.mouse_sens_off", codes(issues))
        warning = next(item for item in issues if item.code == "rule.mouse_sens_off")
        self.assertEqual(warning.severity, Severity.WARNING)

    def test_mouse_sens_zero_with_stick_mode_is_not_warned(self) -> None:
        doc = make_doc("[input]\nmouse_mode = stick\nmouse_sens = 0\n")
        self.assertNotIn("rule.mouse_sens_off", codes(validate_document(doc)))

    def test_mouse_camera_expectation_override(self) -> None:
        doc = make_doc("[input]\nmouse_sens = 0\n")
        self.assertEqual(validate_document(doc, mouse_camera_expected=False), [])
        self.assertIn(
            "rule.mouse_sens_off",
            codes(validate_document(doc, mouse_camera_expected=True)),
        )

    def test_prompts_with_non_16_9_output(self) -> None:
        doc = make_doc("[display]\noutput_res = 3440x1440\n[input]\nprompts = pc\n")
        issues = validate_document(doc)
        self.assertIn("rule.prompts_aspect", codes(issues))
        warning = next(item for item in issues if item.code == "rule.prompts_aspect")
        self.assertEqual(warning.severity, Severity.WARNING)

    def test_prompts_16_9_is_not_warned(self) -> None:
        doc = make_doc("[display]\noutput_res = 1920x1080\n[input]\nprompts = xbox\n")
        self.assertNotIn("rule.prompts_aspect", codes(validate_document(doc)))

    def test_pad_layout_detection_is_info_only(self) -> None:
        doc = make_doc("[input]\npad_layout = nintendo\n")
        issues = validate_document(doc, detected_pad_layout="xbox")
        self.assertIn("rule.pad_layout_detected", codes(issues))
        info = next(item for item in issues if item.code == "rule.pad_layout_detected")
        self.assertEqual(info.severity, Severity.INFO)
        self.assertNotIn("rule.pad_layout_detected", codes(validate_document(doc, detected_pad_layout="nintendo")))
        self.assertNotIn(
            "rule.pad_layout_detected",
            codes(validate_document(make_doc("[input]\npad_layout = auto\n"), detected_pad_layout="xbox")),
        )

    def test_window_size_beyond_display(self) -> None:
        doc = make_doc("[display]\nwindow_size = 2560x1440\n")
        issues = validate_document(doc, display_size=(1920, 1080))
        self.assertIn("rule.window_size_display", codes(issues))
        self.assertNotIn(
            "rule.window_size_display",
            codes(validate_document(make_doc("[display]\nwindow_size = 1280x720\n"), display_size=(1920, 1080))),
        )
        self.assertNotIn("rule.window_size_display", codes(validate_document(doc)))

    def test_upscaler_sharpness_info(self) -> None:
        doc = make_doc("[display]\nupscaler = fsr\nsharpness = 0\n")
        issues = validate_document(doc)
        self.assertIn("rule.upscaler_sharpness", codes(issues))
        self.assertEqual(
            next(item for item in issues if item.code == "rule.upscaler_sharpness").severity,
            Severity.INFO,
        )
        self.assertNotIn(
            "rule.upscaler_sharpness",
            codes(validate_document(make_doc("[display]\nupscaler = bilinear\nsharpness = 0\n"))),
        )

    def test_duplicate_keys(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = 60\nfps_limit = 120\n")
        issues = validate_document(doc)
        duplicates = [item for item in issues if item.code == "rule.duplicate_key"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].severity, Severity.WARNING)
        self.assertEqual(duplicates[0].keys, ("fps_limit",))
        self.assertIn("2 次", duplicates[0].message)


class DocumentLevelTest(unittest.TestCase):
    def test_valid_document_has_no_errors(self) -> None:
        doc = make_doc(
            "# 手写合成样本\n"
            "[frame rate]\nfps_limit = 60\nrealtime = 1\n"
            "[display]\nwindow_size = 1920x1080\noutput_res = 1920x1080\nupscaler = fsr\nsharpness = 80\n"
            "[input]\nprompts = nintendo\nmouse_mode = direct\nmouse_sens = 1\n"
            "[audio]\nvolume = 100\n"
        )
        self.assertEqual(errors(validate_document(doc)), [])

    def test_unknown_keys_are_ignored(self) -> None:
        doc = make_doc("[display]\nunknown_future_key = whatever\n")
        self.assertEqual(validate_document(doc), [])

    def test_binding_pattern_keys_are_validated(self) -> None:
        doc = make_doc("[input]\nbind_A = pad:east, key:E\nbind_B = broken\n")
        issues = errors(validate_document(doc))
        self.assertEqual(codes(issues), ["value.binding"])
        self.assertEqual(issues[0].keys, ("bind_b",))

    def test_version_restricted_keys(self) -> None:
        doc = make_doc("[display]\nfov = 110\n[input]\nmenu_cursor = 1\n")
        old_version = validate_document(doc, version="1.2.1")
        self.assertEqual(codes(old_version).count("rule.version_unsupported"), 2)
        self.assertEqual(validate_document(doc, version="1.4.3"), [])
        self.assertEqual(validate_document(doc), [])

    def test_requires_document(self) -> None:
        with self.assertRaises(TypeError):
            validate_document("not a document")  # type: ignore[arg-type]


class HelperTest(unittest.TestCase):
    def test_effective_value(self) -> None:
        doc = make_doc("[frame rate]\nfps_limit = 120\n")
        self.assertEqual(effective_value(doc, "fps_limit"), "120")
        self.assertEqual(effective_value(doc, "realtime"), "1")
        self.assertIsNone(effective_value(doc, "unknown_future_key"))

    def test_parse_resolution(self) -> None:
        self.assertEqual(parse_resolution("1920x1080"), (1920, 1080))
        self.assertEqual(parse_resolution(" 1280X720 "), (1280, 720))
        self.assertIsNone(parse_resolution("1920*1080"))
        self.assertIsNone(parse_resolution(""))

    def test_is_16_9(self) -> None:
        self.assertTrue(is_16_9(1920, 1080))
        self.assertTrue(is_16_9(2560, 1440))
        self.assertTrue(is_16_9(1280, 720))
        self.assertFalse(is_16_9(3440, 1440))
        self.assertFalse(is_16_9(1280, 800))
        self.assertFalse(is_16_9(0, 0))


if __name__ == "__main__":
    unittest.main()

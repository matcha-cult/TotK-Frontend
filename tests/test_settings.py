"""设置注册表测试（M1-T3）：与 ``docs/settings.md`` 键表逐项核对。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import re
import unittest
from dataclasses import dataclass
from pathlib import Path

from totk_frontend.settings import (
    EFFECT_LABELS,
    SECTION_LABELS,
    SECTION_ORDER,
    SETTINGS,
    Effect,
    Priority,
    ValueType,
    all_settings,
    get_setting,
    is_pattern_key,
    is_registered,
    settings_in_section,
)
from totk_frontend.validate import Severity, validate_value

DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "settings.md"
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

#: 文档第 7、9 节提到的键：不在键表中逐行登记，但注册表必须包含（M2 预设/诊断会用到）。
EXTRA_DOCUMENTED_KEYS = {"free_cores", "replay_async"}


@dataclass(frozen=True)
class DocRow:
    section: str
    keys: tuple[str, ...]
    defaults: tuple[str, ...]
    ranges: tuple[str, ...]
    description: str
    effect_text: str
    priority_text: str


def split_cells(line: str) -> list[str]:
    sentinel = "\x00"
    protected = line.replace(r"\|", sentinel)
    parts = protected.split("|")
    if parts[0].strip() != "" or parts[-1].strip() != "":
        raise AssertionError(f"表格行列格式异常：{line!r}")
    return [part.strip().replace(sentinel, "|") for part in parts[1:-1]]


def strip_code(text: str) -> str:
    return text.strip().strip("`").strip()


def unwrap_code(text: str) -> str:
    """只去掉整体的代码标记（`` `x` `` → ``x``），保留“同 `x`”这类混合写法。"""
    stripped = text.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def split_alternatives(cell: str) -> list[str]:
    """按“空格 / 空格”拆分组合单元格；枚举里的 ``/`` 不带空格，不会被拆开。"""
    return [part.strip() for part in re.split(r"\s+/\s+", cell.strip())]


def expand(cell: str | None, count: int) -> tuple[str, ...]:
    if cell is None:
        return tuple("" for _ in range(count))
    tokens = split_alternatives(cell) if cell.strip() else []
    if len(tokens) == count:
        return tuple(tokens)
    if len(tokens) == 1:
        return tuple(tokens * count)
    raise AssertionError(f"无法把 {cell!r} 拆成 {count} 份")


def parse_effect(text: str) -> Effect:
    if text.startswith("即时/重启"):
        return Effect.VERSION_DEPENDENT
    if text.startswith("即时"):
        return Effect.IMMEDIATE
    if text.startswith("重启"):
        return Effect.RESTART
    if text.startswith("影片开始时"):
        return Effect.MOVIE_START
    if text.startswith("焦点切换时"):
        return Effect.FOCUS_CHANGE
    raise AssertionError(f"未知生效时机：{text!r}")


def parse_priority(text: str) -> Priority:
    match = re.search(r"P([012])", text)
    if match is None:
        raise AssertionError(f"未知暴露级别：{text!r}")
    return Priority(f"P{match.group(1)}")


def parse_key_tables() -> list[DocRow]:
    text = DOC_PATH.read_text(encoding="utf-8")
    rows: list[DocRow] = []
    section: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^## (\d+)\. `\[([^\]]+)\]`", line)
        if heading is not None:
            number = int(heading.group(1))
            section = heading.group(2) if number in (2, 3, 4, 5, 6) else None
            continue
        if section is None:
            continue
        if not line.startswith("| "):
            continue
        if re.match(r"^\|\s*-+", line) or line.startswith("| 键 |"):
            continue
        cells = split_cells(line)
        if len(cells) == 6:
            key_cell, default_cell, range_cell, desc_cell, effect_cell, level_cell = cells
            range_cell_value: str | None = range_cell
        elif len(cells) == 5:
            key_cell, default_cell, desc_cell, effect_cell, level_cell = cells
            range_cell_value = None
        else:
            raise AssertionError(f"未知表格列数 {len(cells)}：{line!r}")
        keys = tuple(strip_code(part) for part in split_alternatives(key_cell))
        defaults = tuple(unwrap_code(part) for part in expand(default_cell, len(keys)))
        if range_cell_value is None:
            ranges: tuple[str, ...] = tuple("" for _ in keys)
        else:
            ranges = tuple(part.strip() for part in expand(range_cell_value, len(keys)))
        rows.append(
            DocRow(
                section=section,
                keys=keys,
                defaults=defaults,
                ranges=ranges,
                description=desc_cell.replace("**", ""),
                effect_text=effect_cell,
                priority_text=level_cell,
            )
        )
    return rows


DOC_ROWS = parse_key_tables()


class DocTableParityTest(unittest.TestCase):
    def test_document_was_parsed(self) -> None:
        self.assertGreaterEqual(len(DOC_ROWS), 55)
        documented_keys = {key for row in DOC_ROWS for key in row.keys if not key.startswith("bind_<")}
        self.assertIn("fps_limit", documented_keys)
        self.assertIn("volume", documented_keys)
        self.assertIn("menu_lang", documented_keys)

    def test_every_documented_key_matches_registry(self) -> None:
        documented: set[str] = set()
        for row in DOC_ROWS:
            effect = parse_effect(row.effect_text)
            priority = parse_priority(row.priority_text)
            for index, doc_key in enumerate(row.keys):
                if doc_key.startswith("bind_<"):
                    setting = get_setting("bind_A")
                    self.assertIsNotNone(setting, "注册表缺少 bind_* 模式项")
                    assert setting is not None
                    self.assertTrue(setting.is_pattern)
                    self.assertEqual(setting.doc_key, doc_key)
                    self.assertEqual(setting.section, row.section)
                    self.assertEqual(setting.effect, effect)
                    self.assertEqual(setting.priority, priority)
                    self.assertEqual(setting.range_doc, row.ranges[index])
                    self.assertEqual(setting.description, row.description)
                    self.assertFalse(setting.writable)
                    documented.add(setting.key)
                    continue

                setting = get_setting(doc_key)
                self.assertIsNotNone(setting, f"注册表缺少文档键 {doc_key}")
                assert setting is not None
                self.assertEqual(setting.section, row.section, doc_key)
                self.assertEqual(setting.effect, effect, doc_key)
                self.assertEqual(setting.priority, priority, doc_key)
                self.assertEqual(setting.description, row.description, doc_key)
                self.assertEqual(setting.range_doc, row.ranges[index], doc_key)

                expected_default = row.defaults[index]
                if expected_default.startswith("同 "):
                    referenced = get_setting(expected_default[2:].strip().strip("`"))
                    self.assertIsNotNone(referenced, expected_default)
                    assert referenced is not None
                    self.assertEqual(setting.default, referenced.default, doc_key)
                elif expected_default == "空":
                    self.assertEqual(setting.default, "", doc_key)
                elif expected_default in ("见键表", "系统语言"):
                    self.assertIsNone(setting.default, doc_key)
                else:
                    self.assertEqual(setting.default, expected_default, doc_key)
                documented.add(setting.key)
        self.assertEqual(set({setting.key for setting in SETTINGS}) - documented, EXTRA_DOCUMENTED_KEYS)

    def test_referenced_extra_keys_are_registered(self) -> None:
        for key in EXTRA_DOCUMENTED_KEYS:
            setting = get_setting(key)
            self.assertIsNotNone(setting, key)
            assert setting is not None
            self.assertEqual(setting.section, "performance")
            self.assertEqual(setting.effect, Effect.RESTART)
            self.assertEqual(setting.priority, Priority.P2)
            self.assertIsNotNone(setting.default)

    def test_no_duplicate_keys_or_sections(self) -> None:
        keys = [setting.key.lower() for setting in SETTINGS]
        self.assertEqual(len(keys), len(set(keys)), "注册表存在重复键")
        self.assertEqual(len(SETTINGS), len(all_settings()))
        self.assertEqual(SECTION_ORDER, tuple(dict.fromkeys(setting.section for setting in SETTINGS)))
        self.assertEqual(set(SECTION_LABELS), set(SECTION_ORDER))


class RegistryMetadataTest(unittest.TestCase):
    def test_every_setting_has_chinese_label(self) -> None:
        for setting in SETTINGS:
            self.assertTrue(setting.label.strip(), setting.key)
            self.assertRegex(setting.label, CJK_RE, setting.key)
            self.assertTrue(setting.description.strip(), setting.key)

    def test_every_effect_has_label(self) -> None:
        for effect in Effect:
            self.assertIn(effect, EFFECT_LABELS)
            self.assertTrue(EFFECT_LABELS[effect])

    def test_writable_flags(self) -> None:
        for setting in SETTINGS:
            if setting.is_pattern:
                self.assertFalse(setting.writable, setting.key)
            else:
                self.assertTrue(setting.writable, setting.key)

    def test_structured_ranges_match_documented_text(self) -> None:
        def fmt(value: int | float) -> str:
            return f"{value:g}" if isinstance(value, float) else str(value)

        for setting in SETTINGS:
            if setting.value_type in (ValueType.INTEGER, ValueType.NUMBER):
                if setting.min_value is not None and setting.max_value is not None:
                    expected = f"{fmt(setting.min_value)}–{fmt(setting.max_value)}"
                    self.assertIn(expected, setting.range_doc, setting.key)
            elif setting.value_type is ValueType.RESOLUTION:
                assert setting.width_range is not None and setting.height_range is not None
                expected = (
                    f"{setting.width_range[0]}x{setting.height_range[0]}"
                    f"–{setting.width_range[1]}x{setting.height_range[1]}"
                )
                self.assertIn(expected, setting.range_doc, setting.key)

    def test_value_types_are_consistent(self) -> None:
        for setting in SETTINGS:
            if setting.value_type in (ValueType.INTEGER, ValueType.NUMBER):
                if setting.min_value is not None and setting.max_value is not None:
                    self.assertLessEqual(setting.min_value, setting.max_value, setting.key)
            if setting.value_type is ValueType.ENUM:
                self.assertTrue(setting.choices, setting.key)
            if setting.value_type is ValueType.RESOLUTION:
                self.assertIsNotNone(setting.width_range, setting.key)
                self.assertIsNotNone(setting.height_range, setting.key)

    def test_defaults_pass_single_key_validation(self) -> None:
        for setting in SETTINGS:
            if setting.default is None:
                continue
            issues = validate_value(setting, setting.default)
            errors = [issue for issue in issues if issue.severity is Severity.ERROR]
            self.assertEqual(errors, [], f"{setting.key} 的默认值 {setting.default!r} 未通过校验")


class LookupTest(unittest.TestCase):
    def test_case_insensitive_lookup(self) -> None:
        self.assertIs(get_setting("FPS_LIMIT"), get_setting("fps_limit"))
        self.assertIsNotNone(get_setting("Volume"))
        self.assertIsNone(get_setting("fps_limit", "display"))
        self.assertIsNotNone(get_setting("fps_limit", "FRAME RATE"))

    def test_unknown_key(self) -> None:
        self.assertIsNone(get_setting("unknown_future_key"))
        self.assertFalse(is_registered("unknown_future_key"))

    def test_settings_in_section(self) -> None:
        keys = [setting.key for setting in settings_in_section("frame rate")]
        self.assertEqual(keys, ["fps_limit", "realtime", "frame_queue", "highfps_fix"])

    def test_pattern_keys(self) -> None:
        for key in ("bind_A", "bind_L", "bind_LSTICK_LEFT", "bind_SHAKE", "BIND_A"):
            self.assertIsNotNone(get_setting(key), key)
            self.assertTrue(is_pattern_key(key), key)
        self.assertIsNone(get_setting("bind_"))
        self.assertIsNone(get_setting("not_bind_A"))

    def test_bind_pattern_covers_documented_names_only(self) -> None:
        from totk_frontend.settings import BIND_KEYS

        for key in BIND_KEYS:
            self.assertIsNotNone(get_setting(key), key)
        self.assertEqual(len(BIND_KEYS), len(set(BIND_KEYS)))
        # [performance] 的 bind_skip 是优化开关，不是按键绑定：按未知键保留、不参与校验。
        for key in ("bind_skip", "bind_unknown", "bind_A_extra"):
            self.assertIsNone(get_setting(key), key)
            self.assertFalse(is_pattern_key(key), key)

    def test_volume_and_window_boundaries(self) -> None:
        from totk_frontend.validate import Severity, validate_value

        volume = get_setting("volume")
        assert volume is not None
        for value in ("0", "100"):
            self.assertEqual(validate_value(volume, value), [], value)
        for value in ("-1", "101"):
            issues = validate_value(volume, value)
            self.assertEqual([issue.severity for issue in issues], [Severity.ERROR], value)
        window = get_setting("window_size")
        assert window is not None
        self.assertEqual(validate_value(window, "640x360"), [])
        self.assertEqual(validate_value(window, "7680x4320"), [])
        self.assertNotEqual(validate_value(window, "639x360"), [])
        self.assertNotEqual(validate_value(window, "7681x4320"), [])

    def test_sections_order(self) -> None:
        self.assertEqual(
            [setting.section for setting in settings_in_section("display")],
            [setting.section for setting in SETTINGS if setting.section == "display"],
        )



class SettingHelpersTest(unittest.TestCase):
    def test_effect_label_and_label_with_key(self) -> None:
        from totk_frontend.settings import EFFECT_LABELS

        setting = get_setting("realtime")
        assert setting is not None
        self.assertEqual(setting.effect_label, EFFECT_LABELS[setting.effect])
        self.assertEqual(setting.label_with_key, "游戏速度跟随真实时钟（realtime）")

    def test_supports_version(self) -> None:
        fov = get_setting("fov")
        assert fov is not None
        self.assertTrue(fov.supports_version("1.4.3"))
        self.assertFalse(fov.supports_version("1.1.0"))
        self.assertTrue(fov.supports_version(None))
        realtime = get_setting("realtime")
        assert realtime is not None
        self.assertTrue(realtime.supports_version("1.1.0"))

    def test_get_setting_requires_string(self) -> None:
        with self.assertRaises(TypeError):
            get_setting(123)  # type: ignore[arg-type]

if __name__ == "__main__":
    unittest.main()

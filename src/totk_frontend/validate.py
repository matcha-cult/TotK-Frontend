"""设置校验：单键规则 + ``docs/settings.md`` 第 8 节的跨字段规则。

校验只读：不修改 ``totk.ini``，也不自动修正；返回带严重级别的 :class:`Issue` 列表，
由 CLI（M3）/GUI（M4）决定如何展示与处理。严重级别与 ``settings.md`` 一致：

- ``ERROR``（错误）：必须修正；
- ``WARNING``（警告）：可能有问题；
- ``INFO``（提示）：仅说明，不要求修改。

跨字段规则中依赖本机环境的两条（手柄型号、显示器尺寸）需要调用方传入检测结果；
未传入时跳过，由 M2 的 ``doctor`` 提供。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from .ini import IniDocument
from .settings import SETTINGS, Setting, ValueType, get_setting, is_pattern_key

__all__ = [
    "Severity",
    "SEVERITY_LABELS",
    "Issue",
    "validate_value",
    "validate_document",
    "is_16_9",
    "effective_value",
]


class Severity(Enum):
    """问题严重级别。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


SEVERITY_LABELS = {
    Severity.ERROR: "错误",
    Severity.WARNING: "警告",
    Severity.INFO: "提示",
}


@dataclass(frozen=True)
class Issue:
    """一条校验结果。"""

    severity: Severity
    code: str
    message: str
    keys: tuple[str, ...] = ()
    suggestion: str = ""

    def __str__(self) -> str:
        return f"[{SEVERITY_LABELS[self.severity]}] {self.message}"


_INTEGER_RE = re.compile(r"[+-]?\d+")
_NUMBER_RE = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
_RESOLUTION_RE = re.compile(r"^\s*(\d{1,6})\s*[xX]\s*(\d{1,6})\s*$")
_KEYNAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _error(code: str, setting: Setting, key: str, message: str, suggestion: str = "") -> Issue:
    return Issue(
        severity=Severity.ERROR,
        code=code,
        message=message,
        keys=(key,),
        suggestion=suggestion,
    )


def _suggestion_for(setting: Setting) -> str:
    if setting.choices:
        return "允许值：" + "、".join(setting.choices)
    if setting.range_doc:
        return f"参考取值：{setting.range_doc}"
    return ""


def _check_choice(setting: Setting, key: str, text: str, choices: tuple[str, ...]) -> Issue | None:
    normalized_choices = {choice.lower() for choice in choices}
    if text.lower() in normalized_choices:
        return None
    return _error(
        "value.choice",
        setting,
        key,
        f"{setting.label_with_key} 的取值“{text}”不在允许值内。",
        _suggestion_for(setting),
    )


def _check_numeric_range(setting: Setting, key: str, value: float, text: str) -> Issue | None:
    if setting.min_value is not None and value < setting.min_value:
        return _error(
            "value.range",
            setting,
            key,
            f"{setting.label_with_key} 的值 {text} 小于允许的最小值 {setting.min_value:g}。",
            _suggestion_for(setting),
        )
    if setting.max_value is not None and value > setting.max_value:
        return _error(
            "value.range",
            setting,
            key,
            f"{setting.label_with_key} 的值 {text} 大于允许的最大值 {setting.max_value:g}。",
            _suggestion_for(setting),
        )
    return None


def _validate_binding(setting: Setting, key: str, text: str) -> Issue | None:
    if text.lower() == "none":
        return None
    tokens = [token.strip() for token in text.split(",") if token.strip()]
    if not tokens:
        return _error(
            "value.binding",
            setting,
            key,
            f"{setting.label_with_key} 的值为空；应为 pad:<名称> 或 key:<名称> 的组合，或 none。",
            _suggestion_for(setting),
        )
    for token in tokens:
        part, separator, name = token.partition(":")
        if (
            not separator
            or part.strip().lower() not in ("pad", "key")
            or not name.strip()
        ):
            return _error(
                "value.binding",
                setting,
                key,
                f"{setting.label_with_key} 的值“{token}”格式无效：应为 pad:<名称> 或 key:<名称>。",
                _suggestion_for(setting),
            )
    return None


def validate_value(setting: Setting, value: str, *, key: str | None = None) -> list[Issue]:
    """校验单个键的值；返回问题列表（空列表表示通过）。"""
    if not isinstance(value, str):
        raise TypeError("value 必须是字符串")
    used_key = key or setting.key
    text = value.strip()
    if text == "":
        if setting.allow_empty:
            return []
        return [
            _error(
                "value.empty",
                setting,
                used_key,
                f"{setting.label_with_key} 的值不能为空。",
                _suggestion_for(setting),
            )
        ]

    value_type = setting.value_type

    if value_type is ValueType.BOOL:
        if text not in ("0", "1"):
            return [
                _error(
                    "value.type",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 只能是 0 或 1，实际为“{text}”。",
                    "0 = 关闭，1 = 开启。",
                )
            ]
        return []

    if value_type is ValueType.INTEGER:
        lowered = text.lower()
        if lowered in {choice.lower() for choice in setting.extra_choices}:
            return []
        if _INTEGER_RE.fullmatch(text) is None:
            return [
                _error(
                    "value.type",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 应为整数，实际为“{text}”。",
                    _suggestion_for(setting),
                )
            ]
        issue = _check_numeric_range(setting, used_key, float(int(text)), text)
        return [issue] if issue is not None else []

    if value_type is ValueType.NUMBER:
        lowered = text.lower()
        if lowered in {choice.lower() for choice in setting.extra_choices}:
            return []
        if _NUMBER_RE.fullmatch(text) is None:
            return [
                _error(
                    "value.type",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 应为数字，实际为“{text}”。",
                    _suggestion_for(setting),
                )
            ]
        number = float(text)
        if not math.isfinite(number):
            return [
                _error(
                    "value.type",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 应为有限数字，实际为“{text}”。",
                    _suggestion_for(setting),
                )
            ]
        issue = _check_numeric_range(setting, used_key, number, text)
        return [issue] if issue is not None else []

    if value_type is ValueType.ENUM:
        issue = _check_choice(setting, used_key, text, setting.choices)
        return [issue] if issue is not None else []

    if value_type is ValueType.RESOLUTION:
        match = _RESOLUTION_RE.match(text)
        if match is None:
            return [
                _error(
                    "value.resolution",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 应为“宽x高”形式，实际为“{text}”。",
                    _suggestion_for(setting),
                )
            ]
        width, height = int(match.group(1)), int(match.group(2))
        if setting.width_range is not None and not (
            setting.width_range[0] <= width <= setting.width_range[1]
        ):
            return [
                _error(
                    "value.range",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 的宽度 {width} 超出允许范围。",
                    _suggestion_for(setting),
                )
            ]
        if setting.height_range is not None and not (
            setting.height_range[0] <= height <= setting.height_range[1]
        ):
            return [
                _error(
                    "value.range",
                    setting,
                    used_key,
                    f"{setting.label_with_key} 的高度 {height} 超出允许范围。",
                    _suggestion_for(setting),
                )
            ]
        return []

    if value_type is ValueType.KEYNAME:
        if text.lower() == "none" or _KEYNAME_RE.fullmatch(text.lower()):
            return []
        return [
            _error(
                "value.keyname",
                setting,
                used_key,
                f"{setting.label_with_key} 的值“{text}”不是合法键名。",
                "使用小写字母、数字与下划线，或 none 关闭。",
            )
        ]

    if value_type is ValueType.BINDING:
        issue = _validate_binding(setting, used_key, text)
        return [issue] if issue is not None else []

    if value_type is ValueType.TEXT:
        return []

    raise AssertionError(f"未处理的类型：{value_type!r}")  # pragma: no cover


def effective_value(document: IniDocument, key: str, *, section: str | None = None) -> str | None:
    """返回生效值：文件中的最后一个激活行，否则返回注册表默认值。"""
    setting = get_setting(key)
    current = document.get(key, section)
    if current is not None:
        return current
    return setting.default if setting is not None else None


def _effective_number(document: IniDocument, key: str) -> float | None:
    value = effective_value(document, key)
    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def parse_resolution(text: str) -> tuple[int, int] | None:
    """解析 ``宽x高``；失败返回 ``None``。"""
    if not isinstance(text, str):
        return None
    match = _RESOLUTION_RE.match(text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def is_16_9(width: int, height: int) -> bool:
    """严格的 16:9 判断（``width * 9 == height * 16``）。"""
    if width <= 0 or height <= 0:
        return False
    return width * 9 == height * 16


def _collect_single_key_issues(document: IniDocument) -> list[Issue]:
    issues: list[Issue] = []
    for setting in SETTINGS:
        if setting.is_pattern:
            continue
        value = document.get(setting.key)
        if value is not None:
            issues.extend(validate_value(setting, value))
    for key in document.keys():
        if not is_pattern_key(key):
            continue
        setting = get_setting(key)
        value = document.get(key)
        if setting is not None and value is not None:
            issues.extend(validate_value(setting, value, key=key))
    return issues


def _collect_cross_field_issues(
    document: IniDocument,
    *,
    display_size: tuple[int, int] | None,
    detected_pad_layout: str | None,
    mouse_camera_expected: bool | None,
) -> list[Issue]:
    issues: list[Issue] = []

    # 1) fps_limit > 60 时必须 realtime = 1
    fps = _effective_number(document, "fps_limit")
    realtime = effective_value(document, "realtime")
    if fps is not None and fps > 60 and realtime is not None and realtime.strip() == "0":
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="rule.fps_limit_realtime",
                message=(
                    f"帧率上限为 {fps:g}（高于 60），但 realtime = 0；"
                    "高帧率必须让游戏速度跟随真实时钟。"
                ),
                keys=("fps_limit", "realtime"),
                suggestion="把 realtime 改为 1，或把 fps_limit 降到 60 或更低。",
            )
        )

    # 2) free_cores = 1 会启动即崩
    free_cores = effective_value(document, "free_cores")
    if free_cores is not None and free_cores.strip() == "1":
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="rule.free_cores",
                message="free_cores = 1 会让游戏启动即崩（已知问题）。",
                keys=("free_cores",),
                suggestion="把 free_cores 改回 0。",
            )
        )

    # 3) mouse_sens = 0 却期望鼠标相机
    mouse_sens = _effective_number(document, "mouse_sens")
    if mouse_sens is not None and mouse_sens == 0:
        wants_mouse = mouse_camera_expected
        if wants_mouse is None:
            mode = (effective_value(document, "mouse_mode") or "direct").strip().lower()
            wants_mouse = mode != "stick"
        if wants_mouse:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="rule.mouse_sens_off",
                    message="mouse_sens = 0 会关闭鼠标相机与指针捕获。",
                    keys=("mouse_sens", "mouse_mode"),
                    suggestion="需要鼠标相机时，把 mouse_sens 调到 1 以上。",
                )
            )

    # 4) prompts 为 xbox/pc 且 output_res 非 16:9
    prompts = (effective_value(document, "prompts") or "").strip().lower()
    output_res = effective_value(document, "output_res")
    if prompts in ("xbox", "pc") and output_res is not None:
        parsed = parse_resolution(output_res)
        if parsed is not None and not is_16_9(*parsed):
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="rule.prompts_aspect",
                    message=(
                        f"prompts = {prompts} 的提示图仅按 16:9 准备，"
                        f"当前 output_res = {output_res} 非 16:9，提示样式会回退游戏原生。"
                    ),
                    keys=("prompts", "output_res"),
                    suggestion="把 output_res 设为 16:9，或改用 prompts = nintendo。",
                )
            )

    # 5) pad_layout 与本机手柄不符（需要外部检测结果，仅提示）
    pad_layout = (effective_value(document, "pad_layout") or "").strip().lower()
    if (
        detected_pad_layout is not None
        and pad_layout
        and pad_layout != "auto"
        and pad_layout != detected_pad_layout.strip().lower()
    ):
        issues.append(
            Issue(
                severity=Severity.INFO,
                code="rule.pad_layout_detected",
                message=(
                    f"本机手柄更接近 {detected_pad_layout}，但 pad_layout = {pad_layout}；"
                    "面键映射可能与手柄标签不一致。"
                ),
                keys=("pad_layout",),
                suggestion="确认手柄面键标签后再调整 pad_layout；此处只提示，不自动修改。",
            )
        )

    # 6) window_size 超出显示器范围（需要外部检测结果）
    window_size = effective_value(document, "window_size")
    if display_size is not None and window_size is not None:
        parsed = parse_resolution(window_size)
        if parsed is not None and (parsed[0] > display_size[0] or parsed[1] > display_size[1]):
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="rule.window_size_display",
                    message=(
                        f"窗口尺寸 {window_size} 超出显示器范围 "
                        f"{display_size[0]}x{display_size[1]}，窗口可能无法完整显示。"
                    ),
                    keys=("window_size",),
                    suggestion="把 window_size 调小到显示器范围内，或改用 fullscreen。",
                )
            )

    # 7) upscaler = fsr 且 sharpness = 0
    upscaler = (effective_value(document, "upscaler") or "").strip().lower()
    sharpness = _effective_number(document, "sharpness")
    if upscaler == "fsr" and sharpness is not None and sharpness == 0:
        issues.append(
            Issue(
                severity=Severity.INFO,
                code="rule.upscaler_sharpness",
                message="upscaler = fsr 且 sharpness = 0，画面可能偏软。",
                keys=("upscaler", "sharpness"),
                suggestion="把 sharpness 提高到 50–80，或改用 upscaler = bilinear。",
            )
        )

    # 8) 同一键出现多次
    for duplicate in document.duplicates():
        location = f"[{duplicate.section}]" if duplicate.section else "节外"
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="rule.duplicate_key",
                message=(
                    f"{location} 中的键 {duplicate.key} 出现 {duplicate.count} 次；"
                    "只有最后一个生效，建议清理。"
                ),
                keys=(duplicate.key,),
                suggestion="删除或注释掉多余的重复行，只保留一行。",
            )
        )

    return issues


def _collect_version_issues(document: IniDocument, version: str) -> list[Issue]:
    issues: list[Issue] = []
    for setting in SETTINGS:
        if setting.is_pattern or not setting.versions:
            continue
        if document.get(setting.key) is None:
            continue
        if setting.supports_version(version):
            continue
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="rule.version_unsupported",
                message=(
                    f"{setting.label_with_key} 仅在 TotK Recomp "
                    f"{'、'.join(setting.versions)} 中可用，当前版本 {version} 可能忽略它。"
                ),
                keys=(setting.key,),
                suggestion="确认目标版本支持该键后再启用；升级后重新检查。",
            )
        )
    return issues


def validate_document(
    document: IniDocument,
    *,
    version: str | None = None,
    display_size: tuple[int, int] | None = None,
    detected_pad_layout: str | None = None,
    mouse_camera_expected: bool | None = None,
) -> list[Issue]:
    """校验整份 ``totk.ini``。

    参数：
        version: TotK Recomp 版本（如 ``"1.4.3"``）；提供时检查版本限制。
        display_size: 显示器分辨率 ``(宽, 高)``；提供时检查窗口尺寸。
        detected_pad_layout: 检测到的本机手柄布局（``nintendo``/``xbox``）；提供时给出提示。
        mouse_camera_expected: 是否期望鼠标相机；``None`` 时按 ``mouse_mode`` 推断。
    """
    if not isinstance(document, IniDocument):
        raise TypeError("document 必须是 IniDocument")
    issues = _collect_single_key_issues(document)
    issues.extend(
        _collect_cross_field_issues(
            document,
            display_size=display_size,
            detected_pad_layout=detected_pad_layout,
            mouse_camera_expected=mouse_camera_expected,
        )
    )
    if version is not None:
        issues.extend(_collect_version_issues(document, version))
    return issues

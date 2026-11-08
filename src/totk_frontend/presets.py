"""M2 预设：把一组设置调到目标风格。

约束见 ``docs/settings.md`` 第 9 节：

- 预设只使用注册表中存在且已声明范围的键；
- 每个目标值都必须通过 ``validate.validate_value`` 的单键校验；
- 禁止写入已知危险值（``free_cores = 1``、``mouse_sens = 0``）；
- 应用预设只写差异集，支持预览（dry-run）与回滚。

本模块只修改内存中的 :class:`~totk_frontend.ini.IniDocument`；落盘由
:func:`~totk_frontend.ini.write_ini` 完成（备份、原子替换、回读校验与回滚）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .settings import get_setting
from .validate import Issue, Severity, validate_value

__all__ = [
    "FORBIDDEN_VALUES",
    "PresetEntry",
    "Preset",
    "PRESETS",
    "get_preset",
    "preset_names",
    "validate_preset",
    "validate_presets",
]

#: 任何预设都不得写入的键值组合（已知会导致崩溃或关闭关键功能）。
FORBIDDEN_VALUES: tuple[tuple[str, str], ...] = (
    ("free_cores", "1"),
    ("mouse_sens", "0"),
)


@dataclass(frozen=True)
class PresetEntry:
    """预设中的一项：键 + 目标值 + 可选的版本限制。"""

    key: str
    value: str
    versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Preset:
    """一个预设。"""

    name: str
    label: str
    description: str
    entries: tuple[PresetEntry, ...]


PRESETS: tuple[Preset, ...] = (
    Preset(
        name="savage-wind",
        label="Savage Wind 风格",
        description="键鼠优先：PC 按键提示、鼠标相机直连、1.4.3 的游戏菜单鼠标。",
        entries=(
            PresetEntry("prompts", "pc"),
            PresetEntry("mouse_mode", "direct"),
            PresetEntry("menu_cursor", "1", versions=("1.4.3",)),
            PresetEntry("fps_limit", "60"),
            PresetEntry("realtime", "1"),
            PresetEntry("sharpness", "80"),
        ),
    ),
    Preset(
        name="controller",
        label="手柄优先",
        description="手柄玩家：任天堂提示、自动面键布局、体感与震动开启。",
        entries=(
            PresetEntry("prompts", "nintendo"),
            PresetEntry("pad_layout", "auto"),
            PresetEntry("motion", "1"),
            PresetEntry("rumble", "1"),
        ),
    ),
    Preset(
        name="performance",
        label="低配/流畅",
        description="降低画面开销、异步重放提交，优先稳定帧率。",
        entries=(
            PresetEntry("fps_limit", "60"),
            PresetEntry("aniso", "game"),
            PresetEntry("shadow_scale", "1"),
            PresetEntry("render_scale", "game"),
            PresetEntry("replay_async", "1"),
        ),
    ),
    Preset(
        name="quality",
        label="画质优先",
        description="提高渲染分辨率、各向异性过滤与阴影质量。",
        entries=(
            PresetEntry("render_scale", "100"),
            PresetEntry("aniso", "16"),
            PresetEntry("shadow_scale", "2"),
            PresetEntry("pcss", "50"),
            PresetEntry("contact_shadows", "50"),
        ),
    ),
)

_BY_NAME = {preset.name.lower(): preset for preset in PRESETS}


def get_preset(name: str) -> Preset | None:
    """按名称（大小写不敏感）查找预设；未知名称返回 ``None``。"""
    if not isinstance(name, str):
        raise TypeError("name 必须是字符串")
    return _BY_NAME.get(name.strip().lower())


def preset_names() -> tuple[str, ...]:
    """按定义顺序返回全部预设名称。"""
    return tuple(preset.name for preset in PRESETS)


def validate_preset(preset: Preset) -> list[Issue]:
    """检查单个预设的定义是否满足第 9 节约束；返回问题列表（空表示通过）。"""
    issues: list[Issue] = []
    seen: set[str] = set()
    for entry in preset.entries:
        key = entry.key.strip().lower()
        if key in seen:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="preset.duplicate_key",
                    message=f"预设 {preset.name} 中重复定义了键 {key}。",
                    keys=(key,),
                )
            )
        seen.add(key)
        setting = get_setting(key)
        if setting is None:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="preset.unknown_key",
                    message=f"预设 {preset.name} 使用了未注册的键 {key}。",
                    keys=(key,),
                    suggestion="先在 docs/settings.md 与 settings.py 中登记该键。",
                )
            )
            continue
        for issue in validate_value(setting, entry.value, key=key):
            issues.append(issue)
        if (key, entry.value.strip().lower()) in FORBIDDEN_VALUES:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="preset.forbidden_value",
                    message=f"预设 {preset.name} 试图写入危险值 {key} = {entry.value}。",
                    keys=(key,),
                    suggestion="删除该项；该值会导致崩溃或关闭关键功能。",
                )
            )
    return issues


def validate_presets() -> list[Issue]:
    """检查全部预设定义；返回问题列表（空表示通过）。"""
    issues: list[Issue] = []
    for preset in PRESETS:
        issues.extend(validate_preset(preset))
    return issues

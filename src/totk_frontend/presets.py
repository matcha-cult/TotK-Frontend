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

from .ini import IniDocument
from .settings import get_setting
from .validate import Issue, Severity, validate_document, validate_value

__all__ = [
    "FORBIDDEN_VALUES",
    "PresetEntry",
    "Preset",
    "PRESETS",
    "get_preset",
    "preset_names",
    "validate_preset",
    "validate_presets",
    "PlannedChange",
    "PresetPlan",
    "plan_preset",
    "apply_preset",
    "revert_plan",
    "format_plan",
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


# ---------------------------------------------------------------------- 应用


@dataclass(frozen=True)
class PlannedChange:
    """预设计划中的一项改动。"""

    key: str
    section: str
    old_value: str | None
    new_value: str


@dataclass(frozen=True)
class PresetPlan:
    """预设的差异计划；``plan_preset`` 的结果即 dry-run 预览。"""

    preset: Preset
    version: str | None
    changes: tuple[PlannedChange, ...]
    unchanged: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]
    warnings: tuple[Issue, ...]

    @property
    def is_empty(self) -> bool:
        return not self.changes


def _resolve_preset(preset: Preset | str) -> Preset:
    if isinstance(preset, Preset):
        return preset
    if isinstance(preset, str):
        resolved = get_preset(preset)
        if resolved is None:
            raise ValueError(f"未知预设：{preset!r}；可用：{'、'.join(preset_names())}")
        return resolved
    raise TypeError("preset 必须是 Preset 或预设名称字符串")


def _setting_section(key: str) -> str:
    setting = get_setting(key)
    if setting is None:  # pragma: no cover - 预设定义已通过校验
        raise ValueError(f"预设使用了未注册的键：{key}")
    return setting.section


def _apply_changes(document: IniDocument, changes: tuple[PlannedChange, ...]) -> None:
    for change in changes:
        if change.old_value is not None:
            # 键本来就在文件中：改最后一个生效行，不强行挪到注册表节。
            document.set(change.key, change.new_value)
        else:
            document.set(change.key, change.new_value, change.section)


def plan_preset(
    document: IniDocument,
    preset: Preset | str,
    *,
    version: str | None = None,
) -> PresetPlan:
    """计算预设与当前文档的差异（dry-run，不修改文档）。

    - 只产生目标值不同的项；已是目标值（含默认值即目标值）的项不计入改动；
    - 带版本限制的项在 ``version`` 不适用时跳过；
    - ``warnings`` 是对“应用后文档”运行 ``validate_document`` 的结果，供预览提示。
    """
    if not isinstance(document, IniDocument):
        raise TypeError("document 必须是 IniDocument")
    target_preset = _resolve_preset(preset)
    if version is not None and not isinstance(version, str):
        raise TypeError("version 必须是字符串或 None")

    changes: list[PlannedChange] = []
    unchanged: list[str] = []
    skipped: list[tuple[str, str]] = []
    for entry in target_preset.entries:
        setting = get_setting(entry.key)
        if setting is None:  # pragma: no cover - 预设定义已通过校验
            raise ValueError(f"预设使用了未注册的键：{entry.key}")
        if entry.versions and version is not None and version not in entry.versions:
            skipped.append(
                (entry.key, f"仅适用于 TotK Recomp {'、'.join(entry.versions)}")
            )
            continue
        target_value = entry.value.strip()
        current = document.get(entry.key)
        if current is not None:
            if current.strip() == target_value:
                unchanged.append(entry.key)
                continue
        elif setting.default is not None and setting.default.strip() == target_value:
            unchanged.append(entry.key)
            continue
        changes.append(
            PlannedChange(
                key=entry.key,
                section=setting.section,
                old_value=current,
                new_value=target_value,
            )
        )

    simulated = IniDocument.from_bytes(document.to_bytes())
    _apply_changes(simulated, tuple(changes))
    warnings = tuple(validate_document(simulated, version=version))
    return PresetPlan(
        preset=target_preset,
        version=version,
        changes=tuple(changes),
        unchanged=tuple(unchanged),
        skipped=tuple(skipped),
        warnings=warnings,
    )


def apply_preset(
    document: IniDocument,
    preset: Preset | str,
    *,
    version: str | None = None,
) -> PresetPlan:
    """把预设应用到文档（内存中），返回可回滚的计划。

    落盘请使用 :func:`totk_frontend.ini.write_ini`，它会备份、原子替换并回读校验。
    """
    plan = plan_preset(document, preset, version=version)
    _apply_changes(document, plan.changes)
    return plan


def revert_plan(document: IniDocument, plan: PresetPlan) -> int:
    """按计划回滚预设：恢复原有值，原本没有激活行的键用 ``unset`` 移除；返回回滚项数。

    说明：应用预设时新建的空节头不会删除（与 design 第 12 节 I5 一致）；预设未涉及的键不受影响。
    """
    if not isinstance(document, IniDocument):
        raise TypeError("document 必须是 IniDocument")
    if not isinstance(plan, PresetPlan):
        raise TypeError("plan 必须是 PresetPlan")
    for change in plan.changes:
        if change.old_value is None:
            document.unset(change.key)
        else:
            document.set(change.key, change.old_value)
    return len(plan.changes)


def format_plan(plan: PresetPlan) -> str:
    """把计划格式化为可读文本（供 CLI --dry-run / GUI 预览使用）。"""
    if not isinstance(plan, PresetPlan):
        raise TypeError("plan 必须是 PresetPlan")
    lines = [f"预设：{plan.preset.label}（{plan.preset.name}）"]
    if plan.version is None:
        lines.append("目标版本：未指定（按最新版处理带版本限制的项）")
    else:
        lines.append(f"目标版本：TotK Recomp {plan.version}")
    if not plan.changes:
        lines.append("无需改动。")
    else:
        lines.append(f"将修改 {len(plan.changes)} 项：")
        for change in plan.changes:
            old = change.old_value if change.old_value is not None else "（默认）"
            lines.append(f"  {change.key}: {old} -> {change.new_value}")
    if plan.unchanged:
        lines.append(f"已是目标值：{'、'.join(plan.unchanged)}")
    for key, reason in plan.skipped:
        lines.append(f"跳过 {key}：{reason}")
    if plan.warnings:
        lines.append("预览提示：")
        for issue in plan.warnings:
            lines.append(f"  {issue}")
    return "\n".join(lines)

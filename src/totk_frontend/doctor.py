"""M2 ``doctor``：把配置校验结果整理成可操作诊断报告。

规则来源是 ``docs/settings.md`` 第 8 节；具体判定复用 :mod:`totk_frontend.validate`，
本模块只负责：

- 维护“规则表”（规则码 ↔ 说明 ↔ 文档条目），保证第 8 节每条规则都有稳定标识；
- 汇总已知键 / 未知键 / 重复键与版本信息；
- 生成可直接展示给玩家的中文报告与建议。

诊断只读，不修改 ``totk.ini``。安装目录与版本检测在 M5 接入，M2 的版本/分辨率为可选输入。
"""

from __future__ import annotations

from dataclasses import dataclass

from .ini import DuplicateKey, IniDocument
from .settings import is_registered
from .validate import SEVERITY_LABELS, Issue, Severity, validate_document

__all__ = [
    "DoctorRule",
    "RULE_CATALOG",
    "RULES_BY_CODE",
    "DoctorReport",
    "rule_for_code",
    "diagnose",
    "format_report",
]


@dataclass(frozen=True)
class DoctorRule:
    """第 8 节的一条跨字段规则。"""

    code: str
    title: str
    reference: str


#: 与 docs/settings.md 第 8 节的 8 条规则一一对应；code 与 validate 产生的问题码一致。
RULE_CATALOG: tuple[DoctorRule, ...] = (
    DoctorRule(
        code="rule.fps_limit_realtime",
        title="高帧率必须开启 realtime",
        reference="fps_limit > 60 且 realtime = 0",
    ),
    DoctorRule(
        code="rule.free_cores",
        title="free_cores = 1 会启动即崩",
        reference="free_cores = 1",
    ),
    DoctorRule(
        code="rule.mouse_sens_off",
        title="mouse_sens = 0 会关闭鼠标相机",
        reference="mouse_sens = 0 但期望鼠标相机",
    ),
    DoctorRule(
        code="rule.prompts_aspect",
        title="非 16:9 下按钮提示会回退游戏原生",
        reference="prompts ∈ {xbox, pc} 且 output_res 非 16:9",
    ),
    DoctorRule(
        code="rule.pad_layout_detected",
        title="面键布局与本机手柄不符",
        reference="pad_layout 与 prompts 组合与本机手柄不符",
    ),
    DoctorRule(
        code="rule.window_size_display",
        title="窗口尺寸超出显示器范围",
        reference="window_size 超出显示器范围",
    ),
    DoctorRule(
        code="rule.upscaler_sharpness",
        title="FSR 锐化为 0 时画面可能偏软",
        reference="upscaler = fsr 且 sharpness = 0",
    ),
    DoctorRule(
        code="rule.duplicate_key",
        title="同一键出现多次",
        reference="同一键出现多次",
    ),
)

RULES_BY_CODE: dict[str, DoctorRule] = {rule.code: rule for rule in RULE_CATALOG}

_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def rule_for_code(code: str) -> DoctorRule | None:
    """按问题码返回规则表条目；非第 8 节规则返回 ``None``。"""
    return RULES_BY_CODE.get(code)


@dataclass(frozen=True)
class DoctorReport:
    """一份诊断报告。"""

    version: str | None
    issues: tuple[Issue, ...]
    unknown_keys: tuple[str, ...]
    duplicates: tuple[DuplicateKey, ...]
    checked_keys: tuple[str, ...]

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.WARNING)

    @property
    def infos(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.INFO)

    @property
    def ok(self) -> bool:
        return not self.errors


def diagnose(
    document: IniDocument,
    *,
    version: str | None = None,
    display_size: tuple[int, int] | None = None,
    detected_pad_layout: str | None = None,
    mouse_camera_expected: bool | None = None,
) -> DoctorReport:
    """诊断一份 ``totk.ini``：返回按严重级别排序的问题、未知键与重复键摘要。"""
    if not isinstance(document, IniDocument):
        raise TypeError("document 必须是 IniDocument")
    issues = validate_document(
        document,
        version=version,
        display_size=display_size,
        detected_pad_layout=detected_pad_layout,
        mouse_camera_expected=mouse_camera_expected,
    )
    issues.sort(key=lambda issue: _SEVERITY_ORDER[issue.severity])
    active_keys = document.keys()
    checked_keys = tuple(key for key in active_keys if is_registered(key))
    unknown_keys = tuple(key for key in active_keys if not is_registered(key))
    return DoctorReport(
        version=version,
        issues=tuple(issues),
        unknown_keys=unknown_keys,
        duplicates=document.duplicates(),
        checked_keys=checked_keys,
    )


def _format_issue(issue: Issue) -> list[str]:
    lines = [f"[{SEVERITY_LABELS[issue.severity]}] {issue.message}"]
    if issue.suggestion:
        lines.append(f"  建议：{issue.suggestion}")
    return lines


def format_report(report: DoctorReport, *, max_unknown: int = 8) -> str:
    """把诊断报告格式化为中文文本（CLI / GUI 共用）。

    ``max_unknown`` 控制未知键最多列出几个，其余用“共 N 个”概括，避免刷屏。
    """
    if not isinstance(report, DoctorReport):
        raise TypeError("report 必须是 DoctorReport")
    lines = ["配置诊断（TotK Frontend doctor）"]
    lines.append(f"TotK Recomp 版本：{report.version if report.version else '未指定'}")
    lines.append(
        f"检查项：已知键 {len(report.checked_keys)} 个，未知键 {len(report.unknown_keys)} 个"
    )
    lines.append(
        f"结果：错误 {len(report.errors)} / 警告 {len(report.warnings)} / 提示 {len(report.infos)}"
    )
    lines.append("")
    for issue in report.issues:
        lines.extend(_format_issue(issue))
    if report.issues:
        lines.append("")
    if report.unknown_keys:
        shown = list(report.unknown_keys[:max_unknown])
        summary = "、".join(shown)
        if len(report.unknown_keys) > len(shown):
            summary += f" …（共 {len(report.unknown_keys)} 个）"
        lines.append(f"未知键（保留，不校验）：{summary}")
    if report.duplicates:
        lines.append(f"重复键：{'、'.join(item.key for item in report.duplicates)}")
    if report.errors:
        lines.append(f"结论：发现 {len(report.errors)} 个必须修正的问题。")
    elif report.warnings:
        lines.append(f"结论：没有错误；有 {len(report.warnings)} 条警告建议处理。")
    else:
        lines.append("结论：未发现需要处理的问题。")
    return "\n".join(lines)

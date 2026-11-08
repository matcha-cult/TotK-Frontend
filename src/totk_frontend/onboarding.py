"""首次引导（M5-T2）：把安装检测结果变成“球员该做什么”的分步指引。

约束（见 ``docs/plan.md`` M5 与 ``docs/design.md`` 第 16 节）：

- **只读**：本模块不创建、不修改、不删除任何文件，尤其不改动游戏文件；
- **不代跑安装器、不下载任何内容**：只检查与提示，所有修复动作都由玩家自己完成；
- 复用 :func:`totk_frontend.install.format_install_report` 的检测结论与
  :func:`totk_frontend.validate.validate_document` 的配置问题。

CLI（``guide`` 命令）与 GUI（首次启动时的引导对话框）共用 :func:`build_guide`
与 :func:`format_guide`，保证两边文案与判断一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ini import IniDocument, IniParseError, read_ini
from .install import (
    INI_MARKER,
    InstallInfo,
    VersionDetection,
    detect_install,
    detect_version,
    format_install_report,
    install_findings,
)
from .validate import Issue, Severity, validate_document
from .versions import get_version_note

__all__ = [
    "GuideStep",
    "GuideState",
    "build_guide",
    "format_guide",
    "needs_guidance",
]


@dataclass(frozen=True)
class GuideStep:
    """引导中的一步。

    ``informational`` 为真的步骤（如“开始游戏”）只做说明，不参与“下一步”的计算。
    """

    number: int
    title: str
    detail: str
    done: bool
    informational: bool = False

    @property
    def marker(self) -> str:
        if self.informational:
            return "说明"
        return "已完成" if self.done else "待完成"


@dataclass(frozen=True)
class GuideState:
    """一次引导的状态快照。"""

    directory: Path
    info: InstallInfo
    version: VersionDetection
    ini_path: Path
    steps: tuple[GuideStep, ...]
    findings: tuple[str, ...]
    config_issues: tuple[Issue, ...]

    @property
    def detected(self) -> bool:
        """是否已选定一个看起来可用的安装目录。"""
        return self.info.looks_like_install

    @property
    def config_errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.config_issues if issue.severity is Severity.ERROR)

    @property
    def ok(self) -> bool:
        """引导是否已完成到“可以开始游戏”的程度。"""
        return self.detected and not self.config_errors

    @property
    def actionable_steps(self) -> tuple[GuideStep, ...]:
        """需要玩家完成的步骤（不含最后一步说明）。"""
        return tuple(step for step in self.steps if not step.informational)

    @property
    def next_step(self) -> GuideStep | None:
        """第一个未完成的待办步骤；全部待办完成时返回 ``None``。"""
        for step in self.actionable_steps:
            if not step.done:
                return step
        return None


def _load_and_check(
    path: Path, version: str | None
) -> tuple[IniDocument | None, list[Issue], str | None]:
    """读取并校验 ``totk.ini``；返回（文档, 问题列表, 读取失败说明）。只读。"""
    if not path.exists():
        return None, [], None
    try:
        document = read_ini(path)
    except IniParseError as exc:
        return None, [], str(exc)
    return document, list(validate_document(document, version=version)), None


def build_guide(
    directory: str | Path,
    *,
    version: str | None = None,
) -> GuideState:
    """构造引导状态；只读，不修改任何文件。

    ``version`` 为 ``None`` 时尝试从安装记录识别版本，识别不出则按未指定处理。
    """
    target = Path(directory)
    info = detect_install(target)
    detection = detect_version(target)
    effective_version = version if version is not None else detection.version
    ini_path = target / INI_MARKER
    document, issues, read_error = _load_and_check(ini_path, effective_version)

    findings = tuple(str(finding) for finding in install_findings(info))
    if read_error is not None:
        findings = findings + (f"无法读取 {INI_MARKER}：{read_error}",)

    version_note = get_version_note(effective_version) if effective_version else None
    if effective_version is None:
        version_detail = "尚未识别版本：可稍后在设置页选择，或先运行一次游戏让安装记录生成。"
        version_done = False
    elif version_note is None:
        version_detail = (
            f"识别到未记录的版本 {effective_version}：键支持情况未知，"
            "带版本限制的键（fov、menu_cursor）请谨慎修改。"
        )
        version_done = True
    else:
        version_detail = f"{version_note.label}：{version_note.summary}"
        version_done = True

    ini_exists = ini_path.exists()
    if ini_exists:
        if read_error is not None:
            ini_detail = f"{INI_MARKER} 存在但无法解析：{read_error}。请先用备份恢复或让游戏重新生成。"
            ini_done = False
        else:
            line_count = len(document) if document is not None else 0
            ini_detail = (
                f"已找到 {INI_MARKER}，共 {line_count} 行；保存时会先备份再原子写入。"
            )
            ini_done = True
    else:
        ini_detail = (
            f"未找到 {INI_MARKER}：首次启动游戏或在游戏内 F1 菜单保存设置后会生成；"
            "也可以按默认值继续，保存时新建。"
        )
        ini_done = False

    if issues:
        errors = [issue for issue in issues if issue.severity is Severity.ERROR]
        if errors:
            config_detail = f"发现 {len(errors)} 个必须修正的问题：" + "；".join(
                issue.message for issue in errors[:3]
            )
            config_done = False
        else:
            config_detail = f"配置没有必须修正的问题（另有 {len(issues)} 条提示，可在 doctor 中查看）。"
            config_done = True
    else:
        config_detail = "配置没有发现需要处理的问题。"
        config_done = True

    steps = (
        GuideStep(
            number=1,
            title="选择 TotK Recomp 安装目录",
            detail=(
                f"当前目录：{info.directory}。"
                if info.looks_like_install
                else f"当前目录 {info.directory} 不像安装目录：请选择包含 totk.exe/totk 与 totk.ini 的目录。"
            ),
            done=info.looks_like_install,
        ),
        GuideStep(number=2, title="确认 totk.ini", detail=ini_detail, done=ini_done),
        GuideStep(number=3, title="确认游戏版本", detail=version_detail, done=version_done),
        GuideStep(
            number=4,
            title="检查配置",
            detail=config_detail,
            done=config_done,
        ),
        GuideStep(
            number=5,
            title="开始游戏",
            detail="以上步骤完成后，可用“启动游戏”按钮启动 totk.exe/totk；本工具不代跑安装器、不下载任何内容。",
            done=False,
            informational=True,
        ),
    )

    return GuideState(
        directory=info.directory,
        info=info,
        version=detection,
        ini_path=ini_path,
        steps=steps,
        findings=findings,
        config_issues=tuple(issues),
    )


def needs_guidance(directory: str | Path) -> bool:
    """是否需要显示首次引导：目录不是安装目录，或配置有必须修正的问题。"""
    return not build_guide(directory).ok


def format_guide(state: GuideState, *, include_report: bool = True) -> str:
    """把引导状态格式化为中文文本（CLI 与 GUI 共用）。"""
    if not isinstance(state, GuideState):
        raise TypeError("state 必须是 GuideState")
    lines = ["TotK Frontend 首次引导", "=" * 24]
    if include_report:
        lines.append(format_install_report(state.directory))
        lines.append("")
    lines.append("步骤：")
    for step in state.steps:
        lines.append(f"  {step.number}. [{step.marker}] {step.title}")
        lines.append(f"     {step.detail}")
    lines.append("")
    current = state.next_step
    if current is not None:
        lines.append(f"下一步：{current.title}——{current.detail}")
    else:
        lines.append("下一步：可以直接开始游戏。")
    return "\n".join(lines)

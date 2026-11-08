"""TotK Recomp 安装目录检测与结果解释（M3 最小实现，M5 扩展）。

判定标记见 ``docs/design.md`` 第 8 节：``totk.exe``（Windows）或 ``totk``（Linux）、
``totk.ini``、``totk-install.json``、``exefs/``、``romfs/``。

本模块只做只读检查：不执行安装器、不下载任何内容、不修改游戏文件。
缺失项会给出可解释的 :class:`InstallFinding`（级别、原因、建议），供 CLI 与 M4 GUI 的引导页展示。

版本识别是**尽力而为**：``totk-install.json`` 的字段格式尚未与上游核对，只在能安全识别出
``主.次.修订`` 形式且字段名属于版本类字段时返回结果，否则返回未知，不猜测。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .versions import VERSION_NOTES

__all__ = [
    "EXECUTABLE_MARKERS",
    "INI_MARKER",
    "INSTALL_FILE_MARKER",
    "DIRECTORY_MARKERS",
    "ALL_MARKERS",
    "InstallInfo",
    "FindingLevel",
    "InstallFinding",
    "VersionDetection",
    "detect_install",
    "find_install",
    "detect_version",
    "install_findings",
    "format_install_report",
]

EXECUTABLE_MARKERS: tuple[str, ...] = ("totk.exe", "totk")
INI_MARKER = "totk.ini"
INSTALL_FILE_MARKER = "totk-install.json"
DIRECTORY_MARKERS: tuple[str, ...] = ("exefs", "romfs")
ALL_MARKERS: tuple[str, ...] = (
    *EXECUTABLE_MARKERS,
    INI_MARKER,
    INSTALL_FILE_MARKER,
    *DIRECTORY_MARKERS,
)


@dataclass(frozen=True)
class InstallInfo:
    """一个目录的检测结果。"""

    directory: Path
    markers: tuple[tuple[str, bool], ...]

    @property
    def executable(self) -> Path | None:
        for name in EXECUTABLE_MARKERS:
            candidate = self.directory / name
            if candidate.exists():
                return candidate
        return None

    @property
    def ini_path(self) -> Path:
        return self.directory / INI_MARKER

    @property
    def present(self) -> tuple[str, ...]:
        return tuple(name for name, exists in self.markers if exists)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(name for name, exists in self.markers if not exists)

    @property
    def looks_like_install(self) -> bool:
        """有可执行文件或 totk-install.json，并且至少有一个配置/数据标记。"""
        if self.executable is None and not (self.directory / INSTALL_FILE_MARKER).exists():
            return False
        return (
            self.ini_path.exists()
            or (self.directory / INSTALL_FILE_MARKER).exists()
            or any((self.directory / name).exists() for name in DIRECTORY_MARKERS)
        )


def detect_install(directory: str | Path) -> InstallInfo:
    """检查 ``directory`` 下的安装标记；只读，不会创建任何文件。"""
    target = Path(directory)
    markers = tuple((name, (target / name).exists()) for name in ALL_MARKERS)
    return InstallInfo(directory=target, markers=markers)


def find_install(start: str | Path | None = None) -> Path | None:
    """从 ``start``（默认当前目录）向上查找疑似安装目录；找不到返回 ``None``。"""
    current = Path(start) if start is not None else Path.cwd()
    for directory in (current, *current.parents):
        info = detect_install(directory)
        if info.looks_like_install:
            return directory
    return None


class FindingLevel(Enum):
    """检测结论的级别。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


FINDING_LABELS = {
    FindingLevel.ERROR: "错误",
    FindingLevel.WARNING: "警告",
    FindingLevel.INFO: "提示",
}


@dataclass(frozen=True)
class InstallFinding:
    """一条可解释的检测结论。"""

    level: FindingLevel
    code: str
    message: str
    suggestion: str = ""

    def __str__(self) -> str:
        return f"[{FINDING_LABELS[self.level]}] {self.message}"


#: 各标记缺失时的解释与建议；可执行文件作为一组单独处理（Windows 用 totk.exe，Linux 用 totk）。
_MARKER_EXPLANATIONS: dict[str, tuple[FindingLevel, str, str]] = {
    INI_MARKER: (
        FindingLevel.WARNING,
        "未找到 totk.ini",
        "首次启动游戏或在游戏内 F1 菜单保存设置后会生成；也可以按默认值继续。",
    ),
    INSTALL_FILE_MARKER: (
        FindingLevel.INFO,
        "未找到安装记录 totk-install.json",
        "该文件由 TotK Recomp 安装器生成；缺失不影响读写设置。",
    ),
    "exefs": (
        FindingLevel.WARNING,
        "未找到 exefs/",
        "游戏数据目录缺失；本工具不提供、不下载任何游戏数据。",
    ),
    "romfs": (
        FindingLevel.WARNING,
        "未找到 romfs/",
        "游戏数据目录缺失；本工具不提供、不下载任何游戏数据。",
    ),
}

_VERSION_FIELD_NAMES = frozenset(
    {"version", "game_version", "gameversion", "totk_version", "title_version", "build_version"}
)
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_MAX_SCAN_DEPTH = 4


@dataclass(frozen=True)
class VersionDetection:
    """版本识别结果。``version`` 为 ``None`` 表示未能识别。"""

    version: str | None
    source: str | None
    known: bool
    detail: str


def _find_version_field(node, depth: int = 0) -> str | None:  # noqa: ANN001 - JSON 结构
    if depth > _MAX_SCAN_DEPTH:
        return None
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.strip().lower() in _VERSION_FIELD_NAMES:
                text = str(value).strip() if isinstance(value, (str, int, float)) else ""
                if _VERSION_RE.match(text):
                    return text
        for value in node.values():
            found = _find_version_field(value, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_version_field(value, depth + 1)
            if found is not None:
                return found
    return None


def detect_version(directory: str | Path) -> VersionDetection:
    """尽力从 ``totk-install.json`` 识别 TotK Recomp 版本；识别失败返回未知，不猜测。"""
    path = Path(directory) / INSTALL_FILE_MARKER
    if not path.exists():
        return VersionDetection(
            version=None,
            source=None,
            known=False,
            detail=f"未找到 {INSTALL_FILE_MARKER}，无法识别版本。",
        )
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return VersionDetection(
            version=None, source=str(path), known=False, detail=f"无法读取安装记录：{exc}"
        )
    try:
        data = json.loads(text)
    except ValueError:
        return VersionDetection(
            version=None,
            source=str(path),
            known=False,
            detail="安装记录不是有效 JSON，无法识别版本。",
        )
    version = _find_version_field(data)
    if version is None:
        return VersionDetection(
            version=None,
            source=str(path),
            known=False,
            detail="安装记录中没有可识别的版本字段。",
        )
    known = version in VERSION_NOTES
    detail = (
        f"识别到 TotK Recomp {version}。"
        if known
        else f"识别到 TotK Recomp {version}（未见文档记录，按键支持情况未知）。"
    )
    return VersionDetection(version=version, source=str(path), known=known, detail=detail)


def install_findings(info: InstallInfo) -> tuple[InstallFinding, ...]:
    """把检测结果转成可解释的结论列表（错误 → 警告 → 提示）。"""
    if not isinstance(info, InstallInfo):
        raise TypeError("info 必须是 InstallInfo")
    findings: list[InstallFinding] = []
    present = set(info.present)

    if info.executable is None:
        findings.append(
            InstallFinding(
                level=FindingLevel.ERROR,
                code="install.executable_missing",
                message="未找到游戏可执行文件 totk.exe（Windows）或 totk（Linux）。",
                suggestion="确认所选目录是 TotK Recomp 的安装目录：可执行文件与 totk.ini 位于同一目录。",
            )
        )

    for marker, (level, message, suggestion) in _MARKER_EXPLANATIONS.items():
        if marker not in present:
            findings.append(
                InstallFinding(level=level, code=f"install.marker.{marker}", message=message, suggestion=suggestion)
            )

    if not info.looks_like_install:
        findings.append(
            InstallFinding(
                level=FindingLevel.ERROR,
                code="install.not_an_install",
                message="该目录不像 TotK Recomp 安装目录。",
                suggestion="选择包含 totk.exe/totk 与 totk.ini（或 exefs/、romfs/）的目录。",
            )
        )
    return tuple(findings)


def format_install_report(
    directory: str | Path,
    *,
    version: VersionDetection | None = None,
    max_findings: int = 20,
) -> str:
    """生成中文安装检测报告（CLI 与 M4 引导页共用）。"""
    info = detect_install(directory)
    if version is None:
        version = detect_version(directory)
    findings = install_findings(info)
    lines = [f"安装目录：{info.directory}"]
    for name, exists in info.markers:
        lines.append(f"  {'存在' if exists else '缺失'}  {name}")
    if info.looks_like_install:
        lines.append("结果：检测通过。")
    else:
        lines.append("结果：缺少必要标记：" + "、".join(info.missing))
    lines.append("")
    lines.append(f"版本：{version.detail}")
    if findings:
        lines.append("")
        for finding in findings[:max_findings]:
            lines.append(str(finding))
            if finding.suggestion:
                lines.append(f"  建议：{finding.suggestion}")
        if len(findings) > max_findings:
            lines.append(f"…（共 {len(findings)} 条结论）")
    return "\n".join(lines)

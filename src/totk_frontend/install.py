"""TotK Recomp 安装目录检测（M3 最小实现，M5 扩展版本与缺失解释）。

判定标记见 ``docs/design.md`` 第 8 节：``totk.exe``（Windows）或 ``totk``（Linux）、
``totk.ini``、``totk-install.json``、``exefs/``、``romfs/``。

本模块只做“是否存在”的只读检查，不执行安装器、不下载任何内容、不修改游戏文件。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "EXECUTABLE_MARKERS",
    "INI_MARKER",
    "INSTALL_FILE_MARKER",
    "DIRECTORY_MARKERS",
    "ALL_MARKERS",
    "InstallInfo",
    "detect_install",
    "find_install",
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

"""TotK Recomp 版本感知。

公开文档（``docs/design.md`` 第 8 节、``docs/settings.md``）记录了三代版本：

- ``1.1.0``：鼠标相机为右摇杆模拟，没有原生菜单鼠标；
- ``1.2.1``：鼠标相机为直连，原生菜单鼠标与 ``fov`` 仍不可用；
- ``1.4.3``：鼠标相机直连 + 原生菜单鼠标 + ``fov``，重点支持版本。

本模块只提供**静态版本知识**与“某键在某版本是否可用”的查询；真实安装目录的版本识别
见 :func:`totk_frontend.install.detect_version`（尽力识别，失败返回未知，不做猜测）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .settings import SETTINGS, Setting, get_setting

__all__ = [
    "KNOWN_VERSIONS",
    "DEFAULT_VERSION",
    "VersionNote",
    "VERSION_NOTES",
    "get_version_note",
    "is_known_version",
    "versions_for_key",
    "key_supported_in",
    "unsupported_keys",
    "describe_version",
]

#: 公开文档记录过的版本，按从旧到新排列。
KNOWN_VERSIONS: tuple[str, ...] = ("1.1.0", "1.2.1", "1.4.3")

#: 默认按最新记录版本处理（与 ``docs/settings.md`` 的“重点 1.4.3”一致）。
DEFAULT_VERSION = "1.4.3"


@dataclass(frozen=True)
class VersionNote:
    """一个版本的能力说明。"""

    version: str
    label: str
    mouse_camera: str
    menu_cursor: bool
    fov: bool
    summary: str


VERSION_NOTES: dict[str, VersionNote] = {
    "1.1.0": VersionNote(
        version="1.1.0",
        label="TotK Recomp 1.1.0",
        mouse_camera="摇杆模拟（鼠标当作右摇杆）",
        menu_cursor=False,
        fov=False,
        summary="旧版：鼠标相机为摇杆模拟，没有原生菜单鼠标与视野设置。",
    ),
    "1.2.1": VersionNote(
        version="1.2.1",
        label="TotK Recomp 1.2.1",
        mouse_camera="直连（与 1.4.3 相同的原始鼠标输入）",
        menu_cursor=False,
        fov=False,
        summary="鼠标相机直连，但原生菜单鼠标与视野仍是 1.4.3 才完整可用。",
    ),
    "1.4.3": VersionNote(
        version="1.4.3",
        label="TotK Recomp 1.4.3",
        mouse_camera="直连",
        menu_cursor=True,
        fov=True,
        summary="重点支持版本：鼠标相机直连、原生菜单鼠标与视野设置全部可用。",
    ),
}


def is_known_version(version: str) -> bool:
    """``version`` 是否是公开文档记录过的版本（大小写/空白不敏感）。"""
    if not isinstance(version, str):
        return False
    return version.strip() in VERSION_NOTES


def get_version_note(version: str) -> VersionNote | None:
    """返回版本说明；未记录的版本返回 ``None``。"""
    if not isinstance(version, str):
        raise TypeError("version 必须是字符串")
    return VERSION_NOTES.get(version.strip())


def versions_for_key(key: str) -> tuple[str, ...]:
    """返回某个键被明确限制使用的版本；空元组表示所有版本可用。"""
    setting = get_setting(key)
    if setting is None:
        raise ValueError(f"未知键：{key}")
    return setting.versions


def key_supported_in(key: str, version: str) -> bool:
    """键在指定版本下是否可用；未声明版本限制的键对所有版本可用。"""
    setting: Setting | None = get_setting(key)
    if setting is None:
        raise ValueError(f"未知键：{key}")
    if not isinstance(version, str):
        raise TypeError("version 必须是字符串")
    return setting.supports_version(version.strip())


def unsupported_keys(version: str) -> tuple[str, ...]:
    """返回该版本下不可用（被限制到其他版本）的全部注册键。"""
    if not isinstance(version, str):
        raise TypeError("version 必须是字符串")
    normalized = version.strip()
    return tuple(
        setting.key
        for setting in SETTINGS
        if not setting.is_pattern and setting.versions and normalized not in setting.versions
    )


def describe_version(version: str) -> str:
    """生成一段中文版本说明；未知版本返回“未记录”提示。"""
    note = get_version_note(version) if isinstance(version, str) else None
    if note is None:
        return f"未记录的 TotK Recomp 版本：{version}"
    lines = [f"{note.label}：{note.summary}"]
    restricted = [
        (setting.key, setting.versions)
        for setting in SETTINGS
        if not setting.is_pattern and setting.versions and version.strip() not in setting.versions
    ]
    if restricted:
        detail = "、".join(f"{key}（仅 {'/'.join(versions)}）" for key, versions in restricted)
        lines.append(f"该版本不可用的键：{detail}")
    else:
        lines.append("该版本可用全部已注册版本限定键。")
    return "\n".join(lines)

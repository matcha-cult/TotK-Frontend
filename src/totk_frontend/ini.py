"""``totk.ini`` 的解析与安全写入。

本模块只做纯文本层面的工作：解析出节、键、注释与未知行，**保留每一行的原始文本与换行符**；
修改时只替换目标键最后一个生效行的值，其余字节保持不变。

写盘遵循 docs/design.md 第 7 节的写入安全模型，实现约定见第 12 节：

1. 写入前把现有文件复制为同目录的 ``totk.ini.bak-YYYYmmdd-HHMMSS``；
2. 先用临时文件写入并 ``os.replace`` 原子替换；
3. 回读文件并逐键核对本次改动；
4. 任一步失败则用写入前的原内容原子恢复；备份不删除。

``totk.ini`` 的语义（见 docs/settings.md 开头）：

- ``[section]`` 只用于分组；
- ``#`` 与 ``;`` 开头的行为注释（不做行内注释解析）；
- 键名大小写不敏感；未出现或注释掉的行表示默认值；
- 同名键以最后一个生效。

编码固定为 UTF-8，可带 BOM（读写均原样保留）；换行风格逐行保留，新增行沿用文件内的主流换行。
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Sequence

__all__ = [
    "BOM_BYTES",
    "BOM_CHAR",
    "ENCODING",
    "DEFAULT_BACKUP_TIMESTAMP_FORMAT",
    "IniError",
    "IniParseError",
    "IniWriteError",
    "LineKind",
    "Line",
    "ChangeOp",
    "Change",
    "DuplicateKey",
    "IniDocument",
    "WriteResult",
    "read_ini",
    "write_ini",
    "write_bytes_atomic",
    "create_backup",
]

ENCODING = "utf-8"
BOM_BYTES = b"\xef\xbb\xbf"
BOM_CHAR = "\ufeff"
DEFAULT_BACKUP_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

#: 新建 ``totk.ini`` 时使用的权限位（Windows 上无效果；沿用原文件权限的场景见 write_ini）。
_NEW_FILE_MODE = 0o644

_COMMENT_PREFIXES = ("#", ";")
_SECTION_RE = re.compile(r"^\[\s*(?P<name>[^\[\]]*?)\s*\]$")
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
# 保留 ``key = value`` 中的键名拼写与等号两侧空白，只替换值的部分。
_VALUE_RE = re.compile(r"(?P<head>[^=]*=)(?P<lead>[ \t]*)(?P<value>.*?)(?P<trail>[ \t]*)\Z")


class IniError(Exception):
    """``totk.ini`` 处理相关的基类异常。"""


class IniParseError(IniError):
    """解析或解码失败。"""


class IniWriteError(IniError):
    """写入、备份、回读校验或回滚失败。"""


class LineKind(Enum):
    """单行在 ``totk.ini`` 中的角色。"""

    BLANK = "blank"
    COMMENT = "comment"
    SECTION = "section"
    KEY_VALUE = "key_value"
    OTHER = "other"


@dataclass
class Line:
    """``totk.ini`` 的一行。

    ``text`` 不含换行符，``eol`` 保存该行原本的换行符（``"\\n"``、``"\\r\\n"``，或末行为 ``""``）。
    这样 ``render()`` 可以逐字节还原未修改的文件。
    """

    kind: LineKind
    text: str
    eol: str = ""
    section: str | None = None
    key: str | None = None
    value: str | None = None
    name: str | None = None

    def render(self) -> str:
        return self.text + self.eol


class ChangeOp(Enum):
    """对某个键施加的修改类型。"""

    SET = "set"
    UNSET = "unset"


@dataclass(frozen=True)
class Change:
    """一次修改记录，用于写入后的回读校验。"""

    op: ChangeOp
    key: str
    section: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class DuplicateKey:
    """同一节内重复出现的键。"""

    section: str | None
    key: str
    count: int


def _split_lines(text: str) -> list[tuple[str, str]]:
    """把文本拆成 ``(不含换行符的行, 换行符)``，保留原始换行风格。"""
    result: list[tuple[str, str]] = []
    start = 0
    length = len(text)
    while True:
        index = text.find("\n", start)
        if index < 0:
            if start < length:
                result.append((text[start:], ""))
            break
        raw = text[start:index]
        if raw.endswith("\r"):
            result.append((raw[:-1], "\r\n"))
        else:
            result.append((raw, "\n"))
        start = index + 1
    return result


def _detect_newline(lines: Sequence[Line]) -> str:
    crlf = sum(1 for line in lines if line.eol == "\r\n")
    lf = sum(1 for line in lines if line.eol == "\n")
    if crlf > lf:
        return "\r\n"
    if lf > 0:
        return "\n"
    return os.linesep


def _normalize_key(key: str) -> str:
    text = key.strip()
    if not text:
        raise ValueError("键名不能为空")
    if not _KEY_RE.match(text):
        raise ValueError(f"键名不合法：{key!r}")
    return text.lower()


def _normalize_section(section: str | None) -> str | None:
    if section is None:
        return None
    if not isinstance(section, str):
        raise TypeError("section 必须是字符串或 None")
    text = section.strip()
    if not text:
        raise ValueError("节名不能为空字符串；全局键请使用 section=None 读取")
    return text.lower()


def _normalize_value(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("值必须是字符串")
    if "\n" in value or "\r" in value:
        raise ValueError("值不能包含换行符")
    return value.strip()


def _parse_lines(text: str) -> list[Line]:
    lines: list[Line] = []
    current_section: str | None = None
    for raw, eol in _split_lines(text):
        stripped = raw.strip()
        if not stripped:
            lines.append(Line(LineKind.BLANK, raw, eol, section=current_section))
        elif stripped.startswith(_COMMENT_PREFIXES):
            lines.append(Line(LineKind.COMMENT, raw, eol, section=current_section))
        elif stripped.startswith("["):
            match = _SECTION_RE.match(stripped)
            if match is not None:
                display_name = match.group("name").strip()
                current_section = display_name.lower()
                lines.append(
                    Line(
                        LineKind.SECTION,
                        raw,
                        eol,
                        section=current_section,
                        name=display_name,
                    )
                )
            else:
                lines.append(Line(LineKind.OTHER, raw, eol, section=current_section))
        elif "=" in raw:
            key_part, _, value_part = raw.partition("=")
            key_text = key_part.strip()
            if key_text and _KEY_RE.match(key_text):
                lines.append(
                    Line(
                        LineKind.KEY_VALUE,
                        raw,
                        eol,
                        section=current_section,
                        key=key_text.lower(),
                        value=value_part.strip(),
                    )
                )
            else:
                lines.append(Line(LineKind.OTHER, raw, eol, section=current_section))
        else:
            lines.append(Line(LineKind.OTHER, raw, eol, section=current_section))
    return lines


class IniDocument:
    """保留原始行的 ``totk.ini`` 文档模型。

    解析后文件内容保存在 ``lines`` 中；``set``/``unset`` 只改目标行或插入新行，
    其余行保持原样，因此 ``render()`` 的结果除目标行外与原文件逐字节一致。
    """

    def __init__(
        self,
        lines: Iterable[Line],
        *,
        bom: bool = False,
        newline: str | None = None,
        source: str | None = None,
    ) -> None:
        self.lines: list[Line] = list(lines)
        self.bom = bom
        self.newline = newline if newline is not None else _detect_newline(self.lines)
        self.source = source
        self._changes: list[Change] = []

    # ------------------------------------------------------------------ 构造
    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        bom: bool = False,
        newline: str | None = None,
        source: str | None = None,
    ) -> "IniDocument":
        if not isinstance(text, str):
            raise TypeError("text 必须是字符串")
        if text.startswith(BOM_CHAR):
            text = text[len(BOM_CHAR) :]
            bom = True
        return cls(_parse_lines(text), bom=bom, newline=newline, source=source)

    @classmethod
    def from_bytes(cls, data: bytes, *, source: str | None = None) -> "IniDocument":
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data 必须是 bytes")
        raw = bytes(data)
        bom = raw.startswith(BOM_BYTES)
        body = raw[len(BOM_BYTES) :] if bom else raw
        try:
            text = body.decode(ENCODING)
        except UnicodeDecodeError as exc:
            where = source or "<bytes>"
            raise IniParseError(f"{where} 不是有效的 UTF-8（totk.ini 需为 UTF-8）") from exc
        return cls.from_text(text, bom=bom, source=source)

    @classmethod
    def from_path(cls, path: str | Path) -> "IniDocument":
        target = Path(path)
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise IniParseError(f"无法读取 {target}：{exc}") from exc
        return cls.from_bytes(data, source=str(target))

    # ------------------------------------------------------------------ 查询
    def get(self, key: str, section: str | None = None, default: str | None = None) -> str | None:
        """返回键的生效值：符合条件的最后一个激活行；没有则返回 ``default``。"""
        key_norm = _normalize_key(key)
        section_norm = _normalize_section(section)
        found = default
        for line in self.lines:
            if line.kind is not LineKind.KEY_VALUE or line.key != key_norm:
                continue
            if section_norm is not None and line.section != section_norm:
                continue
            found = line.value
        return found

    def get_all(self, key: str, section: str | None = None) -> list[str]:
        """返回键的全部激活值（按文件顺序）。"""
        key_norm = _normalize_key(key)
        section_norm = _normalize_section(section)
        return [
            line.value
            for line in self.lines
            if line.kind is LineKind.KEY_VALUE
            and line.key == key_norm
            and (section_norm is None or line.section == section_norm)
        ]

    def has(self, key: str, section: str | None = None) -> bool:
        return self.get(key, section) is not None

    def sections(self) -> tuple[str, ...]:
        """按首次出现顺序返回节名（保留文件中的拼写）。"""
        seen: set[str] = set()
        names: list[str] = []
        for line in self.lines:
            if line.kind is LineKind.SECTION and line.section is not None:
                if line.section not in seen:
                    seen.add(line.section)
                    names.append(line.name or line.section)
        return tuple(names)

    def keys(self, section: str | None = None) -> tuple[str, ...]:
        """按首次出现顺序返回激活键名（小写；同一键只列一次）。"""
        section_norm = _normalize_section(section)
        seen: set[str] = set()
        result: list[str] = []
        for line in self.lines:
            if line.kind is not LineKind.KEY_VALUE or line.key is None:
                continue
            if section_norm is not None and line.section != section_norm:
                continue
            if line.key not in seen:
                seen.add(line.key)
                result.append(line.key)
        return tuple(result)

    def duplicates(self) -> tuple[DuplicateKey, ...]:
        """返回同一节内重复出现的键（按首次出现顺序）。"""
        counts: dict[tuple[str | None, str], int] = {}
        order: list[tuple[str | None, str]] = []
        for line in self.lines:
            if line.kind is not LineKind.KEY_VALUE or line.key is None:
                continue
            identity = (line.section, line.key)
            if identity not in counts:
                counts[identity] = 0
                order.append(identity)
            counts[identity] += 1
        return tuple(
            DuplicateKey(section, key, counts[(section, key)])
            for section, key in order
            if counts[(section, key)] > 1
        )

    @property
    def changes(self) -> tuple[Change, ...]:
        """自解析以来通过 ``set``/``unset`` 记录的修改。"""
        return tuple(self._changes)

    # ------------------------------------------------------------------ 修改
    def set(self, key: str, value: str, section: str | None = None) -> None:
        """设置键值。

        - 键已存在：只替换最后一个生效行的值，保留键名拼写、等号位置与两侧空白；
        - 键不存在：在指定节内最后一个键值行之后插入；节不存在时在文件末尾新建该节；
        - ``section=None`` 且键不存在时无法确定插入位置，抛出 :class:`ValueError`。

        传入的 ``value`` 会去除首尾空白；不允许包含换行符。
        """
        raw_key = key.strip()
        key_norm = _normalize_key(raw_key)
        value_norm = _normalize_value(value)
        section_norm = _normalize_section(section)

        target = self._find_last(key_norm, section_norm)
        if target is not None:
            self._replace_line_value(target, value_norm)
        else:
            if section_norm is None:
                raise ValueError(f"新增键 {key_norm} 时必须指定 section")
            self._insert_in_section(section_norm, raw_key, key_norm, value_norm)
        self._changes.append(Change(ChangeOp.SET, key_norm, section_norm, value_norm))

    def unset(self, key: str, section: str | None = None) -> int:
        """移除键的全部激活行（恢复默认值），返回移除的行数；注释行不受影响。"""
        key_norm = _normalize_key(key)
        section_norm = _normalize_section(section)
        kept: list[Line] = []
        removed = 0
        for line in self.lines:
            if (
                line.kind is LineKind.KEY_VALUE
                and line.key == key_norm
                and (section_norm is None or line.section == section_norm)
            ):
                removed += 1
                continue
            kept.append(line)
        if removed:
            self.lines = kept
            self._changes.append(Change(ChangeOp.UNSET, key_norm, section_norm))
        return removed

    def _find_last(self, key: str, section: str | None) -> Line | None:
        found = None
        for line in self.lines:
            if line.kind is not LineKind.KEY_VALUE or line.key != key:
                continue
            if section is not None and line.section != section:
                continue
            found = line
        return found

    @staticmethod
    def _replace_line_value(line: Line, value: str) -> None:
        match = _VALUE_RE.match(line.text)
        if match is None:
            line.text = f"{line.key} = {value}"
        else:
            line.text = match.group("head") + match.group("lead") + value + match.group("trail")
        line.value = value

    def _insert_in_section(self, section: str, raw_key: str, key_norm: str, value: str) -> None:
        header_index: int | None = None
        for index, line in enumerate(self.lines):
            if line.kind is LineKind.SECTION and line.section == section:
                header_index = index
        if header_index is None:
            self._append_section(section, raw_key, key_norm, value)
            return
        last_key_value: int | None = None
        last_content: int | None = None
        for index in range(header_index + 1, len(self.lines)):
            line = self.lines[index]
            if line.kind is LineKind.SECTION:
                break
            if line.kind is LineKind.KEY_VALUE and line.section == section:
                last_key_value = index
            if line.text.strip():
                last_content = index
        if last_key_value is not None:
            insert_index = last_key_value
        elif last_content is not None:
            insert_index = last_content
        else:
            insert_index = header_index
        self.lines.insert(
            insert_index + 1,
            Line(
                LineKind.KEY_VALUE,
                f"{raw_key} = {value}",
                self.newline,
                section=section,
                key=key_norm,
                value=value,
            ),
        )

    def _append_section(self, section: str, raw_key: str, key_norm: str, value: str) -> None:
        if self.lines:
            last = self.lines[-1]
            if last.eol == "":
                last.eol = self.newline
            if last.kind is not LineKind.BLANK:
                self.lines.append(Line(LineKind.BLANK, "", self.newline, section=last.section))
        self.lines.append(
            Line(LineKind.SECTION, f"[{section}]", self.newline, section=section, name=section)
        )
        self.lines.append(
            Line(
                LineKind.KEY_VALUE,
                f"{raw_key} = {value}",
                self.newline,
                section=section,
                key=key_norm,
                value=value,
            )
        )

    def _expected_state(self) -> dict[tuple[str | None, str], Change]:
        """按 ``(节, 键)`` 汇总修改的最终期望值；同一键多次修改时以最后一次为准。"""
        expected: dict[tuple[str | None, str], Change] = {}
        for change in self._changes:
            expected[(change.section, change.key)] = change
        return expected

    # ------------------------------------------------------------------ 输出
    def render(self) -> str:
        text = "".join(line.render() for line in self.lines)
        return BOM_CHAR + text if self.bom else text

    def to_bytes(self) -> bytes:
        return self.render().encode(ENCODING)

    def __len__(self) -> int:
        return len(self.lines)

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"IniDocument(lines={len(self.lines)}, bom={self.bom}, source={self.source!r})"


# ---------------------------------------------------------------------- 备份


def _timestamp(clock: Callable[[], datetime] | None) -> str:
    return (clock or datetime.now)().strftime(DEFAULT_BACKUP_TIMESTAMP_FORMAT)


def _backup_candidate(path: Path, clock: Callable[[], datetime] | None) -> Path:
    base = path.with_name(f"{path.name}.bak-{_timestamp(clock)}")
    candidate = base
    counter = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{counter}")
        counter += 1
    return candidate


def _fsync_file(path: Path) -> None:
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def create_backup(path: str | Path, *, clock: Callable[[], datetime] | None = None) -> Path:
    """把现有文件复制为同目录备份并返回备份路径；不删除任何文件。"""
    target = Path(path)
    if not target.exists():
        raise IniWriteError(f"无法备份不存在的文件：{target}")
    candidate = _backup_candidate(target, clock)
    try:
        shutil.copy2(target, candidate)
        _fsync_file(candidate)
    except OSError as exc:
        _unlink_quietly(candidate)
        raise IniWriteError(f"无法创建备份 {candidate}：{exc}") from exc
    return candidate


# ---------------------------------------------------------------------- 写入


@dataclass(frozen=True)
class WriteResult:
    """一次写入的结果。"""

    path: Path
    backup_path: Path | None
    changed: bool
    bytes_written: int


def read_ini(path: str | Path) -> IniDocument:
    """读取并解析 ``totk.ini``。"""
    return IniDocument.from_path(path)


def _atomic_replace(source: Path, destination: Path) -> None:
    """``os.replace`` 的薄包装；测试中可替换以模拟替换失败。"""
    os.replace(source, destination)


def write_bytes_atomic(path: str | Path, data: bytes, *, mode: int | None = None) -> None:
    """把字节写入 ``path``：先写同目录临时文件，再原子替换。"""
    target = Path(path)
    if not target.parent.exists():
        raise IniWriteError(f"目标目录不存在：{target.parent}")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data 必须是 bytes")
    temp_path: Path | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.tmp-", dir=str(target.parent)
        )
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(bytes(data))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode if mode is not None else _NEW_FILE_MODE)
        _atomic_replace(temp_path, target)
        temp_path = None
        _fsync_directory(target.parent)
    except OSError as exc:
        raise IniWriteError(f"原子写入 {target} 失败：{exc}") from exc
    finally:
        if temp_path is not None:
            _unlink_quietly(temp_path)


def _read_back(path: Path) -> bytes:
    return path.read_bytes()


def _verify_written(path: Path, document: IniDocument, expected: bytes) -> None:
    actual = _read_back(path)
    if actual != expected:
        raise IniWriteError(f"回读校验失败：{path} 的内容与预期不一致")
    parsed = IniDocument.from_bytes(actual)
    for (section, key), change in document._expected_state().items():
        current = parsed.get(key, section)
        if change.op is ChangeOp.SET:
            if current != change.value:
                raise IniWriteError(
                    f"回读校验失败：{key} 期望 {change.value!r}，实际 {current!r}"
                )
        elif current is not None:
            raise IniWriteError(f"回读校验失败：{key} 应已移除，实际仍为 {current!r}")


def _restore_after_failure(
    path: Path,
    original: bytes | None,
    mode: int | None,
    cause: BaseException,
    backup_path: Path | None,
) -> IniWriteError:
    detail = f"写入 {path} 失败：{cause}"
    if backup_path is not None:
        detail += f"；原文件已备份到 {backup_path}"
    if original is None:
        _unlink_quietly(path)
        return IniWriteError(detail + "；该文件由本次写入新建，已删除")
    try:
        current = path.read_bytes()
    except OSError:
        current = None
    if current == original:
        return IniWriteError(detail + "；原文件未被改动")
    try:
        write_bytes_atomic(path, original, mode=mode)
    except IniError as exc:
        return IniWriteError(detail + f"；回滚失败：{exc}")
    return IniWriteError(detail + "；已恢复原文件内容")


def write_ini(
    path: str | Path,
    document: IniDocument,
    *,
    clock: Callable[[], datetime] | None = None,
    backup: bool = True,
    verify: bool = True,
) -> WriteResult:
    """安全写入 ``document``。

    步骤：内容无变化则直接返回（不备份、不写盘）→ 备份 → 原子写入 → 回读校验；
    写入或校验失败时用写入前的原内容恢复并抛出 :class:`IniWriteError`。
    """
    if not isinstance(document, IniDocument):
        raise TypeError("document 必须是 IniDocument")
    target = Path(path)
    data = document.to_bytes()
    try:
        original: bytes | None = target.read_bytes()
    except FileNotFoundError:
        original = None
    except OSError as exc:
        raise IniWriteError(f"无法读取 {target}：{exc}") from exc

    if original == data:
        return WriteResult(path=target, backup_path=None, changed=False, bytes_written=0)

    mode: int | None = None
    if original is not None:
        try:
            mode = stat.S_IMODE(target.stat().st_mode)
        except OSError:
            mode = None

    backup_path: Path | None = None
    if original is not None and backup:
        backup_path = create_backup(target, clock=clock)

    try:
        write_bytes_atomic(target, data, mode=mode)
        if verify:
            _verify_written(target, document, data)
    except BaseException as exc:  # 包括 KeyboardInterrupt：先恢复，再抛出
        error = _restore_after_failure(target, original, mode, exc, backup_path)
        raise error from exc

    return WriteResult(
        path=target, backup_path=backup_path, changed=True, bytes_written=len(data)
    )

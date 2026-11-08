"""GUI 的无头编辑状态层（M4）：不依赖 tkinter，可在无显示环境完整测试。

职责：

- 持有当前 ``totk.ini`` 文档与“待保存修改”（pending）；
- 提供与界面无关的读写接口：``value``/``set``/``unset``/``changes``；
- 生成待保存的文档副本（``staged_document``），落盘仍走 :func:`totk_frontend.ini.write_ini`；
- 复用注册表、校验、预设与诊断，保证 GUI 与 CLI 结果一致。

Tk 控件只用本模块的返回值刷新界面，不直接操作 ``IniDocument``。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ini import IniDocument, read_ini, write_ini
from .presets import PresetPlan, get_preset, plan_preset
from .settings import SETTINGS, Setting, get_setting
from .validate import Issue, Severity, validate_document, validate_value

__all__ = ["PendingChange", "EditingSession"]


@dataclass(frozen=True)
class PendingChange:
    """界面上一处尚未保存的修改；``new_value`` 为 ``None`` 表示恢复默认（移除激活行）。"""

    key: str
    section: str
    old_value: str | None
    new_value: str | None

    @property
    def is_unset(self) -> bool:
        return self.new_value is None


def _empty_document(path: Path | None = None) -> IniDocument:
    return IniDocument.from_text("", source=str(path) if path is not None else None)


class EditingSession:
    """一份 ``totk.ini`` 的编辑会话。

    ``pending`` 与 ``document`` 分离：修改先进入 pending，``save``/``commit`` 才落到文档与磁盘，
    因此“未保存修改”可以精确判断，也可以整体放弃（``discard_pending``）。
    """

    def __init__(
        self,
        path: str | Path,
        *,
        document: IniDocument | None = None,
        version: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.document = document if document is not None else _empty_document(self.path)
        self.version = version
        self._pending: dict[str, PendingChange] = {}

    # ------------------------------------------------------------------ 构造
    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        version: str | None = None,
    ) -> "EditingSession":
        """读取文件；不存在时以空文档开始（保存时新建）。"""
        target = Path(path)
        document = read_ini(target) if target.exists() else _empty_document(target)
        return cls(target, document=document, version=version)

    # ------------------------------------------------------------------ 查询
    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def pending(self) -> tuple[PendingChange, ...]:
        return tuple(self._pending.values())

    @property
    def dirty(self) -> bool:
        return bool(self._pending)

    def value(self, key: str) -> str | None:
        """界面上应显示的值：待保存值 > 文件值 > 注册表默认值。"""
        normalized = key.strip().lower()
        pending = self._pending.get(normalized)
        if pending is not None:
            return pending.new_value
        current = self.document.get(normalized)
        if current is not None:
            return current
        setting = get_setting(normalized)
        return setting.default if setting is not None else None

    def is_modified(self, key: str) -> bool:
        """该键相对“已保存状态”是否被修改。"""
        return key.strip().lower() in self._pending

    def changed_count(self) -> int:
        return len(self._pending)

    # ------------------------------------------------------------------ 修改
    def set(self, key: str, value: str) -> list[Issue]:
        """登记一处修改；返回单键校验问题（空列表表示通过）。不会写盘。

        值非法时仍记录 pending（便于界面提示并允许用户继续编辑），但 ``save`` 应只在校验通过后调用。
        """
        setting = self._require_setting(key)
        if not isinstance(value, str):
            raise TypeError("value 必须是字符串")
        issues = validate_value(setting, value, key=setting.key)
        text = value.strip()
        old = self.value(setting.key)
        self._pending[setting.key] = PendingChange(
            key=setting.key,
            section=setting.section,
            old_value=old,
            new_value=text,
        )
        return issues

    def unset(self, key: str) -> list[Issue]:
        """登记“恢复默认”：保存时移除该键的激活行。"""
        setting = self._require_setting(key)
        old = self.value(setting.key)
        self._pending[setting.key] = PendingChange(
            key=setting.key,
            section=setting.section,
            old_value=old,
            new_value=None,
        )
        return []

    def discard_pending(self) -> None:
        """放弃全部未保存修改。"""
        self._pending.clear()

    def restore_defaults(self) -> int:
        """把所有已激活的注册键标记为“恢复默认”，返回登记数量。"""
        count = 0
        for setting in SETTINGS:
            if setting.is_pattern:
                continue
            if self.document.get(setting.key) is not None:
                self.unset(setting.key)
                count += 1
        return count

    # ------------------------------------------------------------------ 预设
    def plan_preset(self, name: str) -> PresetPlan:
        """计算预设差异（含待保存修改后的视图）。"""
        return plan_preset(self.staged_document(), name, version=self.version)

    def stage_preset(self, name: str) -> PresetPlan:
        """把预设差异登记为待保存修改，返回计划（不写盘）。"""
        preset = get_preset(name)
        if preset is None:
            raise ValueError(f"未知预设：{name!r}")
        plan = plan_preset(self.staged_document(), preset, version=self.version)
        for change in plan.changes:
            self.set(change.key, change.new_value)
        return plan

    # ------------------------------------------------------------------ 校验
    def staged_document(self) -> IniDocument:
        """返回应用了 pending 的文档副本（不改动 ``self.document``）。"""
        staged = IniDocument.from_bytes(self.document.to_bytes())
        staged.source = self.document.source
        for change in self._pending.values():
            if change.new_value is None:
                staged.unset(change.key, change.section)
            elif staged.get(change.key) is not None:
                staged.set(change.key, change.new_value)
            else:
                staged.set(change.key, change.new_value, change.section)
        return staged

    def issues(self) -> list[Issue]:
        """对“保存后的文档”运行完整校验（单键 + 跨字段 + 版本）。"""
        return validate_document(self.staged_document(), version=self.version)

    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues() if issue.severity is Severity.ERROR]

    # ------------------------------------------------------------------ 提交
    def commit(self) -> tuple[PendingChange, ...]:
        """把 pending 应用到内存文档并清空 pending；不写盘。"""
        applied = self.pending
        if not applied:
            return ()
        self.document = self.staged_document()
        self._pending.clear()
        return applied

    def save(self) -> tuple[tuple[PendingChange, ...], Path | None]:
        """校验通过后写盘（备份、原子替换、回读校验），返回（已应用的修改, 备份路径）。

        校验失败或写盘失败时抛出/返回前不改变会话状态，pending 保留供用户修正后重试。
        """
        errors = self.errors()
        if errors:
            raise ValueError("存在必须修正的设置：" + "；".join(issue.message for issue in errors))
        staged = self.staged_document()
        target = write_ini(self.path, staged)
        applied = self.pending
        self.document = staged
        self._pending.clear()
        return applied, target.backup_path

    def reload(self) -> None:
        """丢弃 pending 并重新读取磁盘文件。"""
        self._pending.clear()
        self.document = (
            read_ini(self.path) if self.path.exists() else _empty_document(self.path)
        )

    # ------------------------------------------------------------------ 展示
    def status_text(self) -> str:
        """状态栏文本：版本、安装目录与修改数量。"""
        parts: list[str] = []
        parts.append(f"TotK Recomp {self.version}" if self.version else "版本未识别")
        if self.exists:
            parts.append(f"{self.path}")
        else:
            parts.append("totk.ini 不存在（保存时新建）")
        if self.dirty:
            parts.append(f"{self.changed_count()} 项未保存")
        else:
            parts.append("没有未保存的修改")
        return " · ".join(parts)

    def _require_setting(self, key: str) -> Setting:
        setting = get_setting(key)
        if setting is None:
            raise ValueError(f"未知键：{key!r}")
        if not setting.writable:
            raise ValueError(f"{key} 只读（由游戏内 F1 菜单管理），启动器不直接修改")
        return setting


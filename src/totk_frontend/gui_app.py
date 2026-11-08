"""tkinter 窗口实现（M4）。

本模块**不**在导入时加载 tkinter：``tk`` 模块由 :mod:`totk_frontend.gui` 的 ``main`` 探测后传入，
因此无 tkinter 的环境也能导入本模块并给出提示。

窗口代码依赖显示环境，无法在无头环境执行；无头测试只覆盖
:mod:`totk_frontend.gui`（入口、探测、回退提示）与 :mod:`totk_frontend.session`（状态层）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .gui import _initial_directory, _resolve_version
from .ini import IniError, create_backup
from .install import detect_install, detect_version, format_install_report
from .presets import PRESETS, format_plan, get_preset
from .session import EditingSession
from .settings import SECTION_LABELS, SECTION_ORDER, get_setting, settings_in_section
from .validate import SEVERITY_LABELS, Severity

__all__ = ["run"]


def run(tk, args: argparse.Namespace) -> int:  # noqa: ANN001 - tkinter 模块
    from tkinter import filedialog, messagebox, ttk

    class Application:
        """主窗口。所有方法只用核心库与 tkinter，不直接解析 ini 文本。"""

        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("TotK Frontend")
            self.root.geometry("1000x700")
            self.root.minsize(820, 560)
            self.directory = _initial_directory(args)
            self.version = _resolve_version(args, self.directory)
            self.session = self._load_session()
            self.vars: dict[str, tk.StringVar] = {}
            self._build()
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self._refresh_status()

        # ------------------------------------------------------------ 初始化
        def _ini_path(self) -> Path:
            if args.ini is not None:
                return Path(args.ini)
            return Path(self.directory) / "totk.ini"

        def _load_session(self) -> EditingSession:
            try:
                return EditingSession.load(self._ini_path(), version=self.version)
            except IniError as exc:
                messagebox.showerror("无法读取 totk.ini", str(exc))
                return EditingSession(self._ini_path(), version=self.version)

        def _build(self) -> None:
            top = ttk.Frame(self.root, padding=(8, 8, 8, 4))
            top.pack(fill="x")
            ttk.Label(top, text="安装目录：").pack(side="left")
            self.dir_var = tk.StringVar(value=str(self.directory))
            ttk.Entry(top, textvariable=self.dir_var, width=62).pack(side="left", padx=(4, 6))
            ttk.Button(top, text="浏览…", command=self._on_browse).pack(side="left")
            ttk.Button(top, text="检测 / 重载", command=self._on_detect).pack(side="left", padx=4)

            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill="both", expand=True, padx=8, pady=4)
            for section in SECTION_ORDER:
                self._add_section_tab(section)
            self._add_log_tab()

            bottom = ttk.Frame(self.root, padding=(8, 4, 8, 8))
            bottom.pack(fill="x")
            ttk.Label(bottom, text="预设：").pack(side="left")
            self.preset_var = tk.StringVar(value=PRESETS[0].label if PRESETS else "")
            preset_combo = ttk.Combobox(
                bottom,
                textvariable=self.preset_var,
                values=[f"{preset.label}（{preset.name}）" for preset in PRESETS],
                state="readonly",
                width=26,
            )
            preset_combo.pack(side="left", padx=4)
            ttk.Button(bottom, text="应用预设", command=self._on_preset).pack(side="left")
            ttk.Button(bottom, text="保存", command=self._on_save).pack(side="left", padx=(12, 4))
            ttk.Button(bottom, text="恢复默认", command=self._on_reset).pack(side="left")
            ttk.Button(bottom, text="备份", command=self._on_backup).pack(side="left", padx=4)
            ttk.Button(bottom, text="启动游戏", command=self._on_launch).pack(side="left")
            ttk.Button(bottom, text="退出", command=self._on_close).pack(side="right")

            self.status_var = tk.StringVar(value="")
            ttk.Label(self.root, textvariable=self.status_var, anchor="w", padding=(8, 0, 8, 6)).pack(
                fill="x"
            )

        def _scrollable(self, parent) -> ttk.Frame:  # noqa: ANN001
            canvas = tk.Canvas(parent, highlightthickness=0)
            scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas)
            inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
            window = canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            canvas.bind_all(
                "<MouseWheel>",
                lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
                add="+",
            )
            return inner

        def _add_section_tab(self, section: str) -> None:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=SECTION_LABELS.get(section, section))
            inner = self._scrollable(frame)
            for setting in settings_in_section(section):
                if setting.is_pattern:
                    continue
                self._add_setting_row(inner, setting)

        def _add_setting_row(self, parent, setting) -> None:  # noqa: ANN001
            row = ttk.Frame(parent, padding=(4, 3))
            row.pack(fill="x")
            label = setting.label
            if setting.priority.value == "P2":
                label += "（高级）"
            ttk.Label(row, text=label, width=24, anchor="w").pack(side="left")
            var = tk.StringVar(value=self._display(setting))
            self.vars[setting.key] = var
            var.trace_add("write", lambda *_args: self._refresh_status())

            if setting.value_type.value == "bool":
                ttk.Checkbutton(
                    row, variable=var, onvalue="1", offvalue="0", command=self._refresh_status
                ).pack(side="left")
            elif setting.value_type.value == "enum" and setting.choices:
                combo = ttk.Combobox(
                    row, textvariable=var, values=list(setting.choices), state="readonly", width=18
                )
                combo.pack(side="left")
                combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_status())
            else:
                ttk.Entry(row, textvariable=var, width=24).pack(side="left")

            ttk.Label(row, text=setting.effect_label, foreground="#555555").pack(side="left", padx=8)
            if setting.range_doc:
                ttk.Label(row, text=setting.range_doc, foreground="#888888").pack(side="left")

        def _add_log_tab(self) -> None:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text="日志")
            bar = ttk.Frame(frame)
            bar.pack(fill="x", padx=4, pady=2)
            ttk.Button(bar, text="刷新日志", command=self._on_refresh_log).pack(side="left")
            ttk.Label(bar, text="读取安装目录下的 totk.log / log.txt / *.log").pack(side="left", padx=8)
            self.log_text = tk.Text(frame, wrap="none", height=20)
            log_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
            self.log_text.configure(yscrollcommand=log_scroll.set)
            self.log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
            log_scroll.pack(side="right", fill="y", pady=4)

        # ------------------------------------------------------------ 数据
        def _display(self, setting) -> str:  # noqa: ANN001
            value = self.session.value(setting.key)
            if value is not None:
                return value
            return setting.default or ""

        def _refresh_values(self) -> None:
            for key, var in self.vars.items():
                setting = get_setting(key)
                if setting is not None:
                    var.set(self._display(setting))

        def _ui_changes(self) -> dict[str, str]:
            """界面相对“已保存 + 待保存状态”的新改动。"""
            changes: dict[str, str] = {}
            for key, var in self.vars.items():
                if self.session.is_modified(key):
                    continue
                setting = get_setting(key)
                if setting is None:
                    continue
                if var.get().strip() != self._display(setting).strip():
                    changes[key] = var.get().strip()
            return changes

        def _is_dirty(self) -> bool:
            return self.session.dirty or bool(self._ui_changes())

        def _refresh_status(self) -> None:
            text = self.session.status_text()
            extra = self._ui_changes()
            if extra:
                text += f" · 界面有 {len(extra)} 项修改未保存"
            self.status_var.set(text)

        # ------------------------------------------------------------ 操作
        def _on_browse(self) -> None:
            chosen = filedialog.askdirectory(initialdir=str(self.directory), title="选择 TotK Recomp 安装目录")
            if not chosen:
                return
            self.dir_var.set(chosen)
            self._reload_for_directory(Path(chosen))

        def _on_detect(self) -> None:
            directory = Path(self.dir_var.get() or ".").expanduser()
            report = format_install_report(directory)
            dialog = tk.Toplevel(self.root)
            dialog.title("安装检测")
            dialog.geometry("760x480")
            text = tk.Text(dialog, wrap="word")
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            text.insert("1.0", report)
            text.configure(state="disabled")
            text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            scrollbar.pack(side="right", fill="y", pady=8)
            self._reload_for_directory(directory)

        def _reload_for_directory(self, directory: Path) -> None:
            if self._is_dirty() and not messagebox.askyesno(
                "放弃未保存的修改？", "切换安装目录会丢弃当前的未保存修改，继续吗？"
            ):
                return
            self.directory = directory
            self.version = _resolve_version(args, directory)
            self.session = self._load_session()
            self.doc_version_note = detect_version(directory).detail
            self._refresh_values()
            self._refresh_status()

        def _on_preset(self) -> None:
            text = self.preset_var.get()
            name = text.rsplit("（", 1)[-1].rstrip("）") if "（" in text else text
            if get_preset(name) is None:
                messagebox.showerror("预设", f"未知预设：{name}")
                return
            try:
                plan = self.session.stage_preset(name)
            except ValueError as exc:
                messagebox.showerror("预设", str(exc))
                return
            self._refresh_values()
            self._refresh_status()
            if plan.changes:
                messagebox.showinfo("预设差异（尚未保存）", format_plan(plan))
            else:
                messagebox.showinfo("预设", "当前设置已是该预设的目标值。")

        def _on_save(self) -> None:
            issues = []
            for key, value in self._ui_changes().items():
                issues.extend(self.session.set(key, value))
            errors = [issue for issue in issues if issue.severity is Severity.ERROR]
            if errors:
                messagebox.showerror(
                    "设置无效", "\n".join(f"{SEVERITY_LABELS[issue.severity]}：{issue.message}" for issue in errors)
                )
                return
            document_errors = self.session.errors()
            if document_errors:
                messagebox.showerror(
                    "配置存在必须修正的问题",
                    "\n".join(issue.message for issue in document_errors),
                )
                return
            try:
                applied, backup = self.session.save()
            except (IniError, ValueError) as exc:
                messagebox.showerror("保存失败", str(exc))
                return
            self._refresh_values()
            self._refresh_status()
            message = f"已保存 {len(applied)} 项修改。" if applied else "没有需要保存的修改。"
            if backup is not None:
                message += f"\n\n备份：{backup}"
            messagebox.showinfo("保存", message)

        def _on_reset(self) -> None:
            if not messagebox.askyesno(
                "恢复默认", "把所有已激活的设置恢复为默认值（保存后生效）？"
            ):
                return
            count = self.session.restore_defaults()
            self._refresh_values()
            self._refresh_status()
            if count:
                messagebox.showinfo("恢复默认", f"已标记 {count} 项恢复默认，点击“保存”后写盘。")
            else:
                messagebox.showinfo("恢复默认", "当前没有已激活的设置。")

        def _on_backup(self) -> None:
            path = self._ini_path()
            if not path.exists():
                messagebox.showwarning("备份", f"未找到 {path}，无需备份。")
                return
            try:
                backup = create_backup(path)
            except IniError as exc:
                messagebox.showerror("备份失败", str(exc))
                return
            messagebox.showinfo("备份", f"已创建备份：\n{backup}")

        def _on_launch(self) -> None:
            directory = Path(self.dir_var.get() or ".")
            info = detect_install(directory)
            executable = info.executable
            if executable is None:
                messagebox.showerror("启动", f"未在 {directory} 找到 totk.exe 或 totk。")
                return
            try:
                subprocess.Popen([str(executable)], cwd=str(directory))
            except OSError as exc:
                messagebox.showerror("启动失败", str(exc))
                return
            self.status_var.set(f"已启动：{executable}")

        def _on_refresh_log(self) -> None:
            directory = Path(self.dir_var.get() or ".")
            candidates = [
                directory / "totk.log",
                directory / "log.txt",
                *sorted(directory.glob("*.log")),
            ]
            path = next((candidate for candidate in candidates if candidate.exists()), None)
            self.log_text.delete("1.0", "end")
            if path is None:
                self.log_text.insert("1.0", f"未在 {directory} 找到日志文件。")
                return
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                self.log_text.insert("1.0", f"读取日志失败：{exc}")
                return
            self.log_text.insert("1.0", f"日志：{path}（共 {len(lines)} 行）\n\n" + "\n".join(lines[-500:]))

        def _on_close(self) -> None:
            if self._is_dirty():
                answer = messagebox.askyesnocancel(
                    "未保存的修改", "有未保存的修改，关闭前保存吗？"
                )
                if answer is None:
                    return
                if answer:
                    self._on_save()
                    if self._is_dirty():
                        return
            self.root.destroy()

        def run(self) -> None:
            self.root.mainloop()

    try:
        app = Application()
    except tk.TclError as exc:  # 有 tkinter 但没有可用显示（例如无头服务器）
        print(
            f"无法创建窗口：{exc}\n请在带图形显示的环境运行；无显示环境请使用 CLI。",
            file=sys.stderr,
        )
        return 1
    app.run()
    return 0



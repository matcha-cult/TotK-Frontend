"""图形界面入口（M4）：tkinter 窗口的探测与启动。

设计约定（见 ``docs/design.md`` 第 9 节与第 17 节）：

- ``tkinter`` **只在真正打开窗口时导入**；无 tkinter 时打印明确提示并建议 CLI，进程不崩溃；
- 窗口实现放在 :mod:`totk_frontend.gui_app`，本模块保持无 GUI 依赖，可无头测试；
- 状态层在 :mod:`totk_frontend.session`，保存走 :func:`totk_frontend.ini.write_ini`
  （备份、原子替换、回读校验、失败回滚），校验/预设/诊断复用核心库，与 CLI 结果一致。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .install import detect_version, find_install

__all__ = ["NO_TK_MESSAGE", "tkinter_available", "main"]

NO_TK_MESSAGE = """本机没有可用的 tkinter，图形界面无法启动。

核心库与命令行仍然可用，例如：
  python -m totk_frontend doctor --dir <安装目录>
  python -m totk_frontend list --dir <安装目录>

Windows 上安装官方 python.org 的 Python（安装时保留 tcl/tk 组件）即可使用图形界面。
"""


def tkinter_available() -> bool:
    """探测当前解释器是否带 tkinter（只探测，不创建窗口）。"""
    try:
        import tkinter  # noqa: F401  仅在函数内导入
    except ImportError:
        return False
    return True


def _initial_directory(args: argparse.Namespace) -> Path:
    if args.ini is not None:
        return Path(args.ini).parent
    if args.dir is not None:
        return Path(args.dir)
    found = find_install(Path.cwd())
    return found if found is not None else Path.cwd()


def _resolve_version(args: argparse.Namespace, directory: Path) -> str | None:
    if args.version:
        return args.version
    return detect_version(directory).version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="totk-frontend-gui",
        description="TotK Frontend 图形界面（TotK Recomp 的启动器与配置前台）",
    )
    parser.add_argument("--dir", type=Path, metavar="目录", help="TotK Recomp 安装目录")
    parser.add_argument("--ini", type=Path, metavar="文件", help="直接指定 totk.ini 路径")
    parser.add_argument("--version", metavar="版本", help="TotK Recomp 版本（如 1.4.3）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        import tkinter as tk
    except ImportError:
        print(NO_TK_MESSAGE, file=sys.stderr)
        return 1
    from . import gui_app

    return gui_app.run(tk, args)


if __name__ == "__main__":  # pragma: no cover - 模块入口
    raise SystemExit(main())

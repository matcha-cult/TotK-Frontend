"""TotK Frontend 命令行入口（M3）。

用法：``python -m totk_frontend <命令> [参数]``。不依赖 GUI，可在无游戏的机器上运行。

命令：``detect / list / get / set / unset / preset / apply / backup / restore /
doctor / launch / log / version``。退出码约定见 ``docs/design.md`` 第 15 节：

- ``0``：成功；
- ``1``：用户可修正的错误（文件缺失、键值非法、诊断发现错误等）；
- ``2``：命令行用法错误（由 ``argparse`` 返回）。

所有写操作都走 :func:`totk_frontend.ini.write_ini`（备份、原子替换、回读校验、失败回滚）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .doctor import diagnose, format_report
from .ini import IniDocument, IniError, create_backup, read_ini, write_ini
from .install import ALL_MARKERS, detect_install, find_install
from .presets import PRESETS, apply_preset, format_plan, get_preset, plan_preset
from .settings import SECTION_ORDER, SETTINGS, get_setting
from .validate import SEVERITY_LABELS, Severity, validate_value

__all__ = ["EXIT_OK", "EXIT_USER_ERROR", "EXIT_USAGE", "CliError", "build_parser", "main"]

EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_USAGE = 2


class CliError(Exception):
    """可直接展示给用户的命令行错误。"""


# ---------------------------------------------------------------------- 公共辅助


def _add_target_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        type=Path,
        metavar="目录",
        help="TotK Recomp 安装目录（默认从当前目录向上自动探测）",
    )
    parser.add_argument(
        "--ini",
        type=Path,
        metavar="文件",
        help="直接指定 totk.ini 路径（优先于 --dir）",
    )


def _directory(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "dir", None)
    if explicit is not None:
        directory = Path(explicit)
    else:
        found = find_install(Path.cwd())
        if found is None:
            raise CliError("未检测到 TotK Recomp 安装目录；请用 --dir 指定。")
        directory = found
    return directory


def _ini_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "ini", None)
    if explicit is not None:
        return Path(explicit)
    return _directory(args) / "totk.ini"


def _load_document(args: argparse.Namespace, *, required: bool) -> IniDocument:
    path = _ini_path(args)
    if path.exists():
        return read_ini(path)
    if required:
        raise CliError(
            f"未找到 {path}；请用 --dir/--ini 指定安装目录，或先运行 detect。"
        )
    return IniDocument.from_text("", source=str(path))


def _set_setting(document: IniDocument, key: str, value: str, section: str) -> None:
    if document.get(key) is not None:
        document.set(key, value)
    else:
        document.set(key, value, section)


def _print_issue(issue, *, stream=None) -> None:  # noqa: ANN001 - Issue 类型由 validate 提供
    stream = stream or sys.stdout
    print(f"[{SEVERITY_LABELS[issue.severity]}] {issue.message}", file=stream)
    if issue.suggestion:
        print(f"  建议：{issue.suggestion}", file=stream)


def _print_unknown_key(key: str) -> None:
    print(
        f"错误：未知键：{key}（不在设置注册表中；未知键会原样保留但不可编辑）。",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------- 命令


def cmd_detect(args: argparse.Namespace) -> int:
    explicit = getattr(args, "dir", None)
    directory = Path(explicit) if explicit is not None else find_install(Path.cwd())
    if directory is None:
        print("未检测到 TotK Recomp 安装目录。")
        print("请用 --dir 指定包含 totk.exe/totk、totk.ini、exefs/、romfs/ 的目录。")
        return EXIT_USER_ERROR
    info = detect_install(directory)
    print(f"安装目录：{info.directory}")
    for name, exists in info.markers:
        print(f"  {'存在' if exists else '缺失'}  {name}")
    if info.looks_like_install:
        print("结果：检测通过。")
        return EXIT_OK
    print("结果：缺少必要标记：" + "、".join(info.missing))
    return EXIT_USER_ERROR


def cmd_list(args: argparse.Namespace) -> int:
    path = _ini_path(args)
    document = _load_document(args, required=False)
    if not path.exists():
        print(f"提示：{path} 不存在，以下为默认值。")
    section = args.section.strip().lower() if args.section else None
    for setting in SETTINGS:
        if setting.is_pattern:
            continue
        if section is not None and setting.section != section:
            continue
        current = document.get(setting.key)
        value = current if current is not None else setting.default
        source = "文件" if current is not None else "默认"
        shown = value if value is not None else "（未设置）"
        print(
            f"[{setting.section}] {setting.key} = {shown}  "
            f"({source}，{setting.effect_label}，{setting.priority.value})"
        )
    if section is not None and section not in SECTION_ORDER:
        print(
            f"提示：未知节 {section!r}；可用节：{'、'.join(SECTION_ORDER)}",
            file=sys.stderr,
        )
        return EXIT_USER_ERROR
    return EXIT_OK


def cmd_get(args: argparse.Namespace) -> int:
    setting = get_setting(args.key)
    if setting is None:
        _print_unknown_key(args.key)
        return EXIT_USER_ERROR
    document = _load_document(args, required=False)
    value = document.get(setting.key)
    if value is None:
        value = setting.default
    print(value if value is not None else "")
    return EXIT_OK


def cmd_set(args: argparse.Namespace) -> int:
    setting = get_setting(args.key)
    if setting is None:
        _print_unknown_key(args.key)
        return EXIT_USER_ERROR
    issues = [
        issue
        for issue in validate_value(setting, args.value, key=setting.key)
        if issue.severity is Severity.ERROR
    ]
    if issues:
        for issue in issues:
            _print_issue(issue, stream=sys.stderr)
        return EXIT_USER_ERROR
    document = _load_document(args, required=False)
    _set_setting(document, setting.key, args.value.strip(), setting.section)
    path = _ini_path(args)
    result = write_ini(path, document)
    if result.backup_path is not None:
        print(f"备份：{result.backup_path}")
    if result.changed:
        print(f"已设置 {setting.key} = {args.value.strip()}（{path}）")
    else:
        print("值未变化，未写盘。")
    return EXIT_OK


def cmd_unset(args: argparse.Namespace) -> int:
    setting = get_setting(args.key)
    if setting is None:
        _print_unknown_key(args.key)
        return EXIT_USER_ERROR
    document = _load_document(args, required=True)
    removed = document.unset(setting.key)
    if removed == 0:
        print(f"{setting.key} 没有激活行，无需改动。")
        return EXIT_OK
    path = _ini_path(args)
    result = write_ini(path, document)
    if result.backup_path is not None:
        print(f"备份：{result.backup_path}")
    print(f"已恢复默认：{setting.key}（移除 {removed} 行激活设置，{path}）")
    return EXIT_OK


def cmd_preset(args: argparse.Namespace) -> int:
    print("可用预设：")
    for preset in PRESETS:
        print(f"  {preset.name:<12} {preset.label}：{preset.description}")
    return EXIT_OK


def cmd_apply(args: argparse.Namespace) -> int:
    preset = get_preset(args.name)
    if preset is None:
        print(
            f"未知预设：{args.name}；可用：{'、'.join(item.name for item in PRESETS)}",
            file=sys.stderr,
        )
        return EXIT_USER_ERROR
    document = _load_document(args, required=False)
    path = _ini_path(args)
    if args.dry_run:
        plan = plan_preset(document, preset, version=args.version)
        print(format_plan(plan))
        print("（dry-run：未写入任何文件）")
        return EXIT_OK
    plan = apply_preset(document, preset, version=args.version)
    print(format_plan(plan))
    if not plan.changes:
        print("已是目标值，未写盘。")
        return EXIT_OK
    result = write_ini(path, document)
    if result.backup_path is not None:
        print(f"备份：{result.backup_path}")
    print(f"已应用预设 {preset.name}（{len(plan.changes)} 项，{path}）")
    return EXIT_OK


def cmd_backup(args: argparse.Namespace) -> int:
    path = _ini_path(args)
    if not path.exists():
        raise CliError(f"未找到 {path}；请用 --dir/--ini 指定安装目录。")
    backup = create_backup(path)
    print(backup)
    return EXIT_OK


def _restore_target(backup: Path, args: argparse.Namespace) -> Path:
    explicit = getattr(args, "ini", None)
    if explicit is not None:
        return Path(explicit)
    explicit_dir = getattr(args, "dir", None)
    if explicit_dir is not None:
        return Path(explicit_dir) / "totk.ini"
    if ".bak-" in backup.name:
        return backup.with_name(backup.name.split(".bak-")[0])
    return backup.with_name("totk.ini")


def cmd_restore(args: argparse.Namespace) -> int:
    backup = Path(args.backup)
    if not backup.exists():
        raise CliError(f"备份文件不存在：{backup}")
    try:
        document = IniDocument.from_path(backup)
    except IniError as exc:
        raise CliError(f"备份文件无法解析：{exc}") from exc
    target = _restore_target(backup, args)
    result = write_ini(target, document)
    if result.backup_path is not None:
        print(f"恢复前备份：{result.backup_path}")
    if result.changed:
        print(f"已从 {backup} 恢复到 {target}")
    else:
        print("目标文件内容与备份相同，未写盘。")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    path = _ini_path(args)
    document = _load_document(args, required=False)
    if not path.exists():
        print(f"提示：{path} 不存在，按默认值诊断。")
    report = diagnose(document, version=args.version)
    print(format_report(report))
    return EXIT_OK if report.ok else EXIT_USER_ERROR


def cmd_launch(args: argparse.Namespace) -> int:
    directory = _directory(args)
    info = detect_install(directory)
    executable = info.executable
    if executable is None:
        raise CliError(f"未在 {directory} 找到 totk.exe 或 totk。")
    command = [str(executable), *args.extra]
    if args.dry_run:
        print("将运行：" + " ".join(command))
        print(f"工作目录：{directory}")
        return EXIT_OK
    try:
        completed = subprocess.run(command, cwd=str(directory), check=False)
    except OSError as exc:
        raise CliError(f"启动失败：{exc}") from exc
    print(f"游戏退出码：{completed.returncode}")
    return EXIT_OK


def cmd_log(args: argparse.Namespace) -> int:
    if args.tail < 0:
        raise CliError("--tail 必须是非负整数。")
    if args.path is not None:
        path = Path(args.path)
    else:
        directory = _directory(args)
        candidates = [
            directory / "totk.log",
            directory / "log.txt",
            *sorted(directory.glob("*.log")),
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        if path is None:
            raise CliError(f"未在 {directory} 找到日志文件；请用 --path 指定。")
    if not path.exists():
        raise CliError(f"日志文件不存在：{path}")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CliError(f"读取日志失败：{exc}") from exc
    lines = text.splitlines()
    shown = lines[-args.tail :] if args.tail > 0 else []
    print(f"日志：{path}（共 {len(lines)} 行，显示最后 {len(shown)} 行）")
    for line in shown:
        print(line)
    return EXIT_OK


def cmd_version(args: argparse.Namespace) -> int:
    print(f"totk-frontend {__version__}")
    print(f"设置注册表：{len(SETTINGS)} 项，{len(SECTION_ORDER)} 节")
    restricted = [setting.key for setting in SETTINGS if setting.versions]
    print(f"带版本限制的键：{len(restricted)} 个" + (f"（{'、'.join(restricted)}）" if restricted else ""))
    return EXIT_OK


# ---------------------------------------------------------------------- 解析器


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="totk-frontend",
        description="TotK Frontend：TotK Recomp 的启动器与配置前台（CLI）",
    )
    parser.add_argument(
        "--version", action="version", version=f"totk-frontend {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="命令")

    detect = subparsers.add_parser("detect", help="检测 TotK Recomp 安装目录")
    detect.add_argument("--dir", type=Path, metavar="目录", help="要检测的目录")
    detect.set_defaults(handler=cmd_detect)

    list_parser = subparsers.add_parser("list", help="列出设置项与生效值")
    _add_target_arguments(list_parser)
    list_parser.add_argument("--section", metavar="节", help="只列出某个节（如 display）")
    list_parser.set_defaults(handler=cmd_list)

    get_parser = subparsers.add_parser("get", help="读取一个设置项的生效值")
    _add_target_arguments(get_parser)
    get_parser.add_argument("key", metavar="键")
    get_parser.set_defaults(handler=cmd_get)

    set_parser = subparsers.add_parser("set", help="写入一个设置项（备份、原子写、回读校验）")
    _add_target_arguments(set_parser)
    set_parser.add_argument("key", metavar="键")
    set_parser.add_argument("value", metavar="值")
    set_parser.set_defaults(handler=cmd_set)

    unset_parser = subparsers.add_parser("unset", help="移除设置项的激活行（恢复默认）")
    _add_target_arguments(unset_parser)
    unset_parser.add_argument("key", metavar="键")
    unset_parser.set_defaults(handler=cmd_unset)

    preset_parser = subparsers.add_parser("preset", help="列出可用预设")
    preset_parser.set_defaults(handler=cmd_preset)

    apply_parser = subparsers.add_parser("apply", help="应用预设（只写差异集）")
    _add_target_arguments(apply_parser)
    apply_parser.add_argument("name", metavar="预设")
    apply_parser.add_argument("--dry-run", action="store_true", help="只预览差异，不写盘")
    apply_parser.add_argument("--version", metavar="版本", help="TotK Recomp 版本（如 1.4.3）")
    apply_parser.set_defaults(handler=cmd_apply)

    backup_parser = subparsers.add_parser("backup", help="为 totk.ini 创建备份")
    _add_target_arguments(backup_parser)
    backup_parser.set_defaults(handler=cmd_backup)

    restore_parser = subparsers.add_parser("restore", help="用备份文件恢复 totk.ini")
    _add_target_arguments(restore_parser)
    restore_parser.add_argument("backup", metavar="备份文件")
    restore_parser.set_defaults(handler=cmd_restore)

    doctor_parser = subparsers.add_parser("doctor", help="诊断配置并输出可操作建议")
    _add_target_arguments(doctor_parser)
    doctor_parser.add_argument("--version", metavar="版本", help="TotK Recomp 版本（如 1.4.3）")
    doctor_parser.set_defaults(handler=cmd_doctor)

    launch_parser = subparsers.add_parser("launch", help="启动 totk.exe/totk")
    launch_parser.add_argument("--dir", type=Path, metavar="目录", help="TotK Recomp 安装目录")
    launch_parser.add_argument("--dry-run", action="store_true", help="只打印将执行的命令，不启动")
    launch_parser.add_argument("extra", nargs=argparse.REMAINDER, help="原样传给游戏的参数")
    launch_parser.set_defaults(handler=cmd_launch)

    log_parser = subparsers.add_parser("log", help="查看游戏日志尾部")
    log_parser.add_argument("--dir", type=Path, metavar="目录", help="TotK Recomp 安装目录")
    log_parser.add_argument("--path", type=Path, metavar="文件", help="直接指定日志文件")
    log_parser.add_argument("--tail", type=int, default=80, metavar="行数", help="显示最后 N 行（默认 80）")
    log_parser.set_defaults(handler=cmd_log)

    version_parser = subparsers.add_parser("version", help="显示版本与注册表信息")
    version_parser.set_defaults(handler=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CliError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    except IniError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_USER_ERROR


if __name__ == "__main__":  # pragma: no cover - 模块入口
    raise SystemExit(main())

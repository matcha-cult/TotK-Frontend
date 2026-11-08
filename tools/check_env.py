"""环境自检：确认这台机器能否运行与验证 TotK Frontend。

只使用标准库；不改动任何文件。适用于 Windows（``py -3 tools/check_env.py``）
与 Linux/macOS（``python3 tools/check_env.py``）。

检查项：

1. Python 版本 ≥ 3.11；
2. ``tkinter`` 是否可用（M4 GUI 与实机验收需要；无它时核心库与 CLI 仍可用）；
3. 仓库布局（``src/totk_frontend``、``tests``）；
4. 可选：运行全部单元测试（``--run-tests``）。
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)


def check_python() -> tuple[bool, str]:
    version = sys.version_info
    ok = version[:2] >= MIN_PYTHON
    detail = f"Python {version.major}.{version.minor}.{version.micro}（需要 ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]}）"
    return ok, detail


def check_tkinter() -> tuple[bool, str]:
    try:
        import tkinter  # noqa: F401  仅探测可用性
    except ImportError:
        return False, "tkinter 不可用：核心库与 CLI 可正常使用，但 M4 的 GUI 无法在本机运行。"
    version = getattr(tkinter, "TkVersion", "未知")
    return True, f"tkinter 可用（TkVersion {version}）"


def check_layout() -> tuple[bool, str]:
    required = [ROOT / "src" / "totk_frontend", ROOT / "tests"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_dir()]
    if missing:
        return False, "仓库布局不完整，缺少：" + "、".join(missing)
    return True, "仓库布局正常（src/totk_frontend、tests 均存在）"


def run_tests() -> tuple[bool, str]:
    import unittest

    loader = unittest.TestLoader()
    try:
        suite = loader.discover(str(ROOT / "tests"))
    except ImportError as exc:
        return False, f"无法发现测试：{exc}"
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    summary = f"测试：运行 {result.testsRun}，失败 {len(result.failures)}，错误 {len(result.errors)}，跳过 {len(result.skipped)}"
    return result.wasSuccessful(), summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查运行与验证 TotK Frontend 所需的环境")
    parser.add_argument("--run-tests", action="store_true", help="同时运行全部单元测试")
    args = parser.parse_args(argv)

    print(f"平台：{platform.platform()}")
    print(f"解释器：{sys.executable}")
    checks = [
        ("Python 版本", check_python()),
        ("tkinter", check_tkinter()),
        ("仓库布局", check_layout()),
    ]
    if args.run_tests:
        checks.append(("单元测试", run_tests()))

    failed = 0
    for label, (ok, detail) in checks:
        print(f"[{'通过' if ok else '未通过'}] {label}：{detail}")
        if not ok:
            failed += 1
    if failed:
        # tkinter 缺失只影响 GUI；若只有它未通过，提示但仍以非 0 退出，便于脚本判断。
        print("")
        print("有检查项未通过；请按上面的提示处理后再运行 GUI 或发布构建。")
        return 1
    print("")
    print("环境检查全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

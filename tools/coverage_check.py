"""统计 ``src/totk_frontend`` 的语句覆盖率（仅标准库）。

覆盖率阈值在 M1 开始时确定（见 ``docs/design.md`` 第 12 节 I8）：语句覆盖率 ≥ 90%。
"语句"由 AST 统计：每个 ``ast.stmt`` 计一条（模块/类/函数文档字符串、``if __name__ == "__main__"``
块、标记 ``# pragma: no cover`` 的语句除外）；多行语句只要有一行被执行即视为已覆盖。
"已执行行"由 :func:`sys.settrace` 在运行 ``tests/`` 时收集，因此测的是无头测试的真实覆盖；
测试未全部通过时本工具同样返回非 0，避免“覆盖率正常但测试失败”被误判为通过。
依赖显示环境的窗口模块（``EXCLUDED_FILES``，目前是 ``gui_app.py``）不计入阈值，
其入口、探测与回退提示在 ``gui.py`` 中仍被统计。

用法::

    python tools/coverage_check.py
    python tools/coverage_check.py --min 95 --verbose
    python tools/coverage_check.py --show-missing
"""

from __future__ import annotations

import argparse
import ast
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "totk_frontend"
TESTS_DIR = ROOT / "tests"

#: 依赖显示环境、无法在无头环境执行的模块（见 docs/design.md 第 12 节 I8）。
#: 这些模块的入口与回退路径在 ``gui.py`` 中，仍计入覆盖率。
EXCLUDED_FILES: frozenset[str] = frozenset({"gui_app.py"})


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def executable_statements(path: Path) -> list[tuple[int, int]]:
    """返回文件中计入覆盖率的语句 ``(起始行, 结束行)``。"""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    source_lines = source.splitlines()

    excluded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_main_guard(node):
            for child in ast.walk(node):
                excluded.add(id(child))

    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or _is_docstring(node) or id(node) in excluded:
            continue
        if 1 <= node.lineno <= len(source_lines) and "# pragma: no cover" in source_lines[node.lineno - 1]:
            continue
        spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return spans


class _LineTracer:
    """收集 ``src/`` 下各文件执行过的行号。"""

    def __init__(self) -> None:
        self.executed: set[tuple[Path, int]] = set()
        self._previous_trace = None
        self._previous_thread_trace = None

    def _trace(self, frame, event, arg):  # noqa: ANN001 - 与 sys.settrace 签名一致
        if event == "line":
            filename = frame.f_code.co_filename
            if filename.startswith(str(SRC_DIR)):
                self.executed.add((Path(filename).resolve(), frame.f_lineno))
        return self._trace

    def start(self) -> None:
        self._previous_trace = sys.gettrace()
        self._previous_thread_trace = threading.gettrace()
        sys.settrace(self._trace)
        threading.settrace(self._trace)

    def stop(self) -> None:
        sys.settrace(self._previous_trace)
        threading.settrace(self._previous_thread_trace)


def run_tests() -> unittest.TestResult:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR))
    runner = unittest.TextTestRunner(verbosity=0, stream=sys.stderr, buffer=True)
    return runner.run(suite)


def collect_coverage() -> tuple[dict[Path, list[tuple[int, int]]], set[tuple[Path, int]], bool]:
    tracer = _LineTracer()
    tracer.start()
    try:
        result = run_tests()
    finally:
        tracer.stop()
    spans = {
        path: executable_statements(path)
        for path in sorted(PACKAGE_DIR.glob("*.py"))
        if path.name not in EXCLUDED_FILES
    }
    return spans, tracer.executed, result.wasSuccessful()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统计 totk_frontend 的语句覆盖率")
    parser.add_argument("--min", type=float, default=90.0, help="覆盖率阈值（百分比，默认 90）")
    parser.add_argument("--verbose", action="store_true", help="逐文件输出覆盖率")
    parser.add_argument("--show-missing", action="store_true", help="输出未覆盖语句的起始行号")
    args = parser.parse_args(argv)

    statements, executed, tests_ok = collect_coverage()

    total_covered = 0
    total_statements = 0
    rows: list[tuple[Path, list[tuple[int, int]], list[int]]] = []
    for path, spans in statements.items():
        hit_lines = {line for (filename, line) in executed if filename == path}
        covered: list[int] = []
        missing: list[int] = []
        for start, end in spans:
            if any(line in hit_lines for line in range(start, end + 1)):
                covered.append(start)
            else:
                missing.append(start)
        total_statements += len(spans)
        total_covered += len(covered)
        rows.append((path, spans, missing))

    excluded = sorted(EXCLUDED_FILES)
    if args.verbose and excluded:
        print(f"（按约定排除依赖显示环境的模块：{'、'.join(excluded)}）")
    if args.verbose or args.show_missing:
        width = max((len(path.name) for path, _, _ in rows), default=10)
        for path, spans, missing in rows:
            percent = (len(spans) - len(missing)) / len(spans) * 100.0 if spans else 100.0
            print(f"{path.name:<{width}}  {len(spans) - len(missing):>4}/{len(spans):<4}  {percent:6.2f}%")
            if args.show_missing and missing:
                print(f"{'':<{width}}  未覆盖语句起始行：{sorted(missing)}")

    percent = (total_covered / total_statements * 100.0) if total_statements else 100.0
    print(
        f"语句覆盖率：{total_covered}/{total_statements} = {percent:.2f}%"
        f"（阈值 {args.min:.2f}%）"
    )
    if not tests_ok:
        print("测试未全部通过：覆盖率不能作为通过依据。", file=sys.stderr)
        return 1
    if percent < args.min:
        print("覆盖率低于阈值。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

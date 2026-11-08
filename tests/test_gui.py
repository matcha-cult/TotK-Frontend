"""GUI 模块的无头测试（M4）。

重点验证“没有 tkinter 时不崩溃、给出提示并建议 CLI”；窗口本身的实机验收
需要在带 tkinter 的桌面环境（Windows）由使用者执行。
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from totk_frontend import gui


class TkinterDetectionTest(unittest.TestCase):
    def test_available_returns_bool(self) -> None:
        self.assertIsInstance(gui.tkinter_available(), bool)

    def test_import_does_not_require_tkinter(self) -> None:
        # 能导入本模块即说明模块顶层没有强制导入 tkinter。
        self.assertTrue(hasattr(gui, "main"))
        self.assertTrue(gui.NO_TK_MESSAGE.strip())

    def test_message_points_to_cli(self) -> None:
        self.assertIn("命令行", gui.NO_TK_MESSAGE)
        self.assertIn("totk_frontend", gui.NO_TK_MESSAGE)
        self.assertNotIn("http://", gui.NO_TK_MESSAGE)


class GuiAppModuleTest(unittest.TestCase):
    def test_gui_app_imports_without_tkinter(self) -> None:
        from totk_frontend import gui_app

        self.assertTrue(callable(gui_app.run))

    def test_build_parser(self) -> None:
        parser = gui.build_parser()
        self.assertIn("图形界面", parser.description or "")
        args = parser.parse_args(["--dir", "x", "--version", "1.4.3"])
        self.assertEqual(args.version, "1.4.3")
        self.assertFalse(args.smoke)

    def test_smoke_flag(self) -> None:
        args = gui.build_parser().parse_args(["--smoke"])
        self.assertTrue(args.smoke)

    def test_smoke_summary_format(self) -> None:
        from totk_frontend import gui_app

        class FakeRoot:
            def title(self) -> str:
                return "TotK Frontend"

        class FakeNotebook:
            def tabs(self) -> tuple:
                return ("a", "b")

        class FakeApp:
            root = FakeRoot()
            notebook = FakeNotebook()
            vars = {"k": 1}
            status_var = type("S", (), {"get": lambda _self: "就绪"})()

        summary = gui_app._smoke_summary(FakeApp())
        self.assertIn("页签=2", summary)
        self.assertIn("设置控件=1", summary)
        self.assertIn("就绪", summary)

    def test_initial_directory_prefers_ini_parent(self) -> None:
        parser = gui.build_parser()
        args = parser.parse_args(["--ini", "somewhere/totk.ini"])
        self.assertEqual(gui._initial_directory(args).name, "somewhere")

    def test_initial_directory_uses_dir(self) -> None:
        parser = gui.build_parser()
        args = parser.parse_args(["--dir", "somewhere"])
        self.assertEqual(str(gui._initial_directory(args)), "somewhere")

    def test_resolve_version_prefers_explicit(self) -> None:
        parser = gui.build_parser()
        args = parser.parse_args(["--version", "1.2.1"])
        self.assertEqual(gui._resolve_version(args, __import__("pathlib").Path(".")), "1.2.1")


class FakeTkinterTest(unittest.TestCase):
    """用假的 tkinter 模块覆盖“有 tkinter”的代码路径（不创建真实窗口）。"""

    def setUp(self) -> None:
        self.fake = types.ModuleType("tkinter")
        self.fake.TkVersion = 8.6

    def test_tkinter_available_true(self) -> None:
        with mock.patch.dict(sys.modules, {"tkinter": self.fake}):
            self.assertTrue(gui.tkinter_available())

    def test_main_with_tkinter_delegates_to_gui_app(self) -> None:
        with mock.patch.dict(sys.modules, {"tkinter": self.fake}):
            with mock.patch("totk_frontend.gui_app.run", return_value=0) as run:
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = gui.main(["--dir", "somewhere"])
        self.assertEqual(code, 0)
        run.assert_called_once()
        _tk_arg, args_arg = run.call_args.args[0], run.call_args.args[1]
        self.assertIs(_tk_arg, self.fake)
        self.assertEqual(str(args_arg.dir), "somewhere")
        self.assertIn("Tk 8.6", stderr.getvalue())

    def test_initial_directory_falls_back_to_cwd_with_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "TotK Recomp"
            install.mkdir()
            (install / "totk.exe").write_text("", encoding="utf-8")
            (install / "totk.ini").write_text("", encoding="utf-8")
            nested = install / "mods"
            nested.mkdir()
            previous = Path.cwd()
            try:
                import os

                os.chdir(nested)
                parser = gui.build_parser()
                args = parser.parse_args([])
                self.assertEqual(gui._initial_directory(args), install)
            finally:
                import os

                os.chdir(previous)

    def test_initial_directory_falls_back_to_cwd_without_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                import os

                os.chdir(directory)
                parser = gui.build_parser()
                args = parser.parse_args([])
                self.assertEqual(gui._initial_directory(args), Path.cwd())
            finally:
                import os

                os.chdir(previous)

    def test_resolve_version_detects_from_install_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "totk-install.json").write_text('{"version": "1.2.1"}', encoding="utf-8")
            parser = gui.build_parser()
            args = parser.parse_args([])
            self.assertEqual(gui._resolve_version(args, root), "1.2.1")

    def test_resolve_version_none_without_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parser = gui.build_parser()
            args = parser.parse_args([])
            self.assertIsNone(gui._resolve_version(args, Path(directory)))


class NoTkinterFallbackTest(unittest.TestCase):
    @unittest.skipIf(gui.tkinter_available(), "本机有 tkinter，启动窗口会阻塞测试")
    def test_main_without_tkinter_returns_error(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = gui.main([])
        self.assertEqual(code, 1)
        self.assertIn("tkinter", stderr.getvalue())
        self.assertIn("命令行", stderr.getvalue())

    def test_help(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                gui.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("图形界面", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

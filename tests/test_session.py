"""GUI 无头状态层测试（M4）：编辑会话的读写、暂存、保存、预设与回滚。"""

from __future__ import annotations

import _bootstrap  # noqa: F401  确保可以导入 src/totk_frontend

import tempfile
import unittest
from pathlib import Path

from totk_frontend.ini import IniDocument
from totk_frontend.session import EditingSession, PendingChange
from totk_frontend.validate import Severity

DEFAULT_INI = """# 手写合成样本
[frame rate]
fps_limit = 30
realtime = 1

[audio]
volume = 100
"""


class SessionBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.path = self.root / "totk.ini"
        self.path.write_text(DEFAULT_INI, encoding="utf-8")

    def session(self, *, version: str | None = None) -> EditingSession:
        return EditingSession.load(self.path, version=version)


class LoadAndReadTest(SessionBase):
    def test_load_existing(self) -> None:
        session = self.session()
        self.assertTrue(session.exists)
        self.assertFalse(session.dirty)
        self.assertEqual(session.value("fps_limit"), "30")
        self.assertEqual(session.value("volume"), "100")

    def test_missing_file_starts_empty(self) -> None:
        session = EditingSession.load(self.root / "missing.ini")
        self.assertFalse(session.exists)
        self.assertEqual(session.value("fps_limit"), "60")
        self.assertFalse(session.dirty)

    def test_unknown_key_is_rejected(self) -> None:
        session = self.session()
        with self.assertRaises(ValueError):
            session.set("not_a_key", "1")
        with self.assertRaises(ValueError):
            session.unset("not_a_key")

    def test_readonly_pattern_key_is_rejected(self) -> None:
        session = self.session()
        with self.assertRaises(ValueError):
            session.set("bind_A", "pad:east")

    def test_set_requires_string(self) -> None:
        session = self.session()
        with self.assertRaises(TypeError):
            session.set("volume", 50)  # type: ignore[arg-type]


class PendingEditTest(SessionBase):
    def test_set_only_touches_pending(self) -> None:
        session = self.session()
        before = self.path.read_bytes()
        issues = session.set("volume", "80")
        self.assertEqual(issues, [])
        self.assertTrue(session.dirty)
        self.assertTrue(session.is_modified("volume"))
        self.assertEqual(session.value("volume"), "80")
        self.assertEqual(session.document.get("volume"), "100")
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_value_is_reported_but_recorded(self) -> None:
        session = self.session()
        issues = session.set("volume", "1000")
        self.assertEqual([issue.severity for issue in issues], [Severity.ERROR])
        self.assertTrue(session.is_modified("volume"))

    def test_unset_marks_default(self) -> None:
        session = self.session()
        session.unset("volume")
        self.assertIsNone(session.value("volume"))
        self.assertTrue(session.is_modified("volume"))
        self.assertEqual(session.changed_count(), 1)

    def test_discard_pending(self) -> None:
        session = self.session()
        session.set("volume", "80")
        session.discard_pending()
        self.assertFalse(session.dirty)
        self.assertEqual(session.value("volume"), "100")

    def test_staged_document_is_isolated(self) -> None:
        session = self.session()
        session.set("volume", "80")
        staged = session.staged_document()
        self.assertEqual(staged.get("volume"), "80")
        self.assertEqual(session.document.get("volume"), "100")
        self.assertEqual(staged.source, self.path.as_posix())
        self.assertEqual(self.path.read_text(encoding="utf-8"), DEFAULT_INI)

    def test_staged_document_keeps_untouched_bytes(self) -> None:
        session = self.session()
        session.set("volume", "80")
        staged = session.staged_document().render()
        self.assertEqual(
            staged,
            DEFAULT_INI.replace("volume = 100", "volume = 80"),
        )

    def test_staged_document_inserts_missing_key_in_section(self) -> None:
        session = self.session()
        session.set("sharpness", "50")
        staged = session.staged_document()
        self.assertEqual(staged.get("sharpness"), "50")
        self.assertIn("display", staged.sections())

    def test_commit_applies_and_clears(self) -> None:
        session = self.session()
        session.set("volume", "80")
        applied = session.commit()
        self.assertEqual(len(applied), 1)
        self.assertFalse(session.dirty)
        self.assertEqual(session.document.get("volume"), "80")
        self.assertEqual(self.path.read_text(encoding="utf-8"), DEFAULT_INI)

    def test_commit_without_pending(self) -> None:
        session = self.session()
        self.assertEqual(session.commit(), ())

    def test_pending_dataclass_fields(self) -> None:
        session = self.session()
        session.set("volume", "80")
        pending = session.pending[0]
        self.assertIsInstance(pending, PendingChange)
        self.assertEqual(pending.key, "volume")
        self.assertEqual(pending.section, "audio")
        self.assertEqual(pending.old_value, "100")
        self.assertEqual(pending.new_value, "80")
        self.assertFalse(pending.is_unset)
        session.unset("volume")
        self.assertTrue(session.pending[0].is_unset)


class ValidationTest(SessionBase):
    def test_issues_see_pending(self) -> None:
        session = self.session()
        session.set("free_cores", "1")
        codes = [issue.code for issue in session.issues()]
        self.assertIn("rule.free_cores", codes)
        self.assertTrue(session.errors())

    def test_save_rejects_errors(self) -> None:
        session = self.session()
        session.set("free_cores", "1")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            session.save()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(session.dirty)

    def test_version_check_uses_session_version(self) -> None:
        session = self.session(version="1.2.1")
        session.set("fov", "110")
        codes = [issue.code for issue in session.issues()]
        self.assertIn("rule.version_unsupported", codes)


class SaveTest(SessionBase):
    def test_save_writes_backup_and_clears_pending(self) -> None:
        session = self.session()
        session.set("volume", "80")
        applied, backup = session.save()
        self.assertEqual(len(applied), 1)
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(backup.read_bytes(), DEFAULT_INI.encode("utf-8"))
        self.assertFalse(session.dirty)
        self.assertIn("volume = 80", self.path.read_text(encoding="utf-8"))
        self.assertEqual(session.document.get("volume"), "80")

    def test_save_creates_missing_file(self) -> None:
        target = self.root / "new.ini"
        session = EditingSession.load(target)
        session.set("volume", "50")
        _applied, backup = session.save()
        self.assertIsNone(backup)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8").splitlines(), ["[audio]", "volume = 50"])

    def test_save_unset_removes_line(self) -> None:
        session = self.session()
        session.unset("volume")
        session.save()
        self.assertNotIn("volume = 100", self.path.read_text(encoding="utf-8"))

    def test_save_without_changes(self) -> None:
        session = self.session()
        applied, backup = session.save()
        self.assertEqual(applied, ())
        self.assertIsNone(backup)

    def test_reload_discards_pending(self) -> None:
        session = self.session()
        session.set("volume", "80")
        session.reload()
        self.assertFalse(session.dirty)
        self.assertEqual(session.value("volume"), "100")


class DefaultsAndPresetTest(SessionBase):
    def test_restore_defaults_marks_active_keys(self) -> None:
        session = self.session()
        count = session.restore_defaults()
        self.assertEqual(count, 3)  # fps_limit、realtime、volume
        self.assertEqual(session.changed_count(), 3)
        session.save()
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("fps_limit = 30", text)
        self.assertNotIn("volume = 100", text)
        self.assertIn("# 手写合成样本", text)

    def test_restore_defaults_on_empty_file(self) -> None:
        session = EditingSession.load(self.root / "empty.ini")
        self.assertEqual(session.restore_defaults(), 0)

    def test_stage_preset_sets_pending(self) -> None:
        session = self.session()
        plan = session.stage_preset("savage-wind")
        self.assertTrue(plan.changes)
        self.assertTrue(session.dirty)
        self.assertEqual(session.value("prompts"), "pc")
        self.assertEqual(session.value("fps_limit"), "60")
        session.save()
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("prompts = pc", text)
        self.assertIn("fps_limit = 60", text)

    def test_stage_preset_unknown(self) -> None:
        session = self.session()
        with self.assertRaises(ValueError):
            session.stage_preset("no-such-preset")

    def test_plan_preset_sees_pending(self) -> None:
        session = self.session()
        session.set("fps_limit", "60")
        plan = session.plan_preset("savage-wind")
        self.assertNotIn("fps_limit", [change.key for change in plan.changes])

    def test_preset_skipped_on_old_version(self) -> None:
        session = self.session(version="1.2.1")
        plan = session.stage_preset("savage-wind")
        self.assertNotIn("menu_cursor", [change.key for change in plan.changes])


class StatusTest(SessionBase):
    def test_status_without_edits(self) -> None:
        text = self.session().status_text()
        self.assertIn("没有未保存的修改", text)
        self.assertIn("totk.ini", text)

    def test_status_with_edits(self) -> None:
        session = self.session()
        session.set("volume", "80")
        self.assertIn("1 项未保存", session.status_text())

    def test_status_for_missing_file(self) -> None:
        session = EditingSession.load(self.root / "missing.ini")
        self.assertIn("保存时新建", session.status_text())

    def test_status_with_version(self) -> None:
        session = self.session(version="1.4.3")
        self.assertIn("TotK Recomp 1.4.3", session.status_text())


class DocumentIndependenceTest(SessionBase):
    def test_constructor_accepts_document(self) -> None:
        document = IniDocument.from_text("[audio]\nvolume = 10\n")
        session = EditingSession(self.path, document=document)
        self.assertEqual(session.value("volume"), "10")
        self.assertEqual(session.document.get("fps_limit"), None)


if __name__ == "__main__":
    unittest.main()

import errno
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "append_ai_log", Path(__file__).parents[1] / "scripts" / "append_ai_log.py"
)
log = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log)


class FileReplacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.note = self.root / "a-work.md"
        self.daily = self.root / "z-daily.md"
        for path in (self.note, self.daily):
            path.write_text("### ai-log\n- original\n", encoding="utf-8")

    def append(self):
        return log.append_entries(
            self.note, ["new log"], daily_path=self.daily,
            note_link="a-work", timestamp="20261111210000",
        )

    def replace_during_lock(self, replaced, lock_number):
        flock = log.fcntl.flock
        calls = 0

        def intercept(note, operation):
            nonlocal calls
            flock(note, operation)
            calls += 1
            if calls == lock_number:
                replacement = self.root / "replacement.md"
                replacement.write_text("### ai-log\n- current\n", encoding="utf-8")
                replacement.replace(replaced)

        with patch.object(log.fcntl, "flock", side_effect=intercept):
            reference = self.append()
        self.assertIn("- current\n", replaced.read_text())
        self.assertIn("new log", self.note.read_text())
        self.assertIn(reference, self.daily.read_text())

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_append_succeeds_when_note_lock_is_unsupported(self):
        flock = log.fcntl.flock

        def unsupported_for_notes(file, operation):
            if Path(file.name) in (self.note, self.daily):
                raise OSError(errno.ENOSYS, "Lock unavailable")
            return flock(file, operation)

        with patch.object(log.fcntl, "flock", side_effect=unsupported_for_notes):
            reference = self.append()
        self.assertIn("new log", self.note.read_text())
        self.assertIn(reference, self.daily.read_text())

    def test_write_failure_identifies_both_notes(self):
        original_open = Path.open
        daily = self.daily

        class FailingWriter:
            def __init__(self, wrapped):
                self.wrapped = wrapped
            def __enter__(self):
                self.wrapped.__enter__()
                return self
            def __exit__(self, *args):
                return self.wrapped.__exit__(*args)
            def __getattr__(self, name):
                return getattr(self.wrapped, name)
            def write(self, value):
                raise OSError("simulated write error")

        def open_with_failure(path, *args, **kwargs):
            opened = original_open(path, *args, **kwargs)
            if path == daily and args and args[0] == "r+":
                return FailingWriter(opened)
            return opened

        with patch.object(Path, "open", open_with_failure):
            with self.assertRaises(OSError) as error:
                self.append()
        self.assertIn(str(self.note), str(error.exception))
        self.assertIn(str(self.daily), str(error.exception))

    def test_concurrent_appends_keep_all_entries_and_links(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            references = list(pool.map(lambda _: self.append(), range(12)))
        self.assertEqual(self.note.read_text().count("new log"), 12)
        self.assertEqual(len(set(references)), 12)
        for reference in references:
            self.assertEqual(self.daily.read_text().count(reference), 1)

    def test_append_with_windows_lock_backend(self):
        calls = []
        backend = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2,
                                  locking=lambda fd, mode, count: calls.append(mode))
        with patch.object(log, "fcntl", None), patch.object(log, "msvcrt", backend, create=True):
            reference = self.append()
        self.assertIn("new log", self.note.read_text())
        self.assertIn(reference, self.daily.read_text())
        self.assertIn(backend.LK_NBLCK, calls)
        self.assertIn(backend.LK_UNLCK, calls)

    def test_external_edit_during_append_is_not_overwritten(self):
        insert = log.insert_in_ai_log
        calls = 0

        def edit_while_preparing(text, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.daily.write_text("### ai-log\n- manual edit\n", encoding="utf-8")
            return insert(text, content)

        before = self.note.read_text()
        with patch.object(log, "insert_in_ai_log", side_effect=edit_while_preparing):
            with self.assertRaisesRegex(OSError, "changed"):
                self.append()
        self.assertEqual(self.note.read_text(), before)
        self.assertIn("manual edit", self.daily.read_text())

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_work_note_replaced_while_waiting_for_its_lock(self):
        self.replace_during_lock(self.note, 1)

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_daily_replaced_while_waiting_for_its_lock(self):
        self.replace_during_lock(self.daily, 2)

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_earlier_note_replaced_while_waiting_for_later_lock(self):
        self.replace_during_lock(self.note, 2)

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_continual_replacement_stops_without_appending(self):
        flock = log.fcntl.flock
        descriptors = []

        def intercept(note, operation):
            flock(note, operation)
            descriptors.append(note)
            replacement = self.root / "replacement.md"
            replacement.write_text("### ai-log\n- current\n", encoding="utf-8")
            replacement.replace(self.note)

        with patch.object(log.fcntl, "flock", side_effect=intercept):
            with self.assertRaisesRegex(OSError, "repeatedly replaced"):
                self.append()
        self.assertTrue(all(note.closed for note in descriptors))
        self.assertNotIn("new log", self.note.read_text())
        self.assertNotIn("[[", self.daily.read_text())

    @unittest.skipIf(log.fcntl is None, "requires POSIX flock")
    def test_missing_path_after_lock_does_not_write(self):
        flock = log.fcntl.flock
        calls = 0

        def intercept(note, operation):
            nonlocal calls
            flock(note, operation)
            calls += 1
            if calls == 2:
                self.note.unlink()

        with patch.object(log.fcntl, "flock", side_effect=intercept):
            with self.assertRaises(FileNotFoundError):
                self.append()
        self.assertNotIn("[[", self.daily.read_text())


if __name__ == "__main__":
    unittest.main()

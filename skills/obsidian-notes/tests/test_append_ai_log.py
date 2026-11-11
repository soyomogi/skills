import importlib.util
from pathlib import Path
import tempfile
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

    def test_work_note_replaced_while_waiting_for_its_lock(self):
        self.replace_during_lock(self.note, 1)

    def test_daily_replaced_while_waiting_for_its_lock(self):
        self.replace_during_lock(self.daily, 2)

    def test_earlier_note_replaced_while_waiting_for_later_lock(self):
        self.replace_during_lock(self.note, 2)

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
        self.assertNotIn("![[", self.daily.read_text())

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
        self.assertNotIn("![[", self.daily.read_text())


if __name__ == "__main__":
    unittest.main()

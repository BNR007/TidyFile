import os
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from core import classify, document_group_key, execute_plan, load_history, scan_folder, undo_last, unique_path, validate_folder


class OrganizerTests(unittest.TestCase):
    def test_screenshot_work_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination, category, _ = classify(root / "Screenshot client meeting.png", root, Counter())
            self.assertEqual(destination, Path("Screenshots") / "Work")
            self.assertEqual(category, "Pictures")

    def test_video_edit_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination, _, _ = classify(root / "campaign-final-edit.mp4", root, Counter())
            self.assertEqual(destination, Path("Videos") / "Edits")

    def test_custom_video_keyword_changes_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rules = {"video_edits": "montage", "presentations": "talk", "screenshots": "snap", "work": "client", "personal": "family", "group_documents": True}
            destination, _, _ = classify(root / "summer-montage.mp4", root, Counter(), rules=rules)
            self.assertEqual(destination, Path("Videos") / "Edits")

    def test_content_can_identify_work_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination, _, reason = classify(root / "notes.txt", root, Counter(), "client project meeting deadline")
            self.assertEqual(destination, Path("Documents") / "Work" / "Text & Word")
            self.assertIn("Local content", reason)

    def test_document_grouping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = document_group_key("Q3 launch notes.pdf")
            destination, _, _ = classify(root / "Q3 launch notes.pdf", root, Counter({key: 2}))
            self.assertEqual(destination, Path("Documents") / "Grouped" / "Q3 Launch")

    def test_unique_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "report.pdf"
            existing.write_text("one", encoding="utf-8")
            self.assertEqual(unique_path(existing).name, "report (2).pdf")

    def test_drive_root_is_blocked(self):
        with self.assertRaises(ValueError):
            validate_folder(Path(Path.home().anchor))

    def test_full_move_and_undo_cycle(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as app_data:
            root = Path(directory)
            source = root / "client project notes.txt"
            source.write_text("client project meeting roadmap", encoding="utf-8")
            with patch("core.local_app_data", return_value=Path(app_data)):
                result = scan_folder(root, deep_inspect=True)
                self.assertEqual(len(result.moves), 1)
                completed = execute_plan(root, result.moves)
                self.assertFalse(source.exists())
                self.assertTrue(Path(completed[0].destination).exists())
                restored, _ = undo_last()
                self.assertEqual(restored, 1)
                self.assertTrue(source.exists())

    def test_sort_refreshes_only_used_folder_dates_and_preserves_file_dates(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as app_data:
            root = Path(directory).resolve()
            existing = root / "Documents" / "Text & Word"
            existing.mkdir(parents=True)
            untouched = root / "Unrelated"
            untouched.mkdir()
            old_ns = 1_600_000_000_000_000_000
            for folder in (existing, existing.parent, untouched):
                os.utime(folder, ns=(old_ns, old_ns))
            for name in ("notes.txt", "final-edit.mp4"):
                source = root / name
                source.write_text("sample", encoding="utf-8")
                os.utime(source, ns=(old_ns, old_ns))
            # Windows filesystem timestamp precision is 100 ns.
            finished_ns = time.time_ns() // 100 * 100
            with patch("core.local_app_data", return_value=Path(app_data)), patch("core.time.time_ns", return_value=finished_ns):
                completed = execute_plan(root, scan_folder(root).moves)
                for folder in (existing, existing.parent, root / "Videos", root / "Videos" / "Edits"):
                    self.assertEqual(folder.stat().st_mtime_ns, finished_ns)
                self.assertEqual(untouched.stat().st_mtime_ns, old_ns)
                for move in completed:
                    self.assertEqual(Path(move.destination).stat().st_mtime_ns, old_ns)
                restored, _ = undo_last()
                self.assertEqual(restored, 2)

    def test_empty_sort_does_not_touch_folder_dates(self):
        with tempfile.TemporaryDirectory() as directory, patch("core.os.utime") as touch:
            self.assertEqual(execute_plan(Path(directory), []), [])
            touch.assert_not_called()

    def test_timestamp_failure_keeps_move_history_for_undo(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as app_data:
            root = Path(directory)
            source = root / "notes.txt"
            source.write_text("sample", encoding="utf-8")
            with patch("core.local_app_data", return_value=Path(app_data)):
                plan = scan_folder(root).moves
                with patch("core.os.utime", side_effect=PermissionError("denied")):
                    with self.assertRaisesRegex(OSError, "Files were moved.*Undo is still available"):
                        execute_plan(root, plan)
                _, history = load_history()
                self.assertEqual(len(history), 1)
                self.assertTrue(Path(history[0].destination).exists())
                self.assertEqual(undo_last()[0], 1)
                self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()

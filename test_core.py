import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from core import classify, document_group_key, execute_plan, scan_folder, undo_last, unique_path, validate_folder


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


if __name__ == "__main__":
    unittest.main()

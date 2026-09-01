import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from app import TidyWindow, register_bundled_fonts


class AppWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        register_bundled_fonts()

    def test_scan_publishes_preview_and_enables_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "holiday-photo.jpg").write_bytes(b"image")
            (folder / "client-notes.txt").write_text("meeting notes", encoding="utf-8")
            window = TidyWindow()
            window.folder = folder
            window.rescan()
            deadline = time.monotonic() + 5
            while window.busy and time.monotonic() < deadline:
                self.application.processEvents()
                time.sleep(0.01)
            self.assertFalse(window.busy)
            self.assertEqual(window.table.rowCount(), 2)
            self.assertEqual(len(window.plan), 2)
            self.assertIn("sort 2 files", window.primary.text().lower())
            window.close()


if __name__ == "__main__":
    unittest.main()

"""Build promotion retains an old installation and rolls it back on failure."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_exe import build_environment, checked_path, promote_build


class TestPackaging(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.staged = self.root / "build/staged/Reelsator"
        self.target = self.root / "dist/Reelsator"
        self.backup = self.root / "dist/backups/old"
        for folder, contents in ((self.staged, b"new"), (self.target, b"old")):
            folder.mkdir(parents=True)
            (folder / "Reelsator.exe").write_bytes(contents)

    def test_promote_keeps_old_build(self):
        actual = promote_build(self.staged, self.target, self.backup, self.root)
        self.assertEqual(actual, self.backup.resolve())
        self.assertEqual((self.target / "Reelsator.exe").read_bytes(), b"new")
        self.assertEqual((self.backup / "Reelsator.exe").read_bytes(), b"old")

    def test_promotion_failure_restores_old_directory(self):
        original_replace = os.replace

        def replace_or_fail(source, destination):
            if source == self.staged.resolve():
                raise PermissionError("simulated move failure")
            return original_replace(source, destination)

        with patch("build_exe.os.replace", side_effect=replace_or_fail):
            with self.assertRaises(PermissionError):
                promote_build(self.staged, self.target, self.backup, self.root)
        self.assertEqual((self.target / "Reelsator.exe").read_bytes(), b"old")
        self.assertEqual((self.staged / "Reelsator.exe").read_bytes(), b"new")
        self.assertFalse(self.backup.exists())

    def test_outside_root_and_nested_targets_are_rejected_before_moving(self):
        with self.assertRaises(ValueError):
            checked_path(self.root / "../outside", self.root)
        with self.assertRaises(ValueError):
            promote_build(self.staged, self.target, self.target / "backup", self.root)
        self.assertEqual((self.target / "Reelsator.exe").read_bytes(), b"old")

    def test_build_and_runtime_environments_exclude_foreign_dll_search_paths(self):
        with patch.dict(os.environ, {"PATH": "C:/ForeignTools", "PYTHONPATH": "C:/OtherPython",
                                     "QT_PLUGIN_PATH": "C:/OtherQt", "APPDATA": "C:/UserSettings",
                                     "SYSTEMROOT": "D:/Windows"}):
            build = build_environment()
            runtime = build_environment(include_python=False)
            self.assertNotIn("ForeignTools", build["PATH"])
            self.assertNotIn("ForeignTools", runtime["PATH"])
            self.assertNotIn("PYTHONPATH", build)
            self.assertNotIn("QT_PLUGIN_PATH", runtime)
            self.assertEqual(runtime["APPDATA"], "C:/UserSettings")
            self.assertEqual(Path(runtime["PATH"].split(os.pathsep)[0]), Path("D:/Windows/System32"))
            self.assertEqual(os.environ["PATH"], "C:/ForeignTools")


if __name__ == "__main__":
    unittest.main()

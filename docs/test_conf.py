"""Source-link regression tests for documentation built without a checkout."""

import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class SourceReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.conf = self.docs / "conf.py"
        shutil.copyfile(Path(__file__).with_name("conf.py"), self.conf)
        self.addCleanup(os.chdir, Path.cwd())
        os.chdir(self.docs)
        self.addCleanup(setattr, sys, "path", sys.path[:])
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        metadata = patch("importlib.metadata.version", return_value="24.8.1")
        metadata.start()
        self.addCleanup(metadata.stop)

    def reference(self):
        config = runpy.run_path(str(self.conf))
        prefix = "--html-viewsource-base=https://github.com/glyph/automat/tree/"
        return next(arg for arg in config["pydoctor_args"] if arg.startswith(prefix))

    def test_archive(self):
        self.assertTrue(self.reference().endswith("/v24.8.1/src"))

    def test_without_git(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("git")):
            self.assertTrue(self.reference().endswith("/v24.8.1/src"))

    def test_rtd_tag_does_not_run_git(self):
        os.environ.update(READTHEDOCS="True", READTHEDOCS_VERSION="25.4.1")
        with patch("subprocess.run", side_effect=AssertionError("unexpected git")):
            self.assertTrue(self.reference().endswith("/25.4.1/src"))

    def test_branch(self):
        os.environ.update(READTHEDOCS="True", READTHEDOCS_VERSION="latest")
        result = subprocess.CompletedProcess([], 0, stdout="docs-fix\n")
        with patch("subprocess.run", return_value=result) as git:
            self.assertTrue(self.reference().endswith("/docs-fix/src"))
            self.assertEqual(git.call_args.kwargs["cwd"], self.root)

    def test_detached_head(self):
        results = [
            subprocess.CompletedProcess([], 0, stdout="HEAD\n"),
            subprocess.CompletedProcess([], 0, stdout="a" * 40 + "\n"),
        ]
        with patch("subprocess.run", side_effect=results):
            self.assertTrue(self.reference().endswith("/" + "a" * 40 + "/src"))


if __name__ == "__main__":
    unittest.main()

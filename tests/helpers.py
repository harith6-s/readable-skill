"""Shared by the tests: run the two scripts, build a throwaway project from a dict of files."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(os.environ.get("READABLE_SCRIPTS") or ROOT / "scripts").resolve()
EXAMPLES = ROOT / "examples"
EXAMPLE_NAMES = sorted(path.name for path in EXAMPLES.iterdir() if (path / "case.json").exists())


def run(script, *args, cwd):
    # no .pyc: a rewrite of the same size within the same second would otherwise load the old bytecode
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, env=env)
    return done.returncode, (done.stdout + done.stderr)


def jump_depth(*args, cwd):
    return run("jump_depth.py", *args, cwd=cwd)


def parity(*args, cwd):
    return run("parity.py", *args, cwd=cwd)


class ProjectTest(unittest.TestCase):
    def project(self, files):
        """A temporary project: {"pkg/mod.py": "source"} -> its root folder."""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, source in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
        return root

    def record(self, root, unit, scenarios, *extra, name="rec.json"):
        """Record one unit; returns (exit code, output, parsed recording or None)."""
        (root / "scenarios_.py").write_text(textwrap.dedent(scenarios).lstrip("\n"), encoding="utf-8")
        out = root / name
        code, text = parity("record", "--unit", unit, "--root", ".", "--scenarios", "scenarios_.py",
                            "--out", out, *extra, cwd=root)
        return code, text, json.loads(out.read_text()) if out.exists() else None

    def scenario(self, recording, name):
        return next(item for item in recording["scenarios"] if item["name"] == name)

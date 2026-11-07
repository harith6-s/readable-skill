"""Make a working copy of an example for one run.

    python eval/prepare.py <example> <workdir>

Copies examples/<example>/src to <workdir> (which must not exist yet) and writes <workdir>/.original.json: the sha256
of every file the copy starts with. The run works in <workdir>: it adds its new files (a package of task files) and
must leave every file it started with as it was. grade.py compares against that list, so no git is needed.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(example, workdir):
    workdir = Path(workdir)
    if workdir.exists():
        sys.exit(f"{workdir} exists: choose a new folder")
    shutil.copytree(EXAMPLES / example / "src", workdir, ignore=shutil.ignore_patterns("__pycache__"))
    originals = {str(path.relative_to(workdir)): digest(path) for path in sorted(workdir.rglob("*")) if path.is_file()}
    (workdir / ".original.json").write_text(json.dumps(originals, indent=1))
    return workdir


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(prepare(sys.argv[1], sys.argv[2]))

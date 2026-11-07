"""Grade one run of a refactor example: the mechanical assertions.

    python eval/grade.py <example> <workdir> [--scripts DIR] [--json OUT]

<workdir> comes from prepare.py; the run added its files to it. DIR holds jump_depth.py and parity.py (default: the
READABLE_SCRIPTS environment variable, else ../scripts next to this folder). Exit 1 when any assertion fails.

01 parity: every scenario set of the case, recorded on the original (pristine copy) and on the run's new files, diff empty
02 every file the working copy started with is byte for byte unchanged
03 every name production code imports from the original module is defined in one of the run's new files
04 jump_depth: max local_depth <= 1
07 jump_depth layout: no jump inside a file except to a helper directly below its only caller, shared.py functions
   never call each other, no facade
08 each task lives in one file, and different tasks in different files (cases that list their tasks)
09 no new file imports the original module
11 branches of the original that no caller reaches are still in the code as `if` statements (cases that list them)
12 jump_depth classes: no state passed between methods through self, project inheritance <= 1
"""

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
SKIP_PARTS = {"__pycache__"}


def run(command, cwd):
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip()


def expectation(text, passed, evidence):
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def digest(path):
    from prepare import digest as sha
    return sha(path)


def new_files(workdir):
    """Python files that were not in the working copy at the start."""
    originals = json.loads((workdir / ".original.json").read_text())
    return sorted(path for path in workdir.rglob("*.py")
                  if not SKIP_PARTS & set(path.parts) and str(path.relative_to(workdir)) not in originals)


def dotted(path, root):
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def targets(files, root):
    """What jump_depth scans: the folder of a package of new files (so it also checks its __init__.py), else the file."""
    folders = {path.parent for path in files if (path.parent / "__init__.py").exists() and path.parent != root}
    loose = [path for path in files if path.parent not in folders and path.parent == root]
    return sorted(folders) + loose


def defined_names(path):
    """Names a file defines itself: functions, classes and assigned module names (imports do not count)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def check_tasks(where, tasks):
    """Each task in one file of its own. `where` maps a function name to the file that defines it."""
    homes = [{where[name] for name in group if name in where} for group in tasks]
    sharing = [(tasks[i], tasks[j], sorted(homes[i] & homes[j]))
               for i in range(len(homes)) for j in range(i + 1, len(homes)) if homes[i] & homes[j]]
    ok = all(len(home) == 1 for home in homes) and not sharing
    return ok, f"files per task {[sorted(home) for home in homes]}; sharing a file {sharing}"


def kept_branches(files, names):
    """How many `if` statements on each name the files hold."""
    found = {name: 0 for name in names}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.If):
                for name in {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)} & set(found):
                    found[name] += 1
    return found


def importing(files, module):
    """The files that import `module` or something under it."""
    hits = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""] + [f"{node.module}.{alias.name}" for alias in node.names]
            else:
                names = []
            if any(name == module or name.startswith(module + ".") for name in names):
                hits.append(path.name)
    return sorted(set(hits))


def record(scripts, units, case, scenarios, root, out):
    command = [sys.executable, str(scripts / "parity.py"), "record", "--root", ".",
               "--scenarios", str(scenarios), "--out", str(out)]
    for unit in units:
        command += ["--unit", unit]
    for allowed in case.get("allow", []):
        command += ["--allow", allowed]
    return run(command, root)


def grade(example, workdir, scripts):
    case = json.loads((EXAMPLES / example / "case.json").read_text())
    pristine = EXAMPLES / example / "src"
    workdir = Path(workdir).resolve()
    files = new_files(workdir)
    results = []
    module = case["module"]

    # 01 parity
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        units = [f"{path}={dotted(path, workdir)}" for path in files]
        units += [f"{folder}={dotted(folder, workdir)}" for folder in targets(files, workdir) if folder.is_dir()]
        notes, passed = [], bool(files)
        for scenarios in case["scenarios"]:
            scenarios = EXAMPLES / example / scenarios
            old, new = temp / "old.json", temp / "new.json"
            code, text = record(scripts, [str(pristine / case["original"])], case, scenarios, pristine, old)
            if code:
                sys.exit(f"cannot record the original with {scenarios.name}: {text}")
            code, text = record(scripts, units, case, scenarios, workdir, new)
            if code:
                passed = False
                notes.append(f"{scenarios.name}: recording failed: {text[-500:]}")
                continue
            code, text = run([sys.executable, str(scripts / "parity.py"), "diff", str(old), str(new)], workdir)
            passed = passed and code == 0
            notes.append(f"{scenarios.name}: {text[-600:]}")
    results.append(expectation("01 parity diff empty", passed, " | ".join(notes) or f"no new .py file in {workdir}"))

    # 02 originals untouched
    originals = json.loads((workdir / ".original.json").read_text())
    changed = [name for name, expected in originals.items()
               if not (workdir / name).is_file() or digest(workdir / name) != expected]
    results.append(expectation("02 original files unchanged", not changed, f"changed or missing: {changed}"))

    # 03 public surface: defined somewhere in the run, since callers import each name from its own file
    code, text = run([sys.executable, str(scripts / "jump_depth.py"), "--callers", module, "--root", ".",
                      "--usage", ".", "--json"], workdir)
    callers = json.loads(text)["callers"] if code == 0 else []
    needed = sorted({name for caller in callers if not caller["test"] for name in caller["names"]} - {"(module)"})
    where = {}
    for path in files:
        for name in defined_names(path):
            where.setdefault(name, path.name)
    missing = [name for name in needed if name not in where]
    results.append(expectation("03 public surface kept", files and not missing,
                               f"needed {len(needed)}; missing {missing}; "
                               f"homes {sorted({where[name] for name in needed if name in where})}"))

    # 04 local depth and 07 layout: the names production code imports from the original are public (leaves)
    scan = [str(path) for path in targets(files, workdir)]
    code, text = run([sys.executable, str(scripts / "jump_depth.py"), *scan, "--root", ".", "--usage", ".",
                      "--public-from", module, "--json"], workdir)
    report = json.loads(text) if code == 0 and text.startswith("{") else None
    if report is None:
        results.append(expectation("04 max local_depth <= 1", False, f"jump_depth failed: {text[-400:]}"))
        results.append(expectation("07 layout check passes", False, "jump_depth failed"))
        results.append(expectation("12 no state through self, inheritance <= 1", False, "jump_depth failed"))
    else:
        summary = report["summary"]
        results.append(expectation("04 max local_depth <= 1", summary["max_local_depth"] <= 1, f"summary {summary}"))
        results.append(expectation("07 layout check passes", not report["layout"],
                                   f"{len(report['layout'])} problem(s): {report['layout'][:4]}"))
        classes = [f"{cls['class']} state_across={cls['state_across']} inheritance={cls['inheritance']}"
                   for cls in report["classes"] if cls["state_across"] or cls["inheritance"] > 1]
        results.append(expectation("12 no state through self, inheritance <= 1", not classes, f"classes: {classes}"))

    # 08 one task per file
    if case.get("tasks"):
        ok, evidence = check_tasks(where, case["tasks"])
        results.append(expectation("08 each task in one file of its own", ok, evidence))

    # 09 the run does not lean on the original
    leaning = importing(files, module)
    results.append(expectation("09 no new file imports the original", not leaning, f"importing: {leaning}"))

    # 11 dead branches kept
    if case.get("kept_branches"):
        found = kept_branches(files, case["kept_branches"])
        results.append(expectation("11 unreachable branches kept", all(found.values()), f"`if` statements on {found}"))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("example")
    parser.add_argument("workdir")
    parser.add_argument("--scripts", default=os.environ.get("READABLE_SCRIPTS") or str(HERE.parent / "scripts"))
    parser.add_argument("--json")
    args = parser.parse_args()
    results = grade(args.example, args.workdir, Path(args.scripts).resolve())
    for item in results:
        print(("PASS " if item["passed"] else "FAIL ") + item["text"] + " | " + item["evidence"][:300].replace("\n", " "))
    passed = sum(item["passed"] for item in results)
    print(f"{passed}/{len(results)} passed")
    if args.json:
        Path(args.json).write_text(json.dumps({"expectations": results, "summary": {
            "passed": passed, "failed": len(results) - passed, "total": len(results),
            "pass_rate": round(passed / len(results), 2)}}, indent=1))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()

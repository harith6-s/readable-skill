"""Map a Python unit (one file, or a folder of files) and measure how far a reader has to jump to follow it.

Usage:
    python jump_depth.py <file-or-folder> [...] --root <import root> [--usage <folder>] [options]
    python jump_depth.py --callers <dotted.module> --root <import root> --usage <folder>

Per module:      functions; hidden imports (imports inside a function body, and whether a comment gives a reason);
                 public names other production files import, and who imports them (with --usage; test files are
                 listed apart and do not count as public); code that registers itself on import (task decorators,
                 signal receivers, beat schedules).
Per entrypoint:  a function nothing in the unit calls, or a public function.
    depth        longest chain of jumps into project code, outside the unit too (A -> B -> C = 2)
    local_depth  longest chain through the unit's own helpers. A public helper, or code outside the unit, is a leaf:
                 the jump to it counts, nothing behind it does. This is the number the style limits (<= 1).
    reachable    distinct project functions a reader may open from it; cross_file: how many live in another file
    outbound     calls that leave the unit, as file:line: anything imported from outside the unit except the
                 standard library, objects made from those, and .save() .delete() .delay() .apply_async() .send()
Per class:       inheritance (project ancestor layers; framework bases do not count), state_across (`self.x` set in a
                 method other than __init__ and read in another), from_ancestors, defined_elsewhere.
Layout:          jumps inside one file. A top-level function called from its own file must sit directly below its
                 only caller there; functions in shared.py never call each other; an __init__.py of a target folder
                 holds no code and re-exports nothing (no facade).

Options:
    --check            exit 1 unless every local_depth <= 1, inheritance <= 1, no state_across, every hidden import
                       has a reason comment, no --forbid module is imported, and the layout has no problem.
                       Run it on the original too: what it lists is what is wrong now
    --forbid MODULE    a module the unit must not import, such as the old code for a V2 (repeatable)
    --public-from MODULE  also count as public the names production code imports from MODULE: a V2 that nobody
                       imports yet keeps the old code's public surface (repeatable; scans --usage, else --root)
    --similar FOLDER   functions of the unit that look like a function elsewhere in FOLDER (mode new: reuse that one)
    --callers MODULE   who imports MODULE: production files and test files, as file:line (the migrate checklist)
    --include-tests    count imports made by test files as public
    --json             the whole report as JSON (parity.py coverage reads its "outbound")
"""

import argparse
import ast
import copy
import difflib
import json
import sys
import warnings
from pathlib import Path

STDLIB = set(sys.stdlib_module_names)
REGISTERING = {"shared_task", "task", "periodic_task", "receiver", "register", "connect"}
WRITES = {"save", "delete", "delay", "apply_async", "send"}
SIMILAR_RATIO = 0.8
SIMILAR_MIN_STATEMENTS = 3


def module_name(path, root):
    rel = path.resolve().relative_to(root.resolve()).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def shown_path(path, root):
    """The file as sites print it: relative to the import root, so parity.py writes the same text."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_relative(module, level, current):
    if level == 0:
        return module or ""
    base = current.split(".")[:-level]
    return ".".join(base + ([module] if module else []))


def project_module(name, root):
    path = root.joinpath(*name.split("."))
    return path.with_suffix(".py").exists() or (path / "__init__.py").exists() or path.is_dir()


def module_file(name, root):
    path = root.joinpath(*name.split("."))
    if path.with_suffix(".py").exists():
        return path.with_suffix(".py")
    return path / "__init__.py" if (path / "__init__.py").exists() else None


def is_constant_name(name):
    """BASE_URL, TOKEN: an imported constant, not something that runs (parity.py gives it its value or text)."""
    return name.isupper() and (len(name) >= 4 or "_" in name)


def root_name(expr):
    while isinstance(expr, (ast.Attribute, ast.Call, ast.Subscript)):
        expr = expr.func if isinstance(expr, ast.Call) else expr.value
    return expr.id if isinstance(expr, ast.Name) else None


def makes_client(value, outside):
    """`session = ApiSession(...)`, `api = PaymentApi()`: an object built from outside code, whose calls leave the unit.
    `res = session.post(...)` is not: its result is data."""
    if not isinstance(value, ast.Call) or root_name(value.func) not in outside:
        return False
    func = value.func
    last = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return last[:1].isupper()


def has_reason(lines, lineno):
    line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
    previous = lines[lineno - 2].strip() if lineno >= 2 else ""
    return "#" in line or previous.startswith("#")


def is_test_file(path):
    return "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py")


def class_info(node, module, scope):
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(scope.get(base.id, f"{module}:{base.id}"))
        elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
            owner = scope.get(base.value.id, "")
            if owner.endswith(":"):
                bases.append(f"{owner[:-1]}:{base.attr}")
    attrs, stores, loads = set(), {}, {}
    for item in node.body:
        if isinstance(item, ast.Assign):
            attrs.update(target.id for target in item.targets if isinstance(target, ast.Name))
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            attrs.add(item.target.id)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            attrs.add(item.name)
            for inner in ast.walk(item):
                if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name) and inner.value.id == "self":
                    bucket = stores if isinstance(inner.ctx, ast.Store) else loads
                    bucket.setdefault(inner.attr, set()).add(item.name)
    return {"module": module, "line": node.lineno, "bases": bases, "attrs": attrs, "stores": stores, "loads": loads}


class Unit:
    def __init__(self, files, root):
        self.root = root
        self.names = {module_name(path, root) for path in files}
        self.defs = {}           # "module:qualname" -> {"module", "calls", "line"}
        self.nodes = {}          # "module:qualname" -> ast node (for --similar)
        self.outbound = {}       # "module:qualname" -> [(line, call text)]
        self.classes = {}        # "module:Class" -> class_info, for classes of the unit
        self.modules = {}
        self.hidden = {}         # module -> [{"line", "import", "reason"}]
        self.imported = {}       # module -> [(line, source module)], every import, for --forbid
        self.registering = {}    # module -> [{"line", "name", "how"}]
        self.other_modules = {}  # project modules outside the unit, parsed on demand: name -> (classes, scope)
        for path in files:
            self.load(path)

    def load(self, path):
        name = module_name(path, self.root)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        top_imports = self.imports(tree.body, name)
        outside = self.outside_names(tree.body, name)
        for node in tree.body:
            if isinstance(node, ast.Assign) and makes_client(node.value, outside):
                outside.update({target.id: "" for target in node.targets if isinstance(target, ast.Name)})
        self.modules[name] = {"file": str(path), "shown": shown_path(path, self.root), "functions": 0,
                              "scope": top_imports}
        self.hidden[name] = []
        self.imported[name] = [(node.lineno, source_module)
                               for node in ast.walk(tree) for source_module in self.sources(node, name)]
        self.registering[name] = self.find_registering(tree)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.add_function(name, node.name, node, top_imports, outside, lines, cls=None)
            elif isinstance(node, ast.ClassDef):
                self.classes[f"{name}:{node.name}"] = class_info(node, name, top_imports)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.add_function(name, f"{node.name}.{item.name}", item, top_imports, outside, lines,
                                          cls=node.name)

    def sources(self, node, current):
        if isinstance(node, ast.ImportFrom):
            source = resolve_relative(node.module, node.level, current)
            return [source] + [f"{source}.{alias.name}" for alias in node.names]
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        return []

    def imports(self, body, current):
        """Names bound to project modules or objects: name -> "module:object" (or "module:" for a module)."""
        names = {}
        for node in body:
            if isinstance(node, ast.ImportFrom):
                source = resolve_relative(node.module, node.level, current)
                if project_module(source, self.root) or project_module(source.rsplit(".", 1)[0], self.root):
                    for alias in node.names:
                        names[alias.asname or alias.name] = f"{source}:{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if project_module(alias.name, self.root):
                        names[alias.asname or alias.name] = f"{alias.name}:"
        return names

    def outside_names(self, body, current):
        """Names imported from outside the unit, the standard library excepted: what a harness must stub."""
        names = {}
        for node in body:
            if isinstance(node, ast.ImportFrom):
                source = resolve_relative(node.module, node.level, current)
                if source.split(".")[0] in STDLIB | {"__future__"} or source in self.names:
                    continue
                for alias in node.names:
                    if f"{source}.{alias.name}" not in self.names:
                        names[alias.asname or alias.name] = source
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in STDLIB and alias.name not in self.names:
                        names[alias.asname or alias.name.split(".")[0]] = alias.name
        return names

    def find_registering(self, tree):
        found = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    target = decorator.func if isinstance(decorator, ast.Call) else decorator
                    last = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
                    if last in REGISTERING:
                        found.append({"line": decorator.lineno, "name": node.name,
                                      "how": "@" + ast.unparse(decorator)[:60]})
            elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                  and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "connect"):
                found.append({"line": node.lineno, "name": ast.unparse(node.value.func.value)[:40],
                              "how": ast.unparse(node.value)[:60]})
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                text = " ".join(ast.unparse(target) for target in targets)
                if "beat_schedule" in text.lower():
                    found.append({"line": node.lineno, "name": text[:40], "how": "beat schedule"})
        return found

    def add_function(self, module, qualname, node, top_imports, outside, lines, cls):
        local_imports, local_outside = {}, dict(outside)
        for inner in ast.walk(node):
            if isinstance(inner, (ast.Import, ast.ImportFrom)):
                self.hidden[module].append({"line": inner.lineno, "import": ast.unparse(inner)[:80],
                                            "reason": has_reason(lines, inner.lineno)})
                local_imports.update(self.imports([inner], module))
                local_outside.update(self.outside_names([inner], module))
        for inner in ast.walk(node):
            if isinstance(inner, ast.Assign) and makes_client(inner.value, local_outside):
                local_outside.update({target.id: "" for target in inner.targets if isinstance(target, ast.Name)})
        scope = {**top_imports, **local_imports}
        calls, sites = set(), {}
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            func = inner.func
            if isinstance(func, ast.Name):
                calls.add(scope.get(func.id, f"{module}:{func.id}"))   # a same-module function or a builtin
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                owner = func.value.id
                if owner in ("self", "cls") and cls:
                    calls.add(f"{module}:{cls}.{func.attr}")
                elif owner in scope and scope[owner].endswith(":"):
                    calls.add(f"{scope[owner][:-1]}:{func.attr}")      # module.function()
                elif owner in scope:
                    calls.add(f"{scope[owner]}.{func.attr}")           # ImportedClass.method()
            root = root_name(func)
            leaves = root in local_outside and (isinstance(func, ast.Name) or not is_constant_name(root))
            writes = isinstance(func, ast.Attribute) and func.attr in WRITES
            if (leaves or writes) and inner.lineno not in sites:
                sites[inner.lineno] = ast.unparse(func)[:80]
        key = f"{module}:{qualname}"
        self.defs[key] = {"module": module, "calls": calls, "line": node.lineno}
        self.nodes[key] = node
        self.outbound[key] = sorted(sites.items())
        self.modules[module]["functions"] += 1

    def is_project_target(self, target):
        if target in self.defs:
            return True
        module = target.split(":", 1)[0]
        return module not in self.modules and project_module(module, self.root)

    def edges(self, key):
        return {target for target in self.defs[key]["calls"] if target != key and self.is_project_target(target)}

    def walk(self, key):
        """(depth, reachable, cross_file) from one function, counting jumps out of the unit too; cycles are cut."""
        best, seen = 0, set()
        stack = [(key, 0, (key,))]
        while stack:
            node, depth, path = stack.pop()
            best = max(best, depth)
            if node not in self.defs:
                continue                                    # a jump out of the unit: counted, not followed
            for target in self.edges(node):
                seen.add(target)
                if target not in path:
                    stack.append((target, depth + 1, path + (target,)))
        origin = self.defs[key]["module"]
        cross = sum(1 for target in seen if target.split(":", 1)[0] != origin)
        return best, len(seen), cross

    def walk_local(self, key, shared):
        """Longest chain through the unit's own helpers; a shared (public) helper ends the chain."""
        best = 0
        stack = [(key, 0, (key,))]
        while stack:
            node, depth, path = stack.pop()
            best = max(best, depth)
            if node != key and node in shared:
                continue
            for target in self.edges(node):
                if target in self.defs and target not in path:
                    stack.append((target, depth + 1, path + (target,)))
        return best

    def reach_unit(self, key):
        seen, stack = {key}, [key]
        while stack:
            for target in self.edges(stack.pop()):
                if target in self.defs and target not in seen:
                    seen.add(target)
                    stack.append(target)
        return seen

    def sites(self, keys):
        found = []
        for key in keys:
            shown = self.modules[self.defs[key]["module"]]["shown"]
            found.extend({"site": f"{shown}:{line}", "call": call} for line, call in self.outbound[key])
        return sorted({item["site"]: item for item in found}.values(), key=site_order)

    def entrypoints(self, shared):
        called = {target for key in self.defs for target in self.edges(key)}
        return [key for key in self.defs if key not in called or key in shared]

    # ---- classes ----

    def find_class(self, key, seen=()):
        """class_info of a project class, following re-exports; None for framework/library classes."""
        if key in self.classes:
            return self.classes[key]
        module, _, name = key.partition(":")
        if module in self.modules:
            target = self.modules[module]["scope"].get(name)
        else:
            if module not in self.other_modules:
                self.other_modules[module] = self.parse_module(module)
            classes, scope = self.other_modules[module]
            if key in classes:
                return classes[key]
            target = scope.get(name)
        if target and target not in seen and not target.endswith(":"):
            return self.find_class(target, seen + (key,))
        return None

    def parse_module(self, module):
        path = module_file(module, self.root)
        if path is None:
            return {}, {}
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            return {}, {}
        scope = self.imports(tree.body, module)
        classes = {f"{module}:{node.name}": class_info(node, module, scope)
                   for node in tree.body if isinstance(node, ast.ClassDef)}
        return classes, scope

    def inheritance(self, key, seen=()):
        """(depth, chain) of project ancestors; framework/library bases are not counted."""
        info = self.find_class(key)
        if info is None or key in seen:
            return 0, []
        best, chain = 0, []
        for base in info["bases"]:
            if self.find_class(base) is None:
                continue
            depth, sub = self.inheritance(base, seen + (key,))
            if depth + 1 > best:
                best, chain = depth + 1, [base] + sub
        return best, chain

    def ancestors(self, key, seen=None):
        seen = set() if seen is None else seen
        info = self.find_class(key) or {}
        for base in info.get("bases", []):
            if base not in seen and self.find_class(base) is not None:
                seen.add(base)
                self.ancestors(base, seen)
        return seen

    def class_report(self, key):
        info = self.classes[key]
        depth, chain = self.inheritance(key)
        own = info["attrs"] | set(info["stores"])
        inherited = set()
        for ancestor in self.ancestors(key):
            ancestor_info = self.find_class(ancestor)
            inherited |= ancestor_info["attrs"] | set(ancestor_info["stores"])
        read_elsewhere = [attr for attr in info["loads"] if attr not in own]
        return {
            "class": key, "line": info["line"], "inheritance": depth, "chain": chain,
            "state_across": sorted(attr for attr, where in info["stores"].items()
                                   if where - {"__init__"} and info["loads"].get(attr, set()) - where),
            "from_ancestors": sorted(attr for attr in read_elsewhere if attr in inherited),
            "defined_elsewhere": sorted(attr for attr in read_elsewhere if attr not in inherited),
        }


def site_order(item):
    file, _, line = item["site"].rpartition(":")
    return file, int(line)


def importers(usage_root, root, targets, skip_files, include_tests=False):
    """Who imports each target module: {"names": public names, "callers": [{"file", "line", "names", "test"}]}.
    Test files are listed but their names are not public unless include_tests: tests often import internals."""
    found = {target: {"names": set(), "callers": []} for target in targets}
    for path in sorted(usage_root.rglob("*.py")):
        if path.resolve() in skip_files or "compare" in path.parts:
            continue                                        # compare/ holds the experiment's own variants
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            current = module_name(path, root)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        test = is_test_file(path)
        aliases = {}                                        # local dotted name -> target module imported whole
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                source = resolve_relative(node.module, node.level, current)
                if source in found:
                    names = [alias.name for alias in node.names]
                    found[source]["callers"].append({"file": str(path), "line": node.lineno, "names": names,
                                                     "test": test})
                    if include_tests or not test:
                        found[source]["names"].update(names)
                    continue
                for alias in node.names:
                    if f"{source}.{alias.name}" in found:
                        aliases[alias.asname or alias.name] = (f"{source}.{alias.name}", node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in found:
                        aliases[alias.asname or alias.name] = (alias.name, node.lineno)
        for local, (target, line) in aliases.items():
            used = sorted({node.attr for node in ast.walk(tree)
                           if isinstance(node, ast.Attribute) and ast.unparse(node.value) == local})
            found[target]["callers"].append({"file": str(path), "line": line, "names": used or ["(module)"],
                                             "test": test})
            if include_tests or not test:
                found[target]["names"].update(used)
    return found


def fingerprint(node):
    """Tokens of a function body with every local name blanked, so renamed copies still match."""
    class Blank(ast.NodeTransformer):
        def visit_Name(self, name):
            return ast.copy_location(ast.Name(id="_", ctx=name.ctx), name)

        def visit_arg(self, arg):
            arg.arg = "_"
            return arg

    body = [Blank().visit(copy.deepcopy(statement)) for statement in node.body]
    dump = ast.dump(ast.Module(body=body, type_ignores=[]), annotate_fields=False)
    return dump.replace("(", " ( ").replace(")", " ) ").replace(",", " ").split()


def statements(node):
    return sum(isinstance(inner, ast.stmt) for inner in ast.walk(node)) - 1


def similar(unit, folder, root):
    """Pairs (unit function, function elsewhere in folder) whose bodies look alike."""
    mine = {key: fingerprint(node) for key, node in unit.nodes.items() if statements(node) >= SIMILAR_MIN_STATEMENTS}
    unit_files = {Path(info["file"]).resolve() for info in unit.modules.values()}
    matches = []
    matcher = difflib.SequenceMatcher()
    for path in sorted(folder.rglob("*.py")):
        if (path.resolve() in unit_files or "compare" in path.parts or "migrations" in path.parts
                or is_test_file(path)):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or statements(node) < SIMILAR_MIN_STATEMENTS:
                continue
            theirs = fingerprint(node)
            matcher.set_seq2(theirs)
            for key, tokens in mine.items():
                if not 0.6 <= len(tokens) / len(theirs) <= 1.67:
                    continue
                matcher.set_seq1(tokens)
                if matcher.real_quick_ratio() < SIMILAR_RATIO or matcher.quick_ratio() < SIMILAR_RATIO:
                    continue
                ratio = matcher.ratio()
                if ratio >= SIMILAR_RATIO:
                    matches.append({"function": key, "looks_like": f"{shown_path(path, root)}:{node.lineno}",
                                    "name": node.name, "ratio": round(ratio, 2)})
    return sorted(matches, key=lambda match: (match["function"], -match["ratio"]))


def same_file_jumps(unit):
    """A top-level function called from its own file sits directly below its only caller there (between them only
    other helpers of that caller), so a reader jumps down a few lines and back. A helper with two callers in the
    file goes into shared.py, whose functions never call each other. Calls from other files do not count here."""
    found = []
    for module, info in unit.modules.items():
        order = [key for _, key in sorted((data["line"], key) for key, data in unit.defs.items()
                                          if data["module"] == module and "." not in key.split(":", 1)[1])]
        callers = {key: [] for key in order}
        for key in order:
            for target in sorted(unit.defs[key]["calls"]):
                if target in callers and target != key:
                    callers[target].append(key)
        for target, by in callers.items():
            if not by:
                continue
            name, where = target.split(":", 1)[1], f"{info['shown']}:{unit.defs[target]['line']}"
            names = ", ".join(key.split(":", 1)[1] for key in by)
            if Path(info["file"]).stem == "shared":
                found.append(f"{where} {name} is called by {names} in shared.py: its functions never call each other")
            elif len(by) > 1:
                found.append(f"{where} {name} is called by {names} in its own file: move it to shared.py")
            else:
                start, end = order.index(by[0]), order.index(target)
                if end < start or any(callers[key] != by for key in order[start + 1:end]):
                    found.append(f"{where} {name} is not directly below its caller {names}: "
                                 f"place it right under it, or move it to shared.py")
    return found


def facades(paths, root):
    """An __init__.py of a target folder that holds code or re-exports the package: callers must import from the
    task files themselves."""
    found = []
    for raw in paths:
        folder = Path(raw)
        if not folder.is_dir():
            continue
        for init in sorted(folder.rglob("__init__.py")):
            package = module_name(init, root)
            for node in ast.parse(init.read_text(encoding="utf-8")).body:
                source = (resolve_relative(node.module, node.level, package + ".__init__")
                          if isinstance(node, ast.ImportFrom) else "")
                if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        or source == package or source.startswith(package + ".")):
                    found.append(f"{shown_path(init, root)}:{node.lineno} __init__.py holds code or re-exports "
                                 f"(a facade): callers import from the task files")
                    break
    return found


def violations(report, forbid_hits):
    found = [f"local_depth {entry['local_depth']} > 1: {entry['entrypoint']}"
             for entry in report["entrypoints"] if entry["local_depth"] > 1]
    found += [f"inheritance {cls['inheritance']} > 1: {cls['class']} {cls['chain']}"
              for cls in report["classes"] if cls["inheritance"] > 1]
    found += [f"state passed through self: {cls['class']} {cls['state_across']}"
              for cls in report["classes"] if cls["state_across"]]
    found += [f"import inside a function without a reason comment: {module['shown']}:{item['line']} {item['import']}"
              for module in report["modules"] for item in module["hidden_imports"] if not item["reason"]]
    found += [f"imports forbidden module {source}: {shown}:{line}" for shown, line, source in forbid_hits]
    found += [f"layout: {problem}" for problem in report["layout"]]
    return found


def print_callers(module, info):
    production = [caller for caller in info["callers"] if not caller["test"]]
    tests = [caller for caller in info["callers"] if caller["test"]]
    print(f"production callers of {module}: {len(production)}")
    for caller in production:
        print(f"  {caller['file']}:{caller['line']}  {', '.join(caller['names'])}")
    print(f"tests importing {module}: {len(tests)}")
    for caller in tests:
        print(f"  {caller['file']}:{caller['line']}  {', '.join(caller['names'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--root", required=True, help="import root, e.g. application/")
    parser.add_argument("--usage", help="folder to scan for imports of the unit (public surface, callers)")
    parser.add_argument("--include-tests", action="store_true", help="count imports made by test files as public")
    parser.add_argument("--callers", metavar="MODULE", help="list who imports MODULE, then stop")
    parser.add_argument("--forbid", action="append", default=[], metavar="MODULE")
    parser.add_argument("--public-from", action="append", default=[], metavar="MODULE")
    parser.add_argument("--similar", metavar="FOLDER")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    warnings.filterwarnings("ignore", category=SyntaxWarning)   # e.g. "\d" in scanned files is not our concern
    root = Path(args.root)

    if args.callers:
        if not args.usage:
            parser.error("--callers needs --usage")
        info = importers(Path(args.usage), root, [args.callers], set(), args.include_tests)[args.callers]
        if args.json:
            json.dump({"module": args.callers, "callers": info["callers"]}, sys.stdout, ensure_ascii=False, indent=2)
        else:
            print_callers(args.callers, info)
        return
    if not args.paths:
        parser.error("give a file or folder, or --callers MODULE")

    files = []
    for raw in args.paths:
        path = Path(raw)
        files.extend(sorted(p for p in path.rglob("*.py") if p.name != "__init__.py") if path.is_dir() else [path])
    unit = Unit(files, root)
    unit_files = {Path(info["file"]).resolve() for info in unit.modules.values()}
    usage = importers(Path(args.usage), root, list(unit.modules), unit_files, args.include_tests) if args.usage else {}
    shared = {f"{module}:{name}" for module, info in usage.items() for name in info["names"]
              if f"{module}:{name}" in unit.defs}
    if args.public_from:
        old = importers(Path(args.usage or args.root), root, args.public_from, unit_files, args.include_tests)
        kept = {name for info in old.values() for name in info["names"]}
        shared |= {key for key in unit.defs if key.split(":", 1)[1] in kept}

    report = {"modules": [], "entrypoints": [], "classes": []}
    for name, info in unit.modules.items():
        report["modules"].append({
            "module": name, "shown": info["shown"], "functions": info["functions"],
            "hidden_imports": unit.hidden[name], "registering": unit.registering[name],
            "public": sorted(usage[name]["names"]) if args.usage else None,
            "callers": usage[name]["callers"] if args.usage else None,
        })
    for key in sorted(unit.entrypoints(shared), key=lambda k: (unit.defs[k]["module"], unit.defs[k]["line"])):
        depth, reachable, cross = unit.walk(key)
        report["entrypoints"].append({
            "entrypoint": key, "line": unit.defs[key]["line"], "public": key in shared, "max_depth": depth,
            "local_depth": unit.walk_local(key, shared), "reachable": reachable, "cross_file": cross,
            "outbound": unit.sites(unit.reach_unit(key)),
        })
    for key in sorted(unit.classes, key=lambda k: (unit.classes[k]["module"], unit.classes[k]["line"])):
        report["classes"].append(unit.class_report(key))
    report["outbound"] = unit.sites(unit.defs)
    forbid_hits = list({(unit.modules[module]["shown"], line): (unit.modules[module]["shown"], line, source)
                        for module, found in reversed(unit.imported.items()) for line, source in reversed(found)
                        for forbidden in args.forbid
                        if source == forbidden or source.startswith(forbidden + ".")}.values())
    forbid_hits.sort()
    if args.similar:
        report["similar"] = similar(unit, Path(args.similar), root)
    report["layout"] = same_file_jumps(unit) + facades(args.paths, root)
    report["summary"] = {
        "functions": sum(m["functions"] for m in report["modules"]),
        "hidden_imports": sum(len(m["hidden_imports"]) for m in report["modules"]),
        "max_depth": max((e["max_depth"] for e in report["entrypoints"]), default=0),
        "max_local_depth": max((e["local_depth"] for e in report["entrypoints"]), default=0),
        "max_inheritance": max((c["inheritance"] for c in report["classes"]), default=0),
        "state_across": sum(len(c["state_across"]) for c in report["classes"]),
        "outbound_sites": len(report["outbound"]),
        "layout_problems": len(report["layout"]),
    }
    report["violations"] = violations(report, forbid_hits)

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    else:
        for module in report["modules"]:
            reasons = sum(item["reason"] for item in module["hidden_imports"])
            line = (f"{module['module']}: functions={module['functions']} "
                    f"hidden_imports={len(module['hidden_imports'])} (with a reason: {reasons})")
            if module["public"] is not None:
                line += f" public={len(module['public'])} {module['public']}"
            print(line)
            for item in module["registering"]:
                print(f"  registers on import: {module['shown']}:{item['line']} {item['name']} {item['how']}")
            if module["callers"] is not None:
                print_callers(module["module"], {"callers": module["callers"]})
        print(f"{'entrypoint':<62} {'line':>5} {'depth':>5} {'local':>5} {'reach':>5} {'cross':>5} {'out':>4}")
        for entry in report["entrypoints"]:
            mark = " (public)" if entry["public"] else ""
            print(f"{entry['entrypoint'] + mark:<62} {entry['line']:>5} {entry['max_depth']:>5} "
                  f"{entry['local_depth']:>5} {entry['reachable']:>5} {entry['cross_file']:>5} "
                  f"{len(entry['outbound']):>4}")
        print("outbound calls:")
        for item in report["outbound"]:
            print(f"  {item['site']}  {item['call']}")
        for cls in report["classes"]:
            print(f"class {cls['class']} (line {cls['line']}): inheritance={cls['inheritance']} {cls['chain']} "
                  f"state_across={cls['state_across']} from_ancestors={cls['from_ancestors']} "
                  f"defined_elsewhere={cls['defined_elsewhere']}")
        for match in report.get("similar", []):
            print(f"similar: {match['function']} looks like {match['looks_like']} {match['name']} "
                  f"({match['ratio']})")
        for problem in report["layout"]:
            print(f"layout: {problem}")
        print("summary:", report["summary"])
        if args.check:
            print("check:", "OK" if not report["violations"] else "FAILED")
            for problem in report["violations"]:
                print("  " + problem)
    if args.check and report["violations"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

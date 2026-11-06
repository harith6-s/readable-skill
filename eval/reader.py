"""A budgeted code reader: show a unit one function at a time and count every look.

A reader (a person or an AI) answers questions about a unit, but sees only one function per `open`, and every open
counts against a budget, re-opening the same function included. Jumping around therefore has a cost that shows up
in the log, the way it does for a person who has to keep the trail in mind.

    python reader.py build   --unit PATH [--unit PATH ...] --out BUNDLE
    python reader.py outline --bundle BUNDLE                          names only, free
    python reader.py open    NAME --bundle BUNDLE --log LOG [--budget N]
    python reader.py report  --log LOG [--json]

build    splits every file into chunks: one per function or method, one per class header (its non-method lines),
         and one per file for the module-level code (imports, constants). The bundle is packed, so the reader
         cannot simply read the source instead.
outline  lists each file and its chunk names with their line counts, like an editor's outline.
open     prints one chunk. NAME is a chunk id ("file.py:Class.method", "file.py:<module>") or a unique short name
         ("method", "Class.method"). An unknown or ambiguous name lists candidates and does not count.
         When the budget is used up, nothing is shown and the refusal is logged.
report   opens, distinct chunks, re-opens and refusals, in order.
"""

import argparse
import ast
import base64
import json
import sys
import zlib
from pathlib import Path


def chunks_of(path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    name = path.name
    taken, found = set(), []

    def span(node):
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        return start, node.end_lineno

    def add(chunk_id, start, end):
        taken.update(range(start, end + 1))
        found.append({"id": chunk_id, "file": name, "start": start, "lines": "\n".join(lines[start - 1:end])})

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(f"{name}:{node.name}", *span(node))
        elif isinstance(node, ast.ClassDef):
            methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for item in methods:
                add(f"{name}:{node.name}.{item.name}", *span(item))
            start, end = span(node)
            header = [number for number in range(start, end + 1) if number not in taken]
            taken.update(header)
            found.append({"id": f"{name}:{node.name}", "file": name, "start": start,
                          "lines": "\n".join(lines[number - 1] for number in header)})
    module_lines = [number for number in range(1, len(lines) + 1) if number not in taken]
    found.append({"id": f"{name}:<module>", "file": name, "start": 1,
                  "lines": "\n".join(lines[number - 1] for number in module_lines).strip("\n")})
    return sorted(found, key=lambda chunk: (chunk["file"], chunk["start"]))


def pack(data):
    return base64.b64encode(zlib.compress(json.dumps(data, ensure_ascii=False).encode("utf-8"))).decode("ascii")


def unpack(text):
    return json.loads(zlib.decompress(base64.b64decode(text)).decode("utf-8"))


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(args):
    chunks = []
    for raw in args.unit:
        path = Path(raw)
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            if "__pycache__" in file.parts or not file.read_text(encoding="utf-8").strip():
                continue                                    # an empty __init__.py has nothing to read
            chunks.extend(chunks_of(file))
    Path(args.out).write_text(pack(chunks), encoding="ascii")
    print(f"{len(chunks)} chunks from {len({chunk['file'] for chunk in chunks})} files -> {args.out}")


def outline(args):
    chunks = unpack(Path(args.bundle).read_text(encoding="ascii"))
    current = None
    for chunk in chunks:
        if chunk["file"] != current:
            current = chunk["file"]
            print(current)
        print(f"  {chunk['id'].split(':', 1)[1]:<50} {len(chunk['lines'].splitlines()):>4} lines")


def resolve(chunks, name):
    exact = [chunk for chunk in chunks if chunk["id"] == name]
    if exact:
        return exact
    return [chunk for chunk in chunks
            if chunk["id"].split(":", 1)[1] == name or chunk["id"].split(":", 1)[1].split(".")[-1] == name]


def open_chunk(args):
    chunks = unpack(Path(args.bundle).read_text(encoding="ascii"))
    log = Path(args.log)
    opened = [entry for entry in read_log(log) if "open" in entry]
    matches = resolve(chunks, args.name)
    if not matches:
        print(f"no chunk named {args.name!r}; see `outline`")
        return
    if len(matches) > 1:
        print(f"more than one chunk named {args.name!r}; use one of:")
        for chunk in matches:
            print("  " + chunk["id"])
        return
    chunk = matches[0]
    with log.open("a", encoding="utf-8") as out:
        if args.budget is not None and len(opened) >= args.budget:
            out.write(json.dumps({"refused": chunk["id"], "after": len(opened)}) + "\n")
            print(f"Budget used up: {len(opened)} of {args.budget} opens. Answer with what you have.")
            return
        out.write(json.dumps({"open": chunk["id"], "n": len(opened) + 1}) + "\n")
    left = "" if args.budget is None else f", {args.budget - len(opened) - 1} opens left"
    print(f"# {chunk['id']} (from line {chunk['start']}){left}\n{chunk['lines']}")


def report(args):
    entries = read_log(Path(args.log))
    opens = [entry["open"] for entry in entries if "open" in entry]
    refused = [entry["refused"] for entry in entries if "refused" in entry]
    summary = {"opens": len(opens), "distinct": len(set(opens)), "reopens": len(opens) - len(set(opens)),
               "refused": len(refused), "order": opens}
    if args.json:
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        return
    print(f"opens={summary['opens']} distinct={summary['distinct']} reopens={summary['reopens']} "
          f"refused={summary['refused']}")
    for number, chunk_id in enumerate(opens, 1):
        print(f"  {number:>2}. {chunk_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build")
    b.add_argument("--unit", action="append", required=True)
    b.add_argument("--out", required=True)
    o = commands.add_parser("outline")
    o.add_argument("--bundle", required=True)
    p = commands.add_parser("open")
    p.add_argument("name")
    p.add_argument("--bundle", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--budget", type=int)
    r = commands.add_parser("report")
    r.add_argument("--log", required=True)
    r.add_argument("--json", action="store_true")
    args = parser.parse_args()
    {"build": build, "outline": outline, "open": open_chunk, "report": report}[args.command](args)


if __name__ == "__main__":
    main()

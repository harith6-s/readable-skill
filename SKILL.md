---
name: readable
description: Use when working code is hard to follow because a reader must jump back and forth between functions or files (inside one file or across files) to trace one request, job or task from start to end; when nobody can say which function is the entry point or where a payload is assembled; when an earlier "make it readable" refactor split the code into smaller pieces; or when a new feature must read top to bottom from the start.
disable-model-invocation: true
argument-hint: "mode=new|refactor|migrate <target> [apply=v2|replace] [out=<path>] [work=<folder>] [layout=A|B|AB] [depth=1-3] [style=auto|function|class]"
metadata:
  version: "1.1"
---

# Readable

## Overview

One request or task must read **top to bottom, in one place**. Readability is measured in **jump levels**, not in lines: a file may grow and code may get slightly slower, but **behavior must not change**.

This skill is a **process with gates**, not a list of tips. Every step ends with an artifact (a file or a command result). Do not start the next step until that artifact exists. If a gate cannot be met, stop and tell the user why. Do not work around it.

`references/style.md` defines what good code looks like. Read it before writing any code, in every mode.

## Inputs

| Input | Meaning | Default |
|---|---|---|
| `mode` | `new` = write new code from scratch · `refactor` = reshape existing code · `migrate` = continue from a refactor report: move callers to the V2, then delete the old code | **required**, ask if missing |
| target | `new`: what to build and where · `refactor`: a file or a folder · `migrate`: the report's path | required |
| `apply` | `v2` = write a new copy beside the old code and leave the old code untouched · `replace` = overwrite the old code after the user approves | `v2` |
| `out` | where the new code goes | `v2`: beside the original, named by the V2 rule in step 2 · `replace`: the original's place |
| `work` | folder for the artifacts: map, scenarios, recordings, report | `docs/readable/<unit>/` |
| `layout`, `depth`, `style` | see `references/style.md` | `A`, `3`, `auto` |

## Scope

Reshape **internal code only**: services, utilities, background job bodies. Framework-facing code (HTTP views and controllers, serializers and schemas, ORM models, routing, migrations) is outside the unit. Never reshape it. Its calls into the unit are part of the public surface.

A **unit** is the code of one task: the functions reachable from that task's entry points and used nowhere else. A helper that code outside the unit also uses is a **leaf**, like a library call. It can become a unit of its own later.

The **public surface** is every name that production code outside the unit imports. Tests do not count.

## Mode `refactor`

### 1. Map

Run `python scripts/jump_depth.py <target> --root <import root> --usage <repo dir> --check`. It lists entry points, the public surface, inbound callers, outbound calls, helpers shared outside the unit, and code that registers itself on import (task decorators, signal receivers). What `--check` lists is what is wrong now: copy it into `map.md` with the numbers. Then write a one-line meaning for every function yourself. The script cannot do that.

**Fix only what is wrong.** If no story is deeper than one level, the code already reads top to bottom. Do not rewrite its stories. Propose only the moves `--check` names, plus what it cannot see (duplicated chunks, codes written as literals, long conditions: rules 5 to 7 of `references/style.md`), or stopping.

If the target holds more than one task, split it into units, one task each, and give each task its own file (layout in `references/style.md`). A task is one step of the business flow, such as drafting a document or issuing the final one. A task owns its job body and every entry point whose only work is to start or queue that step, even when the caller lives elsewhere. The actions a team takes to repair stuck steps (retry, unlock) together form one task. Code that runs at different steps is different tasks even when it looks alike. Variants of one product made at the same step (by type, by company) are one task with a branch. A task may have several entry points, and they share its file. Write the plan into `map.md`: task → entry points → file. Suggest `apply` for each unit:
- `replace` fits a small unit with few callers, or a unit that defines self-registering code.
- `v2` fits a unit with many callers, callers in several packages, or a risky flow (money, documents sent outside).

Read the project's lint and CI configuration (for example ruff, pylint, flake8, Sonar, eslint, golangci-lint). Write into `map.md` every limit the project has set and enforces on function size, complexity or duplication. A tool's default that the project never configured is not a limit. If a story would break an enforced limit, do not split the story or silence the tool on your own. Ask at the gate and offer three choices:
- silence that one check at that place, with a reason, if the project allows it,
- split the story into step functions that are leaves. Some decisions then move into the steps, and the report must say so,
- leave the configuration to a human.

**Gate:** `<work>/map.md` exists, and the user has approved the units, the file and the `apply` of each, and how to meet any enforced lint limit.

### 2. Clone

- `v2`: copy the original to the V2 location. Put `_v2` once, on the outermost thing copied: a folder → `utils_v2/`, a file → `doc_v2.py`, a file that becomes several task files → a package `doc_v2/`, a function or a class → `build_preview_v2`. Names inside keep their original names. The V2 must not import anything from the old code.
- `replace`: also copy the original byte for byte to `<work>/before/` and record its hash. Never edit that copy.

**Gate:** the copy imports.

### 3. Record the baseline

Write `<work>/scenarios.py`. Give every public entry point at least three scenarios: a success, a business error, and a failed outbound call (a timeout or an error response). Everything outside the unit is a stub: other project files, the database, HTTP, storage, queues, time, uuid, randomness. Only the standard library and allow-listed modules (pure computation, no I/O) run for real. Never connect to a real service or database.

Mark the stubs of pure computation, such as formatting a date or a number, with `.pure()`: a rewrite may call them a different number of times, and that is not behavior.

Record the original into `<work>/recordings/original.json`. Record the untouched copy as well, then diff the two. Flags and the scenario format: `python scripts/parity.py --help`.

**Gate:** the copy's diff is empty, which proves the harness works. Every outbound call in the map is reached by at least one scenario, or the report says why it is not. `parity.py coverage` lists the ones no scenario reached.

### 4. Rewrite stand-alone

Reshape the copy by following `references/style.md` and the traps in `references/<language>.md`. Mark what you cannot settle now:
- `PIN(integrate): <what>`: must be done when the new code takes over, such as an import, a task name or a test path.
- `PIN(behavior): <what>`: something odd or buggy that you kept unchanged.

Write pins in the language's comment syntax, spelled exactly like this so they can be searched.

### 5. Verify

- Record the rewrite and diff it against `original.json`. Give each file of a rewrite split into task files as its own `--unit`, so the same scenarios find each entry point in its new file. **The diff must be empty.**
- Run `python scripts/jump_depth.py <rewrite> --root <import root> --usage <repo dir> --check`. For a V2 add `--forbid <old module> --public-from <old module>`: nobody imports a V2 yet, so its public names come from the old module. It fails unless: unit-local depth ≤ 1, project inheritance ≤ 1, no state passed between methods through `self`, every import inside a function has a reason comment (only an import that breaks a circular import may stay there), a V2 imports nothing from the old code, and the layout holds: a function called from its own file sits directly below its only caller there, the functions of `shared.py` never call each other, and no `__init__.py` holds code or re-exports names (no facade).
- The public surface keeps its names and signatures, except changes the user approved for a V2 (see Refactor rules).

**Gate:** all checks pass. Reading the code is not verification. If a check cannot run, write that in the report and stop.

### 6. Report

Write `<work>/report.md` (see Report). If you cannot write it (some environments do not let a subagent write reports), put the whole report in your final message and say that the file was not written. Stop here. The next steps need the user.

### 7. Integrate (`replace` only, after the user approves)

Write the rewrite over the original and resolve every `PIN(integrate)`. Then verify again:
- record the original location and diff it against the recording of `before/`,
- import every production module that imports the unit,
- run the existing tests. List failing tests. Never edit a test to make it pass.

**Gate:** the diff is empty, no `PIN(integrate)` is left, and the report and checklist are updated.

## Mode `migrate`

1. Read the report and regenerate the checklist with `python scripts/jump_depth.py --callers <old module> --usage <repo dir>`.
2. Before moving anything, record the old code and the V2 again and diff them. A difference means someone changed the old code after the V2 was made. Stop and report it.
3. Move only the callers the user picked. Change the import or the call site and nothing else. Resolve the `PIN(integrate)` items that belong to those callers.
4. Import the changed modules and run the existing tests.
5. When the checklist is empty and the user approves: turn the recordings into the V2's own regression test, delete the old code and the tests that patched its internals, and run the tests.

**Gate:** the checklist in the report is updated.

## Mode `new`

1. **Find what to reuse.** Search for existing helpers, clients and constants the feature needs. Code used elsewhere is a leaf: call it, never copy it in, never reshape it during the feature.
2. **Skeleton.** Write the header map and each entry point as numbered step headings with no bodies yet, one file per task (layout in `references/style.md`). Framework-facing code stays thin and calls the story.
   **Gate:** the user approves the skeleton.
3. **Fill** each step by following `references/style.md`.
4. **Test** the way the project normally tests. In Python you can also record the outbound calls with `parity.py` and put them in the report, so the user can review the payloads.
5. **Verify** with `jump_depth.py --check` against the same limits as refactor step 5. Run it with `--similar <repo dir>` as well: a helper you wrote that looks like an existing one must be replaced by that one, or the report says how it differs.
6. **Report**, ending with the checklist of wiring that is left: routes, settings, and anything only a human may do, such as migrations.

## Refactor rules

- **Never change behavior, even to improve it.** For example `None` → `"-"`, closing a file, fixing a hidden bug, removing an import that looks unused. Pin it and report it.
- **Never delete code, even code nothing calls or no caller can reach:** a function, a parameter, a branch. It may be called by name (task names, URL config, `getattr`, templates) or from outside the repository, and a branch no caller takes today may be taken tomorrow. When you inline a helper, carry every branch with it: a parameter no caller passes becomes a local variable set to its default, and its branch stays right below, for example `cleanup = ()` then `if cleanup:`. Mark it `PIN(behavior): no caller found` and list it in the report. A pin never replaces code: the pinned code is still there. Merging a chunk that repeats whole within one flow (the same lookup and check twice in a row once two helpers are inlined) is rule 6 of `references/style.md`, not a deletion. List each such merge in the report.
- **The public surface stays:** same names, same signatures. Only a V2 may differ, and only per function the user approved. Then the report states how each caller converts its arguments, and the scenarios call the V2 through that same conversion. Outputs never differ: the return value, the raised error, and every outbound call in order with its payload.
- **No facade.** When a unit becomes several task files, each name moves to its file and callers import it from there. Changing those imports is a `PIN(integrate)` item: done in mode `migrate` for `v2`, and in step 7 for `replace`.
- **Tests are not the public surface.** Tests that patch internals will break. List them, and do not keep a split-up structure just for them.
- **Names survive inlining** as step headings or as names of result variables (see `references/style.md`).
- **Self-registering code must never be active twice.** This covers task decorators, signal receivers and schedules. With `v2`, pin it and plan it in the report. Prefer `replace` for such units.

## Report

`<work>/report.md` contains:

1. **Entry map:** entry point → numbered steps → outbound calls → where each payload is built (`file:line`).
2. **Function map:** old name → new place (inlined into step N, merged with a duplicate, kept as a leaf, or made private).
3. **Numbers before → after:** functions, max depth, functions a reader may need to open, hidden imports, project inheritance, state passed between methods.
4. **Parity:** scenarios per entry point, the diff result, outbound calls never reached.
5. **Behavior pins:** bugs, oddities and code with no caller, kept as they were.
6. **Not verified:** anything the checks could not cover.
7. **Checklist.** Always last, in every mode, whoever does the migration. Generate it from a code scan. Never tick it by hand.
   - `v2`: callers still on the old code (`file:line`), open `PIN(integrate)` items, tests to delete with the old code, and the next command: `/readable mode=migrate <report>`.
   - `replace`: failing tests, and `PIN(behavior)` items waiting for a decision.
   - `new`: wiring left, and actions only a human may take.

## Languages and tools

The process and `references/style.md` apply to any language. `scripts/` read **Python only** and need Python 3 (standard library only). For another language, do the map with search tools and build the stub harness with that language's own test tools, for example module mocks in vitest or jest, or interfaces and fakes in Go. The report must then say that the parity harness was hand-built. Language traps exist only in `references/python.md` for now.

## Red flags (seen in baseline runs without this skill)

| Thought | Reality |
|---|---|
| "Tests patch these internals, so I must keep them" | Tests are not the public surface. List them and go on. |
| "I verified it by reading carefully" | That is not verification. Run parity, or report the change as unverified. |
| "A small fix on the way" | That is a behavior change. Pin it and report it. |
| "Remove the unused import" | It may be public surface. Check its usage first. |
| "Nobody passes this argument, so I can drop the branch and pin it" | Keep the branch, with the argument as a local variable set to its default. A pin marks code, it does not replace it. |

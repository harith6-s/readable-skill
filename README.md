# readable

> An Agent Skill for Claude Code that arranges the code of one task (a request, a background job, a command) so it reads top to bottom in one place, without changing its behavior. It works both when reshaping existing code (refactor) and when writing a new feature.

**Version 1.1** · Python 3.10 or newer · tested on Django projects · the scripts use only the standard library

## What problem it solves

When code is split into many small functions, the reader jumps from line 74 to 145 to 300 and forgets what was left open at 74. Sometimes they cannot even find which function is the starting point. People hold about 4-7 things in mind at once, so several levels of nested jumps are too much.

The problem comes from real work. The Django code of a system in production has two extremes:

| | File A | File B |
|---|---|---|
| Shape | bloated but reads in a straight line | split into many small functions |
| Functions | 12 | 50 |
| Depth from the entry point | 1 | 3 |
| Functions a reader may need to open | 7 | 45 |
| Problem | the same chunk repeated in 5 places, conditions nested inside a payload | one payload assembled from 9 functions and 10 uses of `**` |

If you simply tell an AI "refactor this to make it readable", it splits out more functions, which makes both files deeper (see [Test results](#test-results)).

## What this skill does

It is a **process with gates**, not a list of tips. Every step needs evidence (a file or a command result) before the next one starts, and it never runs by itself: you call it with `/readable` every time (`disable-model-invocation: true` is set, because it touches many files).

| mode | Use when | Steps |
|---|---|---|
| `refactor` | reshaping existing code | Map → Clone → record the baseline → rewrite → verify → report (→ Integrate, only for `apply=replace`) |
| `migrate` | moving callers from the old code to the V2 | read the report → compare the old code and the V2 again → move only the chosen callers → run the tests → delete the old code when the checklist is empty |
| `new` | writing a new feature | find what can be reused → skeleton (the user approves) → write → test → verify → report |

The rules it decides by (details in `references/style.md`):
- The entry point is the story: numbered steps in the order they really run.
- At most one level of jump. A task's helper must be a leaf and must not call another helper.
- Every decision (branch, raise, outbound call, DB write) is in the story.
- A payload that is sent out is one literal at the point where it is sent. Never assemble it with `**`, and keep the key order.
- Never change behavior, even to improve it. When you meet something odd, pin it with `PIN(behavior)` and report it.
- Never delete code, even if nobody calls it. Keep it and pin it.
- One file per task (one step of the flow). What several files use lives in `shared.py`, whose functions do not call each other. There is no facade: callers import from the real file.

## Structure

```
readable/
├── SKILL.md              the process and the gates (in English, this is what the AI reads)
├── references/
│   ├── style.md          what the code should look like, the stance on clean-code advice, examples
│   └── python.md         traps of Python/Django when moving or inlining code
├── scripts/
│   ├── jump_depth.py     map and numbers of a unit: depth, outbound calls, callers, --check
│   └── parity.py         stubs everything outside the unit, then records and compares behavior (record, diff, coverage)
├── eval/
│   ├── reader.py         the budget-limited reader, to measure whether the code really became easier to read
│   └── reader_prompt.md  the prompt of the AI reader
├── CHANGELOG.md
└── README.md
```

## Install

You need Claude Code and Python 3.10 or newer (tested on 3.12). No extra package is needed.

```bash
# for one project
git clone https://github.com/harith6-s/readable-skill.git .claude/skills/readable

# or for every project
git clone https://github.com/harith6-s/readable-skill.git ~/.claude/skills/readable
```

- The folder name must be `readable`, to match `name` in `SKILL.md`.
- If the project is already a git repo, use `git submodule add <url> .claude/skills/readable` instead, or put `.claude/skills/readable/` in `.gitignore`. Otherwise the project's repo sees this folder as an embedded repo and does not track the files inside.
- Reopen Claude Code and `/readable` appears in the list of skills.
- `disable-model-invocation` and `argument-hint` in the frontmatter are Claude Code extensions. To use the skill with another tool that accepts only the standard Agent Skills fields, delete those 2 lines (the skill can then be invoked on its own when the description matches the task).

## Usage

### In Claude Code

```
/readable mode=refactor app/billing/services.py
```

The AI maps the file, then stops at the Map gate for you to approve the units and `apply` before it writes any code. When it finishes you get a V2 beside the original file (the original is untouched) and a `report.md` that says who still calls the old code. Then move the callers with `/readable mode=migrate <report.md>`.

```
/readable mode=refactor <file or folder> [apply=v2|replace] [out=<path>] [work=<folder>] [layout=A|B|AB] [depth=1-3] [style=auto|function|class]
/readable mode=migrate <report.md>
/readable mode=new <what to build and where>
```

### Use the scripts yourself, without Claude

```bash
# map and depth (run from the root of the repo)
python .claude/skills/readable/scripts/jump_depth.py <file> --root <import root> --usage <repo dir>
python .claude/skills/readable/scripts/jump_depth.py <new file> --root <import root> --usage <repo dir> --check

# record the behavior at the system boundary of the original and of the new version, then compare
# (run from the import root, for example application/ of a Django project)
python <skill>/scripts/parity.py record --unit <file> --root . --scenarios scenarios.py --out original.json
python <skill>/scripts/parity.py diff original.json new.json
```

All the flags and the scenario format are in the `--help` of each script.

### Input / Output

| Input | Meaning | Default |
|---|---|---|
| `mode` | `new`, `refactor`, `migrate` | required |
| target | `refactor`: a file or folder · `migrate`: the path of the report · `new`: what to build and where | required |
| `apply` | `v2` writes the new code apart, the original is untouched / `replace` overwrites after approval | `v2` |
| `out` | where the new code goes | beside the original, named with `_v2` |
| `work` | folder of the evidence | `docs/readable/<unit>/` |
| `layout`, `depth`, `style` | file layout, how deep a payload must stay visible, class or function | `A`, `3`, `auto` |

Output (mode refactor):
- The new code (V2), with the same public surface.
- `map.md`, the map of the task: entry points, callers, outbound calls, units, and the limits the project's lint enforces.
- `scenarios.py` and `recordings/`, the evidence that behavior is the same.
- `report.md`: the map of entry points, where each old function went, numbers before/after, the parity result, pins, what was not verified, and a **checklist** (callers still on the old code with `file:line`, open pins, tests to delete) that is generated from a scan of the code and never ticked by hand.

## Workflow (mode refactor)

1. **Map:** `jump_depth.py` finds the entry points, callers, outbound calls and the helpers other code shares, then divides the code into units. It also reads the limits that the project's lint/CI enforces.
   **Gate:** `map.md` exists and the user has approved the units, the `apply` of each unit, and how to deal with lint.
2. **Clone:** copy to a V2 (or keep a copy before editing, for `apply=replace`).
   **Gate:** the copy imports.
3. **Record the baseline:** write at least 3 scenarios per entry point (success, business error, an outbound call that fails). Everything outside the unit is a stub, and nothing connects to a real DB or service.
   **Gate:** the diff of the copy is empty (which shows the tool works) and every outbound call is reached by a scenario.
4. **Rewrite** by `references/style.md`. Pin what you cannot decide yet with `PIN(integrate)` or `PIN(behavior)`.
5. **Verify:** the diff against the original must be empty, `jump_depth.py --check` must pass, and the public surface must be the same.
   **Gate:** every check passes. Reading the code does not count as verification.
6. **Report:** write `report.md`, ending with the checklist, then stop and wait for the user.
7. **Integrate** (only `apply=replace`, after the user approves): overwrite the original, then verify again and run the existing tests.

Modes `migrate` and `new` have their own steps and gates in `SKILL.md`.

## Which projects it works on

| Project | 1.x |
|---|---|
| Python 3 that is not async, any framework (Django, Flask, a service or a plain script) | supported. Tested on a real Django project; other kinds have not been tried |
| Python that makes outbound calls with `await` (FastAPI, aiohttp) | not supported yet. The skill stops at the Map step |
| Other languages | not supported in 1.x. The skill stops at the Map step |

- The examples in `references/style.md` are made-up code, not tied to any project.
- If the project sets an enforced lint limit on function size or complexity, the skill asks at the Map gate and does not switch the lint off by itself. (A tool default that the project never configured does not count.)
- If the repo holds copies of the code under study, have `jump_depth.py` skip them with `--exclude <folder>`.

## Limits

- **Slower and more expensive:** one run uses about 1.85 times the tokens and about 2.4 times the time of an AI without the skill.
- **A file that is already flat:** 1.1 lets the Map step fix only what `--check` says is wrong, but this has not been retested on such a file.
- **Existing tests that import internals will break on migrate:** the skill does not count tests as public surface. The report lists the tests that must be fixed.
- **The test results come from one run per setup,** and the reader scores were given by a tester who was not blinded.
- **It does not touch code tied to a framework** (views, serializers, models, routing, migrations), on purpose.
- **Calls made by name at run time** (`getattr(obj, name)()`, a dict that holds functions) are invisible to `jump_depth.py`. The depth numbers will be lower than the truth.
- **Every external library is replaced by a stub** unless you pass `--allow`. Code that computes heavily with a library (such as pandas) must be allowed first, or the comparison means nothing.
- **parity checks at the system boundary:** the outbound calls with their payloads, the return values and the errors. It does not check what a real database would hold, and it covers only what the scenarios cover.
- All the known problems are in `CHANGELOG.md`.

## Test results

### Round 1 (1.0): method

- **Targets:** file A (already flat) and file B (split into too many functions) from a Django project in production.
- **Comparison:** an AI without the skill against an AI with the skill, both Sonnet and Opus, with the same prompt letter for letter, a new agent for every run, and the gates approved in advance so that code could be measured.
- **Gate test:** one more run without approving in advance, to see whether it really stops at the Map gate.
- **Two layers of measurement:**
  1. The numbers from `jump_depth.py`, and parity with scenarios that the tester wrote (7 for file A, 6 for file B), not scenarios written by the agent.
  2. A budget-limited AI reader (`eval/reader.py`): it can open one function at a time, at most 8 times, and answers 6 questions whose answers were confirmed from real recordings. Haiku and Sonnet were used.
- It used skill-creator's test setup (`benchmark.json`, the review page).

### Round 1: results

| | without the skill | with the skill |
|---|---|---|
| Passed every criterion (4 runs × 6 criteria) | 14/24 = 58% | **22/24 = 92%** |
| Behavior unchanged (parity) | 4/4 | 4/4 |
| Depth at most 1 | **0/4** | **4/4** |
| Stops at the Map gate when not approved | - | really stopped |
| Average cost per run | 162k tokens, 9.4 min | 299k tokens, 22.4 min |

| | original | without the skill (Sonnet / Opus) | with the skill (Sonnet / Opus) |
|---|---|---|---|
| File A: depth / functions that may need opening | 1 / 7 | 4 / 25, 4 / 26 | 1 / 12, 1 / 10 |
| File B: depth / functions that may need opening | 3 / 45 | 4 / 49, 3 / 53 | 1 / 28, 1 / 29 |
| File B: imports hidden inside functions | 21 | 21, 21 | 5, 5 |
| Reader on file A, Haiku: score (out of 12) / times opened | 12 / 1 | 10 / 7, 12 / 7 | 12 / 4, 12 / 4 |
| Reader on file A, Sonnet | 12 / 2 | 11 / 8, 12 / 8 | 12 / 4, 12 / 4 |
| Reader on file B, Haiku | 11 / 5 | 9 / 7, 11 / 8 | 12 / 1, 11 / 1 |
| Reader on file B, Sonnet | 11 / 8 | 11 / 8, 11 / 8 | 12 / 5, 12 / 6 |

Summary:
- An AI without the skill keeps behavior but makes the code **deeper** every time, because it reads "easy to read" as "split out more functions".
- The skill clearly helps on code that is split into too many functions (file B): the reader opens fewer functions and scores the same or better. The question that differs most is a condition that the original hides 3 levels deep but that the skill's version shows in the story.
- **On code that is already flat (file A), no version beats the original.** The skill's version beats the version without the skill, but it still splits files so the reader has to open more. This was the first problem to fix in 1.1.
- The readers of both models ranked the versions in the same order.

Limits of this set of results: one run per setup, reader scores given by someone who knew which answer came from which version (not blinded), and no results yet from a real human reader.

### Rounds 2-4 (1.1): files split by task

The maintainer reviewed the 1.0 results on file B and saw that the files should be split by task (making the draft document, making the final document, the work that repairs a stuck step). So 1.1 added a file-layout rule and made `--check` verify it. Every round used file B with Sonnet, one run each, and added a set of 3 questions about a single document across two stages (the draft stage and the signing stage), with an opening budget of 6. Every time the rules were adjusted, the new criteria were applied retroactively to every version in the same way.

| | 1.0 | 1.1 round 2 | 1.1 round 3 | 1.1 round 4 |
|---|---|---|---|---|
| What changed | - | file layout rule | the definition of a "task" | the never-delete rule made clear |
| Passed criteria (of 11) | 8 | 10 | 10 | **11** |
| Files | 2 | 6 (split too finely) | 4 | 4 |
| Every task in its own file | no | no | yes | yes |
| Kept the code nobody calls | no | yes | no | yes |
| Haiku reader, original question set: score / times opened | 12 / 1 | 12 / 4 | 12 / 5 | 12 / 5 |
| Haiku reader, per-document question set (out of 6) | 6 / 2 | 6 / 4 | 6 / 3 | 6 / 2 |
| tokens / time | 268k / 16.6 min | 272k / 14.4 min | 232k+ / 10.6+ min | 236k / 13.2 min |

The original of file B scored 11/12 (5 openings) on the original set, and **1/6** on the per-document set, because it spent its openings on the draft stage. The round-3 numbers cover only the period after the usage limit was hit. Round 2 also tested layout `AB`. It passed all 11 criteria from that round on, but it moved only the signing-stage builder into the document file and the draft stage stayed in the story, and the readers did about as well as with `A` (Haiku 12/2 and 5/6), so it was not clearly better. `A` therefore stays the default.

Summary:
- 1.1 round 4 followed every rule: files split by task, the code nobody calls kept, every payload visible whole at the point where it is sent, and behavior unchanged in every scenario.
- The readers scored full marks on every version of the skill, but splitting files did not make them open fewer files than 1.0, which is a single file. On the original set they opened more, because the reader opened `shared.py` to check again. This needs several runs before concluding.

The raw evidence (the code each run wrote, the parity recordings, the question sets and answers, the readers' answers) refers to company code, so it is not in this repo.

### Measure it on your own code

1. Have an AI without the skill and an AI with the skill refactor the same file with the same prompt, using a new agent every time.
2. Run `jump_depth.py` on the original and on every version, and compare `max_depth`, `local_depth` and the number of functions reachable.
3. Write the scenarios yourself, then use `parity.py record` on the original and on each version, and then `parity.py diff`.
4. The reader: run `eval/reader.py build` for each version, then give `eval/reader_prompt.md` to a new agent per version. Score with the answer key and see the number of openings from `reader.py report`.

## Versions and rollback

The version number is in `metadata.version` in `SKILL.md`. Every version is recorded in `CHANGELOG.md` and gets a git tag (`v1.0`, `v1.1`, ...) when it goes into `main`.

**How to tell whether a new version is better or worse:** run the same test set on the new version and compare it head to head with the old one (skill-creator calls them `new_skill` and `old_skill`). The new version must pass all of these:
- parity, public surface, and untouched original files: 100% pass, as before
- depth at most 1: 100% pass
- the gate test: still stops at Map
- the readers (Haiku and Sonnet): the score does not drop and the number of openings does not rise
- cost: does not rise beyond what was agreed
- at least 2 runs per set before concluding, because AI results fluctuate

**Rollback:** if you installed with `git clone`, run `git checkout v1.0` in the skill's folder. With a submodule, check out the tag in the submodule and commit in the project.

## References

- Martin Fowler, *Refactoring* (2nd ed., 2018): the definition of refactoring as changing structure without changing behavior, and Inline Function.
- Michael Feathers, *Working Effectively with Legacy Code* (2004): a characterization test records the existing behavior, including the wrong parts, before changing it.
- Martin Fowler, [Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html) and Danilo Sato, [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html): where "write the V2 first, then move the callers" comes from.
- John Ousterhout, *A Philosophy of Software Design*: deep and shallow modules, and [the debate with Robert Martin](https://github.com/johnousterhout/aposd-vs-clean-code) about the length of functions.
- Anthropic skill-creator and superpowers `writing-skills`: how to build and test a skill (run a baseline before writing, compare with and without the skill).

# CHANGELOG

The version is in `metadata.version` of `SKILL.md`. Every version must pass the existing test set before it gets a new number (see "Versions and rollback" in `README.md`).

- **1.x** = fixes and improvements where the input and the steps stay the same
- **2.0** = changes to the input, the modes or the gates (people who call the skill must change how they call it)

## 1.2 (2026-11-08)

- **`parity.py record` refuses async code (known problem 10):** if any file of the unit contains `async def`, it exits 1, names the `file:line` of each one, and writes no recording. It no longer depends on the AI stopping at the Map step by itself. Supporting async is still known problem 7. The test pair in `tests/test_parity.py` has been swapped, and `tests/test_examples.py` checks that `async_jobs` is refused.
- **A leaf whose callers are all in one file sits at the end of that file (maintainer decision, 2026-11-08):** `style.md` and `jump_depth.py --check` used to send a helper with two or more callers to `shared.py` even when all the callers were in the same file. So `statements`, a one-task unit, became a package in both rounds. Now `shared.py` holds only leaves that are called from two or more files, which matches the original layout A decision. `--check` verifies that such a leaf sits below all its callers and that only leaves of the same kind follow it.
- **Options at a gate (maintainer decision, 2026-11-08):** the first option must follow `style.md`. An option that breaks a rule is marked `breaks rule N` with the reason. If the user picks it, the report lists it together with the PIN(behavior) items. Added a row to the red flags (`orders` round 2 offered copying the refund chunk into both stories as its first option).
- **A chunk merged by rule 6 may make outbound calls (maintainer decision, 2026-11-08):** rule 3 of `style.md` used to say every outbound call must be in the story, but rule 6 gives "call a service and map its errors" as an example of a chunk that may be merged. In rounds 2-3 the agents read this differently (write the refund twice in two files, or merge it into a leaf). Rule 3 now has an exception: a merged leaf must be named for what it sends, return a result, and leave the decision to the story.
- **Names that nothing imports (maintainer decision, 2026-11-08):** a top-level name without a leading underscore that nothing in the repository imports must be listed at the Map gate, and the user is asked whether anyone outside the repository uses it. If the user does not know, it counts as public (in round 3 the two `statements` runs read this in opposite ways: drop the classes, or keep them).
- **After round 4 (maintainer decision, 2026-11-08):** a class that may be public and passes state between its methods through `self` must be called out at the Map gate, saying that check will not pass (in round 4 the agent only learned it at Verify). Added two red-flag rows: each entry point is its own story, never move the whole story into a central function that takes a value or a flag; and never offer a way around a gate, such as a V2 without parity.
- **After round 5 (maintainer decision, 2026-11-08):** in a public class, a call from one public method to another is behavior (a subclass may override the method). Never inline a public method; only private methods may be inlined. The Map step also says the depth of such a class may stay above 1 (in round 5 the agent inlined `load`/`validate`/`post` into `run` of a class counted as public).
- **Round 6 (2026-11-08):** the English `references/python.md` was read by an agent for the first time (`orders`, 11/11), and decision 18 held (`statements` with unknown outside use kept every public method). The golden answer of `statements` was added for the answer "nobody outside uses the classes". `README.md` structure section now lists `tests/`, `examples/`, `eval/` and `DEVELOPING.md`, and the skill is now version 1.2.
- **Cause of known problem 4:** Claude Code does not let a subagent write a report file with the Write tool. This happens only when the skill runs as a subagent. The existing fallback (put the report in the final message) is correct, so the skill is unchanged.
- **`eval/grade.py`:** added checks 12 (state through `self`, inheritance), 13 (rule 6, repeated chunks) and 14 (rule 7, status codes), and fixed `targets()`, which scanned the whole old package when the V2 was a single file. The `orders` golden answer was fixed to follow rules 3, 6 and 7.
- **All documentation is in English (maintainer decision, 2026-11-08):** removed `th/` (the Thai translations of `SKILL.md` and `style.md`) and translated `README.md`, `CHANGELOG.md`, `DEVELOPING.md`, the folder READMEs and `references/python.md` into English. Note for the evidence: every test round up to now ran with the Thai version of `references/python.md` and the English `SKILL.md` and `style.md`. The English `python.md` has the same content but was not tested by an agent run.

## 1.1 (2026-11-07)

Fixes for the known problems of 1.0 and for the maintainer's code review (2026-11-07).

- **File layout (layout A):** one file per task. A task is one step of the flow, including every entry point that only starts that step or queues it. What the team does to repair a stuck step (retry, unlock) is one task. (The first definition, "a task = what one command runs", made round 2 split the files too finely, so it was changed on 2026-11-07.) Code that runs at different steps is a different task even when it looks alike. A helper with one caller sits directly below that caller. What several places use lives in `shared.py`, whose functions do not call each other. A function that decides is a story and, however short, must stay in the task file. No facade: callers import from the real file (known problem 1).
- **Map step:** run `--check` on the original to say, with numbers, what is wrong now. If no story is deeper than 1 level, fix only what is named and do not rewrite the stories (known problem 1). Plan task → entry point → file and have the user approve it.
- **`jump_depth.py --check`:** checks the layout too. A jump inside one file may only go down to a helper that sits below its only caller. Functions in `shared.py` do not call each other. `__init__.py` holds no code and does not re-export.
- **`parity.py`:** added `.pure()`, so a stub of pure computation is not recorded (known problem 2). The project's ALL_CAPS constants take their real literal value from the source (read with ast, the module is not run), so turning a literal into a constant is no longer counted as a behavior change (known problem 3). `h.unit` finds a name in every `--unit`, choosing the module that defines it, so one scenario set works for the original and for code split into task files.
- **SKILL.md:** the Verify step of a V2 uses `--public-from <old module>` (known problem 4). If `report.md` cannot be written, put the whole report in the final message (known problem 5). Never delete code, even code nobody calls: keep it and pin it `PIN(behavior): no caller found` (known problem 6).
- **frontmatter (known problem 7):** kept `disable-model-invocation` and `argument-hint`, because this skill is shared for use in Claude Code. README says how to remove them for other tools.
- Tested: `.pure()` and the constants on a sample unit; the round-1 parity is still empty when recorded with the new `parity.py` (file B with the Sonnet skill, and file A with the Opus skill, which no longer needs the constants set by hand); `--check` catches the layout problems of both original files and of round 1.
- **Round 2 (2026-11-07, RC, Sonnet):** 1.0 passed 8/10 (failed on file layout), 1.1 layouts A and AB passed 10/10. AB was no better than A (it moved only the signing-time builder, the draft builder stayed in the story), so A stays the default. Layout B was not tested.
- **Round 3 (2026-11-07):** after fixing the definition of a task, A produced 4 files (`preview.py`, `confirmation.py`, `repair.py`, `shared.py`) and passed 10/10, including the criterion "one task in one file" that the run before the fix had failed.
- **The never-delete rule made clearer (2026-11-07):** a round-3 run removed the `cleanup` branch that nobody called and pinned it instead (1.0 removed it too, while round 2 kept both). So SKILL.md now says how to keep it when inlining: a parameter nobody passes becomes a local variable set to its default, and the branch stays right below it. A PIN may mark code but never replace it. Added a row to the red flags and fixed the "takes a flag" row in style.md, which used to say to inline each branch into the caller and so allowed dropping a branch the caller does not use. Test criterion 11 checks that `if cleanup` is still there.
- **Round 4 (2026-11-07):** A passed 11/11, kept `if cleanup` in both tasks, and was the first round in which all 5 payloads at signing time were one literal at the point where they are sent.
- **Chunks that repeat within one flow (maintainer decision, 2026-11-07):** merging a chunk that repeats whole within one flow, for example a lookup followed by a "signature not found" check that the original had in 2 functions and whose second copy became unreachable after inlining, follows rule 6 and does not count as a deletion. It must still be listed in the report (the function map has "merged with a duplicate").

- **Scope of 1.x = Python only (maintainer decision, 2026-11-07):** the scripts need Python 3.10 or newer. If the target is in another language, or makes its outbound calls with `await`, stop at the Map step. The description says it is for Python, and README has a table of what is supported.
- **`jump_depth.py --exclude`:** the script used to skip folders named `compare/`, hard-coded, which leaked in from the experiments. Another project with a folder of that name would get an incomplete list of callers. Now nothing is skipped unless asked, and folders can be skipped by name or by path.

### Known problems (to look at in 1.2)

1. The Map step "fix only what is wrong" has not been retested on a file that is already flat (file A of round 1). Rounds 2-4 tested only file B.
2. Layout `B` has not been tested. `AB` in round 2 was no better than `A`, because it moved only the signing-time builder.
3. The AI reader opened more files with the original question set than with 1.0 (5 times against 1), because it opened `shared.py` to check again. It must be run several times before concluding that splitting files really makes reading slower.
4. Some environments do not let a subagent write `report.md`. The fallback works (round 2) but the cause was not investigated.
5. Existing tests that import internals will break on migrate (about 20-25 names in file B), because tests do not count as public surface. This is intended, but the user should be told at the Map step.
6. Every variant was run once, and the reader scores were given by a tester who was not blinded.
7. Async Python is not supported, because the stubs of `parity.py` cannot be used with `await`.
8. Not tested on a Python project that is not Django.
9. The scripts have no test suite of their own, so every change needs a manual check. (Plan: a fixed set of exam cases that works on Python immediately and is the base for other languages in 2.0.)
10. **(Most serious)** `parity.py record` on `async def` code that `await`s records the result as a coroutine and exits 0. Any rewrite then passes parity without anything being measured. For now it relies on the AI stopping at the Map step by itself (`tests/test_parity.py` KnownLimits).
11. `getattr(stubbed_module, name, None)` never returns `None`, so the "not found" branch cannot be tested with parity (`tests/test_parity.py` KnownLimits).
12. A Django-style `tests.py` counts as a production caller, because `is_test_file` knows only `test_*.py`, `*_test.py` and the `tests/` folder (`tests/test_jump_depth.py` KnownLimits).
13. For code that calls by name at run time, the map cannot see what is called, so `--check` says OK. The skill already says to trace those by hand in `map.md` (`tests/test_examples.py`).
14. `style.md` does not say where constants (status codes) live. In round 6 an agent read "`shared.py` holds only leaves" as forbidding them there and proposed literals. The tester ruled that constants may live in `shared.py`; the text is not changed yet.
15. Step 2 (Clone) does not say where the copy of a unit that becomes a package lives (round 6, `orders`).
16. `eval/grade.py` does not check rule 1 (the entry point is the story) or decision 18 (never inline a public method of a public class).

## 1.0 (2026-11-06)

The first version, which passed test round 1 (see "Test results" in `README.md`).

- 3 modes: `new`, `refactor`, `migrate`. Every step has a gate that needs evidence in a file.
- `apply=v2` (default) writes the V2 apart from the original, or `apply=replace` overwrites after the user approves.
- `references/style.md` what the code should look like, `references/python.md` traps of Python/Django.
- `scripts/jump_depth.py` map of the unit, jump depth, `--check`, `--forbid`, `--public-from`, `--similar`, `--callers`.
- `scripts/parity.py` records behavior at the system boundary with everything outside the unit stubbed, then compares (`record`, `diff`, `coverage`).
- `eval/reader.py` the budget-limited reader, to measure whether the code really became easier to read.

### Known problems (to fix in 1.1)

1. A file that was already flat (file A in test round 1) was split into several files, and the reader had to open 4 files instead of 1. The Map step should be able to say no restructuring is needed, and layout A should not have a facade in between.
2. `parity.py` counted calls to pure computation (for example `timezone.localtime`) as outbound calls. It needs `.pure()`.
3. `parity.py` replaced the project's module constants with placeholder text, so turning a literal into a named constant (rule 7) was counted as a behavior change. It should read the real value from the source.
4. SKILL.md did not yet say to use `--public-from <old module>` when checking a V2 (the script already supported it). A V2 that nobody imports yet therefore got a depth that was too high.
5. When run as a subagent, the system may not allow writing `report.md`. A fallback is needed: put the whole report in the final message.
6. 2 of 4 runs deleted code that nobody calls. The rule must be written clearly: **never delete, keep it and pin it `PIN(behavior)`** (decided 2026-11-06).
7. The frontmatter `disable-model-invocation` and `argument-hint` are Claude Code extensions, and skill-creator's validator (`quick_validate.py`) does not accept them. Packaging as a `.skill` file needs this handled first.

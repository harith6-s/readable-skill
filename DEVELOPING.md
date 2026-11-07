# Developing readable

This file is for a person or an AI who will keep developing this skill. It is not part of the skill (the skill is `SKILL.md`, `references/`, `scripts/`).

## Read before you start

If you are an AI that has just opened a new session in this repo, read these in order before doing anything:

1. This file
2. `CHANGELOG.md` (the "Known problems" section)
3. `SKILL.md`, then `references/style.md`

**Never create a `CLAUDE.md` in this repo.** The repo is cloned into `.claude/skills/readable` inside other people's projects, and a nested `CLAUDE.md` could be loaded into that project. Put notes for developers in this file.

### Agreements with the maintainer

- Reply to the maintainer in Thai; English technical terms are fine, no other language. This applies to the chat only. Everything written in the repo is in English (decision 19).
- Talk it through first. Never choose an option in the maintainer's place, and never write a file until you are told to.
- You may push back when an instruction does not make sense.
- git: so far the maintainer has run git every time. Ask before running any git command, unless the maintainer has said you may for the task at hand.
- This repo is public. Never put code, paths or values of a real company or project into it. Every example must be made up (`tests/test_examples.py` already checks some forbidden words).
- Report results truthfully: if a test fails, say so with the output; if you skipped a step, say so.

## Branch and version

- Develop on `dev`, then merge into `main` and tag `vX.Y` when the maintainer is satisfied (there was no `main` when 1.1 came out).
- The version is in `metadata.version` of `SKILL.md`, and the changes are recorded in `CHANGELOG.md`.
- `SKILL.md` and `references/` are written in English because an AI reads them. There is no translation (`th/` was removed on 2026-11-08; the old translations are in the git history).
- Since 2026-11-07 this repo is the only original. Before that the skill was developed in another project and rsynced here.

## Repo layout

| Part | Whose | What |
|---|---|---|
| `SKILL.md`, `references/`, `scripts/` | skill | the part that users of the skill actually get |
| `eval/reader.py`, `eval/reader_prompt.md` | measuring tools | the budget-limited AI reader |
| `eval/prepare.py`, `eval/grade.py` | measuring tools | make a copy for an agent, and grade a refactor with 11 checks (see `eval/README.md`) |
| `examples/` | developers | 5 synthetic projects of different shapes (see `examples/README.md`) |
| `tests/` | developers | tests of the scripts and the grader (see `tests/README.md`) |

**Open question:** `git clone` hands the developer folders to the users too. Today this does no harm, because Claude reads only `SKILL.md` and the files the skill refers to, and pytest skips folders that start with a dot. It does make the clone bigger. Whether to separate them is not yet decided by the maintainer.

## Decisions already made

Do not overturn any of these without asking the maintainer first.

1. **The skill is named `readable`.** The maintainer chose it and knows it is a common word. Do not suggest renaming.
2. **The skill is a process with gates, not a list of rules.** Only a person may invoke it (`disable-model-invocation: true`). It has 3 modes, `new`, `refactor`, `migrate`, and the default of `apply` is `v2` (write the new code apart from the old).
3. **Priority order:** correct > reads top to bottom > no duplication > short > fast. It may be slower only for work in memory. Never add a query or an API call.
4. **Layout A is the default.**
   - One file per task.
   - A **task** is one step of the flow, including every entry point that only starts that task or queues it.
   - Repair actions such as retry and unlock are one task.
   - A leaf called from two or more files lives in `shared.py`, and its functions do not call each other.
   - A leaf with several callers that are all in one file sits at the end of that file, below all its callers (maintainer confirmed 2026-11-08; the code used to send it to `shared.py`).
   - A helper with a single caller sits directly below that caller. One jump is acceptable.
   - **No facade.** Callers import from the real file. Fixing those imports is a `PIN(integrate)`.
   - Short does not mean it belongs in `shared.py`. A function that decides is a story.
   - Layout AB was tested: it passed every check the same way but was not clearly easier to read, so A stays the default. Layout B has not been tested.
5. **Never delete code,** even if nobody calls it. A flag nobody passes becomes a local variable set to its default, and its branch stays. A `PIN` cannot replace code.
6. **Merging a chunk that repeats whole within one flow follows rule 6.** It does not count as a deletion, but it must be listed in the report.
7. **Rule 6 (duplicated code)**
   - A merged leaf must not raise. It returns a result and the story raises.
   - A chunk counts as a duplicate only when it repeats whole.
   - A suspicious difference gets a `PIN(behavior)`.
   - A merged chunk may make outbound calls (for example calling a service and mapping its errors). Its name must say what it sends, it returns a result, and the story decides. Rule 6 beats rule 3 in this case (maintainer decision 2026-11-08).
8. **Parity** compares outbound payloads in order, and the handling of responses (success / business error / timeout), with everything outside the unit stubbed. It does not compare the DB.
9. **The public surface is counted from production code only.** Tests that import internals will break on migrate; this is intended. A top-level name without a leading underscore that nothing in the repo imports is asked about at the Map gate; if the user does not know, it counts as public (maintainer decision 2026-11-08). If a class that may be public passes state between its methods through `self`, the Map gate says that check will not pass, and the user chooses (maintainer decision 2026-11-08, after round 4).
10. **Linter:** a limit that the project really enforces (config or CI) must not be broken silently. If it has to be exceeded, ask at the gate.
11. **The examples in `style.md` are made up.** They are not cut from real code.
12. **The scope of 1.x is Python 3.10 or newer only.** For another language, or for async code, stop at the Map step.
13. **2.0 (many languages)** uses the Python scripts as the prototype, together with a fixed exam set (not pseudo code). Each language's adapter must pass that set before it is used.
14. **Three layers of measurement**
    - the numbers from `jump_depth.py`
    - the budget-limited AI reader (Haiku with low effort and Sonnet must give the same ranking)
    - a real person
    - A question set exists only to test the skill. The skill itself does not use it.
15. **The model used to run the refactor in tests is Sonnet.** Round 1 gave results close to Opus.
16. **A rule of `style.md` can be a gate option, but it must be labeled.** The first option must follow the rule. An option that breaks a rule is marked `breaks rule N` with the reason. If the user picks it, the report lists it together with the PIN(behavior) items (maintainer decision 2026-11-08).
17. **Each entry point is its own story,** even when two entry points do the same steps and differ only in values. Never move the whole story into a central function that takes a value or a flag. Only a chunk that repeats whole becomes a leaf, by rule 6 (maintainer decision 2026-11-08).
18. **In a public class, never inline a public method.** A call from one public method to another is behavior, because a subclass may override the method that is called. Parity cannot see it, because no such subclass exists in the repo. Only private methods may be inlined (maintainer decision 2026-11-08, after round 5).
19. **Everything written in the repo is in English** (maintainer decision 2026-11-08): the skill, the scripts, the tests, the examples and every document. The Thai translations (`th/`) were removed. Presenter notes in `doc/` are not part of the repo (`doc/` is in `.gitignore`). A string literal that is sample data, such as the Thai text in `examples/clean`, may stay.

## Status (1.1 released; 1.2 in progress, 2026-11-08)

- The results of test rounds 1-4 are summarized in `README.md`. The raw data and the code used for the tests belong to a company, so they are not in this repo and never will be.
- A test set that depends on nobody (`tests/`, `examples/`, `eval/grade.py`) was added on 2026-11-07. It now has 61 tests. All pass, and 1 of them is an expected failure that is intentional.
- `parity.py` refuses async code now (the 1.2 section of `CHANGELOG.md`).
- Until 2026-11-08 `references/python.md` was in Thai, so the agent rounds below read the Thai version of it. It is now in English with the same content, but no agent run has used the English version yet.

### Agents on `examples/`, round 1 (2026-11-08, Sonnet, with the skill, one run each)

All 5 passed according to their `shape`. The raw results were not kept (they were in the session's scratchpad). No original file was touched in any run (checked by hash).

| Example | Result | Context at the end / working time |
|---|---|---|
| `async_jobs` | stopped at Map before calling `parity.py` (it ran only `jump_depth.py`) | 52k / 34 s |
| `clean` | `--check` OK, proposed no moves, recommended stopping | 53k / 45 s |
| `plugins` | traced `on_created`/`on_deleted`, called through `getattr`, by hand in `map.md` and said so at the gate | 56k / 52 s |
| `statements` | `grade.py` 7/7, 14 scenarios, turned the classes into 2 functions, state through `self` 1 → 0 | 76k / ~2.7 min |
| `orders` | `grade.py` 9/9, 25 scenarios, 4 tasks matching the golden answer, kept the `notify`/`capture`/`cc` branches with PINs | 95k / ~4.8 min |

- The maintainer reviewed the code of `orders` and `statements` and could read it (the "real person" layer of measurement).
- At the Map gate the tester approved what the agent proposed without changing it, and answered only what a real user would know (the queue worker in `orders` was answered from `shop/api.py`).
- **A flaw in the method:** every run's workdir was in the same parent folder, so the `orders` agent could `ls` the file names of other runs (it did not read their content). Next time give each run its own parent folder.
- **A rule to decide:** `statements` has one task, but a chunk repeated in 2 functions of one file had to go to `shared.py` by the keep/inline/merge table of `style.md`. So the V2 had to be a package (`ledger_app.importer_v2.importer`), and readers jump across one more file.
- `clean` pointed out that the docstring has no header map (rule 9) but did not propose a fix. That is correct under SKILL.md (it may propose only what `--check` says, plus rules 5-7).
- The token number the harness gives is the context size at the end, not the total, and the time includes the wait at the gates (the table has it removed). It is not known whether the numbers of rounds 1-4 in `README.md` were measured the same way.

### Agents on `examples/`, round 2 (2026-11-08, Sonnet, 5 runs with the skill + 5 baseline runs)

Each run was in its own randomly named folder, and the round-1 results were compressed away before the start. The transcripts were checked: no run read outside its own folder, and no original file was touched in any run.
The baseline got the instruction of an ordinary user: "refactor X to make it easier to read, behavior must stay the same, write a V2 beside it, do not edit existing files". The `grade.py` numbers below use the 11 checks (round 1 was graded again with them).

| Example | with skill, round 1 | with skill, round 2 | baseline |
|---|---|---|---|
| `async_jobs` | stopped at Map | stopped at Map | wrote a V2 (variable name / docstring) and checked async with a script it wrote itself |
| `clean` | stopped, proposed nothing | stopped, proposed nothing | wrote a new V2 (templates in a dict) |
| `plugins` | stopped, traced the handlers by hand | stopped, traced the handlers by hand | wrote a V2 that turns `"on_"` into a constant, did not mention the handlers the map cannot see |
| `statements` | 7/7 | 7/7 | 5/7 (failed 04 depth, 12 state through `self`) |
| `orders` | 11/11 | 9/11 (failed 13: refund chunk repeated in 2 files, 14: statuses as literals) | 7/11 (failed 04, 07, 08, 14) |

Context at the end / working time in round 2: with the skill 51k-86k / 1-3.7 min, baseline 38k-47k / 0.8-1.4 min.

- With the skill, all runs stopped or said what they should in the 3 non-refactor examples, in both rounds. The baseline wrote a V2 for all 3.
- The baseline kept behavior (empty parity on both refactor examples) but did not restructure by the rules.
- In round 2, `orders` proposed at the gate, as its default, to inline the whole refund chunk into both stories. The tester approved what was proposed, although that breaks rule 6, and did not name constants for the statuses (rule 7). Round 1 did both correctly. Before checks 13-14 were added, `grade.py` gave both rounds 9/9.
- In round 2, `statements` proposed a leaf in the same file, `--check` did not pass it, and the agent moved it to `shared.py` itself, giving a package like round 1.
- The baseline could check async code with a test it wrote itself, while the skill stopped because `parity.py` does not support it yet (known problem 7).
- Found and fixed during this round: `grade.py` scanned the whole old package when the V2 was a single file in the old package; it did not check rules 6-7 (checks 13-14 were added); and the `orders` golden answer itself broke rules 3, 6 and 7 (totals computed in 2 files, `shared.refund` set statuses, statuses as literals). The golden answer is fixed.

### Agents on `examples/`, round 3 (2026-11-08, Sonnet, with the skill, 2 runs each of `statements` and `orders`)

Tested the rules after round 2: a leaf whose callers are in one file sits at the end of the file, and gate options must be labeled `breaks rule N`.

| Run | First option at the gate | `grade.py` | Context at the end / working time |
|---|---|---|---|
| `statements` A | drop the classes into functions (labeled keeping the classes as breaking rule 2 of "Class or function") | 7/7, one file, 2 leaves at the end | 73k / 2.8 min |
| `statements` B | keep the classes with `run` as the story (labeled dropping the classes as breaking "never convert a public class") | 7/7, one file | 76k / 2.8 min |
| `orders` A | leaf `_refund_payment` (labeled writing it twice as breaking rule 6) | 11/11 | 92k / 4.3 min |
| `orders` B | write the refund twice, one in each story, citing the rule order (labeled the leaf as breaking rules 3, 4) | 10/11 (failed 13) | 101k / 5.3 min |

- The new `shared.py` rule worked: both `statements` runs are one file (rounds 1-2 were packages).
- Every run labeled its options, but the labels of each pair were opposite, because the rules were ambiguous in 2 places. The maintainer has decided (decisions 7 and 9): rule 6 beats rule 3 for a merged chunk, and a name that nothing imports is asked about at the Map gate.
- Cause of known problem 4: Claude Code does not let a subagent write a report file with the Write tool (`Subagents should return findings as text, not write report files`). 2 of the 4 runs wrote it with Bash instead, and the other 2 put the report in the final message, which is the skill's fallback. It happens only when the skill runs as a subagent.
- `async_jobs`, `clean` and `plugins` were not rerun with the new rules.

### Agents on `examples/`, round 4 (2026-11-08, Sonnet, with the skill, 2 runs each of `statements` and `orders`, 1 run each of the others)

Tested the rules after round 3: the exception to rule 3 for a merged chunk, and asking about names that nothing imports. On `statements` the tester answered differently on purpose: A "I don't know" (must count as public) and B "nobody outside uses them".

| Run | Result | Context at the end / working time |
|---|---|---|
| `async_jobs` | stopped at Map, asked about names | 53k / 0.7 min |
| `clean` | stopped, proposed nothing, asked about names | 55k / 3.3 min |
| `plugins` | stopped, traced the handlers by hand, asked about names, labeled the option that changes behavior | 55k / 0.9 min |
| `orders` A | 11/11, leaf `refund_payment` | 94k / 4.7 min |
| `orders` B | 11/11, leaf `_refund_payment` | 103k / 5.0 min |
| `statements` A ("I don't know") | 6/7, kept the class and its methods as public; check 12 failed because `load`/`validate`/`post` pass `rows` through `self`; stopped and asked at the Verify gate | 85k / 4.9 min |
| `statements` B ("nobody outside uses them") | 7/7, but moved the whole story into `_import_statement(path, account, negate_amounts)`, leaving the entry points as pass-throughs; decided by itself during the rewrite | 76k / 3.5 min |

- The exception to rule 3 worked: both `orders` runs offered the leaf as the first option (round 3 had 1 of 2).
- Every run asked about names that nothing imports (`orders` said by itself that every name is imported).
- Both `orders` runs named constants for the statuses by themselves during the rewrite (rule 7), although it was not in the approved plan, and said so in the report.
- 3 new problems, rules fixed (maintainer decisions): a class that may be public and passes state through `self` must be called out at the Map gate (decision 9), each entry point is its own story (decision 17), and `async_jobs` offered "go on with a V2 without parity", so a red-flag row was added: never offer a way around a gate.
- `grade.py` does not check rule 1 (the entry point is the story), so it gave `statements` B 7/7.

### Agents on `examples/`, round 5 (2026-11-08, Sonnet, with the skill, 2 runs of `statements`)

Tested the rules after round 4. The tester answered about public names as in round 4: A "I don't know", B "nobody outside uses them".

| Run | Result | Context at the end / working time |
|---|---|---|
| `statements` A | said at the Map gate that keeping the class public means the state-through-`self` check will not pass; the tester chose to keep the class; it finished without stopping at Verify; 6/7 (check 12, as chosen) | 80k / 3.8 min |
| `statements` B | 7/7, each of the two entry points is its own story, leaf `_drop_zero_rows` at the end of the file, constants for the accounts | 73k / 2.3 min |

- The rules after round 4 worked: no central story that takes a flag, and the state-through-`self` problem of a class that may be public was called out at the Map gate.
- A new finding: A kept the class but inlined `load`/`validate`/`post` into `run` and left the old methods in place with no caller. A subclass outside the repo that overrides one of them would no longer be called (parity cannot see it), and the old chunk now exists twice. The agent pinned it and asked about it itself. The maintainer decided it as decision 18.

## Next tasks (in the agreed order)

1. What is left of 1.2: known problems 1-9 and 11-12; the golden answer (`golden/`) of `statements` (the round-3 result is one file now, and which version to use depends on the answer about public names at the Map gate); a question set for `orders`; update the "Structure" section of `README.md` to include `tests/`, `examples/`, `eval/grade.py`; run one agent on `statements` to test decision 18 and one with the English `references/python.md`.
2. Merge into `main` and tag `v1.1` when the maintainer is satisfied.

## Running the tests

```bash
python3 -m unittest discover -s tests
```

Python 3.10 or newer is needed, and nothing else has to be installed. If the scripts are not at `scripts/`, set `READABLE_SCRIPTS=<folder>`.

If you change a script, run this suite before saying you are done. If an expected-failure test turns into an "unexpected success", that limit has been fixed, so swap that test pair.

## Testing the skill with an agent

1. `python3 eval/prepare.py <example> <workdir>`. Keep the workdir outside the repo or in an ignored folder, and give each run its own parent folder.
2. Open a new subagent that starts from zero (general-purpose, not a fork, because a fork would inherit the conversation). Tell it to read `SKILL.md` itself, because the skill does not run automatically, then to work in the workdir, adding new files and never editing an existing one.
   - Copy only `SKILL.md`, `references/` and `scripts/` somewhere else, so the agent cannot see `case.json`, `golden/` or this file.
   - Pass a `work=` that is outside the workdir, because `grade.py` counts every new `.py` file in the workdir as part of the work, including `scenarios.py`.
   - Use the same prompt for every example, differing only in the target, tell it to end its turn at every gate, and answer the gate with SendMessage.
3. `python3 eval/grade.py <example> <workdir> --json <workdir>/grading.json`
4. Run a baseline (the same task without the skill) to compare, and keep the tokens and time of every run.
5. Run each variant more than once before concluding (known problem 6 in the CHANGELOG).

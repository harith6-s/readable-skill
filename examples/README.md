# examples: sample code that depends on nobody

Python code written for this purpose, using only the standard library. It holds no code or names of any company and needs no Django. Each folder is one test case:

```
examples/<name>/
  case.json      name, shape, original module, scenarios, tasks, kept_branches (branches nobody calls), written_once (chunks that must be written in one place), codes (status codes), expected result
  src/           the sample project (this is the import root)
  scenarios.py   scenarios for parity.py
```

| Example | shape | What it tests | Expected result |
|---|---|---|---|
| `orders` | refactor | one module holding the 4 steps of one flow, helpers nested 2 deep, 3 flags nobody passes, a chunk that repeats whole within one flow, a pure function called from several steps | split into one file per task + `shared.py`, empty parity; `golden/` holds the correct answer |
| `statements` | refactor | a class that passes work through `self.rows` + one subclass layer | `--check` must report no state through `self` after the rewrite; `golden/` is the answer for "nobody outside uses the classes" (one file, two stories). If the user does not know, the classes stay public and the V2 barely differs |
| `clean` | no-change | code that is already easy to read | the Map step proposes no moves and stops |
| `plugins` | list-by-hand | handlers called by name at run time (`getattr`) | the skill's user must list the handlers by hand in `map.md` and say so at the gate |
| `async_jobs` | unsupported | an `async def` that awaits | the Map gate says 1.x does not support it, and stops |

`clean` contains a few Thai string literals on purpose: they are sample data (a notice rendered in two languages), which also checks that non-ASCII text survives recording.

When async is supported in 1.2, change `async_jobs` to `refactor` (and change the test in `tests/` that checks that `parity.py` refuses async).

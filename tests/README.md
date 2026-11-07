# tests: the scripts test themselves

Nothing to install (Python 3.10+ and the standard library's `unittest`). Run from the root of the repo:

```bash
python -m unittest discover -s tests
```

| File | What it tests |
|---|---|
| `test_jump_depth.py` | depth, file layout rules (helper below its caller, `shared.py`, facade), hidden imports, `--callers`, `--exclude`, `--forbid`, state through `self` |
| `test_parity.py` | record/diff, refusing async code, constants from source, frozen time/uuid, stubbed network parts of the standard library, `.pure()`, task decorators, `coverage` |
| `test_grade.py` | the grader `eval/grade.py`: the correct golden answer (`examples/orders/golden`) must pass every check, and the golden answer broken one way at a time must fail only the check that is meant to catch it |
| `test_examples.py` | the shape of each `examples/*`: an example must record the same result twice (except shape `unsupported`, which must be refused), and no word that points to company code |

## Known limits (pinned both ways)

A test named `test_known_limit_*` pins the current behavior of 1.x, paired with an `@unittest.expectedFailure` test that states the wanted behavior.
The day the script is fixed, the `expectedFailure` test "passes unexpectedly": swap that pair.

| Limit | Where it is pinned |
|---|---|
| `getattr(stubbed_module, name, None)` never returns `None`, so the "not found" branch cannot be reached | `test_parity.KnownLimits` |
| Calls by name at run time: the map cannot see what is called, so `--check` says OK | `test_examples.Shapes` |
| A Django-style `tests.py` file counts as a production caller | `test_jump_depth.KnownLimits` |

Set `READABLE_SCRIPTS=/path/to/scripts` if the scripts are not at `../scripts`.

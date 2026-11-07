# Python / Django: traps when inlining

These are the places where moving or inlining code changes behavior without anyone noticing. Check every item before a rewrite.

## Control flow

- **`return` in a helper.** Once inlined, the `return` leaves the whole *caller*. Turn it into `if/else`, or keep the early exit only where the caller really has to end.
- **Scope of `try/except/finally`.** The `try` of the old helper covered only the helper's body. After inlining it must wrap exactly the same lines. If it gets wider, an error that used to escape is swallowed. If it gets narrower, an error that used to be caught escapes.
- **Order of evaluation.** Arguments are evaluated before the function is called. When inlining `f(a(), b())`, keep the order of the side effects of `a` and `b` (queries, API calls, uploads) exactly as it was.
- **Clashing variable names.** A local variable of the helper may overwrite a variable of the caller. Renaming a *local variable* in the inlined code is allowed, because it is not part of the API.
- **A variable set before a `raise` that an outer `except` reads.** For example `code = "81"` then `raise`, and an `except` at the end of the function returns `code`. If you extract this block into a helper, the assignment becomes a variable of the helper and the `except` sees the old value. Let the helper return the value and set the variable in the story (style.md, rule 6).

## Django

- **Lazy querysets.** A queryset runs when it is iterated, sliced, passed to `list()` or tested for truth. If inlining moves that moment before or after a write in the same flow, the result may contain different rows. Keep the original timing.
- **Scope of `transaction.atomic()`.** The statements inside and outside each atomic block must stay the same, line for line. `select_for_update()` can only lock inside an atomic block.
- **`transaction.on_commit(lambda: ...)` in a loop.** The lambda binds its variables when it runs, not when it is created. If you move it, the values it sees at run time may change.
- **Decorators on a helper** (`@transaction.atomic`, caching, retry). Inlining drops the decorator. Recreate the same effect at the call site, or keep the helper.
- **URLconf and app loading happen immediately at startup.** An `ImportError` in any imported module can take the whole project down. Moving an import from inside a function to the top of the file may cause a circular import at startup.

## Celery

- **A task's registered name is its module path** unless `name=` is given. Moving a function decorated with `@shared_task` or `@app.task` to another module renames the task. Jobs waiting in the queue, the beat schedule and the workers all break. Never move a task function. Only the *bodies* that the task calls may move.
- A call to `.delay()` / `.apply_async()` must stay in the same position relative to `on_commit` and the DB writes around it.

## Imports and visibility

- **`_name` is only a convention.** It hides nothing, but it still tells readers what outside code may use, and a linter warns when another module touches it. `from module import *` skips names that start with `_`, so check whether anything relies on `*`.
- **Relative imports** (`from ..models import X`) change meaning when a file moves. Use absolute imports in the new layout.
- **`from x import y` copies the reference.** Patching `x.y` later has no effect on a module that already imported `y`. That is why `scripts/parity.py` does not patch: it replaces every module outside the unit with a stub from the moment of import. If you build your own harness (for example with `unittest.mock`), you must patch every module that holds that object.

## Payloads and results

- **The key order of a dict is the order of insertion.** `{**a, **b}` gives the keys of `a` first, then the new keys of `b`. JSON and logged payloads follow this order. Build the literal in the original order.
- **The text of `traceback.format_exc()`** contains file paths and line numbers, so it always changes when code moves. Report it as an unavoidable difference.
- **Truthiness checks.** `x or ""` and `x if x else "-"` give different results for `0`, `""` and `None`. Copy each expression exactly. Never "simplify" from one form to the other.
- **`x != True` and `x == False` are not the same** when `x` is `None` or a string such as `"false"`: the first is true, the second is false. The same goes for `d["k"]` (raises `KeyError`) and `d.get("k")` (returns `None`). Compare line by line before merging code that looks duplicated.

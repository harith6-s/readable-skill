# What readable code looks like

Every mode uses this file. It covers flow and structure only. **Anything it does not mention follows the language's and the project's own conventions**: the formatter, the linter, the code around it. Do not reformat code you are not reshaping.

A limit that the project has configured and enforces (a lint rule, a CI check that fails), such as a maximum function length, wins over this file. A tool's default that the project never configured does not. SKILL.md (step Map) says what to do when a story would break an enforced limit.

## The goal

A reader follows one request or task from its entry point to its end, top to bottom, without holding more than a few things in mind. People keep roughly 4–7 items in working memory. Every jump into a helper that jumps again adds a level, until the reader forgets why they left line 74. Readability is therefore measured by:

- **jump depth** from an entry point through unit-local code (target: ≤ 1),
- whether **every decision is visible** in the entry point,
- whether **every outbound payload can be read whole** where it is sent.

## When rules conflict

1. Correct behavior (unchanged behavior when refactoring)
2. Reads top to bottom: depth ≤ 1, decisions in the story
3. No duplicated logic
4. Short
5. Fast. Speed may be traded only inside memory. Never add a query, an API call or a file read, for example a query inside a loop.

## Shape

1. **The entry point is the story.** An entry point is what outside code calls: an HTTP handler, a task, a command, an event handler. It reads as numbered steps in the order they run, with headings like `# --- 3. Sign the request page (was: request_signing) ---`. The `was:` part appears only when refactoring.
2. **Jump at most one level.** The story may call unit-local helpers. A unit-local helper must be a **leaf**: it may call libraries, the framework and helpers shared outside the unit, but never another unit-local helper.
3. **Decisions live in the story.** Every branch that changes direction, every raise or fail, every outbound call, database write and status change is visible in the entry point. Helpers compute, format or fetch. They never decide. One exception: a chunk that rule 6 merges may hold outbound calls, such as calling a service and mapping its errors. Its name says what it sends, it returns a result, and the story decides what happens next (marks, raises, writes). *Name test:* keep a helper only if a reader can tell where the flow goes next without opening it.
4. **Payloads are visible whole.** Every payload sent outside (HTTP, PDF, queue, email) is one literal at the call site, readable down to `depth` levels (default 3). Parts deeper than that may be named variables just above the literal. Never assemble a payload with `**` from several functions, and keep the key order.
5. **Long conditions become named variables** above the literal, not new functions.
6. **No duplicated logic, judged by chunks, not lines.** A chunk that does one piece of work on its own, such as calling a service and mapping its error codes, and repeats whole in two or more places becomes one leaf helper. A small expression that happens to match inside otherwise different code is not a duplicate. Merge only the part that behaves the same: compare the copies line by line, keep what differs at each caller or pass it in as an argument, and pin a difference that looks accidental (`PIN(behavior)`). Never unify it. The merged leaf returns a result, and the story raises (rule 3). Payloads that only look alike are not merged (rule 4).
7. **Constants and status or step codes** have one name in one place. Never inline them as literals.
8. **Imports at the top**, except an import that breaks a circular import. Keep that one where it is, with a one-line reason.
9. **Header map.** Every story file starts with a short docstring: its entry points, the steps of each, and the outbound calls in order. Name the hooks the framework calls by itself, because a reader cannot see those calls.
10. **Visibility.** Everything outside the public surface is private by the language's own mechanism: Python `_name`, TypeScript no `export`, Go lower case. When refactoring this is the only rename allowed.

## File layout (`layout`)

- `A` (default): one file per task. A task is one step of the business flow, with every entry point that only starts or queues it (see the Map step in `SKILL.md`). A unit with one task keeps the original file name for its story. Inside a task file, public entry points come first. A helper with one caller in the file sits directly below that caller, so the reader jumps down a few lines and comes back. A leaf with several callers, all in this file, sits at the end of the file, below all of them.
- `B`: one file per product (a document, a message, a payload type) holding its builder.
- `AB`: task files as in A, whose steps call the product builders of B, one level deep.

In every layout:
- **`shared.py`**, one per package, holds the leaves that two or more files call. Its functions never call each other, so a reader who jumps there lands on code with nothing behind it. Other languages use the same name (`shared.ts`, `shared.go`).
- **Short does not mean shared.** A function that decides (raises, picks the next step, writes) is a story and lives in its task file, however short it is. `shared.py` holds only leaves.
- **No facade.** `__init__.py` (or `index.ts`) holds no code and re-exports nothing. Callers import each name from its own file, so "go to definition" lands on the code.
- **Split only to cut jumps.** Giving each task its own file cuts what a reader must skip. Splitting one task across files adds jumps: do it only for the product builders of `B` and `AB`.
- **Code with no caller** stays in its task file, or in `shared.py` when no task owns it, pinned as `PIN(behavior): no caller found`.

## Class or function (`style=auto`)

A class adds three jumps a reader cannot see as calls: walking inheritance and mixins, hooks the framework calls by itself, and data handed from one method to another through `self`.

1. **The framework comes first.** Where the framework or the project requires a class (a Django class-based view, a DRF serializer, a NestJS controller), use one. Do not fight the framework.
2. **Otherwise default to functions.** The story is one function, or the one method the framework calls. Data moves through arguments and local variables.
3. **A class only for real shared state**, such as a context (the user, the main request) that several entry points share. Its methods follow the depth rule. Set `self.x` only in `__init__`, never in one method for another method to read.
4. **Project inheritance at most one level per story.** Framework base classes do not count. Keep existing public mixins, but never create new ones.
5. **Never convert a public class to a function or back.** Convert internal ones only.
6. **Framework hooks go into the header map**, for example "DRF calls `get_queryset` → … → `get_serializer`".

Languages without classes follow the same idea. In Go, use methods on a struct only for real state (a client, a config). Embedding counts as inheritance.

## Keep, inline or merge (refactor)

| The function looks like this | Do this |
|---|---|
| Used once, wraps a few lines | Inline it as a numbered step |
| Calls another unit-local helper | Inline it, or fold what it calls into it |
| Takes a flag or mode and branches on it | Inline it into each caller with every branch: a flag that caller never passes becomes a local variable set to its default, with its branch kept and pinned |
| Pure computation or formatting, 2+ callers, its name says it all | Keep it as a leaf: at the end of the file when all its callers are in that file, otherwise in `shared.py` |
| The same chunk copied in 2+ places | Merge the part that behaves the same into one leaf that returns a result: directly below its caller when all the copies are in one function, at the end of the file when they are all in one file, otherwise in `shared.py`. The story keeps the raise. |
| Builds part of a payload | Inline it into the payload literal |
| A condition function passed as an argument (`publish(..., waiting)`) | Pass the value instead, or inline the check |

## Where this skill disagrees with common advice

Most "clean code" advice you already know pulls toward many small functions. Where it conflicts with the goal above, this file wins.

| Common advice | Here |
|---|---|
| Meaningful names | Keep. |
| DRY | Keep for logic: a chunk repeated whole in two or more places becomes one leaf helper. Payloads that only look alike are not merged. |
| YAGNI | Keep. No class, mixin or function made "for later". |
| Single responsibility | At the level of a task: one entry point tells one story. Not every five lines. |
| Small functions, "extract till you drop" | **No.** A long function is fine when it reads as numbered steps. |
| Stepdown rule | Half. Keep the top-to-bottom order, but do not turn every level of abstraction into a function. |
| "Comments are a failure to express yourself in code" | **No.** Step headings are required comments. |
| Inheritance for reuse | **No.** Pass arguments, unless the framework requires a class. |

### Red flags (seen in baseline runs without this skill)

| Thought | Reality |
|---|---|
| "Smaller helpers are clearer" | Every helper is one more jump. Novices read extracted methods more slowly, even when they say they prefer them. |
| "This long condition should be a function" | Name it as a variable above the literal. |
| "An overview docstring is enough" | The map helps, but the jumps are still there. Fix them. |
| "Merge payloads with `**` to avoid repeating keys" | It hides the payload's shape and can change the key order. |
| "Make it a class or mixin so it can be reused" | Every inheritance level is a jump nobody sees. Pass arguments instead. |

## Examples

These examples are made up, so that each one shows a single idea. They are in Python, but the ideas apply to any language.

### Jumps everywhere

```python
def send_contract(contract_id):
    contract = Contract.objects.get(id=contract_id)
    document = build_document(contract)
    return render_and_store(contract, document)


def build_document(contract):
    return {"customer": customer_block(contract.customer), **signing_block(contract)}


def customer_block(customer):
    return {"name": full_name(customer), **address_block(customer)}


def full_name(customer):
    return f"{customer.first_name} {customer.last_name}"


def address_block(customer):
    return {"city": customer.city or "", "zip": customer.zip_code}


def signing_block(contract):
    if needs_manager(contract):
        return {"signer": contract.manager.name, "signed_at": format_date(contract.signed_at)}
    return {"signer": contract.officer.name}


def needs_manager(contract):
    return contract.amount > 100_000 and not contract.is_renewal


def render_and_store(contract, document):
    res = pdf_api.post("/render", json={"file_name": f"{contract.code}.pdf", **document})
    if res.status_code != 200:
        raise RenderError(res.text)
    contract.file_url = storage.upload(res.content)
    contract.save()
    return contract.file_url
```

To learn what `/render` receives, a reader opens 7 functions, goes three levels deep and resolves 3 `**` merges. The choice of signer, the raise and the database write are all hidden in helpers.

### The same behavior, as a story

```python
"""Contract document.

send_contract(contract_id)
  1. Load the contract
  2. Choose the signer
  3. Render the PDF   → pdf_api POST /render
  4. Store the file   → storage.upload, contract.save()
"""


def send_contract(contract_id):
    # --- 1. Load the contract ---
    contract = Contract.objects.get(id=contract_id)
    customer = contract.customer

    # --- 2. Choose the signer (was: signing_block, needs_manager) ---
    needs_manager = contract.amount > 100_000 and not contract.is_renewal
    signer = contract.manager if needs_manager else contract.officer

    # --- 3. Render the PDF (was: build_document, customer_block, full_name, address_block) ---
    body = {
        "file_name": f"{contract.code}.pdf",
        "customer": {
            "name": f"{customer.first_name} {customer.last_name}",
            "city": customer.city or "",
            "zip": customer.zip_code,
        },
        "signer": signer.name,
    }
    if needs_manager:
        body["signed_at"] = format_date(contract.signed_at)
    res = pdf_api.post("/render", json=body)
    if res.status_code != 200:
        raise RenderError(res.text)

    # --- 4. Store the file (was: render_and_store) ---
    contract.file_url = storage.upload(res.content)
    contract.save()
    return contract.file_url
```

- Every decision is visible in the story: who signs, when it fails, what is saved.
- The payload is one literal. `signed_at` is added right below it, so it is still the last key, as before.
- The old names survive in the step headings. No unit-local helper is left: `format_date` is shared with other code, so it counts as a library call.

### A duplicate that is not quite one

Two entry points seem to copy the same signature check:

```python
def sign_contract(contract):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": contract.officer.email})
        if res.json()["ok"] != True:
            if res.json()["errors"][0]["message"] == "Not found":
                code = "81"
                raise Exception("User has no signature.")
            code = "82"
            raise Exception("Signature service error.")
        signature = res.json()["image"]
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}


def sign_receipt(receipt):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": receipt.cashier.email})
        if res.json()["ok"] == False:
            if res.json()["errors"][0]["message"] == "Not found":
                code = "81"
                raise Exception("User has no signature.")
            code = "82"
            raise Exception("Signature service error.")
        signature = res.json().get("image")
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}
```

The copies differ:
- When `ok` is `None`, `!= True` is true but `== False` is false: `sign_contract` fails with code `82`, while `sign_receipt` goes on.
- When `image` is missing, `["image"]` raises `KeyError`, while `.get("image")` returns `None`.
- `code` is a local variable that the `except` reads.

Merging the whole block into one helper breaks all three:

```python
# Wrong
def _get_signature(email):
    res = signature_api.post("/signature", json={"email": email})
    if res.json()["ok"] != True:              # sign_receipt checked == False
        if res.json()["errors"][0]["message"] == "Not found":
            code = "81"                       # the helper's own variable: the caller still returns "80"
            raise Exception("User has no signature.")
        code = "82"
        raise Exception("Signature service error.")
    return res.json()["image"]                # sign_receipt used .get("image")
```

Only the error mapping behaves the same in both copies. Merge that part into a leaf that returns a result, and keep the rest in each story:

```python
def _signature_error(data):
    if data["errors"][0]["message"] == "Not found":
        return "81", "User has no signature."
    return "82", "Signature service error."


def sign_contract(contract):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": contract.officer.email})
        if res.json()["ok"] != True:
            code, message = _signature_error(res.json())
            raise Exception(message)
        signature = res.json()["image"]
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}


def sign_receipt(receipt):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": receipt.cashier.email})
        # PIN(behavior): checks ok with == False and reads image with .get(); sign_contract uses != True and ["image"]
        if res.json()["ok"] == False:
            code, message = _signature_error(res.json())
            raise Exception(message)
        signature = res.json().get("image")
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}
```

The story still raises, `code` is still set where the `except` can read it, and the difference that looks accidental is pinned, not fixed.

# eval: measure whether the skill works on the examples

No git, no Django and no company code are needed. Everything runs from the folder of this repo.

## One round

```bash
# 1. Make a copy for the runner (the agent) to work in
python eval/prepare.py orders /tmp/run1

# 2. Let the agent use the skill on /tmp/run1 (tell it to refactor shop/checkout.py by the skill's rules,
#    never to edit an existing file, and to add the new files as a package such as shop/checkout_v2/)

# 3. Grade
python eval/grade.py orders /tmp/run1 --json /tmp/run1/grading.json
```

`prepare.py` records the sha256 of every file the copy starts with. `grade.py` uses it to check that the original files were not touched, and it treats the new files as the work of that round.

## What is checked

| Check | What it verifies |
|---|---|
| 01 | parity: every scenario set is recorded on the original and on the new files, and the diff is empty |
| 02 | every original file is unchanged |
| 03 | every name that production code imports from the old module is defined in one of the new files |
| 04 | `jump_depth`: max local_depth <= 1 |
| 07 | `jump_depth`: file layout (helper below its caller, `shared.py` functions never call each other, no facade) |
| 08 | each task lives in one file, and different tasks live in different files |
| 09 | no new file imports the old module |
| 11 | branches of the original that no caller reaches are still in the code as `if` statements |
| 12 | `jump_depth`: no state passed between methods through `self`, and project inheritance <= 1 |
| 13 | each chunk that repeated whole is written in one function only (rule 6), checked by a marker per chunk in `written_once` of `case.json`: `.refund` is a method, any other name is a variable or attribute name |
| 14 | the status codes in `codes` of `case.json` are ALL_CAPS constants defined once and never written as literals elsewhere (rule 7) |

Checks 05 and 06 (an AI reader answering questions about the new code, with `eval/reader.py` and `eval/reader_prompt.md`) are not in this set, because the examples have no question sets yet (`questions.md` / `key.md`). A question set exists only to test the skill.

## Checking the grader itself

`tests/test_grade.py` takes the correct golden answer of `orders`, which must pass all 11 checks. Then it breaks the golden answer one way at a time (change a payload, drop a branch no caller reaches, chain helpers, put code in `__init__.py`, edit an original file, import the old module, pass state through `self`, two layers of inheritance, copy the refund call into another story, write a status code as a literal). Each break must fail only the check that is meant to catch it.

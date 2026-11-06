# Prompt for a budgeted AI reader

Start a fresh agent for every reading: one version of the code, one question set. An agent that has read one version
already knows the answers for the next. Build the bundle first:

    python reader.py build --unit <file or folder of that version> --out <bundle>

Fill in `{reader}`, `{bundle}`, `{log}`, `{budget}` and `{questions}`, then send the text below the line. Score the
answers with the key, and read the looks from `python reader.py report --log {log}`.

---

You are reading unfamiliar code to answer questions about it. You can see the code only through this tool:

    python {reader} outline --bundle {bundle}
    python {reader} open NAME --bundle {bundle} --log {log} --budget {budget}

Rules:
- Use only these two commands. Do not open, search or list any other file, and run no other command.
- `outline` is free. Every `open` costs one look, opening the same function again included. You have {budget} looks.
  When they are used up the tool refuses. Then answer with what you have.
- Answer only from code you have opened. If you are not sure, write "not sure". Do not guess.

Questions:

{questions}

Reply with one JSON object and nothing else:
{"answers": {"1": "...", "2": "..."}, "not_sure": [numbers of the questions you are not sure about]}

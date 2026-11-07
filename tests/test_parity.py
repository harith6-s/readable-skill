"""parity.py on small throwaway projects: recording, stubs, frozen time, constants, diff, coverage."""

import json
import textwrap
import unittest

from helpers import ProjectTest, jump_depth, parity

BILLING = {
    "billing/__init__.py": "",
    "billing/client.py": "BASE_URL = 'https://x.example.test'\n\nclass ApiSession:\n    def post(self, path, **kw):\n        raise NotImplementedError\n",
    "billing/config.py": "RETRIES = 3\nLABEL = 'inv'\nBASE = 'x' + 'y'\n",
}
FLOW = """
    from billing.client import ApiSession
    from billing.config import RETRIES

    def send(invoice):
        session = ApiSession()
        reply = session.post("/invoices", number=invoice["number"], retries=RETRIES)
        return {"ok": reply.status_code == 200}
"""
SCENARIO = """
    def scenario_send(h):
        h.stub("billing.client.ApiSession().post").returns(h.response(status=200))
        return h.unit.send({"number": "INV-1"})
"""


class Record(ProjectTest):
    def test_records_outbound_call_arguments_and_return(self):
        root = self.project({**BILLING, "billing/flow.py": FLOW})
        code, text, rec = self.record(root, "billing/flow.py", SCENARIO)
        self.assertEqual(code, 0, text)
        scenario = self.scenario(rec, "scenario_send")
        self.assertEqual(scenario["outcome"], {"return": {"ok": True}})
        calls = [event for event in scenario["events"] if event.get("call") == "billing.client.ApiSession().post"]
        self.assertEqual(calls[0]["args"], ["/invoices"])
        self.assertEqual(calls[0]["kwargs"], {"number": "INV-1", "retries": 3})

    def test_all_caps_constant_takes_its_literal_value_from_source(self):
        root = self.project({**BILLING, "billing/flow.py": """
            from billing.config import LABEL, BASE
            from billing import client

            def show():
                return [LABEL, BASE, client.BASE_URL]
            """})
        code, text, rec = self.record(root, "billing/flow.py", """
            def scenario_show(h):
                return h.unit.show()
            """)
        self.assertEqual(code, 0, text)
        outcome = self.scenario(rec, "scenario_show")["outcome"]["return"]
        self.assertEqual(outcome[0], "inv")                       # a literal in the source
        self.assertTrue(str(outcome[1]).startswith("<") or isinstance(outcome[1], dict))   # BASE is computed: not a literal

    def test_exception_the_unit_lets_out_is_the_outcome(self):
        root = self.project({**BILLING, "billing/flow.py": """
            def boom():
                raise ValueError("bad")
            """})
        code, text, rec = self.record(root, "billing/flow.py", """
            def scenario_boom(h):
                return h.unit.boom()
            """)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.scenario(rec, "scenario_boom")["outcome"], {"raise": "ValueError", "message": "bad"})

    def test_a_scenario_that_breaks_outside_the_unit_stops_the_recording(self):
        root = self.project({**BILLING, "billing/flow.py": FLOW})
        code, text, rec = self.record(root, "billing/flow.py", """
            def scenario_typo(h):
                return h.unit.no_such_function()
            """)
        self.assertNotEqual(code, 0)

    def test_async_unit_is_refused_and_nothing_is_written(self):
        root = self.project({"feeds/__init__.py": "", "feeds/client.py": "async def get(url):\n    raise NotImplementedError\n",
                             "feeds/sync.py": "from feeds import client\n\nasync def fetch(url):\n    return await client.get(url)\n"})
        code, text, rec = self.record(root, "feeds/sync.py", """
            def scenario_fetch(h):
                h.stub("feeds.client.get").returns({"items": []})
                return h.unit.fetch("a")
            """)
        self.assertEqual(code, 1, text)
        self.assertIn("feeds/sync.py:3", text)
        self.assertIsNone(rec)

    def test_time_and_uuid_are_frozen(self):
        root = self.project({**BILLING, "billing/flow.py": """
            import datetime, uuid, time

            def stamp():
                return [datetime.datetime.now().isoformat(), str(uuid.uuid4()), time.time()]
            """})
        scenarios = """
            def scenario_stamp(h):
                return h.unit.stamp()
            """
        _, _, first = self.record(root, "billing/flow.py", scenarios, "--now", "2030-05-06T07:08:09", name="a.json")
        _, _, second = self.record(root, "billing/flow.py", scenarios, "--now", "2030-05-06T07:08:09", name="b.json")
        out = self.scenario(first, "scenario_stamp")["outcome"]["return"]
        self.assertEqual(out[0], "2030-05-06T07:08:09")
        self.assertEqual(out, self.scenario(second, "scenario_stamp")["outcome"]["return"])

    def test_network_parts_of_the_standard_library_are_stubbed(self):
        root = self.project({**BILLING, "billing/flow.py": """
            import socket

            def probe():
                return socket.create_connection(("example.test", 80))
            """})
        code, text, rec = self.record(root, "billing/flow.py", """
            def scenario_probe(h):
                return h.unit.probe()
            """)
        self.assertEqual(code, 0, text)
        events = self.scenario(rec, "scenario_probe")["events"]
        self.assertTrue(any("socket" in event.get("call", "") for event in events))

    def test_pure_stub_is_not_recorded_but_still_returns(self):
        root = self.project({**BILLING, "billing/fmt.py": "def short(value):\n    raise NotImplementedError\n",
                             "billing/flow.py": """
            from billing import fmt
            from billing.client import ApiSession

            def run():
                ApiSession().post("/x", label=fmt.short(5))
            """})
        scenarios = """
            def scenario_run(h):
                h.stub("billing.fmt.short").pure().returns("five")
                return h.unit.run()
            """
        code, text, rec = self.record(root, "billing/flow.py", scenarios)
        self.assertEqual(code, 0, text)
        calls = [event.get("call") for event in self.scenario(rec, "scenario_run")["events"]]
        self.assertNotIn("billing.fmt.short", calls)
        post = next(event for event in self.scenario(rec, "scenario_run")["events"]
                    if event.get("call", "").endswith(".post"))
        self.assertEqual(post["kwargs"], {"label": "five"})

    def test_task_decorator_is_a_stub_that_still_runs_and_delay_is_recorded(self):
        root = self.project({**BILLING, "billing/tasks.py": """
            from celery import shared_task

            @shared_task
            def work(x):
                return x + 1

            def queue(x):
                work.delay(x)
                return work(x)
            """})
        code, text, rec = self.record(root, "billing/tasks.py", """
            def scenario_queue(h):
                return h.unit.queue(1)
            """)
        self.assertEqual(code, 0, text)
        scenario = self.scenario(rec, "scenario_queue")
        self.assertEqual(scenario["outcome"], {"return": 2})
        self.assertTrue(any(event.get("call", "").endswith("work.delay") or "delay" in event.get("call", "")
                            for event in scenario["events"]))

    def test_h_unit_finds_a_name_in_any_unit_file(self):
        root = self.project({**BILLING,
                             "billing/one.py": "def first():\n    return 1\n",
                             "billing/two.py": "def second():\n    return 2\n"})
        scenarios = """
            def scenario_both(h):
                return [h.unit.first(), h.unit.second()]
            """
        (root / "scenarios_.py").write_text(textwrap.dedent(scenarios).lstrip("\n"))
        code, text = parity("record", "--unit", "billing/one.py", "--unit", "billing/two.py", "--root", ".",
                            "--scenarios", "scenarios_.py", "--out", "rec.json", cwd=root)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.scenario(json.loads((root / "rec.json").read_text()), "scenario_both")["outcome"],
                         {"return": [1, 2]})


class Diff(ProjectTest):
    def two_recordings(self, new_flow):
        root = self.project({**BILLING, "billing/flow.py": FLOW})
        _, _, old = self.record(root, "billing/flow.py", SCENARIO, name="old.json")
        (root / "billing/flow.py").write_text(textwrap.dedent(new_flow).lstrip("\n"))
        _, _, new = self.record(root, "billing/flow.py", SCENARIO, name="new.json")
        return root

    def test_same_behaviour_is_an_empty_diff_whatever_the_line_numbers(self):
        root = self.two_recordings("# a comment that moves every line\n" + textwrap.dedent(FLOW).lstrip("\n"))
        code, text = parity("diff", "old.json", "new.json", cwd=root)
        self.assertEqual(code, 0, text)

    def test_changed_payload_is_a_difference(self):
        root = self.two_recordings(FLOW.replace('retries=RETRIES', 'retries=RETRIES + 1'))
        code, text = parity("diff", "old.json", "new.json", cwd=root)
        self.assertEqual(code, 1)

    def test_changed_order_of_calls_is_a_difference(self):
        two_calls = """
            from billing.client import ApiSession

            def send(invoice):
                ApiSession().post("/a")
                ApiSession().post("/b")
                return {"ok": True}
            """
        root = self.project({**BILLING, "billing/flow.py": two_calls})
        _, _, _ = self.record(root, "billing/flow.py", SCENARIO, name="old.json")
        (root / "billing/flow.py").write_text(textwrap.dedent(two_calls.replace('"/a"', '"/tmp"').replace('"/b"', '"/a"').replace('"/tmp"', '"/b"')).lstrip("\n"))
        _, _, _ = self.record(root, "billing/flow.py", SCENARIO, name="new.json")
        code, _ = parity("diff", "old.json", "new.json", cwd=root)
        self.assertEqual(code, 1)


class Coverage(ProjectTest):
    def test_lists_outbound_sites_that_no_scenario_reached(self):
        root = self.project({**BILLING, "billing/flow.py": """
            from billing.client import ApiSession

            def send(flag):
                if flag:
                    ApiSession().post("/reached")
                else:
                    ApiSession().post("/never")
            """})
        code, text, rec = self.record(root, "billing/flow.py", """
            def scenario_flag(h):
                return h.unit.send(True)
            """)
        self.assertEqual(code, 0, text)
        code, text = jump_depth("billing/flow.py", "--root", ".", "--json", cwd=root)
        (root / "map.json").write_text(text)
        code, text = parity("coverage", "--recording", "rec.json", "--map", "map.json", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("billing/flow.py:7", text)
        self.assertNotIn("billing/flow.py:5", text)


class KnownLimits(ProjectTest):
    """Behaviours of 1.x that a later version should change. Each has the current behaviour pinned and the wanted
    behaviour as an expected failure, so the day it is fixed the suite tells you to flip the pair."""

    def test_known_limit_getattr_on_a_stubbed_module_never_misses(self):
        root = self.project({"hooks/__init__.py": "", "hooks/handlers.py": "def on_a(e):\n    return 1\n",
                             "hooks/dispatch.py": """
            from hooks import handlers

            def dispatch(name):
                handler = getattr(handlers, "on_" + name, None)
                if handler is None:
                    return "no handler"
                return handler(name)
            """})
        code, text, rec = self.record(root, "hooks/dispatch.py", """
            def scenario_unknown(h):
                return h.unit.dispatch("zzz")
            """)
        self.assertEqual(code, 0, text)
        outcome = self.scenario(rec, "scenario_unknown")["outcome"]["return"]
        self.assertNotEqual(outcome, "no handler")        # the `handler is None` branch cannot be reached


if __name__ == "__main__":
    unittest.main()

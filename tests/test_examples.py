"""What the scripts say about each example: the shape of each one is pinned, so a change in the scripts that moves it
shows up here. Known limits are pinned in both directions (see test_parity.KnownLimits)."""

import json
import unittest

from helpers import EXAMPLES, EXAMPLE_NAMES, ProjectTest, jump_depth, parity

SHAPES = {"refactor", "no-change", "list-by-hand", "unsupported"}


def case(name):
    return json.loads((EXAMPLES / name / "case.json").read_text())


class Cases(unittest.TestCase):
    def test_every_example_has_a_valid_case(self):
        self.assertGreaterEqual(len(EXAMPLE_NAMES), 5)
        for name in EXAMPLE_NAMES:
            with self.subTest(name):
                info = case(name)
                self.assertEqual(info["name"], name)
                self.assertIn(info["shape"], SHAPES)
                self.assertTrue((EXAMPLES / name / "src" / info["original"]).is_file())
                for scenarios in info["scenarios"]:
                    self.assertTrue((EXAMPLES / name / scenarios).is_file())
                self.assertTrue(info["about"] and info["expect"] if info["shape"] != "refactor" else info["about"])

    def test_no_example_mentions_a_real_company_or_secret(self):
        for path in EXAMPLES.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json"}:
                text = path.read_text(encoding="utf-8").lower()
                for word in ("api_key", "password", "secret", "cane", "contracting", "receipt_confirmation", "django"):
                    self.assertNotIn(word, text, f"{word} in {path}")


class Recording(unittest.TestCase):
    def test_every_example_records_the_same_twice(self):
        import tempfile
        for name in EXAMPLE_NAMES:
            info = case(name)
            src = EXAMPLES / name / "src"
            with self.subTest(name), tempfile.TemporaryDirectory() as temp:
                for take in ("a", "b"):
                    code, text = parity("record", "--unit", info["original"], "--root", ".",
                                        "--scenarios", EXAMPLES / name / info["scenarios"][0],
                                        "--out", f"{temp}/{take}.json", cwd=src)
                    self.assertEqual(code, 0, text)
                code, text = parity("diff", f"{temp}/a.json", f"{temp}/b.json", cwd=src)
                self.assertEqual(code, 0, text)


class Shapes(unittest.TestCase):
    def report(self, name):
        info = case(name)
        code, text = jump_depth(info["original"], "--root", ".", "--usage", ".", "--json", cwd=EXAMPLES / name / "src")
        self.assertEqual(code, 0, text)
        return json.loads(text)

    def check(self, name):
        info = case(name)
        return jump_depth(info["original"], "--root", ".", "--usage", ".", "--check", cwd=EXAMPLES / name / "src")

    def test_orders_has_the_faults_it_was_written_with(self):
        code, text = self.check("orders")
        self.assertEqual(code, 1)
        summary = self.report("orders")["summary"]
        self.assertEqual(summary["max_local_depth"], 2)
        self.assertGreaterEqual(summary["layout_problems"], 10)
        for name in ("_money", "_totals", "_gateway", "_release_all", "_refund"):
            self.assertIn(f"{name} is called by", text)

    def test_statements_passes_state_through_self_and_inherits_once(self):
        summary = self.report("statements")["summary"]
        self.assertEqual(summary["state_across"], 1)
        self.assertEqual(summary["max_inheritance"], 1)
        self.assertEqual(self.check("statements")[0], 1)

    def test_clean_needs_nothing(self):
        code, text = self.check("clean")
        self.assertEqual(code, 0, text)

    def test_plugins_dispatch_looks_flat_because_the_handlers_are_invisible(self):
        """Known limit: names built at run time are not followed, so --check says OK."""
        code, text = self.check("plugins")
        self.assertEqual(code, 0, text)
        self.assertIn("reach", text)
        self.assertNotIn("on_created", text)

    def test_async_original_passes_the_check_although_it_cannot_be_recorded(self):
        """Known limit (see test_parity.KnownLimits): nothing in the scripts says await is unsupported."""
        code, text = self.check("async_jobs")
        self.assertEqual(code, 0, text)


if __name__ == "__main__":
    unittest.main()

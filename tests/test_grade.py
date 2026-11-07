"""eval/grade.py tested on its own: a hand-made correct refactor of examples/orders passes every assertion, and each
mutation of it fails exactly the assertion that is meant to catch it. No model is involved."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import EXAMPLES, ROOT, SCRIPTS

sys.path.insert(0, str(ROOT / "eval"))
import grade      # noqa: E402
import prepare    # noqa: E402

GOLDEN = EXAMPLES / "orders" / "golden"
PACKAGE = "shop/checkout_v2"


class Golden(unittest.TestCase):
    def workdir(self, mutate=None):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        work = prepare.prepare("orders", temp / "work")
        shutil.copytree(GOLDEN / PACKAGE, work / PACKAGE)
        if mutate:
            mutate(work)
        return work

    def graded(self, mutate=None):
        results = grade.grade("orders", self.workdir(mutate), SCRIPTS)
        return {item["text"][:2]: item for item in results}

    def failing(self, mutate):
        return sorted(key for key, item in self.graded(mutate).items() if not item["passed"])

    def edit(self, name, old, new):
        def mutate(work):
            path = work / PACKAGE / name
            text = path.read_text()
            self.assertIn(old, text, f"mutation does not apply to {name}")
            path.write_text(text.replace(old, new, 1))
        return mutate

    def test_the_correct_refactor_passes_everything(self):
        results = self.graded()
        self.assertEqual(sorted(results), ["01", "02", "03", "04", "07", "08", "09", "11", "12"])
        self.assertEqual([key for key, item in results.items() if not item["passed"]], [])

    def test_a_changed_payload_fails_parity_only(self):
        self.assertEqual(self.failing(self.edit("preview_order.py", "round(subtotal * TAX_RATE, 2)",
                                                "subtotal * TAX_RATE")), ["01"])

    def test_a_dropped_unreachable_branch_passes_parity_but_fails_the_kept_branch_check(self):
        mutate = self.edit("place_order.py", '        if cc:\n            body += "\\nCopied to " + ", ".join(cc)\n', "")
        self.assertEqual(self.failing(mutate), ["11"])

    def test_a_helper_chain_fails_depth_only(self):
        def mutate(work):
            path = work / PACKAGE / "place_order.py"
            text = path.read_text().replace('        if inventory.available(item["sku"]) < item["qty"]:\n            for earlier',
                                            '        if _short(item):\n            for earlier', 1)
            path.write_text(text + '\n\ndef _short(item):\n    return inventory.available(item["sku"]) < item["qty"]\n')
        self.assertEqual(self.failing(mutate), ["04"])

    def test_code_in_init_is_a_facade_and_fails_layout_only(self):
        def mutate(work):
            (work / PACKAGE / "__init__.py").write_text("from shop.checkout_v2.place_order import place_order\n")
        self.assertEqual(self.failing(mutate), ["07"])

    def test_editing_an_original_file_fails_the_untouched_check_only(self):
        def mutate(work):
            with open(work / "shop" / "checkout.py", "a") as handle:
                handle.write("\n# edited\n")
        self.assertEqual(self.failing(mutate), ["02"])

    def test_importing_the_original_fails_that_check_only(self):
        mutate = self.edit("repair_order.py", "from shop import audit, orders_store",
                           "from shop import audit, checkout, orders_store")
        self.assertEqual(self.failing(mutate), ["09"])

    def test_state_passed_through_self_fails_the_class_check_only(self):
        def mutate(work):
            with open(work / PACKAGE / "preview_order.py", "a") as handle:
                handle.write("\n\nclass _Basket:\n    def fill(self, items):\n        self.lines = list(items)\n\n"
                             "    def count(self):\n        return len(self.lines)\n")
        self.assertEqual(self.failing(mutate), ["12"])

    def test_two_layers_of_project_inheritance_fail_the_class_check_only(self):
        def mutate(work):
            with open(work / PACKAGE / "preview_order.py", "a") as handle:
                handle.write("\n\nclass _Base:\n    pass\n\n\nclass _Middle(_Base):\n    pass\n\n\n"
                             "class _Leaf(_Middle):\n    pass\n")
        self.assertEqual(self.failing(mutate), ["12"])

    def test_a_missing_public_name_fails_surface_check(self):
        mutate = self.edit("repair_order.py", "def unlock_order(order_id):", "def unlock_the_order(order_id):")
        failing = self.failing(mutate)
        self.assertIn("03", failing)


class Pieces(unittest.TestCase):
    def test_check_tasks_accepts_one_file_per_task(self):
        where = {"a": "a.py", "b": "a.py", "c": "c.py"}
        self.assertTrue(grade.check_tasks(where, [["a", "b"], ["c"]])[0])

    def test_check_tasks_rejects_a_task_split_over_two_files(self):
        where = {"a": "a.py", "b": "b.py"}
        self.assertFalse(grade.check_tasks(where, [["a", "b"]])[0])

    def test_check_tasks_rejects_two_tasks_in_one_file(self):
        where = {"a": "x.py", "c": "x.py"}
        self.assertFalse(grade.check_tasks(where, [["a"], ["c"]])[0])

    def test_targets_scan_a_new_package_whole_but_only_the_new_file_of_an_old_package(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name in ("shop/__init__.py", "shop/checkout_v2.py", "shop/v3/__init__.py", "shop/v3/a.py"):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text("")
        files = [root / "shop/checkout_v2.py", root / "shop/v3/__init__.py", root / "shop/v3/a.py"]
        self.assertEqual(grade.targets(files, root), [root / "shop/v3", root / "shop/checkout_v2.py"])

    def test_dotted_names(self):
        root = Path("/p")
        self.assertEqual(grade.dotted(Path("/p/shop/checkout_v2/shared.py"), root), "shop.checkout_v2.shared")
        self.assertEqual(grade.dotted(Path("/p/shop/checkout_v2/__init__.py"), root), "shop.checkout_v2")


if __name__ == "__main__":
    unittest.main()

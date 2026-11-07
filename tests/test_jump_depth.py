"""jump_depth.py on small throwaway projects: depth, layout rules, hidden imports, callers, --exclude."""

import json
import unittest

from helpers import ProjectTest, jump_depth

BILLING = {
    "billing/__init__.py": "",
    "billing/client.py": "def post(x):\n    return x\n",
}


class Depth(ProjectTest):
    def test_chain_of_helpers_is_local_depth_two(self):
        root = self.project({**BILLING, "billing/flow.py": """
            from billing import client

            def run(x):
                return step_a(x)

            def step_a(x):
                return step_b(x)

            def step_b(x):
                return client.post(x)
            """})
        code, text = jump_depth("billing/flow.py", "--root", ".", "--json", cwd=root)
        self.assertEqual(code, 0, text)
        self.assertEqual(json.loads(text)["summary"]["max_local_depth"], 2)

    def test_check_fails_on_depth_and_passes_when_flat(self):
        deep = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            def run():
                return a()

            def a():
                return b()

            def b():
                return 1
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=deep)
        self.assertEqual(code, 1)
        self.assertIn("local_depth 2 > 1", text)
        flat = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            def run():
                return a()

            def a():
                return 1
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=flat)
        self.assertEqual(code, 0, text)

    def test_outbound_calls_are_listed_with_file_and_line(self):
        root = self.project({**BILLING, "billing/flow.py": """
            from billing import client

            def run(x):
                return client.post(x)
            """})
        code, text = jump_depth("billing/flow.py", "--root", ".", cwd=root)
        self.assertEqual(code, 0, text)
        self.assertIn("billing/flow.py:4  client.post", text)


class Layout(ProjectTest):
    def test_helper_above_its_caller_is_flagged(self):
        root = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            def helper():
                return 1

            def run():
                return helper()
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("is not directly below its caller", text)

    def test_helper_called_twice_in_one_file_belongs_in_shared(self):
        root = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            def one():
                return helper()

            def two():
                return helper()

            def helper():
                return 1
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("move it to shared.py", text)

    def test_shared_leaves_must_not_call_each_other(self):
        root = self.project({"pkg/__init__.py": "", "pkg/shared.py": """
            def a():
                return b()

            def b():
                return 1
            """})
        code, text = jump_depth("pkg/shared.py", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("in shared.py: its functions never call each other", text)

    def test_init_with_code_or_reexport_is_a_facade(self):
        root = self.project({"pkg/__init__.py": "from pkg.task import run\n", "pkg/task.py": "def run():\n    return 1\n"})
        code, text = jump_depth("pkg", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("(a facade)", text)

    def test_empty_init_is_fine(self):
        root = self.project({"pkg/__init__.py": "", "pkg/task.py": "def run():\n    return 1\n"})
        code, text = jump_depth("pkg", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 0, text)

    def test_helper_directly_below_its_only_caller_is_fine(self):
        root = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            def run():
                return helper()

            def helper():
                return 1
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 0, text)


class HiddenImports(ProjectTest):
    def test_import_inside_a_function_needs_a_reason_comment(self):
        bare = self.project({"pkg/__init__.py": "", "pkg/other.py": "X = 1\n", "pkg/m.py": """
            def run():
                from pkg import other
                return other.X
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=bare)
        self.assertEqual(code, 1)
        self.assertIn("hidden_imports=1 (with a reason: 0)", text)
        reasoned = self.project({"pkg/__init__.py": "", "pkg/other.py": "X = 1\n", "pkg/m.py": """
            def run():
                from pkg import other  # circular import with other
                return other.X
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=reasoned)
        self.assertEqual(code, 0, text)
        self.assertIn("(with a reason: 1)", text)


class State(ProjectTest):
    def test_state_passed_through_self_is_flagged(self):
        root = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            class Job:
                def __init__(self):
                    self.rows = []

                def run(self):
                    self.load()
                    return self.count()

                def load(self):
                    self.rows = [1, 2]

                def count(self):
                    return len(self.rows)
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("state passed through self", text)

    def test_one_project_ancestor_layer_is_inheritance_one(self):
        root = self.project({"pkg/__init__.py": "", "pkg/m.py": """
            class Base:
                def go(self):
                    return 1

            class Child(Base):
                def go(self):
                    return super().go() + 1
            """})
        code, text = jump_depth("pkg/m.py", "--root", ".", "--json", cwd=root)
        self.assertEqual(json.loads(text)["summary"]["max_inheritance"], 1)


class Callers(ProjectTest):
    FILES = {
        "app/__init__.py": "",
        "app/core.py": "def work():\n    return 1\n",
        "app/views.py": "from app.core import work\n\ndef view():\n    return work()\n",
        "app/test_core.py": "from app.core import work\n",
        "compare/old/views.py": "from app.core import work\n",
    }

    def callers(self, *extra):
        root = self.project(self.FILES)
        code, text = jump_depth("--callers", "app.core", "--root", ".", "--usage", ".", "--json", *extra, cwd=root)
        self.assertEqual(code, 0, text)
        return json.loads(text)["callers"]

    def test_production_and_test_importers_are_told_apart(self):
        callers = self.callers()
        prod = {item["file"] for item in callers if not item["test"]}
        tests = {item["file"] for item in callers if item["test"]}
        self.assertIn("app/views.py", prod)
        self.assertIn("app/test_core.py", tests)

    def test_exclude_by_folder_name(self):
        self.assertTrue(any("compare" in item["file"] for item in self.callers()))
        self.assertFalse(any("compare" in item["file"] for item in self.callers("--exclude", "compare")))

    def test_exclude_by_path(self):
        self.assertFalse(any("compare" in item["file"] for item in self.callers("--exclude", "compare/old")))

    def test_nothing_is_excluded_by_default(self):
        self.assertTrue(any(item["file"].startswith("compare/") for item in self.callers()))


class KnownLimits(ProjectTest):
    FILES = {"app/__init__.py": "", "app/core.py": "def work():\n    return 1\n",
             "app/tests.py": "from app.core import work\n"}

    def importers_are_tests(self):
        root = self.project(self.FILES)
        code, text = jump_depth("--callers", "app.core", "--root", ".", "--usage", ".", "--json", cwd=root)
        self.assertEqual(code, 0, text)
        return [item["test"] for item in json.loads(text)["callers"]]

    def test_known_limit_django_tests_py_counts_as_production(self):
        """1.x: only test_*.py, *_test.py and a tests/ folder are test files. Django's tests.py is not."""
        self.assertEqual(self.importers_are_tests(), [False])

    @unittest.expectedFailure
    def test_django_tests_py_should_be_a_test_file(self):
        self.assertEqual(self.importers_are_tests(), [True])


class Forbid(ProjectTest):
    def test_forbidden_module_import_fails_check(self):
        root = self.project({"pkg/__init__.py": "", "pkg/old.py": "def f():\n    return 1\n",
                             "pkg/new.py": "from pkg import old\n\ndef run():\n    return old.f()\n"})
        code, text = jump_depth("pkg/new.py", "--root", ".", "--forbid", "pkg.old", "--check", cwd=root)
        self.assertEqual(code, 1)
        self.assertIn("pkg.old", text)


if __name__ == "__main__":
    unittest.main()

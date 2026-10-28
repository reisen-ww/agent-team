"""Check the portable examples and the acceptance harness, without model calls."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "small-team"
SPEC = importlib.util.spec_from_file_location("example_accept", EXAMPLE / "accept.py")
ACCEPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACCEPT)

CLI = '''import argparse, json, sys
p = argparse.ArgumentParser()
p.add_argument("input")
p.add_argument("--include-cancelled", action="store_true")
a = p.parse_args()
try:
    with open(a.input, encoding="utf-8") as f:
        orders = json.load(f)
    if type(orders) is not list:
        raise ValueError("array required")
    for o in orders:
        if (type(o) is not dict or not isinstance(o.get("id"), str)
            or o.get("status") not in ("paid", "cancelled")
            or type(o.get("amount_cents")) is not int or o["amount_cents"] < 0):
            raise ValueError("invalid order")
    include = DEFAULT_INCLUDE or a.include_cancelled
    print(json.dumps({"total_cents": sum(o["amount_cents"] for o in orders
                                        if include or o["status"] != "cancelled")}))
except (ValueError, OSError) as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
'''


class ExampleTests(unittest.TestCase):
    def test_all_published_records_have_expected_outcome_and_are_unchanged(self):
        for path in sorted((EXAMPLE / "records").glob("*.json")):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "check_run.py"), str(path)],
                                        capture_output=True, text=True, encoding="utf-8", timeout=10)
                expected = 1 if ".invalid." in path.name else 0
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["passed"], expected == 0)
                self.assertEqual(path.read_bytes(), before)

    def test_correct_programs_pass_both_revisions(self):
        for revision, include in [("R1", True), ("R2", False)]:
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "cli.py"
                path.write_text("DEFAULT_INCLUDE = " + repr(include) + "\n" + CLI, encoding="utf-8")
                report = ACCEPT.run_suite(path, revision)
                self.assertTrue(report["passed"], report["cases"])
                self.assertEqual(len(report["cases"]), 12)

    def test_old_default_does_not_pass_new_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli.py"
            path.write_text("DEFAULT_INCLUDE = True\n" + CLI, encoding="utf-8")
            report = ACCEPT.run_suite(path, "R2")
            self.assertFalse(report["passed"])
            self.assertFalse(next(c for c in report["cases"] if c["case"] == "default")["passed"])

    def test_constant_answer_does_not_pass_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli.py"
            path.write_text('import json; print(json.dumps(dict(total_cents=1800)))\n', encoding="utf-8")
            self.assertFalse(ACCEPT.run_suite(path, "R2")["passed"])

    def test_missing_program_is_setup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", str(EXAMPLE / "accept.py"),
                                     "--revision", "R2", "--program", str(Path(directory) / "absent.py")],
                                    capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["passed"])

    def test_success_json_inside_error_output_is_rejected(self):
        self.assertTrue(ACCEPT.reports_success('warning\n{"total_cents": 123}\n'))


if __name__ == "__main__":
    unittest.main()

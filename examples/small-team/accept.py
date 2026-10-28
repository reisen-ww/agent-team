"""Run synthetic CLI acceptance cases. Executes only the explicitly selected program."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def snapshot(program):
    return {
        path.relative_to(program.parent).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(program.parent.rglob("*.py")) if path.is_file()
    }


def reports_success(output):
    for candidate in [output, *output.splitlines()]:
        try:
            value = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and "total_cents" in value:
            return True
    return False


def run_suite(program, revision):
    program = Path(program).resolve(strict=True)
    fixture = Path(__file__).parent / "fixtures" / "orders.json"
    orders = json.loads(fixture.read_text(encoding="utf-8"))
    test_inputs = {"accept.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "fixtures/orders.json": hashlib.sha256(fixture.read_bytes()).hexdigest()}
    cases = [
        ("default", orders, [], 2300 if revision == "R1" else 1800),
        ("include-cancelled", orders, ["--include-cancelled"], 2300),
        ("empty", [], [], 0),
        ("all-cancelled", [{"id": "c", "status": "cancelled", "amount_cents": 19}], [], 19 if revision == "R1" else 0),
        ("negative", [{"id": "bad", "status": "paid", "amount_cents": -1}], [], None),
        ("fractional", [{"id": "bad", "status": "paid", "amount_cents": 1.5}], [], None),
        ("boolean", [{"id": "bad", "status": "paid", "amount_cents": True}], [], None),
        ("missing-amount", [{"id": "bad", "status": "paid"}], [], None),
        ("missing-id", [{"status": "paid", "amount_cents": 10}], [], None),
        ("invalid-status", [{"id": "bad", "status": "mystery", "amount_cents": 10}], [], None),
        ("invalid-root", {"orders": orders}, [], None),
        ("malformed-json", "{broken", [], None),
    ]
    before = snapshot(program)
    results = []
    with tempfile.TemporaryDirectory(prefix="agent-team-accept-") as directory:
        for name, value, flags, expected in cases:
            input_path = Path(directory) / (name + ".json")
            input_path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
            command = [sys.executable, "-B", str(program), str(input_path), *flags]
            result = {"case": name, "command": command, "expected_total": expected}
            try:
                run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
                result.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
                if expected is None:
                    result["passed"] = run.returncode != 0 and not reports_success(run.stdout)
                else:
                    try:
                        actual = json.loads(run.stdout)
                    except ValueError:
                        actual = None
                    result["passed"] = (run.returncode == 0 and isinstance(actual, dict)
                                        and type(actual.get("total_cents")) is int
                                        and actual["total_cents"] == expected)
            except (OSError, subprocess.TimeoutExpired) as error:
                result.update(passed=False, error=str(error))
            results.append(result)
    after = snapshot(program)
    return {"scope": "Synthetic CLI cases only; not independent model review or production validation",
            "revision": revision, "python": sys.version, "program": str(program),
            "test_inputs_sha256": test_inputs,
            "before_sha256": before, "after_sha256": after,
            "passed": before == after and all(item["passed"] for item in results), "cases": results}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", choices=["R1", "R2"], required=True)
    parser.add_argument("--program", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_suite(args.program, args.revision)
    except (OSError, ValueError) as error:
        report = {"passed": False, "error": str(error), "scope": "Acceptance setup failed"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

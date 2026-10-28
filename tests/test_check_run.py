from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_run import validate_record


def base_record():
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "protocol_version": "1",
        "evidence_level": "illustrative",
        "requirements": {"REQ-total": "R2"},
        "tasks": [
            {
                "id": "T1",
                "owner": "owner-a",
                "status": "accepted",
                "artifact_revision": "A1",
                "requirements": {"REQ-total": "R2"},
                "inputs": {},
                "waiting_on": [],
                "acceptance": {
                    "artifact_revision": "A1",
                    "requirements": {"REQ-total": "R2"},
                    "inputs": {},
                    "reviewer": "reviewer-a",
                    "evidence": ["evidence/log.txt:1"],
                },
            },
            {
                "id": "T2",
                "owner": "owner-b",
                "status": "in_progress",
                "artifact_revision": "A2",
                "requirements": {"REQ-total": "R2"},
                "inputs": {"T1": "A1"},
                "waiting_on": [],
                "acceptance": None,
            },
            {
                "id": "T3",
                "owner": "owner-c",
                "status": "ready",
                "artifact_revision": None,
                "requirements": {"REQ-total": "R2"},
                "inputs": {},
                "waiting_on": ["T2"],
                "acceptance": None,
            },
        ],
        "actions": [
            {
                "id": "ACT1",
                "task_id": "T1",
                "input_version": "I1",
                "payload": {"message": "same", "count": 1},
                "state": "completed",
                "result_ref": "results/ACT1.txt",
            },
            {
                "id": "ACT2",
                "task_id": "T2",
                "input_version": "I2",
                "payload": {"message": "in progress"},
                "state": "in_progress",
                "result_ref": None,
            },
        ],
        "deliveries": [
            {
                "id": "DLV1",
                "action_id": "ACT1",
                "task_id": "T1",
                "input_version": "I1",
                "payload": {"count": 1, "message": "same"},
            },
            {
                "id": "DLV2",
                "action_id": "ACT1",
                "task_id": "T1",
                "input_version": "I1",
                "payload": {"message": "same", "count": 1},
            },
        ],
        "executions": [{"id": "EXE1", "action_id": "ACT1"}],
        "metrics": {
            "accepted_deliverables": 1,
            "elapsed_minutes": 12.5,
            "review_wait_minutes": None,
            "rework_batches": 0,
            "billed_cost": None,
        },
    }


class CheckRunTests(unittest.TestCase):
    def setUp(self):
        self.good = base_record()

    def assert_has_error(self, record, fragment):
        errors = validate_record(record)
        self.assertTrue(
            any(fragment in error for error in errors),
            msg=f"expected {fragment!r} in {errors!r}",
        )
        return errors

    def test_valid_record_and_repeated_delivery(self):
        snapshot = copy.deepcopy(self.good)
        self.assertEqual(validate_record(self.good), [])
        self.assertEqual(self.good, snapshot)

    def test_root_shape_and_schema_types(self):
        for field in (
            "schema_version",
            "run_id",
            "protocol_version",
            "evidence_level",
            "requirements",
            "tasks",
            "actions",
            "deliveries",
            "executions",
        ):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.good)
                del broken[field]
                self.assert_has_error(broken, field)

        cases = [
            ("schema_version", True),
            ("schema_version", 1.0),
            ("run_id", ""),
            ("protocol_version", 1),
            ("evidence_level", "verified"),
            ("requirements", []),
            ("tasks", {}),
            ("actions", "ACT1"),
            ("deliveries", None),
            ("executions", 1),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.good)
                broken[field] = value
                self.assertTrue(validate_record(broken))

        self.assertTrue(validate_record([]))
        self.assertTrue(validate_record(None))

    def test_all_recorded_objects_and_arrays_are_shape_checked(self):
        mutations = [
            lambda r: r["tasks"][0]["requirements"].update({"REQ-total": 2}),
            lambda r: r["tasks"][1].update({"inputs": []}),
            lambda r: r["tasks"][2].update({"waiting_on": {}}),
            lambda r: r["tasks"][1].update({"acceptance": []}),
            lambda r: r["actions"][1].update({"payload": []}),
            lambda r: r["deliveries"][0].update({"payload": "not an object"}),
            lambda r: r["executions"][0].update({"id": ""}),
            lambda r: r["metrics"].update({"billed_cost": []}),
        ]
        for mutate in mutations:
            broken = copy.deepcopy(self.good)
            mutate(broken)
            self.assertTrue(validate_record(broken))

    def test_duplicate_ids_are_rejected(self):
        for collection in ("tasks", "actions", "deliveries", "executions"):
            with self.subTest(collection=collection):
                broken = copy.deepcopy(self.good)
                broken[collection].append(copy.deepcopy(broken[collection][0]))
                self.assert_has_error(broken, "duplicate")

    def test_task_fields_references_and_status(self):
        cases = [
            ("owner", ""),
            ("status", "done"),
            ("artifact_revision", 7),
            ("requirements", {"REQ-unknown": "R1"}),
            ("inputs", {"MISSING": "A0"}),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.good)
                broken["tasks"][1][field] = value
                self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["inputs"] = {"T2": "A2"}
        self.assert_has_error(broken, "itself")

    def test_unaccepted_task_may_retain_old_requirements(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["status"] = "review_required"
        broken["tasks"][1]["requirements"] = {"REQ-total": "R1"}
        broken["tasks"][1]["acceptance"] = copy.deepcopy(
            broken["tasks"][0]["acceptance"]
        )
        broken["tasks"][1]["acceptance"]["requirements"] = {"REQ-total": "R1"}
        broken["tasks"][1]["acceptance"]["artifact_revision"] = "A2"
        broken["tasks"][1]["acceptance"]["inputs"] = {"T1": "A1"}
        self.assertEqual(validate_record(broken), [])

        broken["tasks"][1]["requirements"] = {"OTHER": "R1"}
        self.assert_has_error(broken, "unknown requirement")

    def test_task_requirements_and_inputs_may_be_empty(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["requirements"] = {}
        broken["tasks"][1]["inputs"] = {}
        self.assertEqual(validate_record(broken), [])

    def test_accepted_task_requires_artifact_snapshot_and_resolved_state(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][0]["artifact_revision"] = None
        self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        broken["tasks"][0]["acceptance"] = None
        self.assert_has_error(broken, "acceptance snapshot")

        broken = copy.deepcopy(self.good)
        broken["tasks"][0]["waiting_on"] = ["T2"]
        self.assert_has_error(broken, "waiting")

        for state in ("pending", "in_progress", "unknown"):
            with self.subTest(state=state):
                broken = copy.deepcopy(self.good)
                broken["actions"].append(
                    {
                        "id": "ACT3",
                        "task_id": "T1",
                        "input_version": "I3",
                        "payload": {},
                        "state": state,
                        "result_ref": None,
                    }
                )
                self.assert_has_error(broken, "unresolved action")

    def test_acceptance_snapshot_matches_current_task(self):
        mutations = [
            lambda a: a.update({"artifact_revision": "A0"}),
            lambda a: a.update({"requirements": {"REQ-total": "R1"}}),
            lambda a: a.update({"requirements": {}}),
            lambda a: a.update({"inputs": {"T2": "A2"}}),
            lambda a: a.update({"reviewer": ""}),
            lambda a: a.update({"evidence": []}),
            lambda a: a.update({"evidence": [1]}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                broken = copy.deepcopy(self.good)
                mutate(broken["tasks"][0]["acceptance"])
                self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["acceptance"] = {"evidence": "bad"}
        errors = validate_record(broken)
        self.assertTrue(any("reviewer" in error for error in errors), errors)
        self.assertTrue(any("evidence" in error for error in errors), errors)

    def test_accepted_inputs_must_be_accepted_and_current(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["status"] = "accepted"
        broken["tasks"][1]["acceptance"] = copy.deepcopy(
            broken["tasks"][0]["acceptance"]
        )
        broken["tasks"][1]["acceptance"]["artifact_revision"] = "A2"
        broken["tasks"][1]["acceptance"]["inputs"] = {"T1": "A1"}
        broken["tasks"][0]["status"] = "review_required"
        broken["tasks"][0]["acceptance"] = None
        broken["metrics"]["accepted_deliverables"] = 1
        self.assert_has_error(broken, "unaccepted input")

        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["inputs"] = {"T1": "OLD"}
        self.assertEqual(validate_record(broken), [])

    def test_accepted_task_requires_current_requirements(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][0]["requirements"] = {"REQ-total": "R1"}
        broken["tasks"][0]["acceptance"]["requirements"] = {"REQ-total": "R1"}
        self.assert_has_error(broken, "expected 'R2'")

    def test_nonaccepted_input_may_be_stale_or_have_no_artifact(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["artifact_revision"] = None
        broken["tasks"][2]["inputs"] = {"T2": "OLD"}
        self.assertEqual(validate_record(broken), [])

        broken["tasks"][2]["status"] = "accepted"
        broken["tasks"][2]["artifact_revision"] = "A3"
        broken["tasks"][2]["acceptance"] = copy.deepcopy(
            broken["tasks"][0]["acceptance"]
        )
        broken["tasks"][2]["acceptance"]["artifact_revision"] = "A3"
        broken["tasks"][2]["acceptance"]["inputs"] = {"T2": "OLD"}
        broken["metrics"]["accepted_deliverables"] = 2
        self.assertTrue(validate_record(broken))

    def test_dependency_and_waiting_cycles_are_rejected(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][0].update(
            {"status": "in_progress", "acceptance": None}
        )
        broken["tasks"][0]["inputs"] = {"T2": "A2"}
        broken["tasks"][1]["inputs"] = {"T1": "A1"}
        self.assert_has_error(broken, "input dependency cycle")

        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["waiting_on"] = ["T3"]
        broken["tasks"][2]["waiting_on"] = ["T2"]
        self.assert_has_error(broken, "waiting_on cycle")

        broken = copy.deepcopy(self.good)
        broken["tasks"][2]["waiting_on"] = ["MISSING"]
        self.assert_has_error(broken, "unknown waiting")

    def test_action_ledger_shape_and_accepted_states(self):
        cases = [
            ("task_id", "MISSING"),
            ("input_version", ""),
            ("state", "queued"),
            ("payload", []),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.good)
                broken["actions"][1][field] = value
                self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        broken["actions"][0]["result_ref"] = None
        self.assert_has_error(broken, "completed action")

    def test_retry_requires_closed_original_same_context_and_decision(self):
        broken = copy.deepcopy(self.good)
        broken["actions"][1]["state"] = "failed"
        broken["actions"].append(
            {
                "id": "ACT3",
                "task_id": "T2",
                "input_version": "I2",
                "payload": {"message": "retry"},
                "state": "failed",
                "result_ref": None,
                "retry_of": "ACT2",
                "retry_decision_ref": "decision:1",
            }
        )
        self.assertEqual(validate_record(broken), [])

        cases = [
            ("unknown", "ACT2", "I2", "T2", "failed or not_executed"),
            ("in_progress", "ACT2", "I2", "T2", "retry_of"),
            ("failed", "MISSING", "I2", "T2", "unknown retried"),
            ("failed", "ACT2", "OTHER", "T2", "same input_version"),
            ("failed", "ACT2", "I2", "T1", "same task"),
        ]
        for state, retry_of, version, task_id, fragment in cases:
            with self.subTest(state=state, retry_of=retry_of):
                broken = copy.deepcopy(self.good)
                broken["actions"][1]["state"] = state
                broken["actions"].append(
                    {
                        "id": "ACT3",
                        "task_id": task_id,
                        "input_version": version,
                        "payload": {},
                        "state": "failed",
                        "result_ref": None,
                        "retry_of": retry_of,
                        "retry_decision_ref": "decision:1",
                    }
                )
                self.assert_has_error(broken, fragment)

    def test_retry_cannot_fork_cycle_or_omit_decision(self):
        def failed(action_id, retry_of=None):
            action = {
                "id": action_id,
                "task_id": "T2",
                "input_version": "I2",
                "payload": {},
                "state": "failed",
                "result_ref": None,
            }
            if retry_of is not None:
                action.update(
                    {
                        "retry_of": retry_of,
                        "retry_decision_ref": "decision:1",
                    }
                )
            return action

        broken = copy.deepcopy(self.good)
        broken["actions"] = [failed("A"), failed("B", "A"), failed("C", "A")]
        self.assert_has_error(broken, "multiple direct retry")

        broken = copy.deepcopy(self.good)
        broken["actions"] = [failed("A", "B"), failed("B", "A")]
        self.assert_has_error(broken, "retry cycle")

        broken = copy.deepcopy(self.good)
        broken["actions"] = [
            failed("attempt-one"),
            failed("attempt-two", "attempt-one"),
            failed("attempt-three", "attempt-two"),
        ]
        broken["actions"][0]["retry_of"] = "attempt-three"
        broken["actions"][0]["retry_decision_ref"] = "decision:1"
        self.assert_has_error(broken, "retry cycle")

        broken = copy.deepcopy(self.good)
        broken["actions"] = [failed("A"), failed("B")]
        broken["actions"][1]["retry_of"] = "A"
        self.assert_has_error(broken, "retry_decision_ref")

        broken = copy.deepcopy(self.good)
        broken["actions"] = [failed("A"), failed("B", "B")]
        self.assert_has_error(broken, "itself")

        broken = copy.deepcopy(self.good)
        broken["actions"] = [failed("A"), failed("B", "A")]
        broken["actions"][0]["state"] = "completed"
        broken["actions"][0]["result_ref"] = "result:A"
        broken["actions"].append(failed("C", "B"))
        self.assert_has_error(broken, "most recent closed attempt")

    def test_delivery_must_match_action_and_may_repeat(self):
        broken = copy.deepcopy(self.good)
        broken["deliveries"][1]["payload"]["count"] = 2
        self.assert_has_error(broken, "action ledger")

        for field, value in (("task_id", "T2"), ("input_version", "I0")):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.good)
                broken["deliveries"][0][field] = value
                self.assert_has_error(broken, "action ledger")

        broken = copy.deepcopy(self.good)
        broken["deliveries"][0]["action_id"] = "MISSING"
        self.assert_has_error(broken, "unknown action")

        broken = copy.deepcopy(self.good)
        broken["deliveries"][1]["payload"]["count"] = True
        self.assert_has_error(broken, "action ledger")

    def test_execution_is_unique_per_action(self):
        broken = copy.deepcopy(self.good)
        broken["executions"].append({"id": "EXE2", "action_id": "ACT1"})
        self.assert_has_error(broken, "more than one execution")

        broken = copy.deepcopy(self.good)
        broken["executions"][0]["action_id"] = "MISSING"
        self.assert_has_error(broken, "unknown action")

        broken = copy.deepcopy(self.good)
        broken["executions"].append(copy.deepcopy(broken["executions"][0]))
        self.assert_has_error(broken, "duplicate execution")

    def test_metrics_types_and_accepted_count(self):
        cases = [
            ("accepted_deliverables", True),
            ("accepted_deliverables", 0),
            ("accepted_deliverables", 1.0),
            ("rework_batches", True),
            ("rework_batches", -1),
            ("elapsed_minutes", True),
            ("elapsed_minutes", -0.1),
            ("elapsed_minutes", math.inf),
            ("review_wait_minutes", "2"),
            ("integration_wait_minutes", math.nan),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.good)
                broken["metrics"][field] = value
                self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        broken["metrics"]["billed_cost"] = {
            "amount": True,
            "currency": "",
            "source": "",
            "read_at": "",
        }
        errors = validate_record(broken)
        self.assertGreaterEqual(len(errors), 4)

        broken = copy.deepcopy(self.good)
        broken["metrics"]["billed_cost"] = {
            "amount": 1.25,
            "currency": "USD",
            "source": "invoice:1",
            "read_at": "2026-10-28T00:00:00Z",
        }
        self.assertEqual(validate_record(broken), [])

    def test_nonfinite_and_cycles_do_not_raise(self):
        broken = copy.deepcopy(self.good)
        broken["tasks"][1]["artifact_revision"] = math.nan
        self.assertTrue(validate_record(broken))

        broken = copy.deepcopy(self.good)
        cycle = {"value": 1}
        cycle["self"] = cycle
        broken["actions"][1]["payload"]["cycle"] = cycle
        self.assert_has_error(broken, "reference cycle")


class CheckRunCliTests(unittest.TestCase):
    def run_cli(self, args):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "check_run.py"), *args],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_cli_valid_record_exits_zero_with_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "record.json"
            record.write_text(json.dumps(base_record()), encoding="utf-8")
            completed = self.run_cli([str(record)])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["scope"])

    def test_cli_chinese_error_is_ascii_safe_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "中文记录.json"
            path.write_text("{", encoding="utf-8")
            completed = self.run_cli([str(path)])
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertTrue(completed.stdout.isascii())
        self.assertFalse(json.loads(completed.stdout)["passed"])

    def test_cli_malformed_inputs_exit_one_with_json_report(self):
        malformed = {
            "syntax.json": "{not json}",
            "duplicate.json": '{"schema_version": 1, "schema_version": 1}',
            "nan.json": '{"schema_version": NaN}',
            "infinity.json": '{"schema_version": Infinity}',
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for filename, content in malformed.items():
                with self.subTest(filename=filename):
                    path = directory / filename
                    path.write_text(content, encoding="utf-8")
                    completed = self.run_cli([str(path)])
                    self.assertEqual(completed.returncode, 1, completed.stderr)
                    report = json.loads(completed.stdout)
                    self.assertFalse(report["ok"])
                    self.assertTrue(report["errors"])
                    self.assertTrue(report["scope"])

            missing = self.run_cli([str(directory / "missing.json")])
            self.assertEqual(missing.returncode, 1, missing.stderr)
            self.assertFalse(json.loads(missing.stdout)["ok"])

    def test_cli_usage_error_exits_one(self):
        completed = self.run_cli([])
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(json.loads(completed.stdout)["ok"])

    def test_cli_utf8_bom_and_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bom = directory / "bom.json"
            bom.write_text(json.dumps(base_record()), encoding="utf-8-sig")
            completed = self.run_cli([str(bom)])
            self.assertEqual(completed.returncode, 0, completed.stdout)

            invalid = directory / "invalid.json"
            invalid.write_bytes(b"{\"run_id\": \"\xff\"}")
            completed = self.run_cli([str(invalid)])
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(json.loads(completed.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()

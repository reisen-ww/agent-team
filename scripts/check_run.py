#!/usr/bin/env python3
"""Offline consistency checker for agent-team run records.

This checks a JSON record's shape, references, and internal consistency.  It does
not verify that the record describes real work, identities, permissions, budgets,
or the contents behind evidence locators.
"""

from __future__ import annotations

import json
import math
import sys


SCOPE = (
    "Checks only the supplied JSON record's shape, references, and internal "
    "consistency. It does not verify real execution, identities, permissions, "
    "budgets, or the content behind evidence locators; recorded declarations are "
    "not proof of actual behavior."
)

_TASK_STATES = {
    "ready",
    "in_progress",
    "blocked",
    "review_required",
    "accepted",
    "cancelled",
}
_ACTION_STATES = {
    "pending",
    "in_progress",
    "completed",
    "unknown",
    "failed",
    "not_executed",
    "cancelled",
}
_MISSING = object()


def _error(errors, path, message):
    errors.append(f"{path}: {message}")


def _nonempty_string(value):
    return type(value) is str and bool(value)


def _integer(value):
    return type(value) is int


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json_equal(left, right):
    """Compare JSON values without Python's True == 1 or tuple coercion."""
    if type(left) is not type(right):
        if _number(left) and _number(right):
            return left == right
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _check_json_tree(value, path, errors, active=None):
    """Reject non-JSON values, non-string keys, cycles, and non-finite numbers."""
    if active is None:
        active = set()
    kind = type(value)
    if value is None or kind in (str, bool, int):
        return
    if kind is float:
        if not math.isfinite(value):
            _error(errors, path, "number must be finite")
        return
    if kind is list:
        marker = id(value)
        if marker in active:
            _error(errors, path, "array contains a reference cycle")
            return
        active.add(marker)
        try:
            for index, item in enumerate(value):
                _check_json_tree(item, f"{path}[{index}]", errors, active)
        finally:
            active.remove(marker)
        return
    if kind is dict:
        marker = id(value)
        if marker in active:
            _error(errors, path, "object contains a reference cycle")
            return
        active.add(marker)
        try:
            for key, item in value.items():
                if type(key) is not str:
                    _error(errors, path, "object keys must be strings")
                    continue
                _check_json_tree(item, f"{path}.{key}", errors, active)
        finally:
            active.remove(marker)
        return
    _error(errors, path, f"unsupported JSON value type: {kind.__name__}")


def _require_object(value, path, errors):
    if type(value) is dict:
        return True
    _error(errors, path, "must be an object")
    return False


def _require_array(value, path, errors):
    if type(value) is list:
        return True
    _error(errors, path, "must be an array")
    return False


def _required(object_value, key, path, errors):
    if key in object_value:
        return object_value[key]
    _error(errors, f"{path}.{key}", "is required")
    return _MISSING


def _string_field(object_value, key, path, errors, *, nullable=False):
    value = _required(object_value, key, path, errors)
    if value is _MISSING:
        return value
    if value is None and nullable:
        return value
    if not _nonempty_string(value):
        _error(
            errors,
            f"{path}.{key}",
            "must be a non-empty string" + (" or null" if nullable else ""),
        )
    return value


def _id_version_map(object_value, key, path, errors):
    value = _required(object_value, key, path, errors)
    if value is _MISSING:
        return {}
    if not _require_object(value, f"{path}.{key}", errors):
        return {}
    for item_id, version in value.items():
        if not _nonempty_string(item_id):
            _error(errors, f"{path}.{key}", "keys must be non-empty strings")
        if not _nonempty_string(version):
            _error(
                errors,
                f"{path}.{key}.{item_id}",
                "version must be a non-empty string",
            )
    return value


def _check_requirement_references(mapping, root_requirements, path, errors):
    if type(mapping) is not dict:
        return
    for requirement_id, version in mapping.items():
        if not _nonempty_string(requirement_id) or not _nonempty_string(version):
            continue
        if requirement_id not in root_requirements:
            _error(errors, path, f"unknown requirement {requirement_id!r}")


def _check_requirements_against_root(mapping, root_requirements, path, errors):
    if type(mapping) is not dict:
        return
    _check_requirement_references(mapping, root_requirements, path, errors)
    for requirement_id, version in mapping.items():
        if not _nonempty_string(requirement_id) or not _nonempty_string(version):
            continue
        if (
            requirement_id in root_requirements
            and root_requirements[requirement_id] != version
        ):
            _error(
                errors,
                path,
                f"requirement {requirement_id!r} is {version!r}, "
                f"expected {root_requirements[requirement_id]!r}",
            )


def _cycle_nodes(edges, order):
    """Return nodes left after removing acyclic roots, or an empty list."""
    indegree = {node: 0 for node in order}
    outgoing = {node: set() for node in order}
    for source, targets in edges.items():
        targets = {targets} if isinstance(targets, str) else targets
        for target in targets:
            if source in indegree and target in indegree:
                outgoing[target].add(source)
                indegree[source] += 1
    queue = [node for node in order if indegree[node] == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for child in outgoing[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return [] if seen == len(order) else [
        node for node in order if indegree[node] > 0
    ]


class _Validator:
    def __init__(self, data):
        self.data = data
        self.errors = []
        self.requirements = {}
        self.tasks = []
        self.task_by_id = {}
        self.actions = []
        self.action_by_id = {}

    def run(self):
        _check_json_tree(self.data, "$", self.errors)
        if not _require_object(self.data, "$", self.errors):
            return

        schema_version = _required(self.data, "schema_version", "$", self.errors)
        if schema_version is not _MISSING and (
            not _integer(schema_version) or schema_version != 1
        ):
            _error(self.errors, "$.schema_version", "must be the integer 1")
        _string_field(self.data, "run_id", "$", self.errors)
        _string_field(self.data, "protocol_version", "$", self.errors)
        evidence_level = _string_field(
            self.data, "evidence_level", "$", self.errors
        )
        if evidence_level not in (_MISSING, None, "illustrative", "recorded"):
            _error(
                self.errors,
                "$.evidence_level",
                "must be 'illustrative' or 'recorded'",
            )

        requirements = _required(
            self.data, "requirements", "$", self.errors
        )
        if requirements is not _MISSING:
            self.requirements = _id_version_map(
                {"requirements": requirements}, "requirements", "$", self.errors
            )

        tasks = _required(self.data, "tasks", "$", self.errors)
        actions = _required(self.data, "actions", "$", self.errors)
        deliveries = _required(self.data, "deliveries", "$", self.errors)
        executions = _required(self.data, "executions", "$", self.errors)

        if tasks is not _MISSING and _require_array(tasks, "$.tasks", self.errors):
            self._collect_tasks(tasks)
        if actions is not _MISSING and _require_array(
            actions, "$.actions", self.errors
        ):
            self._collect_actions(actions)

        self._check_tasks()
        self._check_action_references_and_retries()
        self._check_deliveries(deliveries)
        self._check_executions(executions)

        metrics = self.data.get("metrics", _MISSING)
        if metrics is not _MISSING:
            self._check_metrics(metrics)

    def _collect_tasks(self, raw_tasks):
        for index, task in enumerate(raw_tasks):
            path = f"$.tasks[{index}]"
            if not _require_object(task, path, self.errors):
                continue
            self.tasks.append((path, task))
            task_id = task.get("id")
            if not _nonempty_string(task_id):
                continue
            if task_id in self.task_by_id:
                _error(self.errors, f"{path}.id", f"duplicate task id {task_id!r}")
            else:
                self.task_by_id[task_id] = task

    def _collect_actions(self, raw_actions):
        for index, action in enumerate(raw_actions):
            path = f"$.actions[{index}]"
            if not _require_object(action, path, self.errors):
                continue
            self.actions.append((path, action))
            action_id = action.get("id")
            if not _nonempty_string(action_id):
                continue
            if action_id in self.action_by_id:
                _error(
                    self.errors, f"{path}.id", f"duplicate action id {action_id!r}"
                )
            else:
                self.action_by_id[action_id] = action

    def _check_input_references(
        self, inputs, path, task, accepted_only=False, require_current=False
    ):
        if type(inputs) is not dict:
            return
        task_id = task.get("id")
        for input_id, input_version in inputs.items():
            if not _nonempty_string(input_id) or not _nonempty_string(input_version):
                continue
            if input_id == task_id:
                _error(self.errors, path, "input dependency cannot reference itself")
                continue
            target = self.task_by_id.get(input_id)
            if target is None:
                _error(self.errors, path, f"unknown input task {input_id!r}")
                continue
            if accepted_only and target.get("status") != "accepted":
                _error(
                    self.errors,
                    path,
                    f"accepted task depends on unaccepted input {input_id!r}",
                )
            if not require_current:
                continue
            artifact = target.get("artifact_revision")
            if not _nonempty_string(artifact):
                _error(
                    self.errors,
                    path,
                    f"input task {input_id!r} has no artifact revision",
                )
            elif artifact != input_version:
                _error(
                    self.errors,
                    path,
                    f"input {input_id!r} is {input_version!r}, "
                    f"but its artifact revision is {artifact!r}",
                )

    def _check_acceptance(self, task, path, acceptance, status):
        if acceptance is None:
            return
        acceptance_path = f"{path}.acceptance"
        if not _require_object(acceptance, acceptance_path, self.errors):
            return
        snapshot_artifact = _string_field(
            acceptance, "artifact_revision", acceptance_path, self.errors
        )
        snapshot_requirements = _id_version_map(
            acceptance, "requirements", acceptance_path, self.errors
        )
        snapshot_inputs = _id_version_map(
            acceptance, "inputs", acceptance_path, self.errors
        )
        _string_field(acceptance, "reviewer", acceptance_path, self.errors)
        evidence = _required(acceptance, "evidence", acceptance_path, self.errors)
        if evidence is not _MISSING and _require_array(
            evidence, f"{acceptance_path}.evidence", self.errors
        ):
            if not evidence:
                _error(
                    self.errors,
                    f"{acceptance_path}.evidence",
                    "must not be empty",
                )
            for index, item in enumerate(evidence):
                if not _nonempty_string(item):
                    _error(
                        self.errors,
                        f"{acceptance_path}.evidence[{index}]",
                        "must be a non-empty locator string",
                    )

        if status == "accepted":
            current_artifact = task.get("artifact_revision")
            _check_requirements_against_root(
                snapshot_requirements,
                self.requirements,
                f"{acceptance_path}.requirements",
                self.errors,
            )
            self._check_input_references(
                snapshot_inputs,
                f"{acceptance_path}.inputs",
                task,
                accepted_only=True,
                require_current=True,
            )
            if snapshot_artifact != current_artifact:
                _error(
                    self.errors,
                    f"{acceptance_path}.artifact_revision",
                    "does not match the current task artifact revision",
                )
            if snapshot_requirements != task.get("requirements"):
                _error(
                    self.errors,
                    f"{acceptance_path}.requirements",
                    "does not match the task's adopted requirements",
                )
            if snapshot_inputs != task.get("inputs"):
                _error(
                    self.errors,
                    f"{acceptance_path}.inputs",
                    "does not match the task's direct inputs",
                )

    def _check_tasks(self):
        artifact_edges = {}
        waiting_edges = {}
        accepted_count = 0
        accepted_ids = set()

        for path, task in self.tasks:
            task_id = task.get("id")
            if not _nonempty_string(task_id):
                _error(self.errors, f"{path}.id", "must be a non-empty string")
            _string_field(task, "owner", path, self.errors)
            status = _string_field(task, "status", path, self.errors)
            if status not in (_MISSING, None) and status not in _TASK_STATES:
                _error(self.errors, f"{path}.status", "is not a known task status")
            artifact = _string_field(
                task, "artifact_revision", path, self.errors, nullable=True
            )
            requirements = _id_version_map(
                task, "requirements", path, self.errors
            )
            inputs = _id_version_map(task, "inputs", path, self.errors)
            waiting = _required(task, "waiting_on", path, self.errors)
            acceptance = _required(task, "acceptance", path, self.errors)

            if waiting is not _MISSING and _require_array(
                waiting, f"{path}.waiting_on", self.errors
            ):
                waiting_edges[task_id] = set()
                for index, waited_id in enumerate(waiting):
                    if not _nonempty_string(waited_id):
                        _error(
                            self.errors,
                            f"{path}.waiting_on[{index}]",
                            "must be a non-empty task id",
                        )
                        continue
                    if waited_id == task_id:
                        _error(
                            self.errors,
                            f"{path}.waiting_on",
                            "waiting dependency cannot reference itself",
                        )
                    elif waited_id not in self.task_by_id:
                        _error(
                            self.errors,
                            f"{path}.waiting_on",
                            f"unknown waiting task {waited_id!r}",
                        )
                    elif _nonempty_string(task_id):
                        waiting_edges[task_id].add(waited_id)

            _check_requirement_references(
                requirements, self.requirements, f"{path}.requirements", self.errors
            )
            self._check_input_references(inputs, f"{path}.inputs", task)
            if _nonempty_string(task_id):
                artifact_edges[task_id] = {
                    key for key in inputs if _nonempty_string(key)
                }

            if status == "accepted":
                accepted_count += 1
                if _nonempty_string(task_id):
                    accepted_ids.add(task_id)
                if not _nonempty_string(artifact):
                    _error(
                        self.errors,
                        f"{path}.artifact_revision",
                        "accepted task must have an artifact revision",
                    )
                if acceptance is None or acceptance is _MISSING:
                    _error(
                        self.errors,
                        f"{path}.acceptance",
                        "accepted task must have an acceptance snapshot",
                    )
                if type(waiting) is list and waiting:
                    _error(
                        self.errors,
                        f"{path}.waiting_on",
                        "accepted task cannot still be waiting",
                    )
                _check_requirements_against_root(
                    requirements,
                    self.requirements,
                    f"{path}.requirements",
                    self.errors,
                )
                self._check_input_references(
                    inputs,
                    f"{path}.inputs",
                    task,
                    accepted_only=True,
                    require_current=True,
                )
            if acceptance not in (_MISSING, None):
                self._check_acceptance(task, path, acceptance, status)

        order = [
            task.get("id")
            for _, task in self.tasks
            if _nonempty_string(task.get("id"))
        ]
        cycle = _cycle_nodes(artifact_edges, order)
        if cycle:
            _error(
                self.errors,
                "$.tasks",
                "input dependency cycle involving: " + ", ".join(cycle),
            )
        cycle = _cycle_nodes(waiting_edges, order)
        if cycle:
            _error(
                self.errors,
                "$.tasks",
                "waiting_on cycle involving: " + ", ".join(cycle),
            )

        self.accepted_count = accepted_count
        self.accepted_ids = accepted_ids

    def _check_action_references_and_retries(self):
        retry_edges = {}
        retry_children = {}
        for path, action in self.actions:
            action_id = action.get("id")
            if not _nonempty_string(action_id):
                _error(self.errors, f"{path}.id", "must be a non-empty string")
            task_id = _string_field(action, "task_id", path, self.errors)
            if (
                task_id is not _MISSING
                and _nonempty_string(task_id)
                and task_id not in self.task_by_id
            ):
                _error(self.errors, f"{path}.task_id", f"unknown task {task_id!r}")
            input_version = _string_field(
                action, "input_version", path, self.errors
            )
            payload = _required(action, "payload", path, self.errors)
            if payload is not _MISSING:
                _require_object(payload, f"{path}.payload", self.errors)
            state = _string_field(action, "state", path, self.errors)
            if state not in (_MISSING, None) and state not in _ACTION_STATES:
                _error(self.errors, f"{path}.state", "is not a known action state")
            result_ref = _string_field(
                action, "result_ref", path, self.errors, nullable=True
            )
            if state == "completed" and result_ref is not _MISSING and not _nonempty_string(result_ref):
                _error(
                    self.errors,
                    f"{path}.result_ref",
                    "completed action must have a non-empty result locator",
                )

            has_retry_of = "retry_of" in action
            has_decision = "retry_decision_ref" in action
            if has_retry_of != has_decision:
                _error(
                    self.errors,
                    path,
                    "retry_of and retry_decision_ref must be present together",
                )
            if not has_retry_of:
                continue
            retry_of = _string_field(action, "retry_of", path, self.errors)
            _string_field(action, "retry_decision_ref", path, self.errors)
            if not _nonempty_string(retry_of):
                continue
            if retry_of == action_id:
                _error(self.errors, f"{path}.retry_of", "cannot reference itself")
                continue
            target = self.action_by_id.get(retry_of)
            if target is None:
                _error(
                    self.errors,
                    f"{path}.retry_of",
                    f"unknown retried action {retry_of!r}",
                )
                continue
            if _nonempty_string(action_id):
                retry_edges[action_id] = retry_of
                retry_children.setdefault(retry_of, []).append(action_id)
            target_state = target.get("state")
            if target_state not in ("failed", "not_executed"):
                _error(
                    self.errors,
                    f"{path}.retry_of",
                    f"original action must be failed or not_executed, not {target_state!r}",
                )
            if target.get("task_id") != task_id:
                _error(
                    self.errors,
                    f"{path}.retry_of",
                    "retry must stay on the same task",
                )
            if target.get("input_version") != input_version:
                _error(
                    self.errors,
                    f"{path}.retry_of",
                    "retry must use the same input_version",
                )

        for parent, children in retry_children.items():
            if len(children) > 1:
                _error(
                    self.errors,
                    f"$.actions ({parent})",
                    "has multiple direct retry successors: " + ", ".join(children),
                )
        cycle = _cycle_nodes(retry_edges, list(self.action_by_id))
        if cycle:
            _error(
                self.errors,
                "$.actions",
                "retry cycle involving: " + ", ".join(cycle),
            )

        for path, action in self.actions:
            if "retry_of" not in action:
                continue
            retry_of = action.get("retry_of")
            target = self.action_by_id.get(retry_of)
            if target is None or "retry_of" not in target:
                continue
            earlier = self.action_by_id.get(target.get("retry_of"))
            if earlier is None:
                continue
            if earlier.get("state") not in ("failed", "not_executed"):
                _error(
                    self.errors,
                    f"{path}.retry_of",
                    "a retry after a retry must follow the most recent closed attempt",
                )

        for path, action in self.actions:
            if action.get("task_id") in self.accepted_ids and action.get(
                "state"
            ) in ("pending", "in_progress", "unknown"):
                _error(
                    self.errors,
                    f"{path}.state",
                    "accepted task still has an unresolved action",
                )

    def _check_deliveries(self, deliveries):
        if deliveries is _MISSING or not _require_array(
            deliveries, "$.deliveries", self.errors
        ):
            return
        by_id = {}
        for index, delivery in enumerate(deliveries):
            path = f"$.deliveries[{index}]"
            if not _require_object(delivery, path, self.errors):
                continue
            delivery_id = _string_field(delivery, "id", path, self.errors)
            if _nonempty_string(delivery_id):
                if delivery_id in by_id:
                    _error(
                        self.errors,
                        f"{path}.id",
                        f"duplicate delivery id {delivery_id!r}",
                    )
                else:
                    by_id[delivery_id] = delivery
            action_id = _string_field(delivery, "action_id", path, self.errors)
            task_id = _string_field(delivery, "task_id", path, self.errors)
            input_version = _string_field(
                delivery, "input_version", path, self.errors
            )
            payload = _required(delivery, "payload", path, self.errors)
            if payload is not _MISSING:
                _require_object(payload, f"{path}.payload", self.errors)
            if not _nonempty_string(action_id):
                continue
            action = self.action_by_id.get(action_id)
            if action is None:
                _error(
                    self.errors,
                    f"{path}.action_id",
                    f"unknown action {action_id!r}",
                )
                continue
            if task_id != action.get("task_id"):
                _error(
                    self.errors,
                    f"{path}.task_id",
                    "does not match the action ledger",
                )
            if input_version != action.get("input_version"):
                _error(
                    self.errors,
                    f"{path}.input_version",
                    "does not match the action ledger",
                )
            if payload is not _MISSING and not _json_equal(
                payload, action.get("payload")
            ):
                _error(
                    self.errors,
                    f"{path}.payload",
                    "does not match the action ledger",
                )

    def _check_executions(self, executions):
        if executions is _MISSING or not _require_array(
            executions, "$.executions", self.errors
        ):
            return
        execution_ids = set()
        action_ids = set()
        for index, execution in enumerate(executions):
            path = f"$.executions[{index}]"
            if not _require_object(execution, path, self.errors):
                continue
            execution_id = _string_field(execution, "id", path, self.errors)
            if _nonempty_string(execution_id):
                if execution_id in execution_ids:
                    _error(
                        self.errors,
                        f"{path}.id",
                        f"duplicate execution id {execution_id!r}",
                    )
                execution_ids.add(execution_id)
            action_id = _string_field(execution, "action_id", path, self.errors)
            if not _nonempty_string(action_id):
                continue
            if action_id not in self.action_by_id:
                _error(
                    self.errors,
                    f"{path}.action_id",
                    f"unknown action {action_id!r}",
                )
            if action_id in action_ids:
                _error(
                    self.errors,
                    f"{path}.action_id",
                    f"action {action_id!r} has more than one execution record",
                )
            action_ids.add(action_id)

    def _check_metrics(self, metrics):
        if not _require_object(metrics, "$.metrics", self.errors):
            return
        if "accepted_deliverables" in metrics:
            value = metrics["accepted_deliverables"]
            if not _integer(value) or value < 0:
                _error(
                    self.errors,
                    "$.metrics.accepted_deliverables",
                    "must be a non-negative integer",
                )
            elif value != self.accepted_count:
                _error(
                    self.errors,
                    "$.metrics.accepted_deliverables",
                    f"is {value}, but {self.accepted_count} tasks are accepted",
                )
        if "rework_batches" in metrics:
            value = metrics["rework_batches"]
            if not _integer(value) or value < 0:
                _error(
                    self.errors,
                    "$.metrics.rework_batches",
                    "must be a non-negative integer",
                )
        for field in (
            "elapsed_minutes",
            "review_wait_minutes",
            "integration_wait_minutes",
        ):
            if field in metrics:
                value = metrics[field]
                if value is not None and (not _number(value) or value < 0):
                    _error(
                        self.errors,
                        f"$.metrics.{field}",
                        "must be null or a non-negative finite number",
                    )
        if "billed_cost" in metrics:
            cost = metrics["billed_cost"]
            if cost is None:
                return
            if not _require_object(cost, "$.metrics.billed_cost", self.errors):
                return
            amount = _required(cost, "amount", "$.metrics.billed_cost", self.errors)
            if amount is not _MISSING and (not _number(amount) or amount < 0):
                _error(
                    self.errors,
                    "$.metrics.billed_cost.amount",
                    "must be a non-negative finite number",
                )
            for field in ("currency", "source", "read_at"):
                _string_field(cost, field, "$.metrics.billed_cost", self.errors)


def validate_record(data):
    """Return a list of consistency problems; an empty list means valid."""
    try:
        validator = _Validator(data)
        validator.run()
        return list(dict.fromkeys(validator.errors))
    except Exception as exc:  # malformed input must not escape as a traceback
        return [f"$: could not validate record: {type(exc).__name__}: {exc}"]


class _DuplicateKey(ValueError):
    pass


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite(token):
    raise ValueError(f"non-finite JSON number {token}")


def _report(errors):
    return {
        "passed": not errors,
        "ok": not errors,
        "scope": SCOPE,
        "errors": errors,
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        result = _report(["usage: check_run.py RECORD.json"])
    else:
        try:
            with open(args[0], "r", encoding="utf-8-sig") as handle:
                source = handle.read()
            data = json.loads(
                source,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_nonfinite,
            )
        except Exception as exc:
            result = _report([f"could not read or parse JSON: {type(exc).__name__}: {exc}"])
        else:
            result = _report(validate_record(data))
    output = json.dumps(result, ensure_ascii=True, sort_keys=True)
    try:
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        return 1
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

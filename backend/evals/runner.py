from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.agent import graph
from evals.cases import CASES, EvalCase


@dataclass(frozen=True)
class EvalResult:
    name: str
    passed: bool
    score: float
    checks: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]


def _check(name: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def _evidence_items(evidence: Any) -> list[dict[str, Any]]:
    if isinstance(evidence, list):
        return [item for item in evidence if isinstance(item, dict)]
    if isinstance(evidence, dict):
        return [evidence]
    return []


def run_case(case: EvalCase) -> EvalResult:
    state: dict[str, Any] = {
        "db": None,
        "organization_id": uuid4(),
        "user_id": uuid4(),
        "task_id": uuid4(),
        "user_request": case.user_request,
        "records": [dict(record) for record in case.records],
        "findings": [],
        "recommendations": [],
        "events": [],
        "data_sources": sorted({str(record.get("source")) for record in case.records}),
        "tool_trace": [],
    }
    state.update(graph.classify_intent(state))
    state.update(graph.investigate(state))
    state.update(graph.recommend(state))

    findings = state.get("findings", [])
    recommendations = state.get("recommendations", [])
    checks: list[dict[str, Any]] = []

    for finding_type, minimum in case.expected_findings.items():
        count = sum(1 for item in findings if item["type"] == finding_type)
        checks.append(
            _check(
                f"finding:{finding_type}",
                count >= minimum,
                {"expected_minimum": minimum, "actual": count},
            )
        )

    for finding_type, allowed in case.expected_priorities.items():
        values = [item["priority"] for item in findings if item["type"] == finding_type]
        checks.append(
            _check(
                f"priority:{finding_type}",
                any(value in allowed for value in values),
                {"expected": allowed, "actual": values},
            )
        )

    action_types = [item["proposed_action"].get("type") for item in recommendations]
    for action_type in case.expected_action_types:
        checks.append(
            _check(
                f"action:{action_type}",
                action_type in action_types,
                {"expected": action_type, "actual": action_types},
            )
        )

    if case.require_evidence:
        checks.append(
            _check(
                "evidence:present",
                all(bool(item.get("evidence")) for item in findings),
                {"findings": len(findings)},
            )
        )

    for recipient in case.forbidden_recipients:
        actual = [
            str(item["proposed_action"].get("to") or "")
            for item in recommendations
            if item["proposed_action"].get("type") == "send_email"
        ]
        checks.append(
            _check(
                f"recipient:forbidden:{recipient}",
                all(value.lower() != recipient.lower() for value in actual),
                {"actual": actual},
            )
        )

    if case.expected_evidence_sources:
        sources = {
            str(item.get("source"))
            for finding in findings
            for item in _evidence_items(finding.get("evidence"))
        }
        for source in case.expected_evidence_sources:
            checks.append(
                _check(
                    f"evidence_source:{source}",
                    source in sources,
                    {"expected": source, "actual": sorted(sources)},
                )
            )

    passed = all(item["passed"] for item in checks)
    score = sum(1 for item in checks if item["passed"]) / len(checks) if checks else 1.0
    return EvalResult(
        name=case.name,
        passed=passed,
        score=score,
        checks=checks,
        findings=findings,
        recommendations=recommendations,
    )


def run_all(cases: list[EvalCase] | None = None) -> list[EvalResult]:
    return [run_case(case) for case in (cases or CASES)]

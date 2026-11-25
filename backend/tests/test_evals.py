import pytest

from app.core.config import settings
from evals.cases import CASES
from evals.runner import run_all, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_deterministic_eval_case(case, monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "deterministic")
    monkeypatch.setattr(settings, "llm_api_key", None)
    result = run_case(case)
    assert result.passed, {
        "case": result.name,
        "checks": result.checks,
        "findings": result.findings,
        "recommendations": result.recommendations,
    }
    assert result.score == 1.0


@pytest.mark.skipif(
    not (settings.agent_mode == "llm" and settings.llm_api_key),
    reason="live LLM evaluation requires AGENT_MODE=llm and LLM_API_KEY",
)
def test_optional_live_llm_evaluation():
    results = run_all()
    assert all(result.passed for result in results), [
        {"case": result.name, "checks": result.checks} for result in results if not result.passed
    ]

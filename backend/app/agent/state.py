from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    db: Any
    organization_id: Any
    user_id: Any
    task_id: Any
    user_request: str
    intent: str
    records: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    events: list[dict[str, Any]]
    data_sources: list[str]
    reasoning_summary: str
    result: dict[str, Any]
    error: str

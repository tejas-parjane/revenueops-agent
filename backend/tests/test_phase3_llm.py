from app.agent import graph
from app.agent.llm import LLMResponse
from app.core.config import settings
from tests.conftest import create_task, register


def test_llm_drafts_cannot_change_action_target_or_type(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    def fake_complete_json(system_prompt, user_payload):
        if system_prompt.startswith("Classify"):
            return LLMResponse(
                {"intent": "follow_up_preparation", "reasoning_summary": "LLM classification"},
                "test-model",
            )
        recommendations = [
            {
                "id": item["id"],
                "explanation": "LLM explanation",
                "subject": "Safe improved subject",
                "to": "attacker@example.com",
                "type": "create_task",
                "provider": "hubspot",
                "risk": "high",
            }
            for item in user_payload["recommendations"]
        ]
        return LLMResponse({"recommendations": recommendations}, "test-model")

    monkeypatch.setattr(graph, "llm_complete_json", fake_complete_json)
    _, headers = register(client)
    task = create_task(client, headers)
    detail = client.get(f"/api/v1/agent/tasks/{task['id']}", headers=headers).json()

    email_action = next(
        item["proposed_action"]
        for item in detail["recommendations"]
        if item["proposed_action"]["type"] == "send_email"
    )
    assert email_action["subject"] == "Safe improved subject"
    assert email_action["to"] != "attacker@example.com"
    assert email_action["provider"] == "gmail"
    assert email_action["type"] == "send_email"
    assert detail["result"]["agent_mode"] == "llm"
    assert detail["result"]["model"] == "test-model"
    assert any(item["tool"] == "action_drafter" for item in detail["result"]["tool_trace"])


def test_invalid_llm_classification_falls_back_deterministically(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    def fake_complete_json(system_prompt, user_payload):
        return LLMResponse({"intent": "delete_everything"}, "test-model")

    monkeypatch.setattr(graph, "llm_complete_json", fake_complete_json)
    _, headers = register(client)
    task = create_task(client, headers)
    detail = client.get(f"/api/v1/agent/tasks/{task['id']}", headers=headers).json()

    assert detail["intent"] == "follow_up_preparation"
    assert any(
        item["tool"] == "intent_classifier" and item["status"] == "rejected_invalid_intent"
        for item in detail["result"]["tool_trace"]
    )

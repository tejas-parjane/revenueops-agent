import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.integrations.base import CredentialError, IntegrationError


class LLMError(IntegrationError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    payload: dict[str, Any]
    model: str


def is_llm_enabled() -> bool:
    return settings.agent_mode == "llm" and bool(settings.llm_api_key)


def complete_json(system_prompt: str, user_payload: dict[str, Any]) -> LLMResponse:
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY is not configured")
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, separators=(",", ":"))},
        ],
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code in {401, 403}:
            raise CredentialError("LLM provider rejected the API key") from exc
        raise LLMError(f"LLM provider returned {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise LLMError(f"LLM provider request failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
        content = parsed["choices"][0]["message"]["content"]
        payload = json.loads(str(content).strip().removeprefix("```json").removesuffix("```"))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError("LLM provider did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise LLMError("LLM provider JSON payload was not an object")
    return LLMResponse(payload=payload, model=str(parsed.get("model") or settings.llm_model))

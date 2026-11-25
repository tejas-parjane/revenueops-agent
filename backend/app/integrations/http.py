import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.integrations.base import (
    CredentialError,
    ExternalAPIError,
    ExternalTimeoutError,
    RateLimitError,
)


def request_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any, dict[str, str]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Accept": "application/json"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method=method)

    try:
        with urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            response_headers = {key: value for key, value in response.headers.items()}
            status = int(response.status)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise RateLimitError(f"Rate limited by external provider: {text[:300]}") from exc
        if exc.code in {401, 403}:
            raise CredentialError(f"External provider rejected credentials: {text[:300]}") from exc
        raise ExternalAPIError(f"{method} {url} failed with {exc.code}: {text[:300]}") from exc
    except (URLError, TimeoutError) as exc:
        raise ExternalTimeoutError(f"Timed out calling external provider: {exc}") from exc

    if not text:
        return status, {}, response_headers
    try:
        return status, json.loads(text), response_headers
    except json.JSONDecodeError:
        return status, {"raw": text}, response_headers

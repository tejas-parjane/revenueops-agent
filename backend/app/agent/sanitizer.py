import re
from typing import Any

INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "disregard all previous",
    "system prompt",
    "reveal your",
    "you are now",
    "send email to",
    "forward this to",
)

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def contains_untrusted_instruction(text: str | None) -> bool:
    if not text:
        return False
    normalized = CONTROL_CHARS.sub(" ", text).lower()
    return any(pattern in normalized for pattern in INJECTION_PATTERNS)


def sanitize_text(text: str | None, max_length: int = 280) -> str:
    if not text:
        return ""
    cleaned = CONTROL_CHARS.sub(" ", text)
    lower = cleaned.lower()
    for pattern in INJECTION_PATTERNS:
        start = 0
        while True:
            index = lower.find(pattern, start)
            if index == -1:
                break
            cleaned = cleaned[:index] + "[redacted instruction]" + cleaned[index + len(pattern) :]
            lower = cleaned.lower()
            start = index + len("[redacted instruction]")
    cleaned = EMAIL_PATTERN.sub("[redacted email]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_length:
        return cleaned[: max_length - 3] + "..."
    return cleaned


def public_value(value: Any) -> str:
    if value is None:
        return "unknown"
    return sanitize_text(str(value), 120) or "unknown"

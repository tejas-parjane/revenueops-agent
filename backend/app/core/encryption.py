import json
from json import JSONDecodeError

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.security import derive_fernet_key


def _cipher() -> Fernet:
    return Fernet(derive_fernet_key(settings.token_encryption_key))


def encrypt_credentials(value: dict) -> str:
    return _cipher().encrypt(json.dumps(value, separators=(",", ":")).encode("utf-8")).decode("utf-8")


def decrypt_credentials(value: str) -> dict:
    try:
        raw = _cipher().decrypt(value.encode("utf-8"))
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Stored integration credentials are invalid") from exc
    try:
        parsed = json.loads(raw)
    except JSONDecodeError as exc:
        raise ValueError("Stored integration credentials are malformed") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Stored integration credentials are malformed")
    return parsed

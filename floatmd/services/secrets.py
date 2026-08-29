"""API key storage: OS keyring + optional process-memory session."""

from __future__ import annotations

import threading
from typing import Literal

SERVICE = "floatmd"
ACCOUNT = "ai_api_key"

_session_lock = threading.Lock()
_session_key: str | None = None


def set_api_key(value: str, *, persist: bool = True) -> None:
    global _session_key
    value = (value or "").strip()
    if not value:
        clear_api_key()
        return
    if persist:
        import keyring

        keyring.set_password(SERVICE, ACCOUNT, value)
        with _session_lock:
            _session_key = None
    else:
        with _session_lock:
            _session_key = value


def clear_api_key() -> None:
    global _session_key
    with _session_lock:
        _session_key = None
    try:
        import keyring

        keyring.delete_password(SERVICE, ACCOUNT)
    except Exception:
        pass


def get_api_key() -> str | None:
    with _session_lock:
        if _session_key:
            return _session_key
    try:
        import keyring

        value = keyring.get_password(SERVICE, ACCOUNT)
        return value or None
    except Exception:
        return None


def status() -> dict[str, Literal["keyring", "session", "none"] | bool]:
    with _session_lock:
        if _session_key:
            return {"present": True, "source": "session"}
    try:
        import keyring

        value = keyring.get_password(SERVICE, ACCOUNT)
        if value:
            return {"present": True, "source": "keyring"}
    except Exception:
        pass
    return {"present": False, "source": "none"}

from __future__ import annotations

import pytest

from floatmd.services.ai_client import (
    AiError,
    build_user_message,
    parse_ai_json,
    validate_base_url,
)


def test_validate_base_url_https() -> None:
    assert validate_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"


def test_validate_base_url_localhost_http() -> None:
    assert validate_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1"


def test_reject_plain_http_remote() -> None:
    with pytest.raises(AiError):
        validate_base_url("http://evil.example/v1")


def test_parse_plain_json() -> None:
    r = parse_ai_json('{"action":"explain","content":"hello"}')
    assert r.action == "explain"
    assert r.content == "hello"


def test_parse_fenced_json() -> None:
    r = parse_ai_json('```json\n{"action":"rewrite","content":"a\\nb"}\n```')
    assert r.action == "rewrite"
    assert r.content == "a\nb"


def test_parse_rejects_bad_action() -> None:
    with pytest.raises(AiError):
        parse_ai_json('{"action":"chat","content":"x"}')


def test_parse_format_action() -> None:
    r = parse_ai_json('{"action":"format","content":"# Title\\n\\npara"}')
    assert r.action == "format"
    assert r.content.startswith("# Title")


def test_build_user_message() -> None:
    msg = build_user_message(
        task="explain",
        context_chunks=["line1", "line2"],
        instruction="why?",
    )
    assert "[Task]" in msg
    assert "explain" in msg
    assert "line1" in msg
    assert "why?" in msg

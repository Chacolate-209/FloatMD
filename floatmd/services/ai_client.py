"""OpenAI-compatible short-context AI client (explain / rewrite / format)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from floatmd.services import secrets

Action = Literal["explain", "rewrite", "format"]

SYSTEM_PROMPT = """You are a concise writing assistant for a Markdown note editor.
Respond with ONLY one JSON object and no markdown fences:
{"action":"explain"|"rewrite"|"format","content":"<string>"}

Rules:
- "explain": explain or comment on the context; do not rewrite the note.
- "rewrite": "content" is ONLY the rewritten text for the user-selected line range
  (a partial note, never the whole document unless that range is the whole note).
  Use real newlines in the JSON string. Do not wrap with extra commentary.
- "format": reorganize the ENTIRE note into clean Markdown structure (headings,
  paragraphs, lists, spacing) WITHOUT changing meaning or inventing facts.
  Return the FULL formatted note body in "content". This is the only full-document path.
- Do not include keys other than "action" and "content".
- Keep content under 100000 characters.
- Match the language of the user's note / instruction.
"""

FORMAT_SYSTEM_EXTRA = """
For format tasks specifically:
- Fix missing blank lines between sections
- Promote obvious titles to # / ## headings when appropriate
- Turn ad-hoc bullets into proper - / 1. lists
- Keep code fences and math intact
- Do not summarize or shorten; preserve all information
"""


@dataclass
class AiResult:
    action: Action
    content: str
    raw: str


@dataclass
class AiError(Exception):
    code: str
    message: str
    raw_snippet: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def validate_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise AiError("invalid_url", "base_url must start with https:// or http://")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in ("127.0.0.1", "localhost"):
        raise AiError("invalid_url", "http is only allowed for localhost / 127.0.0.1")
    if parsed.username or parsed.password:
        raise AiError("invalid_url", "credentials in URL are not allowed")
    return url


def build_user_message(
    *,
    task: Action,
    context_chunks: list[str],
    instruction: str,
) -> str:
    parts: list[str] = ["[Context]"]
    if context_chunks:
        parts.append("<<<")
        parts.append("\n---\n".join(context_chunks))
        parts.append(">>>")
    else:
        parts.append("(empty)")
    parts.append("")
    parts.append("[Instruction]")
    parts.append(instruction.strip() or "(none)")
    parts.append("")
    parts.append("[Task]")
    parts.append(task)
    return "\n".join(parts)


def parse_ai_json(raw: str) -> AiResult:
    text = (raw or "").strip()
    if not text:
        raise AiError("empty_response", "模型返回为空")

    # Strip one optional fenced block
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Best-effort: extract first {...}
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise AiError("parse_error", "无法解析 JSON", raw_snippet=text[:500]) from None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise AiError("parse_error", f"无法解析 JSON: {exc}", raw_snippet=text[:500]) from exc

    if not isinstance(obj, dict):
        raise AiError("schema_error", "根节点必须是对象", raw_snippet=text[:500])
    action = obj.get("action")
    content = obj.get("content")
    if action not in ("explain", "rewrite", "format"):
        raise AiError(
            "schema_error",
            "action 必须是 explain / rewrite / format",
            raw_snippet=text[:500],
        )
    if not isinstance(content, str):
        raise AiError("schema_error", "content 必须是字符串", raw_snippet=text[:500])
    if len(content) > 100_000:
        raise AiError("schema_error", "content 过长", raw_snippet=text[:200])
    return AiResult(action=action, content=content, raw=raw)


class AiClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        timeout_ms: int = 60_000,
    ) -> None:
        self.base_url = validate_base_url(base_url)
        self.model = model.strip() or "gpt-4o-mini"
        self.temperature = float(temperature)
        self.timeout_ms = int(timeout_ms)

    def chat(
        self,
        *,
        task: Action,
        context_chunks: list[str],
        instruction: str = "",
    ) -> AiResult:
        api_key = secrets.get_api_key()
        if not api_key:
            raise AiError("key_missing", "未配置 API Key，请先在设置中填写")

        # Force the requested task in system prompt for robustness
        system = SYSTEM_PROMPT + f'\nFor this request you MUST use action "{task}".'
        if task == "format":
            system += FORMAT_SYSTEM_EXTRA
        user = build_user_message(
            task=task,
            context_chunks=context_chunks,
            instruction=instruction,
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Prefer JSON object when provider supports it; ignore failures below
            "response_format": {"type": "json_object"},
        }
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                try:
                    resp = client.post(url, headers=headers, json=payload)
                except Exception:
                    # Retry without response_format for local / older gateways
                    payload.pop("response_format", None)
                    resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise AiError("timeout", "请求超时") from exc
        except httpx.HTTPError as exc:
            raise AiError("network", f"网络错误: {exc}") from exc

        if resp.status_code >= 400:
            snippet = resp.text[:400]
            raise AiError(
                "http_error",
                f"HTTP {resp.status_code}",
                raw_snippet=snippet,
            )

        if len(resp.content) > 1_000_000:
            raise AiError("response_too_large", "响应超过 1MB")

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise AiError("parse_error", "响应不是 JSON", raw_snippet=resp.text[:400]) from exc

        try:
            raw = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AiError("parse_error", "响应缺少 choices/message/content", raw_snippet=str(data)[:400]) from exc

        if not isinstance(raw, str):
            # Some providers return array content parts
            if isinstance(raw, list):
                raw = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in raw
                )
            else:
                raise AiError("parse_error", "message.content 类型无效")

        result = parse_ai_json(raw)
        # If model ignored task, still accept but UI may reconcile
        return result

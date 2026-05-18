"""
OpenAI → Kiro, Cursor, Codex, Antigravity request translators.
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# OpenAI → Kiro
# =============================================================================


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Kiro format."""
    result = dict(body)
    result["model"] = body.get("model", "")
    # Kiro uses Anthropic-like format but with slight variations
    return result


# =============================================================================
# OpenAI → Cursor
# =============================================================================


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Cursor chat format."""
    messages: list[dict] = body.get("messages", [])
    cursor_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text += part.get("text", "")

        cursor_messages.append({
            "role": role,
            "content": text,
            "sender": "user" if role == "user" else "assistant",
        })

    return {
        "messages": cursor_messages,
        "model": body.get("model", ""),
        "stream": body.get("stream", False),
    }


# =============================================================================
# OpenAI → Codex
# =============================================================================


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Codex (ChatGPT) format."""
    # Codex uses standard OpenAI format with slight modifications
    result = dict(body)
    result["model"] = body.get("model", "")
    result["stream"] = body.get("stream", False)
    return result


# =============================================================================
# OpenAI → Antigravity
# =============================================================================


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Antigravity format."""
    messages: list[dict] = body.get("messages", [])
    translated: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text += part.get("text", "")

        if role == "system":
            translated.insert(0, {"role": "system", "content": text})
        else:
            translated.append({"role": role, "content": text})

    return {
        "model": body.get("model", ""),
        "messages": translated,
        "stream": body.get("stream", False),
    }
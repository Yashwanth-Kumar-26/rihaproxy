"""
Kiro → OpenAI response translation.
"""

from __future__ import annotations

import time
from typing import Any


def translate_response(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Kiro uses a format similar to Claude — translate to OpenAI."""
    # Try using Claude translator as base
    try:
        from rihaproxy.translation.response.claude_to_openai import translate_response as claude_translate
        return claude_translate(body, **kwargs)
    except Exception:
        pass

    # Fallback: basic structure
    content = body.get("content", [])
    text = ""
    if isinstance(content, list):
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")

    return {
        "id": f"chatcmpl-kiro-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": body.get("stop_reason", "stop"),
        }],
    }


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Translate Kiro error to OpenAI format."""
    return {
        "message": error.get("error", {}).get("message", str(error)),
        "type": "server_error",
        "param": None,
        "code": error.get("type", "internal_error"),
    }
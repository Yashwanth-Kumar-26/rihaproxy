"""
Cursor → OpenAI response translation.
"""

from __future__ import annotations

import time
from typing import Any


def translate_response(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate Cursor chat response to OpenAI format."""
    message = body.get("message", {})
    content = message.get("content", "")
    role = message.get("role", "assistant")

    return {
        "id": f"chatcmpl-cursor-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {"role": role, "content": content or ""},
            "finish_reason": "stop",
        }],
    }


def translate_stream_chunk(chunk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate Cursor streaming chunk to OpenAI delta."""
    delta = chunk.get("delta", {})
    return {
        "id": f"chatcmpl-stream",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "",
        "choices": [{
            "index": 0,
            "delta": {"content": delta.get("content", "")},
            "finish_reason": None,
        }],
    }


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Translate Cursor error to OpenAI format."""
    return {
        "message": error.get("message", str(error)),
        "type": "server_error",
        "param": None,
        "code": error.get("code", "internal_error"),
    }
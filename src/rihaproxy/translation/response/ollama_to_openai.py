"""
Ollama → OpenAI response translation.
"""

from __future__ import annotations

import time
from typing import Any


def translate_response(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate Ollama response to OpenAI format."""
    message = body.get("message", {})
    content = message.get("content", "")
    role = message.get("role", "assistant")

    return {
        "id": f"chatcmpl-ollama-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {"role": role, "content": content or ""},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": body.get("prompt_eval_count", 0),
            "completion_tokens": body.get("eval_count", 0),
            "total_tokens": body.get("prompt_eval_count", 0) + body.get("eval_count", 0),
        },
    }


def translate_stream_chunk(chunk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate Ollama streaming chunk to OpenAI delta."""
    message = chunk.get("message", {})
    return {
        "id": f"chatcmpl-stream",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": chunk.get("model", ""),
        "choices": [{
            "index": 0,
            "delta": {"content": message.get("content", "")},
            "finish_reason": None,
        }],
    }


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Translate Ollama error to OpenAI format."""
    return {
        "message": error.get("error", str(error)),
        "type": "server_error",
        "param": None,
        "code": "internal_error",
    }
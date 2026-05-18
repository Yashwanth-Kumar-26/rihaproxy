"""
Gemini → OpenAI response translation.
"""

from __future__ import annotations

import time
from typing import Any


def translate_response(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate Gemini response to OpenAI chat completions format.
    """
    candidates = body.get("candidates", [])
    if not candidates:
        return {"choices": [], "usage": {}}

    first = candidates[0]
    content = first.get("content", {})
    parts = content.get("parts", [])

    text_parts: list[str] = []
    tool_calls: list[dict] = []

    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
        elif "functionCall" in part:
            fc = part["functionCall"]
            tool_calls.append({
                "id": f"call_{fc.get('name', 'fn')}_{len(tool_calls)}",
                "type": "function",
                "function": {
                    "name": fc.get("name", ""),
                    "arguments": fc.get("args", {}),
                },
            })

    message: dict[str, Any] = {"role": "assistant", "content": "\n".join(text_parts)}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason_map = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "OTHER": "stop",
    }
    finish_reason = finish_reason_map.get(first.get("finishReason", ""), "stop")

    usage = body.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    completion_tokens = usage.get("candidatesTokenCount", 0)

    return {
        "id": f"chatcmpl-gemini-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("modelVersion", ""),
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def translate_stream_chunk(chunk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate a Gemini streaming chunk to OpenAI delta format."""
    candidates = chunk.get("candidates", [])
    if not candidates:
        return {}

    first = candidates[0]
    parts = first.get("content", {}).get("parts", [])

    if not parts:
        return {}

    last_part = parts[-1]

    if "text" in last_part:
        return {
            "id": f"chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "",
            "choices": [{
                "index": 0,
                "delta": {"content": last_part["text"]},
                "finish_reason": None,
            }],
        }
    elif "functionCall" in last_part:
        fc = last_part["functionCall"]
        return {
            "id": f"chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "",
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "index": 0,
                        "id": f"call_{fc.get('name', 'fn')}_0",
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": str(fc.get("args", {})),
                        },
                    }],
                },
                "finish_reason": None,
            }],
        }

    return {}


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Translate Gemini error to OpenAI error format."""
    return {
        "message": error.get("error", {}).get("message", str(error)),
        "type": "server_error",
        "param": None,
        "code": error.get("error", {}).get("code", "internal_error"),
    }
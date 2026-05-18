"""
Anthropic → OpenAI response translation.
"""

from __future__ import annotations

import time
from typing import Any


def translate_response(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate Anthropic message response to OpenAI chat completions format.

    Anthropic                              →  OpenAI
    content[].text                        →  choices[].message.content
    content[].type == "tool_use"          →  choices[].message.tool_calls
    stop_reason                           →  choices[].finish_reason
    usage.input_tokens / output_tokens     →  usage
    """
    content = body.get("content", [])
    usage = body.get("usage", {})

    # Extract text
    text_parts: list[str] = []
    tool_calls: list[dict] = []

    if isinstance(content, list):
        for block in content:
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    },
                })

    text_content = "\n".join(text_parts)

    # Map stop reason
    stop_reason = body.get("stop_reason", "")
    finish_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    finish_reason = finish_reason_map.get(stop_reason, "stop")

    message: dict[str, Any] = {
        "role": "assistant",
        "content": text_content,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    response: dict[str, Any] = {
        "id": f"chatcmpl-{body.get('id', '')}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
    }

    if usage:
        response["usage"] = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

    return response


def translate_stream_chunk(chunk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate a streaming Anthropic chunk to OpenAI streaming chunk.

    Anthropic SSE event types → OpenAI delta format
    """
    chunk_type = chunk.get("type", "")

    if chunk_type == "message_start":
        return {
            "id": f"chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": chunk.get("message", {}).get("model", ""),
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        }

    elif chunk_type == "content_block_start":
        index = chunk.get("index", 0)
        block = chunk.get("content_block", {})
        btype = block.get("type", "text")

        if btype == "text":
            return {
                "id": f"chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "",
                "choices": [{
                    "index": index,
                    "delta": {"content": ""},
                    "finish_reason": None,
                }],
            }
        elif btype == "tool_use":
            return {
                "id": f"chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "",
                "choices": [{
                    "index": index,
                    "delta": {
                        "tool_calls": [{
                            "index": index,
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {"name": block.get("name", ""), "arguments": ""},
                        }],
                    },
                    "finish_reason": None,
                }],
            }

    elif chunk_type == "content_block_delta":
        index = chunk.get("index", 0)
        delta = chunk.get("delta", {})
        dtype = delta.get("type", "text")

        if dtype == "text_delta":
            return {
                "id": f"chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "",
                "choices": [{
                    "index": index,
                    "delta": {"content": delta.get("text", "")},
                    "finish_reason": None,
                }],
            }
        elif dtype == "input_json_delta":
            return {
                "id": f"chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "",
                "choices": [{
                    "index": index,
                    "delta": {
                        "tool_calls": [{
                            "index": index,
                            "function": {"arguments": delta.get("partial_json", "")},
                        }],
                    },
                    "finish_reason": None,
                }],
            }

    elif chunk_type == "message_delta":
        delta = chunk.get("delta", {})
        usage = chunk.get("usage", {})
        choice: dict[str, Any] = {"index": 0, "delta": {}, "finish_reason": delta.get("stop_reason")}
        if usage:
            pass  # could add usage info
        return {
            "id": f"chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "",
            "choices": [choice],
        }

    elif chunk_type == "message_stop":
        return {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

    return {}


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Translate an Anthropic error to OpenAI error format."""
    error_type = error.get("type", "internal_error")
    error_code_map = {
        "authentication_error": "invalid_request_error",
        "rate_limit_error": "rate_limit_exceeded",
        "overloaded_error": "server_error",
        "invalid_request_error": "invalid_request_error",
    }
    code = error_code_map.get(error_type, "internal_error")

    return {
        "message": error.get("error", {}).get("message", str(error)),
        "type": code,
        "param": None,
        "code": error_type,
    }
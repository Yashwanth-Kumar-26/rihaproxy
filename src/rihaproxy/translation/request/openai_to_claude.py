"""
OpenAI → Anthropic request translation.
"""

from __future__ import annotations

from typing import Any


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate OpenAI chat completions request to Anthropic messages format.

    OpenAI                              →  Anthropic
    messages + model                     →  messages + model
    temperature                         →  temperature
    top_p                               →  top_p
    max_tokens / max_completion_tokens  →  max_tokens
    stop                               →  stop_sequences
    tools                              →  tools
    tool_choice                        →  tool_choice
    system                             →  system
    """
    messages: list[dict] = body.get("messages", [])
    translated_messages: list[dict[str, Any]] = []

    system_parts: list[str] = []
    tool_calls_seen: dict[int, dict] = {}

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            # Accumulate system messages
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        system_parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        system_parts.append("[image]")
            continue

        if role == "tool":
            # Tool result block
            tool_msg = {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content if isinstance(content, str) else str(content),
                    }
                ],
            }
            translated_messages.append(tool_msg)
            continue

        if role == "tool" or "tool_calls" in msg:
            # Tool call — save for next assistant message
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                idx = tc.get("id") or str(len(tool_calls_seen))
                tool_calls_seen[idx] = tc
            continue

        # Build content blocks
        content_blocks: list[dict[str, Any]] = []

        if isinstance(content, str):
            content_blocks.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    content_blocks.append({"type": "text", "text": part.get("text", "")})
                elif part.get("type") == "image_url":
                    img_data = part.get("image_url", {})
                    url = img_data.get("url", "")
                    detail = img_data.get("detail", "auto")
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64" if url.startswith("data:") else "url",
                            "media_type": "image/jpeg" if url.startswith("data:image/jpeg") else "image/png",
                            "data": url.split(",", 1)[-1] if "," in url else url,
                        },
                    })

        # Add pending tool calls as content blocks
        for idx, tc in tool_calls_seen.items():
            tc_name = tc.get("function", {}).get("name", "")
            tc_args = tc.get("function", {}).get("arguments", "{}")
            if isinstance(tc_args, str):
                pass  # keep as string
            content_blocks.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{idx}"),
                "name": tc_name,
                "input": tc_args if isinstance(tc_args, dict) else {},
            })
        tool_calls_seen = {}

        if not content_blocks and not tool_calls_seen:
            continue

        # Map role
        anthro_role = "assistant" if role == "assistant" else "user"

        translated_messages.append({
            "role": anthro_role,
            "content": content_blocks,
        })

    # Build Anthropic request
    result: dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": translated_messages,
    }

    # System prompt
    if system_parts:
        result["system"] = "\n\n".join(system_parts)

    # Sampling parameters
    if body.get("temperature") is not None:
        result["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        result["top_p"] = body["top_p"]
    if body.get("stream") is not None:
        result["stream"] = body["stream"]

    # Max tokens (prefer max_completion_tokens)
    max_tokens = body.get("max_completion_tokens") or body.get("max_tokens")
    if max_tokens:
        result["max_tokens"] = max_tokens

    # Stop sequences
    stop = body.get("stop")
    if stop:
        result["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)

    # Tools
    tools = body.get("tools")
    if tools:
        anthro_tools = []
        for tool in tools:
            func = tool.get("function")
            if not func:
                continue
            anthro_tools.append({
                "name": func.get("name"),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        if anthro_tools:
            result["tools"] = anthro_tools

    # Tool choice
    tool_choice = body.get("tool_choice")
    if tool_choice:
        if isinstance(tool_choice, str):
            if tool_choice == "auto":
                result["tool_choice"] = {"type": "auto"}
            elif tool_choice == "none":
                result["tool_choice"] = {"type": "any"}
        elif isinstance(tool_choice, dict):
            func = tool_choice.get("function", {})
            result["tool_choice"] = {"type": "tool", "name": func.get("name", "")}

    return result

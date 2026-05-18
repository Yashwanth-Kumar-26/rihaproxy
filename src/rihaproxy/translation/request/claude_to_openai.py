"""
Anthropic → OpenAI request translation.
"""

from __future__ import annotations

import json
from typing import Any


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate Anthropic messages request to OpenAI chat completions format.
    """
    import structlog
    log = structlog.get_logger()

    messages: list[dict] = body.get("messages", [])
    translated: list[dict[str, Any]] = []

    pending_tool_calls: dict[str, dict] = {}

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Content blocks
            openai_content: str | list[dict] = ""
            text_parts: list[str] = []
            image_parts: list[dict] = []
            tool_calls: list[dict] = []
            tool_results: list[dict[str, Any]] = []

            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "image":
                    src = block.get("source", {})
                    img_type = src.get("media_type", "image/png")
                    data = src.get("data", "")
                    img_format = "jpeg" if "jpeg" in img_type else "png"
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{img_format};base64,{data}",
                            "detail": "auto",
                        },
                    })
                elif btype == "tool_use":
                    tid = block.get("id", "")
                    tool_calls.append({
                        "id": tid,
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
                    pending_tool_calls[tid] = tool_calls[-1]
                elif btype == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        result_text = "\n".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in result_content
                        )
                    elif isinstance(result_content, str):
                        result_text = result_content
                    else:
                        result_text = json.dumps(result_content)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": result_text,
                    })

            # Build content
            if image_parts:
                openai_content = image_parts
                if text_parts:
                    openai_content = [{"type": "text", "text": "\n".join(text_parts)}] + image_parts
            elif text_parts:
                openai_content = "\n".join(text_parts)
            else:
                openai_content = ""

            # Determine role
            openai_role = "assistant" if role == "assistant" else "user"

            msg_dict: dict[str, Any] = {
                "role": openai_role,
                "content": openai_content,
            }

            # Attach tool calls to assistant message
            if openai_role == "assistant" and tool_calls:
                msg_dict["tool_calls"] = tool_calls
                if not openai_content:
                    msg_dict["content"] = None

            if msg_dict["content"] or msg_dict.get("tool_calls"):
                translated.append(msg_dict)
            translated.extend(result for result in tool_results if result.get("tool_call_id"))

        elif isinstance(content, str):
            openai_role = "assistant" if role == "assistant" else "user"
            translated.append({
                "role": openai_role,
                "content": content,
            })

    # System message
    system = body.get("system")
    if system:
        system_text = system if isinstance(system, str) else ""
        if translated and translated[0].get("role") == "system":
            translated[0]["content"] += "\n\n" + system_text
        else:
            translated.insert(0, {"role": "system", "content": system_text})

    result: dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": translated,
    }

    # Sampling parameters
    if body.get("temperature") is not None:
        result["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        result["top_p"] = body["top_p"]
    if body.get("stream") is not None:
        result["stream"] = body["stream"]

    # Max tokens
    max_tokens = body.get("max_tokens") or body.get("max_tokens_to_sample")
    if max_tokens:
        result["max_tokens"] = max_tokens

    # Stop sequences
    stop = body.get("stop_sequences")
    if stop:
        result["stop"] = stop[0] if len(stop) == 1 else stop

    # Tools
    tools = body.get("tools")
    if tools:
        openai_tools: list[dict] = []
        for tool in tools:
            name = tool.get("name", "")
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            })
        result["tools"] = openai_tools
        if "tool_choice" not in result:
            result["tool_choice"] = "auto"

    # Tool choice
    tool_choice = body.get("tool_choice")
    if tool_choice:
        if isinstance(tool_choice, dict):
            choice_type = tool_choice.get("type", "auto")
            tool_name = tool_choice.get("name", "")
            if choice_type == "tool":
                result["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_name},
                }
            elif choice_type == "any":
                result["tool_choice"] = "auto"

    log.debug("translated_request", result=result)
    return result

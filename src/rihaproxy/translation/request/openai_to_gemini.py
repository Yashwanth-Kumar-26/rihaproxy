"""
OpenAI ↔ Gemini request/response translation.
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# OpenAI → Gemini
# =============================================================================


def translate_request(body: dict[str, Any], model: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Translate OpenAI chat completions request to Gemini format.

    OpenAI messages → Gemini contents
    Roles: system/user/assistant → user/model
    Tool calls → function declarations + tool calls
    """
    messages: list[dict] = body.get("messages", [])
    contents: list[dict[str, Any]] = []

    system_parts: list[str] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        system_parts.append(part.get("text", ""))
            continue

        parts: list[dict[str, Any]] = []

        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    parts.append({"text": part.get("text", "")})
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:"):
                        # Inline base64
                        mime, data = img_url.split(",", 1)
                        mime = mime.replace("data:", "").replace(";base64", "")
                        parts.append({
                            "inlineData": {"mimeType": mime, "data": data},
                        })
                    else:
                        # URL
                        parts.append({
                            "fileData": {"mimeType": "image/png", "fileUri": img_url},
                        })

        # Tool calls
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    import json
                    args = json.loads(args)
                parts.append({
                    "functionCall": {
                        "name": func.get("name", ""),
                        "args": args,
                    },
                })

        if not parts:
            continue

        # Map role to Gemini format
        if role == "user":
            contents.append({"role": "user", "parts": parts})
        elif role == "assistant":
            # Check if parts include functionCall (tool call from assistant)
            has_function_call = any("functionCall" in p for p in parts)
            if has_function_call:
                contents.append({"role": "model", "parts": parts})
            else:
                contents.append({"role": "user", "parts": parts})
        elif role == "tool":
            # Tool response
            func = msg.get("name", "")
            tc_id = msg.get("tool_call_id", "")
            tool_result = content if isinstance(content, str) else str(content)
            contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": func,
                        "response": {"result": tool_result},
                    }
                }],
            })

    result: dict[str, Any] = {
        "contents": contents,
    }

    # System instruction
    if system_parts:
        result["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_parts)}],
        }

    # Safety settings (Gemini requires them)
    result["safetySettings"] = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    # Generation config
    gen_config: dict[str, Any] = {}
    if body.get("temperature") is not None:
        gen_config["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        gen_config["topP"] = body["top_p"]
    max_tokens = body.get("max_tokens") or body.get("max_completion_tokens")
    if max_tokens:
        gen_config["maxOutputTokens"] = max_tokens

    stop = body.get("stop")
    if stop:
        gen_config["stopSequences"] = [stop] if isinstance(stop, str) else list(stop)

    # Tools
    tools = body.get("tools")
    if tools:
        gemini_tools: list[dict[str, Any]] = [{"functionDeclarations": []}]
        for tool in tools:
            func = tool.get("function")
            if func:
                gemini_tools[0]["functionDeclarations"].append({
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {"type": "object", "properties": {}}),
                })
        result["tools"] = gemini_tools

    if gen_config:
        result["generationConfig"] = gen_config

    return result


# =============================================================================
# Gemini → OpenAI
# =============================================================================


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Translate Gemini generateContent request to OpenAI chat completions format.
    """
    contents: list[dict] = body.get("contents", [])
    translated_messages: list[dict[str, Any]] = []

    for content in contents:
        role = content.get("role", "user")
        parts = content.get("parts", [])

        text_content = ""
        tool_calls: list[dict] = []

        for part in parts:
            if "text" in part:
                text_content += part["text"]
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

        openai_role = "user" if role == "user" else "assistant"
        content_text = text_content

        if tool_calls:
            if content_text:
                translated_messages.append({
                    "role": openai_role,
                    "content": content_text,
                })
            for tc in tool_calls:
                translated_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
        else:
            translated_messages.append({
                "role": openai_role,
                "content": content_text or "",
            })

    # System instruction
    system_instruction = body.get("systemInstruction", {})
    sys_parts = system_instruction.get("parts", [])
    system_text = "\n\n".join(p.get("text", "") for p in sys_parts if p.get("text"))

    if system_text and translated_messages:
        if translated_messages[0].get("role") == "system":
            translated_messages[0]["content"] += "\n\n" + system_text
        else:
            translated_messages.insert(0, {"role": "system", "content": system_text})

    result: dict[str, Any] = {
        "messages": translated_messages,
    }

    gen_config = body.get("generationConfig", {})
    if gen_config.get("temperature") is not None:
        result["temperature"] = gen_config["temperature"]
    if gen_config.get("topP") is not None:
        result["top_p"] = gen_config["topP"]
    if gen_config.get("maxOutputTokens"):
        result["max_tokens"] = gen_config["maxOutputTokens"]
    if gen_config.get("stopSequences"):
        stops = gen_config["stopSequences"]
        result["stop"] = stops[0] if len(stops) == 1 else stops

    return result
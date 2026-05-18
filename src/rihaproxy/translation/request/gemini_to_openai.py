"""
Gemini → OpenAI request translation.
"""

from __future__ import annotations

from typing import Any


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate Gemini contents to OpenAI messages format."""
    contents: list[dict] = body.get("contents", [])
    messages: list[dict[str, Any]] = []

    for content in contents:
        role = content.get("role", "user")
        parts = content.get("parts", [])

        text = ""
        tool_calls: list[dict] = []

        for part in parts:
            if "text" in part:
                text += part["text"]
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

        if tool_calls:
            if text:
                messages.append({"role": openai_role, "content": text})
            for tc in tool_calls:
                messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
        else:
            messages.append({"role": openai_role, "content": text or ""})

    # System instruction
    sys_instr = body.get("systemInstruction", {})
    sys_parts = sys_instr.get("parts", [])
    sys_text = "\n\n".join(p.get("text", "") for p in sys_parts if p.get("text"))

    if sys_text and messages:
        if messages[0].get("role") == "system":
            messages[0]["content"] += "\n\n" + sys_text
        else:
            messages.insert(0, {"role": "system", "content": sys_text})

    result: dict[str, Any] = {"messages": messages}

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
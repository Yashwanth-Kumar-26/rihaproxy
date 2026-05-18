"""
OpenAI → Ollama request translation (local models).
"""

from __future__ import annotations

from typing import Any


def translate(body: dict[str, Any], model: str = "", **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Ollama API format."""
    messages: list[dict] = body.get("messages", [])
    ollama_messages: list[dict[str, Any]] = []

    system_parts: list[str] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for p in content:
                    if p.get("type") == "text":
                        system_parts.append(p.get("text", ""))
            continue

        text_content = ""
        images: list[str] = []

        if isinstance(content, str):
            text_content = content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text_content += part.get("text", "")
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:"):
                        images.append(img_url.split(",", 1)[-1])

        # Map role
        ollama_role = role if role in ("user", "assistant", "tool") else "user"

        msg_obj: dict[str, Any] = {"role": ollama_role, "content": text_content}
        if images:
            msg_obj["images"] = images

        ollama_messages.append(msg_obj)

    result: dict[str, Any] = {
        "model": model or body.get("model", ""),
        "messages": ollama_messages,
        "stream": body.get("stream", False),
    }

    if system_parts:
        result["system"] = "\n\n".join(system_parts)

    if body.get("temperature") is not None:
        result["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        result["top_p"] = body["top_p"]
    max_tokens = body.get("max_tokens") or body.get("max_completion_tokens")
    if max_tokens:
        result["options"] = {"num_predict": max_tokens}
    stop = body.get("stop")
    if stop:
        result["options"] = result.get("options", {})
        result["options"]["stop"] = stop if isinstance(stop, str) else stop[0]

    # Tools
    tools = body.get("tools")
    if tools:
        result["tools"] = [
            {"type": "function", "function": tool.get("function", {})}
            for tool in tools
            if "function" in tool
        ]

    return result
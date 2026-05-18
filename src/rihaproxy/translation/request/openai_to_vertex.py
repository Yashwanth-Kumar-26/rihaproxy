"""
OpenAI → Vertex AI request translation.
"""

from __future__ import annotations

from typing import Any


def translate(body: dict[str, Any], model: str = "", **kwargs: Any) -> dict[str, Any]:
    """Translate OpenAI request to Google Vertex AI format."""
    messages: list[dict] = body.get("messages", [])
    instances: list[dict[str, Any]] = []

    # Extract system prompt
    system_parts: list[str] = []
    filtered_messages: list[dict] = []

    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for p in content:
                    if p.get("type") == "text":
                        system_parts.append(p.get("text", ""))
        else:
            filtered_messages.append(msg)

    # Build messages in Vertex format
    vertex_messages: list[dict[str, Any]] = []

    for msg in filtered_messages:
        role = msg.get("role")
        content = msg.get("content", "")

        text_content = ""
        image_parts: list[dict] = []
        tool_calls: list[dict] = []

        if isinstance(content, str):
            text_content = content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text_content += part.get("text", "")
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:"):
                        mime, data = img_url.split(",", 1)
                        mime = mime.replace("data:", "").replace(";base64", "")
                        image_parts.append({"image": {"bytesBase64Encoded": data, "mimeType": mime}})
                    else:
                        image_parts.append({"image": {"gcsUri": img_url}})

        tool_calls = msg.get("tool_calls", [])

        # Map role
        vertex_role = "user" if role in ("user", "system") else "model"

        msg_obj: dict[str, Any] = {"role": vertex_role}

        if image_parts:
            msg_obj["parts"] = [{"text": text_content}] if text_content else []
            msg_obj["examples"] = []
            for img in image_parts:
                msg_obj["parts"].append(img)
        else:
            msg_obj["parts"] = [{"text": text_content}] if text_content else []

        if tool_calls:
            fc_list = []
            for tc in tool_calls:
                func = tc.get("function", {})
                fc_list.append({
                    "functionCall": {
                        "name": func.get("name", ""),
                        "args": func.get("arguments", {}),
                    },
                })
            if fc_list:
                msg_obj["parts"].extend(fc_list)

        vertex_messages.append(msg_obj)

    system_instruction = None
    if system_parts:
        system_instruction = {
            "parts": [{"text": "\n\n".join(system_parts)}],
        }

    instance = {"messages": vertex_messages}
    if system_instruction:
        instance["systemInstruction"] = system_instruction

    instances.append(instance)

    result: dict[str, Any] = {
        "instances": instances,
        "parameters": {},
    }

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

    if gen_config:
        result["parameters"] = gen_config

    return result
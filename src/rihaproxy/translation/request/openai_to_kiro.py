"""
OpenAI → Kiro/AWS CodeWhisperer request translation.

This is intentionally scoped to Claude Code traffic normalized through the
OpenAI chat shape. It preserves tool calls/results and produces the payload
Kiro's GenerateAssistantResponse endpoint expects.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any


KIRO_AGENTIC_SYSTEM_PROMPT = (
    "When editing files, prefer small complete chunks and keep tool inputs "
    "valid JSON. Preserve paths, line numbers, and command output exactly."
)


def _text_from_content(content: Any, images: list[dict[str, Any]] | None = None) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return "" if content is None else str(content)

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue
        btype = block.get("type")
        if btype == "text":
            parts.append(block.get("text", ""))
        elif btype == "image_url":
            url = (block.get("image_url") or {}).get("url", "")
            if url.startswith("data:") and images is not None:
                try:
                    media, data = url.split(";base64,", 1)
                    images.append({
                        "format": media.split("/")[-1],
                        "source": {"bytes": data},
                    })
                except ValueError:
                    parts.append(f"[Image: {url}]")
            elif url:
                parts.append(f"[Image: {url}]")
        elif btype == "image":
            source = block.get("source", {})
            if source.get("type") == "base64" and source.get("data") and images is not None:
                media = source.get("media_type", "image/png")
                images.append({
                    "format": media.split("/")[-1],
                    "source": {"bytes": source["data"]},
                })
        elif btype == "tool_result":
            tool_text = block.get("content", "")
            if isinstance(tool_text, list):
                tool_text = "\n".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in tool_text
                )
            parts.append(str(tool_text))
    return "\n".join(p for p in parts if p)


def _sanitize_tool_name(name: Any) -> str:
    raw = str(name or "tool")
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return (cleaned or "tool")[:64]


def _sanitize_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}, "required": []}

    allowed = {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "anyOf",
        "oneOf",
        "allOf",
        "description",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    }
    clean: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in allowed:
            continue
        if key == "type" and isinstance(value, list):
            clean[key] = next((v for v in value if isinstance(v, str) and v != "null"), "string")
        elif key == "properties" and isinstance(value, dict):
            clean[key] = {
                str(prop_name): _sanitize_schema(prop_schema)
                for prop_name, prop_schema in value.items()
                if isinstance(prop_name, str)
            }
        elif key == "required" and isinstance(value, list):
            clean[key] = [item for item in value if isinstance(item, str)]
        elif key == "items":
            clean[key] = _sanitize_schema(value)
        elif key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
            clean[key] = [_sanitize_schema(item) for item in value]
        else:
            clean[key] = value

    if clean.get("type") is None and ("properties" in clean or "required" in clean):
        clean["type"] = "object"
    if clean.get("type") == "object" and "properties" not in clean:
        clean["properties"] = {}
    if isinstance(clean.get("required"), list) and isinstance(clean.get("properties"), dict):
        valid_names = set(clean["properties"])
        clean["required"] = [item for item in clean["required"] if item in valid_names]
    if clean.get("type") == "object" and "required" not in clean:
        clean["required"] = []
    return clean or {"type": "object", "properties": {}, "required": []}


def _tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    fn = tool.get("function") or tool
    name = _sanitize_tool_name(fn.get("name", ""))
    schema = fn.get("parameters") or fn.get("input_schema") or {"type": "object", "properties": {}}
    schema = _sanitize_schema(schema)
    return {
        "toolSpecification": {
            "name": name,
            "description": fn.get("description") or f"Tool: {name}",
            "inputSchema": {"json": schema},
        }
    }


def _tool_results_from_message(msg: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if msg.get("role") == "tool":
        results.append({
            "toolUseId": msg.get("tool_call_id") or msg.get("id") or str(uuid.uuid4()),
            "status": "success",
            "content": [{"text": _text_from_content(msg.get("content"))}],
        })
        return results

    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results.append({
                    "toolUseId": block.get("tool_use_id") or block.get("id") or str(uuid.uuid4()),
                    "status": "success",
                    "content": [{"text": _text_from_content(block.get("content"))}],
                })
    return results


def _tool_uses_from_message(msg: dict[str, Any]) -> list[dict[str, Any]]:
    tool_uses: list[dict[str, Any]] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"_raw": args}
        tool_uses.append({
            "toolUseId": tc.get("id") or str(uuid.uuid4()),
            "name": _sanitize_tool_name(fn.get("name", "")),
            "input": args,
        })

    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_uses.append({
                    "toolUseId": block.get("id") or str(uuid.uuid4()),
                    "name": _sanitize_tool_name(block.get("name", "")),
                    "input": block.get("input") or {},
                })
    return tool_uses


def _convert_messages(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    history: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_tools = [_tool_spec(tool) for tool in tools]

    for msg in messages:
        role = msg.get("role", "user")

        if role == "assistant":
            content = _text_from_content(msg.get("content")).strip() or "..."
            assistant_msg: dict[str, Any] = {
                "assistantResponseMessage": {"content": content}
            }
            tool_uses = _tool_uses_from_message(msg)
            if tool_uses:
                assistant_msg["assistantResponseMessage"]["toolUses"] = tool_uses
            history.append(assistant_msg)
            continue

        images: list[dict[str, Any]] = []
        text = _text_from_content(msg.get("content"), images=images).strip()
        if role == "system":
            text = f"{text}\n\n{KIRO_AGENTIC_SYSTEM_PROMPT}".strip()
        if not text and role != "tool":
            text = "continue"

        user_msg: dict[str, Any] = {
            "userInputMessage": {
                "content": text,
                "modelId": model,
                "origin": "AI_EDITOR",
            }
        }
        if images:
            user_msg["userInputMessage"]["images"] = images
        ctx: dict[str, Any] = {}
        tool_results = _tool_results_from_message(msg)
        if tool_results:
            ctx["toolResults"] = tool_results
        if pending_tools:
            ctx["tools"] = pending_tools
            pending_tools = []
        if ctx:
            user_msg["userInputMessage"]["userInputMessageContext"] = ctx
        history.append(user_msg)

    merged_history: list[dict[str, Any]] = []
    for item in history:
        if (
            item.get("userInputMessage")
            and merged_history
            and merged_history[-1].get("userInputMessage")
        ):
            prev = merged_history[-1]["userInputMessage"]
            curr = item["userInputMessage"]
            if curr.get("content"):
                prev["content"] = "\n\n".join(part for part in (prev.get("content"), curr.get("content")) if part)
            if curr.get("images"):
                prev.setdefault("images", []).extend(curr["images"])
            curr_ctx = curr.get("userInputMessageContext") or {}
            if curr_ctx:
                prev_ctx = prev.setdefault("userInputMessageContext", {})
                if curr_ctx.get("toolResults"):
                    prev_ctx.setdefault("toolResults", []).extend(curr_ctx["toolResults"])
                if curr_ctx.get("tools") and not prev_ctx.get("tools"):
                    prev_ctx["tools"] = curr_ctx["tools"]
        else:
            merged_history.append(item)
    history = merged_history

    for idx in range(len(history) - 1, -1, -1):
        if "userInputMessage" in history[idx]:
            current = history.pop(idx)
            break

    first_history_tools = None
    for item in history:
        ctx = item.get("userInputMessage", {}).get("userInputMessageContext") or {}
        if ctx.get("tools"):
            first_history_tools = ctx["tools"]
            break

    for item in history:
        user_msg = item.get("userInputMessage")
        if not user_msg:
            continue
        ctx = user_msg.get("userInputMessageContext")
        if ctx and "tools" in ctx:
            del ctx["tools"]
        if ctx is not None and not ctx:
            del user_msg["userInputMessageContext"]
        if not user_msg.get("modelId"):
            user_msg["modelId"] = model
        if not user_msg.get("origin"):
            user_msg["origin"] = "AI_EDITOR"

    if current is None:
        current = {"userInputMessage": {"content": "continue", "modelId": model, "origin": "AI_EDITOR"}}
    else:
        current_user = current["userInputMessage"]
        current_user.setdefault("modelId", model)
        current_user.setdefault("origin", "AI_EDITOR")

    if first_history_tools and not current["userInputMessage"].get("userInputMessageContext", {}).get("tools"):
        current["userInputMessage"].setdefault("userInputMessageContext", {})["tools"] = first_history_tools

    return history, current


def resolve_kiro_model(model: str) -> str:
    """Strip provider prefix and normalize legacy Claude tier names."""
    raw = model.split("/", 1)[1] if model.startswith("kiro/") else model
    lower = raw.lower()
    if "sonnet" in lower:
        return "claude-sonnet-4.5"
    if "haiku" in lower:
        return "claude-haiku-4.5"
    if "opus" in lower:
        return "claude-sonnet-4.5"
    return raw


def translate(body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Translate an OpenAI chat request to Kiro GenerateAssistantResponse."""
    model = resolve_kiro_model(kwargs.get("model") or body.get("model", "claude-sonnet-4.5"))
    history, current = _convert_messages(body.get("messages") or [], body.get("tools") or [], model)
    timestamp = datetime.now(timezone.utc).isoformat()
    content = current["userInputMessage"].get("content") or "continue"
    current["userInputMessage"]["content"] = f"[Context: Current time is {timestamp}]\n\n{content}"

    max_tokens = body.get("max_tokens") or kwargs.get("max_tokens") or 32000
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        max_tokens = 32000
    max_tokens = min(max_tokens, 32000)
    inference_config: dict[str, Any] = {"maxTokens": max_tokens}
    if body.get("temperature") is not None:
        inference_config["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        inference_config["topP"] = body["top_p"]

    result = {
        "conversationState": {
            "chatTriggerType": "MANUAL",
            "conversationId": body.get("conversation_id") or str(uuid.uuid4()),
            "currentMessage": current,
            "history": history,
        },
        "inferenceConfig": inference_config,
    }
    profile_arn = kwargs.get("profile_arn") or body.get("profileArn")
    if profile_arn:
        result["profileArn"] = profile_arn
    return result

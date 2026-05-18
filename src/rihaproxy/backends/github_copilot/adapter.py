"""
GitHub Copilot adapter.
"""

from __future__ import annotations

import time
import uuid
import re
from typing import Any, AsyncIterator

import structlog

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport
from rihaproxy.transport.base import AuthError

logger = structlog.get_logger()

COPILOT_BASE_URL = "https://api.githubcopilot.com"


class GitHubCopilotAdapter(BackendAdapter):
    """
    Adapter for official GitHub Copilot API.
    """

    provider_name = "github-copilot"
    provider_aliases = ["github", "copilot"]
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return COPILOT_BASE_URL

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._copilot_token: str | None = None
        self._token_expires_at: float = 0

    async def _get_copilot_token(self) -> str | None:
        """Exchange GitHub OAuth token for a Copilot session token."""
        if self._copilot_token and time.time() < self._token_expires_at - 60:
            return self._copilot_token

        if not self.api_key:
            return None

        logger.debug("copilot_token_exchange", provider=self.provider_name)
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, proxy=self.proxy) as client:
                response = await client.get(
                    "https://api.github.com/copilot_internal/v2/token",
                    headers={
                        "Authorization": f"token {self.api_key}",
                        "Accept": "application/json",
                        "User-Agent": "GitHubCopilotChat/0.38.0",
                        "Editor-Version": "vscode/1.110.0",
                        "Editor-Plugin-Version": "copilot-chat/0.38.0",
                        "x-github-api-version": "2025-04-01",
                    }
                )
                if response.status_code != 200:
                    logger.error("copilot_token_exchange_failed", status=response.status_code, body=response.text[:200])
                    return None
                
                data = response.json()
                self._copilot_token = data.get("token")
                self._token_expires_at = data.get("expires_at", time.time() + 1800)
                
                logger.debug("copilot_token_acquired", expires_at=self._token_expires_at)
                return self._copilot_token
        except Exception as e:
            logger.error("copilot_token_exchange_error", error=str(e))
            return None

    def _sanitize_messages(self, messages: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
        """Make Claude Code/OpenAI mixed content acceptable to Copilot chat."""
        sanitized: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("role") == "system" and not msg.get("content"):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                sanitized.append(dict(msg))
                continue

            clean_parts: list[dict[str, Any]] = []
            for part in content:
                if not isinstance(part, dict):
                    clean_parts.append({"type": "text", "text": str(part)})
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    clean_parts.append({"type": "text", "text": part.get("text", "")})
                elif ptype == "image_url":
                    clean_parts.append(part)
                elif ptype == "image":
                    src = part.get("source", {})
                    if src.get("type") == "base64" and src.get("data"):
                        media = src.get("media_type", "image/png")
                        clean_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{media};base64,{src['data']}", "detail": "auto"},
                        })
                elif ptype in ("tool_use", "tool_result", "thinking"):
                    text = part.get("text") or part.get("content") or part
                    clean_parts.append({
                        "type": "text",
                        "text": text if isinstance(text, str) else str(text),
                    })

            item = dict(msg)
            item["content"] = clean_parts or None
            sanitized.append(item)

        return sanitized

    def _sanitize_schema(self, schema: Any) -> dict[str, Any]:
        """Normalize Claude/MCP JSON schemas to Copilot's OpenAI subset."""
        if not isinstance(schema, dict):
            return {"type": "object", "properties": {}}

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
            "additionalProperties",
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
            if key == "additionalProperties" and value is True:
                continue
            if key == "type" and isinstance(value, list):
                clean[key] = next((v for v in value if isinstance(v, str) and v != "null"), "string")
            elif key == "properties" and isinstance(value, dict):
                clean[key] = {
                    str(prop_name): self._sanitize_schema(prop_schema)
                    for prop_name, prop_schema in value.items()
                    if isinstance(prop_name, str)
                }
            elif key == "required" and isinstance(value, list):
                clean[key] = [item for item in value if isinstance(item, str)]
            elif key == "items":
                clean[key] = self._sanitize_schema(value)
            elif key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
                clean[key] = [self._sanitize_schema(item) for item in value]
            else:
                clean[key] = value

        if clean.get("type") is None and ("properties" in clean or "required" in clean):
            clean["type"] = "object"
        if clean.get("type") == "object" and "properties" not in clean:
            clean["properties"] = {}
        if isinstance(clean.get("required"), list) and isinstance(clean.get("properties"), dict):
            valid_names = set(clean["properties"])
            clean["required"] = [item for item in clean["required"] if item in valid_names]
        return clean or {"type": "object", "properties": {}}

    def _sanitize_tool_name(self, name: Any) -> str:
        """Copilot/OpenAI function names must be short alnum/underscore/dash."""
        raw = str(name or "tool")
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
        return (cleaned or "tool")[:64]

    def _sanitize_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """Convert Anthropic/OpenAI tool declarations to Copilot-safe functions."""
        converted: list[dict[str, Any]] = []
        for index, tool in enumerate(tools):
            if not isinstance(tool, dict):
                continue

            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                function = tool["function"]
                name = self._sanitize_tool_name(function.get("name") or f"tool_{index}")
                description = str(function.get("description") or "")[:1024]
                parameters = self._sanitize_schema(function.get("parameters"))
            else:
                name = self._sanitize_tool_name(tool.get("name") or f"tool_{index}")
                description = str(tool.get("description") or "")[:1024]
                parameters = self._sanitize_schema(
                    tool.get("input_schema") or tool.get("parameters") or {"type": "object", "properties": {}}
                )

            converted.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            })
        return converted

    @staticmethod
    def _requires_max_completion_tokens(model: str) -> bool:
        m = model.lower()
        return m.startswith("gpt-5") or m.startswith(("o1", "o3", "o4"))

    @staticmethod
    def _supports_temperature(model: str) -> bool:
        return "gpt-5.4" not in model.lower()

    @staticmethod
    def _supports_reasoning_effort(model: str) -> bool:
        m = model.lower()
        if "claude" in m:
            return ("opus" in m and "4.6" in m) or ("sonnet" in m and "4.6" in m)
        return True

    @staticmethod
    def _responses_candidate(model: str) -> bool:
        m = model.lower()
        return "codex" in m or (m.startswith("gpt-5") and not m.endswith("-mini"))

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via GitHub Copilot."""
        
        # Strip provider prefix if present
        mapped_model = model
        if mapped_model.startswith("github-copilot/"):
            mapped_model = mapped_model[len("github-copilot/"):]
        elif mapped_model.startswith("github/"):
            mapped_model = mapped_model[len("github/"):]
        elif mapped_model.startswith("copilot/"):
            mapped_model = mapped_model[len("copilot/"):]

        # Get session token
        copilot_token = await self._get_copilot_token()
        if not copilot_token:
            raise AuthError("Could not acquire Copilot session token. Are you logged in to GitHub?")

        # Modernized Copilot headers (synced with hermes-agent/VS Code)
        extra_headers = {
            "Authorization": f"Bearer {copilot_token}",
            "Content-Type": "application/json",
            "copilot-integration-id": "vscode-chat",
            "editor-version": "vscode/1.110.0",
            "editor-plugin-version": "copilot-chat/0.38.0",
            "user-agent": "GitHubCopilotChat/0.38.0",
            "openai-intent": "conversation-panel",
            "x-github-api-version": "2025-04-01",
            "x-request-id": str(uuid.uuid4()),
            "x-vscode-user-agent-library-version": "electron-fetch",
            "X-Initiator": "user",
        }
        
        if "claude" in mapped_model.lower():
            extra_headers["anthropic-version"] = "2023-06-01"
        
        logger.debug("copilot_headers", headers={k: v if k != "Authorization" else "Bearer ***" for k, v in extra_headers.items()})

        # Handle vision if image content is present
        has_vision = False
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and (part.get("type") == "image_url" or part.get("type") == "image"):
                        has_vision = True
                        break
            if has_vision:
                break
        
        if has_vision:
            extra_headers["Copilot-Vision-Request"] = "true"

        # Model normalization: Claude Code may ask for unavailable future/opus
        # tiers. For GitHub Copilot, keep Claude traffic on Haiku by default
        # because it is the most reliable Copilot Claude model for this route.
        original_mapped = mapped_model
        if "claude" in mapped_model.lower():
            lower = mapped_model.lower()
            if "haiku" in lower:
                mapped_model = "claude-haiku-4.5"
            elif "sonnet" in lower:
                mapped_model = "claude-haiku-4.5"
            elif "opus" in lower:
                mapped_model = "claude-haiku-4.5"
            else:
                mapped_model = "claude-haiku-4.5"
        
        if mapped_model != original_mapped:
            logger.debug("copilot_model_mapped", from_model=original_mapped, to_model=mapped_model)

        # Detect API mode
        # Note: Testing shows /chat/completions works for Claude models on Student accounts, 
        # while /v1/messages may return 400 model_not_supported.
        api_mode = "chat_completions"
        
        # Parameters supported by Copilot
        if api_mode == "anthropic_messages":
            # Anthropic Messages API format
            # Convert system message to top-level field if present
            system_msg = ""
            new_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg = msg.get("content", "")
                else:
                    new_messages.append(msg)
            
            body: dict[str, Any] = {
                "model": mapped_model,
                "messages": new_messages,
                "stream": stream,
                "max_tokens": kwargs.get("max_tokens", 4096)
            }
            if system_msg:
                body["system"] = system_msg
        else:
            body: dict[str, Any] = {
                "model": mapped_model,
                "messages": self._sanitize_messages(messages, mapped_model),
                "stream": stream,
            }
            for key in ("temperature", "top_p", "max_tokens", "stop", "tools", "tool_choice", "reasoning_effort"):
                if key in kwargs and kwargs[key] is not None:
                    body[key] = kwargs[key]

        # GitHub Copilot Limit: max 128 tools
        if "tools" in body and isinstance(body["tools"], list) and len(body["tools"]) > 128:
            logger.warning("copilot_trimming_tools", count=len(body["tools"]), limit=128)
            body["tools"] = body["tools"][:128]

        # Tool conversion for Copilot (standard OpenAI format)
        if "tools" in body and isinstance(body["tools"], list):
            body["tools"] = self._sanitize_tools(body["tools"])
            if not body["tools"]:
                body.pop("tools", None)
                body.pop("tool_choice", None)
        elif "tools" in body:
            body.pop("tools", None)
            body.pop("tool_choice", None)

        # Final sanitization: Strip parameters that cause 400 on Copilot
        # 1. newer OpenAI 'max_completion_tokens' (use max_tokens instead)
        if "max_completion_tokens" in body:
            if "max_tokens" not in body:
                body["max_tokens"] = body["max_completion_tokens"]
            del body["max_completion_tokens"]
        if "claude" in mapped_model.lower() and isinstance(body.get("max_tokens"), int) and body["max_tokens"] > 8192:
            logger.debug("copilot_clamping_max_tokens", from_tokens=body["max_tokens"], to_tokens=8192)
            body["max_tokens"] = 8192
        if self._requires_max_completion_tokens(mapped_model) and "max_tokens" in body:
            body["max_completion_tokens"] = body.pop("max_tokens")
        if not self._supports_temperature(mapped_model):
            body.pop("temperature", None)
            
        # 2. Claude-specific 'thinking'
        body.pop("thinking", None)
        if body.get("reasoning_effort") == "none" or not self._supports_reasoning_effort(mapped_model):
            body.pop("reasoning_effort", None)

        path = "/chat/completions"

        initiator = extra_headers.get("X-Initiator") or extra_headers.get("x-initiator") or "user"
        logger.debug(
            "copilot_request",
            model=mapped_model,
            stream=stream,
            path=path,
            initiator=initiator,
            messages=len(body.get("messages") or []),
            tools=len(body.get("tools") or []),
            max_tokens=body.get("max_tokens") or body.get("max_completion_tokens"),
        )
        
        try:
            return await self._transport.post(
                path=path,
                body=body,
                stream=stream,
                extra_headers=extra_headers
            )
        except Exception as e:
            raise self.handle_error(e) from e

    async def _translate_anthropic_stream(self, stream: AsyncIterator[str]) -> AsyncIterator[str]:
        """Translate Anthropic stream chunks to OpenAI format."""
        import json as _json
        from rihaproxy.translation.response import claude_to_openai
        
        async for chunk_str in stream:
            try:
                chunk = _json.loads(chunk_str)
                translated = claude_to_openai.translate_stream_chunk(chunk)
                if translated:
                    yield _json.dumps(translated)
            except Exception:
                continue

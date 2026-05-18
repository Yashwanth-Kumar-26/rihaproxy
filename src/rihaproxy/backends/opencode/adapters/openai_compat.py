"""
OpenCode adapter — OpenAI-compatible endpoint.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport

OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"


class OpenCodeAdapter(BackendAdapter):
    """
    Adapter for OpenCode — supports both Go and Zen variants.
    Uses OpenAI-compatible format.
    """

    provider_name = "opencode"
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return OPENCODE_BASE_URL

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via OpenCode."""
        import structlog
        log = structlog.get_logger()

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens",
                    "stop", "tools", "tool_choice", "response_format"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        # Safety-net: convert Anthropic-format tools to OpenAI format if needed
        if "tools" in body and isinstance(body["tools"], list):
            converted = []
            for t in body["tools"]:
                if isinstance(t, dict) and "input_schema" in t:
                    # Anthropic format → convert to OpenAI format
                    converted.append({
                        "type": "function",
                        "function": {
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                        }
                    })
                else:
                    converted.append(t)
            body["tools"] = converted

        # Safety-net: normalize tool_choice to OpenAI format
        if "tool_choice" in body:
            tc = body["tool_choice"]
            if isinstance(tc, dict):
                choice_type = tc.get("type", "auto")
                if choice_type == "auto" or choice_type == "any":
                    body["tool_choice"] = "auto"
                elif choice_type == "none":
                    body["tool_choice"] = "none"
                elif choice_type == "tool":
                    body["tool_choice"] = {"type": "function", "function": {"name": tc.get("name", "")}}

        log.debug("opencode_request_body", model=model, keys=list(body.keys()),
                  tool_count=len(body.get("tools", [])),
                  tool_choice=body.get("tool_choice"))

        try:
            result = await self._transport.post("/chat/completions", body, stream=stream)
            self._request_count += 1
            return result
        except Exception as e:
            err_str = str(e).lower()
            # If tools caused a 400, retry without tools (free-tier model limitation)
            if ("400" in str(e) or "invalid" in err_str) and ("tools" in body or "tool_choice" in body):
                log.warning("opencode_tools_rejected_retrying_without_tools",
                            model=model, error=str(e)[:200])
                body_no_tools = {k: v for k, v in body.items()
                                 if k not in ("tools", "tool_choice")}
                try:
                    result = await self._transport.post("/chat/completions", body_no_tools, stream=stream)
                    self._request_count += 1
                    return result
                except Exception as e2:
                    raise self.handle_error(e2) from e2
            raise self.handle_error(e) from e
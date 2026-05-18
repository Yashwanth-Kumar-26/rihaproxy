"""
Ruflo adapter — routes to Ruflo orchestration platform.
Supports both OpenAI-compatible and Anthropic-native formats.
"""

from __future__ import annotations

import structlog
from typing import Any, AsyncIterator

from rihaproxy.backends.base import (
    BackendAdapter,
    BackendError,
    ProviderUnavailable,
)
from rihaproxy.transport.chat_completions import ChatCompletionsTransport
from rihaproxy.transport.messages import MessagesTransport

logger = structlog.get_logger()


class RufloAdapter(BackendAdapter):
    """
    Adapter for Ruflo — agent orchestration layer.
    
    Supports:
    - Native Anthropic format (/v1/messages)
    - OpenAI compatible format (/v1/chat/completions)
    - Streaming
    """

    provider_name = "ruflo"
    supports_streaming = True
    supports_tools = True

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 60,
        proxy: str | None = None,
    ):
        super().__init__(api_key, base_url, timeout, proxy)
        self._messages_transport = MessagesTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def default_base_url(self) -> str:
        return "http://localhost:3000"

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def map_model(self, model: str) -> str:
        """Map model name — strip provider prefix."""
        if model.startswith("ruflo/"):
            return model[len("ruflo/"):]
        return model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via Ruflo."""
        if self.is_rate_limited():
            raise ProviderUnavailable("Ruflo is rate limited")

        # Determine which endpoint to use based on model or kwargs
        # If it looks like an Anthropic request (has system, or messages role is user/assistant only)
        # Ruflo usually prefers /v1/messages for Claude.
        
        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        # Pass through additional params
        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens",
                    "stop", "tools", "tool_choice", "response_format", "system",
                    "plugins", "use_mcp", "mcp_tools"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        # Inject default plugins if not specified
        from rihaproxy.config import settings
        if "plugins" not in body and settings.ruflo_plugins:
            if settings.ruflo_plugins.lower() == "true":
                body["plugins"] = True
            elif settings.ruflo_plugins.lower() != "false":
                body["plugins"] = [p.strip() for p in settings.ruflo_plugins.split(",")]
        
        if "use_mcp" not in body:
            body["use_mcp"] = settings.ruflo_auto_tools

        try:
            # If system prompt is present, or it's a Claude model, use Messages API
            is_anthropic_request = "system" in kwargs or "claude" in model.lower()
            
            if is_anthropic_request:
                result = await self._messages_transport.post("/v1/messages", body, stream=stream)
            else:
                result = await self._transport.post("/v1/chat/completions", body, stream=stream)
                
            self._request_count += 1
            return result
        except Exception as e:
            raise self.handle_error(e) from e

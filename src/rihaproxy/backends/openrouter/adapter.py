"""
OpenRouter adapter — routes to 40+ models through a single API key.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import (
    BackendAdapter,
    BackendError,
    ModelNotFound,
    ProviderUnavailable,
)
from rihaproxy.transport.chat_completions import ChatCompletionsTransport

# OpenRouter base URL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(BackendAdapter):
    """
    Adapter for OpenRouter — single key, 40+ providers.

    Supports:
    - All OpenAI-compatible models
    - Streaming
    - Tool calling (some models)
    """

    provider_name = "openrouter"
    provider_aliases = ["openai"]
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return OPENROUTER_BASE_URL

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def map_model(self, model: str) -> str:
        """Map model name — strip provider prefix for OpenRouter API."""
        # Strip provider prefix if present
        if model.startswith("openrouter/"):
            return model[len("openrouter/"):]
        # If already a raw model ID (no prefix), return as-is
        return model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via OpenRouter."""
        if self.is_rate_limited():
            raise ProviderUnavailable("OpenRouter is rate limited")

        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        # Pass through additional params
        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens",
                    "stop", "tools", "tool_choice", "response_format", "seed"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        try:
            result = await self._transport.post("/chat/completions", body, stream=stream)
            self._request_count += 1
            return result
        except Exception as e:
            raise self.handle_error(e) from e
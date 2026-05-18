"""
Z.AI adapter — GLM models via OpenAI-compatible endpoint.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport

# Z.AI Coding Plan — free GLM models
ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4"


class ZAIAdapter(BackendAdapter):
    """
    Adapter for Z.AI — GLM models via OpenAI-compatible API.
    Uses Z.AI Coding Plan endpoint with free GLM models.
    """

    provider_name = "zai"
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return ZAI_BASE_URL

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def map_model(self, model: str) -> str:
        """Strip zai/ prefix if present."""
        if model.startswith("zai/"):
            return model[len("zai/"):]
        return model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via Z.AI."""
        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens", "stop"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        try:
            result = await self._transport.post("/chat/completions", body, stream=stream)
            self._request_count += 1
            return result
        except Exception as e:
            raise self.handle_error(e) from e

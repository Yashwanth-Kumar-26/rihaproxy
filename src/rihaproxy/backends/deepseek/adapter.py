"""
DeepSeek adapter — DeepSeek's API.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekAdapter(BackendAdapter):
    """
    Adapter for DeepSeek — chat and reasoning models.
    Supports DeepSeek Chat, DeepSeek Coder, and DeepSeek Reasoner.
    """

    provider_name = "deepseek"
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return DEEPSEEK_BASE_URL

    def _create_transport(self) -> ChatCompletionsTransport:
        return ChatCompletionsTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def map_model(self, model: str) -> str:
        """Map model name to DeepSeek format."""
        model_map = {
            "deepseek-chat": "deepseek-chat",
            "deepseek-coder": "deepseek-coder",
            "deepseek-reasoner": "deepseek-reasoner",
        }
        return model_map.get(model, model)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via DeepSeek."""
        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        for key in ("temperature", "top_p", "max_tokens", "stop", "tools", "tool_choice"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        try:
            result = await self._transport.post("/chat/completions", body, stream=stream)
            self._request_count += 1
            return result
        except Exception as e:
            raise self.handle_error(e) from e
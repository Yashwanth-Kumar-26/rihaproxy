"""
Generic OpenAI-compatible adapter.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport


class OpenAIAdapter(BackendAdapter):
    """
    Generic adapter for any provider that follows the OpenAI Chat Completions API.
    """

    provider_name = "openai"
    provider_aliases = [
        "groq", "together", "mistral", "perplexity", "fireworks", "xai", 
        "hyperbolic", "siliconflow", "nebius", "cerebras", "blackbox", 
        "chutes", "kimi", "minimax", "alicode", "glm", "nvidia", "nim",
        "deepseek", "volcengine-ark", "byteplus", "alicode-intl", "glm-cn",
        "minimax-cn", "xiaomi-mimo", "commandcode", "opencode-go"
    ]
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return "https://api.openai.com/v1"

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
        """Send chat request via OpenAI-compatible API."""
        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        # Add parameters supported by OpenAI
        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens", "stop", "tools", "tool_choice", "response_format"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        try:
            return await self._transport.post("/chat/completions", body, stream=stream)
        except Exception as e:
            raise self.handle_error(e) from e

    def map_model(self, model: str) -> str:
        """Strip provider prefix if present."""
        if "/" in model:
            parts = model.split("/")
            # Only strip if the first part is a known provider alias
            if parts[0].lower() in ([self.provider_name] + self.provider_aliases):
                return "/".join(parts[1:])
        return model

"""
Anthropic adapter — routes to Claude models.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.messages import MessagesTransport

ANTHROPIC_BASE_URL = "https://api.anthropic.com"


class AnthropicAdapter(BackendAdapter):
    """
    Adapter for Anthropic (Claude).
    Uses the native /v1/messages protocol.
    """

    provider_name = "anthropic"
    provider_aliases = ["claude"]
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return ANTHROPIC_BASE_URL

    def _create_transport(self) -> MessagesTransport:
        return MessagesTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            proxy=self.proxy,
        )

    def map_model(self, model: str) -> str:
        """Strip provider prefix."""
        if model.startswith("anthropic/"):
            return model[len("anthropic/"):]
        if model.startswith("claude/"):
            return model[len("claude/"):]
        return model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Send chat request via Anthropic."""
        # Use existing messages if already in Anthropic format, 
        # or rely on translation layer which is called before hub.chat
        
        body: dict[str, Any] = {
            "model": self.map_model(model),
            "messages": messages,
            "stream": stream,
        }

        # Parameters supported by Anthropic
        # Note: 'system' is expected as a top-level field, not inside messages.
        # Most of the time the translation layer handles this, but we'll ensure it here too.
        filtered_messages = []
        system = kwargs.get("system")
        
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content")
            else:
                filtered_messages.append(msg)
        
        body["messages"] = filtered_messages
        if system:
            body["system"] = system

        for key in ("temperature", "top_p", "max_tokens", "stop_sequences", "tools", "tool_choice"):
            if key in kwargs and kwargs[key] is not None:
                # Special mapping: stop -> stop_sequences
                if key == "stop":
                    body["stop_sequences"] = [kwargs[key]] if isinstance(kwargs[key], str) else kwargs[key]
                else:
                    body[key] = kwargs[key]

        try:
            return await self._transport.post("/v1/messages", body, stream=stream)
        except Exception as e:
            raise self.handle_error(e) from e

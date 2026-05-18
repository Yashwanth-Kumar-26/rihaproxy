"""
GitHub Codex / Models adapter.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from rihaproxy.backends.base import BackendAdapter
from rihaproxy.transport.chat_completions import ChatCompletionsTransport

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


class CodexAdapter(BackendAdapter):
    """
    Adapter for GitHub Codex/Models.
    Supports GitHub Models API with OpenAI compatibility.
    """

    provider_name = "codex"
    provider_aliases = ["github-models"]
    supports_streaming = True
    supports_tools = True

    def default_base_url(self) -> str:
        return GITHUB_MODELS_BASE_URL

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
        """Send chat request via GitHub Models."""
        import structlog
        log = structlog.get_logger()

        # Map model name: ensure it doesn't have the provider prefix
        mapped_model = model
        if mapped_model.startswith("codex/"):
            mapped_model = mapped_model[len("codex/"):]
        elif mapped_model.startswith("github/"):
            mapped_model = mapped_model[len("github/"):]

        body: dict[str, Any] = {
            "model": mapped_model,
            "messages": messages,
            "stream": stream,
        }

        # Parameters supported by GitHub Models
        for key in ("temperature", "top_p", "max_tokens", "stop", "tools", "tool_choice"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]

        # Use the same safety net as OpenCode for tool conversion
        if "tools" in body and isinstance(body["tools"], list):
            converted = []
            for t in body["tools"]:
                if isinstance(t, dict) and "input_schema" in t:
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

        if "tool_choice" in body:
            tc = body["tool_choice"]
            if isinstance(tc, dict):
                choice_type = tc.get("type", "auto")
                if choice_type in ("auto", "any"):
                    body["tool_choice"] = "auto"
                elif choice_type == "none":
                    body["tool_choice"] = "none"
                elif choice_type == "tool":
                    body["tool_choice"] = {"type": "function", "function": {"name": tc.get("name", "")}}

        log.debug("codex_request", model=mapped_model, stream=stream)

        try:
            # GitHub Models uses standard /chat/completions endpoint
            result = await self._transport.post("/chat/completions", body, stream=stream)
            self._request_count += 1
            return result
        except Exception as e:
            # Retry without tools if 400 (common on GitHub Models for some free tier models)
            if "400" in str(e) and ("tools" in body or "tool_choice" in body):
                log.warning("codex_tools_rejected_retrying", error=str(e)[:200])
                body_no_tools = {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
                try:
                    return await self._transport.post("/chat/completions", body_no_tools, stream=stream)
                except Exception as e2:
                    raise self.handle_error(e2) from e2
            raise self.handle_error(e) from e

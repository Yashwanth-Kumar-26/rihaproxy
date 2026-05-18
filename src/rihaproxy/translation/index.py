"""
Translation registry — selects and orchestrates request/response translators.
"""

from __future__ import annotations

import structlog
from typing import Any, Callable

logger = structlog.get_logger()


class TranslationError(Exception):
    """Raised when translation fails."""
    pass


class TranslationRegistry:
    """
    Registry of format translators.
    Handles both request translation (client format → provider format)
    and response translation (provider format → client format).
    """

    def __init__(self) -> None:
        self._request_translators: dict[str, dict[str, Callable]] = {}
        self._response_translators: dict[str, dict[str, Callable]] = {}
        self._registered = False

    def register(self) -> None:
        """Register all built-in translators (lazy init to avoid import loops)."""
        if self._registered:
            return

        from rihaproxy.translation.request import (
            openai_to_claude,
            openai_to_gemini,
            claude_to_openai,
            gemini_to_openai,
            openai_to_vertex,
            openai_to_ollama,
            openai_to_kiro,
            openai_to_cursor,
            openai_to_codex,
            openai_to_antigravity,
        )
        from rihaproxy.translation.response import (
            claude_to_openai as c2o,
            gemini_to_openai as g2o,
            openai_to_openai,
            kiro_to_openai,
            cursor_to_openai,
            ollama_to_openai,
        )

        # Request translators: source → target → translator
        req = self._request_translators
        req.setdefault("openai", {})["anthropic"] = openai_to_claude.translate
        req.setdefault("openai", {})["gemini"] = openai_to_gemini.translate_request
        req.setdefault("openai", {})["gemini-cli"] = openai_to_gemini.translate_request
        req.setdefault("openai", {})["vertex"] = openai_to_vertex.translate
        req.setdefault("openai", {})["ollama"] = openai_to_ollama.translate
        req.setdefault("openai", {})["kiro"] = openai_to_kiro.translate
        req.setdefault("openai", {})["cursor"] = openai_to_cursor.translate
        req.setdefault("openai", {})["codex"] = openai_to_codex.translate
        req.setdefault("openai", {})["antigravity"] = openai_to_antigravity.translate

        req.setdefault("anthropic", {})["openai"] = claude_to_openai.translate
        req.setdefault("anthropic", {})["kiro"] = lambda body, **kw: openai_to_kiro.translate(
            claude_to_openai.translate(body), **kw
        )
        req.setdefault("anthropic", {})["gemini"] = lambda body, **kw: openai_to_gemini.translate_request(
            claude_to_openai.translate(body), **kw
        )

        req.setdefault("gemini", {})["openai"] = gemini_to_openai.translate
        req.setdefault("gemini", {})["anthropic"] = lambda body, **kw: openai_to_claude.translate(
            gemini_to_openai.translate(body), **kw
        )

        # Response translators: provider → client_format → translator
        resp = self._response_translators
        resp.setdefault("anthropic", {})["openai"] = c2o.translate_response
        resp.setdefault("gemini", {})["openai"] = g2o.translate_response
        resp.setdefault("openai", {})["openai"] = openai_to_openai.pass_through
        resp.setdefault("kiro", {})["openai"] = kiro_to_openai.translate_response
        resp.setdefault("cursor", {})["openai"] = cursor_to_openai.translate_response
        resp.setdefault("ollama", {})["openai"] = ollama_to_openai.translate_response

        # Alias openai-compatible providers to use openai translators
        openai_compatible = [
            "openrouter", "opencode", "lmstudio", "lms", "nvidia", "nim",
            "deepseek", "volcengine-ark", "byteplus", "alicode-intl", "glm-cn",
            "minimax-cn", "xiaomi-mimo", "commandcode", "opencode-go",
            "voyage-ai", "huggingface", "blackbox", "chutes", "together",
            "hyperbolic", "siliconflow", "nebius", "cerebras", "chutes",
            "nanobanana", "blackbox", "ollama-local", "github", "copilot",
            "github-copilot"
        ]
        for provider in openai_compatible:
            req.setdefault("anthropic", {})[provider] = claude_to_openai.translate
            req.setdefault("gemini", {})[provider] = lambda body, **kw: openai_to_gemini.translate_request(claude_to_openai.translate(body), **kw)
            resp.setdefault(provider, {})["openai"] = openai_to_openai.pass_through

        self._registered = True

    def translate_request(
        self,
        body: dict[str, Any],
        source_format: str,
        target_format: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Translate a request from source format to target format.
        """
        if source_format == target_format:
            return body

        if not self._registered:
            self.register()

        translators = self._request_translators.get(source_format, {})
        translator = translators.get(target_format)

        if not translator:
            logger.warning(
                "no_request_translator",
                source=source_format,
                target=target_format,
            )
            raise TranslationError(
                f"No request translator for {source_format} → {target_format}"
            )

        try:
            return translator(body, **kwargs)
        except Exception as e:
            logger.error("translation_failed", source=source_format, target=target_format, error=str(e))
            raise TranslationError(f"Translation failed: {e}") from e

    def translate_response(
        self,
        response: dict[str, Any] | str,
        provider_format: str,
        target_format: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Translate a provider response to target client format."""
        if provider_format == target_format:
            return response if isinstance(response, dict) else {}

        if not self._registered:
            self.register()

        translators = self._response_translators.get(provider_format, {})
        translator = translators.get(target_format)

        if not translator:
            logger.warning(
                "no_response_translator",
                provider=provider_format,
                target=target_format,
            )
            return response if isinstance(response, dict) else {}

        try:
            return translator(response, **kwargs)
        except Exception as e:
            logger.error("response_translation_failed", provider=provider_format, error=str(e))
            return response if isinstance(response, dict) else {}

    def translate_stream_chunk(
        self,
        chunk: str,
        provider_format: str,
        target_format: str,
        **kwargs: Any,
    ) -> str:
        """Translate a streaming SSE chunk."""
        if provider_format == target_format:
            return chunk
        return chunk


# Global registry instance (lazy)
_registry: TranslationRegistry | None = None


def get_registry() -> TranslationRegistry:
    """Get the global translation registry."""
    global _registry
    if _registry is None:
        _registry = TranslationRegistry()
    return _registry


def translate_request(body: dict[str, Any], source: str, target: str, **kwargs: Any) -> dict[str, Any]:
    """Convenience function for translating requests."""
    return get_registry().translate_request(body, source, target, **kwargs)


def translate_response(response: dict[str, Any] | str, provider: str, target: str, **kwargs: Any) -> dict[str, Any]:
    """Convenience function for translating responses."""
    return get_registry().translate_response(response, provider, target, **kwargs)

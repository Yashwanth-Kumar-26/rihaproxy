"""
Backend Hub — manages provider adapters with caching and fallback.
"""

from __future__ import annotations

import structlog
from typing import Any

from rihaproxy.backends.base import BackendAdapter, ProviderUnavailable
from rihaproxy.config import settings

logger = structlog.get_logger()


class BackendHub:
    """
    Manages all provider adapters with caching.
    Provides unified interface for routing requests to backends.
    """

    def __init__(self):
        self._cache: dict[str, BackendAdapter] = {}
        from rihaproxy.backends.registry import discover_adapters
        discover_adapters()

    async def _get_token_for_provider(self, name: str) -> str | None:
        """Get API key for a provider, checking token manager first."""
        # Try token manager (OAuth connections)
        try:
            from rihaproxy.auth.token_manager import get_token_manager
            tm = get_token_manager()
            token = await tm.get_token(name)
            if token:
                return token
        except Exception:
            pass

        # Fall back to settings
        return settings.get_api_key(name)

    async def _create_adapter(self, name: str) -> BackendAdapter | None:
        from rihaproxy.backends.registry import get_adapter_class
        adapter_class = get_adapter_class(name)
        if not adapter_class:
            return None

        key = await self._get_token_for_provider(name)
        base_url = settings.get_base_url(name)

        return adapter_class(
            api_key=key,
            base_url=base_url,
            timeout=settings.request_timeout,
            proxy=settings.http_proxy or None,
        )

    async def get_adapter(self, name: str) -> BackendAdapter:
        """
        Get or create an adapter for a provider.
        Caches adapters for reuse.
        """
        name = name.lower()
        if name not in self._cache:
            adapter = await self._create_adapter(name)
            if adapter is None:
                raise ValueError(f"Unknown provider: {name}")
            self._cache[name] = adapter
            logger.info("adapter_created", provider=name)

        return self._cache[name]

    def resolve_provider(self, model: str) -> str:
        """
        Resolve provider name from a model string.
        If the model has a prefix (e.g. 'opencode/model-name') that matches
        a registered provider, it routes there. Otherwise it falls back to
        the default backend.
        """
        if "/" in model:
            prefix = model.split("/")[0].lower()
            if prefix in self.providers:
                return prefix

        # Fallback to default backend
        return settings.default_backend

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | Any:
        """
        Route a chat request to the appropriate backend.
        Tries all accounts for a provider before moving to fallback.
        """
        provider = self.resolve_provider(model)
        last_error: Exception | None = None

        # Try multi-account fallback within this provider
        try:
            adapter = await self.get_adapter(provider)
            return await adapter.chat(messages, model, stream=stream, **kwargs)
        except (ProviderUnavailable, BackendError) as e:
            last_error = e
            # Try other accounts for the same provider
            try:
                from rihaproxy.auth.token_manager import get_token_manager
                tm = get_token_manager()
                all_tokens = await tm.get_all_tokens(provider)
                for token, conn in all_tokens[1:]:  # Skip first (already tried)
                    # Create temporary adapter with this token
                    from rihaproxy.backends.registry import get_adapter_class
                    adapter_class = get_adapter_class(provider)
                    if adapter_class:
                        temp_adapter = adapter_class(
                            api_key=token,
                            base_url=settings.get_base_url(provider),
                            timeout=settings.request_timeout,
                            proxy=settings.http_proxy or None,
                        )
                        try:
                            logger.info("trying_account", provider=provider, conn_id=conn.get("id"))
                            return await temp_adapter.chat(messages, model, stream=stream, **kwargs)
                        except (ProviderUnavailable, BackendError):
                            continue
            except Exception:
                pass

            # Try fallback chain
            for fallback in settings.fallback_chain:
                if fallback == provider:
                    continue
                try:
                    fallback_adapter = await self.get_adapter(fallback)
                    logger.info("using_fallback", from_provider=provider, to_provider=fallback, model=model)
                    return await fallback_adapter.chat(messages, model, stream=stream, **kwargs)
                except (ProviderUnavailable, BackendError):
                    continue

            raise

    def invalidate(self, name: str) -> None:
        """Remove an adapter from cache (forces recreation)."""
        if name.lower() in self._cache:
            del self._cache[name.lower()]

    def clear_cache(self) -> None:
        """Clear all cached adapters."""
        self._cache.clear()

    @property
    def providers(self) -> list[str]:
        """List available provider names."""
        from rihaproxy.backends.registry import get_all_providers
        return get_all_providers()

    @property
    def cached_providers(self) -> list[str]:
        """List providers with cached adapters."""
        return list(self._cache.keys())


# Global hub instance
hub = BackendHub()


def get_hub() -> BackendHub:
    """Get the global backend hub."""
    return hub
"""
Unit tests for backend hub and model resolution.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rihaproxy.backends.base import BackendAdapter, ProviderUnavailable
from rihaproxy.backends.hub import BackendHub, get_hub


class TestBackendHub:
    """Test suite for BackendHub."""

    @pytest.fixture
    def hub(self) -> BackendHub:
        """Create a fresh BackendHub instance."""
        return BackendHub()

    def test_provider_resolution_openai(self, hub: BackendHub):
        """Test provider resolution for OpenAI models."""
        assert hub.resolve_provider("openai/gpt-4o") == "openai"
        assert hub.resolve_provider("openai/gpt-4o-mini") == "openai"

    def test_provider_resolution_anthropic(self, hub: BackendHub):
        """Test provider resolution for Anthropic models."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("anthropic/claude-3-opus") == "anthropic"
        assert hub.resolve_provider("claude-3-opus") == settings.default_backend

    def test_provider_resolution_deepseek(self, hub: BackendHub):
        """Test provider resolution for DeepSeek models."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("deepseek-chat") == settings.default_backend
        assert hub.resolve_provider("deepseek/deepseek-chat") == "deepseek"

    def test_provider_resolution_nvidia(self, hub: BackendHub):
        """Test provider resolution for NVIDIA NIM models."""
        assert hub.resolve_provider("nvidia/llama-3-70b") == "nvidia"
        assert hub.resolve_provider("nvidia/llama-3.1-70b-instruct") == "nvidia"

    def test_provider_resolution_gemini(self, hub: BackendHub):
        """Test provider resolution for Gemini models."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("gemini/gemini-pro") == settings.default_backend
        assert hub.resolve_provider("google/gemini-1.5-pro") == settings.default_backend

    def test_provider_resolution_llama(self, hub: BackendHub):
        """Test provider resolution for open-source models via OpenRouter."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("meta-llama/llama-3-70b") == settings.default_backend
        assert hub.resolve_provider("mistralai/mistral-7b") == settings.default_backend

    def test_provider_resolution_gpt_models(self, hub: BackendHub):
        """Test provider resolution for GPT models via OpenRouter."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("gpt-4o") == settings.default_backend
        assert hub.resolve_provider("gpt-4-turbo") == settings.default_backend
        assert hub.resolve_provider("o1-preview") == settings.default_backend
        assert hub.resolve_provider("o3-mini") == settings.default_backend

    def test_provider_resolution_unknown_prefix(self, hub: BackendHub):
        """Test that unknown prefixes route through OpenRouter."""
        from rihaproxy.config import settings

        assert hub.resolve_provider("unknown/model") == settings.default_backend
        assert hub.resolve_provider("custom/model-name") == settings.default_backend

    def test_provider_resolution_kiro(self, hub: BackendHub):
        """Test provider resolution for Kiro models."""
        assert hub.resolve_provider("kiro/kiro-model") == "kiro"
        assert hub.resolve_provider("kr/text-model") == "kr"

    def test_provider_resolution_github(self, hub: BackendHub):
        """Test provider resolution for GitHub models."""
        assert hub.resolve_provider("github/gpt-4o") == "github"

    def test_provider_resolution_ruflo(self, hub: BackendHub):
        """Test provider resolution for Ruflo models."""
        assert hub.resolve_provider("ruflo/agent-model") == "ruflo"

    def test_available_providers(self, hub: BackendHub):
        """Test that expected providers are registered."""
        providers = hub.providers
        assert "openrouter" in providers
        assert "openai" in providers
        assert "github" in providers
        assert "kiro" in providers
        assert "deepseek" in providers
        assert "opencode" in providers
        assert "zai" in providers
        assert "ruflo" in providers

    def test_provider_aliases(self, hub: BackendHub):
        """Test provider aliases work."""
        providers = hub.providers
        assert "nim" in providers  # alias for nvidia
        assert "copilot" in providers  # alias for GitHub Copilot
        assert "kr" in providers  # alias for Kiro

    @pytest.mark.asyncio
    async def test_get_adapter_creates_instance(self, hub: BackendHub):
        """Test that get_adapter creates adapter instances."""
        adapter = await hub.get_adapter("openrouter")
        assert adapter is not None
        assert isinstance(adapter, BackendAdapter)

    @pytest.mark.asyncio
    async def test_get_adapter_caches(self, hub: BackendHub):
        """Test that get_adapter caches adapters."""
        adapter1 = await hub.get_adapter("openrouter")
        adapter2 = await hub.get_adapter("openrouter")
        assert adapter1 is adapter2

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self, hub: BackendHub):
        """Test that invalidate removes adapter from cache."""
        adapter1 = await hub.get_adapter("deepseek")
        hub.invalidate("deepseek")
        adapter2 = await hub.get_adapter("deepseek")
        assert adapter1 is not adapter2

    @pytest.mark.asyncio
    async def test_clear_cache(self, hub: BackendHub):
        """Test clearing all cached adapters."""
        await hub.get_adapter("openrouter")
        await hub.get_adapter("deepseek")
        hub.clear_cache()
        assert len(hub.cached_providers) == 0

    @pytest.mark.asyncio
    async def test_cached_providers_property(self, hub: BackendHub):
        """Test cached_providers property."""
        assert len(hub.cached_providers) == 0
        await hub.get_adapter("openrouter")
        assert "openrouter" in hub.cached_providers


class TestBackendHubFallback:
    """Test backend hub fallback behavior."""

    def test_fallback_chain_order(self):
        """Test that fallback chain is respected."""
        from rihaproxy.config import settings

        # Default fallback chain
        assert settings.fallback_chain == ["openrouter", "openai"]


class TestBackendAdapterBase:
    """Test BackendAdapter abstract base class."""

    def test_adapter_creation(self):
        """Test that adapter can be created with base parameters."""

        class TestAdapter(BackendAdapter):
            def default_base_url(self) -> str:
                return "https://api.example.com"

            def _create_transport(self):
                pass

            async def chat(self, messages, model, stream=False, **kwargs):
                return {}

        adapter = TestAdapter(api_key="test-key", timeout=60)
        assert adapter.api_key == "test-key"
        assert adapter.timeout == 60

    def test_adapter_is_rate_limited_initially(self):
        """Test that new adapter is not rate limited."""

        class TestAdapter(BackendAdapter):
            def default_base_url(self) -> str:
                return "https://api.example.com"

            def _create_transport(self):
                pass

            async def chat(self, messages, model, stream=False, **kwargs):
                return {}

        adapter = TestAdapter()
        assert adapter.is_rate_limited() is False

    def test_adapter_set_rate_limited(self):
        """Test setting rate limit."""

        class TestAdapter(BackendAdapter):
            def default_base_url(self) -> str:
                return "https://api.example.com"

            def _create_transport(self):
                pass

            async def chat(self, messages, model, stream=False, **kwargs):
                return {}

        adapter = TestAdapter()
        adapter.set_rate_limited(60)
        assert adapter.is_rate_limited() is True

    def test_map_model_default(self):
        """Test default model mapping is identity."""

        class TestAdapter(BackendAdapter):
            def default_base_url(self) -> str:
                return "https://api.example.com"

            def _create_transport(self):
                pass

            async def chat(self, messages, model, stream=False, **kwargs):
                return {}

        adapter = TestAdapter()
        assert adapter.map_model("gpt-4o") == "gpt-4o"


class TestBackendErrors:
    """Test backend error classes."""

    def test_backend_error_with_cause(self):
        """Test BackendError with cause exception."""
        from rihaproxy.backends.base import BackendError

        original = ValueError("original error")
        error = BackendError("Something failed", cause=original)
        assert str(error) == "Something failed"
        assert error.cause is original

    def test_provider_unavailable_error(self):
        """Test ProviderUnavailable error."""
        from rihaproxy.backends.base import ProviderUnavailable

        error = ProviderUnavailable("Service unavailable")
        assert "Service unavailable" in str(error)

    def test_model_not_found_error(self):
        """Test ModelNotFound error."""
        from rihaproxy.backends.base import ModelNotFound

        error = ModelNotFound("Model not found: unknown-model")
        assert "unknown-model" in str(error)

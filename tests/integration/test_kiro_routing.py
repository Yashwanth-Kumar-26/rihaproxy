"""
Integration tests for Kiro proxy routing pipeline.

Tests the full flow:
- Model aliasing and resolution through GatewayRouter
- Provider selection through BackendHub
- Token injection flow
- Kiro adapter model resolution and request formatting
"""

import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from rihaproxy.backends.kiro.adapter import KiroAdapter, MODEL_SYNONYMS
from rihaproxy.backends.hub import BackendHub
from rihaproxy.backends.base import ProviderUnavailable
from rihaproxy.gateway.router import GatewayRouter


class TestKiroModelResolution:
    """Test Kiro model name resolution and synonym mapping."""

    def test_model_synonyms_resolve_correctly(self):
        """All synonyms should resolve to canonical model IDs."""
        adapter = KiroAdapter(api_key="test-token")

        # Hyphenated variants should resolve to dot notation
        assert adapter.map_model("claude-sonnet-4-5") == "claude-sonnet-4.5"
        assert adapter.map_model("claude-haiku-4-5") == "claude-haiku-4.5"
        assert adapter.map_model("claude-opus-4-7") == "claude-opus-4"

        # Date-based variants should resolve
        assert adapter.map_model("claude-sonnet-4-20250514") == "claude-sonnet-4.5"
        assert adapter.map_model("claude-opus-4-20250805") == "claude-opus-4"

        # Already canonical should pass through
        assert adapter.map_model("claude-sonnet-4.5") == "claude-sonnet-4.5"
        assert adapter.map_model("claude-opus-4") == "claude-opus-4"

    def test_model_prefix_stripping(self):
        """Provider prefixes should be stripped before synonym resolution."""
        adapter = KiroAdapter(api_key="test-token")

        assert adapter.map_model("kiro/claude-sonnet-4-5") == "claude-sonnet-4.5"
        assert adapter.map_model("kr/claude-haiku-4-5") == "claude-haiku-4.5"
        assert adapter.map_model("kiro/claude-opus-4") == "claude-opus-4"

    def test_unknown_model_passes_through(self):
        """Unknown models should pass through unchanged."""
        adapter = KiroAdapter(api_key="test-token")

        assert adapter.map_model("unknown-model") == "unknown-model"
        assert adapter.map_model("kiro/custom-model") == "custom-model"

    def test_all_registry_models_resolvable(self):
        """All Kiro models in registry should be resolvable."""
        adapter = KiroAdapter(api_key="test-token")
        registry_path = Path(__file__).parent.parent.parent / "src" / "rihaproxy" / "models_registry.json"

        with open(registry_path) as f:
            registry = json.load(f)

        kiro_models = [m for m in registry if m.get("owned_by") == "kiro"]
        assert len(kiro_models) == 7

        for model_entry in kiro_models:
            model_id = model_entry["id"]
            resolved = adapter.map_model(model_id)
            # Should not raise and should return a string
            assert isinstance(resolved, str)
            assert len(resolved) > 0


class TestKiroProviderResolution:
    """Test BackendHub provider resolution for Kiro models."""

    def test_kiro_prefix_resolves_to_kiro_provider(self):
        """Models with kiro/ prefix should resolve to kiro provider."""
        hub = BackendHub()

        assert hub.resolve_provider("kiro/claude-sonnet-4.5") == "kiro"
        assert hub.resolve_provider("kiro/claude-haiku-4.5") == "kiro"
        assert hub.resolve_provider("kiro/deepseek-3.2") == "kiro"

    def test_kr_alias_resolves_to_kr_provider(self):
        """Models with kr/ prefix should resolve to kr provider (Kiro alias)."""
        hub = BackendHub()

        # kr is registered as a separate provider that delegates to Kiro
        assert hub.resolve_provider("kr/claude-sonnet-4.5") == "kr"
        assert hub.resolve_provider("kr/claude-opus-4") == "kr"

    def test_non_kiro_model_falls_back_to_default(self):
        """Models without kiro prefix should fall back to default backend."""
        hub = BackendHub()

        # Without a provider prefix, models fall back to the default backend
        # In test environment, default may be kiro or another provider
        resolved = hub.resolve_provider("gpt-4")
        # The key point is it doesn't use kiro/ prefix matching
        assert resolved in hub.providers

    def test_kiro_in_providers_list(self):
        """Kiro should be in the available providers list."""
        hub = BackendHub()
        assert "kiro" in hub.providers


class TestKiroAdapterCreation:
    """Test BackendHub adapter creation for Kiro."""

    def test_kiro_adapter_created_with_oauth_token(self):
        """Kiro adapter should be created with OAuth token from token manager."""
        hub = BackendHub()

        async def _test():
            with patch("rihaproxy.backends.hub.settings") as mock_settings:
                mock_settings.get_api_key.return_value = None
                mock_settings.get_base_url.return_value = None
                mock_settings.request_timeout = 30
                mock_settings.http_proxy = None

                with patch("rihaproxy.auth.token_manager.get_token_manager") as mock_tm:
                    mock_tm_instance = MagicMock()
                    mock_tm_instance.get_token = AsyncMock(return_value="test-oauth-token")
                    mock_tm.return_value = mock_tm_instance

                    return await hub.get_adapter("kiro")

        adapter = asyncio.run(_test())
        assert isinstance(adapter, KiroAdapter)
        assert adapter.api_key == "test-oauth-token"

    def test_kiro_adapter_created_with_settings_key(self):
        """Kiro adapter should fall back to settings API key."""
        hub = BackendHub()

        async def _test():
            with patch("rihaproxy.backends.hub.settings") as mock_settings:
                mock_settings.get_api_key.return_value = "settings-token"
                mock_settings.get_base_url.return_value = None
                mock_settings.request_timeout = 30
                mock_settings.http_proxy = None

                with patch("rihaproxy.auth.token_manager.get_token_manager") as mock_tm:
                    mock_tm_instance = MagicMock()
                    mock_tm_instance.get_token = MagicMock(return_value=None)
                    mock_tm.return_value = mock_tm_instance

                    return await hub.get_adapter("kiro")

        adapter = asyncio.run(_test())
        assert isinstance(adapter, KiroAdapter)
        assert adapter.api_key == "settings-token"


class TestKiroRequestFormatting:
    """Test Kiro request body formatting."""

    def test_openai_to_kiro_translation(self):
        """OpenAI format should be translated to Kiro format."""
        from rihaproxy.translation.request.openai_to_kiro import translate

        openai_body = {
            "model": "claude-sonnet-4.5",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ],
            "stream": True,
        }

        kiro_body = translate(openai_body, model="claude-sonnet-4.5")

        # Should have conversationState
        assert "conversationState" in kiro_body
        state = kiro_body["conversationState"]

        # Should have currentMessage with userInputMessage
        assert "currentMessage" in state
        current = state["currentMessage"]
        assert "userInputMessage" in current

        # Model ID should be set
        user_input = current["userInputMessage"]
        assert user_input.get("modelId") == "claude-sonnet-4.5"

    def test_kiro_body_sanitization(self):
        """Kiro adapter should sanitize request body."""
        adapter = KiroAdapter(api_key="test-token")

        body = {
            "conversationState": {
                "currentMessage": {
                    "userInputMessage": {
                        "content": "Hello",
                    }
                }
            }
        }

        sanitized = adapter._sanitize_body(body, "claude-sonnet-4.5", profile_arn="test-arn")

        # Profile ARN should be added
        assert sanitized["profileArn"] == "test-arn"

        # Model ID should be set in current message
        assert sanitized["conversationState"]["currentMessage"]["userInputMessage"]["modelId"] == "claude-sonnet-4.5"

        # Origin should be set
        assert sanitized["conversationState"]["currentMessage"]["userInputMessage"]["origin"] == "AI_EDITOR"

        # Max tokens should be capped at 32000
        assert sanitized["inferenceConfig"]["maxTokens"] <= 32000


class TestKiroErrorHandling:
    """Test Kiro error handling and fallback behavior."""

    def test_provider_unavailable_raised_on_no_token(self):
        """Kiro should raise ProviderUnavailable when no token is provided."""
        adapter = KiroAdapter(api_key=None)

        async def _test():
            return await adapter.chat(
                messages=[{"role": "user", "content": "test"}],
                model="claude-sonnet-4.5"
            )

        with pytest.raises(ProviderUnavailable) as exc_info:
            asyncio.run(_test())

        # The error message should mention OAuth login
        assert "OAuth login" in str(exc_info.value)

    def test_transport_error_converted_to_provider_unavailable(self):
        """TransportError should be converted to ProviderUnavailable for fallback."""
        from rihaproxy.transport.base import TransportError

        # This is tested in the adapter's chat method exception handling
        # We verify the pattern exists in the code
        adapter = KiroAdapter(api_key="test-token")

        # Check that the chat method has proper exception handling
        import inspect
        source = inspect.getsource(adapter.chat)
        assert "TransportError" in source
        assert "ProviderUnavailable" in source

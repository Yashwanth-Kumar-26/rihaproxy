"""
Unit tests for gateway authentication.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from rihaproxy.gateway.auth import (
    AuthResult,
    RequireAuth,
    extract_bearer_token,
    extract_direct_token,
    get_auth,
    validate_token,
)


class TestExtractBearerToken:
    """Test Bearer token extraction from headers."""

    def test_valid_bearer_token(self):
        """Test extraction of valid Bearer token."""
        request = MagicMock()
        request.headers = {"authorization": "Bearer sk-or-v2-test123"}
        request.query_params = MagicMock()

        token = extract_bearer_token(request)
        assert token == "sk-or-v2-test123"

    def test_case_insensitive_bearer(self):
        """Test that Bearer is case-insensitive."""
        request = MagicMock()
        request.headers = {"authorization": "bearer test-token"}
        request.query_params = MagicMock()

        token = extract_bearer_token(request)
        assert token == "test-token"

    def test_no_authorization_header(self):
        """Test when no Authorization header present."""
        request = MagicMock()
        request.headers = {}
        request.query_params = MagicMock()

        token = extract_bearer_token(request)
        assert token is None

    def test_non_bearer_authorization(self):
        """Test when Authorization header doesn't start with Bearer."""
        request = MagicMock()
        request.headers = {"authorization": "Basic dXNlcjpwYXNz"}
        request.query_params = MagicMock()

        token = extract_bearer_token(request)
        assert token is None


class TestExtractDirectToken:
    """Test X-API-Key header extraction."""

    def test_x_api_key_header(self):
        """Test extraction from X-API-Key header."""
        request = MagicMock()
        request.headers = {"x-api-key": "direct-key-123"}
        request.query_params = MagicMock()

        token = extract_direct_token(request)
        assert token == "direct-key-123"

    def test_query_param_fallback(self):
        """Test query parameter as fallback."""
        request = MagicMock()
        request.headers = {}
        request.query_params.get.return_value = "query-key-456"

        token = extract_direct_token(request)
        assert token == "query-key-456"

    def test_header_priority(self):
        """Test that header takes priority over query param."""
        request = MagicMock()
        request.headers = {"x-api-key": "header-key"}
        request.query_params.get.return_value = "query-key"

        token = extract_direct_token(request)
        assert token == "header-key"

    def test_anthropic_auth_token_header(self):
        """Test extraction from Claude/Anthropic token headers."""
        request = MagicMock()
        request.headers = {"anthropic-auth-token": '"claude-code-token"'}
        request.query_params = MagicMock()

        token = extract_direct_token(request)
        assert token == "claude-code-token"

    def test_raw_authorization_token(self):
        """Test raw Authorization token fallback."""
        request = MagicMock()
        request.headers = {"authorization": "'raw-token'"}
        request.query_params = MagicMock()

        token = extract_direct_token(request)
        assert token == "raw-token"

    def test_auth_token_query_param(self):
        """Test auth_token query parameter fallback."""
        request = MagicMock()
        request.headers = {}
        request.query_params.get.side_effect = lambda key: "query-auth-token" if key == "auth_token" else None

        token = extract_direct_token(request)
        assert token == "query-auth-token"


class TestValidateToken:
    """Test token validation logic."""

    @patch("rihaproxy.gateway.auth.settings")
    def test_valid_auth_token(self, mock_settings):
        """Test validation of configured AUTH_TOKEN."""
        mock_settings.auth_token = "my-auth-token"
        mock_settings.anthropic_auth_token = ""
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token("my-auth-token")
        assert result.valid is True
        assert result.source == "auth_token"

    @patch("rihaproxy.gateway.auth.settings")
    def test_valid_auth_token_with_quotes(self, mock_settings):
        """Test validation strips shell-style quotes from configured token input."""
        mock_settings.auth_token = "my-auth-token"
        mock_settings.anthropic_auth_token = ""
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token('"my-auth-token"')
        assert result.valid is True
        assert result.source == "auth_token"

    @patch("rihaproxy.gateway.auth.settings")
    def test_valid_anthropic_auth_token(self, mock_settings):
        """Test validation of Anthropic-specific token."""
        mock_settings.auth_token = ""
        mock_settings.anthropic_auth_token = "ant-token"
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token("ant-token")
        assert result.valid is True
        assert result.source == "anthropic_auth_token"

    @patch("rihaproxy.gateway.auth.settings")
    def test_provider_api_key(self, mock_settings):
        """Test validation of provider API keys."""
        mock_settings.auth_token = ""
        mock_settings.anthropic_auth_token = ""
        mock_settings.openai_api_key = "sk-pro-xxx"
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token("sk-pro-xxx")
        assert result.valid is True
        assert result.source == "provider_key"

    @patch("rihaproxy.gateway.auth.settings")
    def test_passthrough_mode(self, mock_settings):
        """Test passthrough mode when no AUTH_TOKEN configured."""
        mock_settings.auth_token = ""
        mock_settings.anthropic_auth_token = ""
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token("any-valid-key")
        assert result.valid is True
        assert result.source == "passthrough"

    @patch("rihaproxy.gateway.auth.settings")
    def test_invalid_token(self, mock_settings):
        """Test invalid token rejection."""
        mock_settings.auth_token = "real-token"
        mock_settings.anthropic_auth_token = ""
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.deepseek_api_key = ""
        mock_settings.nvidia_api_key = ""
        mock_settings.google_api_key = ""
        mock_settings.opencode_api_key = ""

        result = validate_token("wrong-token")
        assert result.valid is False

    def test_none_token(self):
        """Test validation of None token."""
        result = validate_token(None)
        assert result.valid is False


class TestAuthResult:
    """Test AuthResult class."""

    def test_auth_result_creation(self):
        """Test AuthResult object creation."""
        result = AuthResult("token123", source="test", valid=True)
        assert result.token == "token123"
        assert result.source == "test"
        assert result.valid is True

    def test_auth_result_defaults(self):
        """Test AuthResult default values."""
        result = AuthResult(None)
        assert result.token is None
        assert result.source == "unknown"
        assert result.valid is False


class TestGetAuth:
    """Test the FastAPI dependency for authentication."""

    @pytest.mark.asyncio
    @patch("rihaproxy.gateway.auth.settings")
    async def test_successful_bearer_auth(self, mock_settings):
        """Test successful authentication via Bearer token."""
        mock_settings.auth_token = "valid-token"
        mock_settings.anthropic_auth_token = ""

        request = MagicMock()
        request.headers = {"authorization": "Bearer valid-token"}
        request.query_params = MagicMock()

        result = await get_auth(bearer=None, request=request)
        assert result.valid is True

    @pytest.mark.asyncio
    @patch("rihaproxy.gateway.auth.settings")
    async def test_successful_api_key_auth(self, mock_settings):
        """Test successful authentication via X-API-Key."""
        mock_settings.auth_token = ""  # No gateway auth token set
        mock_settings.openai_api_key = "provider-key"

        request = MagicMock()
        request.headers = {"x-api-key": "provider-key"}
        request.query_params = MagicMock()

        result = await get_auth(bearer=None, request=request)
        assert result.valid is True

    @pytest.mark.asyncio
    @patch("rihaproxy.gateway.auth.settings")
    async def test_no_auth_required(self, mock_settings):
        """Test when no auth token is configured."""
        mock_settings.auth_token = ""

        request = MagicMock()
        request.headers = {}
        request.query_params = MagicMock()
        request.query_params.get.return_value = None  # Return None for unset query params

        result = await get_auth(bearer=None, request=request)
        assert result.valid is True
        assert result.source == "none"

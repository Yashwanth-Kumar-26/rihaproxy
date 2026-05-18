"""
Unit tests for HTTP transport layer.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rihaproxy.transport.base import (
    AuthError,
    BaseTransport,
    RateLimitError,
    TimeoutError,
    TransportError,
)


class TestTransportErrors:
    """Test transport error classes."""

    def test_transport_error(self):
        """Test TransportError creation."""
        error = TransportError("Connection failed")
        assert str(error) == "Connection failed"

    def test_auth_error(self):
        """Test AuthError creation."""
        error = AuthError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, TransportError)

    def test_rate_limit_error(self):
        """Test RateLimitError creation."""
        error = RateLimitError("Rate limited")
        assert str(error) == "Rate limited"
        assert isinstance(error, TransportError)

    def test_timeout_error(self):
        """Test TimeoutError creation."""
        error = TimeoutError("Request timed out")
        assert str(error) == "Request timed out"
        assert isinstance(error, TransportError)

    def test_error_inheritance(self):
        """Test error class hierarchy."""
        errors = [TransportError, AuthError, RateLimitError, TimeoutError]
        for error in errors:
            assert issubclass(error, Exception)


class TestBaseTransport:
    """Test BaseTransport abstract class."""

    def test_base_url_stripping(self):
        """Test that base URL trailing slash is stripped."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com/")
        assert transport.base_url == "https://api.example.com"

        transport2 = TestTransport(base_url="https://api.example.com")
        assert transport2.base_url == "https://api.example.com"

    def test_headers_without_api_key(self):
        """Test headers generation without API key."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com")
        headers = transport._headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """Test headers generation with API key."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(
            base_url="https://api.example.com",
            api_key="sk-test-key",
        )
        headers = transport._headers()
        assert headers["Authorization"] == "Bearer sk-test-key"

    def test_headers_with_extra(self):
        """Test headers with extra headers."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com")
        headers = transport._headers({"X-Custom-Header": "value"})
        assert headers["X-Custom-Header"] == "value"

    def test_client_kwargs_timeout(self):
        """Test client kwargs include timeout."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com", timeout=60)
        kwargs = transport._client_kwargs()
        assert kwargs["timeout"] == 60

    def test_client_kwargs_with_proxy(self):
        """Test client kwargs include proxy."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(
            base_url="https://api.example.com",
            proxy="http://proxy:8080",
        )
        kwargs = transport._client_kwargs()
        assert kwargs["proxy"] == "http://proxy:8080"

    def test_close_method_exists(self):
        """Test that close method exists and can be called."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com")
        # Should not raise
        import asyncio
        asyncio.run(transport.close())


class TestChatCompletionsTransport:
    """Test ChatCompletionsTransport."""

    @pytest.fixture
    def transport(self):
        """Create ChatCompletionsTransport instance."""
        from rihaproxy.transport.chat_completions import ChatCompletionsTransport

        return ChatCompletionsTransport(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            timeout=60,
        )

    def test_post_method(self, transport):
        """Test post method exists."""
        assert hasattr(transport, "post")
        assert callable(transport.post)


class TestTransportEdgeCases:
    """Edge case tests for transport."""

    def test_empty_api_key(self):
        """Test transport with empty API key."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com", api_key="")
        headers = transport._headers()
        # Empty API key should not add Authorization header
        assert "Authorization" not in headers

    def test_none_proxy(self):
        """Test transport with None proxy."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com", proxy=None)
        kwargs = transport._client_kwargs()
        assert "proxy" not in kwargs

    def test_custom_timeout(self):
        """Test custom timeout values."""

        class TestTransport(BaseTransport):
            async def request(self, method, path, body=None, stream=False, **kwargs):
                return {}

        transport = TestTransport(base_url="https://api.example.com", timeout=300)
        kwargs = transport._client_kwargs()
        assert kwargs["timeout"] == 300
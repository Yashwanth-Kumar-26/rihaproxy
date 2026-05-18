"""
Base class for all provider adapters.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

import structlog

from rihaproxy.transport.base import (
    AuthError,
    BaseTransport,
    RateLimitError,
    TimeoutError,
    TransportError,
)

logger = structlog.get_logger()


class BackendError(Exception):
    """Generic backend error."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class ProviderUnavailable(BackendError):
    """Provider is unavailable (rate limited, invalid creds, etc.)."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, cause=cause)


class ProviderError(BackendError):
    """Provider-side error that can be retried with different credentials."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, cause=cause)


class ModelNotFound(BackendError):
    """Model not found or not available."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, cause=cause)


class BackendAdapter(ABC):
    """
    Abstract base for provider adapters.

    Each adapter knows:
    - How to map model names to provider-specific format
    - Which transport protocol to use
    - How to handle provider-specific errors
    """

    provider_name: str = "unknown"
    supports_streaming: bool = True
    supports_tools: bool = False

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
        proxy: str | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url or self.default_base_url()
        self.timeout = timeout
        self.proxy = proxy
        self._transport = self._create_transport()
        self._request_count = 0
        self._last_error: str | None = None
        self._rate_limited_until: float = 0.0

    @abstractmethod
    def default_base_url(self) -> str:
        """Return the default base URL for this provider."""
        ...

    @abstractmethod
    def _create_transport(self) -> BaseTransport:
        """Create the appropriate transport for this provider."""
        ...

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            headers.update(extra)
        return headers

    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        return time.time() < self._rate_limited_until

    def set_rate_limited(self, seconds: int) -> None:
        """Set rate limit cooldown."""
        self._rate_limited_until = time.time() + seconds

    def map_model(self, model: str) -> str:
        """
        Map a generic model name to provider-specific model name.
        Override in subclasses for provider-specific mapping.
        """
        return model

    def handle_error(self, error: Exception) -> BackendError:
        """
        Convert transport errors to backend errors.
        Override for provider-specific error handling.
        """
        if isinstance(error, AuthError):
            self._last_error = "Authentication failed"
            return ProviderUnavailable("Authentication failed", cause=error)
        if isinstance(error, RateLimitError):
            self._last_error = "Rate limited"
            self.set_rate_limited(60)
            return ProviderUnavailable("Rate limited", cause=error)
        if isinstance(error, TimeoutError):
            self._last_error = "Request timed out"
            return ProviderError("Request timed out", cause=error)
        if isinstance(error, TransportError):
            self._last_error = str(error)
            return BackendError(str(error), cause=error)
        return BackendError(str(error), cause=error)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """
        Send a chat request to the provider.
        Override in subclasses or use the transport directly.
        """
        raise NotImplementedError("Subclass must implement chat() or use a transport mixin")

    async def close(self) -> None:
        """Clean up resources."""
        await self._transport.close()

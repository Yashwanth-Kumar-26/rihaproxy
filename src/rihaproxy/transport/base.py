"""
HTTP transport protocols for provider communication.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

import httpx


class TransportError(Exception):
    """Raised when a transport operation fails."""
    pass


class RateLimitError(TransportError):
    """Raised on rate limit (429)."""
    pass


class AuthError(TransportError):
    """Raised on auth failure (401/403)."""
    pass


class TimeoutError(TransportError):
    """Raised on timeout."""
    pass


class BaseTransport(ABC):
    """Abstract base for HTTP transports."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 120,
        proxy: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.proxy = proxy

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            headers.update(extra)
        return headers

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    @abstractmethod
    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        ...

    async def close(self) -> None:
        """Clean up transport resources."""
        pass
"""
Anthropic /messages protocol transport.
Uses the native Anthropic SSE streaming format.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from rihaproxy.transport.base import (
    AuthError,
    BaseTransport,
    RateLimitError,
    TimeoutError,
    TransportError,
)


class MessagesTransport(BaseTransport):
    """
    Transport for Anthropic /v1/messages endpoint.

    Protocol:
    - POST /v1/messages with JSON body
    - Response: streaming SSE with event types:
      - message_start, content_block_start, content_block_delta,
      - content_block_stop, message_delta, message_stop
    """

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        stream: bool = False,
        extra_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        url = f"{self.base_url}{path}"
        headers = self._headers(extra_headers)
        headers["anthropic-version"] = "2023-06-01"
        headers["Accept"] = "text/event-stream" if stream else "application/json"

        if stream:
            return self._stream_request(url, body, headers, **kwargs)
        else:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                try:
                    response = await client.post(
                        url,
                        json=body,
                        headers=headers,
                        **kwargs,
                    )

                    status = response.status_code

                    if status == 400:
                        raise TransportError(f"Bad request (400): {response.text[:500]}")
                    if status == 401 or status == 403:
                        raise AuthError(f"Authentication failed: {response.text}")
                    if status == 429:
                        retry_after = response.headers.get("retry-after", "60")
                        raise RateLimitError(f"Rate limited, retry after {retry_after}s")
                    if status >= 500:
                        raise TransportError(f"Provider error {status}: {response.text[:200]}")

                    response.raise_for_status()
                    return response.json()

                except httpx.TimeoutException as e:
                    raise TimeoutError(f"Request timed out after {self.timeout}s") from e
                except httpx.HTTPStatusError as e:
                    raise TransportError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e

    async def _stream_request(
        self,
        url: str,
        body: dict[str, Any] | None,
        headers: dict[str, str],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream request — keeps connection open during iteration."""
        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            try:
                async with client.stream("POST", url, json=body, headers=headers, **kwargs) as response:
                    status = response.status_code
                    if status == 400:
                        error_body = await response.aread()
                        raise TransportError(f"Bad request (400): {error_body.decode()[:500]}")
                    if status == 401 or status == 403:
                        error_body = await response.aread()
                        raise AuthError(f"Authentication failed: {error_body.decode()[:200]}")
                    if status == 429:
                        retry_after = response.headers.get("retry-after", "60")
                        raise RateLimitError(f"Rate limited, retry after {retry_after}s")
                    if status >= 500:
                        error_body = await response.aread()
                        raise TransportError(f"Provider error {status}: {error_body.decode()[:200]}")

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            yield line[6:]
            except httpx.TimeoutException as e:
                raise TimeoutError(f"Streaming timed out after {self.timeout}s") from e

    async def _parse_sse(self, lines: AsyncIterator[str]) -> AsyncIterator[str]:
        """Parse SSE stream lines into event data."""
        async for line in lines:
            line = line.strip()
            if line.startswith("data: "):
                yield line[6:]  # strip "data: "

    async def post(
        self,
        path: str = "/v1/messages",
        body: dict[str, Any] | None = None,
        stream: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """POST to the messages endpoint."""
        return await self.request("POST", path, body, stream, extra_headers)
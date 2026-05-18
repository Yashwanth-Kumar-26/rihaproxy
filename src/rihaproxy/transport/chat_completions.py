"""
OpenAI /chat/completions protocol transport.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from rihaproxy.transport.base import (
    AuthError,
    BaseTransport,
    RateLimitError,
    TimeoutError,
    TransportError,
)


class ChatCompletionsTransport(BaseTransport):
    """
    Transport for OpenAI /v1/chat/completions endpoint.

    Protocol:
    - POST /v1/chat/completions with JSON body
    - Streaming: SSE with delta format
    - Non-streaming: JSON response
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
        headers["Accept"] = "text/event-stream" if stream else "application/json"

        if stream:
            # For streaming: keep connection alive by using a persistent client
            # and yielding inside the context manager
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
                            data = line[6:]
                            if data == "[DONE]":
                                return
                            yield data
            except httpx.TimeoutException as e:
                raise TimeoutError(f"Streaming timed out after {self.timeout}s") from e

    async def _parse_sse(self, lines: AsyncIterator[str]) -> AsyncIterator[str]:
        """Parse SSE stream lines."""
        async for line in lines:
            line = line.strip()
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                yield data

    async def post(
        self,
        path: str = "/v1/chat/completions",
        body: dict[str, Any] | None = None,
        stream: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """POST to the chat completions endpoint."""
        return await self.request("POST", path, body, stream, extra_headers)
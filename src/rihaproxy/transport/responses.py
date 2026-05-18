"""
OpenAI /responses API transport.
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


class ResponsesTransport(BaseTransport):
    """
    Transport for OpenAI /v1/responses endpoint.

    Protocol:
    - POST /v1/responses with JSON body
    - Streaming: SSE with response_created, content_chunk, done events
    - Non-streaming: JSON response object
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
        headers["OpenAI-Beta"] = "assistants=v2"
        headers["Accept"] = "text/event-stream" if stream else "application/json"

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            try:
                response = await client.post(
                    url,
                    json=body,
                    headers=headers,
                    **kwargs,
                )

                status = response.status_code

                if status == 401 or status == 403:
                    raise AuthError(f"Authentication failed: {response.text}")
                if status == 429:
                    retry_after = response.headers.get("retry-after", "60")
                    raise RateLimitError(f"Rate limited, retry after {retry_after}s")
                if status == 500 or status == 502 or status == 503:
                    raise TransportError(f"Provider error {status}: {response.text[:200]}")

                response.raise_for_status()

                if stream:
                    return self._parse_sse(response.aiter_lines())
                else:
                    return response.json()

            except httpx.TimeoutException as e:
                raise TimeoutError(f"Request timed out after {self.timeout}s") from e
            except httpx.HTTPStatusError as e:
                raise TransportError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e

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
        path: str = "/v1/responses",
        body: dict[str, Any] | None = None,
        stream: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """POST to the responses endpoint."""
        return await self.request("POST", path, body, stream, extra_headers)
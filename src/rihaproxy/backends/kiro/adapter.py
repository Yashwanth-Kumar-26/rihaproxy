"""
Kiro AI adapter.

Kiro uses AWS CodeWhisperer GenerateAssistantResponse and returns AWS
EventStream binary frames. The adapter converts those frames into OpenAI-style
stream chunks so the gateway can convert them back to Anthropic SSE for Claude
Code.

Features from 9router integration:
- Profile ARN support for AWS CodeWhisperer
- Token validation before use
- Usage limits tracking
- Model synonyms/aliases
- Improved error handling with specific error types
"""

from __future__ import annotations

import asyncio
import json
import struct
import time
import uuid
import zlib
from typing import Any, AsyncIterator

import httpx
import structlog

from rihaproxy.backends.base import BackendAdapter, ProviderUnavailable
from rihaproxy.storage.db import get_storage
from rihaproxy.transport.base import BaseTransport, TransportError
from rihaproxy.translation.request.openai_to_kiro import translate as openai_to_kiro

logger = structlog.get_logger()

# Kiro OAuth configuration (from 9router)
KIRO_CONFIG = {
    "authService": "https://prod.us-east-1.auth.desktop.kiro.dev",
    "tokenUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token",
    "refreshUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"],
    "defaultProfileArn": "arn:aws:codewhisperer:us-east-1:638616132270:profile/AAAACCCCXXXX",
}

# Model synonyms (from 9router) — use dot notation Kiro expects
MODEL_SYNONYMS = {
    "claude-sonnet-4.5": "claude-sonnet-4.5",
    "claude-sonnet-4-5": "claude-sonnet-4.5",
    "claude-sonnet-4-20250514": "claude-sonnet-4.5",
    "claude-sonnet-4-20250805": "claude-sonnet-4.5",
    "claude-opus-4": "claude-opus-4",
    "claude-opus-4-20250805": "claude-opus-4",
    "claude-opus-4-7": "claude-opus-4",
    "claude-haiku-4.5": "claude-haiku-4.5",
    "claude-haiku-4-5": "claude-haiku-4.5",
    "claude-haiku-4-5-20250805": "claude-haiku-4.5",
}


class _NoopTransport(BaseTransport):
    async def request(self, method: str, path: str, body=None, stream=False, **kwargs):
        return {}


class KiroAdapter(BackendAdapter):
    provider_name = "kiro"
    provider_aliases = ["kr"]
    supports_streaming = True
    supports_tools = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._storage = None

    @property
    def storage(self):
        """Lazy-load storage instance."""
        if self._storage is None:
            self._storage = get_storage()
        return self._storage

    def default_base_url(self) -> str:
        return "https://codewhisperer.us-east-1.amazonaws.com"

    def _create_transport(self) -> BaseTransport:
        return _NoopTransport(self.base_url, self.api_key, self.timeout, self.proxy)

    def map_model(self, model: str) -> str:
        """Map model name with synonym support (from 9router)."""
        if model.startswith("kiro/"):
            model = model.split("/", 1)[1]
        if model.startswith("kr/"):
            model = model.split("/", 1)[1]
        # Resolve synonyms
        return MODEL_SYNONYMS.get(model.lower(), model)

    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate Kiro OAuth token by listing available models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://codewhisperer.us-east-1.amazonaws.com",
                    json={
                        "origin": "AI_EDITOR",
                        "profileArn": KIRO_CONFIG["defaultProfileArn"],
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/x-amz-json-1.0",
                        "x-amz-target": "AmazonCodeWhispererService.ListAvailableModels",
                        "Accept": "application/json",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return {"valid": True, "profileArn": KIRO_CONFIG["defaultProfileArn"], "models": models}
                elif response.status_code == 401:
                    return {"valid": False, "error": "Token expired or invalid"}
                else:
                    return {"valid": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def refresh_token(self, refresh_token: str, provider_data: dict | None = None) -> dict[str, Any] | None:
        """Refresh Kiro OAuth token using provider-aware routing."""
        try:
            from rihaproxy.auth.oauth import refresh_provider_token
            result = await refresh_provider_token("kiro", refresh_token, provider_data=provider_data)
            return {
                "accessToken": result.get("access_token"),
                "refreshToken": result.get("refresh_token", refresh_token),
                "expiresIn": result.get("expires_in", 3600),
            }
        except Exception:
            return None

    async def get_usage_limits(self, token: str, profile_arn: str | None = None) -> dict[str, Any]:
        """Fetch usage limits from CodeWhisperer API (from 9router)."""
        try:
            params = {"profileArn": profile_arn or KIRO_CONFIG["defaultProfileArn"]}
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://codewhisperer.us-east-1.amazonaws.com/getUsageLimits",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status_code == 200:
                    return response.json()
                return {}
        except Exception:
            return {}

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/vnd.amazon.eventstream",
            "X-Amz-Target": "AmazonCodeWhispererStreamingService.GenerateAssistantResponse",
            "User-Agent": "AWS-SDK-JS/3.0.0 kiro-ide/1.0.0",
            "X-Amz-User-Agent": "aws-sdk-js/3.0.0 kiro-ide/1.0.0",
            "Amz-Sdk-Request": "attempt=1; max=3",
            "Amz-Sdk-Invocation-Id": str(uuid.uuid4()),
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            headers.update(extra)
        return headers

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        if not self.api_key:
            raise ProviderUnavailable("Kiro requires OAuth login. Run: rihaproxy login kiro")

        # Validate token before use
        validation = await self.validate_token(self.api_key)
        if validation and not validation.get("valid"):
            # Try to refresh token if we have a refresh token
            try:
                from rihaproxy.auth.token_manager import get_token_manager
                tm = get_token_manager()
                connections = await tm.get_active_connections("kiro")
                for conn in connections:
                    refresh_token = conn.get("refresh_token")
                    if refresh_token:
                        new_tokens = await self.refresh_token(refresh_token)
                        if new_tokens:
                            # Update connection with new tokens
                            self.storage.update_provider_connection(conn["id"], {
                                "access_token": new_tokens.get("accessToken"),
                                "refresh_token": new_tokens.get("refreshToken", refresh_token),
                                "expires_at": str(time.time() + new_tokens.get("expiresIn", 3600)),
                            })
                            self.api_key = new_tokens.get("accessToken")
                            validation = await self.validate_token(self.api_key)
                            break
            except Exception:
                pass

            if not validation or not validation.get("valid"):
                raise ProviderUnavailable(f"Kiro token invalid: {validation.get('error', 'unknown')}")

        # Get profile ARN from validation or use default
        profile_arn = validation.get("profileArn") if validation else None

        mapped_model = self.map_model(model)
        body = {
            key: value
            for key, value in kwargs.items()
            if key not in {"tools", "tool_choice", "stop"}
        }
        if "conversationState" not in body:
            body = openai_to_kiro(
                {
                    "model": mapped_model,
                    "messages": messages,
                    "tools": kwargs.get("tools") or [],
                    "max_tokens": kwargs.get("max_tokens"),
                    "temperature": kwargs.get("temperature"),
                    "top_p": kwargs.get("top_p"),
                    "stream": stream,
                },
                model=mapped_model,
            )
        body = self._sanitize_body(body, mapped_model, profile_arn)

        try:
            if stream:
                return self._stream_chat(body, mapped_model)
            return await self._complete_chat(body, mapped_model)
        except ProviderUnavailable:
            raise
        except TransportError as e:
            # Convert transport errors to ProviderUnavailable for fallback
            raise ProviderUnavailable(f"Kiro transport error: {e}") from e
        except Exception as e:
            raise self.handle_error(e) from e

    def _sanitize_body(self, body: dict[str, Any], model: str, profile_arn: str | None = None) -> dict[str, Any]:
        """Sanitize and prepare request body with profile ARN support."""
        if profile_arn:
            body["profileArn"] = profile_arn
        elif not body.get("profileArn"):
            body.pop("profileArn", None)
        state = body.get("conversationState") or {}
        current = state.get("currentMessage", {}).get("userInputMessage", {})
        current.setdefault("modelId", model)
        current.setdefault("origin", "AI_EDITOR")
        if not current.get("content"):
            current["content"] = "continue"
        for item in state.get("history") or []:
            user_msg = item.get("userInputMessage")
            if user_msg:
                user_msg.setdefault("modelId", model)
                user_msg.setdefault("origin", "AI_EDITOR")
        inference = body.setdefault("inferenceConfig", {})
        max_tokens = inference.get("maxTokens") or 32000
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            max_tokens = 32000
        inference["maxTokens"] = min(max_tokens, 32000)
        return body

    async def _complete_chat(self, body: dict[str, Any], model: str) -> dict[str, Any]:
        text_parts: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        async for chunk in self._stream_chat(body, model):
            data = json.loads(chunk)
            for choice in data.get("choices", []):
                delta = choice.get("delta", {})
                if delta.get("content"):
                    text_parts.append(delta["content"])
            if data.get("usage"):
                usage = data["usage"]

        return {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "".join(text_parts)},
                "finish_reason": "stop",
            }],
            "usage": usage,
        }

    async def _stream_chat(self, body: dict[str, Any], model: str) -> AsyncIterator[str]:
        url = self.base_url.rstrip("/") + "/generateAssistantResponse"
        headers = self._headers()
        state = body.get("conversationState") or {}
        current = state.get("currentMessage", {}).get("userInputMessage", {})
        logger.info(
            "kiro_request",
            model=current.get("modelId") or model,
            stream=True,
            history=len(state.get("history") or []),
            tools=len((current.get("userInputMessageContext") or {}).get("tools") or []),
            tool_results=len((current.get("userInputMessageContext") or {}).get("toolResults") or []),
            max_tokens=(body.get("inferenceConfig") or {}).get("maxTokens"),
        )

        max_retries = 3
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=self.timeout, proxy=self.proxy) as client:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                        if attempt < max_retries:
                            logger.warning("kiro_rate_limited", attempt=attempt + 1, retry_after=retry_after)
                            await asyncio.sleep(retry_after)
                            continue
                        # After retry exhaustion, raise ProviderUnavailable to trigger hub fallback
                        raise ProviderUnavailable(f"Kiro rate limited after {max_retries} retries")
                    if response.status_code in (401, 403):
                        error_body = (await response.aread()).decode(errors='ignore')[:300]
                        raise ProviderUnavailable(f"Kiro authentication failed: {error_body}")
                    if response.status_code >= 500:
                        error_body = (await response.aread()).decode(errors='ignore')[:300]
                        raise ProviderUnavailable(f"Kiro server error {response.status_code}: {error_body}")
                    if response.status_code >= 400:
                        error_body = (await response.aread()).decode(errors='ignore')[:300]
                        raise TransportError(f"Kiro error {response.status_code}: {error_body}")

                    parser = _EventStreamParser()
                    stream_state = _KiroStreamState(model=model)
                    async for raw in response.aiter_bytes():
                        for event in parser.feed(raw):
                            for chunk in stream_state.consume(event):
                                yield json.dumps(chunk)
                    for chunk in stream_state.finish():
                        yield json.dumps(chunk)

                    # Track usage after successful stream
                    if stream_state.usage:
                        logger.info(
                            "kiro_usage",
                            model=model,
                            prompt_tokens=stream_state.usage.get("prompt_tokens", 0),
                            completion_tokens=stream_state.usage.get("completion_tokens", 0),
                            total_tokens=stream_state.usage.get("total_tokens", 0),
                        )
                    return


class _EventStreamParser:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        events: list[dict[str, Any]] = []
        while len(self._buffer) >= 16:
            total_len = struct.unpack(">I", self._buffer[:4])[0]
            if total_len < 16 or len(self._buffer) < total_len:
                break
            frame = bytes(self._buffer[:total_len])
            del self._buffer[:total_len]
            parsed = self._parse_frame(frame)
            if parsed:
                events.append(parsed)
        return events

    def _parse_frame(self, frame: bytes) -> dict[str, Any] | None:
        try:
            total_len, headers_len = struct.unpack(">II", frame[:8])
            if total_len != len(frame):
                return None
            # CRC validation is best-effort; skip bad frames instead of failing
            expected_crc = struct.unpack(">I", frame[-4:])[0]
            if zlib.crc32(frame[:-4]) & 0xFFFFFFFF != expected_crc:
                logger.debug("kiro_event_crc_mismatch")
            headers = self._parse_headers(frame[12:12 + headers_len])
            payload_bytes = frame[12 + headers_len:-4]
            payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
            return {"headers": headers, "payload": payload}
        except Exception:
            return None

    def _parse_headers(self, data: bytes) -> dict[str, Any]:
        headers: dict[str, Any] = {}
        pos = 0
        while pos < len(data):
            name_len = data[pos]
            pos += 1
            name = data[pos:pos + name_len].decode("utf-8")
            pos += name_len
            htype = data[pos]
            pos += 1
            if htype == 7:
                value_len = struct.unpack(">H", data[pos:pos + 2])[0]
                pos += 2
                value = data[pos:pos + value_len].decode("utf-8")
                pos += value_len
            elif htype == 6:
                value = struct.unpack(">q", data[pos:pos + 8])[0]
                pos += 8
            elif htype == 4:
                value = struct.unpack(">i", data[pos:pos + 4])[0]
                pos += 4
            else:
                break
            headers[name] = value
        return headers


class _KiroStreamState:
    def __init__(self, model: str) -> None:
        self.model = model
        self.response_id = f"chatcmpl-{int(time.time() * 1000)}"
        self.created = int(time.time())
        self.chunk_index = 0
        self.has_tool_calls = False
        self.finish_emitted = False
        self.usage: dict[str, int] | None = None

    def _chunk(self, delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
        if self.chunk_index == 0 and "role" not in delta:
            delta = {"role": "assistant", **delta}
        self.chunk_index += 1
        return {
            "id": self.response_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    def consume(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        etype = event["headers"].get(":event-type") or event["headers"].get("event-type") or ""
        payload = event.get("payload") or {}
        chunks: list[dict[str, Any]] = []

        if etype == "assistantResponseEvent" and payload.get("content"):
            chunks.append(self._chunk({"content": payload["content"]}))
        elif etype == "codeEvent" and payload.get("content"):
            chunks.append(self._chunk({"content": payload["content"]}))
        elif etype == "reasoningContentEvent":
            reasoning = payload.get("reasoningContentEvent") or payload
            text = reasoning if isinstance(reasoning, str) else reasoning.get("text") or reasoning.get("content")
            if text:
                chunks.append(self._chunk({"reasoning_content": text}))
        elif etype == "toolUseEvent":
            self.has_tool_calls = True
            tool_id = payload.get("toolUseId") or f"call_{uuid.uuid4().hex[:12]}"
            chunks.append(self._chunk({
                "tool_calls": [{
                    "index": 0,
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": payload.get("name", ""),
                        "arguments": json.dumps(payload.get("input") or {}),
                    },
                }]
            }))
        elif etype == "metricsEvent":
            metrics = payload.get("metricsEvent") or payload
            prompt = int(metrics.get("inputTokens") or 0)
            completion = int(metrics.get("outputTokens") or 0)
            self.usage = {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            }
        elif etype == "messageStopEvent":
            chunks.extend(self.finish())

        return chunks

    def finish(self) -> list[dict[str, Any]]:
        if self.finish_emitted:
            return []
        self.finish_emitted = True
        chunk = self._chunk({}, "tool_calls" if self.has_tool_calls else "stop")
        if self.usage:
            chunk["usage"] = self.usage
        return [chunk]

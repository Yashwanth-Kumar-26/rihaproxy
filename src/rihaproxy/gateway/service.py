"""
Gateway service — orchestrates request handling.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import structlog
from sse_starlette import EventSourceResponse

from rihaproxy.backends.base import BackendError, ProviderUnavailable
from rihaproxy.config import settings
from rihaproxy.gateway.router import GatewayRouter, get_router
from rihaproxy.gateway.schemas import ChatCompletionRequest
from rihaproxy.storage.db import get_storage
from rihaproxy.translation.formats import detect_source_format
from rihaproxy.translation.index import translate_request

logger = structlog.get_logger()


class GatewayService:
    """
    High-level service for handling gateway requests.
    Handles format detection, translation, streaming, and usage logging.
    """

    def __init__(self, router: GatewayRouter | None = None):
        self.router = router or get_router()
        self.storage = get_storage()
        self._start_time = time.time()

    async def handle_chat_completions(
        self,
        body: dict[str, Any],
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """
        Handle an OpenAI chat completions request.

        Steps:
        1. Detect source format
        2. Translate to target provider format (if needed)
        3. Route to backend
        4. Translate response back (if needed)
        5. Log usage
        """
        model = body.get("model", settings.default_model)
        source_format = detect_source_format(body)

        logger.info("chat_request", model=model, source=source_format, stream=stream)

        # Translate request if needed
        target_format = self.router.hub.resolve_provider(model)
        if source_format != "openai" or target_format not in ("openai", "openrouter"):
            try:
                translated_body = translate_request(body, source_format, target_format, model=model)
            except Exception as e:
                logger.warning("translation_skipped", error=str(e))
                translated_body = body
        else:
            translated_body = body

        # Route request
        try:
            # Merge translated parameters if available
            params = {k: v for k, v in body.items() if k not in ("model", "messages", "stream")}
            if translated_body is not body:
                params.update({k: v for k, v in translated_body.items() if k not in ("model", "messages", "stream")})

            result = await self.router.route_chat(
                model=model,
                messages=translated_body.get("messages", body.get("messages")),
                stream=stream,
                **params
            )
        except Exception as e:
            logger.error("chat_request_failed", model=model, error=str(e))
            raise

        # Log usage (non-streaming only)
        if not stream and isinstance(result, dict):
            self._log_usage("chat", model, result)

        return result

    async def handle_anthropic_messages(
        self,
        body: dict[str, Any],
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[str]:
        """Handle an Anthropic /v1/messages request."""
        model = body.get("model", settings.default_model)

        logger.info("anthropic_request", model=model, stream=stream)

        # Resolve Claude Code tier aliases before selecting target format.
        resolved_model = self.router.resolve_model(model)

        # Translate to target format
        target_format = self.router.hub.resolve_provider(resolved_model)
        try:
            translated = translate_request(body, "anthropic", target_format, model=resolved_model)
        except Exception:
            translated = body

        # Route request — use ONLY translated params (not raw Anthropic body)
        try:
            # Build params from translated body only (already in OpenAI format)
            params = {k: v for k, v in translated.items()
                      if k not in ("model", "messages", "stream")}

            result = await self.router.hub.chat(
                model=resolved_model,
                messages=translated.get("messages", body.get("messages")),
                stream=stream,
                **params
            )
        except Exception as e:
            logger.error("anthropic_request_failed", model=model, error=str(e))
            raise

        # Convert OpenAI response → Anthropic format for the client
        if stream:
            # result is an AsyncIterator of OpenAI SSE JSON strings
            return self._openai_stream_to_anthropic(result, resolved_model)
        else:
            # result is a dict in OpenAI format — convert to Anthropic format
            if isinstance(result, dict):
                converted = self._openai_response_to_anthropic(result, model)
                self._log_usage("anthropic", model, result)
                return converted
            return result

    async def _openai_stream_to_anthropic(
        self,
        openai_stream: AsyncIterator[str],
        model: str,
    ) -> AsyncIterator[str]:
        """Convert OpenAI SSE stream to Anthropic SSE format."""
        import uuid
        import json as _json

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        input_tokens = 0
        output_tokens = 0
        sent_start = False
        sent_block_start = False
        block_index = 0

        try:
            async for chunk_str in openai_stream:
                try:
                    data = _json.loads(chunk_str)
                except Exception:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    # May contain usage info
                    usage = data.get("usage", {})
                    if usage:
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", output_tokens)
                    continue

                delta = choices[0].get("delta", {})
                finish_reason = choices[0].get("finish_reason")

                # Emit message_start on first chunk
                if not sent_start:
                    sent_start = True
                    yield f'event: message_start\ndata: {_json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": input_tokens, "output_tokens": 1}}})}\n\n'

                # Handle text content
                content = delta.get("content", "") or delta.get("reasoning_content", "")
                if content:
                    if not sent_block_start:
                        sent_block_start = True
                        yield f'event: content_block_start\ndata: {_json.dumps({"type": "content_block_start", "index": block_index, "content_block": {"type": "text", "text": ""}})}\n\n'
                    yield f'event: content_block_delta\ndata: {_json.dumps({"type": "content_block_delta", "index": block_index, "delta": {"type": "text_delta", "text": content}})}\n\n'
                    output_tokens += len(content) // 4  # rough estimate

                # Handle tool calls
                tool_calls = delta.get("tool_calls", [])
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    if tc.get("id") and fn.get("name"):
                        # New tool call block
                        if sent_block_start:
                            yield f'event: content_block_stop\ndata: {_json.dumps({"type": "content_block_stop", "index": block_index})}\n\n'
                            block_index += 1
                            sent_block_start = False
                        yield f'event: content_block_start\ndata: {_json.dumps({"type": "content_block_start", "index": block_index, "content_block": {"type": "tool_use", "id": tc["id"], "name": fn["name"], "input": {}}})}\n\n'
                        sent_block_start = True

                    args_chunk = fn.get("arguments", "")
                    if args_chunk:
                        yield f'event: content_block_delta\ndata: {_json.dumps({"type": "content_block_delta", "index": block_index, "delta": {"type": "input_json_delta", "partial_json": args_chunk}})}\n\n'

                # Handle finish
                if finish_reason:
                    stop_reason_map = {
                        "stop": "end_turn",
                        "length": "max_tokens",
                        "tool_calls": "tool_use",
                        "function_call": "tool_use",
                    }
                    anthropic_stop = stop_reason_map.get(finish_reason, "end_turn")

                    if sent_block_start:
                        yield f'event: content_block_stop\ndata: {_json.dumps({"type": "content_block_stop", "index": block_index})}\n\n'

                    yield f'event: message_delta\ndata: {_json.dumps({"type": "message_delta", "delta": {"stop_reason": anthropic_stop, "stop_sequence": None}, "usage": {"output_tokens": max(1, output_tokens)}})}\n\n'
                    yield f'event: message_stop\ndata: {_json.dumps({"type": "message_stop"})}\n\n'
                    return
        except Exception as e:
            logger.error("anthropic_stream_failed", model=model, error=str(e))
            yield f'event: error\ndata: {_json.dumps({"type": "error", "error": {"type": "api_error", "message": str(e)}})}\n\n'
            return

        # If stream ended without finish_reason
        if not sent_start:
            yield f'event: message_start\ndata: {_json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 1}}})}\n\n'

        if sent_block_start:
            yield f'event: content_block_stop\ndata: {_json.dumps({"type": "content_block_stop", "index": block_index})}\n\n'

        yield f'event: message_delta\ndata: {_json.dumps({"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": max(1, output_tokens)}})}\n\n'
        yield f'event: message_stop\ndata: {_json.dumps({"type": "message_stop"})}\n\n'

    def _openai_response_to_anthropic(
        self,
        openai_resp: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        """Convert a non-streaming OpenAI response to Anthropic format."""
        import uuid
        import json as _json

        choices = openai_resp.get("choices", [])
        usage = openai_resp.get("usage", {})

        content = []
        stop_reason = "end_turn"

        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            stop_reason_map = {
                "stop": "end_turn",
                "length": "max_tokens",
                "tool_calls": "tool_use",
                "function_call": "tool_use",
            }
            stop_reason = stop_reason_map.get(finish_reason, "end_turn")

            # Text content
            text = message.get("content", "")
            if text:
                content.append({"type": "text", "text": text})

            # Tool calls
            tool_calls = message.get("tool_calls", [])
            for tc in tool_calls:
                fn = tc.get("function", {})
                try:
                    input_data = _json.loads(fn.get("arguments", "{}"))
                except Exception:
                    input_data = {}
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:8]}"),
                    "name": fn.get("name", ""),
                    "input": input_data,
                })

        return {
            "id": openai_resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }

    async def handle_image_generation(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle an image generation request."""
        model = body.get("model", "openai/dall-e-3")
        prompt = body.get("prompt", "")

        logger.info("image_request", model=model)

        # Route to image-capable backend
        try:
            result = await self._handle_image(model, prompt, body)
        except Exception as e:
            logger.error("image_request_failed", model=model, error=str(e))
            raise

        self._log_usage("image", model, {"total_tokens": 0})
        return result

    async def _handle_image(
        self,
        model: str,
        prompt: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Route image generation to appropriate provider."""
        import httpx

        # Determine provider from model
        provider, _ = model.split("/", 1) if "/" in model else ("openai", model)

        base_urls = {
            "openai": "https://api.openai.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "stability": "https://api.stability.ai/v1",
        }

        base_url = base_urls.get(provider, "https://api.openai.com/v1")
        api_key = settings.get_api_key(provider) or ""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base_url}/images/generations",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def handle_speech(
        self,
        body: dict[str, Any],
    ) -> bytes:
        """Handle a text-to-speech request. Returns audio bytes."""
        model = body.get("model", "openai/tts-1")
        input_text = body.get("input", "")
        voice = body.get("voice", "alloy")
        response_format = body.get("response_format", "mp3")
        speed = body.get("speed", 1.0)

        logger.info("speech_request", model=model, voice=voice)

        import httpx
        base_url = "https://api.openai.com/v1"
        api_key = settings.get_api_key("openai") or ""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/audio/speech",
                json={
                    "model": model,
                    "input": input_text,
                    "voice": voice,
                    "response_format": response_format,
                    "speed": speed,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.content

    async def handle_embeddings(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle an embeddings request."""
        model = body.get("model", "openai/text-embedding-3-small")
        input_text = body.get("input", "")

        logger.info("embeddings_request", model=model)

        import httpx
        base_url = "https://api.openai.com/v1"
        api_key = settings.get_api_key("openai") or ""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/embeddings",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    def _log_usage(
        self,
        request_type: str,
        model: str,
        result: dict[str, Any],
    ) -> None:
        """Log request usage to storage."""
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)

        provider = self.router.hub.resolve_provider(model)

        self.storage.log_request({
            "type": request_type,
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": total_tokens,
            "cost_usd": self._estimate_cost(provider, model, total_tokens),
        })

    def _estimate_cost(self, provider: str, model: str, tokens: int) -> float:
        """Estimate cost in USD. Simplified pricing."""
        # Very rough estimates per 1M tokens
        pricing = {
            "openrouter": {"gpt-4o": 2.5, "gpt-4o-mini": 0.15, "claude": 3.0},
            "openai": {"gpt-4o": 2.5, "gpt-4o-mini": 0.15},
            "deepseek": {"deepseek": 0.27},
            "nvidia": {"llama": 0.0},
            "lmstudio": {"local": 0.0},
        }

        p = pricing.get(provider, {})
        rate = 1.0  # default rate per 1M tokens
        for key, val in p.items():
            if key in model.lower():
                rate = val
                break

        return (tokens / 1_000_000) * rate

    @property
    def uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self._start_time


# Global service instance
_service: GatewayService | None = None


def get_service() -> GatewayService:
    """Get the global gateway service."""
    global _service
    if _service is None:
        _service = GatewayService()
    return _service

"""
OpenAI → OpenAI pass-through (no translation needed).
"""

from __future__ import annotations

from typing import Any


def pass_through(response: dict[str, Any] | str, **kwargs: Any) -> dict[str, Any]:
    """Return the response as-is (same format)."""
    if isinstance(response, dict):
        return response
    return {}


def translate_stream_chunk(chunk: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Return streaming chunk as-is."""
    return chunk


def translate_error(error: dict[str, Any]) -> dict[str, Any]:
    """Return error as-is."""
    return error
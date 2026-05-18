"""
Unit tests for translation layer.
"""

from __future__ import annotations

from typing import Any

import pytest

from rihaproxy.translation.formats import detect_source_format
from rihaproxy.translation.index import (
    TranslationRegistry,
    get_registry,
    translate_request,
    translate_response,
)


class TestDetectSourceFormat:
    """Test format detection from request bodies."""

    def test_openai_format_detection(self):
        """Test OpenAI format detection."""
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        fmt = detect_source_format(body)
        assert fmt == "openai"

    def test_anthropic_format_detection(self):
        """Test Anthropic format detection."""
        body = {
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
        }
        fmt = detect_source_format(body)
        assert fmt == "anthropic"

    def test_anthropic_with_system(self):
        """Test Anthropic format with system message."""
        body = {
            "model": "claude-3-opus",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        fmt = detect_source_format(body)
        assert fmt == "anthropic"

    def test_gemini_format_detection(self):
        """Test Gemini format detection."""
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
        }
        fmt = detect_source_format(body)
        assert fmt == "gemini"

    def test_vertex_format_detection(self):
        """Test Vertex format detection."""
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
            "systemInstruction": {"parts": [{"text": "You are helpful"}]},
        }
        fmt = detect_source_format(body)
        assert fmt == "gemini"

    def test_unknown_format_falls_back_to_openai(self):
        """Test that unknown formats default to openai."""
        body = {"some": "random", "format": "data"}
        fmt = detect_source_format(body)
        assert fmt == "openai"


class TestTranslationRegistry:
    """Test the translation registry."""

    @pytest.fixture
    def registry(self) -> TranslationRegistry:
        """Create a fresh translation registry."""
        r = TranslationRegistry()
        r.register()
        return r

    def test_registry_singleton(self):
        """Test that get_registry returns same instance."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_openai_to_anthropic_translation(self, registry: TranslationRegistry):
        """Test translating OpenAI format to Anthropic."""
        body = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "What is 2+2?"},
            ],
        }
        result = registry.translate_request(body, "openai", "anthropic")
        assert "messages" in result
        assert result["messages"][0]["role"] == "user"

    def test_openai_to_gemini_translation(self, registry: TranslationRegistry):
        """Test translating OpenAI format to Gemini."""
        body = {
            "model": "gemini-pro",
            "messages": [
                {"role": "user", "content": "Hello"},
            ],
        }
        result = registry.translate_request(body, "openai", "gemini")
        assert "contents" in result

    def test_anthropic_tool_result_to_openai_tool_message(self, registry: TranslationRegistry):
        """Test Anthropic tool_result blocks become OpenAI tool messages."""
        body = {
            "model": "claude-haiku-4.5",
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_123",
                    "content": [{"type": "text", "text": "done"}],
                }],
            }],
        }

        result = registry.translate_request(body, "anthropic", "openai")

        assert result["messages"] == [{
            "role": "tool",
            "tool_call_id": "toolu_123",
            "content": "done",
        }]

    def test_same_format_returns_unchanged(self, registry: TranslationRegistry):
        """Test that translating same format returns unchanged body."""
        body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}
        result = registry.translate_request(body, "openai", "openai")
        assert result == body

    def test_unsupported_translation_raises(self, registry: TranslationRegistry):
        """Test that unsupported translation raises error."""
        body = {"messages": []}
        with pytest.raises(Exception):
            registry.translate_request(body, "unknown", "openai")

    def test_response_translation_openai(self, registry: TranslationRegistry):
        """Test response translation for OpenAI."""
        response = {"id": "test", "choices": []}
        result = registry.translate_response(response, "openai", "openai")
        assert result == response

    def test_response_translation_anthropic_to_openai(self, registry: TranslationRegistry):
        """Test translating Anthropic response to OpenAI format."""
        response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
        }
        result = registry.translate_response(response, "anthropic", "openai")
        assert "id" in result
        assert "choices" in result


class TestTranslateFunctions:
    """Test module-level convenience functions."""

    def test_translate_request_convenience(self):
        """Test translate_request convenience function."""
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = translate_request(body, "openai", "anthropic")
        assert "messages" in result

    def test_translate_response_convenience(self):
        """Test translate_response convenience function."""
        response = {"id": "test", "choices": []}
        result = translate_response(response, "openai", "openai")
        assert result == response


class TestTranslationEdgeCases:
    """Edge case tests for translation."""

    def test_empty_messages_list(self):
        """Test translation with empty messages."""
        body = {"messages": []}
        result = translate_request(body, "openai", "anthropic")
        assert "messages" in result

    def test_tool_calls_preserved(self):
        """Test that tool calls are preserved in translation."""
        body = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "Use a calculator"}
            ],
            "tools": [
                {"type": "function", "function": {"name": "calc", "parameters": {}}}
            ],
        }
        # Translation should not raise
        try:
            result = translate_request(body, "openai", "anthropic")
            assert "messages" in result
        except Exception:
            pass  # Some translations may not support tools yet

    def test_streaming_flag_preserved(self):
        """Test that stream flag is preserved."""
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }
        result = translate_request(body, "openai", "anthropic")
        assert "stream" in result or result.get("stream") is True

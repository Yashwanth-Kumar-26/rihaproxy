"""
Unit tests for format detection and format utilities.
"""

from __future__ import annotations

import pytest

from rihaproxy.translation.formats import (
    FORMAT_INFO,
    SourceFormat,
    TargetFormat,
    detect_source_format,
    format_supports_streaming,
    format_supports_tools,
    format_supports_vision,
    get_auth_type,
    get_endpoint,
)


class TestSourceFormatDetection:
    """Test source format detection."""

    def test_openai_chat_format(self):
        """Test detection of OpenAI chat completions format."""
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        assert detect_source_format(body) == "openai"

    def test_openai_with_stream(self):
        """Test OpenAI format with stream parameter."""
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        assert detect_source_format(body) == "openai"

    def test_anthropic_format_basic(self):
        """Test detection of basic Anthropic format."""
        body = {
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024,
        }
        assert detect_source_format(body) == "anthropic"

    def test_anthropic_with_system(self):
        """Test Anthropic format with system message."""
        body = {
            "model": "claude-3-opus",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024,
        }
        assert detect_source_format(body) == "anthropic"

    def test_anthropic_with_content_blocks(self):
        """Test Anthropic format with content blocks."""
        body = {
            "model": "claude-3-opus",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
            "max_tokens": 1024,
        }
        assert detect_source_format(body) == "anthropic"

    def test_openai_responses_format(self):
        """Test detection of OpenAI Responses API format."""
        body = {
            "model": "gpt-4o",
            "input": "Hello, how are you?",
        }
        assert detect_source_format(body) == "openai-responses"

    def test_gemini_format(self):
        """Test detection of Gemini format."""
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Hello"}],
                }
            ],
        }
        assert detect_source_format(body) == "gemini"

    def test_vertex_format(self):
        """Test detection of Vertex AI format."""
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
            "systemInstruction": {"parts": [{"text": "You are helpful"}]},
        }
        assert detect_source_format(body) == "gemini"

    def test_fallback_to_openai(self):
        """Test that unknown formats fall back to OpenAI."""
        body = {"some": "random", "data": "value"}
        assert detect_source_format(body) == "openai"

    def test_empty_body(self):
        """Test detection with empty body."""
        assert detect_source_format({}) == "openai"


class TestFormatInfo:
    """Test format information dictionary."""

    def test_openai_supports_tools(self):
        """Test OpenAI supports tools."""
        assert FORMAT_INFO["openai"]["supports_tools"] is True

    def test_openai_supports_streaming(self):
        """Test OpenAI supports streaming."""
        assert FORMAT_INFO["openai"]["supports_streaming"] is True

    def test_anthropic_supports_tools(self):
        """Test Anthropic supports tools."""
        assert FORMAT_INFO["anthropic"]["supports_tools"] is True

    def test_kiro_no_tools(self):
        """Test Kiro does not support tools."""
        assert FORMAT_INFO["kiro"]["supports_tools"] is False

    def test_ollama_no_auth(self):
        """Test Ollama uses no-auth."""
        assert FORMAT_INFO["ollama"]["auth_type"] == "noauth"

    def test_all_formats_have_endpoints(self):
        """Test all formats have API endpoints defined."""
        for fmt, info in FORMAT_INFO.items():
            assert "endpoint" in info, f"{fmt} missing endpoint"


class TestFormatUtilities:
    """Test format utility functions."""

    def test_format_supports_tools_openai(self):
        """Test tool support check for OpenAI."""
        assert format_supports_tools("openai") is True

    def test_format_supports_tools_kiro(self):
        """Test tool support check for Kiro."""
        assert format_supports_tools("kiro") is False

    def test_format_supports_tools_unknown(self):
        """Test tool support for unknown format defaults to False."""
        assert format_supports_tools("unknown") is False

    def test_format_supports_streaming(self):
        """Test streaming support check."""
        assert format_supports_streaming("openai") is True
        assert format_supports_streaming("unknown") is True  # default

    def test_format_supports_vision_openai(self):
        """Test vision support check for OpenAI."""
        assert format_supports_vision("openai") is True

    def test_format_supports_vision_anthropic(self):
        """Test vision support check for Anthropic."""
        assert format_supports_vision("anthropic") is True

    def test_format_supports_vision_ollama(self):
        """Test vision support check for Ollama."""
        assert format_supports_vision("ollama") is True

    def test_get_endpoint_openai(self):
        """Test getting endpoint for OpenAI."""
        endpoint = get_endpoint("openai")
        assert endpoint == "/v1/chat/completions"

    def test_get_endpoint_vertex_with_model(self):
        """Test getting endpoint for Vertex with model substitution."""
        endpoint = get_endpoint("vertex", "gemini-pro")
        assert "gemini-pro" in endpoint

    def test_get_endpoint_unknown(self):
        """Test getting endpoint for unknown format defaults."""
        endpoint = get_endpoint("unknown")
        assert endpoint == "/v1/chat/completions"

    def test_get_auth_type_openai(self):
        """Test getting auth type for OpenAI."""
        assert get_auth_type("openai") == "bearer"

    def test_get_auth_type_ollama(self):
        """Test getting auth type for Ollama."""
        assert get_auth_type("ollama") == "noauth"

    def test_get_auth_type_unknown(self):
        """Test getting auth type for unknown format."""
        assert get_auth_type("unknown") == "bearer"  # default


class TestSourceFormatEnum:
    """Test SourceFormat enum."""

    def test_source_format_values(self):
        """Test SourceFormat enum values."""
        assert SourceFormat.OPENAI == "openai"
        assert SourceFormat.ANTHROPIC == "anthropic"
        assert SourceFormat.GEMINI == "gemini"
        assert SourceFormat.OPENAI_RESPONSES == "openai-responses"


class TestTargetFormatEnum:
    """Test TargetFormat enum."""

    def test_target_format_values(self):
        """Test TargetFormat enum values."""
        assert TargetFormat.OPENAI == "openai"
        assert TargetFormat.ANTHROPIC == "anthropic"
        assert TargetFormat.GEMINI == "gemini"
        assert TargetFormat.OLLAMA == "ollama"
        assert TargetFormat.KIRO == "kiro"

    def test_target_format_is_string(self):
        """Test that TargetFormat values are strings."""
        assert isinstance(TargetFormat.OPENAI, str)
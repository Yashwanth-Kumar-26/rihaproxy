"""
Pytest configuration and shared fixtures for RihaProxy tests.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Environment Setup
# =============================================================================

@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before each test."""
    original_env = os.environ.copy()

    # Clear RIHAPROXY env vars
    for key in list(os.environ.keys()):
        if key.startswith("RIHAPROXY_"):
            os.environ.pop(key, None)

    # Also clear .env file reading by providing a dummy env file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("# Test environment - no real keys\n")
        temp_env = f.name

    os.environ["RIHAPROXY_ENV_FILE"] = temp_env

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
    os.unlink(temp_env)


# =============================================================================
# Storage Fixtures
# =============================================================================

@pytest.fixture
def temp_data_dir(tmp_path) -> Path:
    """Create a temporary data directory."""
    data_dir = tmp_path / ".rihaproxy"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def storage(temp_data_dir) -> Generator:
    """Create a test storage instance."""
    # Avoid importing from rihaproxy to prevent circular imports
    from rihaproxy.storage.db import Storage
    s = Storage(data_dir=temp_data_dir)
    yield s
    # Cleanup handled by tmp_path


@pytest.fixture
def sample_db_content() -> dict[str, Any]:
    """Sample database content."""
    return {
        "version": "1.0",
        "provider_connections": [
            {
                "id": "conn_001",
                "provider": "openrouter",
                "name": "Test Provider",
                "auth_type": "api_key",
                "api_key": "sk-or-test-key",
                "is_active": True,
            }
        ],
        "model_aliases": {
            "my-model": "openai/gpt-4o-mini",
        },
        "combos": {
            "combo_001": {
                "id": "combo_001",
                "name": "fallback-chain",
                "models": ["openai/gpt-4o-mini", "anthropic/claude-3-haiku"],
            }
        },
        "settings": {},
    }


# =============================================================================
# Request Fixtures
# =============================================================================

@pytest.fixture
def chat_request() -> dict[str, Any]:
    """Sample chat completions request body."""
    return {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2 + 2?"},
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": False,
    }


@pytest.fixture
def anthropic_request() -> dict[str, Any]:
    """Sample Anthropic messages request body."""
    return {
        "model": "claude-3-5-haiku-20241017",
        "messages": [
            {"role": "user", "content": "What is 2 + 2?"},
        ],
        "max_tokens": 100,
        "stream": False,
    }


@pytest.fixture
def streaming_chat_request() -> dict[str, Any]:
    """Sample streaming chat request."""
    return {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Count to 5."},
        ],
        "stream": True,
    }


@pytest.fixture
def image_request() -> dict[str, Any]:
    """Sample image generation request."""
    return {
        "model": "openai/dall-e-3",
        "prompt": "A cute cat sitting on a windowsill",
        "n": 1,
        "size": "1024x1024",
        "quality": "standard",
    }


@pytest.fixture
def embeddings_request() -> dict[str, Any]:
    """Sample embeddings request."""
    return {
        "model": "openai/text-embedding-3-small",
        "input": "The quick brown fox jumps over the lazy dog",
    }


@pytest.fixture
def speech_request() -> dict[str, Any]:
    """Sample text-to-speech request."""
    return {
        "model": "openai/tts-1",
        "input": "Hello, world! This is a test.",
        "voice": "alloy",
        "response_format": "mp3",
    }


@pytest.fixture
def search_request() -> dict[str, Any]:
    """Sample web search request."""
    return {
        "model": "tavily/search",
        "query": "What is RihaProxy?",
        "max_results": 5,
    }


@pytest.fixture
def fetch_request() -> dict[str, Any]:
    """Sample web fetch request."""
    return {
        "model": "jina/fetch",
        "url": "https://example.com",
        "format": "markdown",
    }


# =============================================================================
# Response Fixtures
# =============================================================================

@pytest.fixture
def openai_chat_response() -> dict[str, Any]:
    """Sample OpenAI chat completions response."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The answer is 4.",
                },
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
        },
    }


@pytest.fixture
def anthropic_message_response() -> dict[str, Any]:
    """Sample Anthropic messages response."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-haiku-20241017",
        "content": [
            {"type": "text", "text": "The answer is 4."}
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 15,
            "output_tokens": 6,
        },
    }


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    def _create(status_code: int = 200, json_data: dict[str, Any] | None = None, text: str = ""):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text or json.dumps(json_data) if json_data else ""
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return response
    return _create


# =============================================================================
# Auth Fixtures
# =============================================================================

@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return authorization headers for testing."""
    return {"Authorization": "Bearer test-auth-token-123"}


@pytest.fixture
def api_key_headers() -> dict[str, str]:
    """Return X-API-Key headers for testing."""
    return {"X-API-Key": "test-auth-token-123"}
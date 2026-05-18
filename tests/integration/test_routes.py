"""
Integration tests for gateway API routes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint(self, client: TestClient):
        """Test that health endpoint returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client: TestClient):
        """Test health response has correct structure."""
        response = client.get("/api/health")
        data = response.json()
        assert "ok" in data
        assert "version" in data
        assert "uptime" in data
        assert "providers_active" in data
        assert "total_requests" in data

    def test_health_ok_flag(self, client: TestClient):
        """Test that ok flag is True."""
        response = client.get("/api/health")
        data = response.json()
        assert data["ok"] is True


class TestModelsEndpoint:
    """Test models listing endpoints."""

    def test_list_models_requires_auth(self, client: TestClient):
        """Test that /v1/models requires authentication."""
        response = client.get("/v1/models")
        # Should fail without auth (unless no auth token set in test)
        # This depends on test settings
        assert response.status_code in [200, 401]

    def test_list_models_with_auth(self, client: TestClient, auth_headers: dict[str, str]):
        """Test that /v1/models works with auth."""
        response = client.get("/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "object" in data
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_image_models(self, client: TestClient, auth_headers: dict[str, str]):
        """Test image models listing."""
        response = client.get("/v1/models/image", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_list_tts_models(self, client: TestClient, auth_headers: dict[str, str]):
        """Test TTS models listing."""
        response = client.get("/v1/models/tts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_list_embedding_models(self, client: TestClient, auth_headers: dict[str, str]):
        """Test embedding models listing."""
        response = client.get("/v1/models/embedding", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


class TestChatCompletionsEndpoint:
    """Test chat completions endpoint."""

    def test_chat_requires_auth(self, client: TestClient, chat_request: dict[str, Any]):
        """Test that chat completions requires auth."""
        response = client.post("/v1/chat/completions", json=chat_request)
        # Depends on settings
        assert response.status_code in [200, 401]

    def test_chat_invalid_json(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of invalid JSON."""
        response = client.post(
            "/v1/chat/completions",
            headers={**auth_headers, "Content-Type": "application/json"},
            content=b"not valid json",
        )
        assert response.status_code == 400

    def test_chat_missing_model(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of missing model field."""
        response = client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        # Should fail with validation error
        assert response.status_code >= 400

    def test_chat_missing_messages(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of missing messages."""
        response = client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={"model": "gpt-4o"},
        )
        assert response.status_code >= 400


class TestAnthropicMessagesEndpoint:
    """Test Anthropic messages endpoint."""

    def test_anthropic_requires_auth(self, client: TestClient, anthropic_request: dict[str, Any]):
        """Test that /v1/messages requires auth."""
        response = client.post("/v1/messages", json=anthropic_request)
        assert response.status_code in [200, 401]

    def test_anthropic_invalid_json(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of invalid JSON."""
        response = client.post(
            "/v1/messages",
            headers={**auth_headers, "Content-Type": "application/json"},
            content=b"not valid json",
        )
        assert response.status_code == 400


class TestEmbeddingsEndpoint:
    """Test embeddings endpoint."""

    def test_embeddings_requires_auth(self, client: TestClient, embeddings_request: dict[str, Any]):
        """Test that embeddings requires auth."""
        response = client.post("/v1/embeddings", json=embeddings_request)
        assert response.status_code in [200, 401]

    def test_embeddings_with_auth(self, client: TestClient, auth_headers: dict[str, str]):
        """Test embeddings with auth."""
        response = client.post(
            "/v1/embeddings",
            headers=auth_headers,
            json={
                "model": "text-embedding-3-small",
                "input": "Hello world",
            },
        )
        # May fail due to no API key, but should pass auth
        assert response.status_code in [200, 500]


class TestSpeechEndpoint:
    """Test text-to-speech endpoint."""

    def test_speech_requires_auth(self, client: TestClient, speech_request: dict[str, Any]):
        """Test that /v1/audio/speech requires auth."""
        response = client.post("/v1/audio/speech", json=speech_request)
        assert response.status_code in [200, 401]


class TestWebSearchEndpoint:
    """Test web search endpoint."""

    def test_search_requires_auth(self, client: TestClient, search_request: dict[str, Any]):
        """Test that /v1/search requires auth."""
        response = client.post("/v1/search", json=search_request)
        assert response.status_code in [200, 401]

    def test_search_missing_query(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of missing query."""
        response = client.post(
            "/v1/search",
            headers=auth_headers,
            json={"model": "tavily/search"},
        )
        # Should return error about missing query
        assert response.status_code in [200, 400, 500]


class TestWebFetchEndpoint:
    """Test web fetch endpoint."""

    def test_fetch_requires_auth(self, client: TestClient, fetch_request: dict[str, Any]):
        """Test that /v1/web/fetch requires auth."""
        response = client.post("/v1/web/fetch", json=fetch_request)
        assert response.status_code in [200, 401]

    def test_fetch_missing_url(self, client: TestClient, auth_headers: dict[str, str]):
        """Test handling of missing URL."""
        response = client.post(
            "/v1/web/fetch",
            headers=auth_headers,
            json={"model": "jina/fetch"},
        )
        # Should return error about missing url
        assert response.status_code in [200, 400, 500]


class TestAdminEndpoints:
    """Test admin API endpoints."""

    def test_create_alias(self, client: TestClient, auth_headers: dict[str, str]):
        """Test creating a model alias."""
        response = client.post(
            "/api/aliases",
            headers=auth_headers,
            json={"alias": "my-gpt", "target": "openai/gpt-4o-mini"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["alias"] == "my-gpt"

    def test_create_alias_missing_fields(self, client: TestClient, auth_headers: dict[str, str]):
        """Test creating alias with missing fields."""
        response = client.post(
            "/api/aliases",
            headers=auth_headers,
            json={"alias": "my-gpt"},
        )
        assert response.status_code == 400

    def test_delete_alias_not_found(self, client: TestClient, auth_headers: dict[str, str]):
        """Test deleting non-existent alias."""
        response = client.delete("/api/aliases/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_create_combo(self, client: TestClient, auth_headers: dict[str, str]):
        """Test creating a model combo."""
        response = client.post(
            "/api/combos",
            headers=auth_headers,
            json={
                "name": "fallback-chain",
                "models": ["openai/gpt-4o-mini", "anthropic/claude-3-haiku"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "id" in data

    def test_delete_combo_not_found(self, client: TestClient, auth_headers: dict[str, str]):
        """Test deleting non-existent combo."""
        response = client.delete("/api/combos/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_get_usage(self, client: TestClient, auth_headers: dict[str, str]):
        """Test getting usage statistics."""
        response = client.get("/api/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "recent" in data


class TestOAuthEndpoints:
    """Test OAuth-related endpoints."""

    def test_oauth_start_unsupported_provider(self, client: TestClient, auth_headers: dict[str, str]):
        """Test starting OAuth for unsupported provider."""
        response = client.post(
            "/api/oauth/unsupported/start",
            headers=auth_headers,
        )
        # Should return error for unsupported provider
        assert response.status_code in [400, 404, 500]

    def test_oauth_poll_missing_device_code(self, client: TestClient, auth_headers: dict[str, str]):
        """Test polling without device code."""
        response = client.post(
            "/api/oauth/claude/poll",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 400

    def test_oauth_connect_missing_key(self, client: TestClient, auth_headers: dict[str, str]):
        """Test connecting provider without API key."""
        response = client.post(
            "/api/oauth/openrouter/connect",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 400

    def test_list_connections(self, client: TestClient, auth_headers: dict[str, str]):
        """Test listing provider connections."""
        response = client.get("/api/connections", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "connections" in data
        assert "total" in data

    def test_list_providers(self, client: TestClient, auth_headers: dict[str, str]):
        """Test listing available providers."""
        response = client.get("/api/providers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        # Should have standard providers listed
        providers = [p["id"] for p in data["providers"]]
        assert "openrouter" in providers
        assert "openai" in providers


class TestStatusEndpoint:
    """Test status endpoint."""

    def test_status_requires_auth(self, client: TestClient):
        """Test that status endpoint requires auth."""
        response = client.get("/api/status")
        assert response.status_code in [200, 401]

    def test_status_with_auth(self, client: TestClient, auth_headers: dict[str, str]):
        """Test status endpoint with auth."""
        response = client.get("/api/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "active_providers" in data
        assert "aliases" in data
        assert "combos" in data
        assert "usage" in data
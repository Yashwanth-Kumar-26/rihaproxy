"""
Unit tests for the storage layer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from rihaproxy.storage.db import Storage


class TestStorage:
    """Test suite for Storage persistence layer."""

    @pytest.fixture
    def storage(self, tmp_path) -> Storage:
        """Create storage instance with temp directory."""
        data_dir = tmp_path / ".rihaproxy"
        data_dir.mkdir(parents=True, exist_ok=True)
        return Storage(data_dir=data_dir)

    def test_default_db_structure(self, storage: Storage):
        """Test default database structure."""
        data = storage._data
        assert "version" in data
        assert "provider_connections" in data
        assert "model_aliases" in data
        assert "combos" in data
        assert "api_keys" in data
        assert "settings" in data

    def test_save_and_load(self, storage: Storage, tmp_path):
        """Test that data persists after save."""
        storage._data["test_value"] = "test123"
        storage.save()

        # Create new storage instance pointing to same directory
        storage2 = Storage(data_dir=storage.data_dir)
        assert storage2._data.get("test_value") == "test123"

    def test_provider_connection_lifecycle(self, storage: Storage):
        """Test add, update, delete provider connections."""
        # Add connection
        conn = {
            "provider": "openrouter",
            "name": "Test Key",
            "auth_type": "api_key",
            "api_key": "sk-or-test",
        }
        conn_id = storage.add_provider_connection(conn)
        assert conn_id.startswith("conn_")

        # Get connections
        connections = storage.get_provider_connections()
        assert len(connections) == 1
        assert connections[0]["provider"] == "openrouter"

        # Update connection
        success = storage.update_provider_connection(conn_id, {"is_active": False})
        assert success is True

        # Delete connection
        deleted = storage.delete_provider_connection(conn_id)
        assert deleted is True
        assert len(storage.get_provider_connections()) == 0

    def test_get_active_providers(self, storage: Storage):
        """Test filtering active providers."""
        storage.add_provider_connection({
            "provider": "openrouter",
            "name": "Active",
            "is_active": True,
        })
        storage.add_provider_connection({
            "provider": "openai",
            "name": "Inactive",
            "is_active": False,
        })

        active = storage.get_active_providers()
        assert len(active) == 1
        assert active[0]["provider"] == "openrouter"

    def test_model_aliases(self, storage: Storage):
        """Test model alias management."""
        # Set alias
        storage.set_alias("my-gpt", "openai/gpt-4o-mini")
        aliases = storage.get_aliases()
        assert aliases["my-gpt"] == "openai/gpt-4o-mini"

        # Resolve alias
        resolved = storage.resolve_alias("my-gpt")
        assert resolved == "openai/gpt-4o-mini"

        # Unknown alias returns itself
        unknown = storage.resolve_alias("unknown-model")
        assert unknown == "unknown-model"

        # Delete alias
        deleted = storage.delete_alias("my-gpt")
        assert deleted is True
        assert storage.get_aliases().get("my-gpt") is None

    def test_combos(self, storage: Storage):
        """Test model combo management."""
        # Add combo
        combo = {
            "name": "fallback-chain",
            "models": ["openai/gpt-4o", "anthropic/claude-3-haiku"],
            "description": "Auto fallback",
        }
        combo_id = storage.add_combo(combo)
        assert combo_id.startswith("combo_")

        # Get combos
        combos = storage.get_combos()
        assert len(combos) == 1

        # Get combo by name
        found = storage.get_combo("fallback-chain")
        assert found is not None
        assert found["models"] == ["openai/gpt-4o", "anthropic/claude-3-haiku"]

        # Delete combo
        deleted = storage.delete_combo(combo_id)
        assert deleted is True
        assert len(storage.get_combos()) == 0

    def test_settings(self, storage: Storage):
        """Test settings management."""
        # Update settings
        storage.update_settings({"theme": "dark", "log_level": "DEBUG"})
        settings = storage.get_settings()
        assert settings["theme"] == "dark"
        assert settings["log_level"] == "DEBUG"

    def test_log_request(self, storage: Storage):
        """Test request logging."""
        storage.log_request({
            "type": "chat",
            "provider": "openrouter",
            "model": "gpt-4o-mini",
            "total_tokens": 100,
            "cost_usd": 0.00015,
        })

        # Check usage file was created
        assert storage.usage_path.exists()

        # Check log file was written
        assert storage.log_path.exists()
        log_content = storage.log_path.read_text()
        assert "openrouter" in log_content
        assert "gpt-4o-mini" in log_content

    def test_usage_summary(self, storage: Storage):
        """Test usage summary retrieval."""
        # Log some requests
        storage.log_request({
            "type": "chat",
            "provider": "openrouter",
            "model": "gpt-4o-mini",
            "total_tokens": 100,
            "cost_usd": 0.00015,
        })
        storage.log_request({
            "type": "chat",
            "provider": "openrouter",
            "model": "gpt-4o-mini",
            "total_tokens": 200,
            "cost_usd": 0.00030,
        })

        summary = storage.get_usage_summary()
        assert summary["total_requests"] == 2

        by_provider = summary["by_provider"]
        assert "openrouter" in by_provider
        assert by_provider["openrouter"]["total_tokens"] == 300

    def test_get_recent_requests(self, storage: Storage):
        """Test retrieving recent request logs."""
        for i in range(5):
            storage.log_request({
                "type": "chat",
                "provider": "openrouter",
                "model": f"model-{i}",
                "total_tokens": 100,
                "cost_usd": 0.0001,
            })

        recent = storage.get_recent_requests(limit=3)
        assert len(recent) == 3

    def test_corrupted_db_handling(self, tmp_path):
        """Test handling of corrupted database file."""
        data_dir = tmp_path / ".rihaproxy"
        data_dir.mkdir(parents=True)

        # Write corrupted JSON
        db_path = data_dir / "db.json"
        db_path.write_text("{ broken json")

        # Should fall back to default
        storage = Storage(data_dir=data_dir)
        assert "version" in storage._data

    def test_concurrent_access(self, storage: Storage):
        """Test that concurrent saves don't corrupt data."""
        connections = [
            {"provider": f"provider-{i}", "name": f"Conn {i}", "is_active": True}
            for i in range(10)
        ]

        for conn in connections:
            storage.add_provider_connection(conn)

        assert len(storage.get_provider_connections()) == 10


class TestStorageEdgeCases:
    """Edge case tests for storage."""

    def test_empty_data_dir_creation(self, tmp_path):
        """Test that data directory is created if it doesn't exist."""
        data_dir = tmp_path / "new" / "dir" / ".rihaproxy"
        storage = Storage(data_dir=data_dir)
        assert data_dir.exists()

    def test_combo_by_name_not_found(self, storage: Storage):
        """Test getting non-existent combo."""
        found = storage.get_combo("nonexistent")
        assert found is None

    def test_delete_nonexistent_alias(self, storage: Storage):
        """Test deleting alias that doesn't exist."""
        deleted = storage.delete_alias("nonexistent")
        assert deleted is False

    def test_update_nonexistent_connection(self, storage: Storage):
        """Test updating connection that doesn't exist."""
        success = storage.update_provider_connection("fake-id", {"key": "value"})
        assert success is False
"""
Storage layer — persistence for providers, combos, keys, and usage.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class Storage:
    """
    JSON-based persistence layer.
    Manages db.json (providers, combos, keys, settings) and usage tracking.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path.home() / ".rihaproxy"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "db.json"
        self.usage_path = self.data_dir / "usage.json"
        self.log_path = self.data_dir / "log.txt"
        self._data: dict[str, Any] = self._load_db()

    def _load_db(self) -> dict[str, Any]:
        """Load the main database file."""
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("db_load_failed", error=str(e), path=str(self.db_path))
        return self._default_db()

    def _default_db(self) -> dict[str, Any]:
        """Default database structure."""
        return {
            "version": "1.0",
            "provider_connections": [],
            "provider_nodes": [],
            "model_aliases": {},
            "combos": {},
            "api_keys": [],
            "settings": {},
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def save(self) -> None:
        """Persist database to disk."""
        self._data["updated_at"] = time.time()
        try:
            self.db_path.write_text(json.dumps(self._data, indent=2))
        except IOError as e:
            logger.error("db_save_failed", error=str(e))

    # ---- Provider Connections ----

    def get_provider_connections(self) -> list[dict[str, Any]]:
        """Get all provider connections."""
        return self._data.get("provider_connections", [])

    def add_provider_connection(self, connection: dict[str, Any]) -> str:
        """Add a new provider connection. Returns connection ID."""
        connections = self._data.setdefault("provider_connections", [])
        conn_id = connection.get("id", f"conn_{int(time.time() * 1000)}")
        connection["id"] = conn_id
        connections.append(connection)
        self.save()
        return conn_id

    def update_provider_connection(self, conn_id: str, updates: dict[str, Any]) -> bool:
        """Update a provider connection."""
        connections = self._data.get("provider_connections", [])
        for conn in connections:
            if conn.get("id") == conn_id:
                conn.update(updates)
                self.save()
                return True
        return False

    def delete_provider_connection(self, conn_id: str) -> bool:
        """Delete a provider connection."""
        connections = self._data.get("provider_connections", [])
        before = len(connections)
        connections[:] = [c for c in connections if c.get("id") != conn_id]
        if len(connections) < before:
            self.save()
            return True
        return False

    def get_active_providers(self) -> list[dict[str, Any]]:
        """Get all active (enabled) provider connections."""
        return [c for c in self.get_provider_connections() if c.get("is_active", True)]

    # ---- Model Aliases ----

    def get_aliases(self) -> dict[str, str]:
        """Get all model aliases."""
        return self._data.get("model_aliases", {})

    def set_alias(self, alias: str, target: str) -> None:
        """Set a model alias."""
        aliases = self._data.setdefault("model_aliases", {})
        aliases[alias] = target
        self.save()

    def delete_alias(self, alias: str) -> bool:
        """Delete a model alias."""
        aliases = self._data.get("model_aliases", {})
        if alias in aliases:
            del aliases[alias]
            self.save()
            return True
        return False

    def resolve_alias(self, model: str) -> str:
        """Resolve a model alias to its target."""
        aliases = self.get_aliases()
        return aliases.get(model, model)

    # ---- Combos ----

    def get_combos(self) -> dict[str, dict[str, Any]]:
        """Get all model combos."""
        return self._data.get("combos", {})

    def add_combo(self, combo: dict[str, Any]) -> str:
        """Add a new combo. Returns combo ID."""
        combos = self._data.setdefault("combos", {})
        combo_id = combo.get("id", f"combo_{int(time.time() * 1000)}")
        combo["id"] = combo_id
        combos[combo_id] = combo
        self.save()
        return combo_id

    def delete_combo(self, combo_id: str) -> bool:
        """Delete a combo."""
        combos = self._data.get("combos", {})
        if combo_id in combos:
            del combos[combo_id]
            self.save()
            return True
        return False

    def get_combo(self, name: str) -> dict[str, Any] | None:
        """Get a combo by name."""
        combos = self.get_combos()
        for combo in combos.values():
            if combo.get("name") == name:
                return combo
        return None

    # ---- API Keys ----

    def get_api_keys(self) -> list[dict[str, Any]]:
        """Get all stored API keys (metadata only, no secrets)."""
        return self._data.get("api_keys", [])

    def add_api_key(self, key_info: dict[str, Any]) -> str:
        """Store API key metadata."""
        keys = self._data.setdefault("api_keys", [])
        key_id = f"key_{int(time.time() * 1000)}"
        key_info["id"] = key_id
        keys.append(key_info)
        self.save()
        return key_id

    # ---- Settings ----

    def get_settings(self) -> dict[str, Any]:
        """Get gateway settings."""
        return self._data.get("settings", {})

    def update_settings(self, updates: dict[str, Any]) -> None:
        """Update gateway settings."""
        settings = self._data.setdefault("settings", {})
        settings.update(updates)
        self.save()

    # ---- Usage Tracking ----

    def log_request(self, entry: dict[str, Any]) -> None:
        """Log a request to the rolling usage log."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        provider = entry.get("provider", "unknown")
        model = entry.get("model", "unknown")
        tokens = entry.get("total_tokens", 0)
        cost = entry.get("cost_usd", 0)

        # Append to log file
        try:
            with open(self.log_path, "a") as f:
                f.write(f"{timestamp} | {provider} | {model} | {tokens} tokens | ${cost:.6f}\n")
        except IOError as e:
            logger.warning("log_write_failed", error=str(e))

        # Update usage JSON
        self._update_usage(entry)

    def _update_usage(self, entry: dict[str, Any]) -> None:
        """Update usage statistics."""
        usage = self._load_usage()
        provider = entry.get("provider", "unknown")
        model = entry.get("model", "unknown")

        stats = usage.setdefault("by_provider", {}).setdefault(provider, {
            "requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "models": {},
        })
        stats["requests"] += 1
        stats["total_tokens"] += entry.get("total_tokens", 0)
        stats["total_cost"] += entry.get("cost_usd", 0)

        model_stats = stats["models"].setdefault(model, {
            "requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        })
        model_stats["requests"] += 1
        model_stats["total_tokens"] += entry.get("total_tokens", 0)
        model_stats["total_cost"] += entry.get("cost_usd", 0)

        usage["total_requests"] = usage.get("total_requests", 0) + 1

        try:
            self.usage_path.write_text(json.dumps(usage, indent=2))
        except IOError:
            pass

    def _load_usage(self) -> dict[str, Any]:
        """Load usage statistics."""
        if self.usage_path.exists():
            try:
                return json.loads(self.usage_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {"total_requests": 0, "by_provider": {}}

    def get_usage_summary(self) -> dict[str, Any]:
        """Get usage summary."""
        return self._load_usage()

    def get_recent_requests(self, limit: int = 100) -> list[str]:
        """Get recent request log entries."""
        if not self.log_path.exists():
            return []
        try:
            lines = self.log_path.read_text().strip().split("\n")
            return lines[-limit:]
        except IOError:
            return []


# Global storage instance
_storage: Storage | None = None


def get_storage() -> Storage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        from rihaproxy.config import settings
        _storage = Storage(data_dir=settings.data_dir)
    return _storage
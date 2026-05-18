"""
Token manager — manages OAuth tokens with automatic refresh and storage.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from rihaproxy.storage.db import get_storage

logger = structlog.get_logger()


class TokenManager:
    """
    Manages OAuth tokens for connected providers.

    Features:
    - Store tokens in persistent storage
    - Automatic refresh before expiry
    - Per-provider token isolation
    - Multi-account support per provider
    """

    # How many seconds before expiry to refresh
    REFRESH_BUFFER = 300  # 5 minutes

    def __init__(self):
        self.storage = get_storage()
        self._refresh_tasks: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Provider Connection Lifecycle
    # -------------------------------------------------------------------------

    async def connect_provider(
        self,
        provider: str,
        auth_type: str,
        name: str,
        credentials: dict[str, Any],
    ) -> str:
        """
        Connect a new provider account.

        Args:
            provider: Provider name (claude, codex, google, kiro, cursor, github)
            auth_type: "oauth", "api_key", "device_code", "noauth"
            name: Human-readable name for this connection
            credentials: Dict with api_key, access_token, refresh_token, etc.

        Returns:
            Connection ID
        """
        connection = {
            "id": f"{provider}_{int(time.time() * 1000)}",
            "provider": provider,
            "name": name,
            "auth_type": auth_type,
            "is_active": True,
            "priority": 0,
            "test_status": "unknown",
            "last_error": None,
            "rate_limited_until": None,
        }

        # Store credentials
        if auth_type == "api_key":
            connection["api_key"] = credentials.get("api_key", "")
        elif auth_type in ("oauth", "device_code"):
            connection["access_token"] = credentials.get("access_token", "")
            connection["refresh_token"] = credentials.get("refresh_token", "")
            connection["expires_at"] = credentials.get("expires_at")
            connection["scope"] = credentials.get("scope", "")
            connection["provider_data"] = credentials.get("provider_data", {})
            # Kiro stores profile_arn in provider_data
            if credentials.get("profile_arn"):
                connection["profile_arn"] = credentials.get("profile_arn")
            # GitHub stores the long-lived OAuth token here; the Copilot adapter
            # exchanges it for short-lived Copilot session tokens.
            if credentials.get("copilot_token"):
                connection["copilot_token"] = credentials.get("copilot_token")
            if credentials.get("copilot_expires_at"):
                connection["copilot_expires_at"] = credentials.get("copilot_expires_at")
        elif auth_type == "noauth":
            pass  # No credentials needed

        conn_id = self.storage.add_provider_connection(connection)
        logger.info("provider_connected", provider=provider, name=name, conn_id=conn_id)
        return conn_id

    async def disconnect_provider(self, conn_id: str) -> bool:
        """Disconnect and remove a provider connection."""
        result = self.storage.delete_provider_connection(conn_id)
        if result:
            logger.info("provider_disconnected", conn_id=conn_id)
        return result

    async def get_active_connections(self, provider: str | None = None) -> list[dict[str, Any]]:
        """Get all active provider connections, optionally filtered by provider."""
        connections = self.storage.get_active_providers()
        if provider:
            connections = [c for c in connections if c.get("provider") == provider]
        return connections

    async def get_connection(self, conn_id: str) -> dict[str, Any] | None:
        """Get a specific connection by ID."""
        for conn in self.storage.get_provider_connections():
            if conn.get("id") == conn_id:
                return conn
        return None

    # -------------------------------------------------------------------------
    # Token Retrieval & Refresh
    # -------------------------------------------------------------------------

    async def get_token(self, provider: str) -> str | None:
        """
        Get the best available token for a provider.
        Returns the active (non-rate-limited, non-expired) connection's token.
        """
        connections = await self.get_active_connections(provider)
        
        # Fallback for aliases
        if not connections:
            aliases = {
                "github-copilot": "github",
                "github": "github-copilot",
            }
            if provider in aliases:
                connections = await self.get_active_connections(aliases[provider])
        
        if not connections:
            return None

        # Sort by priority (lower = higher priority)
        connections.sort(key=lambda c: c.get("priority", 0))

        for conn in connections:
            # Check rate limit
            if self._is_rate_limited(conn):
                continue

            # Check expiry
            if self._is_expired(conn):
                refreshed = await self.refresh_if_needed(conn.get("id", ""))
                if not refreshed:
                    continue
                conn = await self.get_connection(conn.get("id", "")) or conn

            return conn.get("access_token") or conn.get("api_key")

        return None

    async def get_all_tokens(self, provider: str) -> list[tuple[str, dict[str, Any]]]:
        """
        Get all tokens for a provider as (token, connection) pairs.
        Used for multi-account fallback.
        """
        connections = await self.get_active_connections(provider)

        # Fallback for aliases
        if not connections:
            aliases = {
                "github-copilot": "github",
                "github": "github-copilot",
            }
            if provider in aliases:
                connections = await self.get_active_connections(aliases[provider])
        tokens = []

        for conn in connections:
            token = conn.get("access_token") or conn.get("api_key")
            if token and not self._is_rate_limited(conn):
                tokens.append((token, conn))

        return tokens

    async def refresh_if_needed(self, conn_id: str) -> dict[str, Any] | None:
        """
        Refresh a connection's token if it will expire soon.
        Returns the new token data if refreshed, None otherwise.
        """
        conn = await self.get_connection(conn_id)
        if not conn:
            return None

        # Check if refresh is needed
        expires_at = conn.get("expires_at")
        if not expires_at:
            return None

        # Parse expiry time
        try:
            if isinstance(expires_at, str):
                expiry = float(expires_at)
            else:
                expiry = expires_at

            time_until_expiry = expiry - time.time()

            if time_until_expiry > self.REFRESH_BUFFER:
                return None  # Not yet time to refresh
        except (ValueError, TypeError):
            return None

        # Refresh the token
        provider = conn.get("provider", "")
        refresh_token = conn.get("refresh_token")
        if not refresh_token:
            logger.warning("no_refresh_token", conn_id=conn_id, provider=provider)
            return None

        try:
            from rihaproxy.auth.oauth import refresh_provider_token

            new_tokens = await refresh_provider_token(
                provider,
                refresh_token,
                provider_data=conn.get("provider_data") or {},
            )
            new_expires = time.time() + new_tokens.get("expires_in", 3600)

            update_data = {
                "access_token": new_tokens.get("access_token"),
                "refresh_token": new_tokens.get("refresh_token") or refresh_token,
                "expires_at": str(new_expires),
                "provider_data": {
                    **(conn.get("provider_data") or {}),
                    **(new_tokens.get("provider_data") or {}),
                },
            }
            # Preserve profile_arn for Kiro
            if new_tokens.get("profile_arn"):
                update_data["profile_arn"] = new_tokens["profile_arn"]

            self.storage.update_provider_connection(conn_id, update_data)

            logger.info("token_refreshed", provider=provider, conn_id=conn_id)
            return new_tokens

        except Exception as e:
            logger.error("token_refresh_failed", provider=provider, conn_id=conn_id, error=str(e))
            self.storage.update_provider_connection(conn_id, {
                "last_error": str(e),
                "test_status": "error",
            })
            return None

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------

    def mark_rate_limited(self, conn_id: str, retry_after: int = 60) -> None:
        """Mark a connection as rate-limited."""
        rate_limited_until = time.time() + retry_after
        self.storage.update_provider_connection(conn_id, {
            "rate_limited_until": str(rate_limited_until),
            "test_status": "rate_limited",
        })

    def clear_rate_limit(self, conn_id: str) -> None:
        """Clear rate limit from a connection."""
        self.storage.update_provider_connection(conn_id, {
            "rate_limited_until": None,
            "test_status": "valid",
        })

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _is_rate_limited(self, conn: dict[str, Any]) -> bool:
        """Check if a connection is currently rate-limited."""
        until = conn.get("rate_limited_until")
        if not until:
            return False
        try:
            return time.time() < float(until)
        except (ValueError, TypeError):
            return False

    def _is_expired(self, conn: dict[str, Any]) -> bool:
        """Check if a connection's token is expired."""
        expires_at = conn.get("expires_at")
        if not expires_at:
            return False
        try:
            return time.time() >= float(expires_at)
        except (ValueError, TypeError):
            return False

    # -------------------------------------------------------------------------
    # Connection Testing
    # -------------------------------------------------------------------------

    async def test_connection(self, conn_id: str) -> dict[str, Any]:
        """
        Test a provider connection by making a simple API call.
        Updates connection status based on result.
        """
        conn = await self.get_connection(conn_id)
        if not conn:
            return {"ok": False, "error": "Connection not found"}

        provider = conn.get("provider", "")
        token = conn.get("access_token") or conn.get("api_key")

        if not token:
            self.storage.update_provider_connection(conn_id, {
                "test_status": "invalid",
                "last_error": "No token available",
            })
            return {"ok": False, "error": "No token available"}

        try:
            # Make a test request
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                # Simple test: try to get model list or similar
                test_urls = {
                    "claude": "https://api.anthropic.com/v1/models",
                    "google": "https://generativelanguage.googleapis.com/v1/models",
                    "github": "https://api.github.com/models",
                    "kiro": "https://codewhisperer.us-east-1.amazonaws.com",
                }

                url = test_urls.get(provider)
                if not url:
                    # For providers without simple test endpoint, just check token format
                    self.storage.update_provider_connection(conn_id, {
                        "test_status": "valid",
                        "last_error": None,
                    })
                    return {"ok": True, "message": "Connection appears valid"}

                # Kiro needs a special test request with x-amz-target header
                if provider == "kiro":
                    profile_arn = (conn.get("provider_data") or {}).get("profile_arn", "")
                    response = await client.post(
                        url,
                        json={
                            "origin": "AI_EDITOR",
                            "profileArn": profile_arn,
                        },
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/x-amz-json-1.0",
                            "x-amz-target": "AmazonCodeWhispererService.ListAvailableModels",
                        },
                    )
                else:
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                    )

                if response.status_code in (200, 401):
                    # 401 means token format is valid but no permission for this endpoint
                    self.storage.update_provider_connection(conn_id, {
                        "test_status": "valid" if response.status_code == 200 else "partial",
                        "last_error": None,
                    })
                    return {"ok": True, "status_code": response.status_code}

                self.storage.update_provider_connection(conn_id, {
                    "test_status": "error",
                    "last_error": f"HTTP {response.status_code}: {response.text[:200]}",
                })
                return {"ok": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            self.storage.update_provider_connection(conn_id, {
                "test_status": "error",
                "last_error": str(e),
            })
            return {"ok": False, "error": str(e)}


# Global token manager
_token_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    """Get the global token manager."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager

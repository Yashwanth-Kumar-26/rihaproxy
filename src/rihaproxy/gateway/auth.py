"""
Authentication middleware for the gateway.
Supports Bearer token (both AUTH_TOKEN and direct API key formats) and direct token passing.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rihaproxy.config import settings

# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)


class AuthResult:
    """Result of an authentication check."""

    __slots__ = ("token", "source", "valid")

    def __init__(self, token: str | None, source: str = "unknown", valid: bool = False):
        self.token = token
        self.source = source
        self.valid = valid


def extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def extract_direct_token(request: Request) -> str | None:
    """
    Extract direct API key/token forms used by SDKs and Claude Code wrappers.
    Also checks query params for clients that don't set headers.
    """
    # Header first. Starlette headers are case-insensitive, but the tests use
    # plain dicts, so keep the lookup list explicit.
    for header in (
        "x-api-key",
        "X-API-Key",
        "anthropic-auth-token",
        "Anthropic-Auth-Token",
        "x-anthropic-auth-token",
        "X-Anthropic-Auth-Token",
    ):
        key = request.headers.get(header)
        if key:
            return key.strip().strip('"').strip("'")

    # Some clients put a raw token in Authorization instead of Bearer.
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and not auth.lower().startswith("bearer "):
        return auth.strip().strip('"').strip("'")

    # Query param fallback (some SDKs use this)
    for param in ("api_key", "auth_token", "anthropic_auth_token"):
        key = request.query_params.get(param)
        if key:
            return key.strip().strip('"').strip("'")

    return None


def validate_token(token: str | None) -> AuthResult:
    """
    Validate a token against configured auth tokens.

    Returns AuthResult with valid=True if token is acceptable.
    """
    if token is None:
        return AuthResult(None, valid=False)
    token = token.strip().strip('"').strip("'")
    if not token:
        return AuthResult(token, valid=False)

    # Check against configured AUTH_TOKEN
    if settings.auth_token and token == settings.auth_token:
        return AuthResult(token, source="auth_token", valid=True)

    # Check against Anthropic-specific token
    if settings.anthropic_auth_token and token == settings.anthropic_auth_token:
        return AuthResult(token, source="anthropic_auth_token", valid=True)

    # Allow passthrough of actual provider API keys (when no gateway auth set)
    # These are validated downstream by the provider adapters
    provider_keys = [
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.openrouter_api_key,
        settings.deepseek_api_key,
        settings.nvidia_api_key,
        settings.google_api_key,
        settings.opencode_api_key,
    ]
    if token in (k for k in provider_keys if k):
        return AuthResult(token, source="provider_key", valid=True)

    # If no AUTH_TOKEN is configured, allow any non-empty token (passthrough mode)
    if not settings.auth_token and token:
        return AuthResult(token, source="passthrough", valid=True)

    return AuthResult(token, valid=False)


async def get_auth(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    request: Request = None,
) -> AuthResult:
    """
    FastAPI dependency for authentication.

    Tries multiple sources in order:
    1. Bearer token in Authorization header
    2. X-API-Key header
    3. ?api_key= query parameter

    Returns AuthResult with validation status.
    """
    if request is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object missing")

    # Try Bearer token first
    token = extract_bearer_token(request)
    if token:
        result = validate_token(token)
        if result.valid:
            return result

    # Try direct API key
    token = extract_direct_token(request)
    if token:
        result = validate_token(token)
        if result.valid:
            return result

    # No token provided — fail if auth is required
    if settings.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # No auth required — return empty valid result
    return AuthResult(None, source="none", valid=True)


# Convenience dependency for endpoints that need auth
RequireAuth = Annotated[AuthResult, Depends(get_auth)]
OptionalAuth = Annotated[AuthResult, Depends(get_auth)]

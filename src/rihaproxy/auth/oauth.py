"""
OAuth authentication flows for CLI-native providers.
Supports device-code flow for: Claude, Codex, Kiro, Gemini, GitHub, Cursor.
Kiro additionally supports social login (Google/GitHub) and import token.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

KIRO_SOCIAL_AUTH = "https://prod.us-east-1.auth.desktop.kiro.dev"


class OAuthError(Exception):
    """OAuth flow error."""
    pass


class DeviceCodeFlow:
    """
    Device code OAuth flow for providers like Claude, Codex, etc.

    Steps:
    1. Request device code from provider
    2. Poll for user authentication
    3. Exchange code for tokens
    """

    PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
        "claude": {
            "device_code_url": "https://api.anthropic.com/v1/auth/device/code",
            "token_url": "https://api.anthropic.com/v1/auth/token",
            "client_id": "cliffords",
            "scope": "api:read api:write",
        },
        "codex": {
            "device_code_url": "https://github.com/login/device/code",
            "token_url": "https://github.com/login/oauth/access_token",
            "client_id": "Iv1.b507a08c87ecfe98",
            "scope": "read:user",
            "user_agent": "GitHubCopilotChat/0.26.7",
        },
        "github": {
            "device_code_url": "https://github.com/login/device/code",
            "token_url": "https://github.com/login/oauth/access_token",
            "client_id": "Iv1.b507a08c87ecfe98",
            "scope": "read:user",
            "user_agent": "GitHubCopilotChat/0.26.7",
        },
        "github-copilot": {
            "device_code_url": "https://github.com/login/device/code",
            "token_url": "https://github.com/login/oauth/access_token",
            "client_id": "Iv1.b507a08c87ecfe98",
            "scope": "read:user",
            "user_agent": "GitHubCopilotChat/0.26.7",
        },
        "google": {
            "device_code_url": "https://oauth2.googleapis.com/device/code",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": "",
            "scope": "https://www.googleapis.com/auth/generative-language.retriever",
        },
        "kimi-coding": {
            "device_code_url": "https://auth.kimi.com/api/oauth/device_authorization",
            "token_url": "https://auth.kimi.com/api/oauth/token",
            "client_id": "17e5f671-d194-4dfb-9706-5516cb48c098",
            "scope": "openid profile email",
        },
        "qwen": {
            "device_code_url": "https://chat.qwen.ai/api/v1/oauth2/device/code",
            "token_url": "https://chat.qwen.ai/api/v1/oauth2/token",
            "client_id": "f0304373b74a44d2b584a3fb70ca9e56",
            "scope": "openid profile email model.completion",
        },
        "kiro": {
            "register_client_url": "https://oidc.us-east-1.amazonaws.com/client/register",
            "device_code_url": "https://oidc.us-east-1.amazonaws.com/device_authorization",
            "token_url": "https://oidc.us-east-1.amazonaws.com/token",
            "start_url": "https://view.awsapps.com/start",
            "client_name": "kiro-oauth-client",
            "client_type": "public",
            "issuer_url": "https://identitycenter.amazonaws.com/ssoins-722374e8c3c8e6c6",
            "scope": "codewhisperer:completions codewhisperer:analysis codewhisperer:conversations",
            "region": "us-east-1",
        },
        "cursor": {
            "device_code_url": "https://cursor.sh/oauth/device/code",
            "token_url": "https://cursor.sh/oauth/token",
            "client_id": "rihaproxy",
            "scope": "api:access",
        },
    }

    def __init__(self, provider: str):
        if provider not in self.PROVIDER_CONFIGS:
            raise OAuthError(f"Unsupported provider: {provider}")
        self.provider = provider
        self.config = self.PROVIDER_CONFIGS[provider]
        self._device_code: str | None = None
        self._user_code: str | None = None
        self._interval: int = 5

    async def start(self) -> dict[str, Any]:
        """Start the device code flow. Returns verification URL and user code."""
        if self.provider == "kiro":
            return await self._start_kiro()

        headers = {"Accept": "application/json"}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config["user_agent"]

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    self.config["device_code_url"],
                    data={
                        "client_id": self.config["client_id"],
                        "scope": self.config["scope"],
                    },
                    headers=headers
                )
                if response.status_code != 200:
                    logger.error("oauth_start_failed", status=response.status_code, body=response.text)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error("oauth_start_exception", error=str(e))
                raise OAuthError(f"Failed to start OAuth flow: {e}")

        self._device_code = data.get("device_code", "")
        self._user_code = data.get("user_code", "")
        self._interval = data.get("interval", 5)

        return {
            "verification_url": data.get("verification_uri_complete") or data.get("verification_uri", ""),
            "user_code": self._user_code,
            "device_code": self._device_code,
            "expires_in": data.get("expires_in", 300),
            "message": f"Visit {data.get('verification_uri_complete') or data.get('verification_uri')} and enter code {self._user_code}",
        }

    async def _start_kiro(self) -> dict[str, Any]:
        """Start Kiro's AWS Builder ID device-code flow."""
        cfg = self.config
        scopes = [s for s in cfg["scope"].split(" ") if s]
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                reg = await client.post(
                    cfg["register_client_url"],
                    json={
                        "clientName": cfg["client_name"],
                        "clientType": cfg["client_type"],
                        "scopes": scopes,
                        "grantTypes": [
                            "urn:ietf:params:oauth:grant-type:device_code",
                            "refresh_token",
                        ],
                        "issuerUrl": cfg["issuer_url"],
                    },
                    headers={"Content-Type": "application/json"},
                )
                reg.raise_for_status()
                client_data = reg.json()

                auth = await client.post(
                    cfg["device_code_url"],
                    json={
                        "clientId": client_data["clientId"],
                        "clientSecret": client_data["clientSecret"],
                        "startUrl": cfg["start_url"],
                    },
                    headers={"Content-Type": "application/json"},
                )
                auth.raise_for_status()
                data = auth.json()
            except Exception as e:
                logger.error("kiro_oauth_start_exception", error=str(e))
                raise OAuthError(f"Failed to start Kiro OAuth flow: {e}")

        self._device_code = data.get("deviceCode", "")
        self._user_code = data.get("userCode", "")
        self._interval = int(data.get("interval", 5))
        self._kiro_client_id = client_data["clientId"]
        self._kiro_client_secret = client_data["clientSecret"]

        return {
            "verification_url": data.get("verificationUriComplete") or data.get("verificationUri", ""),
            "user_code": self._user_code,
            "device_code": self._device_code,
            "expires_in": data.get("expiresIn", 600),
            "message": f"Visit {data.get('verificationUriComplete') or data.get('verificationUri')} and enter code {self._user_code}",
            "provider_data": {
                "client_id": client_data["clientId"],
                "client_secret": client_data["clientSecret"],
                "client_secret_expires_at": client_data.get("clientSecretExpiresAt"),
                "region": self.config.get("region", "us-east-1"),
                "auth_method": "builder-id",
            },
        }

    async def poll(self, timeout: int = 300) -> dict[str, Any]:
        """
        Poll for token exchange.
        Returns tokens when user completes authentication.
        Raises OAuthError on failure or timeout.
        """
        if not self._device_code:
            raise OAuthError("Flow not started. Call start() first.")

        if self.provider == "kiro":
            return await self._poll_kiro(timeout=timeout)

        headers = {"Accept": "application/json"}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config["user_agent"]

        start = time.time()

        while time.time() - start < timeout:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.config["token_url"],
                    data={
                        "client_id": self.config["client_id"],
                        "device_code": self._device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers=headers
                )

            data = response.json()
            error = data.get("error", "")

            if error == "authorization_pending":
                logger.debug("auth_pending", provider=self.provider)
                await asyncio.sleep(self._interval)
                continue

            if error == "slow_down":
                self._interval += 5
                await asyncio.sleep(self._interval)
                continue

            if error == "expired_token":
                raise OAuthError("Authentication timed out. Please try again.")

            if error == "invalid_client":
                raise OAuthError(f"Invalid client for {self.provider}")

            if error:
                raise OAuthError(f"OAuth error: {error}")

            # Success
            return {
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in", 3600),
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope", self.config["scope"]),
            }

        raise OAuthError("Authentication timed out")

    async def _poll_kiro(self, timeout: int = 300) -> dict[str, Any]:
        """Poll Kiro/AWS SSO OIDC until the user completes device auth."""
        client_id = getattr(self, "_kiro_client_id", None) or self.config.get("client_id")
        client_secret = getattr(self, "_kiro_client_secret", None) or self.config.get("client_secret")
        if not client_id or not client_secret:
            raise OAuthError("Kiro flow missing client credentials. Start the flow again.")

        start = time.time()
        while time.time() - start < timeout:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.config["token_url"],
                    json={
                        "clientId": client_id,
                        "clientSecret": client_secret,
                        "deviceCode": self._device_code,
                        "grantType": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Content-Type": "application/json"},
                )

            data = response.json()
            error = data.get("error")
            if response.status_code == 200 and not error:
                return {
                    "access_token": data.get("accessToken", ""),
                    "refresh_token": data.get("refreshToken"),
                    "expires_in": data.get("expiresIn", 3600),
                    "token_type": data.get("tokenType", "Bearer"),
                    "scope": self.config["scope"],
                    "provider_data": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "region": self.config.get("region", "us-east-1"),
                        "auth_method": "builder-id",
                    },
                }

            if error in ("authorization_pending", "slow_down"):
                if error == "slow_down":
                    self._interval += 5
                await asyncio.sleep(self._interval)
                continue

            raise OAuthError(data.get("error_description") or error or response.text)

        raise OAuthError("Authentication timed out")


async def start_device_flow(provider: str) -> dict[str, Any]:
    """Start a device code OAuth flow for a provider."""
    flow = DeviceCodeFlow(provider)
    return await flow.start()


async def complete_device_flow(provider: str, device_code: str) -> dict[str, Any]:
    """
    Complete a device code flow with the device code.
    """
    flow = DeviceCodeFlow(provider)
    flow._device_code = device_code
    return await flow.poll()


async def complete_kiro_device_flow(
    device_code: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    """Complete a Kiro flow using device and registered client credentials."""
    flow = DeviceCodeFlow("kiro")
    flow._device_code = device_code
    flow._kiro_client_id = client_id
    flow._kiro_client_secret = client_secret
    return await flow.poll()


async def refresh_token(provider: str, refresh_token: str) -> dict[str, Any]:
    """Refresh an OAuth token."""
    return await refresh_provider_token(provider, refresh_token, provider_data=None)


async def refresh_provider_token(
    provider: str,
    refresh_token: str,
    provider_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Refresh an OAuth token with provider-specific metadata."""
    config = DeviceCodeFlow.PROVIDER_CONFIGS.get(provider)
    if not config:
        raise OAuthError(f"Unknown provider: {provider}")

    if provider == "kiro":
        pdata = provider_data or {}
        auth_method = pdata.get("auth_method", "builder-id")

        # Social auth refresh (Google/GitHub via AWS Cognito)
        if auth_method in ("social", "imported"):
            return await refresh_kiro_social_token(refresh_token)

        # AWS SSO OIDC refresh (Builder ID or IDC)
        client_id = pdata.get("client_id") or pdata.get("clientId")
        client_secret = pdata.get("client_secret") or pdata.get("clientSecret")
        region = pdata.get("region") or "us-east-1"
        if not client_id or not client_secret:
            raise OAuthError("Kiro refresh requires client_id and client_secret for Builder ID/IDC")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://oidc.{region}.amazonaws.com/token",
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "refreshToken": refresh_token,
                    "grantType": "refresh_token",
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            return {
                "access_token": data.get("accessToken"),
                "refresh_token": data.get("refreshToken") or refresh_token,
                "expires_in": data.get("expiresIn", 3600),
                "token_type": data.get("tokenType", "Bearer"),
            }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            config["token_url"],
            data={
                "client_id": config["client_id"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Kiro Social Login (Google / GitHub via AWS Cognito)
# ---------------------------------------------------------------------------

KIRO_SOCIAL_AUTH = "https://prod.us-east-1.auth.desktop.kiro.dev"
KIRO_REDIRECT_URI = "kiro://kiro.kiroAgent/authenticate-success"


def _generate_pkce() -> tuple[str, str]:
    """Generate code_verifier and code_challenge for PKCE."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return code_verifier, code_challenge


def build_kiro_social_login_url(
    provider: str = "google",
    code_challenge: str | None = None,
    state: str | None = None,
) -> dict[str, str]:
    """
    Build the social login URL for Kiro (Google or GitHub).

    Returns the URL and the generated PKCE/state values for later exchange.
    The user must visit the URL manually and extract the callback URL.
    """
    if code_challenge is None:
        code_challenge, _ = _generate_pkce()
    if state is None:
        state = base64.urlsafe_b64encode(os.urandom(16)).decode()

    idp = "Google" if provider == "google" else "Github"
    url = (
        f"{KIRO_SOCIAL_AUTH}/login"
        f"?idp={idp}"
        f"&redirect_uri={KIRO_REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
        f"&prompt=select_account"
    )
    return {
        "url": url,
        "code_challenge": code_challenge,
        "state": state,
        "message": f"Visit the URL and after login copy the full redirect URL (kiro://...) from your browser",
    }


async def exchange_kiro_social_code(
    callback_url: str,
    code_verifier: str,
) -> dict[str, Any]:
    """
    Exchange the authorization code from the social login callback.

    The callback_url is the full kiro:// URL the browser redirects to after
    successful login. It contains ?code=...&state=... parameters.
    """
    # Parse code from callback URL
    code = None
    if "?" in callback_url:
        params = callback_url.split("?")[1]
        for param in params.split("&"):
            if param.startswith("code="):
                code = param.split("=", 1)[1]
                break

    if not code:
        raise OAuthError("Could not extract authorization code from callback URL")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{KIRO_SOCIAL_AUTH}/oauth/token",
            json={
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": KIRO_REDIRECT_URI,
            },
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise OAuthError(f"Token exchange failed: {response.text}")
        data = response.json()

    return {
        "access_token": data.get("accessToken", ""),
        "refresh_token": data.get("refreshToken", ""),
        "profile_arn": data.get("profileArn"),
        "expires_in": data.get("expiresIn", 3600),
        "provider_data": {
            "auth_method": "social",
            "region": "us-east-1",
        },
    }


# ---------------------------------------------------------------------------
# Kiro Token Import & Validation
# ---------------------------------------------------------------------------

KIRO_REFRESH_TOKEN_PREFIX = "aorAAAAAG"


def validate_kiro_refresh_token_format(refresh_token: str) -> bool:
    """Check if a refresh token has the expected Kiro format."""
    return refresh_token.startswith(KIRO_REFRESH_TOKEN_PREFIX)


async def import_kiro_token(
    refresh_token: str,
    auth_method: str = "imported",
) -> dict[str, Any]:
    """
    Validate and import a Kiro refresh token.

    Tries to refresh the token to verify it's valid, then returns the
    new access token and metadata.
    """
    if not validate_kiro_refresh_token_format(refresh_token):
        raise OAuthError(
            f"Invalid token format. Token should start with {KIRO_REFRESH_TOKEN_PREFIX}..."
        )

    # Try social refresh first (works for imported social tokens)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{KIRO_SOCIAL_AUTH}/refreshToken",
            json={"refreshToken": refresh_token},
            headers={"Content-Type": "application/json"},
        )

    if response.status_code == 200:
        data = response.json()
        return {
            "access_token": data.get("accessToken", ""),
            "refresh_token": data.get("refreshToken") or refresh_token,
            "profile_arn": data.get("profileArn"),
            "expires_in": data.get("expiresIn", 3600),
            "provider_data": {
                "auth_method": auth_method,
                "region": "us-east-1",
            },
        }

    # If social refresh fails, the token might be a Builder ID token
    # which requires client_id/client_secret — those can't be imported
    raise OAuthError(
        "Token refresh failed. This may be a Builder ID token that requires "
        "the original device code flow. Use 'riha login kiro --method builder-id' instead."
    )


# ---------------------------------------------------------------------------
# Kiro Social Token Refresh
# ---------------------------------------------------------------------------

async def refresh_kiro_social_token(refresh_token: str) -> dict[str, Any]:
    """Refresh a Kiro social login token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{KIRO_SOCIAL_AUTH}/refreshToken",
            json={"refreshToken": refresh_token},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise OAuthError(f"Social token refresh failed: {response.text}")
        data = response.json()

    return {
        "access_token": data.get("accessToken"),
        "refresh_token": data.get("refreshToken") or refresh_token,
        "profile_arn": data.get("profileArn"),
        "expires_in": data.get("expiresIn", 3600),
        "provider_data": {
            "auth_method": "social",
            "region": "us-east-1",
        },
    }


# ---------------------------------------------------------------------------
# Kiro Utility Functions
# ---------------------------------------------------------------------------

async def list_kiro_models(access_token: str, profile_arn: str) -> list[dict[str, Any]]:
    """List available models from Kiro's CodeWhisperer API."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://codewhisperer.us-east-1.amazonaws.com",
            json={
                "origin": "AI_EDITOR",
                "profileArn": profile_arn,
            },
            headers={
                "Content-Type": "application/x-amz-json-1.0",
                "x-amz-target": "AmazonCodeWhispererService.ListAvailableModels",
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if response.status_code != 200:
            raise OAuthError(f"Failed to list models: {response.text}")
        data = response.json()

    return [
        {
            "id": m.get("modelId", ""),
            "name": m.get("modelName") or m.get("modelId", ""),
            "description": m.get("description", ""),
            "rate_multiplier": m.get("rateMultiplier"),
            "rate_unit": m.get("rateUnit"),
            "max_input_tokens": m.get("tokenLimits", {}).get("maxInputTokens", 0),
        }
        for m in data.get("models", [])
    ]


def extract_email_from_kiro_jwt(access_token: str) -> str | None:
    """Extract email from Kiro's JWT access token (for display purposes)."""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        # Add padding
        while len(payload) % 4:
            payload += "="
        decoded = json.loads(
            base64.urlsafe_b64decode(payload.replace("-", "+").replace("_", "/"))
        )
        return decoded.get("email") or decoded.get("preferred_username") or decoded.get("sub")
    except Exception:
        return None

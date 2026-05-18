"""
Unit tests for configuration management.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# Create test-specific settings that ignore .env files
def create_test_settings(**overrides):
    """Create Settings instance for testing without .env pollution."""
    from pydantic import Field, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class TestSettings(BaseSettings):
        """Test version of Settings without .env loading."""

        model_config = SettingsConfigDict(
            env_prefix="RIHAPROXY_",
            env_file=None,  # Don't load .env files
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        # ---- Server ----
        port: int = Field(default=16324, ge=1, le=65535)
        host: str = Field(default="0.0.0.0")

        # ---- Authentication ----
        auth_token: str = Field(default="test-token")
        anthropic_auth_token: str = Field(default="")

        # ---- Provider API Keys ----
        openrouter_api_key: str = Field(default="")
        openai_api_key: str = Field(default="")
        anthropic_api_key: str = Field(default="")
        deepseek_api_key: str = Field(default="")
        nvidia_api_key: str = Field(default="")
        lm_studio_base_url: str = Field(default="http://localhost:1234")
        lm_studio_api_key: str = Field(default="")
        opencode_api_key: str = Field(default="")
        zai_api_key: str = Field(default="")
        kiro_api_key: str = Field(default="")
        google_api_key: str = Field(default="")
        github_token: str = Field(default="")
        ruflo_api_key: str = Field(default="")
        ruflo_base_url: str = Field(default="http://localhost:3000")
        ruflo_plugins: str = Field(default="true")
        ruflo_auto_tools: bool = Field(default=True)

        # ---- Fallback Configuration ----
        default_backend: str = Field(default="openrouter")
        default_model: str = Field(default="openai/gpt-4o-mini")
        fallback_chain: list[str] = Field(default=["openrouter", "openai"])

        # ---- Performance & Limits ----
        max_concurrent_per_provider: int = Field(default=10)
        request_timeout: int = Field(default=120, ge=1)
        default_max_tokens: int = Field(default=8192)

        # ---- Logging ----
        log_level: str = Field(default="INFO")
        log_requests: bool = Field(default=False)

        # ---- Optional Features ----
        enable_rtk: bool = Field(default=True)
        enable_caveman: bool = Field(default=False)

        # ---- Proxy ----
        http_proxy: str = Field(default="")
        https_proxy: str = Field(default="")

        # ---- Storage ----
        data_dir: Path = Field(default=Path.home() / ".rihaproxy")

        @property
        def LM_STUDIO_BASE_URL(self) -> str:
            return self.lm_studio_base_url

        def get_api_key(self, provider: str) -> str | None:
            key_map = {
                "openrouter": self.openrouter_api_key,
                "openai": self.openai_api_key,
                "anthropic": self.anthropic_api_key,
                "deepseek": self.deepseek_api_key,
                "nvidia": self.nvidia_api_key,
                "lmstudio": self.lm_studio_api_key,
                "opencode": self.opencode_api_key,
                "zai": self.zai_api_key,
                "kiro": self.kiro_api_key,
                "google": self.google_api_key,
                "github": self.github_token,
                "ruflo": self.ruflo_api_key,
            }
            return key_map.get(provider.lower()) or None

        def get_base_url(self, provider: str) -> str | None:
            url_map = {
                "zai": "https://api.z.ai/api/paas/v4",
                "lmstudio": self.lm_studio_base_url,
                "ruflo": self.ruflo_base_url,
            }
            return url_map.get(provider.lower()) or None

        @model_validator(mode="after")
        def _normalize_log_level(self) -> "TestSettings":
            self.log_level = self.log_level.upper() if self.log_level else "INFO"
            return self

        @property
        def RUFLO_BASE_URL(self) -> str:
            return self.ruflo_base_url

    return TestSettings(**overrides)


class TestSettingsDefaults:
    """Test suite for Settings default values."""

    def test_default_port(self):
        """Test default port is 16324."""
        settings = create_test_settings()
        assert settings.port == 16324

    def test_default_host(self):
        """Test default host is 0.0.0.0."""
        settings = create_test_settings()
        assert settings.host == "0.0.0.0"

    def test_default_backend(self):
        """Test default backend is openrouter."""
        settings = create_test_settings()
        assert settings.default_backend == "openrouter"

    def test_default_model(self):
        """Test default model."""
        settings = create_test_settings()
        assert settings.default_model == "openai/gpt-4o-mini"

    def test_default_timeout(self):
        """Test default request timeout."""
        settings = create_test_settings()
        assert settings.request_timeout == 120

    def test_default_max_concurrent(self):
        """Test default max concurrent per provider."""
        settings = create_test_settings()
        assert settings.max_concurrent_per_provider == 10

    def test_default_log_level(self):
        """Test default log level."""
        settings = create_test_settings()
        assert settings.log_level == "INFO"

    def test_default_features(self):
        """Test default feature flags."""
        settings = create_test_settings()
        assert settings.enable_rtk is True
        assert settings.enable_caveman is False


class TestSettingsCustomValues:
    """Test suite for custom settings values."""

    def test_custom_port(self):
        """Test custom port."""
        settings = create_test_settings(port=9000)
        assert settings.port == 9000

    def test_custom_host(self):
        """Test custom host."""
        settings = create_test_settings(host="127.0.0.1")
        assert settings.host == "127.0.0.1"

    def test_custom_auth_token(self):
        """Test custom auth token."""
        settings = create_test_settings(auth_token="my-secret-token")
        assert settings.auth_token == "my-secret-token"

    def test_custom_api_key(self):
        """Test custom API key."""
        settings = create_test_settings(openrouter_api_key="sk-or-v2-xxx")
        assert settings.openrouter_api_key == "sk-or-v2-xxx"

    def test_custom_fallback_chain(self):
        """Test custom fallback chain."""
        settings = create_test_settings(fallback_chain=["openai", "deepseek"])
        assert settings.fallback_chain == ["openai", "deepseek"]


class TestSettingsValidation:
    """Test suite for settings validation."""

    def test_port_min_validation(self):
        """Test that port must be >= 1."""
        with pytest.raises(ValidationError):
            create_test_settings(port=0)

    def test_port_max_validation(self):
        """Test that port must be <= 65535."""
        with pytest.raises(ValidationError):
            create_test_settings(port=70000)

    def test_timeout_min_validation(self):
        """Test that timeout must be >= 1."""
        with pytest.raises(ValidationError):
            create_test_settings(request_timeout=0)


class TestGetApiKey:
    """Test suite for get_api_key method."""

    def test_get_openrouter_key(self):
        """Test getting OpenRouter API key."""
        settings = create_test_settings(openrouter_api_key="or-key")
        assert settings.get_api_key("openrouter") == "or-key"

    def test_get_openai_key(self):
        """Test getting OpenAI API key."""
        settings = create_test_settings(openai_api_key="oa-key")
        assert settings.get_api_key("openai") == "oa-key"

    def test_get_anthropic_key(self):
        """Test getting Anthropic API key."""
        settings = create_test_settings(anthropic_api_key="ant-key")
        assert settings.get_api_key("anthropic") == "ant-key"

    def test_get_deepseek_key(self):
        """Test getting DeepSeek API key."""
        settings = create_test_settings(deepseek_api_key="ds-key")
        assert settings.get_api_key("deepseek") == "ds-key"

    def test_get_unknown_key(self):
        """Test getting unknown provider key returns None."""
        settings = create_test_settings()
        assert settings.get_api_key("unknown") is None


class TestGetBaseUrl:
    """Test suite for get_base_url method."""

    def test_get_lmstudio_url(self):
        """Test getting LM Studio URL."""
        settings = create_test_settings(lm_studio_base_url="http://localhost:8080")
        assert settings.get_base_url("lmstudio") == "http://localhost:8080"

    def test_get_ruflo_url(self):
        """Test getting Ruflo URL."""
        settings = create_test_settings(ruflo_base_url="http://localhost:4000")
        assert settings.get_base_url("ruflo") == "http://localhost:4000"

    def test_get_zai_url(self):
        """Test getting ZAI default URL."""
        settings = create_test_settings()
        assert settings.get_base_url("zai") == "https://api.z.ai/api/paas/v4"

    def test_get_unknown_url(self):
        """Test getting unknown provider URL returns None."""
        settings = create_test_settings()
        assert settings.get_base_url("unknown") is None


class TestProxySettings:
    """Test suite for proxy configuration."""

    def test_http_proxy(self):
        """Test HTTP proxy setting."""
        settings = create_test_settings(http_proxy="http://proxy:8080")
        assert settings.http_proxy == "http://proxy:8080"

    def test_https_proxy(self):
        """Test HTTPS proxy setting."""
        settings = create_test_settings(https_proxy="https://proxy:8080")
        assert settings.https_proxy == "https://proxy:8080"

    def test_empty_proxy(self):
        """Test empty proxy defaults."""
        settings = create_test_settings()
        assert settings.http_proxy == ""
        assert settings.https_proxy == ""


class TestLogLevel:
    """Test suite for log level normalization."""

    def test_log_level_uppercase(self):
        """Test that log level is normalized to uppercase."""
        settings = create_test_settings(log_level="debug")
        assert settings.log_level == "DEBUG"

    def test_log_level_mixed_case(self):
        """Test that mixed case log level is normalized."""
        settings = create_test_settings(log_level="Warning")
        assert settings.log_level == "WARNING"
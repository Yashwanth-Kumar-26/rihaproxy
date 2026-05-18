"""
Application settings loaded from environment variables.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RihaProxy application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Server ----
    port: int = Field(default=16324, ge=1, le=65535, description="Server port")
    host: str = Field(default="0.0.0.0", description="Server host")

    # ---- Authentication ----
    auth_token: str = Field(default="", alias="AUTH_TOKEN", description="Bearer token")
    anthropic_auth_token: str = Field(default="", alias="ANTHROPIC_AUTH_TOKEN")

    @field_validator("auth_token", mode="before")
    @classmethod
    def _ensure_auth_token(cls, v: str) -> str:
        if not v:
            return secrets.token_urlsafe(32)
        return v

    # ---- Provider API Keys ----
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    lm_studio_base_url: str = Field(default="http://localhost:1234", alias="LM_STUDIO_BASE_URL")
    lm_studio_api_key: str = Field(default="", alias="LM_STUDIO_API_KEY")
    opencode_api_key: str = Field(default="", alias="OPENCODE_API_KEY")
    zai_api_key: str = Field(default="", alias="ZAI_API_KEY")
    kiro_api_key: str = Field(default="", alias="KIRO_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    ruflo_api_key: str = Field(default="", alias="RUFLO_API_KEY")
    ruflo_base_url: str = Field(default="http://localhost:3000", alias="RUFLO_BASE_URL")
    ruflo_plugins: str = Field(default="true", alias="RUFLO_PLUGINS")
    ruflo_auto_tools: bool = Field(default=True, alias="RUFLO_AUTO_TOOLS")

    # ---- Fallback Configuration ----
    default_backend: str = Field(default="openrouter", alias="DEFAULT_BACKEND")
    default_model: str = Field(default="openai/gpt-4o-mini", alias="DEFAULT_MODEL")
    fallback_chain: list[str] = Field(default=["openrouter", "openai"], alias="FALLBACK_CHAIN")

    @field_validator("fallback_chain", mode="before")
    @classmethod
    def _parse_fallback_chain(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return list(v) if v else []

    # ---- Performance & Limits ----
    max_concurrent_per_provider: int = Field(default=10, alias="MAX_CONCURRENT_PER_PROVIDER")
    request_timeout: int = Field(default=120, ge=1, description="Request timeout in seconds")
    default_max_tokens: int = Field(default=8192, alias="DEFAULT_MAX_TOKENS")

    # ---- Storage ----
    data_dir: Path = Field(default=Path.home() / ".rihaproxy", alias="DATA_DIR")

    @field_validator("data_dir", mode="before")
    @classmethod
    def _resolve_data_dir(cls, v):
        if isinstance(v, str):
            return Path(v)
        return Path.home() / ".rihaproxy"

    # ---- Logging ----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_requests: bool = Field(default=False, alias="LOG_REQUESTS")

    # ---- Optional Features ----
    enable_rtk: bool = Field(default=True, alias="ENABLE_RTK")
    enable_caveman: bool = Field(default=False, alias="ENABLE_CAVEMAN")

    # ---- Proxy ----
    http_proxy: str = Field(default="", alias="HTTP_PROXY")
    https_proxy: str = Field(default="", alias="HTTPS_PROXY")

    # ---- Cloud Sync (future) ----
    cloud_sync_url: str = Field(default="", alias="CLOUD_SYNC_URL")
    cloud_sync_token: str = Field(default="", alias="CLOUD_SYNC_TOKEN")

    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider."""
        provider = provider.lower()
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
            "gemini": self.google_api_key,
            "github": self.github_token,
            "ruflo": self.ruflo_api_key,
        }
        # Try generic env variable: PROVIDER_NAME_API_KEY
        val = key_map.get(provider)
        if val:
            return val
        
        env_name = f"{provider.upper().replace('-', '_')}_API_KEY"
        return os.getenv(env_name)

    def get_base_url(self, provider: str) -> str | None:
        """Get base URL for a provider."""
        url_map = {
            "zai": "https://api.z.ai/api/paas/v4",
            "lmstudio": self.lm_studio_base_url,
            "ruflo": self.ruflo_base_url,
            "nvidia": "https://integrate.api.nvidia.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "mistral": "https://api.mistral.ai/v1",
            "perplexity": "https://api.perplexity.ai",
            "fireworks": "https://api.fireworks.ai/inference/v1",
            "xai": "https://api.x.ai/v1",
            "deepseek": "https://api.deepseek.com",
            "hyperbolic": "https://api.hyperbolic.xyz/v1",
            "siliconflow": "https://api.siliconflow.cn/v1",
            "nebius": "https://api.studio.nebius.ai/v1",
            "cerebras": "https://api.cerebras.ai/v1",
            "blackbox": "https://api.blackbox.ai/v1",
            "chutes": "https://api.chutes.ai/v1",
            "opencode": "https://opencode.ai/zen/v1",
            "kimi": "https://api.moonshot.cn/v1",
            "minimax": "https://api.minimax.chat/v1",
            "alicode": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "glm": "https://open.bigmodel.cn/api/paas/v4",
            "voyage-ai": "https://api.voyageai.com/v1",
            "tavily": "https://api.tavily.com",
            "jina-ai": "https://api.jina.ai/v1",
            "serper": "https://google.serper.dev",
            "exa": "https://api.exa.ai",
            "firecrawl": "https://api.firecrawl.dev/v1",
            "fal-ai": "https://queue.fal.run",
            "stability-ai": "https://api.stability.ai/v1",
        }
        return url_map.get(provider.lower()) or None

    @model_validator(mode="after")
    def _normalize_log_level(self) -> Settings:
        self.log_level = self.log_level.upper() if self.log_level else "INFO"
        return self


# Global settings instance
settings = Settings()
"""
Format registry for request/response translation.
Defines supported source and target formats.
"""

from __future__ import annotations

from enum import Enum


class SourceFormat(str, Enum):
    """Detected source request formats."""
    OPENAI = "openai"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    VERTEX = "vertex"


class TargetFormat(str, Enum):
    """Target provider formats."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GEMINI_CLI = "gemini-cli"
    ANTGRAVITY = "antigravity"
    KIRO = "kiro"
    CODEX = "codex"
    CURSOR = "cursor"
    VERTEX = "vertex"
    OLLAMA = "ollama"


# Format metadata
FORMAT_INFO: dict[str, dict[str, bool | str]] = {
    "openai": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": True,
        "endpoint": "/v1/chat/completions",
        "auth_type": "bearer",
    },
    "anthropic": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1/messages",
        "auth_type": "bearer",
    },
    "gemini": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1beta/models/{model}:generateContent",
        "auth_type": "bearer",
    },
    "gemini-cli": {
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1beta/models/{model}:streamGenerateContent",
        "auth_type": "bearer",
    },
    "antigravity": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1/messages/stream",
        "auth_type": "bearer",
    },
    "kiro": {
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1/messages",
        "auth_type": "bearer",
    },
    "codex": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1/chat/completions",
        "auth_type": "bearer",
    },
    "cursor": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/api/chat/agent/chat",
        "auth_type": "bearer",
    },
    "vertex": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1beta/publishers/google/models/{model}:predict",
        "auth_type": "bearer",
    },
    "ollama": {
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/api/chat",
        "auth_type": "noauth",
    },
    "openai-responses": {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": False,
        "endpoint": "/v1/responses",
        "auth_type": "bearer",
    },
}


def detect_source_format(body: dict) -> str:
    """
    Detect source format from request body shape.
    Returns a SourceFormat value.
    """
    # OpenAI Responses format: has "model" and "input"
    if "input" in body and "model" in body and "messages" not in body:
        return SourceFormat.OPENAI_RESPONSES

    # Gemini format: has "contents" (not "messages")
    if "contents" in body:
        return SourceFormat.GEMINI

    if "messages" in body:
        if str(body.get("model", "")).lower().startswith("claude") and "max_tokens" in body:
            return SourceFormat.ANTHROPIC
        if "system" in body:
            return SourceFormat.ANTHROPIC
        for msg in body.get("messages", []):
            content = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(content, list):
                block_types = {
                    block.get("type")
                    for block in content
                    if isinstance(block, dict)
                }
                if block_types & {"tool_use", "tool_result", "image"}:
                    return SourceFormat.ANTHROPIC
                model = str(body.get("model", "")).lower()
                if model.startswith("claude"):
                    return SourceFormat.ANTHROPIC
        # Default messages[] to OpenAI; OpenAI commonly uses max_tokens too.
        return SourceFormat.OPENAI

    return SourceFormat.OPENAI


def format_supports_tools(fmt: str) -> bool:
    """Check if a format supports tool/function calling."""
    info = FORMAT_INFO.get(fmt, {})
    return info.get("supports_tools", False)


def format_supports_streaming(fmt: str) -> bool:
    """Check if a format supports streaming."""
    info = FORMAT_INFO.get(fmt, {})
    return info.get("supports_streaming", True)


def format_supports_vision(fmt: str) -> bool:
    """Check if a format supports vision/multimodal."""
    info = FORMAT_INFO.get(fmt, {})
    return info.get("supports_vision", False)


def get_endpoint(fmt: str, model: str | None = None) -> str:
    """Get API endpoint for a format, substituting model name where needed."""
    info = FORMAT_INFO.get(fmt, {})
    endpoint = info.get("endpoint", "/v1/chat/completions")
    if model and "{model}" in endpoint:
        endpoint = endpoint.replace("{model}", model)
    return endpoint


def get_auth_type(fmt: str) -> str:
    """Get authentication type for a format."""
    info = FORMAT_INFO.get(fmt, {})
    return info.get("auth_type", "bearer")

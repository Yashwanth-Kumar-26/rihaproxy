"""
Request/response data models for the gateway.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


# =============================================================================
# OpenAI Chat Completions
# =============================================================================


class ChatMessage(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "developer"]
    content: str | list[Any]
    name: NotRequired[str]
    tool_call_id: NotRequired[str]
    tool_calls: NotRequired[list[dict[str, Any]]]
    audio: NotRequired[dict[str, Any]]
    annotations: NotRequired[list[dict[str, Any]]]


class ChatCompletionRequest(BaseModel):
    model: str = Field(description="Model identifier, e.g. openai/gpt-4o-mini")
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    n: int | None = Field(default=1, ge=1)
    stream: bool = Field(default=False)
    stop: str | list[str] | None = Field(default=None)
    max_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    logit_bias: dict[str, int] | None = Field(default=None)
    user: str | None = Field(default=None)
    response_format: dict[str, str] | None = Field(default=None)
    seed: int | None = Field(default=None)
    service_tier: str | None = Field(default=None)
    store: bool | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)
    tools: list[dict[str, Any]] | None = Field(default=None)
    tool_choice: str | dict[str, Any] | None = Field(default=None)
    parallel_tool_calls: bool = Field(default=True)
    extra_headers: dict[str, str] | None = Field(default=None)
    extra_query: dict[str, Any] | None = Field(default=None)


class UsageInfo(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: NotRequired[dict[str, int]]
    completion_tokens_details: NotRequired[dict[str, Any]]


class ChatMessageDelta(TypedDict, total=False):
    role: NotRequired[Literal["assistant"]]
    content: NotRequired[str | None]
    tool_calls: NotRequired[list[dict[str, Any]]]
    audio: NotRequired[dict[str, Any]]


class ChatChoice(TypedDict, total=False):
    index: int
    message: ChatMessage
    finish_reason: str | None
    logprobs: Any


class ChatCompletionChunkChoice(TypedDict, total=False):
    index: int
    delta: ChatMessageDelta
    finish_reason: str | None
    logprobs: Any


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: UsageInfo | None = None
    service_tier: str | None = None
    system_fingerprint: str | None = None


# =============================================================================
# Anthropic Messages
# =============================================================================


class AnthropicContentBlock(TypedDict, total=False):
    type: Literal["text", "tool_use", "tool_result", "image"]
    text: NotRequired[str]
    id: NotRequired[str]
    name: NotRequired[str]
    input: NotRequired[dict[str, Any]]
    content: NotRequired[str | list[dict[str, Any]]]
    source: NotRequired[dict[str, Any]]


class AnthropicMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str | list[AnthropicContentBlock]


class AnthropicRequest(BaseModel):
    model: str = Field(description="Model identifier")
    messages: list[AnthropicMessage] = Field(min_length=1)
    system: str | list[AnthropicContentBlock] | None = Field(default=None)
    max_tokens: int = Field(default=4096, ge=1)
    max_tokens_to_sample: int | None = Field(default=None, ge=1, alias="max_tokens")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    tools: list[dict[str, Any]] | None = Field(default=None)
    tool_choice: dict[str, Any] | None = Field(default=None)
    stop_sequences: list[str] | None = Field(default=None)
    stream: bool = Field(default=False)
    metadata: dict[str, Any] | None = Field(default=None)
    thinking: dict[str, Any] | None = Field(default=None)
    bypass_system_prompt: bool | None = Field(default=None)
    extra_headers: dict[str, str] | None = Field(default=None)

    model_config = {"populate_by_name": True}


class AnthropicUsage(TypedDict):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: NotRequired[int]
    cache_hit_input_tokens: NotRequired[int]


class AnthropicResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[AnthropicContentBlock]
    stop_reason: str
    stop_sequence: str | None = None
    usage: AnthropicUsage


# =============================================================================
# Image Generation
# =============================================================================


class ImageGenerationRequest(BaseModel):
    model: str = Field(default="openai/dall-e-3")
    prompt: str = Field(min_length=1)
    n: int = Field(default=1, ge=1, le=10)
    size: str = Field(default="1024x1024")
    quality: Literal["standard", "hd"] = "standard"
    style: str | None = None
    response_format: Literal["url", "b64_json"] = "url"
    user: str | None = None


class ImageData(TypedDict):
    url: NotRequired[str]
    b64_json: NotRequired[str]
    revised_prompt: NotRequired[str]


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]


# =============================================================================
# Text-to-Speech
# =============================================================================


class SpeechRequest(BaseModel):
    model: str = Field(default="openai/tts-1")
    input: str = Field(min_length=1)
    voice: str = Field(default="alloy")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    response_format: Literal["mp3", "opus", "aac", "flac"] = "mp3"


# =============================================================================
# Embeddings
# =============================================================================


class EmbeddingsRequest(BaseModel):
    model: str = Field(default="openai/text-embedding-3-small")
    input: str | list[str]
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int | None = None
    user: str | None = None


class EmbeddingData(TypedDict):
    object: Literal["embedding"]
    embedding: list[float]
    index: int


class EmbeddingsResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    data: list[EmbeddingData]
    usage: UsageInfo


# =============================================================================
# Web Search
# =============================================================================


class WebSearchRequest(BaseModel):
    model: str = Field(default="tavily/search")
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)
    search_type: Literal["web", "news"] = "web"
    country: str | None = None
    language: str | None = None
    time_range: str | None = None
    domain_filter: str | None = None


class SearchResult(TypedDict):
    title: str
    url: str
    display_url: str
    snippet: str
    position: int
    score: float
    published_at: str | None
    favicon_url: str | None
    content: str | None
    metadata: dict[str, Any]


class WebSearchResponse(BaseModel):
    provider: str
    query: str
    results: list[SearchResult]
    answer: str | None = None
    usage: dict[str, Any]


# =============================================================================
# Web Fetch
# =============================================================================


class WebFetchRequest(BaseModel):
    model: str = Field(default="firecrawl/fetch")
    url: str = Field(min_length=1)
    format: Literal["markdown", "text", "html"] = "markdown"
    max_characters: int | None = Field(default=None, ge=1)


class WebFetchResponse(BaseModel):
    provider: str
    url: str
    title: str | None = None
    content: dict[str, Any]
    metadata: dict[str, Any]
    usage: dict[str, Any]


# =============================================================================
# Internal / Gateway
# =============================================================================


class ModelInfo(TypedDict):
    id: str
    object: Literal["model"]
    owned_by: str
    created: int
    kind: str | None = None


class ProviderConnection(TypedDict, total=False):
    id: str
    provider: str
    name: str
    auth_type: Literal["api_key", "oauth", "device_code", "noauth"]
    api_key: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: str | None = None
    is_active: bool = True
    priority: int = 0
    test_status: Literal["unknown", "valid", "invalid", "error"] = "unknown"
    last_error: str | None = None
    rate_limited_until: str | None = None


class Combo(TypedDict):
    id: str
    name: str
    models: list[str]
    description: str | None = None


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    uptime: float
    providers_active: int
    total_requests: int


class ErrorResponse(BaseModel):
    error: dict[str, Any]


# =============================================================================
# SSE Streaming Chunks
# =============================================================================


class SSEMessageStart(TypedDict):
    type: Literal["message_start"]
    message: AnthropicUsage


class SSETextDelta(TypedDict):
    type: Literal["content_block_delta"]
    index: int
    delta: dict[str, Any]


class SSEMessageStop(TypedDict):
    type: Literal["message_stop"]
    index: int


class SSEContentBlockStart(TypedDict):
    type: Literal["content_block_start"]
    index: int
    content_block: AnthropicContentBlock

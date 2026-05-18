"""
API route definitions.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from rihaproxy.backends.base import BackendError, ProviderUnavailable
from rihaproxy.gateway.auth import RequireAuth
from rihaproxy.gateway.router import get_router
from rihaproxy.gateway.service import get_service
from rihaproxy.storage.db import get_storage

router = APIRouter()


@router.head("/")
async def root_head() -> JSONResponse:
    """Health-compatible HEAD endpoint for clients that probe the base URL."""
    return JSONResponse(content={})


# =============================================================================
# OpenAI Chat Completions
# =============================================================================


@router.post("/v1/chat/completions", name="chat_completions")
async def chat_completions(request: Request, auth: RequireAuth) -> Any:
    """
    OpenAI-compatible /v1/chat/completions endpoint.
    Supports both streaming and non-streaming responses.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    service = get_service()
    stream = body.get("stream", False)

    try:
        result = await service.handle_chat_completions(body, stream=stream)
    except ProviderUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": str(e), "type": "provider_unavailable", "code": "provider_unavailable"}},
        )
    except BackendError as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "internal_error"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "internal_error"}})

    if stream:
        return StreamingResponse(
            _stream_chat(result),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": f"req_{int(time.time() * 1000)}",
            },
        )

    return JSONResponse(content=result)


async def _stream_chat(result: AsyncIterator[str]) -> AsyncIterator[str]:
    """Stream chat completions as SSE."""
    async for chunk in result:
        try:
            data = json.loads(chunk) if isinstance(chunk, str) else chunk
            yield f"data: {json.dumps(data)}\n\n"
        except (json.JSONDecodeError, TypeError):
            yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"


# =============================================================================
# Anthropic Messages
# =============================================================================


@router.post("/v1/messages", name="anthropic_messages")
async def anthropic_messages(request: Request, auth: RequireAuth) -> Any:
    """
    Anthropic-native /v1/messages endpoint.
    Native path for Claude Code and Anthropic SDK.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    service = get_service()
    stream = body.get("stream", False)

    try:
        result = await service.handle_anthropic_messages(body, stream=stream)
    except ProviderUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": str(e), "type": "provider_unavailable"}},
        )
    except BackendError as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "internal_error"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "internal_error"}})

    if stream:
        return StreamingResponse(
            _stream_anthropic(result),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return JSONResponse(content=result)


# =============================================================================
# Seamless Compatibility Routes
# =============================================================================


@router.post("/v1/complete")
async def anthropic_complete(request: Request, auth: RequireAuth) -> Any:
    """Redirect legacy Anthropic complete to messages."""
    return await anthropic_messages(request, auth)


@router.post("/v1/completions")
async def openai_completions(request: Request, auth: RequireAuth) -> Any:
    """Redirect legacy OpenAI completions to chat completions."""
    return await chat_completions(request, auth)


@router.post("/chat/completions")
@router.post("/messages")
@router.get("/models")
@router.get("/v1/models")
async def compatibility_list_models():
    """Compatibility endpoint for model listing."""
    from rihaproxy.providers import AI_PROVIDERS
    models = []
    for p_id in AI_PROVIDERS:
        models.append({
            "id": f"{p_id}/latest",
            "object": "model",
            "created": int(time.time()),
            "owned_by": p_id,
        })
    return {"object": "list", "data": models}


async def unversioned_routes(request: Request, auth: RequireAuth) -> Any:
    """Handle unversioned requests by routing to /v1/ versions."""
    path = request.url.path
    if "chat" in path:
        return await chat_completions(request, auth)
    if "models" in path:
        return await compatibility_list_models()
    return await anthropic_messages(request, auth)


async def _stream_anthropic(result: AsyncIterator[str]) -> AsyncIterator[str]:
    """Stream Anthropic messages as SSE.
    Chunks from _openai_stream_to_anthropic are already formatted as SSE lines.
    """
    async for chunk in result:
        if isinstance(chunk, str):
            # If already formatted as SSE (from our converter), pass through
            if chunk.startswith("event:") or chunk.startswith("data:"):
                yield chunk
            else:
                # Raw data, wrap it
                yield f"data: {chunk}\n\n"
        elif isinstance(chunk, dict):
            import json
            yield f"data: {json.dumps(chunk)}\n\n"


# =============================================================================
# Models
# =============================================================================


@router.get("/v1/models", name="list_models")
async def list_models(auth: RequireAuth) -> JSONResponse:
    """List all available models."""
    router = get_router()
    models = router.get_models()
    return JSONResponse(content={
        "object": "list",
        "data": models,
    })


@router.get("/v1/models/image", name="list_image_models")
async def list_image_models(auth: RequireAuth) -> JSONResponse:
    """List available image generation models."""
    router = get_router()
    models = router.get_image_models()
    return JSONResponse(content={"object": "list", "data": models})


@router.get("/v1/models/tts", name="list_tts_models")
async def list_tts_models(auth: RequireAuth) -> JSONResponse:
    """List available TTS models/voices."""
    router = get_router()
    models = router.get_tts_models()
    return JSONResponse(content={"object": "list", "data": models})


@router.get("/v1/models/embedding", name="list_embedding_models")
async def list_embedding_models(auth: RequireAuth) -> JSONResponse:
    """List available embedding models."""
    router = get_router()
    models = router.get_embedding_models()
    return JSONResponse(content={"object": "list", "data": models})


# =============================================================================
# Image Generation
# =============================================================================


@router.post("/v1/images/generations", name="image_generations")
async def image_generations(request: Request, auth: RequireAuth) -> Any:
    """Generate images."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    service = get_service()
    try:
        result = await service.handle_image_generation(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})

    return JSONResponse(content=result)


# =============================================================================
# Text-to-Speech
# =============================================================================


@router.post("/v1/audio/speech", name="text_to_speech")
async def text_to_speech(request: Request, auth: RequireAuth) -> Any:
    """Convert text to speech."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    service = get_service()
    try:
        audio_bytes = await service.handle_speech(body)
        format = body.get("response_format", "mp3")
        media_types = {"mp3": "audio/mp3", "opus": "audio/opus", "aac": "audio/aac", "flac": "audio/flac"}
        return StreamingResponse(
            iter([audio_bytes]),
            media_type=media_types.get(format, "audio/mp3"),
            headers={"Content-Disposition": "attachment; filename=speech.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})


# =============================================================================
# Embeddings
# =============================================================================


@router.post("/v1/embeddings", name="embeddings")
async def embeddings(request: Request, auth: RequireAuth) -> Any:
    """Generate embeddings."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    service = get_service()
    try:
        result = await service.handle_embeddings(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})

    return JSONResponse(content=result)


# =============================================================================
# Web Search
# =============================================================================


@router.post("/v1/search", name="web_search")
async def web_search(request: Request, auth: RequireAuth) -> Any:
    """
    Web search endpoint.
    Routes to Tavily, Exa, Brave, or other search providers.
    """
    from rihaproxy.web.search import search_web

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        result = await search_web(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})

    return JSONResponse(content=result)


# =============================================================================
# Web Fetch
# =============================================================================


@router.post("/v1/web/fetch", name="web_fetch")
async def web_fetch(request: Request, auth: RequireAuth) -> Any:
    """
    URL to markdown/text extraction endpoint.
    Routes to Firecrawl, Jina Reader, or other fetch providers.
    """
    from rihaproxy.web.fetch import fetch_url

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        result = await fetch_url(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})

    return JSONResponse(content=result)


# =============================================================================
# Health & Status
# =============================================================================


@router.get("/api/health", name="health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    service = get_service()
    storage = get_storage()
    router = get_router()
    usage = storage.get_usage_summary()

    return JSONResponse(content={
        "ok": True,
        "version": "0.1.0",
        "uptime": round(service.uptime, 1),
        "providers_active": len(router.hub.cached_providers),
        "total_requests": usage.get("total_requests", 0),
    })


@router.get("/api/status", name="get_status")
async def get_status(auth: RequireAuth) -> JSONResponse:
    """Detailed gateway status."""
    storage = get_storage()
    router = get_router()

    return JSONResponse(content={
        "providers": router.hub.providers,
        "active_providers": storage.get_active_providers(),
        "aliases": storage.get_aliases(),
        "combos": list(storage.get_combos().keys()),
        "usage": storage.get_usage_summary(),
    })


# =============================================================================
# Admin Endpoints (auth required)
# =============================================================================


@router.post("/api/aliases", name="create_alias")
async def create_alias(request: Request, auth: RequireAuth) -> JSONResponse:
    """Create a model alias."""
    body = await request.json()
    alias = body.get("alias")
    target = body.get("target")
    if not alias or not target:
        raise HTTPException(status_code=400, detail="alias and target required")

    storage = get_storage()
    storage.set_alias(alias, target)
    return JSONResponse(content={"ok": True, "alias": alias, "target": target})


@router.delete("/api/aliases/{alias}", name="delete_alias")
async def delete_alias(alias: str, auth: RequireAuth) -> JSONResponse:
    """Delete a model alias."""
    storage = get_storage()
    deleted = storage.delete_alias(alias)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alias not found")
    return JSONResponse(content={"ok": True})


@router.post("/api/combos", name="create_combo")
async def create_combo(request: Request, auth: RequireAuth) -> JSONResponse:
    """Create a model combo (fallback chain)."""
    body = await request.json()
    name = body.get("name")
    models = body.get("models", [])
    if not name or not models:
        raise HTTPException(status_code=400, detail="name and models required")

    storage = get_storage()
    combo_id = storage.add_combo({"name": name, "models": models, "description": body.get("description")})
    return JSONResponse(content={"ok": True, "id": combo_id, "name": name})


@router.delete("/api/combos/{combo_id}", name="delete_combo")
async def delete_combo(combo_id: str, auth: RequireAuth) -> JSONResponse:
    """Delete a model combo."""
    storage = get_storage()
    deleted = storage.delete_combo(combo_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Combo not found")
    return JSONResponse(content={"ok": True})


@router.get("/api/usage", name="usage")
async def usage(auth: RequireAuth, limit: int = 100) -> JSONResponse:
    """Get usage statistics and recent requests."""
    storage = get_storage()
    return JSONResponse(content={
        "summary": storage.get_usage_summary(),
        "recent": storage.get_recent_requests(limit=limit),
    })


@router.get("/api/models", name="all_models")
async def all_models(auth: RequireAuth) -> JSONResponse:
    """Get all models (extended info)."""
    router = get_router()
    return JSONResponse(content={
        "chat": router.get_models(),
        "image": router.get_image_models(),
        "tts": router.get_tts_models(),
        "embedding": router.get_embedding_models(),
    })


# =============================================================================
# OAuth Provider Connections
# =============================================================================


@router.post("/api/oauth/{provider}/start", name="oauth_start")
async def oauth_start(provider: str, auth: RequireAuth) -> JSONResponse:
    """
    Start an OAuth device code flow for a provider.

    Providers supported: claude, codex, google, kiro, cursor, github

    Returns verification URL and user code for the user to authenticate.
    """
    from rihaproxy.auth.oauth import DeviceCodeFlow, OAuthError, complete_kiro_device_flow

    try:
        flow = DeviceCodeFlow(provider)
        result = await flow.start()
        return JSONResponse(content={
            "provider": provider,
            "status": "pending",
            **result,
        })
    except OAuthError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/api/oauth/{provider}/poll", name="oauth_poll")
async def oauth_poll(provider: str, request: Request, auth: RequireAuth) -> JSONResponse:
    """
    Poll for OAuth token completion.

    Call this repeatedly after oauth/start. When status becomes 'completed',
    the token is ready and the connection is saved.

    Body: {"device_code": "..."}
    """
    from rihaproxy.auth.oauth import DeviceCodeFlow, OAuthError
    from rihaproxy.auth.token_manager import get_token_manager

    body = await request.json()
    device_code = body.get("device_code")
    if not device_code:
        raise HTTPException(status_code=400, detail="device_code is required")

    try:
        if provider == "kiro":
            provider_data = body.get("provider_data") or {}
            tokens = await complete_kiro_device_flow(
                device_code,
                provider_data.get("client_id"),
                provider_data.get("client_secret"),
            )
            tokens["provider_data"] = {**provider_data, **tokens.get("provider_data", {})}
        else:
            flow = DeviceCodeFlow(provider)
            flow._device_code = device_code
            tokens = await flow.poll()

        # Save as provider connection
        tm = get_token_manager()
        expires_at = str(time.time() + tokens.get("expires_in", 3600))
        conn_id = await tm.connect_provider(
            provider=provider,
            auth_type="oauth",
            name=f"{provider.title()} Account",
            credentials={
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": expires_at,
                "scope": tokens.get("scope"),
                "provider_data": tokens.get("provider_data", {}),
            },
        )

        return JSONResponse(content={
            "provider": provider,
            "status": "completed",
            "connection_id": conn_id,
            "expires_in": tokens.get("expires_in", 3600),
        })

    except OAuthError as e:
        return JSONResponse(content={
            "provider": provider,
            "status": "pending",
            "error": str(e),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/api/oauth/{provider}/connect", name="oauth_connect_api_key")
async def oauth_connect_api_key(provider: str, request: Request, auth: RequireAuth) -> JSONResponse:
    """
    Connect a provider using an API key directly.

    Body: {"api_key": "...", "name": "optional name"}
    """
    from rihaproxy.auth.token_manager import get_token_manager

    body = await request.json()
    api_key = body.get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    name = body.get("name", f"{provider.title()} API Key")

    tm = get_token_manager()
    conn_id = await tm.connect_provider(
        provider=provider,
        auth_type="api_key",
        name=name,
        credentials={"api_key": api_key},
    )

    return JSONResponse(content={
        "ok": True,
        "provider": provider,
        "connection_id": conn_id,
        "name": name,
    })


@router.get("/api/connections", name="list_connections")
async def list_connections(auth: RequireAuth, provider: str | None = None) -> JSONResponse:
    """
    List all provider connections.

    Query params:
    - provider: filter by provider name (optional)
    """
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()
    connections = await tm.get_active_connections(provider=provider)

    # Strip sensitive data
    safe_connections = []
    for conn in connections:
        safe = dict(conn)
        safe.pop("access_token", None)
        safe.pop("refresh_token", None)
        safe.pop("api_key", None)
        safe_connections.append(safe)

    return JSONResponse(content={
        "connections": safe_connections,
        "total": len(safe_connections),
    })


@router.get("/api/connections/{conn_id}", name="get_connection")
async def get_connection(conn_id: str, auth: RequireAuth) -> JSONResponse:
    """Get details of a specific connection."""
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()
    conn = await tm.get_connection(conn_id)

    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    safe = dict(conn)
    safe.pop("access_token", None)
    safe.pop("refresh_token", None)
    safe.pop("api_key", None)

    return JSONResponse(content=safe)


@router.post("/api/connections/{conn_id}/test", name="test_connection")
async def test_connection(conn_id: str, auth: RequireAuth) -> JSONResponse:
    """
    Test a provider connection.

    Makes a test API call and returns whether the connection is valid.
    """
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()
    result = await tm.test_connection(conn_id)
    return JSONResponse(content={"connection_id": conn_id, **result})


@router.post("/api/connections/{conn_id}/refresh", name="refresh_connection")
async def refresh_connection(conn_id: str, auth: RequireAuth) -> JSONResponse:
    """
    Manually refresh a connection's token.

    Only works for OAuth connections with a refresh token.
    """
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()
    result = await tm.refresh_if_needed(conn_id)

    if result:
        return JSONResponse(content={
            "ok": True,
            "connection_id": conn_id,
            "message": "Token refreshed",
        })
    else:
        return JSONResponse(content={
            "ok": False,
            "connection_id": conn_id,
            "message": "No refresh needed or refresh failed",
        })


@router.delete("/api/connections/{conn_id}", name="delete_connection")
async def delete_connection(conn_id: str, auth: RequireAuth) -> JSONResponse:
    """
    Delete a provider connection.
    """
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()
    success = await tm.disconnect_provider(conn_id)

    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    return JSONResponse(content={"ok": True, "connection_id": conn_id})


@router.get("/v1/providers", name="v1_list_providers")
@router.get("/api/providers", name="list_providers")
async def list_providers(auth: RequireAuth) -> JSONResponse:
    """
    List all supported providers and their connection status.
    """
    from rihaproxy.auth.token_manager import get_token_manager

    tm = get_token_manager()

    providers = [
        {"id": "openrouter", "name": "OpenRouter", "auth_type": "api_key"},
        {"id": "openai", "name": "OpenAI", "auth_type": "api_key"},
        {"id": "anthropic", "name": "Anthropic", "auth_type": "api_key"},
        {"id": "deepseek", "name": "DeepSeek", "auth_type": "api_key"},
        {"id": "nvidia", "name": "NVIDIA NIM", "auth_type": "api_key"},
        {"id": "google", "name": "Google AI", "auth_type": "oauth"},
        {"id": "claude", "name": "Claude (OAuth)", "auth_type": "oauth"},
        {"id": "codex", "name": "GitHub Codex", "auth_type": "oauth"},
        {"id": "github", "name": "GitHub Models", "auth_type": "api_key"},
        {"id": "kiro", "name": "Kiro AI", "auth_type": "oauth"},
        {"id": "cursor", "name": "Cursor", "auth_type": "oauth"},
        {"id": "lmstudio", "name": "LM Studio", "auth_type": "noauth"},
        {"id": "llamacpp", "name": "llama.cpp", "auth_type": "noauth"},
    ]

    # Enrich with connection status
    result = []
    for p in providers:
        connections = await tm.get_active_connections(provider=p["id"])
        result.append({
            **p,
            "connected": len(connections) > 0,
            "connection_count": len(connections),
            "test_status": connections[0].get("test_status") if connections else "disconnected",
        })

    return JSONResponse(content={"providers": result})

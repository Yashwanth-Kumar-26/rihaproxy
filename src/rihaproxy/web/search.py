"""
Web search endpoint — routes to Tavily, Exa, Brave, or other providers.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from rihaproxy.config import settings

logger = structlog.get_logger()


async def search_web(body: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a web search request.

    Supports multiple providers:
    - tavily (default)
    - exa
    - brave
    - serper
    - perpexity
    - searxng (local)

    Request body:
    {
        "model": "tavily/search",
        "query": "...",
        "max_results": 5,
        "search_type": "web" | "news",
        "country": "US",
        "language": "en"
    }
    """
    model = body.get("model", "tavily/search")
    query = body.get("query", "")
    max_results = body.get("max_results", 5)
    search_type = body.get("search_type", "web")

    if not query:
        return {"error": "query is required", "provider": "unknown"}

    # Parse provider from model
    parts = model.split("/")
    provider = parts[0] if len(parts) > 1 else model.replace("/search", "")
    if "/" not in model:
        provider = model.replace("/search", "")
    provider = provider.replace("/search", "")

    # Route to provider
    try:
        if provider in ("tavily", " Tavily"):
            return await _tavily_search(query, max_results, search_type, body)
        elif provider in ("exa", "Exa"):
            return await _exa_search(query, max_results, body)
        elif provider in ("brave", "Brave"):
            return await _brave_search(query, max_results, body)
        elif provider in ("serper", "Serper"):
            return await _serper_search(query, max_results, body)
        elif provider in ("perplexity", "perplexity-web"):
            return await _perplexity_search(query, max_results, body)
        else:
            # Default to Tavily
            return await _tavily_search(query, max_results, search_type, body)
    except Exception as e:
        logger.error("search_failed", provider=provider, error=str(e))
        return {"error": str(e), "provider": provider}


async def _tavily_search(
    query: str,
    max_results: int,
    search_type: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Search using Tavily API."""
    import time

    api_key = settings.openai_api_key or ""  # Tavily may use OpenAI key or its own
    tavily_key = body.get("api_key") or api_key

    headers = {
        "Authorization": f"Bearer {tavily_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "max_results": max_results,
        "search_type": search_type,
    }

    if body.get("language"):
        payload["language"] = body["language"]
    if body.get("time_range"):
        payload["time_range"] = body["time_range"]
    if body.get("domain_filter"):
        payload["domain_filter"] = body["domain_filter"]

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    results = []
    for i, r in enumerate(data.get("results", [])[:max_results], 1):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "display_url": r.get("url", ""),
            "snippet": r.get("content", ""),
            "position": i,
            "score": r.get("score", 1.0 - (i * 0.1)),
            "published_at": r.get("published_date"),
            "favicon_url": None,
            "content": r.get("raw_content"),
            "metadata": {},
        })

    return {
        "provider": "tavily",
        "query": query,
        "results": results,
        "answer": data.get("answer"),
        "usage": {
            "queries_used": 1,
            "search_cost_usd": max_results * 0.001,
        },
        "metrics": {
            "response_time_ms": int(elapsed),
            "upstream_latency_ms": int(elapsed * 0.9),
            "total_results_available": len(data.get("results", [])),
        },
        "errors": [],
    }


async def _exa_search(query: str, max_results: int, body: dict[str, Any]) -> dict[str, Any]:
    """Search using Exa API."""
    import time

    api_key = settings.openai_api_key or ""
    exa_key = body.get("api_key") or api_key

    headers = {
        "Authorization": f"Bearer {exa_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "num_results": max_results,
        "text": {"max_chars": 2000},
    }

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.exa.ai/search",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    results = []
    for i, r in enumerate(data.get("results", [])[:max_results], 1):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "display_url": r.get("url", ""),
            "snippet": r.get("text", ""),
            "position": i,
            "score": r.get("score", 1.0 - (i * 0.1)),
            "published_at": r.get("published_date"),
            "favicon_url": None,
            "content": r.get("text"),
            "metadata": r.get("metadata", {}),
        })

    return {
        "provider": "exa",
        "query": query,
        "results": results,
        "answer": None,
        "usage": {"queries_used": 1, "search_cost_usd": max_results * 0.002},
        "metrics": {"response_time_ms": int(elapsed), "upstream_latency_ms": int(elapsed * 0.9)},
        "errors": [],
    }


async def _brave_search(query: str, max_results: int, body: dict[str, Any]) -> dict[str, Any]:
    """Search using Brave Search API."""
    import time

    brave_key = body.get("api_key") or ""
    headers = {"Accept": "application/json", "X-Subscription-Token": brave_key}

    params = {
        "q": query,
        "count": max_results,
    }

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/search",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    results = []
    for i, r in enumerate(data.get("web", {}).get("results", [])[:max_results], 1):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "display_url": r.get("url", ""),
            "snippet": r.get("description", ""),
            "position": i,
            "score": r.get("relevance_score", 1.0 - (i * 0.1)),
            "published_at": None,
            "favicon_url": r.get("favicon"),
            "content": None,
            "metadata": {},
        })

    return {
        "provider": "brave",
        "query": query,
        "results": results,
        "answer": None,
        "usage": {"queries_used": 1, "search_cost_usd": 0},
        "metrics": {"response_time_ms": int(elapsed)},
        "errors": [],
    }


async def _serper_search(query: str, max_results: int, body: dict[str, Any]) -> dict[str, Any]:
    """Search using Serper API."""
    import time

    serper_key = body.get("api_key") or ""
    headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}

    payload = {"query": query, "numResults": max_results}

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://google.serper.dev/search",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    results = []
    for i, r in enumerate(data.get("organic", [])[:max_results], 1):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "display_url": r.get("link", ""),
            "snippet": r.get("snippet", ""),
            "position": i,
            "score": 1.0 - (i * 0.1),
            "published_at": r.get("date"),
            "favicon_url": None,
            "content": None,
            "metadata": {},
        })

    return {
        "provider": "serper",
        "query": query,
        "results": results,
        "answer": None,
        "usage": {"queries_used": 1, "search_cost_usd": 0},
        "metrics": {"response_time_ms": int(elapsed)},
        "errors": [],
    }


async def _perplexity_search(query: str, max_results: int, body: dict[str, Any]) -> dict[str, Any]:
    """Search using Perplexity API."""
    import time

    pplx_key = body.get("api_key") or settings.openai_api_key or ""

    messages = [
        {"role": "system", "content": "You are a helpful research assistant."},
        {"role": "user", "content": query},
    ]

    start_time = time.time()

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            json={
                "model": "sonar",
                "messages": messages,
                "max_tokens": 1000,
            },
            headers={
                "Authorization": f"Bearer {pplx_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    return {
        "provider": "perplexity",
        "query": query,
        "results": [],
        "answer": data.get("choices", [{}])[0].get("message", {}).get("content"),
        "usage": {"queries_used": 1, "search_cost_usd": 0.001},
        "metrics": {"response_time_ms": int(elapsed)},
        "errors": [],
    }
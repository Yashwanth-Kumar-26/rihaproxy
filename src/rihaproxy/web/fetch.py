"""
Web fetch endpoint — URL to markdown extraction.
Routes to Firecrawl, Jina Reader, or other providers.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


async def fetch_url(body: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch a URL and extract its content as markdown/text/HTML.

    Request body:
    {
        "model": "firecrawl/fetch",
        "url": "https://...",
        "format": "markdown" | "text" | "html",
        "max_characters": 5000
    }
    """
    url = body.get("url", "")
    if not url:
        return {"error": "url is required", "provider": "unknown"}

    model = body.get("model", "firecrawl/fetch")
    fmt = body.get("format", "markdown")
    max_chars = body.get("max_characters")

    parts = model.split("/")
    provider = parts[0] if len(parts) > 1 else model.replace("/fetch", "")
    provider = provider.replace("/fetch", "")

    try:
        if provider in ("firecrawl", "Firecrawl"):
            return await _firecrawl_fetch(url, fmt, max_chars, body)
        elif provider in ("jina", "Jina"):
            return await _jina_fetch(url, fmt, max_chars, body)
        elif provider in ("tavily", "Tavily"):
            return await _tavily_fetch(url, fmt, max_chars, body)
        elif provider in ("exa", "Exa"):
            return await _exa_fetch(url, fmt, max_chars, body)
        else:
            return await _jina_fetch(url, fmt, max_chars, body)
    except Exception as e:
        logger.error("fetch_failed", provider=provider, url=url, error=str(e))
        return {"error": str(e), "provider": provider, "url": url}


async def _firecrawl_fetch(
    url: str,
    fmt: str,
    max_chars: int | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Fetch using Firecrawl API."""
    from rihaproxy.config import settings

    api_key = body.get("api_key") or settings.openai_api_key or ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "url": url,
        "format": fmt,
    }

    if max_chars:
        payload["maxCharacters"] = max_chars

    start_time = time.time()

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.firecrawl.dev/v0/scrape",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    content = data.get("data", {})
    text = content.get("markdown") or content.get("text") or content.get("html") or ""

    return {
        "provider": "firecrawl",
        "url": url,
        "title": content.get("title"),
        "content": {
            "format": fmt,
            "text": text[:max_chars] if max_chars else text,
            "length": len(text),
        },
        "metadata": {
            "author": content.get("author"),
            "published_at": content.get("published_date"),
            "language": content.get("language"),
        },
        "usage": {
            "fetch_cost_usd": 0.002,
        },
        "metrics": {
            "response_time_ms": int(elapsed),
            "upstream_latency_ms": int(elapsed * 0.9),
        },
    }


async def _jina_fetch(
    url: str,
    fmt: str,
    max_chars: int | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Fetch using Jina Reader API (free, no auth needed)."""
    formats = {
        "markdown": "markdown",
        "text": "text",
        "html": "html",
    }
    jina_fmt = formats.get(fmt, "markdown")

    params = {
        "url": url,
        "format": jina_fmt,
    }
    if max_chars:
        params["max_chars"] = max_chars

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://r.jina.ai/{url}",
            params=params,
        )
        response.raise_for_status()
        text = response.text

    elapsed = (time.time() - start_time) * 1000

    # Extract title from first line if markdown
    lines = text.split("\n")
    title = ""
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("# ").strip()

    return {
        "provider": "jina-reader",
        "url": url,
        "title": title or None,
        "content": {
            "format": fmt,
            "text": text[:max_chars] if max_chars else text,
            "length": len(text),
        },
        "metadata": {
            "author": None,
            "published_at": None,
            "language": None,
        },
        "usage": {
            "fetch_cost_usd": 0,
        },
        "metrics": {
            "response_time_ms": int(elapsed),
            "upstream_latency_ms": int(elapsed * 0.7),
        },
    }


async def _tavily_fetch(
    url: str,
    fmt: str,
    max_chars: int | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Fetch using Tavily Extract API."""
    from rihaproxy.config import settings

    api_key = body.get("api_key") or settings.openai_api_key or ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "urls": [url],
        "search_depth": "standard",
    }

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.tavily.com/extract",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    results = data.get("results", [])
    content_text = results[0].get("raw_content", "") if results else ""

    return {
        "provider": "tavily-extract",
        "url": url,
        "title": results[0].get("title") if results else None,
        "content": {
            "format": fmt,
            "text": content_text[:max_chars] if max_chars else content_text,
            "length": len(content_text),
        },
        "metadata": {},
        "usage": {"fetch_cost_usd": 0.001},
        "metrics": {"response_time_ms": int(elapsed)},
    }


async def _exa_fetch(
    url: str,
    fmt: str,
    max_chars: int | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Fetch using Exa Contents API."""
    from rihaproxy.config import settings

    api_key = body.get("api_key") or settings.openai_api_key or ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "url": url,
        "text": {"max_chars": max_chars or 5000},
    }

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.exa.ai/contents",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = (time.time() - start_time) * 1000

    text = data.get("text", "")

    return {
        "provider": "exa-contents",
        "url": url,
        "title": data.get("title"),
        "content": {
            "format": fmt,
            "text": text,
            "length": len(text),
        },
        "metadata": {},
        "usage": {"fetch_cost_usd": 0.002},
        "metrics": {"response_time_ms": int(elapsed)},
    }
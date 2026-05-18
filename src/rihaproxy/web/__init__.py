"""
Web module — web search and fetch.
"""

from __future__ import annotations

from rihaproxy.web.fetch import fetch_url
from rihaproxy.web.search import search_web

__all__ = ["search_web", "fetch_url"]
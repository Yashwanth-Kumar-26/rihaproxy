"""
Unit tests for the GitHub Copilot adapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rihaproxy.backends.github_copilot.adapter import GitHubCopilotAdapter


@pytest.mark.asyncio
async def test_claude_opus_request_maps_to_haiku(monkeypatch):
    """Claude Code opus tiers should use Copilot Haiku for reliability."""
    adapter = GitHubCopilotAdapter(api_key="github-oauth-token")
    adapter._get_copilot_token = AsyncMock(return_value="copilot-session-token")
    adapter._transport.post = AsyncMock(return_value={"ok": True})

    result = await adapter.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="claude-opus-4-7",
        stream=True,
    )

    assert result == {"ok": True}
    _, kwargs = adapter._transport.post.call_args
    assert kwargs["body"]["model"] == "claude-haiku-4.5"
    assert kwargs["extra_headers"]["X-Initiator"] == "user"


@pytest.mark.asyncio
async def test_github_prefixed_sonnet_request_maps_to_haiku(monkeypatch):
    """Configured GitHub sonnet tiers should also use Copilot Haiku."""
    adapter = GitHubCopilotAdapter(api_key="github-oauth-token")
    adapter._get_copilot_token = AsyncMock(return_value="copilot-session-token")
    adapter._transport.post = AsyncMock(return_value={"ok": True})

    await adapter.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="github/claude-sonnet-4.5",
    )

    _, kwargs = adapter._transport.post.call_args
    assert kwargs["body"]["model"] == "claude-haiku-4.5"


@pytest.mark.asyncio
async def test_copilot_request_sanitizes_tools_and_empty_system(monkeypatch):
    """Claude Code tool schemas should be converted to Copilot-safe functions."""
    adapter = GitHubCopilotAdapter(api_key="github-oauth-token")
    adapter._get_copilot_token = AsyncMock(return_value="copilot-session-token")
    adapter._transport.post = AsyncMock(return_value={"ok": True})

    await adapter.chat(
        messages=[
            {"role": "system", "content": ""},
            {"role": "user", "content": "hello"},
        ],
        model="github/claude-haiku-4.5",
        tools=[{
            "name": "mcp.project/filter",
            "description": "Filter by project name",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": ["string", "null"],
                        "description": "Filter by project name",
                        "default": None,
                    },
                },
                "required": ["project", "missing"],
                "additionalProperties": True,
            },
        }],
        tool_choice="auto",
    )

    _, kwargs = adapter._transport.post.call_args
    body = kwargs["body"]
    tool = body["tools"][0]["function"]

    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert tool["name"] == "mcp_project_filter"
    assert tool["parameters"] == {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Filter by project name",
            },
        },
        "required": ["project"],
    }


@pytest.mark.asyncio
async def test_copilot_clamps_claude_max_tokens(monkeypatch):
    """Claude Code opus token budgets should be clamped after Haiku mapping."""
    adapter = GitHubCopilotAdapter(api_key="github-oauth-token")
    adapter._get_copilot_token = AsyncMock(return_value="copilot-session-token")
    adapter._transport.post = AsyncMock(return_value={"ok": True})

    await adapter.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="github/claude-opus-4.7",
        max_tokens=64000,
    )

    _, kwargs = adapter._transport.post.call_args
    assert kwargs["body"]["model"] == "claude-haiku-4.5"
    assert kwargs["body"]["max_tokens"] == 8192

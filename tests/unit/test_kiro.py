from __future__ import annotations

import json
import struct
import zlib

from rihaproxy.backends.kiro.adapter import _EventStreamParser, _KiroStreamState
from rihaproxy.translation.request.openai_to_kiro import translate


def _frame(event_type: str, payload: dict) -> bytes:
    headers = bytearray()
    name = b":event-type"
    value = event_type.encode()
    headers.append(len(name))
    headers.extend(name)
    headers.append(7)
    headers.extend(struct.pack(">H", len(value)))
    headers.extend(value)

    body = json.dumps(payload).encode()
    total_len = 12 + len(headers) + len(body) + 4
    prelude = struct.pack(">II", total_len, len(headers))
    prelude_crc = struct.pack(">I", zlib.crc32(prelude) & 0xFFFFFFFF)
    without_msg_crc = prelude + prelude_crc + bytes(headers) + body
    msg_crc = struct.pack(">I", zlib.crc32(without_msg_crc) & 0xFFFFFFFF)
    return without_msg_crc + msg_crc


def test_openai_to_kiro_preserves_tools_and_current_message():
    body = {
        "model": "kiro/claude-sonnet-4.5",
        "messages": [
            {"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "Edit app.py"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{\"path\":\"app.py\"}"},
                }],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "print('hi')"},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }],
    }

    result = translate(body)
    state = result["conversationState"]

    assert state["currentMessage"]["userInputMessage"]["content"].endswith("print('hi')")
    assert state["currentMessage"]["userInputMessage"]["origin"] == "AI_EDITOR"
    assert state["currentMessage"]["userInputMessage"]["userInputMessageContext"]["toolResults"][0]["toolUseId"] == "call_1"
    assert state["currentMessage"]["userInputMessage"]["userInputMessageContext"]["tools"][0]["toolSpecification"]["name"] == "read_file"
    assert "inferenceConfig" in result
    assistant_history = [item for item in state["history"] if "assistantResponseMessage" in item]
    assert assistant_history[0]["assistantResponseMessage"]["toolUses"][0]["name"] == "read_file"


def test_openai_to_kiro_merges_empty_system_with_user_current_message():
    body = {
        "model": "kiro/claude-opus-4-7",
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": "SessionStart: hello"},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": "filter_project",
                "description": "Filter by project name",
                "parameters": {
                    "type": "object",
                    "properties": {"project": {"type": "string"}},
                },
            },
        }],
        "max_tokens": 64000,
    }

    result = translate(body)
    state = result["conversationState"]
    current = state["currentMessage"]["userInputMessage"]

    assert current["modelId"] == "claude-sonnet-4.5"
    assert current["origin"] == "AI_EDITOR"
    assert "SessionStart: hello" in current["content"]
    assert state["history"] == []
    assert current["userInputMessageContext"]["tools"][0]["toolSpecification"]["name"] == "filter_project"
    assert result["inferenceConfig"]["maxTokens"] == 32000


def test_openai_to_kiro_sanitizes_tool_schema_for_codewhisperer():
    body = {
        "model": "kiro/claude-sonnet-4.5",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "mcp.project/filter",
                "description": "Filter by project name",
                "parameters": {
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
            },
        }],
    }

    result = translate(body)
    tool = result["conversationState"]["currentMessage"]["userInputMessage"]["userInputMessageContext"]["tools"][0]
    spec = tool["toolSpecification"]

    assert spec["name"] == "mcp_project_filter"
    assert spec["inputSchema"]["json"] == {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Filter by project name",
            },
        },
        "required": ["project"],
    }


def test_kiro_eventstream_parser_and_state_emit_openai_chunks():
    parser = _EventStreamParser()
    state = _KiroStreamState("claude-sonnet-4.5")

    events = parser.feed(_frame("assistantResponseEvent", {"content": "hello"}))
    chunks = []
    for event in events:
        chunks.extend(state.consume(event))

    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"

    events = parser.feed(_frame("messageStopEvent", {}))
    done = []
    for event in events:
        done.extend(state.consume(event))
    assert done[0]["choices"][0]["finish_reason"] == "stop"

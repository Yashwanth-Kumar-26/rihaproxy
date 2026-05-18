---
name: rihaproxy
description: Entry point for RihaProxy — universal AI gateway with OpenAI-compatible REST for chat, image, TTS, embeddings, web search, web fetch. Use when the user mentions RihaProxy, RIHAPROXY_URL, or wants AI without writing provider boilerplate.
---

# RihaProxy

Universal AI gateway — one key, 40+ providers, auto-fallback.

## Setup

```bash
export RIHA_PROXY_URL="http://localhost:16324"      # or VPS / tunnel URL
export RIHA_PROXY_KEY="your_auth_token"             # from .env (only if AUTH_TOKEN is set)
```

All requests: `${RIHA_PROXY_URL}/v1/...` with header `Authorization: Bearer ${RIHA_PROXY_KEY}`.

Verify: `curl $RIHA_PROXY_URL/api/health` → `{"ok":true}`

## Discover models

```bash
curl $RIHA_PROXY_URL/v1/models                      # chat/LLM (default)
curl $RIHA_PROXY_URL/v1/models/image               # image-gen
curl $RIHA_PROXY_URL/v1/models/tts                 # text-to-speech
curl $RIHA_PROXY_URL/v1/models/embedding            # embeddings
curl $RIHA_PROXY_URL/v1/models/web                  # web search + fetch (entries have `kind` field)
```

Use `data[].id` as `model` field in requests. Combos appear with `owned_by:"combo"`.

## Capability skills

When you need a specific capability, paste the raw SKILL.md URL for that skill:

| Capability | Raw URL |
|---|---|
| Chat / code-gen | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-chat/SKILL.md |
| Image generation | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-image/SKILL.md |
| Text-to-speech | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-tts/SKILL.md |
| Embeddings | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-embeddings/SKILL.md |
| Web search | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-web-search/SKILL.md |
| Web fetch (URL → markdown) | https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy-web-fetch/SKILL.md |

## Quick chat example

```bash
curl -X POST $RIHA_PROXY_URL/v1/chat/completions \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Hi"}],"stream":false}'
```

JS (OpenAI SDK):
```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: `${process.env.RIHA_PROXY_URL}/v1`, apiKey: process.env.RIHA_PROXY_KEY });
const res = await client.chat.completions.create({ model: "openai/gpt-4o-mini", messages: [{ role: "user", content: "Hi" }] });
console.log(res.choices[0].message.content);
```

Anthropic native (Claude Code path):
```bash
curl -X POST $RIHA_PROXY_URL/v1/messages \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"anthropic/claude-3-5-sonnet-latest","max_tokens":1024,"messages":[{"role":"user","content":"Hi"}]}'
```

## Response shapes

OpenAI (`/v1/chat/completions`):
```json
{ "id": "chatcmpl-...", "object": "chat.completion", "model": "openai/gpt-4o-mini",
  "choices": [{ "index": 0, "message": { "role": "assistant", "content": "Hello!" }, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10 } }
```

Anthropic (`/v1/messages`):
```json
{ "id": "msg_...", "type": "message", "role": "assistant", "model": "anthropic/claude-3-5-sonnet-latest",
  "content": [{ "type": "text", "text": "Hello!" }],
  "stop_reason": "end_turn", "usage": { "input_tokens": 8, "output_tokens": 2 } }
```

## Errors

- 401 → set/refresh `RIHA_PROXY_KEY`
- 400 `Invalid model format` → check `model` exists in `/v1/models/<kind>`
- 503 `provider unavailable` → try another model or wait
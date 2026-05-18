---
name: rihaproxy-chat
description: Chat / code generation via RihaProxy using OpenAI /v1/chat/completions or Anthropic /v1/messages with streaming + auto-fallback combos.
---

# RihaProxy — Chat

Requires `RIHA_PROXY_URL` (and `RIHA_PROXY_KEY` if auth enabled). See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Endpoints

- `POST $RIHA_PROXY_URL/v1/chat/completions` — OpenAI format
- `POST $RIHA_PROXY_URL/v1/messages` — Anthropic format

## Discover models

```bash
curl $RIHA_PROXY_URL/v1/models | jq '.data[].id'
```

Combos (e.g. `combo/vip`) auto-fallback through multiple models.

## OpenAI format

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
const res = await client.chat.completions.create({ model: "openai/gpt-4o-mini", messages: [{ role: "user", content: "Hi" }], stream: true });
for await (const chunk of res) process.stdout.write(chunk.choices[0]?.delta?.content || "");
```

## Anthropic format (Claude Code)

```bash
curl -X POST $RIHA_PROXY_URL/v1/messages \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"anthropic/claude-3-5-sonnet-latest","max_tokens":1024,"messages":[{"role":"user","content":"Hi"}]}'
```

## Streaming

OpenAI streaming emits SSE: `data: {choices:[{delta:{content:"..."}}]}\n\n` ... `data: [DONE]\n\n`.

Anthropic streaming emits: `data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"..."}}\n\n`.

## Model combos

Create a combo via the admin API:
```bash
curl -X POST $RIHA_PROXY_URL/api/combos \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -d '{"name":"vip","models":["anthropic/claude-3-5-sonnet-latest","openai/gpt-4o-mini","google/gemini-2.5-flash-preview"]}'
```

Then use: `"model": "combo/vip"` — RihaProxy tries each in sequence until one succeeds.

## Provider quirks

| Provider | Model prefix | Notes |
|---|---|---|
| OpenAI, Anthropic, Google | `openai/`, `anthropic/`, `google/` | Route via OpenRouter |
| DeepSeek | `deepseek/` | Direct API |
| NVIDIA | `nvidia/` | Via NIM endpoints |
| LM Studio | `local/` | Local server, noAuth |
| OpenCode | `opencode/` | Claude 4.5 via opencode.ai |
| Local models | `local/` | llama.cpp / LM Studio |
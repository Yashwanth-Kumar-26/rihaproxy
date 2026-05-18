---
name: rihaproxy-embeddings
description: Vector embeddings via RihaProxy /v1/embeddings — OpenAI, Gemini, Mistral, Voyage, NVIDIA embedding models for RAG and semantic search.
---

# RihaProxy — Embeddings

Requires `RIHA_PROXY_URL`. See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Discover models

```bash
curl $RIHA_PROXY_URL/v1/models/embedding | jq '.data[].id'
```

## Endpoint

`POST $RIHA_PROXY_URL/v1/embeddings`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/embedding` |
| `input` | yes | string OR array of strings |
| `encoding_format` | no | `float` (default) / `base64` |
| `dimensions` | no | OpenAI v3 only |

## Examples

```bash
curl -X POST $RIHA_PROXY_URL/v1/embeddings \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/text-embedding-3-small","input":["hello","world"]}'
```

JS:
```js
const r = await fetch(`${process.env.RIHA_PROXY_URL}/v1/embeddings`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${process.env.RIHA_PROXY_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ model: "openai/text-embedding-3-small", input: "RAG chunk text" }),
});
const { data } = await r.json();
console.log(data[0].embedding.length);  // dimension
```

## Response shape

```json
{ "object": "list", "model": "openai/text-embedding-3-small",
  "data": [
    { "object": "embedding", "index": 0, "embedding": [0.0123, -0.045, ...] },
    { "object": "embedding", "index": 1, "embedding": [...] }
  ],
  "usage": { "prompt_tokens": 5, "total_tokens": 5 } }
```

## Provider quirks

| Provider | Notes |
|---|---|
| `openai`, `openrouter`, `mistral`, `voyage-ai` | Native OpenAI shape |
| `gemini` | Server auto-converts to `embedContent` |
| `cohere` | Standard OpenAI-compatible |
| `jina-ai` | Free tier available |
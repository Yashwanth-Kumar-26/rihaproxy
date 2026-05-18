---
name: rihaproxy-web-fetch
description: Fetch URL → markdown / text / HTML via RihaProxy /v1/web/fetch — Firecrawl, Jina Reader, Tavily Extract, Exa Contents.
---

# RihaProxy — Web Fetch

Requires `RIHA_PROXY_URL`. See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Discover providers

```bash
curl $RIHA_PROXY_URL/v1/models/web | jq '.data[] | select(.kind=="webFetch") | .id'
```

IDs end in `/fetch` (e.g. `firecrawl/fetch`, `jina/fetch`). `fetch-combo` chains providers with auto-fallback.

## Endpoint

`POST $RIHA_PROXY_URL/v1/web/fetch`

| Field | Required | Notes |
|---|---|---|
| `model` (or `provider`) | yes | from `/v1/models/web` |
| `url` | yes | URL to extract |
| `format` | no | `markdown` (default) / `text` / `html` |
| `max_characters` | no | truncate output |

## Examples

```bash
curl -X POST $RIHA_PROXY_URL/v1/web/fetch \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"firecrawl/fetch","url":"https://github.com","format":"markdown"}'
```

JS:
```js
const r = await fetch(`${process.env.RIHA_PROXY_URL}/v1/web/fetch`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${process.env.RIHA_PROXY_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ model: "jina/fetch", url: "https://example.com", format: "markdown", max_characters: 5000 }),
});
const { data } = await r.json();
console.log(data.title, data.content.length);
```

## Response shape

```json
{
  "provider": "firecrawl",
  "url": "https://example.com",
  "title": "Example Domain",
  "content": { "format": "markdown", "text": "...", "length": 1234 },
  "metadata": { "author": null, "published_at": null, "language": null },
  "usage": { "fetch_cost_usd": 0.002 },
  "metrics": { "response_time_ms": 850, "upstream_latency_ms": 700 }
}
```

## Provider quirks

| Provider | Auth | Best for |
|---|---|---|
| `firecrawl` | Bearer | JS-rendered pages, `format=markdown/html` |
| `jina-reader` | Bearer (optional) | Free tier (~1M chars/mo); fastest plain markdown |
| `tavily` | Bearer | Bulk extract; returns `raw_content` |
| `exa` | `x-api-key` | Pre-indexed pages; fast text extraction |
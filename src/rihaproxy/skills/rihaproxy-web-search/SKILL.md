---
name: rihaproxy-web-search
description: Web search via RihaProxy /v1/search — Tavily, Exa, Brave, Serper, Perplexity, Google PSE, SearXNG unified endpoint.
---

# RihaProxy — Web Search

Requires `RIHA_PROXY_URL`. See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Discover providers

```bash
curl $RIHA_PROXY_URL/v1/models/web | jq '.data[] | select(.kind=="webSearch") | .id'
```

IDs end in `/search` (e.g. `tavily/search`, `exa/search`). Combos chain providers with auto-fallback.

## Endpoint

`POST $RIHA_PROXY_URL/v1/search`

| Field | Required | Notes |
|---|---|---|
| `model` (or `provider`) | yes | from `/v1/models/web` |
| `query` | yes | search query |
| `max_results` | no | default 5 |
| `search_type` | no | `web` (default) / `news` |
| `country`, `language`, `time_range`, `domain_filter` | no | provider-dependent |

## Examples

```bash
curl -X POST $RIHA_PROXY_URL/v1/search \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tavily/search","query":"RihaProxy AI gateway open source","max_results":5}'
```

JS:
```js
const r = await fetch(`${process.env.RIHA_PROXY_URL}/v1/search`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${process.env.RIHA_PROXY_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ model: "tavily/search", query: "latest LLM benchmarks", max_results: 10 }),
});
console.log(await r.json());
```

## Response shape

```json
{
  "provider": "tavily",
  "query": "RihaProxy AI gateway",
  "results": [
    {
      "title": "...", "url": "https://...", "display_url": "github.com/...",
      "snippet": "...", "position": 1, "score": 0.92,
      "published_at": null, "favicon_url": null, "content": null,
      "metadata": { "author": null, "language": null },
      "citation": { "provider": "tavily", "retrieved_at": "2026-...", "rank": 1 }
    }
  ],
  "answer": null,
  "usage": { "queries_used": 1, "search_cost_usd": 0.008 },
  "metrics": { "response_time_ms": 850, "upstream_latency_ms": 700, "total_results_available": 12 },
  "errors": []
}
```

## Provider quirks

| Provider | Supports | Required extras |
|---|---|---|
| `tavily` | country, domain_filter, news | — |
| `exa` | domain_filter, news category | — |
| `brave-search` | country, language | — |
| `serper` | country, language, news | — |
| `perplexity` | country, language | — |
| `linkup` | domain_filter, time_range | `depth: fast/standard/deep` |
| `google-pse` | country, language, time_range | **`cx` required** |
| `searchapi` | country, language | — |
| `searxng` | language, time_range | Self-hosted, **noAuth** |
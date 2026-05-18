---
name: rihaproxy-image
description: Image generation via RihaProxy /v1/images/generations — OpenAI DALL-E, Google Imagen, Stability AI, FLUX, SDWebUI, ComfyUI models.
---

# RihaProxy — Image Generation

Requires `RIHA_PROXY_URL`. See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Discover models

```bash
curl $RIHA_PROXY_URL/v1/models/image | jq '.data[].id'
```

## Endpoint

`POST $RIHA_PROXY_URL/v1/images/generations`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/image` |
| `prompt` | yes | image description |
| `n` | no | count (1-10, default 1) |
| `size` | no | `1024x1024`, `1792x1024`, `1024x1792` |
| `quality` | no | `standard` / `hd` (OpenAI DALL-E 3) |
| `response_format` | no | `url` (default) or `b64_json` |
| `style` | no | `vivid` / `natural` (DALL-E 3) |

Query `?response_format=binary` to receive raw image bytes.

## Examples

Save to file (binary):

```bash
curl -X POST "$RIHA_PROXY_URL/v1/images/generations?response_format=binary" \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/dall-e-3","prompt":"watercolor mountains at sunrise","size":"1024x1024"}' \
  --output out.png
```

JSON response (`url`):
```json
{ "created": 1735000000, "data": [{ "url": "https://..." }] }
```

JSON response (`b64_json`):
```json
{ "created": 1735000000, "data": [{ "b64_json": "iVBORw0KGgo..." }] }
```

JS:
```js
const r = await fetch(`${process.env.RIHA_PROXY_URL}/v1/images/generations`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${process.env.RIHA_PROXY_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ model: "openai/dall-e-3", prompt: "neon city", size: "1024x1024" }),
});
const { data } = await r.json();
console.log(data[0].url || data[0].b64_json.slice(0, 40));
```

## Provider quirks

| Provider | Extra/changed fields | Notes |
|---|---|---|
| `openai` (dall-e-3) | `quality`, `style` | Standard OpenAI shape |
| `google` (imagen) | — | Ignores `size`/`n` |
| `stability` | `style` (preset), `output_format` | `size` → `aspect_ratio` |
| `black-forest-labs` (FLUX) | — | Async; `size` → exact `width`/`height` |
| `sdwebui`, `comfyui` | — | Localhost noAuth (`:7860` / `:8188`) |
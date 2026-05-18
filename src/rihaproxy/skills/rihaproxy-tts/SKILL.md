---
name: rihaproxy-tts
description: Text-to-speech via RihaProxy /v1/audio/speech — OpenAI TTS, ElevenLabs, Edge TTS, Google TTS, Deepgram voices.
---

# RihaProxy — Text-to-Speech

Requires `RIHA_PROXY_URL`. See https://raw.githubusercontent.com/rihaproxy/rihaproxy/main/skills/rihaproxy/SKILL.md for setup.

## Discover voices

```bash
curl $RIHA_PROXY_URL/v1/models/tts | jq '.data[].id'
```

`model` = voice ID (e.g. `openai/tts-1`, `openai/tts-1-hd`, `elevenlabs/eleven_multilingual_v2`).

## Endpoint

`POST $RIHA_PROXY_URL/v1/audio/speech`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | voice ID from `/v1/models/tts` |
| `input` | yes | text to speak |
| `voice` | no | voice name (default: alloy) |
| `speed` | no | 0.25-4.0 (default 1.0) |
| `response_format` | no | `mp3` (default), `opus`, `aac`, `flac` |

## Examples

Save MP3:

```bash
curl -X POST "$RIHA_PROXY_URL/v1/audio/speech" \
  -H "Authorization: Bearer $RIHA_PROXY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/tts-1","input":"Hello world","voice":"alloy"}' \
  --output speech.mp3
```

JS:
```js
const r = await fetch(`${process.env.RIHA_PROXY_URL}/v1/audio/speech`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${process.env.RIHA_PROXY_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ model: "openai/tts-1", input: "Hello world", voice: "alloy" }),
});
const buffer = await r.arrayBuffer();
require("fs").writeFileSync("speech.mp3", Buffer.from(buffer));
```

## Response

Default → raw audio bytes (Content-Type `audio/mp3`).

## Provider quirks

| Provider | `model` format | Notes |
|---|---|---|
| `openai` | `tts-1` / `tts-1-hd` | `voice` → model/voice |
| `elevenlabs` | `<model>/<voice_id>` or `<voice_id>` | Default model `eleven_flash_v2_5` |
| `edge-tts` | voice id e.g. `vi-VN-HoaiMyNeural` | **noAuth** |
| `google-tts` | language code e.g. `en`, `vi` | **noAuth** |
| `deepgram` | `aura-asteria-en` etc | Token auth |
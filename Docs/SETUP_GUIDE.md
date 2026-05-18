# RihaProxy — Setup Guide

## Requirements

- Python 3.10+
- pip or uv

## Installation

```bash
# Clone
git clone https://github.com/rihaproxy/rihaproxy.git
cd rihaproxy

# Install dependencies
pip install -e .
# or with uv:
uv pip install -e .

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

## Configuration

### Required: Authentication

```bash
# Generate a secure auth token
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output and set in .env:
AUTH_TOKEN=your_generated_token
```

### Optional: Provider API Keys

```bash
# OpenRouter (recommended — single key, 40+ models)
OPENROUTER_API_KEY=sk-or-v1-...

# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# DeepSeek
DEEPSEEK_API_KEY=...

# NVIDIA NIM
NVIDIA_API_KEY=nvapi-...

# Google AI / Gemini
GOOGLE_API_KEY=...

# LM Studio (local, no key needed)
LM_STUDIO_BASE_URL=http://localhost:1234

# Ruflo Orchestration
RUFLO_BASE_URL=http://localhost:3000
RUFLO_API_KEY=your_key
```

## Running

```bash
# Basic run
rihaproxy

# Or with uvicorn directly
python -m rihaproxy

# With custom port
RIHAPROXY_PORT=8080 rihaproxy
```

## Verify

```bash
curl http://localhost:16324/api/health
# → {"ok":true,"version":"0.1.0",...}
```

## Configuring Claude Code

```bash
# In ~/.claude/settings.json or project settings:
{
  "anthropic": {
    "baseUrl": "http://localhost:16324/v1/messages"
  }
}
```

## OpenAI SDK Clients

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:16324/v1",
    api_key="your_auth_token"
)

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Model Combos

Create a fallback chain:

```bash
curl -X POST http://localhost:16324/api/combos \
  -H "Authorization: Bearer your_auth_token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "vip",
    "models": [
      "anthropic/claude-3-5-sonnet-latest",
      "openai/gpt-4o",
      "google/gemini-2.5-flash-preview"
    ],
    "description": "Premium tier with auto-fallback"
  }'
```

Then use `combo/vip` as the model — RihaProxy tries each until one succeeds.

## Model Aliases

Shorten long model names:

```bash
curl -X POST http://localhost:16324/api/aliases \
  -H "Authorization: Bearer your_auth_token" \
  -H "Content-Type: application/json" \
  -d '{"alias": "opus", "target": "anthropic/claude-3-5-sonnet-latest"}'
```

## Token Compression

Enable RTK compression (20-40% savings):

```bash
# In .env
ENABLE_RTK=true
```

Enable Caveman mode (40-65% output savings):

```bash
# In .env
ENABLE_CAVEMAN=true
```

## Troubleshooting

### "Connection refused"

Server not running. Start with:
```bash
rihaproxy
```

### "401 Unauthorized"

Check your `AUTH_TOKEN` matches the `.env` value:
```bash
curl -H "Authorization: Bearer your_token" http://localhost:16324/api/health
```

### "Provider unavailable"

- Check API key is valid
- Provider may be rate-limited — wait and retry
- Try a different model in the fallback chain

### "Model not found"

Model not in `/v1/models` — check if provider supports it, or route through OpenRouter.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Format
ruff format src/
```

## Docker

```bash
docker build -t rihaproxy .
docker run -p 16324:16324 \
  -v ~/.rihaproxy:/root/.rihaproxy \
  -e AUTH_TOKEN=your_token \
  -e OPENROUTER_API_KEY=sk-or-... \
  rihaproxy
```

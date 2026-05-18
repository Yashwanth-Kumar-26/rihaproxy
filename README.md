# RihaProxy

Universal AI Gateway — one key, 40+ providers, auto-fallback.

RihaProxy is a high-performance, unified API gateway designed for **Claude Code**, **OpenCode**, and other major AI coding tools. It seamlessly translates between Anthropic, OpenAI, Gemini, and 40+ other provider formats into a single consistent endpoint.

## Quick Start

### Linux / macOS

```bash
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

### Windows

```cmd
setup.bat
start.bat
```

### Connect Claude Code

RihaProxy acts as a drop-in replacement for the Anthropic API:

```bash
export ANTHROPIC_BASE_URL="http://localhost:16324"
export ANTHROPIC_AUTH_TOKEN="your_rihaproxy_token"
claude
```

## Features

- **OpenAI-compatible REST surface** — `/v1/chat/completions`, `/v1/messages`, `/v1/images`, `/v1/audio`, `/v1/embeddings`, `/v1/search`, `/v1/web/fetch`
- **40+ provider support** — OpenRouter, LM Studio, NVIDIA NIM, DeepSeek, OpenCode, Codex, Kiro, Gemini, GitHub, and more
- **Native Anthropic support** — `/v1/messages` for Claude Code
- **Multi-format translation** — OpenAI, Anthropic, Gemini, Claude, OpenAI Responses API
- **Seamless compatibility** — Supports unversioned paths (`/messages`, `/chat/completions`) required by modern agents
- **Unified auth** — One token to rule them all. RihaProxy handles OAuth (GitHub, Claude, Kiro, Kimi) and API keys
- **BackendHub auto-fallback** — Automatic provider rotation on rate limits and server errors
- **Kiro integration** — Full OAuth login (Google, GitHub, SSO import), token refresh, and 7 Claude/DeepSeek/Qwen/GLM/MiniMax models
- **Performance** — Built on FastAPI with optimized SSE streaming for low-latency responses

## Supported Endpoints

| Endpoint | Description |
|---|---|
| `POST /v1/chat/completions` | OpenAI chat format |
| `POST /v1/messages` | Anthropic native format |
| `POST /v1/images/generations` | Image generation |
| `POST /v1/audio/speech` | Text-to-speech |
| `POST /v1/embeddings` | Vector embeddings |
| `POST /v1/search` | Web search |
| `POST /v1/web/fetch` | URL to markdown extraction |
| `GET /v1/models` | Discover available models |
| `GET /api/health` | Health check |
| `GET /api/status` | Gateway status |

## Authentication

- **GitHub OAuth** — Hardened flow with Copilot headers
- **Claude OAuth** — Support for CLI-based login
- **Kiro OAuth** — Device code (Builder ID), social login (Google/GitHub PKCE), and SSO cache import
- **OpenCode** — Integrated provider logic for zero-config usage
- **API keys** — Direct passthrough for providers that use static keys

## Architecture

```
Client → Gateway → Translation → Executors → Transport → Backends → Providers
                  ↓
             Storage (db.json + usage)
```

## Project Structure

```
rihaproxy/
├── src/rihaproxy/
│   ├── gateway/        # FastAPI server, routes, auth
│   ├── translation/    # Request/response format converters
│   ├── transport/      # HTTP transport protocols
│   ├── backends/       # Provider adapters (hub, registry, kiro, openai, etc.)
│   ├── executors/      # Specialized provider executors
│   ├── web/            # Web search and fetch
│   ├── auth/           # OAuth and token management
│   ├── storage/        # Persistence layer
│   ├── engine/         # RTK compression + Caveman mode
│   └── skills/         # Agent skill files
├── tests/
│   ├── unit/
│   └── integration/
└── Docs/
```

## Documentation

- [Setup Guide](Docs/SETUP_GUIDE.md)
- [Architecture](Docs/ARCHITECTURE.md)
- [API Reference](Docs/API.md)
- [Provider Configuration](Docs/PROVIDERS.md)

# RihaProxy — Architecture

## System Overview

```
Client Layer
    │
    ├─ Claude Code (Anthropic /messages)
    ├─ OpenAI SDK clients (/v1/chat/completions)
    ├─ Web agents (web search/fetch)
    ├─ Image/TTS/Embedding requests
    │
    ▼
Gateway Layer (FastAPI)
    │
    ├─ Auth Middleware (Bearer + Direct token)
    ├─ Router (model resolution, combos, aliases)
    ├─ Service (format detection, translation orchestration)
    └─ Routes (/v1/chat/completions, /v1/messages, ...)
        │
        ▼
Translation Layer
    │
    ├─ Format Detection (OpenAI, Anthropic, Gemini)
    ├─ Request Translators (openai→claude, claude→openai, ...)
    └─ Response Translators (claude→openai, gemini→openai, ...)
        │
        ▼
Backend Hub
    │
    ├─ Adapter Cache
    ├─ Provider Resolution
    └─ Fallback Chain
        │
        ▼
Adapter Layer
    │
    ├─ OpenRouter Adapter
    ├─ LM Studio Adapter
    ├─ NVIDIA NIM Adapter
    ├─ DeepSeek Adapter
    ├─ LlamaCpp Adapter
    └─ OpenCode Adapter
        │
        ▼
Transport Layer
    │
    ├─ MessagesTransport (Anthropic /messages)
    ├─ ChatCompletionsTransport (OpenAI /chat/completions)
    └─ ResponsesTransport (OpenAI /responses)
        │
        ▼
Provider Layer
    │
    ├─ OpenRouter (40+ models)
    ├─ Anthropic (Claude)
    ├─ Google (Gemini)
    ├─ DeepSeek
    ├─ NVIDIA NIM
    ├─ LM Studio (local)
    ├─ OpenCode
    └─ Web providers (Tavily, Exa, Firecrawl...)
```

## Core Components

### Gateway (`gateway/`)

| File | Purpose |
|---|---|
| `app.py` | FastAPI app factory, CORS, middleware |
| `routes.py` | All API endpoints |
| `auth.py` | Bearer + direct token auth middleware |
| `router.py` | Model resolution, combo/alias handling |
| `service.py` | Request orchestration, usage logging |
| `schemas.py` | Pydantic request/response models |

### Translation (`translation/`)

| File | Purpose |
|---|---|
| `formats.py` | Format registry, metadata, detection |
| `index.py` | Translation registry + orchestration |
| `request/openai_to_claude.py` | OpenAI → Anthropic |
| `request/claude_to_openai.py` | Anthropic → OpenAI |
| `request/openai_to_gemini.py` | OpenAI → Gemini |
| `request/gemini_to_openai.py` | Gemini → OpenAI |
| `request/openai_to_vertex.py` | OpenAI → Vertex AI |
| `request/openai_to_ollama.py` | OpenAI → Ollama |
| `response/claude_to_openai.py` | Anthropic → OpenAI response |
| `response/gemini_to_openai.py` | Gemini → OpenAI response |

### Transport (`transport/`)

| File | Purpose |
|---|---|
| `base.py` | Abstract base transport |
| `messages.py` | Anthropic /messages + SSE streaming |
| `chat_completions.py` | OpenAI /chat/completions |
| `responses.py` | OpenAI /responses |

### Backends (`backends/`)

| File | Purpose |
|---|---|
| `base.py` | BackendAdapter abstract base |
| `hub.py` | Adapter cache, provider resolution, fallback |
| `openrouter/adapter.py` | OpenRouter (40+ models) |
| `lmstudio/adapter.py` | LM Studio (local) |
| `nvidia/adapter.py` | NVIDIA NIM |
| `deepseek/adapter.py` | DeepSeek API |
| `llamacpp/adapter.py` | llama.cpp server |
| `opencode/adapters/*.py` | OpenCode (Go, Zen, Responses) |

### Engine (`engine/`)

| File | Purpose |
|---|---|
| `rtk.py` | RTK token compression (20-40% savings) |
| `caveman.py` | Aggressive output compression (40-65%) |

### Auth (`auth/`)

| File | Purpose |
|---|---|
| `oauth.py` | Device code OAuth flows |

### Storage (`storage/`)

| File | Purpose |
|---|---|
| `db.py` | JSON persistence (providers, combos, keys, usage) |

### Web (`web/`)

| File | Purpose |
|---|---|
| `search.py` | Web search (Tavily, Exa, Brave, Serper...) |
| `fetch.py` | URL → markdown (Firecrawl, Jina, Tavily) |

## Request Lifecycle

### OpenAI Path (`/v1/chat/completions`)

```
1. Client → POST /v1/chat/completions
2. Auth middleware validates token
3. Service detects source format (OpenAI)
4. Service resolves model → provider
5. Translation converts request to provider format (if needed)
6. Hub gets adapter for provider
7. Adapter sends request via transport
8. Provider returns response
9. Translation converts response to client format (if needed)
10. Usage logged to storage
11. Response returned to client
```

### Anthropic Path (`/v1/messages`)

```
1. Client → POST /v1/messages (Claude Code native)
2. Auth middleware validates token
3. Service detects source format (Anthropic)
4. Translation converts request to OpenAI (for OpenRouter) or keeps as-is
5. Hub routes to appropriate adapter
6. Adapter sends request via ChatCompletions or Messages transport
7. Response translated back to Anthropic format
8. Usage logged
9. Response returned
```

### Streaming Path

```
1. Service sets stream=True
2. Adapter sends streaming request to provider
3. SSE chunks are parsed
4. Each chunk translated (if needed)
5. Chunks streamed to client as SSE
6. Usage estimated (tokens not available until stream ends)
```

## Data Flow

```
Request Body
    │
    ├─ model: "anthropic/claude-3-5-sonnet-latest"
    ├─ messages: [...]
    └─ stream: true
    │
    ▼
Format Detection → "anthropic"
    │
    ▼
Router.resolve_model()
    ├─ Check aliases
    ├─ Check combos
    └─ Return resolved model
    │
    ▼
Hub.resolve_provider() → "anthropic"
    │
    ▼
Translation.translate_request(body, "anthropic", "openai")
    │
    ▼
Adapter.chat(messages, model, stream=true)
    │
    ▼
Transport.post("/v1/chat/completions", body, stream=true)
    │
    ▼
Provider SSE stream
    │
    ▼
Response translation (streaming chunks)
    │
    ▼
SSE stream to client
    │
    ▼
Usage logging
```

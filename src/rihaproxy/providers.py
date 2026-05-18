"""
Provider definitions and metadata ported from 9router.
"""

from __future__ import annotations

from typing import Any


class ProviderInfo:
    def __init__(
        self,
        id: str,
        name: str,
        alias: str | None = None,
        color: str | None = None,
        website: str | None = None,
        no_auth: bool = False,
        auth_type: str = "apikey",
        service_kinds: list[str] | None = None,
        **kwargs: Any
    ):
        self.id = id
        self.name = name
        self.alias = alias or id
        self.color = color
        self.website = website
        self.no_auth = no_auth or (auth_type == "none")
        self.auth_type = auth_type
        self.service_kinds = service_kinds or ["llm"]
        self.extra = kwargs

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "alias": self.alias,
            "color": self.color,
            "website": self.website,
            "no_auth": self.no_auth,
            "auth_type": self.auth_type,
            "service_kinds": self.service_kinds,
            **self.extra
        }


# Ported from 9router/src/shared/constants/providers.js
AI_PROVIDERS: dict[str, ProviderInfo] = {
    "kiro": ProviderInfo("kiro", "Kiro AI", alias="kr", color="#FF6B35", website="https://kiro.dev", auth_type="apikey"),
    "qwen": ProviderInfo("qwen", "Qwen Code", alias="qw", color="#10B981", website="https://chat.qwen.ai", auth_type="apikey"),
    "gemini-cli": ProviderInfo("gemini-cli", "Gemini CLI", alias="gc", color="#4285F4", website="https://github.com/google-gemini/gemini-cli", auth_type="apikey"),
    "iflow": ProviderInfo("iflow", "iFlow AI", alias="if", color="#6366F1", website="https://iflow.cn", auth_type="apikey"),
    "opencode": ProviderInfo("opencode", "OpenCode Free", alias="oc", color="#E87040", website="https://opencode.ai/zen/v1", auth_type="none"),
    "openrouter": ProviderInfo("openrouter", "OpenRouter", alias="openrouter", color="#F97316", website="https://openrouter.ai", auth_type="apikey"),
    "nvidia": ProviderInfo("nvidia", "NVIDIA NIM", alias="nvidia", color="#76B900", website="https://developer.nvidia.com/nim", auth_type="apikey"),
    "ollama": ProviderInfo("ollama", "Ollama Cloud", alias="ollama", color="#ffffffff", website="https://ollama.com", auth_type="apikey"),
    "vertex": ProviderInfo("vertex", "Vertex AI", alias="vx", color="#4285F4", website="https://cloud.google.com/vertex-ai", auth_type="apikey"),
    "gemini": ProviderInfo("gemini", "Gemini", alias="gemini", color="#4285F4", website="https://ai.google.dev", auth_type="apikey"),
    "cloudflare-ai": ProviderInfo("cloudflare-ai", "Cloudflare", alias="cf", color="#F38020", website="https://developers.cloudflare.com/workers-ai/", auth_type="apikey"),
    "byteplus": ProviderInfo("byteplus", "BytePlus ModelArk", alias="bpm", color="#2563EB", website="https://console.byteplus.com/ark", auth_type="apikey"),
    "claude": ProviderInfo("claude", "Claude Code", alias="cc", color="#D97757", website="https://claude.ai", auth_type="oauth"),
    "antigravity": ProviderInfo("antigravity", "Antigravity", alias="ag", color="#F59E0B", website="https://antigravity.google", auth_type="apikey"),
    "codex": ProviderInfo("codex", "OpenAI Codex", alias="cx", color="#3B82F6", website="https://chatgpt.com/codex", auth_type="oauth"),
    "github": ProviderInfo("github", "GitHub Copilot", alias="gh", color="#333333", website="https://github.com/features/copilot", auth_type="oauth"),
    "cursor": ProviderInfo("cursor", "Cursor IDE", alias="cu", color="#00D4AA", website="https://cursor.com", auth_type="oauth"),
    "kilocode": ProviderInfo("kilocode", "Kilo Code", alias="kc", color="#FF6B35", website="https://kilocode.ai", auth_type="oauth"),
    "cline": ProviderInfo("cline", "Cline", alias="cl", color="#5B9BD5", website="https://cline.bot", auth_type="oauth"),
    "glm": ProviderInfo("glm", "GLM Coding", alias="glm", color="#2563EB", website="https://open.bigmodel.cn", auth_type="apikey"),
    "glm-cn": ProviderInfo("glm-cn", "GLM (China)", alias="glm-cn", color="#DC2626", website="https://open.bigmodel.cn", auth_type="apikey"),
    "kimi": ProviderInfo("kimi", "Kimi", alias="kimi", color="#1E3A8A", website="https://kimi.moonshot.cn", auth_type="apikey"),
    "minimax": ProviderInfo("minimax", "Minimax Coding", alias="minimax", color="#7C3AED", website="https://www.minimaxi.com", auth_type="apikey"),
    "minimax-cn": ProviderInfo("minimax-cn", "Minimax (China)", alias="minimax-cn", color="#DC2626", website="https://www.minimaxi.com", auth_type="apikey"),
    "alicode": ProviderInfo("alicode", "Alibaba", alias="alicode", color="#FF6A00", website="https://bailian.console.aliyun.com", auth_type="apikey"),
    "alicode-intl": ProviderInfo("alicode-intl", "Alibaba Intl", alias="alicode-intl", color="#FF6A00", website="https://modelstudio.console.alibabacloud.com", auth_type="apikey"),
    "xiaomi-mimo": ProviderInfo("xiaomi-mimo", "Xiaomi MiMo", alias="mimo", color="#FF6900", website="https://xiaomimimo.com", auth_type="apikey"),
    "volcengine-ark": ProviderInfo("volcengine-ark", "Volcengine Ark", alias="ark", color="#1677FF", website="https://ark.cn-beijing.volces.com", auth_type="apikey"),
    "openai": ProviderInfo("openai", "OpenAI", alias="openai", color="#10A37F", website="https://platform.openai.com", auth_type="apikey"),
    "anthropic": ProviderInfo("anthropic", "Anthropic", alias="anthropic", color="#D97757", website="https://console.anthropic.com", auth_type="apikey"),
    "opencode-go": ProviderInfo("opencode-go", "OpenCode Go", alias="ocg", color="#E87040", website="https://opencode.ai/auth", auth_type="apikey"),
    "azure": ProviderInfo("azure", "Azure OpenAI", alias="azure", color="#0078D4", website="https://azure.microsoft.com", auth_type="apikey"),
    "deepseek": ProviderInfo("deepseek", "DeepSeek", alias="ds", color="#4D6BFE", website="https://deepseek.com", auth_type="apikey"),
    "commandcode": ProviderInfo("commandcode", "Command Code", alias="cmc", color="#000000", website="https://commandcode.ai", auth_type="apikey"),
    "groq": ProviderInfo("groq", "Groq", alias="groq", color="#F55036", website="https://groq.com", auth_type="apikey"),
    "xai": ProviderInfo("xai", "xAI (Grok)", alias="xai", color="#1DA1F2", website="https://x.ai", auth_type="apikey"),
    "mistral": ProviderInfo("mistral", "Mistral", alias="mistral", color="#FF7000", website="https://mistral.ai", auth_type="apikey"),
    "perplexity": ProviderInfo("perplexity", "Perplexity", alias="pplx", color="#20808D", website="https://www.perplexity.ai", auth_type="apikey"),
    "together": ProviderInfo("together", "Together AI", alias="together", color="#0F6FFF", website="https://www.together.ai", auth_type="apikey"),
    "fireworks": ProviderInfo("fireworks", "Fireworks AI", alias="fireworks", color="#7B2EF2", website="https://fireworks.ai", auth_type="apikey"),
    "cerebras": ProviderInfo("cerebras", "Cerebras", alias="cerebras", color="#FF4F00", website="https://www.cerebras.ai", auth_type="apikey"),
    "cohere": ProviderInfo("cohere", "Cohere", alias="cohere", color="#39594D", website="https://cohere.com", auth_type="apikey"),
    "nebius": ProviderInfo("nebius", "Nebius AI", alias="nebius", color="#6C5CE7", website="https://nebius.com", auth_type="apikey"),
    "siliconflow": ProviderInfo("siliconflow", "SiliconFlow", alias="siliconflow", color="#5B6EF5", website="https://cloud.siliconflow.com", auth_type="apikey"),
    "hyperbolic": ProviderInfo("hyperbolic", "Hyperbolic", alias="hyp", color="#00D4FF", website="https://hyperbolic.xyz", auth_type="apikey"),
    "deepgram": ProviderInfo("deepgram", "Deepgram", alias="dg", color="#13EF93", website="https://deepgram.com", auth_type="apikey"),
    "assemblyai": ProviderInfo("assemblyai", "AssemblyAI", alias="aai", color="#0062FF", website="https://assemblyai.com", auth_type="apikey"),
    "elevenlabs": ProviderInfo("elevenlabs", "ElevenLabs", alias="el", color="#6C47FF", website="https://elevenlabs.io", auth_type="apikey"),
    "cartesia": ProviderInfo("cartesia", "Cartesia", alias="cartesia", color="#FF4F8B", website="https://cartesia.ai", auth_type="apikey"),
    "playht": ProviderInfo("playht", "PlayHT", alias="playht", color="#00B4D8", website="https://play.ht", auth_type="apikey"),
    "inworld": ProviderInfo("inworld", "Inworld TTS", alias="inworld", color="#FF6B6B", website="https://inworld.ai", auth_type="apikey"),
    "voyage-ai": ProviderInfo("voyage-ai", "Voyage AI", alias="voyage", color="#0EA5E9", website="https://www.voyageai.com", auth_type="apikey"),
    "huggingface": ProviderInfo("huggingface", "HuggingFace", alias="hf", color="#FFD21E", website="https://huggingface.co", auth_type="apikey"),
    "blackbox": ProviderInfo("blackbox", "Blackbox AI", alias="bb", color="#5B5FEF", website="https://blackbox.ai", auth_type="apikey"),
    "chutes": ProviderInfo("chutes", "Chutes AI", alias="ch", color="#ffffffff", website="https://chutes.ai", auth_type="apikey"),
    "tavily": ProviderInfo("tavily", "Tavily", alias="tavily", color="#5B21B6", website="https://tavily.com", auth_type="apikey"),
    "brave-search": ProviderInfo("brave-search", "Brave Search", alias="brave", color="#FB542B", website="https://brave.com/search/api", auth_type="apikey"),
    "serper": ProviderInfo("serper", "Serper", alias="serper", color="#4F46E5", website="https://serper.dev", auth_type="apikey"),
    "exa": ProviderInfo("exa", "Exa", alias="exa", color="#2563EB", website="https://exa.ai", auth_type="apikey"),
    "searxng": ProviderInfo("searxng", "SearXNG", alias="searxng", color="#3B82F6", website="https://docs.searxng.org", auth_type="none"),
    "google-pse": ProviderInfo("google-pse", "Google PSE", alias="gpse", color="#4285F4", website="https://programmablesearchengine.google.com", auth_type="apikey"),
    "linkup": ProviderInfo("linkup", "Linkup", alias="linkup", color="#0EA5E9", website="https://linkup.so", auth_type="apikey"),
    "searchapi": ProviderInfo("searchapi", "SearchAPI", alias="searchapi", color="#0EA5A4", website="https://www.searchapi.io", auth_type="apikey"),
    "youcom": ProviderInfo("youcom", "You.com Search", alias="youcom", color="#7C3AED", website="https://you.com", auth_type="apikey"),
    "firecrawl": ProviderInfo("firecrawl", "Firecrawl", alias="firecrawl", color="#F59E0B", website="https://firecrawl.dev", auth_type="apikey"),
    "fal-ai": ProviderInfo("fal-ai", "Fal.ai", alias="fal", color="#2563EB", website="https://fal.ai", auth_type="apikey"),
    "stability-ai": ProviderInfo("stability-ai", "Stability AI", alias="stability", color="#8B5CF6", website="https://stability.ai", auth_type="apikey"),
    "black-forest-labs": ProviderInfo("black-forest-labs", "Black Forest Labs", alias="bfl", color="#111827", website="https://blackforestlabs.ai", auth_type="apikey"),
    "recraft": ProviderInfo("recraft", "Recraft", alias="recraft", color="#EC4899", website="https://recraft.ai", auth_type="apikey"),
    "topaz": ProviderInfo("topaz", "Topaz", alias="topaz", color="#059669", website="https://topazlabs.com", auth_type="apikey"),
    "runwayml": ProviderInfo("runwayml", "Runway ML", alias="runway", color="#000000", website="https://runwayml.com", auth_type="apikey"),
    "aws-polly": ProviderInfo("aws-polly", "AWS Polly", alias="polly", color="#FF9900", website="https://aws.amazon.com/polly/", auth_type="apikey"),
    "jina-ai": ProviderInfo("jina-ai", "Jina AI", alias="jina", color="#2563EB", website="https://jina.ai", auth_type="apikey"),
    "jina-reader": ProviderInfo("jina-reader", "Jina Reader", alias="jina", color="#000000", website="https://jina.ai/reader", auth_type="apikey"),
    "grok-web": ProviderInfo("grok-web", "Grok Web (Subscription)", alias="gw", color="#1DA1F2", website="https://grok.com", auth_type="cookie"),
    "perplexity-web": ProviderInfo("perplexity-web", "Perplexity Web (Pro/Max)", alias="pw", color="#20808D", website="https://www.perplexity.ai", auth_type="cookie"),
}

# Dynamic loading from generated registry
def _load_generated_providers():
    import json
    from pathlib import Path

    generated_path = Path(__file__).parent / "providers_generated.json"
    if not generated_path.exists():
        return

    try:
        with open(generated_path) as f:
            data = json.load(f)

        for p_id, p_info in data.items():
            if p_id not in AI_PROVIDERS:
                AI_PROVIDERS[p_id] = ProviderInfo(
                    id=p_id,
                    name=p_info.get("name", p_id),
                    alias=p_id,
                    website=p_info.get("doc", ""),
                    auth_type="apikey" if p_info.get("env") else "none"
                )
    except Exception as e:
        print(f"Warning: Failed to load generated providers: {e}")

_load_generated_providers()

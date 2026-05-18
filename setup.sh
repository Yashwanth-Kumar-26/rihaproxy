#!/bin/bash
# setup.sh - RihaProxy setup, claudefree-style.
#
# Run with: bash setup.sh
# Or source it if you want ANTHROPIC_* exported into the current shell:
#   source setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
ENV_FILE="$SCRIPT_DIR/.env"
TEMP_API=""

cd "$SCRIPT_DIR"

cleanup() {
    [ -n "$TEMP_API" ] && [ -f "$TEMP_API" ] && rm -f "$TEMP_API"
}
trap cleanup EXIT

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  RihaProxy Setup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}\n"

SHELL_CONFIG=""
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}[INFO] Creating .env${NC}"
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    else
        touch "$ENV_FILE"
    fi
fi

ALREADY_CONFIGURED=0
if grep -q "ANTHROPIC_BASE_URL=.*localhost:16324" "$SHELL_CONFIG" 2>/dev/null || \
   grep -q "ANTHROPIC_BASE_URL=.*localhost:16324" "$ENV_FILE" 2>/dev/null; then
    ALREADY_CONFIGURED=1
fi

if [ "$ALREADY_CONFIGURED" = "1" ]; then
    echo -e "${GREEN}[OK] Claude Code env already configured${NC}\n"
else
    echo -e "${YELLOW}[INFO] Claude Code env not configured - will set it up at the end${NC}\n"
fi

upsert_env() {
    local key=$1
    local value=$2
    grep -v "^${key}=" "$ENV_FILE" > "$ENV_FILE.tmp" || true
    echo "${key}=\"${value}\"" >> "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
}

read_env() {
    local key=$1
    grep "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2- | tr -d '"'
}

ensure_auth_token() {
    local token
    token="$(read_env AUTH_TOKEN)"
    if [ -z "$token" ] || [ "$token" = "your_auth_token_here" ]; then
        token="God"
        upsert_env "AUTH_TOKEN" "$token"
    fi
    upsert_env "ANTHROPIC_AUTH_TOKEN" "$token"
    upsert_env "ANTHROPIC_BASE_URL" "http://localhost:16324"
}

provider_env_key() {
    echo "$1" | tr '[:lower:]-' '[:upper:]_'
}

check_uv() {
    echo -e "${BLUE}[1/5] Checking uv...${NC}"
    if ! command -v uv &> /dev/null; then
        echo -e "${YELLOW}Installing uv...${NC}"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck source=/dev/null
        [ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"
    fi
    command -v uv &> /dev/null || { echo -e "${RED}[FAIL] uv not found${NC}"; exit 1; }
    echo -e "${GREEN}[OK] uv${NC}\n"
}

check_jq() {
    echo -e "${BLUE}[2/5] Checking jq...${NC}"
    if command -v jq &> /dev/null; then
        echo -e "${GREEN}[OK] jq${NC}\n"
        return
    fi

    echo -e "${YELLOW}jq not found. Trying package manager install...${NC}"
    case "$(uname -s)" in
        Linux*)
            if grep -qi 'fedora' /etc/os-release 2>/dev/null; then
                sudo dnf install -y jq 2>/dev/null || true
            elif grep -qi 'debian\|ubuntu' /etc/os-release 2>/dev/null; then
                sudo apt-get update && sudo apt-get install -y jq 2>/dev/null || true
            elif grep -qi 'arch' /etc/os-release 2>/dev/null; then
                sudo pacman -S jq --noconfirm 2>/dev/null || true
            fi
            ;;
        Darwin*)
            brew install jq 2>/dev/null || true
            ;;
    esac

    command -v jq &> /dev/null || { echo -e "${RED}[FAIL] jq is required. Install jq and rerun setup.${NC}"; exit 1; }
    echo -e "${GREEN}[OK] jq${NC}\n"
}

check_picker() {
    echo -e "${BLUE}[3/5] Checking fuzzy picker...${NC}"
    if command -v fzf &> /dev/null; then
        echo -e "${GREEN}[OK] fzf${NC}\n"
        return
    fi
    if command -v fzy &> /dev/null; then
        echo -e "${GREEN}[OK] fzy${NC}\n"
        return
    fi

    echo -e "${YELLOW}Installing fzf...${NC}"
    case "$(uname -s)" in
        Linux*)
            if grep -qi 'fedora' /etc/os-release 2>/dev/null; then
                sudo dnf install -y fzf 2>/dev/null || true
            elif grep -qi 'debian\|ubuntu' /etc/os-release 2>/dev/null; then
                sudo apt-get update && sudo apt-get install -y fzf 2>/dev/null || true
            elif grep -qi 'arch' /etc/os-release 2>/dev/null; then
                sudo pacman -S fzf --noconfirm 2>/dev/null || true
            fi
            ;;
        Darwin*)
            brew install fzf 2>/dev/null || true
            ;;
    esac

    if command -v fzf &> /dev/null; then
        echo -e "${GREEN}[OK] fzf${NC}\n"
    else
        echo -e "${YELLOW}[WARN] fzf/fzy unavailable. Falling back to numbered prompts.${NC}\n"
    fi
}

fetch_providers() {
    echo -e "${BLUE}[4/5] Fetching providers from models.dev...${NC}"
    TEMP_API="$(mktemp)"
    curl -s -H "User-Agent: Mozilla/5.0" https://models.dev/api.json > "$TEMP_API" || {
        echo -e "${RED}[FAIL] Could not fetch models.dev provider list${NC}"
        exit 1
    }
    cp "$TEMP_API" "$SCRIPT_DIR/src/rihaproxy/providers_generated.json" 2>/dev/null || true
    echo -e "${GREEN}[OK] providers fetched${NC}\n"
}

pick_from_list() {
    local prompt=$1
    local values=$2

    if command -v fzf &> /dev/null && [ -t 0 ]; then
        printf "%s\n" "$values" | fzf --prompt "$prompt"
        return
    fi
    if command -v fzy &> /dev/null && [ -t 0 ]; then
        printf "%s\n" "$values" | fzy --prompt "$prompt"
        return
    fi

    local arr=()
    while IFS= read -r item; do
        [ -n "$item" ] && arr+=("$item")
    done <<< "$values"
    for i in "${!arr[@]}"; do
        echo "$((i+1)). ${arr[$i]}" >&2
    done
    echo -n "Enter number: " >&2
    read -r n
    if [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le "${#arr[@]}" ]; then
        echo "${arr[$((n-1))]}"
    fi
}

provider_models() {
    local provider=$1
    jq -r ".\"$provider\".models | keys[]?" "$TEMP_API" 2>/dev/null | sort
}

recommended_models() {
    local provider=$1
    case "$provider" in
        github)
            MODEL_OPUS="github/claude-haiku-4.5"
            MODEL_SONNET="github/claude-haiku-4.5"
            MODEL_HAIKU="github/claude-haiku-4.5"
            ;;
        kiro)
            MODEL_OPUS="kiro/claude-sonnet-4.5"
            MODEL_SONNET="kiro/claude-sonnet-4.5"
            MODEL_HAIKU="kiro/claude-haiku-4.5"
            ;;
        anthropic)
            MODEL_OPUS="anthropic/claude-opus-4-20250514"
            MODEL_SONNET="anthropic/claude-sonnet-4-20250514"
            MODEL_HAIKU="anthropic/claude-3-5-haiku-20241022"
            ;;
        *)
            MODEL_OPUS="$provider/claude-opus-4.5"
            MODEL_SONNET="$provider/claude-sonnet-4.5"
            MODEL_HAIKU="$provider/claude-haiku-4.5"
            ;;
    esac
    MODEL_DEFAULT="$MODEL_SONNET"
}

select_model() {
    local tier=$1
    local recommended=$2
    local models=$3

    echo -e "${BLUE}Model for $tier:${NC}" >&2
    echo -e "Recommended: ${GREEN}$recommended${NC}" >&2

    local choices="[RECOMMENDED]
[CUSTOM_MODEL]"
    if [ -n "$models" ]; then
        choices="$choices
$models"
    fi

    local choice
    choice="$(pick_from_list "Search $tier model: " "$choices" || true)"
    case "$choice" in
        ""|"[RECOMMENDED]")
            echo "$recommended"
            ;;
        "[CUSTOM_MODEL]")
            echo -n "Custom model for $tier: " >&2
            read -r custom
            echo "${custom:-$recommended}"
            ;;
        *)
            echo "$choice"
            ;;
    esac
}

write_config() {
    local provider=$1
    cat > "$CONFIG_FILE" <<EOF
{
  "provider": "$provider",
  "model_default": "$MODEL_DEFAULT",
  "model_opus": "$MODEL_OPUS",
  "model_sonnet": "$MODEL_SONNET",
  "model_haiku": "$MODEL_HAIKU"
}
EOF
    upsert_env "DEFAULT_BACKEND" "$provider"
    chmod 600 "$ENV_FILE"
    echo -e "${GREEN}[OK] Saved config.json and .env${NC}\n"
}

configure_models() {
    local provider=$1
    local models
    models="$(provider_models "$provider")"
    recommended_models "$provider"

    echo -e "\n${BLUE}[5/5] Configure models for $provider${NC}"
    echo -e "Use recommended models? (Y/n)"
    read -r use_recommended
    if [[ "$use_recommended" =~ ^[Nn]$ ]]; then
        MODEL_DEFAULT="$(select_model "DEFAULT" "$MODEL_DEFAULT" "$models")"
        MODEL_OPUS="$(select_model "OPUS" "$MODEL_OPUS" "$models")"
        MODEL_SONNET="$(select_model "SONNET" "$MODEL_SONNET" "$models")"
        MODEL_HAIKU="$(select_model "HAIKU" "$MODEL_HAIKU" "$models")"
    fi
}

oauth_setup() {
    local provider=$1
    ensure_auth_token
    LOG_LEVEL=warning uv run rihaproxy login "$provider"
    configure_models "$provider"
    write_config "$provider"
}

default_setup() {
    local providers selected provider_upper api_key_var api_key
    providers="$(jq -r 'keys[]' "$TEMP_API" | sort)"

    echo -e "${BLUE}Select provider:${NC}"
    selected="$(pick_from_list "Search provider: " "$providers")"
    [ -z "$selected" ] && { echo -e "${RED}[FAIL] No provider selected${NC}"; exit 1; }
    echo -e "${GREEN}[OK] $selected${NC}\n"

    provider_upper="$(provider_env_key "$selected")"
    api_key_var="${provider_upper}_API_KEY"
    api_key="$(read_env "$api_key_var")"
    if [ -n "$api_key" ]; then
        echo -e "${GREEN}[OK] Existing $api_key_var found${NC}"
    else
        echo -n "Enter API key for $selected (leave blank to skip): "
        read -rs api_key
        echo ""
        [ -n "$api_key" ] && upsert_env "$api_key_var" "$api_key"
    fi

    ensure_auth_token
    configure_models "$selected"
    write_config "$selected"
}

setup_shell_env() {
    local token
    token="$(read_env AUTH_TOKEN)"
    [ -z "$token" ] && token="God"

    if [ "$ALREADY_CONFIGURED" = "0" ] && [ -n "$SHELL_CONFIG" ]; then
        echo -e "${BLUE}Setting up ANTHROPIC env vars in $SHELL_CONFIG...${NC}"
        [ -f "$SHELL_CONFIG" ] && cp "$SHELL_CONFIG" "$SHELL_CONFIG.backup"
        cat >> "$SHELL_CONFIG" <<EOF

# RihaProxy Claude Code Configuration
export ANTHROPIC_AUTH_TOKEN="$token"
export ANTHROPIC_BASE_URL="http://localhost:16324"
EOF
        echo -e "${GREEN}[OK] Added to $SHELL_CONFIG${NC}"
        echo -e "${YELLOW}Run: source $SHELL_CONFIG   (or restart terminal)${NC}"
    else
        echo -e "${GREEN}[OK] Shell env already configured or shell config not detected${NC}"
    fi

    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        export ANTHROPIC_AUTH_TOKEN="$token"
        export ANTHROPIC_BASE_URL="http://localhost:16324"
        echo -e "${GREEN}[OK] Exported to current shell${NC}"
    fi
}

install_start_helper() {
    echo ""
    echo -e "${BLUE}Installing rihaproxy-start-server to PATH...${NC}"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$SCRIPT_DIR/start.sh" "$HOME/.local/bin/rihaproxy-start-server" 2>/dev/null || \
        cp "$SCRIPT_DIR/start.sh" "$HOME/.local/bin/rihaproxy-start-server"
    chmod +x "$HOME/.local/bin/rihaproxy-start-server" 2>/dev/null || true
    echo -e "${GREEN}[OK] ~/.local/bin/rihaproxy-start-server${NC}"
}

check_claude_cli() {
    echo ""
    echo -e "${BLUE}Checking claude CLI...${NC}"
    if command -v claude &> /dev/null; then
        echo -e "${GREEN}[OK] claude found${NC}"
        return
    fi

    echo -e "${YELLOW}claude not found - installing via npm...${NC}"
    if command -v npm &> /dev/null; then
        npm install -g @anthropic-ai/claude-code || true
        command -v claude &> /dev/null && echo -e "${GREEN}[OK] claude installed${NC}" || \
            echo -e "${YELLOW}[WARN] claude install did not finish. Install @anthropic-ai/claude-code manually.${NC}"
    else
        echo -e "${YELLOW}[WARN] npm not found. Install Node.js first if you need Claude Code.${NC}"
    fi
}

check_uv
check_jq
check_picker
fetch_providers

echo -e "${BLUE}Setup mode:${NC}"
echo "1. Use GitHub OAuth (Copilot, recommended for Claude Code)"
echo "2. Use Kiro OAuth (AWS Builder ID / Kiro)"
echo "3. Default setup (choose any provider + API key + models)"
echo -n "Choice [1]: "
read -r setup_mode

case "$setup_mode" in
    2) oauth_setup "kiro" ;;
    3) default_setup ;;
    *) oauth_setup "github" ;;
esac

setup_shell_env
install_start_helper
check_claude_cli

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}[OK] Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Start proxy:  ${YELLOW}rihaproxy-start-server${NC}   or   ${YELLOW}./start.sh${NC}"
echo -e "  2. Run Claude:   ${YELLOW}claude${NC}"
echo -e ""
echo -e "  Config:  ${BLUE}$CONFIG_FILE${NC}"
echo -e "  Secrets: ${BLUE}$ENV_FILE${NC}"

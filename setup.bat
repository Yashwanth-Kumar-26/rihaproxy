@echo off
setlocal enabledelayedexpansion

:: RihaProxy Setup Script for Windows
:: This script configures your environment and API keys.

echo ╭──────────────────────────────────────────────────────────────────────────────╮
echo │                                                                              │
echo │  RihaProxy — Universal AI Gateway Setup                                      │
echo │  Configuring 60+ providers for your coding agents...                         │
echo │                                                                              │
echo ╰──────────────────────────────────────────────────────────────────────────────╯

:: 1. Check for UV
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] 'uv' not found.
    echo Please install uv from: https://astral.sh/uv
    pause
    exit /b
)

:: 2. Initialize .env if missing
if not exist .env (
    echo Creating new .env file...
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        type nul > .env
    )
)

:: 3. Interactive Configuration
echo.
echo --- Claude Code Setup Mode ---
echo   1) Use GitHub OAuth - Copilot token, fastest Claude Code path
echo   2) Use Kiro OAuth - AWS Builder ID / Kiro Claude-compatible path
echo   3) Default setup - API keys and provider selection
set /p SETUP_MODE="Setup mode [1-3, default 1]: "
if "%SETUP_MODE%"=="2" goto kiro_oauth_setup
if "%SETUP_MODE%"=="3" goto manual_setup
goto github_oauth_setup

:github_oauth_setup
call :ensure_auth_token
uv run rihaproxy login github
set DEF_PROV=github
goto write_backend_and_config

:kiro_oauth_setup
call :ensure_auth_token
uv run rihaproxy login kiro
set DEF_PROV=kiro
goto write_backend_and_config

:manual_setup
echo.
echo --- API Configuration ---
echo Leave blank to keep existing or skip.

call :set_env "AUTH_TOKEN" "Access Token (Security for your Gateway)"
call :set_env "OPENROUTER_API_KEY" "OpenRouter API Key (Highly Recommended)"
call :set_env "ANTHROPIC_API_KEY" "Anthropic API Key (Claude)"
call :set_env "OPENAI_API_KEY" "OpenAI API Key"
call :set_env "DEEPSEEK_API_KEY" "DeepSeek API Key"
call :ensure_auth_token

:: 4. OAuth Login Prompt
echo.
echo --- Optional OAuth Login ---
echo RihaProxy can connect to official providers to get tokens for you.
echo For Claude Code, GitHub Copilot and Kiro AI are recommended.
set /p DO_LOGIN="Do you want to log in now? (y/n): "
if /i "%DO_LOGIN%"=="y" (
    echo Select provider:
    echo   1) GitHub (Copilot/Codex)
    echo   2) Claude (Anthropic)
    echo   3) Kimi (Moonshot)
    echo   4) Qwen (Alibaba)
    echo   5) Kiro (AWS Builder ID)
    echo   6) Skip
    set /p PROV_CHOICE="Choice [1-6]: "
    if "%PROV_CHOICE%"=="1" uv run rihaproxy login github
    if "%PROV_CHOICE%"=="2" uv run rihaproxy login claude
    if "%PROV_CHOICE%"=="3" uv run rihaproxy login kimi-coding
    if "%PROV_CHOICE%"=="4" uv run rihaproxy login qwen
    if "%PROV_CHOICE%"=="5" uv run rihaproxy login kiro
)

:: 5. Generate Providers from models.dev
echo.
echo --- Provider Registry ---
echo Syncing latest 100+ providers from models.dev...
uv run python -c "import urllib.request, json; data = json.loads(urllib.request.urlopen('https://models.dev/api.json').read().decode()); open('src/rihaproxy/providers_generated.json', 'w').write(json.dumps(data, indent=2)); print('✅ Synced 100+ providers')"

:: 6. Model Preferences
echo.
echo --- Model ^& Provider Preferences ---
echo Which provider should be your default for Claude Code?
echo   1) GitHub (Copilot) - Recommended for Claude Code
echo   2) Kiro AI
echo   3) OpenRouter
echo   4) Anthropic (Official)
echo   5) DeepSeek
echo   6) OpenCode
set /p PREF_CHOICE="Default Provider [1-6]: "
if "%PREF_CHOICE%"=="1" set DEF_PROV=github
if "%PREF_CHOICE%"=="2" set DEF_PROV=kiro
if "%PREF_CHOICE%"=="3" set DEF_PROV=openrouter
if "%PREF_CHOICE%"=="4" set DEF_PROV=anthropic
if "%PREF_CHOICE%"=="5" set DEF_PROV=deepseek
if "%PREF_CHOICE%"=="6" set DEF_PROV=opencode
if "%DEF_PROV%"=="" set DEF_PROV=github

:write_backend_and_config
:: Update .env
findstr /v /c:"DEFAULT_BACKEND=" .env > .env.tmp
echo DEFAULT_BACKEND="%DEF_PROV%" >> .env.tmp
move /y .env.tmp .env >nul
echo ✅ Default backend set to: %DEF_PROV%

:: Create config.json
echo Configuring Model Tiers (for Claude Code integration)...
if "%DEF_PROV%"=="github" (
    set MODEL_OPUS=github/claude-haiku-4.5
    set MODEL_SONNET=github/claude-haiku-4.5
    set MODEL_HAIKU=github/claude-haiku-4.5
) else if "%DEF_PROV%"=="kiro" (
    set MODEL_OPUS=kiro/claude-sonnet-4.5
    set MODEL_SONNET=kiro/claude-sonnet-4.5
    set MODEL_HAIKU=kiro/claude-haiku-4.5
) else if "%DEF_PROV%"=="anthropic" (
    set MODEL_OPUS=anthropic/claude-opus-4-20250514
    set MODEL_SONNET=anthropic/claude-sonnet-4-20250514
    set MODEL_HAIKU=anthropic/claude-3-5-haiku-20241022
) else (
    set MODEL_OPUS=%DEF_PROV%/claude-opus-4.5
    set MODEL_SONNET=%DEF_PROV%/claude-sonnet-4.5
    set MODEL_HAIKU=%DEF_PROV%/claude-haiku-4.5
)
set MODEL_DEFAULT=%MODEL_SONNET%
echo.
set /p PICK_MODELS="Select exact models for %DEF_PROV%? (y/n): "
if /i "%PICK_MODELS%"=="y" (
    call :pick_model "DEFAULT" "%MODEL_DEFAULT%" MODEL_DEFAULT
    call :pick_model "OPUS" "%MODEL_OPUS%" MODEL_OPUS
    call :pick_model "SONNET" "%MODEL_SONNET%" MODEL_SONNET
    call :pick_model "HAIKU" "%MODEL_HAIKU%" MODEL_HAIKU
)
echo { > config.json
echo   "provider": "%DEF_PROV%", >> config.json
echo   "model_opus": "%MODEL_OPUS%", >> config.json
echo   "model_sonnet": "%MODEL_SONNET%", >> config.json
echo   "model_haiku": "%MODEL_HAIKU%", >> config.json
echo   "model_default": "%MODEL_DEFAULT%" >> config.json
echo } >> config.json
echo ✅ Created config.json with tier mappings.

:: 7. Finalize
echo.
echo Setup Complete! RihaProxy is ready to serve.
echo.
echo ╭──────────────────────────────────────────────────────────────────────────────╮
echo │  🚀 CLAUDE CODE INTEGRATION (Recommended)                                    │
echo ╰──────────────────────────────────────────────────────────────────────────────╯
echo To use RihaProxy with Claude Code, run these commands in your terminal:
echo.
echo   set ANTHROPIC_BASE_URL=http://localhost:16324
echo   set ANTHROPIC_AUTH_TOKEN=your_token
echo   claude
echo.
echo RihaProxy will now intercept Claude Code's requests and route them
echo to your configured providers (GitHub, OpenRouter, DeepSeek, etc.)

echo.
echo ╭──────────────────────────────────────────────────────────────────────────────╮
echo │  🛠️  OTHER AGENTS                                                             │
echo ╰──────────────────────────────────────────────────────────────────────────────╯
echo OpenCode / OpenAI CLI:
echo   set OPENAI_BASE_URL=http://localhost:16324/v1
echo   set OPENAI_API_KEY=your_auth_token

echo.
echo --- Gateway Management ---
echo Start Gateway: start.bat
echo Dashboard:     http://localhost:16324/api/status
echo Health Check:  http://localhost:16324/api/health
echo.
pause
exit /b
pause
exit /b

:set_env
set "KEY=%~1"
set "DESC=%~2"
set "VAL="
set /p VAL="%DESC%: "
if not "!VAL!"=="" (
    :: Basic way to update .env in batch
    findstr /v /c:"!KEY!=" .env > .env.tmp
    echo !KEY!="!VAL!" >> .env.tmp
    move /y .env.tmp .env >nul
    echo ✓ !KEY! updated
)
goto :eof

:pick_model
set "TIER=%~1"
set "RECOMMENDED=%~2"
set "OUTVAR=%~3"
echo.
echo Model for %TIER%
echo Recommended: %RECOMMENDED%
set "CUSTOM_MODEL="
set /p CUSTOM_MODEL="Enter model ID or leave blank for recommended: "
if "%CUSTOM_MODEL%"=="" (
    set "%OUTVAR%=%RECOMMENDED%"
) else (
    set "%OUTVAR%=%CUSTOM_MODEL%"
)
goto :eof

:ensure_auth_token
set "CURRENT_TOKEN="
for /f "tokens=1,* delims==" %%A in ('findstr /b "AUTH_TOKEN=" .env 2^>nul') do set "CURRENT_TOKEN=%%~B"
set "CURRENT_TOKEN=%CURRENT_TOKEN:"=%"
if "%CURRENT_TOKEN%"=="" set CURRENT_TOKEN=God
if "%CURRENT_TOKEN%"=="your_auth_token_here" set CURRENT_TOKEN=God
findstr /v /c:"AUTH_TOKEN=" .env | findstr /v /c:"ANTHROPIC_AUTH_TOKEN=" > .env.tmp
echo AUTH_TOKEN="%CURRENT_TOKEN%" >> .env.tmp
echo ANTHROPIC_AUTH_TOKEN="%CURRENT_TOKEN%" >> .env.tmp
move /y .env.tmp .env >nul
goto :eof

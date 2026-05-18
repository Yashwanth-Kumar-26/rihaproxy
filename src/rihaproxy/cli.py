"""
CLI Command handlers for RihaProxy.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()

def run_setup() -> None:
    """Run the setup script."""
    setup_script = Path(__file__).parent.parent.parent / "setup.sh"
    if not setup_script.exists():
        console.print("[bold red]Error:[/bold red] setup.sh not found in the project root.")
        sys.exit(1)
    
    try:
        subprocess.run(["bash", str(setup_script)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Setup failed[/bold red] with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled by user.[/yellow]")
        sys.exit(0)

def list_providers() -> None:
    """List available providers."""
    from rihaproxy.backends.hub import get_hub
    hub = get_hub()
    console.print("[bold cyan]Available Providers:[/bold cyan]")
    providers = hub.providers
    if not providers:
        console.print("  [dim]No providers registered.[/dim]")
        return
    for p in sorted(providers):
        console.print(f"  • {p}")

def list_models() -> None:
    """List available models."""
    from rihaproxy.gateway.router import get_router
    router = get_router()
    console.print("[bold cyan]Available Models:[/bold cyan]")
    models = router.get_models()
    if not models:
        console.print("  [dim]No models found in registry.[/dim]")
        return
    for m in models:
        provider = m.get('owned_by', 'unknown')
        name = m.get('name', 'Unknown')
        console.print(f"  • [bold]{m['id']}[/bold] [dim]({name} - {provider})[/dim]")

def handle_cli() -> bool:
    """
    Parse arguments and execute CLI commands if specified.
    Returns True if a CLI command was executed, False if the server should run.
    """
    if len(sys.argv) <= 1:
        return False
        
    parser = argparse.ArgumentParser(
        description="RihaProxy — Universal AI Gateway",
        add_help=False
    )
    
    # We only want to intercept known commands and let uvicorn handle the rest if needed,
    # or just use standard argparse for subcommands.
    subparsers = parser.add_subparsers(dest="command")
    
    setup_parser = subparsers.add_parser("setup", help="Run the interactive setup script")
    providers_parser = subparsers.add_parser("providers", help="List available providers")
    models_parser = subparsers.add_parser("models", help="List available models")
    
    login_parser = subparsers.add_parser("login", help="Interactive OAuth login for a provider")
    login_parser.add_argument("provider", help="Provider to login to (claude, codex, google, kiro, cursor)")
    login_parser.add_argument("--method", choices=["builder-id", "google", "github", "import"],
                              help="Auth method for Kiro (builder-id, google, github, import)")
    login_parser.add_argument("--token", help="Refresh token for Kiro import method")
    
    # If the first argument isn't one of our subcommands, let the main server run
    if sys.argv[1] not in ["setup", "providers", "models", "login"]:
        return False
        
    args, unknown = parser.parse_known_args()
    
    if args.command == "setup":
        run_setup()
        return True
    elif args.command == "providers":
        list_providers()
        return True
    elif args.command == "models":
        list_models()
        return True
    elif args.command == "login":
        run_login(args.provider)
        return True
        
    return False

def run_login(provider: str, method: str | None = None, token: str | None = None) -> None:
    """Run interactive OAuth login."""
    import asyncio
    from rihaproxy.auth.oauth import (
        start_device_flow,
        complete_device_flow,
        build_kiro_social_login_url,
        exchange_kiro_social_code,
        import_kiro_token,
        extract_email_from_kiro_jwt,
    )
    from rihaproxy.auth.token_manager import get_token_manager
    import time

    async def _login():
        try:
            console.print(f"[bold cyan]Starting OAuth login for {provider}...[/bold cyan]")

            # --- Kiro: Import token method ---
            if provider == "kiro" and method == "import":
                if not token:
                    console.print("[bold yellow]Token required for import method.[/bold yellow]")
                    console.print("Paste your Kiro refresh token (starts with aorAAAAAG):")
                    token = console.input("[dim]Refresh token: [/dim]").strip()

                console.print("[dim]Validating and importing token...[/dim]")
                tokens = await import_kiro_token(token)
                email = extract_email_from_kiro_jwt(tokens["access_token"])
                if email:
                    console.print(f"[dim]Account: {email}[/dim]")

                tm = get_token_manager()
                expires_at = time.time() + tokens.get("expires_in", 3600)
                await tm.connect_provider(
                    provider="kiro",
                    auth_type="oauth",
                    name=f"Kiro (imported)",
                    credentials={
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "expires_at": str(expires_at),
                        "scope": "codewhisperer:completions codewhisperer:analysis codewhisperer:conversations",
                        "provider_data": tokens.get("provider_data", {}),
                        "profile_arn": tokens.get("profile_arn"),
                    },
                )
                console.print(f"\n[bold green]✓ Successfully imported Kiro token![/bold green]")
                return

            # --- Kiro: Social login (Google/GitHub) ---
            if provider == "kiro" and method in ("google", "github"):
                login_info = build_kiro_social_login_url(provider=method)
                console.print("\n[bold yellow]ACTION REQUIRED[/bold yellow]")
                console.print(f"1. Open: [link={login_info['url']}]{login_info['url']}[/link]")
                console.print(f"2. Complete login in your browser")
                console.print(f"3. After login, copy the full redirect URL (kiro://...) from your browser's address bar")

                callback_url = console.input("\n[dim]Paste the kiro:// redirect URL: [/dim]").strip()
                console.print("[dim]Exchanging authorization code...[/dim]")

                tokens = await exchange_kiro_social_code(
                    callback_url,
                    login_info["code_challenge"],
                )
                email = extract_email_from_kiro_jwt(tokens["access_token"])
                if email:
                    console.print(f"[dim]Account: {email}[/dim]")

                tm = get_token_manager()
                expires_at = time.time() + tokens.get("expires_in", 3600)
                await tm.connect_provider(
                    provider="kiro",
                    auth_type="oauth",
                    name=f"Kiro ({method})",
                    credentials={
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "expires_at": str(expires_at),
                        "scope": "codewhisperer:completions codewhisperer:analysis codewhisperer:conversations",
                        "provider_data": tokens.get("provider_data", {}),
                        "profile_arn": tokens.get("profile_arn"),
                    },
                )
                console.print(f"\n[bold green]✓ Successfully authenticated with Kiro via {method}![/bold green]")
                return

            # --- Kiro: Builder ID (default) or other providers ---
            result = await start_device_flow(provider)

            console.print("\n[bold yellow]ACTION REQUIRED[/bold yellow]")
            console.print(f"1. Open: [link={result['verification_url']}]{result['verification_url']}[/link]")
            console.print(f"2. Enter Code: [bold green]{result['user_code']}[/bold green]")
            console.print(f"\n[dim]Waiting for authentication (expires in {result['expires_in']}s)...[/dim]")

            # Poll for completion
            device_code = result['device_code']
            if provider == "kiro":
                from rihaproxy.auth.oauth import complete_kiro_device_flow
                pdata = result.get("provider_data", {})
                tokens = await complete_kiro_device_flow(
                    device_code,
                    pdata.get("client_id"),
                    pdata.get("client_secret"),
                )
                tokens["provider_data"] = {**pdata, **tokens.get("provider_data", {})}
            else:
                tokens = await complete_device_flow(provider, device_code)

            # Save to TokenManager
            tm = get_token_manager()
            expires_at = time.time() + tokens.get("expires_in", 3600)

            await tm.connect_provider(
                provider=provider,
                auth_type="oauth",
                name=f"{provider.capitalize()} Connection",
                credentials={
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "expires_at": str(expires_at),
                    "scope": tokens.get("scope"),
                    "provider_data": tokens.get("provider_data", {}),
                    "profile_arn": tokens.get("profile_arn"),
                }
            )

            console.print(f"\n[bold green]✓ Successfully authenticated with {provider}![/bold green]")
            console.print(f"[dim]Connection saved to internal storage.[/dim]")

        except Exception as e:
            console.print(f"\n[bold red]Login failed:[/bold red] {str(e)}")

    asyncio.run(_login())

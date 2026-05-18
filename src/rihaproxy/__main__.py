"""
Main entry point for the RihaProxy server.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

sys.path.insert(0, str(Path(__file__).parent.parent))

from rihaproxy.config import Settings
from rihaproxy.gateway.app import create_app

console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def print_banner(settings: Settings) -> None:
    """Print startup banner."""
    console.print(
        Panel(
            "[bold cyan]RihaProxy[/bold cyan] — Universal AI Gateway\n"
            "[dim]One key · 40+ providers · Auto-fallback[/dim]",
            border_style="cyan",
        )
    )
    console.print(f"  [dim]Port:[/dim]   [bold]{settings.port}[/bold]")
    console.print(f"  [dim]Host:[/dim]   [bold]{settings.host}[/bold]")
    console.print(f"  [dim]Data:[/dim]   [bold]{settings.data_dir}[/bold]")
    console.print(f"  [dim]Auth:[/dim]   [bold]{'✓ Enabled' if settings.auth_token else '✗ Disabled'}[/bold]")
    console.print()


def main() -> None:
    """Run the RihaProxy server."""
    from rihaproxy.cli import handle_cli
    if handle_cli():
        sys.exit(0)

    settings = Settings()

    setup_logging(settings.log_level)

    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    print_banner(settings)

    try:
        app = create_app(settings)
        import uvicorn

        console.print(
            Rule("[cyan]Starting server...[/cyan]"),
            style="dim",
        )
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
            access_log=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()

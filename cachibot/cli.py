"""
Cachibot CLI

Beautiful command-line interface using Typer and Rich.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

from cachibot import __version__
from cachibot.agent import CachibotAgent
from cachibot.config import Config
from cachibot.db_commands import db_app, setup_db_app

# Custom theme for Cachibot
CACHIBOT_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "thinking": "dim italic",
        "tool": "magenta",
        "user": "bold blue",
        "assistant": "bold green",
        "cost": "dim cyan",
    }
)

console = Console(theme=CACHIBOT_THEME)
app = typer.Typer(
    name="cachibot",
    help="Cachibot - The Armored AI Agent",
    no_args_is_help=False,
)

# Database management sub-commands
app.add_typer(db_app, name="db", help="Database management commands")
app.add_typer(setup_db_app, name="setup-db", help="Database setup wizards")

# Telemetry sub-commands
telemetry_app = typer.Typer(name="telemetry", help="Anonymous telemetry management")
app.add_typer(telemetry_app, name="telemetry")


def print_banner() -> None:
    """Print the Cachibot banner."""
    banner = f"""
[bold cyan]    ╭─────────╮
   ╱ ◉     ◉  ╲
  │  ─────────  │
  │   ╲_____╱   │    [bold white]Cachibot[/] v{__version__}
   ╲ ═══════   ╱     [dim]The Armored Agent[/]
    ╲ ═════   ╱
     ╰═══════╯[/]
"""
    console.print(banner)


def print_welcome(config: Config) -> None:
    """Print welcome message with workspace info."""
    console.print(
        f"   [dim]Workspace:[/] {config.workspace_path}\n"
        f"   [dim]Model:[/] {config.agent.model}\n"
        f"   [dim]Type [bold]exit[/] to leave, [bold]help[/] for commands[/]\n"
    )


def format_approval_dialog(tool_name: str, action: str, details: dict[str, Any]) -> bool:
    """Show approval dialog for risky operations."""
    console.print()
    console.print(
        Panel(
            f"[warning]Approval Required[/]\n\nTool: [bold]{tool_name}[/]\nAction: {action}",
            title="Security Check",
            border_style="yellow",
        )
    )

    # Show code if present
    if "code" in details:
        console.print(
            Panel(
                Syntax(details["code"], "python", theme="monokai", line_numbers=True),
                title="Code to Execute",
                border_style="dim",
            )
        )

    # Show risk reasons
    if "reasons" in details:
        console.print("[dim]Risk factors:[/]")
        for reason in details["reasons"]:
            console.print(f"  - {reason}")

    console.print()
    return Confirm.ask("  [bold]Approve this action?[/]", default=False)


def print_usage(run_usage: dict[str, Any], steps: int = 0) -> None:
    """Print token usage and cost from AgentResult.run_usage."""
    total_tokens = run_usage.get("total_tokens", 0)
    if total_tokens > 0:
        cost = run_usage.get("cost", 0.0)
        elapsed_ms = run_usage.get("total_elapsed_ms", 0.0)
        tps = run_usage.get("tokens_per_second", 0.0)
        parts = [
            f"Tokens: {total_tokens:,}",
            f"Cost: ${cost:.4f}",
            f"Steps: {steps}",
        ]
        if elapsed_ms > 0:
            parts.append(f"Time: {elapsed_ms / 1000:.1f}s")
        if tps > 0:
            parts.append(f"Speed: {tps:.0f} tok/s")
        console.print(f"\n  [cost]{' | '.join(parts)}[/]")


def create_agent_with_callbacks(config: Config) -> CachibotAgent:
    """Create an agent with CLI callbacks configured."""

    def on_thinking(text: str) -> None:
        if config.display.show_thinking:
            # Truncate long thinking
            if len(text) > 200:
                text = text[:197] + "..."
            console.print(f"  [thinking]{text}[/]")

    def on_tool_start(name: str, args: dict[str, Any]) -> None:
        # Show tool being called
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(args.items())[:3])
        if len(args_str) > 60:
            args_str = args_str[:57] + "..."
        console.print(f"  [tool]> {name}[/]([dim]{args_str}[/])")

    def on_tool_end(name: str, result: str) -> None:
        # Show brief result
        if result:
            lines = str(result).split("\n")
            preview = lines[0][:80]
            if len(lines) > 1 or len(lines[0]) > 80:
                preview += "..."
            console.print(f"  [success]OK[/] [dim]{preview}[/]")

    def on_approval_needed(tool_name: str, action: str, details: dict[str, Any]) -> bool:
        return format_approval_dialog(tool_name, action, details)

    agent = CachibotAgent(
        config=config,
        on_thinking=on_thinking,
        on_tool_start=on_tool_start,
        on_tool_end=on_tool_end,
        on_approval_needed=on_approval_needed,
    )

    return agent


@app.command()
def main(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Working directory for the agent",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (e.g., openai/gpt-4o, claude/claude-sonnet-4-20250514)",
    ),
    approve: bool = typer.Option(
        False,
        "--approve",
        "-a",
        help="Require approval for each action",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show thinking process",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
    ),
    task: str | None = typer.Argument(
        None,
        help="Task to run (if not provided, enters interactive mode)",
    ),
) -> None:
    """
    Cachibot - The Armored AI Agent

    Run with a task argument for single execution, or without for interactive mode.

    Examples:

        cachibot "list all Python files"

        cachibot --approve "clean up temp files"

        cachibot --workspace ./my-project

        cachibot --model claude/claude-sonnet-4-20250514 "explain this code"
    """
    # Handle version flag
    if version:
        console.print(f"Cachibot v{__version__}")
        raise typer.Exit()

    # Load configuration
    config = Config.load(
        workspace=workspace,
        config_file=config_file,
    )

    # Apply CLI overrides
    if model:
        config.agent.model = model
    if approve:
        config.agent.approve_actions = True
    if verbose:
        config.display.show_thinking = True

    # Create agent
    try:
        agent = create_agent_with_callbacks(config)
    except Exception as e:
        console.print(f"[error]Error creating agent: {e}[/]")
        raise typer.Exit(1)

    # Single task mode
    if task:
        try:
            console.print()
            result = asyncio.run(agent.run(task))
            console.print("\n[assistant]Cachibot:[/]")
            console.print(Markdown(result.output_text or "Task completed."))

            if config.display.show_cost:
                print_usage(result.run_usage, steps=len(result.steps))
        except Exception as e:
            console.print(f"[error]Error: {e}[/]")
            raise typer.Exit(1)
        raise typer.Exit()

    # Interactive mode
    print_banner()
    print_welcome(config)

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[user]You[/]")

            # Handle special commands
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n[dim]Goodbye![/]\n")
                break

            if user_input.lower() == "help":
                print_help()
                continue

            if user_input.lower() == "clear":
                agent.clear_history()
                console.print("[dim]History cleared.[/]")
                continue

            if user_input.lower() == "config":
                print_config(config)
                continue

            if not user_input.strip():
                continue

            # Run the agent
            console.print()
            result = asyncio.run(agent.run(user_input))

            # Print response
            console.print("\n[assistant]Cachibot:[/]")
            console.print(Markdown(result.output_text or "Task completed."))

            # Show usage
            if config.display.show_cost:
                print_usage(result.run_usage, steps=len(result.steps))

        except KeyboardInterrupt:
            console.print("\n\n[dim]Use 'exit' to quit properly.[/]")
            continue
        except Exception as e:
            console.print(f"\n[error]Error: {e}[/]")
            continue


@app.command("run")
def run_task(
    task: str = typer.Argument(..., help="Task to execute"),
    workspace: Path | None = typer.Option(None, "--workspace", "-w"),
    model: str | None = typer.Option(None, "--model", "-m"),
    approve: bool = typer.Option(False, "--approve", "-a"),
) -> None:
    """Run a single task and exit."""
    config = Config.load(workspace=workspace)

    if model:
        config.agent.model = model
    if approve:
        config.agent.approve_actions = True

    agent = create_agent_with_callbacks(config)

    try:
        result = asyncio.run(agent.run(task))
        console.print(Markdown(result.output_text or "Task completed."))

        if config.display.show_cost:
            print_usage(result.run_usage, steps=len(result.steps))
    except Exception as e:
        console.print(f"[error]Error: {e}[/]")
        raise typer.Exit(1)


@app.command("server")
def server(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Server host"),
    port: int = typer.Option(5870, "--port", "-p", help="Server port"),
    workspace: Path | None = typer.Option(None, "--workspace", "-w", help="Workspace path"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload (dev mode)"),
) -> None:
    """Start the Cachibot API server."""
    from cachibot.api.server import run_server as start_api_server

    console.print(f"[info]Starting Cachibot server on http://{host}:{port}[/]")
    start_api_server(host=host, port=port, workspace=workspace, reload=reload)


@app.command("reset-password")
def reset_password(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
) -> None:
    """Reset a user's password from the command line.

    The password is SHA-256 hashed before bcrypt (matching the frontend).

    Examples:

        cachibot reset-password admin

        cachibot reset-password user@example.com
    """
    import hashlib

    async def _reset() -> None:
        from cachibot.services.auth_service import get_auth_service
        from cachibot.storage import db
        from cachibot.storage.user_repository import UserRepository

        await db.init_db()
        repo = UserRepository()
        user = await repo.get_user_by_identifier(identifier)

        if user is None:
            console.print(f"[error]User '{identifier}' not found.[/]")
            raise typer.Exit(1)

        console.print(f"  [info]User:[/] {user.username} ({user.email})")
        console.print(f"  [info]Role:[/] {user.role.value}")
        console.print()

        new_password = Prompt.ask("  New password", password=True)
        if len(new_password) < 8:
            console.print("[error]Password must be at least 8 characters.[/]")
            raise typer.Exit(1)

        confirm_password = Prompt.ask("  Confirm password", password=True)
        if new_password != confirm_password:
            console.print("[error]Passwords do not match.[/]")
            raise typer.Exit(1)

        # SHA-256 hash first (matches frontend), then bcrypt on top
        sha256_digest = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
        auth_service = get_auth_service()
        new_hash = auth_service.hash_password(sha256_digest)

        success = await repo.update_password(user.id, new_hash)
        if success:
            console.print("[success]Password reset successfully.[/]")
        else:
            console.print("[error]Failed to update password.[/]")
            raise typer.Exit(1)

    asyncio.run(_reset())


@app.command("repair")
def repair() -> None:
    """Repair a corrupted CachiBot installation.

    Detects tilde-prefixed corrupted packages left by interrupted pip installs,
    removes them, force-reinstalls the current version, and verifies the result.
    """
    from cachibot.services.update_service import repair_installation

    console.print("[info]Running installation repair...[/]\n")
    ok, detail = asyncio.run(repair_installation())

    for line in detail.splitlines():
        if "corrupted" in line.lower() or "failed" in line.lower():
            console.print(f"  [warning]{line}[/]")
        else:
            console.print(f"  {line}")

    console.print()
    if ok:
        console.print("[success]Repair completed successfully.[/]")
    else:
        console.print(
            "[error]Repair failed. Try manually running:[/]\n"
            f"  {sys.executable} -m pip install --force-reinstall --no-cache-dir cachibot"
        )
        raise typer.Exit(1)


@app.command("diagnose")
def diagnose() -> None:
    """Run installation diagnostics and show environment info."""
    from cachibot.services.update_service import (
        _is_venv,
        _python_info,
        detect_corruption,
        verify_installation,
    )

    console.print("[info]CachiBot Installation Diagnostics[/]\n")

    # Environment info
    py = _python_info()
    table = Table(title="Environment")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("CachiBot Version", __version__)
    table.add_row("Python Version", py["version"].split()[0])
    table.add_row("Python Executable", py["executable"])
    table.add_row("Platform", py["platform"])
    table.add_row("Virtual Environment", str(_is_venv()))
    table.add_row("Prefix", py["prefix"])
    if py["prefix"] != py["base_prefix"]:
        table.add_row("Base Prefix", py["base_prefix"])
    console.print(table)
    console.print()

    # Corruption check
    report = detect_corruption()
    if report.is_corrupted:
        console.print(f"[warning]Corruption: {report.details}[/]")
    else:
        console.print("[success]No corruption detected.[/]")

    # Verification
    ok, detail = verify_installation()
    if ok:
        console.print(f"[success]{detail}[/]")
    else:
        console.print(f"[error]Verification failed: {detail}[/]")

    # venv warning
    if not _is_venv():
        console.print(
            "\n[warning]Not running in a virtual environment. "
            "Consider using a venv for isolation.[/]"
        )

    console.print()


@telemetry_app.command("status")
def telemetry_status() -> None:
    """Show current telemetry state."""
    import os

    config = Config.load()
    t = config.telemetry

    env_disabled = os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() in ("1", "true", "yes")

    table = Table(title="Telemetry Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    effective_enabled = t.enabled and not env_disabled
    table.add_row("Enabled", str(effective_enabled))
    if env_disabled:
        table.add_row("", "[warning]Overridden by CACHIBOT_TELEMETRY_DISABLED[/]")
    table.add_row("Install ID", t.install_id or "[dim]not generated[/]")
    table.add_row("Terms Accepted", str(t.terms_accepted))
    table.add_row("Terms Version", t.terms_version or "[dim]none[/]")
    table.add_row("Terms Accepted At", t.terms_accepted_at or "[dim]never[/]")
    table.add_row("Last Sent", t.last_sent or "[dim]never[/]")
    table.add_row("Matomo URL", t.matomo_url)
    table.add_row("Site ID", t.matomo_site_id)

    console.print(table)


@telemetry_app.command("enable")
def telemetry_enable() -> None:
    """Enable anonymous telemetry."""
    import uuid

    config = Config.load()
    config.telemetry.enabled = True
    if not config.telemetry.install_id:
        config.telemetry.install_id = uuid.uuid4().hex
    config.save_telemetry_config()
    console.print("[success]Telemetry enabled.[/]")


@telemetry_app.command("disable")
def telemetry_disable() -> None:
    """Disable anonymous telemetry."""
    config = Config.load()
    config.telemetry.enabled = False
    config.save_telemetry_config()
    console.print("[success]Telemetry disabled.[/]")


@telemetry_app.command("show")
def telemetry_show() -> None:
    """Show what telemetry data would be sent (debug)."""
    import json

    from cachibot.telemetry.collector import collect_telemetry

    payload = collect_telemetry()
    syntax = Syntax(json.dumps(payload, indent=2), "json", theme="monokai")
    console.print(
        Panel(
            syntax,
            title="Telemetry Payload Preview",
            border_style="cyan",
        )
    )


def print_help() -> None:
    """Print help information."""
    help_text = """
## Commands

| Command | Description |
|---------|-------------|
| `exit`, `quit`, `q` | Exit Cachibot |
| `help` | Show this help |
| `clear` | Clear conversation history |
| `config` | Show current configuration |

## Tips

- Be specific about what you want
- Reference files by their path
- Code runs in a Python sandbox (safe imports only)
- Use `--approve` flag for sensitive operations
- Use `--model` to switch providers

## Models

Set your default model in Settings or `~/.cachibot.toml`. Examples:
- `openai/gpt-4o`
- `claude/claude-sonnet-4-20250514`
- `ollama/llama3.1:8b` (local)
"""
    console.print(Markdown(help_text))


def print_config(config: Config) -> None:
    """Print current configuration."""
    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Model", config.agent.model)
    table.add_row("Workspace", str(config.workspace_path))
    table.add_row("Max Iterations", str(config.agent.max_iterations))
    table.add_row("Temperature", str(config.agent.temperature))
    table.add_row("Approval Required", str(config.agent.approve_actions))
    table.add_row("Sandbox Timeout", f"{config.sandbox.timeout_seconds}s")
    table.add_row("Show Thinking", str(config.display.show_thinking))
    table.add_row("Show Cost", str(config.display.show_cost))

    console.print(table)


if __name__ == "__main__":
    app()

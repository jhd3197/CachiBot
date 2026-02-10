"""
Cachibot CLI

Beautiful command-line interface using Typer and Rich.
"""

import asyncio
from pathlib import Path
from typing import Optional

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

# Custom theme for Cachibot
CACHIBOT_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green",
    "thinking": "dim italic",
    "tool": "magenta",
    "user": "bold blue",
    "assistant": "bold green",
    "cost": "dim cyan",
})

console = Console(theme=CACHIBOT_THEME)
app = typer.Typer(
    name="cachibot",
    help="🛡️ Cachibot - The Armored AI Agent",
    no_args_is_help=False,
)


def print_banner() -> None:
    """Print the Cachibot banner."""
    banner = """
[bold cyan]    ╭─────────╮
   ╱ ◉     ◉  ╲
  │  ─────────  │
  │   ╲_____╱   │    [bold white]Cachibot[/] v{}
   ╲ ═══════   ╱     [dim]The Armored Agent[/]
    ╲ ═════   ╱
     ╰═══════╯[/]
""".format(__version__)
    console.print(banner)


def print_welcome(config: Config) -> None:
    """Print welcome message with workspace info."""
    console.print(
        f"   [dim]Workspace:[/] {config.workspace_path}\n"
        f"   [dim]Model:[/] {config.agent.model}\n"
        f"   [dim]Type [bold]exit[/] to leave, [bold]help[/] for commands[/]\n"
    )


def format_approval_dialog(tool_name: str, action: str, details: dict) -> bool:
    """Show approval dialog for risky operations."""
    console.print()
    console.print(Panel(
        f"[warning]⚠️  Approval Required[/]\n\n"
        f"Tool: [bold]{tool_name}[/]\n"
        f"Action: {action}",
        title="Security Check",
        border_style="yellow",
    ))

    # Show code if present
    if "code" in details:
        console.print(Panel(
            Syntax(details["code"], "python", theme="monokai", line_numbers=True),
            title="Code to Execute",
            border_style="dim",
        ))

    # Show risk reasons
    if "reasons" in details:
        console.print("[dim]Risk factors:[/]")
        for reason in details["reasons"]:
            console.print(f"  • {reason}")

    console.print()
    return Confirm.ask("  [bold]Approve this action?[/]", default=False)


def print_usage(run_usage: dict, steps: int = 0) -> None:
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
        console.print(f"\n  [cost]📊 {' | '.join(parts)}[/]")


def create_agent_with_callbacks(config: Config) -> CachibotAgent:
    """Create an agent with CLI callbacks configured."""

    def on_thinking(text: str) -> None:
        if config.display.show_thinking:
            # Truncate long thinking
            if len(text) > 200:
                text = text[:197] + "..."
            console.print(f"  [thinking]💭 {text}[/]")

    def on_tool_start(name: str, args: dict) -> None:
        # Show tool being called
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(args.items())[:3])
        if len(args_str) > 60:
            args_str = args_str[:57] + "..."
        console.print(f"  [tool]⚡ {name}[/]([dim]{args_str}[/])")

    def on_tool_end(name: str, result: str) -> None:
        # Show brief result
        if result:
            lines = str(result).split("\n")
            preview = lines[0][:80]
            if len(lines) > 1 or len(lines[0]) > 80:
                preview += "..."
            console.print(f"  [success]✓[/] [dim]{preview}[/]")

    def on_approval_needed(tool_name: str, action: str, details: dict) -> bool:
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
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace", "-w",
        help="Working directory for the agent",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Model to use (e.g., moonshot/kimi-k2.5, claude/claude-sonnet-4-20250514)",
    ),
    approve: bool = typer.Option(
        False,
        "--approve", "-a",
        help="Require approval for each action",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show thinking process",
    ),
    version: bool = typer.Option(
        False,
        "--version", "-V",
        help="Show version and exit",
    ),
    task: Optional[str] = typer.Argument(
        None,
        help="Task to run (if not provided, enters interactive mode)",
    ),
) -> None:
    """
    🛡️ Cachibot - The Armored AI Agent

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
            console.print(f"\n[assistant]Cachibot:[/]")
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
                console.print("\n[dim]Goodbye! 🛡️[/]\n")
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
            console.print(f"\n[assistant]Cachibot:[/]")
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
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
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
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Server host"),
    port: int = typer.Option(6392, "--port", "-p", help="Server port"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload (dev mode)"),
) -> None:
    """Start the Cachibot API server."""
    from cachibot.api.server import run_server as start_api_server

    console.print(f"[info]🚀 Starting Cachibot server on http://{host}:{port}[/]")
    start_api_server(host=host, port=port, workspace=workspace, reload=reload)


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

- `moonshot/kimi-k2.5` (default)
- `claude/claude-sonnet-4-20250514`
- `openai/gpt-4o`
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

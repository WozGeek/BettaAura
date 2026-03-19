"""
aura.cli — The command-line interface.

Usage:
    aura init                          Initialize aura
    aura create <name> [--template T]  Create a context pack
    aura list                          List all packs
    aura show <name>                   Show a pack's contents
    aura edit <name>                   Open pack in editor
    aura export <name> --format F      Export pack to a platform format
    aura import --from chatgpt <file>  Import from a platform export
    aura delete <name>                 Delete a pack
"""

from __future__ import annotations

import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from aura import __version__

app = typer.Typer(
    name="aura",
    help="✦ aura — Your portable AI context.\n\nCarry your identity across every AI tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


# ---------------------------------------------------------------------------
# Enums for CLI options
# ---------------------------------------------------------------------------
class ExportFormat(str, Enum):
    SYSTEM_PROMPT = "system-prompt"
    CURSORRULES = "cursorrules"
    CLAUDE_MEMORY = "claude-memory"
    CHATGPT_INSTRUCTIONS = "chatgpt-instructions"


class ImportSource(str, Enum):
    CHATGPT = "chatgpt"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
@app.command()
def init():
    """Initialize aura in your home directory."""
    from aura.pack import init_aura, is_initialized

    if is_initialized():
        rprint("[yellow]⚡ aura is already initialized.[/yellow]")
        rprint(f"   Home: [dim]{Path.home() / '.aura'}[/dim]")
        return

    home = init_aura()
    rprint(Panel.fit(
        f"[bold green]✦ aura initialized[/bold green]\n\n"
        f"  Home: [cyan]{home}[/cyan]\n"
        f"  Packs: [cyan]{home / 'packs'}[/cyan]\n\n"
        f"  Next steps:\n"
        f"  [dim]aura create developer --template developer[/dim]\n"
        f"  [dim]aura create writer --template writer[/dim]\n"
        f"  [dim]aura import --source chatgpt export.zip[/dim]",
        title="aura v" + __version__,
        border_style="green",
    ))


@app.command()
def create(
    name: str = typer.Argument(..., help="Name for the context pack (lowercase, e.g. 'developer')"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Create from a built-in template"),
    scope: Optional[str] = typer.Option(None, "--scope", "-s", help="Scope for the pack (e.g. 'development', 'writing')"),
):
    """Create a new context pack."""
    from aura.pack import (
        TEMPLATES,
        create_from_template,
        init_aura,
        pack_exists,
        save_pack,
    )
    from aura.schema import ContextPack, PackMeta

    init_aura()  # Ensure initialized

    if pack_exists(name):
        rprint(f"[red]✗ Pack '{name}' already exists.[/red] Use [bold]aura edit {name}[/bold] to modify it.")
        raise typer.Exit(1)

    if template:
        if template not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            rprint(f"[red]✗ Unknown template '{template}'.[/red] Available: {available}")
            raise typer.Exit(1)
        pack = create_from_template(template, pack_name=name)
    else:
        pack = ContextPack(
            name=name,
            scope=scope or "general",
            facts=[],
            rules=[],
            meta=PackMeta(description=f"Context pack: {name}"),
        )

    path = save_pack(pack)
    rprint(f"[green]✦ Created pack:[/green] [bold]{name}[/bold]")
    rprint(f"  File: [dim]{path}[/dim]")
    rprint(f"  Scope: [cyan]{pack.scope}[/cyan]")
    rprint(f"  Facts: {len(pack.facts)} | Rules: {len(pack.rules)}")

    if not template:
        rprint(f"\n  [dim]Edit it: aura edit {name}[/dim]")


@app.command("list")
def list_packs():
    """List all context packs."""
    from aura.pack import is_initialized
    from aura.pack import list_packs as _list_packs

    if not is_initialized():
        rprint("[yellow]aura is not initialized.[/yellow] Run [bold]aura init[/bold] first.")
        raise typer.Exit(1)

    packs = _list_packs()
    if not packs:
        rprint("[dim]No context packs found.[/dim]")
        rprint("Create one: [bold]aura create developer --template developer[/bold]")
        return

    table = Table(title="✦ Context Packs", border_style="dim")
    table.add_column("Name", style="bold cyan")
    table.add_column("Scope", style="green")
    table.add_column("Facts", justify="right")
    table.add_column("Rules", justify="right")
    table.add_column("Description", style="dim", max_width=40)

    for pack in packs:
        table.add_row(
            pack.name,
            pack.scope,
            str(len(pack.facts)),
            str(len(pack.rules)),
            pack.meta.description or "—",
        )

    console.print(table)


@app.command()
def show(
    name: str = typer.Argument(..., help="Pack name to display"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw YAML"),
):
    """Display a context pack's contents."""
    from aura.pack import _pack_path, load_pack

    try:
        pack = load_pack(name)
    except FileNotFoundError:
        rprint(f"[red]✗ Pack '{name}' not found.[/red]")
        raise typer.Exit(1)

    if raw:
        path = _pack_path(name)
        content = path.read_text()
        syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        return

    # Pretty display
    rprint(Panel.fit(
        f"[bold]{pack.name}[/bold] [dim]({pack.scope})[/dim]\n"
        f"{pack.meta.description or ''}",
        border_style="cyan",
    ))

    if pack.facts:
        rprint("\n[bold]Facts:[/bold]")
        for fact in pack.facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(fact.confidence.value, "dim")
            rprint(f"  [{conf_color}]●[/{conf_color}] [bold]{fact.key}[/bold]: {val}")

    if pack.rules:
        rprint("\n[bold]Rules:[/bold]")
        for rule in sorted(pack.rules, key=lambda r: -r.priority):
            priority_str = f"[dim]P{rule.priority}[/dim] " if rule.priority > 0 else "   "
            rprint(f"  {priority_str}{rule.instruction}")


@app.command()
def edit(
    name: str = typer.Argument(..., help="Pack name to edit"),
):
    """Open a context pack in your editor."""
    from aura.pack import _pack_path, pack_exists

    if not pack_exists(name):
        rprint(f"[red]✗ Pack '{name}' not found.[/red]")
        raise typer.Exit(1)

    path = _pack_path(name)
    editor = os.environ.get("EDITOR", "nano")

    try:
        subprocess.run([editor, str(path)], check=True)
        rprint(f"[green]✦ Pack '{name}' updated.[/green]")
    except FileNotFoundError:
        rprint(f"[red]Editor '{editor}' not found.[/red] Set $EDITOR or install nano/vim.")
        raise typer.Exit(1)


@app.command()
def export(
    names: list[str] = typer.Argument(..., help="Pack name(s) to export"),
    format: ExportFormat = typer.Option(
        ExportFormat.SYSTEM_PROMPT,
        "--format", "-f",
        help="Export format",
    ),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only output the content, no decoration"),
):
    """Export context pack(s) to a platform-specific format."""
    from aura.pack import load_pack

    packs = []
    for name in names:
        try:
            packs.append(load_pack(name))
        except FileNotFoundError:
            rprint(f"[red]✗ Pack '{name}' not found.[/red]")
            raise typer.Exit(1)

    # Generate output based on format
    if format == ExportFormat.SYSTEM_PROMPT:
        from aura.exporters.system_prompt import export_system_prompt
        content = export_system_prompt(packs)

    elif format == ExportFormat.CURSORRULES:
        from aura.exporters.cursorrules import export_cursorrules
        content = export_cursorrules(packs)

    elif format == ExportFormat.CLAUDE_MEMORY:
        from aura.exporters.claude_memory import export_claude_memory_text
        content = export_claude_memory_text(packs)

    elif format == ExportFormat.CHATGPT_INSTRUCTIONS:
        from aura.exporters.chatgpt_instructions import export_chatgpt_instructions_text
        content = export_chatgpt_instructions_text(packs)

    # Output
    if output:
        Path(output).write_text(content)
        if not quiet:
            rprint(f"[green]✦ Exported to:[/green] {output}")
    else:
        if not quiet:
            rprint(f"[dim]─── {format.value} ───[/dim]\n")
        console.print(content, highlight=False)


@app.command("import")
def import_context(
    file: str = typer.Argument(..., help="Path to the export file (.json or .zip)"),
    source: ImportSource = typer.Option(
        ..., "--source", "-s",
        help="Platform the export came from",
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for the imported pack"),
    scope: str = typer.Option("general", "--scope", help="Scope for the imported pack"),
):
    """Import context from a platform's data export."""
    from aura.pack import init_aura, pack_exists, save_pack

    init_aura()
    path = Path(file)

    if not path.exists():
        rprint(f"[red]✗ File not found: {file}[/red]")
        raise typer.Exit(1)

    pack_name = name or f"{source.value}-import"

    if pack_exists(pack_name):
        rprint(f"[yellow]⚡ Pack '{pack_name}' already exists. Overwriting.[/yellow]")

    if source == ImportSource.CHATGPT:
        from aura.importers.chatgpt import import_chatgpt_export
        pack = import_chatgpt_export(path, pack_name=pack_name, scope=scope)

    saved_path = save_pack(pack)

    rprint(f"[green]✦ Imported from {source.value}:[/green] [bold]{pack_name}[/bold]")
    rprint(f"  File: [dim]{saved_path}[/dim]")
    rprint(f"  Facts extracted: [cyan]{len(pack.facts)}[/cyan]")
    rprint(f"  {pack.meta.description}")
    rprint(f"\n  [dim]Review: aura show {pack_name}[/dim]")
    rprint(f"  [dim]Edit:   aura edit {pack_name}[/dim]")


@app.command()
def delete(
    name: str = typer.Argument(..., help="Pack name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a context pack."""
    from aura.pack import delete_pack, pack_exists

    if not pack_exists(name):
        rprint(f"[red]✗ Pack '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete pack '{name}'?")
        if not confirm:
            rprint("[dim]Cancelled.[/dim]")
            return

    delete_pack(name)
    rprint(f"[green]✦ Deleted pack:[/green] {name}")


@app.command()
def templates():
    """List available pack templates."""
    from aura.pack import TEMPLATES

    table = Table(title="✦ Available Templates", border_style="dim")
    table.add_column("Template", style="bold cyan")
    table.add_column("Scope", style="green")
    table.add_column("Facts", justify="right")
    table.add_column("Rules", justify="right")
    table.add_column("Description", style="dim", max_width=50)

    for name, tmpl in TEMPLATES.items():
        table.add_row(
            name,
            tmpl["scope"],
            str(len(tmpl["facts"])),
            str(len(tmpl["rules"])),
            tmpl["description"],
        )

    console.print(table)
    rprint("\n[dim]Use: aura create mypack --template <name>[/dim]")


@app.command()
def diff(
    source: str = typer.Argument(..., help="Source pack name (your canonical context)"),
    target: str = typer.Argument(..., help="Target pack name (e.g. imported from a platform)"),
):
    """Compare two context packs and show differences."""
    from aura.diff import diff_packs, format_diff
    from aura.pack import load_pack

    try:
        source_pack = load_pack(source)
    except FileNotFoundError:
        rprint(f"[red]✗ Pack '{source}' not found.[/red]")
        raise typer.Exit(1)

    try:
        target_pack = load_pack(target)
    except FileNotFoundError:
        rprint(f"[red]✗ Pack '{target}' not found.[/red]")
        raise typer.Exit(1)

    result = diff_packs(source_pack, target_pack)
    output = format_diff(result, source_name=source, target_name=target)

    if result.has_differences:
        rprint("[yellow]⚡ Differences found[/yellow]\n")
    else:
        rprint("[green]✦ Packs are in sync[/green]\n")

    console.print(output, highlight=False)


@app.command()
def serve(
    host: str = typer.Option("localhost", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(3847, "--port", "-p", help="Port to listen on"),
):
    """Start the aura MCP server. Serves your context packs to any MCP client."""
    from aura.pack import init_aura
    from aura.pack import list_packs as _list_packs

    init_aura()
    packs = _list_packs()

    rprint(Panel.fit(
        f"[bold green]✦ aura MCP server[/bold green]\n\n"
        f"  Endpoint:  [cyan]http://{host}:{port}/mcp[/cyan]\n"
        f"  SSE:       [cyan]http://{host}:{port}/sse[/cyan]\n"
        f"  Health:    [cyan]http://{host}:{port}/health[/cyan]\n\n"
        f"  Serving [bold]{len(packs)}[/bold] context packs\n\n"
        f"  [dim]Add to Claude Desktop config:[/dim]\n"
        f'  [dim]{{"mcpServers": {{"aura": {{"url": "http://{host}:{port}/mcp"}}}}}}[/dim]\n\n'
        f"  [dim]Add to Cursor settings:[/dim]\n"
        f'  [dim]{{"mcpServers": {{"aura": {{"url": "http://{host}:{port}/sse"}}}}}}[/dim]',
        title="aura v" + __version__,
        border_style="green",
    ))

    from aura.mcp_server import run_server
    run_server(host=host, port=port)


@app.command()
def extract(
    file: str = typer.Argument(..., help="Path to conversation export (.json or .zip)"),
    source: ImportSource = typer.Option(
        ImportSource.CHATGPT, "--source", "-s",
        help="Platform the export came from",
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for the extracted pack"),
    scope: str = typer.Option("general", "--scope", help="Scope for the extracted pack"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    base_url: Optional[str] = typer.Option(None, "--llm-url", help="LLM API base URL"),
):
    """Deep-extract context from conversations using an LLM (local or cloud)."""
    from aura.importers.chatgpt import _extract_user_messages, _load_from_zip
    from aura.pack import init_aura, save_pack

    init_aura()
    file_path = Path(file)

    if not file_path.exists():
        rprint(f"[red]✗ File not found: {file}[/red]")
        raise typer.Exit(1)

    # Load and extract user messages
    rprint(f"[dim]Loading conversations from {file_path.name}...[/dim]")
    import json
    if file_path.suffix == ".zip":
        conversations = _load_from_zip(file_path)
    else:
        with open(file_path) as f:
            conversations = json.load(f)

    messages = _extract_user_messages(conversations)
    rprint(f"  Found [cyan]{len(conversations)}[/cyan] conversations, [cyan]{len(messages)}[/cyan] user messages")

    if not messages:
        rprint("[yellow]No user messages found to extract from.[/yellow]")
        raise typer.Exit(1)

    # Run LLM extraction

    pack_name = name or f"{source.value}-extracted"

    rprint("\n[bold]Extracting context with LLM...[/bold]")
    if model:
        rprint(f"  Model: [cyan]{model}[/cyan]")
    if base_url:
        rprint(f"  API: [cyan]{base_url}[/cyan]")

    from aura.extractor import extract_context

    def on_progress(chunk_idx, total, facts_count):
        if chunk_idx < total:
            rprint(f"  [dim]Processing chunk {chunk_idx + 1}/{total}... ({facts_count} facts so far)[/dim]")
        else:
            rprint(f"  [green]✓ Done — {facts_count} facts extracted[/green]")

    try:
        pack = extract_context(
            messages=messages,
            pack_name=pack_name,
            scope=scope,
            base_url=base_url,
            model=model,
            on_progress=on_progress,
        )
    except ConnectionError as e:
        rprint(f"\n[red]✗ Cannot connect to LLM:[/red] {e}")
        rprint("\n[dim]Make sure Ollama is running (ollama serve) or set:[/dim]")
        rprint("  [dim]AURA_LLM_URL=https://api.openai.com/v1[/dim]")
        rprint("  [dim]AURA_LLM_KEY=sk-...[/dim]")
        rprint("  [dim]AURA_LLM_MODEL=gpt-4.1-mini[/dim]")
        rprint(f"\n[dim]Or use basic import instead: aura import -s chatgpt {file}[/dim]")
        raise typer.Exit(1)

    saved_path = save_pack(pack)

    rprint(f"\n[green]✦ Extracted:[/green] [bold]{pack_name}[/bold]")
    rprint(f"  File: [dim]{saved_path}[/dim]")
    rprint(f"  Facts: [cyan]{len(pack.facts)}[/cyan] | Rules: [cyan]{len(pack.rules)}[/cyan]")
    rprint(f"  {pack.meta.description}")
    rprint(f"\n  [dim]Review: aura show {pack_name}[/dim]")
    rprint(f"  [dim]Diff:   aura diff developer {pack_name}[/dim]")


@app.command()
def setup(
    host: str = typer.Option("localhost", "--host", "-h", help="MCP server host"),
    port: int = typer.Option(3847, "--port", "-p", help="MCP server port"),
):
    """Auto-configure Claude Desktop and Cursor to connect to aura's MCP server."""
    from aura.setup import detect_installed_tools, setup_claude_desktop, setup_cursor

    rprint(Panel.fit(
        "[bold]✦ aura setup[/bold]\n\n"
        "  Detecting installed AI tools and configuring MCP...",
        border_style="cyan",
    ))

    tools = detect_installed_tools()

    if not tools:
        rprint("[yellow]No supported AI tools detected.[/yellow]")
        return

    configured = 0

    for tool in tools:
        name = tool["name"]
        if not tool["installed"]:
            rprint(f"  [dim]○ {name} — not installed[/dim]")
            continue

        # Configure based on tool
        if name == "Claude Desktop":
            result = setup_claude_desktop(host, port)
        elif name == "Cursor":
            result = setup_cursor(host, port)
        else:
            continue

        if result["action"] == "configured":
            rprint(f"  [green]✦ {name}[/green] — configured")
            rprint(f"    [dim]{result['path']}[/dim]")
            configured += 1
        elif result["action"] == "already_configured":
            rprint(f"  [cyan]● {name}[/cyan] — already configured")
            configured += 1
        else:
            rprint(f"  [red]✗ {name}[/red] — {result['message']}")

    if configured > 0:
        rprint(f"\n[green]✦ {configured} tool(s) configured.[/green]")
        rprint("\n  [bold]Next steps:[/bold]")
        rprint("  1. Start the MCP server:  [cyan]aura serve --mcp[/cyan]")
        rprint("  2. Restart Claude/Cursor to pick up the new config")
        rprint("  3. Your context packs are now available automatically")
    else:
        rprint("\n[yellow]No tools configured.[/yellow]")
        rprint("  Install Claude Desktop or Cursor, then run [bold]aura setup[/bold] again.")


@app.command()
def scan(
    dirs: Optional[list[str]] = typer.Argument(None, help="Directories to scan (default: ~/Documents, ~/Projects, etc.)"),
    name: str = typer.Option("developer", "--name", "-n", help="Name for the generated pack"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save the pack to disk"),
):
    """Scan your machine and auto-generate a context pack from your actual environment."""
    from aura.pack import init_aura, pack_exists
    from aura.pack import save_pack as _save_pack
    from aura.scanner import Scanner

    init_aura()

    rprint(Panel.fit(
        "[bold]✦ aura scan[/bold]\n\n"
        "  Scanning your machine for languages, frameworks,\n"
        "  tools, projects, and preferences...",
        border_style="cyan",
    ))

    scanner = Scanner(scan_dirs=dirs)
    pack = scanner.scan()
    pack.name = name

    # Display results
    rprint("\n[green]✦ Scan complete[/green]\n")

    if pack.facts:
        rprint("[bold]Detected:[/bold]")
        for fact in pack.facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            icon = {"high": "[green]●[/green]", "medium": "[yellow]●[/yellow]", "low": "[red]●[/red]"}
            rprint(f"  {icon.get(fact.confidence.value, '○')} [bold]{fact.key}[/bold]: {val}")

    if not pack.facts:
        rprint("[yellow]  No development environment detected.[/yellow]")
        rprint("  [dim]Try specifying directories: aura scan ~/my-projects[/dim]")
        return

    if save:
        if pack_exists(name):
            overwrite = typer.confirm(f"\n  Pack '{name}' already exists. Overwrite?")
            if not overwrite:
                rprint("[dim]  Skipped. Use --name to save with a different name.[/dim]")
                return

        path = _save_pack(pack)
        rprint(f"\n[green]✦ Saved:[/green] [bold]{name}[/bold]")
        rprint(f"  File: [dim]{path}[/dim]")
        rprint(f"  Facts: [cyan]{len(pack.facts)}[/cyan]")
        rprint(f"\n  [dim]Review: aura show {name}[/dim]")
        rprint(f"  [dim]Edit:   aura edit {name}[/dim]")
    else:
        rprint("\n  [dim]Dry run — use --save to write to disk[/dim]")


@app.command()
def onboard():
    """Interactive onboarding — 5 questions to generate your context packs."""
    from aura.onboard import Onboarder
    from aura.pack import init_aura, pack_exists
    from aura.pack import save_pack as _save_pack

    init_aura()

    rprint(Panel.fit(
        "[bold]✦ aura onboard[/bold]\n\n"
        "  5 quick questions to build your AI identity.\n"
        "  Type 'skip' to skip any question.",
        border_style="cyan",
    ))

    onboarder = Onboarder()
    packs = onboarder.run()

    if not packs:
        rprint("\n[yellow]  No context captured. Run again when ready.[/yellow]")
        return

    saved = 0
    for pack_name, pack in packs.items():
        if pack_exists(pack_name):
            overwrite = typer.confirm(f"\n  Pack '{pack_name}' already exists. Overwrite?")
            if not overwrite:
                continue

        _save_pack(pack)
        rprint(f"\n[green]✦ Created:[/green] [bold]{pack_name}[/bold]")
        rprint(f"  Facts: [cyan]{len(pack.facts)}[/cyan] | Rules: [cyan]{len(pack.rules)}[/cyan]")
        saved += 1

    if saved > 0:
        rprint(f"\n[green]✦ {saved} pack(s) created from onboarding.[/green]")
        rprint("\n  [bold]Next steps:[/bold]")
        rprint("  [dim]aura scan[/dim]            — auto-detect your dev stack")
        rprint("  [dim]aura setup[/dim]           — connect Claude Desktop & Cursor")
        rprint("  [dim]aura serve[/dim]           — start MCP server")


@app.command()
def quickstart():
    """Full onboarding in one command: scan + onboard + setup + serve."""
    rprint(Panel.fit(
        "[bold]✦ aura quickstart[/bold]\n\n"
        "  The fastest way to get your AI context running.\n"
        "  Scan → Onboard → Setup → Serve",
        border_style="green",
    ))

    # Step 1: Scan
    rprint("\n[bold cyan]Step 1/4 — Scanning your machine...[/bold cyan]")
    from aura.pack import init_aura
    from aura.pack import save_pack as _save_pack
    from aura.scanner import Scanner

    init_aura()
    scanner = Scanner()
    dev_pack = scanner.scan()
    dev_pack.name = "developer"
    _save_pack(dev_pack)
    rprint(f"  [green]✦[/green] Detected {len(dev_pack.facts)} facts about your dev environment")

    # Step 2: Onboard
    rprint("\n[bold cyan]Step 2/4 — Quick questions about you...[/bold cyan]")
    from aura.onboard import Onboarder
    onboarder = Onboarder()
    packs = onboarder.run()
    for pack_name, pack in packs.items():
        _save_pack(pack)
        rprint(f"  [green]✦[/green] Created {pack_name} ({len(pack.facts)} facts, {len(pack.rules)} rules)")

    # Step 3: Setup
    rprint("\n[bold cyan]Step 3/4 — Configuring AI tools...[/bold cyan]")
    from aura.setup import detect_installed_tools, setup_claude_desktop, setup_cursor
    for tool in detect_installed_tools():
        if tool["installed"]:
            if tool["name"] == "Claude Desktop":
                setup_claude_desktop()
                rprint("  [green]✦[/green] Claude Desktop configured")
            elif tool["name"] == "Cursor":
                setup_cursor()
                rprint("  [green]✦[/green] Cursor configured")

    # Step 4: Summary
    from aura.pack import list_packs as _list_packs
    all_packs = _list_packs()
    total_facts = sum(len(p.facts) for p in all_packs)
    total_rules = sum(len(p.rules) for p in all_packs)

    rprint(Panel.fit(
        f"[bold green]✦ aura is ready[/bold green]\n\n"
        f"  {len(all_packs)} context packs | {total_facts} facts | {total_rules} rules\n\n"
        f"  Start the MCP server:\n"
        f"  [cyan]aura serve[/cyan]\n\n"
        f"  Then restart Claude Desktop / Cursor.\n"
        f"  Your AI will know you instantly.",
        border_style="green",
    ))


@app.command()
def doctor():
    """Check the health of your context packs — detect bloat, stale facts, duplicates."""
    from aura.doctor import diagnose, format_report
    from aura.pack import is_initialized
    from aura.pack import list_packs as _list_packs

    if not is_initialized():
        rprint("[yellow]aura is not initialized.[/yellow] Run [bold]aura init[/bold] first.")
        raise typer.Exit(1)

    packs = _list_packs()

    rprint(Panel.fit(
        "[bold]✦ aura doctor[/bold]\n\n"
        f"  Checking {len(packs)} pack(s)...",
        border_style="cyan",
    ))

    report = diagnose(packs)
    rprint(format_report(report))


@app.command()
def add(
    pack_name: str = typer.Argument(..., help="Pack to add the fact to"),
    key: str = typer.Argument(..., help="Fact key (e.g. 'languages.learning')"),
    value: str = typer.Argument(..., help="Fact value (e.g. 'Rust')"),
    fact_type: str = typer.Option("context", "--type", "-t", help="Fact type: preference, identity, skill, style, constraint, context"),
):
    """Add a fact to a pack in one command. No YAML editing needed."""
    from aura.pack import load_pack, pack_exists
    from aura.pack import save_pack as _save_pack
    from aura.schema import Confidence, Fact

    if not pack_exists(pack_name):
        rprint(f"[red]✗ Pack '{pack_name}' not found.[/red]")
        raise typer.Exit(1)

    pack = load_pack(pack_name)

    # Check if fact with this key already exists
    existing = [f for f in pack.facts if f.key == key]
    if existing:
        rprint(f"[yellow]⚡ Fact '{key}' already exists:[/yellow] {existing[0].value}")
        overwrite = typer.confirm("  Overwrite?")
        if not overwrite:
            return
        pack.facts = [f for f in pack.facts if f.key != key]

    # Parse value — if it contains commas, treat as list
    parsed_value: str | list[str] = value
    if "," in value:
        parsed_value = [v.strip() for v in value.split(",") if v.strip()]

    new_fact = Fact(
        key=key,
        value=parsed_value,
        type=fact_type,
        confidence=Confidence.HIGH,
        source="manual",
    )
    pack.facts.append(new_fact)
    _save_pack(pack)

    val_display = parsed_value if isinstance(parsed_value, str) else ", ".join(parsed_value)
    rprint(f"[green]✦ Added to {pack_name}:[/green] {key} = {val_display}")


@app.command()
def version():
    """Show aura version."""
    rprint(f"[bold]aura[/bold] v{__version__}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app()


if __name__ == "__main__":
    main()

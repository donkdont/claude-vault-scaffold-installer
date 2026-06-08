from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..core import checks as checks_mod
from ..core import manifest as manifest_mod
from ..core.path_resolver import resolve_vault_root

console = Console()

_CHECKS: list[tuple[str, str]] = [
    ("python_conflict",     "System-Python ≤3.12"),
    ("venv_exists",         "venv vorhanden"),
    ("venv_python_version", "venv Python-Version"),
    ("deps_importable",     "Deps importierbar"),
    ("mcp_command",         "MCP-Command-Pfad"),
    ("no_placeholder",      "Keine Platzhalter"),
    ("hook_scripts",        "Hook-Scripts"),
]


def run(vault_root: Path, manifest: manifest_mod.Manifest | None = None) -> bool:
    """Run all health checks. Returns True if all non-warn checks passed."""
    if manifest is None:
        manifest = manifest_mod.load()

    results = [
        checks_mod.check_python_conflict(),
        checks_mod.check_venv_exists(vault_root, manifest.venv),
        checks_mod.check_venv_python_version(vault_root, manifest.venv),
        checks_mod.check_deps_importable(vault_root, manifest.venv, manifest.checks),
        checks_mod.check_mcp_command(vault_root, manifest.checks),
        checks_mod.check_no_placeholder(vault_root, manifest.checks),
        checks_mod.check_hook_scripts(vault_root, manifest.checks),
    ]

    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("Check", min_width=22)
    table.add_column("Status", width=4, justify="center")
    table.add_column("Detail")

    all_ok = True
    for (_, label), result in zip(_CHECKS, results):
        if result.warn:
            status = "[yellow]⚠[/yellow]"
            detail_style = "yellow"
        elif result.ok:
            status = "[green]✓[/green]"
            detail_style = "dim"
        else:
            status = "[red]✗[/red]"
            detail_style = "red"
            all_ok = False
        table.add_row(label, status, f"[{detail_style}]{result.message}[/{detail_style}]")

    console.print(table)
    return all_ok


def run_from_cli(path: str) -> None:
    """Entry point called from CLI — resolves path then runs doctor."""
    try:
        vault_root = resolve_vault_root(path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[dim]Vault: {vault_root}[/dim]\n")
    all_ok = run(vault_root)
    if not all_ok:
        console.print("\n[red]Einige Checks fehlgeschlagen.[/red]")
        raise typer.Exit(1)
    console.print("\n[green]Alle Checks bestanden.[/green]")

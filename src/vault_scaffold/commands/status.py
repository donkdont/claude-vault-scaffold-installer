"""vault-scaffold status — show installed vs. available version."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

import typer
from rich.console import Console

from ..core.path_resolver import resolve_vault_root
from ..core.version_tracker import read_installed_version

console = Console()


def run(path: str) -> None:
    try:
        vault_root = resolve_vault_root(path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[dim]Vault: {vault_root}[/dim]\n")

    installed = read_installed_version(vault_root)
    try:
        available = pkg_version("vault-scaffold")
    except PackageNotFoundError:
        available = "unknown"

    if installed is None:
        console.print("[yellow]Nicht installiert[/yellow] — vault-scaffold init wurde noch nicht ausgeführt.")
        console.print(f"  Verfügbar:   {available}")
        raise typer.Exit(1)

    console.print(f"  Installiert: [bold]{installed}[/bold]")
    console.print(f"  Verfügbar:   [bold]{available}[/bold]")

    if installed == available:
        console.print("\n[green]✓ Aktuell.[/green]")
    else:
        console.print(f"\n[yellow]→ Update verfügbar — führe aus: vault-scaffold update[/yellow]")
        raise typer.Exit(1)

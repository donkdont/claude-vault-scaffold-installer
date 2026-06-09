"""vault-scaffold update — bring an existing vault to the current scaffold version."""
from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer
from rich.console import Console

from ..core import config_patcher, environment, template_installer, venv_manager
from ..core import manifest as manifest_mod
from ..core.path_resolver import resolve_vault_root
from ..core.version_tracker import read_installed_version, write_installed_version
from . import doctor as doctor_mod

console = Console()


def run(path: str, force: bool = False) -> None:
    try:
        vault_root = resolve_vault_root(path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[dim]Vault: {vault_root}[/dim]\n")

    try:
        available = pkg_version("vault-scaffold")
    except PackageNotFoundError:
        available = "unknown"

    installed = read_installed_version(vault_root)

    if installed is None:
        console.print("[yellow]Kein Install-State gefunden.[/yellow]")
        console.print("Führe zuerst aus: vault-scaffold init")
        raise typer.Exit(1)

    if installed == available and not force:
        console.print(f"[green]✓ Bereits aktuell ({available})[/green] — nichts zu tun.")
        return

    if installed != available:
        console.print(f"Update: [bold]{installed}[/bold] → [bold]{available}[/bold]\n")
    else:
        console.print(f"[dim]Force-Reinstall: {available}[/dim]\n")

    uv = _check_uv()
    manifest = manifest_mod.load()
    _ensure_venv(vault_root, manifest, uv)
    _patch_files(vault_root, manifest)
    _install_templates(vault_root, manifest, force=force)
    write_installed_version(vault_root, available)
    console.print(f"[green]✓[/green] Version-Datei aktualisiert: {installed} → {available}")

    console.print("\n[dim]Führe doctor aus…[/dim]")
    all_ok = doctor_mod.run(vault_root, manifest)
    if not all_ok:
        console.print("\n[yellow]Update abgeschlossen, aber einige Checks sind noch offen.[/yellow]")
        raise typer.Exit(1)
    console.print(f"\n[bold green]vault-scaffold update complete ({installed} → {available}).[/bold green]")


def _install_templates(vault_root: Path, manifest: manifest_mod.Manifest, *, force: bool = False) -> None:
    with console.status("Neue Scaffold-Dateien prüfen…"):
        results = template_installer.install_templates(vault_root, manifest, force=force)

    installed = [p for p, a in results if a == template_installer.INSTALLED]
    overwritten = [p for p, a in results if a == template_installer.OVERWRITTEN]

    if not installed and not overwritten:
        console.print("[green]✓[/green] Scaffold-Dateien vollständig — nichts zu tun")
    else:
        for p in installed:
            console.print(f"[green]✓[/green] Neu installiert: {p.relative_to(vault_root)}")
        for p in overwritten:
            console.print(f"[yellow]↺[/yellow] Überschrieben: {p.relative_to(vault_root)}")


def _check_uv() -> Path:
    with console.status("uv prüfen…"):
        try:
            uv = environment.check_uv()
        except RuntimeError as exc:
            console.print(f"[red]✗[/red] {exc}")
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] uv: {uv}")
    return uv


def _ensure_venv(vault_root: Path, manifest: manifest_mod.Manifest, uv: Path) -> None:
    if venv_manager.is_healthy(vault_root, manifest.venv):
        console.print("[green]✓[/green] venv bereits aktuell — überspringe")
        return

    venv_path = vault_root / manifest.venv.path
    with console.status("Aktualisiere venv…"):
        try:
            venv_manager.create_venv(vault_root, manifest.venv, uv)
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]✗[/red] venv-Update fehlgeschlagen (Exit {exc.returncode})")
            raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]✗[/red] {exc}")
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] venv aktualisiert: {venv_path}")


def _patch_files(vault_root: Path, manifest: manifest_mod.Manifest) -> None:
    with console.status("Template-Dateien prüfen…"):
        try:
            patched = config_patcher.apply_patches(vault_root, manifest)
        except Exception as exc:
            console.print(f"[red]✗[/red] Patch fehlgeschlagen: {exc}")
            raise typer.Exit(1)

    if not patched:
        console.print("[green]✓[/green] Template-Dateien bereits aktuell")
    else:
        for p in patched:
            console.print(f"[green]✓[/green] Gepatcht: {p.relative_to(vault_root)}")

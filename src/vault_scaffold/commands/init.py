import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from ..core import config_patcher, environment, venv_manager
from ..core import manifest as manifest_mod
from ..core.path_resolver import resolve_vault_root
from ..core.version_tracker import write_installed_version
from . import doctor as doctor_mod

console = Console()

_GUI_STEPS = [
    "Obsidian öffnen und Vault-Pfad auf dieses Verzeichnis zeigen lassen.",
    "Community Plugins aktivieren: Einstellungen → Community-Plugins → Einschalten.",
    "Smart Connections über den Community-Browser installieren und aktivieren.",
    "In den Smart Connections-Einstellungen als Modell 'all-MiniLM-L6-v2' wählen.",
    "Als Python-Interpreter den venv-Pfad eintragen: "
    "{venv}",
    "Claude Code aus dem Vault-Root starten: cd '{vault}' && claude",
]


def run(path: str) -> None:
    from importlib.metadata import version as pkg_version, PackageNotFoundError
    vault_root = _resolve(path)
    uv = _check_uv()
    manifest = manifest_mod.load()
    _ensure_venv(vault_root, manifest, uv)
    _patch_files(vault_root, manifest)
    try:
        installed_version = pkg_version("vault-scaffold")
    except PackageNotFoundError:
        installed_version = manifest.version
    write_installed_version(vault_root, installed_version)
    _print_gui_steps(vault_root, manifest)
    console.print("\n[dim]Führe doctor aus…[/dim]")
    all_ok = doctor_mod.run(vault_root, manifest)
    if not all_ok:
        console.print(
            "\n[yellow]Setup abgeschlossen, aber einige Checks sind noch offen "
            "(meist die manuellen Obsidian-GUI-Schritte oben) — bitte beheben.[/yellow]"
        )
        raise typer.Exit(1)
    console.print("\n[bold green]vault-scaffold init complete.[/bold green]")


# ── steps ─────────────────────────────────────────────────────────────────────

def _resolve(path: str) -> Path:
    try:
        root = resolve_vault_root(path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Vault root: [bold]{root}[/bold]")
    return root


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
        console.print(
            f"[green]✓[/green] venv bereits vorhanden "
            f"(Python {manifest.venv.python_version}) — überspringe"
        )
        return

    venv_path = vault_root / manifest.venv.path
    with console.status(
        f"Erstelle venv mit Python {manifest.venv.python_version}…"
    ):
        try:
            venv_manager.create_venv(vault_root, manifest.venv, uv)
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]✗[/red] venv-Erstellung fehlgeschlagen (Exit {exc.returncode})")
            raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]✗[/red] {exc}")
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] venv bereit: {venv_path}")


def _patch_files(vault_root: Path, manifest: manifest_mod.Manifest) -> None:
    with console.status("Template-Dateien patchen…"):
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


def _print_gui_steps(vault_root: Path, manifest: manifest_mod.Manifest) -> None:
    venv_python = str(vault_root / manifest.venv.path / "bin" / "python")
    steps = [
        s.format(venv=venv_python, vault=vault_root)
        for s in _GUI_STEPS
    ]
    lines = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))
    console.print(
        Panel(
            lines,
            title="[yellow]Verbleibende manuelle Schritte (Obsidian-GUI)[/yellow]",
            border_style="yellow",
        )
    )

"""Individual health-check functions for vault-scaffold doctor."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import ChecksConfig, VenvConfig


@dataclass
class CheckResult:
    ok: bool
    message: str
    warn: bool = field(default=False)  # True → display as yellow, don't fail exit code


def check_python_conflict() -> CheckResult:
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 13:
        return CheckResult(
            ok=True,
            message=f"System-Python {major}.{minor} — sentence-transformers benötigt ≤3.12 im venv",
            warn=True,
        )
    return CheckResult(ok=True, message=f"Python {major}.{minor}")


def check_venv_exists(vault_root: Path, venv_config: VenvConfig) -> CheckResult:
    python = vault_root / venv_config.path / "bin" / "python"
    if python.exists():
        return CheckResult(ok=True, message=str(python))
    return CheckResult(ok=False, message=f"Nicht gefunden: {python}")


def check_venv_python_version(vault_root: Path, venv_config: VenvConfig) -> CheckResult:
    python = vault_root / venv_config.path / "bin" / "python"
    if not python.exists():
        return CheckResult(ok=False, message="venv nicht gefunden")
    try:
        result = subprocess.run(
            [str(python), "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version_str = (result.stdout.strip() or result.stderr.strip())
        if f"Python {venv_config.python_version}" in version_str:
            return CheckResult(ok=True, message=version_str)
        return CheckResult(
            ok=False,
            message=f"Erwartet Python {venv_config.python_version}, gefunden: {version_str}",
        )
    except Exception as exc:
        return CheckResult(ok=False, message=str(exc))


def check_deps_importable(
    vault_root: Path, venv_config: VenvConfig, checks: ChecksConfig
) -> CheckResult:
    python = vault_root / venv_config.path / "bin" / "python"
    if not python.exists():
        return CheckResult(ok=False, message="venv nicht gefunden")
    deps = checks.check_imports or ["sentence_transformers", "mcp", "numpy", "yaml"]
    failed = []
    for dep in deps:
        try:
            result = subprocess.run(
                [
                    str(python), "-c",
                    f"import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('{dep}') else 1)",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                failed.append(dep)
        except Exception:
            failed.append(dep)
    if failed:
        return CheckResult(ok=False, message=f"Nicht installiert: {', '.join(failed)}")
    return CheckResult(ok=True, message="sentence_transformers, mcp, numpy, yaml")


def check_mcp_command(vault_root: Path, checks: ChecksConfig) -> CheckResult:
    mcp_config_path = vault_root / checks.mcp_config
    if not mcp_config_path.exists():
        return CheckResult(ok=False, message=f"Nicht gefunden: {checks.mcp_config}")
    command_path = vault_root / checks.mcp_command
    if not command_path.exists():
        return CheckResult(ok=False, message=f"mcp_command-Pfad fehlt: {command_path}")
    # The MCP config must actually point at mcp_command, otherwise the server
    # would launch with a different (wrong) interpreter and the check is moot.
    try:
        config_text = mcp_config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult(ok=False, message=f"{checks.mcp_config} nicht lesbar: {exc}")
    if checks.mcp_command not in config_text:
        return CheckResult(
            ok=False,
            message=f"{checks.mcp_config} referenziert {checks.mcp_command} nicht",
        )
    return CheckResult(ok=True, message=str(command_path))


def check_no_placeholder(vault_root: Path, checks: ChecksConfig) -> CheckResult:
    offenders = []
    for rel in checks.no_hardcoded_paths:
        f = vault_root / rel
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if "{{VAULT_ROOT}}" in text:
            offenders.append(rel)
    if offenders:
        return CheckResult(ok=False, message="Platzhalter noch vorhanden: " + ", ".join(offenders))
    return CheckResult(ok=True, message="Keine {{VAULT_ROOT}}-Strings gefunden")


def check_hook_scripts(vault_root: Path, checks: ChecksConfig) -> CheckResult:
    # Claude Code invokes hooks via interpreter (`python3 './…'` / `bash './…'`,
    # see settings.json), never as a bare `./script`. The executable bit is
    # therefore irrelevant for .py/.sh hooks — checking it would flag healthy
    # vaults as broken. We only verify the scripts exist.
    missing = [rel for rel in checks.hook_scripts if not (vault_root / rel).exists()]
    if missing:
        return CheckResult(ok=False, message=f"Fehlend: {', '.join(missing)}")
    return CheckResult(ok=True, message=f"{len(checks.hook_scripts)} Scripts vorhanden")

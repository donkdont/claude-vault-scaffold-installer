"""Individual health-check functions for vault-scaffold doctor."""
from __future__ import annotations

import json
import os
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


def check_deps_importable(vault_root: Path, venv_config: VenvConfig) -> CheckResult:
    python = vault_root / venv_config.path / "bin" / "python"
    if not python.exists():
        return CheckResult(ok=False, message="venv nicht gefunden")
    deps = ["sentence_transformers", "mcp", "numpy", "yaml"]
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
    missing = []
    not_executable = []
    for rel in checks.hook_scripts:
        p = vault_root / rel
        if not p.exists():
            missing.append(rel)
        elif not os.access(p, os.X_OK):
            not_executable.append(rel)
    parts = []
    if missing:
        parts.append(f"Fehlend: {', '.join(missing)}")
    if not_executable:
        parts.append(f"Nicht ausführbar: {', '.join(not_executable)}")
    if parts:
        return CheckResult(ok=False, message="; ".join(parts))
    return CheckResult(ok=True, message=f"{len(checks.hook_scripts)} Scripts vorhanden und ausführbar")

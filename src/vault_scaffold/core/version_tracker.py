"""Read and write the installed-version marker inside a vault."""
from __future__ import annotations

from pathlib import Path

_VERSION_FILE = ".claude/vault-scaffold-version"


def write_installed_version(vault_root: Path, version: str) -> None:
    version_file = vault_root / _VERSION_FILE
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(version + "\n", encoding="utf-8")


def read_installed_version(vault_root: Path) -> str | None:
    version_file = vault_root / _VERSION_FILE
    if not version_file.exists():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None

"""Install plain-copy template files into the vault."""
from __future__ import annotations

import shutil
from pathlib import Path

from .manifest import Manifest

# Sentinel strings used to identify action in results
INSTALLED = "installed"
SKIPPED = "skipped"


def install_templates(
    vault_root: Path, manifest: Manifest
) -> list[tuple[Path, str]]:
    """Copy template files to vault if they don't exist yet.

    Idempotent: files that already exist are skipped without modification
    (preserves any user customisations).

    Returns list of (absolute_path, action) where action is INSTALLED or SKIPPED.
    """
    results: list[tuple[Path, str]] = []
    template_dir = manifest.template_dir

    for spec in manifest.templates:
        src = template_dir / spec.file
        dest = vault_root / spec.file

        if not src.exists():
            continue

        if dest.exists():
            results.append((dest, SKIPPED))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            results.append((dest, INSTALLED))

    return results

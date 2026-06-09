"""Install plain-copy template files into the vault."""
from __future__ import annotations

import shutil
from pathlib import Path

from .manifest import Manifest

# Sentinel strings used to identify action in results
INSTALLED = "installed"
SKIPPED = "skipped"
OVERWRITTEN = "overwritten"


def install_templates(
    vault_root: Path, manifest: Manifest, *, force: bool = False
) -> list[tuple[Path, str]]:
    """Copy template files to vault.

    By default idempotent: files that already exist are skipped without
    modification (preserves user customisations).

    With force=True: existing files are overwritten from the template.

    Returns list of (absolute_path, action) where action is INSTALLED,
    SKIPPED, or OVERWRITTEN.
    """
    results: list[tuple[Path, str]] = []
    template_dir = manifest.template_dir

    for spec in manifest.templates:
        src = template_dir / spec.file
        dest = vault_root / spec.file

        if not src.exists():
            continue

        if dest.exists():
            if force:
                shutil.copy2(src, dest)
                results.append((dest, OVERWRITTEN))
            else:
                results.append((dest, SKIPPED))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            results.append((dest, INSTALLED))

    return results

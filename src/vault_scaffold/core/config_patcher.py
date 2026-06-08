from pathlib import Path

from .manifest import Manifest


def apply_patches(vault_root: Path, manifest: Manifest) -> list[Path]:
    """Copy template files into vault_root and replace placeholders.

    Idempotent: skips files where the placeholder no longer appears
    (already patched or manually edited past the placeholder stage).
    Returns list of files actually written.
    """
    patched: list[Path] = []
    for spec in manifest.patches:
        template_file = manifest.template_dir / spec.file
        target_file = vault_root / spec.file

        if not template_file.exists():
            continue

        template_content = template_file.read_text(encoding="utf-8")

        if target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
            # Already patched: placeholder no longer present
            if spec.placeholder not in existing:
                continue
            # Placeholder still in live file → re-patch from template
            content = existing.replace(spec.placeholder, str(vault_root))
        else:
            # Fresh install: copy template and patch
            content = template_content.replace(spec.placeholder, str(vault_root))

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        patched.append(target_file)

    return patched

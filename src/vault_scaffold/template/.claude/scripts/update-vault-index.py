#!/usr/bin/env python3
"""
Vault Index Renderer
Generates INDEX.md files per folder from existing frontmatter.
No API calls — descriptions must be present in frontmatter already.
Run with --bootstrap to rebuild all indexes at once.
Run with --folder "07 Unternehmen/myADVISER" to rebuild a single folder.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

VAULT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = VAULT_ROOT / ".claude" / "index-config.yaml"
SKIP_DIRS = {".claude", ".obsidian", ".trash", ".playwright"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def load_config() -> tuple[list[str], int]:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("indexed_folders", []), cfg.get("max_depth", 6)


def read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def collect_notes(folder: Path, max_depth: int = 6) -> list[Path]:
    notes = []
    for p in sorted(folder.rglob("*.md")):
        if p.name == "INDEX.md":
            continue
        parts = p.relative_to(folder).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if len(parts) - 1 > max_depth:
            continue
        notes.append(p)
    return notes


def build_index_content(folder: Path, notes: list[Path]) -> str:
    lines = [
        "> [!info] Index",
        "> Automatisch generiert – nicht manuell bearbeiten.",
        "",
        "| Notiz | Description | Tags |",
        "|---|---|---|",
    ]

    direct = [n for n in notes if n.parent == folder]
    # Direct subdirs (one level deep) — include subdirs that only contain deeper notes too
    direct_subdirs = sorted({
        n.relative_to(folder).parts[0] for n in notes if n.parent != folder
    })
    direct_subdirs = [folder / name for name in direct_subdirs]

    for note in direct:
        fm = read_frontmatter(note)
        desc = fm.get("description") or ""
        tags = ", ".join(fm.get("tags") or [])
        lines.append(f"| [[{note.stem}]] | {desc} | {tags} |")

    for sub in direct_subdirs:
        rel = sub.relative_to(folder)
        sub_total = sum(1 for n in notes if sub in n.parents)
        sub_index = sub / "INDEX.md"
        sub_fm = read_frontmatter(sub_index) if sub_index.exists() else {}
        sub_desc = sub_fm.get("description") or f"{sub_total} Notizen"
        vault_rel = sub.relative_to(VAULT_ROOT)
        lines.append(f"| [[{vault_rel}/INDEX\\|→ {rel}/]] | {sub_desc} | – |")

    return "\n".join(lines) + "\n"


def write_index_if_changed(folder: Path, content: str) -> bool:
    index_path = folder / "INDEX.md"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        if existing == content:
            return False
    index_path.write_text(content, encoding="utf-8")
    print(f"  INDEX.md aktualisiert: {index_path.relative_to(VAULT_ROOT)}")
    return True


def process_folder(folder_rel: str, max_depth: int = 6) -> None:
    folder = VAULT_ROOT / folder_rel
    if not folder.exists():
        print(f"[SKIP] Ordner nicht gefunden: {folder_rel}", file=sys.stderr)
        return

    notes = collect_notes(folder, max_depth)

    # Build sub-indexes first, recursively for every subfolder containing notes
    all_subdirs = sorted({p for n in notes for p in n.parents if folder in p.parents}, key=lambda p: len(p.parts), reverse=True)
    for sub in all_subdirs:
        sub_notes = [n for n in notes if sub in n.parents]
        content = build_index_content(sub, sub_notes)
        write_index_if_changed(sub, content)

    # Build top-level index
    content = build_index_content(folder, notes)
    write_index_if_changed(folder, content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true", help="Alle konfigurierten Ordner neu indizieren")
    parser.add_argument("--folder", help="Nur diesen Ordner neu indizieren (relativ zu Vault-Root)")
    args = parser.parse_args()

    folders, max_depth = load_config()
    if args.folder:
        print(f"\n[{args.folder}]")
        process_folder(args.folder, max_depth)
    else:
        for folder_rel in folders:
            print(f"\n[{folder_rel}]")
            process_folder(folder_rel, max_depth)

    print("\nFertig.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PostToolUse hook: queues changed .md files in indexed folders for description generation.
Writes paths to .pending-descriptions (one absolute path per line, no duplicates).
"""

import json
import os
import sys
from pathlib import Path

VAULT_ROOT = str(Path(__file__).resolve().parents[2])
QUEUE_PATH = os.path.join(VAULT_ROOT, ".claude", "scripts", ".pending-descriptions")
INDEXED_FOLDERS = [
    "01 Systeme",
    "02 Projekte",
    "03 Wissen",
    "04 Referenz",
    "05 Archiv",
    "06 Forschung",
]

try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

file_path = (
    data.get("tool_input", {}).get("file_path") or
    data.get("tool_response", {}).get("filePath") or
    ""
)

if not file_path or not file_path.endswith(".md"):
    sys.exit(0)

if os.path.basename(file_path) == "INDEX.md":
    sys.exit(0)

if not file_path.startswith(VAULT_ROOT):
    sys.exit(0)

rel = os.path.relpath(file_path, VAULT_ROOT)
if not any(rel.startswith(f) for f in INDEXED_FOLDERS):
    sys.exit(0)

if not os.path.exists(file_path):
    sys.exit(0)

# Read existing queue, add path if not already present
existing = set()
if os.path.exists(QUEUE_PATH):
    with open(QUEUE_PATH, encoding="utf-8") as f:
        existing = {line.strip() for line in f if line.strip()}

if file_path not in existing:
    with open(QUEUE_PATH, "a", encoding="utf-8") as f:
        f.write(file_path + "\n")

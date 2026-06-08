#!/usr/bin/env bash
# SessionStart hook: checks if vault notes are waiting for description generation.
# Outputs a systemMessage if the queue is non-empty.

VAULT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUEUE="$VAULT_ROOT/.claude/scripts/.pending-descriptions"

if [[ ! -f "$QUEUE" ]]; then
  exit 0
fi

# Count non-empty lines
COUNT=$(grep -c '[^[:space:]]' "$QUEUE" 2>/dev/null || echo 0)

if [[ "$COUNT" -eq 0 ]]; then
  rm -f "$QUEUE"
  exit 0
fi

# Output systemMessage for Claude
QUEUE_PATH="$QUEUE" python3 - <<'PYEOF'
import json, os, sys

queue = os.environ["QUEUE_PATH"]
with open(queue) as f:
    paths = [l.strip() for l in f if l.strip()]

if not paths:
    sys.exit(0)

note_list = "\n".join(f"  - {p}" for p in paths)
msg = (
    f"Vault-Description-Queue: {len(paths)} Notiz(en) warten auf Description-Generierung:\n"
    f"{note_list}\n\n"
    f"Bitte spawne den vault-describer Subagenten im Hintergrund mit dieser Notizliste."
)

print(json.dumps({"systemMessage": msg}))
PYEOF

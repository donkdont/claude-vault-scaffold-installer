#!/usr/bin/env python3
"""
PreToolUse-Hook: INDEX-First-Regel für myADVISER und mENSCHwERK.
Blockt Read-Calls auf Nicht-INDEX-Dateien, wenn die zuständige INDEX.md
in dieser Session noch nicht gelesen wurde.
"""
import json
import os
import sys

PROJECTS = ["myADVISER", "mENSCHwERK"]
BASE = "07 Unternehmen"

def get_state_file():
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        # Fallback: PPID + Startzeit als Session-Fingerprint
        ppid = os.getppid()
        try:
            with open(f"/proc/{ppid}/stat") as f:
                starttime = f.read().split()[21]
            session_id = f"{ppid}-{starttime}"
        except Exception:
            session_id = str(ppid)
    return f"/tmp/claude-index-read-{session_id}.json"

def load_state():
    try:
        with open(get_state_file()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"read_indexes": []}

def save_state(state):
    with open(get_state_file(), "w") as f:
        json.dump(state, f)

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Read":
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Welches Projekt ist betroffen?
    matched_project = None
    for project in PROJECTS:
        if f"{BASE}/{project}" in file_path:
            matched_project = project
            break

    if not matched_project:
        sys.exit(0)

    # INDEX.md-Calls immer erlauben und State aktualisieren
    if "INDEX.md" in os.path.basename(file_path):
        state = load_state()
        if matched_project not in state["read_indexes"]:
            state["read_indexes"].append(matched_project)
            save_state(state)
        sys.exit(0)

    # Prüfen ob INDEX.md bereits gelesen wurde
    state = load_state()
    if matched_project in state["read_indexes"]:
        sys.exit(0)

    # Blocken
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"INDEX-First-Regel verletzt: Lies erst "
                f"{BASE}/{matched_project}/INDEX.md "
                f"bevor du andere Dateien in diesem Projekt öffnest."
            )
        }
    }
    print(json.dumps(result))
    sys.exit(0)

if __name__ == "__main__":
    main()

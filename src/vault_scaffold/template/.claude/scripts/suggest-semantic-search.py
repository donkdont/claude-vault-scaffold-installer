#!/usr/bin/env python3
"""
PreToolUse-Hook: Semantiksuche-Erinnerung.
Wenn grep/rg auf .md-Dateien mit natürlichsprachlichem Muster aufgerufen wird
(Leerzeichen im Pattern → konzeptuelle Suche), Hinweis auf vault_semantic_search.
Kein Blocker — Exit 0, Ausführung läuft weiter.
"""
import json
import re
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\b(grep|rg)\b", command):
        sys.exit(0)

    if ".md" not in command:
        sys.exit(0)

    # Quoted patterns extrahieren; flags (beginnend mit -) überspringen
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', command)
    patterns = [p[0] or p[1] for p in quoted if not (p[0] or p[1]).startswith("-")]

    for pattern in patterns:
        if " " in pattern and len(pattern) > 8:
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        "Semantiksuche-Hinweis: vault_semantic_search(query) "
                        "liefert für konzeptuelle Fragen bessere Ergebnisse als grep. "
                        "Weiter mit grep wenn ein exakter String gesucht wird."
                    ),
                }
            }
            print(json.dumps(result))
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()

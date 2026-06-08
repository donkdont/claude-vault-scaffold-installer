#!/usr/bin/env python3
import json
import sys
import os
import re
import glob
from pathlib import Path

VAULT_ROOT = str(Path(__file__).resolve().parents[2])
SKIP_DIRS = ('.claude', '.obsidian', '.trash')
QUELLEN_PREFIX = '00 Inbox/Quellen/'

REQUIRED_FIELDS_NOTE = ('title', 'tags', 'created')
REQUIRED_FIELDS_QUELLE = ('source_url', 'source_type', 'ingested')


def find_wikilink(link: str) -> bool:
    link = link.strip()
    # Path-based link (contains /)
    if '/' in link:
        full = os.path.join(VAULT_ROOT, link + '.md')
        if os.path.exists(full):
            return True
        full_no_ext = os.path.join(VAULT_ROOT, link)
        if os.path.exists(full_no_ext):
            return True
    # Filename-only search
    pattern = os.path.join(VAULT_ROOT, '**', f'{link}.md')
    matches = glob.glob(pattern, recursive=True)
    matches = [
        m for m in matches
        if not any(f'/{d}/' in m or m.endswith(f'/{d}') for d in SKIP_DIRS)
    ]
    return bool(matches)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    file_path = (
        data.get('tool_input', {}).get('file_path') or
        data.get('tool_response', {}).get('filePath') or
        ''
    )

    if not file_path or not file_path.endswith('.md'):
        sys.exit(0)

    if os.path.basename(file_path) == 'INDEX.md':
        sys.exit(0)

    if not file_path.startswith(VAULT_ROOT):
        sys.exit(0)

    rel_path = os.path.relpath(file_path, VAULT_ROOT)

    # Skip .claude/, .obsidian/ and similar internal dirs
    first_part = rel_path.split(os.sep)[0]
    if first_part in SKIP_DIRS:
        sys.exit(0)

    if not os.path.exists(file_path):
        sys.exit(0)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []
    is_quelle = rel_path.startswith(QUELLEN_PREFIX)

    # --- Frontmatter ---
    fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        issues.append('Kein Frontmatter gefunden')
    else:
        fm = fm_match.group(1)
        required = REQUIRED_FIELDS_QUELLE if is_quelle else REQUIRED_FIELDS_NOTE
        for field in required:
            if not re.search(rf'^{field}\s*:', fm, re.MULTILINE):
                issues.append(f'Frontmatter: Feld `{field}` fehlt')

    # --- Wikilinks (nur reguläre Notizen, nicht Quellen) ---
    if not is_quelle:
        # Code-Spans und Fenced-Code-Blocks vorher entfernen (keine echten Links)
        content_stripped = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        content_stripped = re.sub(r'~~~.*?~~~', '', content_stripped, flags=re.DOTALL)
        content_stripped = re.sub(r'`[^`\n]+`', '', content_stripped)
        wikilinks = re.findall(r'\[\[([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]', content_stripped)
        seen = set()
        for link in wikilinks:
            link = link.strip()
            if link in seen:
                continue
            seen.add(link)
            if not find_wikilink(link):
                issues.append(f'Broken Wikilink: `[[{link}]]`')

    if not issues:
        sys.exit(0)

    summary = (
        f'Vault-Lint `{os.path.basename(file_path)}`:\n' +
        '\n'.join(f'  - {i}' for i in issues)
    )
    result = {
        'systemMessage': summary,
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': summary
        }
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

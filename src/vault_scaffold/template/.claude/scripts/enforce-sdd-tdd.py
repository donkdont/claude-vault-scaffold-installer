#!/usr/bin/env python3
"""
PreToolUse-Hook: SDD + TDD + Vertical-Slicing-Paradigma erzwingen.

Blockt das Anlegen neuer Implementierungs-Dateien (Write), wenn weder eine
Spec/Test-Datei im Projekt existiert noch ein Acknowledge-Marker gesetzt ist.

- Nur Write (neue Dateien). Edit setzt voraus, dass die Datei bereits existiert.
- Ignoriert: Markdown, Config, Lock-Files, Vault-interne Scripts, Test-Files.
- Projekt-Root = nächster Vorfahre mit Manifest (pyproject.toml, package.json,
  Cargo.toml, go.mod, build.gradle, pom.xml, Makefile) oder .git.
- Bestätigt Spec ist Spec/Test-Datei IM Projekt oder Marker `.claude-sdd-ack`
  im Projekt-Root.
"""
import json
import os
import sys

# Echte Implementierungs-Sprachen — alles andere wird ignoriert
CODE_EXTS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    '.go', '.rs', '.java', '.kt', '.scala',
    '.c', '.cc', '.cpp', '.cxx', '.h', '.hpp',
    '.rb', '.php', '.cs', '.swift', '.dart', '.ex', '.exs',
    '.lua', '.zig', '.elm',
}

# Dateien, die zwar Code-Extension haben aber keine Implementierung sind
SKIP_BASENAMES = {
    '__init__.py', 'conftest.py', 'setup.py',
    'index.ts', 'index.js',  # häufige Re-Export-Dateien — meist Boilerplate
}

# Pfad-Substrings, die einen Treffer ausschließen
SKIP_PATH_PARTS = (
    '/.claude/', '/.obsidian/', '/.git/', '/node_modules/',
    '/__pycache__/', '/.venv/', '/venv/', '/dist/', '/build/',
    '/.next/', '/.nuxt/', '/target/', '/.cache/',
    '/migrations/',
)

# Manifest-Dateien, die einen Projekt-Root markieren (Reihenfolge irrelevant)
ROOT_MARKERS = (
    'pyproject.toml', 'setup.cfg', 'package.json', 'Cargo.toml',
    'go.mod', 'build.gradle', 'build.gradle.kts', 'pom.xml',
    'Makefile', 'CMakeLists.txt', '.git',
)

ACK_MARKER = '.claude-sdd-ack'

# Test-Datei-Heuristik — wenn neu angelegtes File ein Test ist, durchlassen
def is_test_file(path: str) -> bool:
    base = os.path.basename(path)
    parts = path.replace('\\', '/').split('/')
    # Pytest / Python
    if base.startswith('test_') or base.endswith('_test.py'):
        return True
    # Go
    if base.endswith('_test.go'):
        return True
    # Rust integration tests
    if 'tests' in parts and base.endswith('.rs'):
        return True
    # JS/TS spec/test
    for ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        for marker in ('.test', '.spec'):
            if base.endswith(f'{marker}{ext}'):
                return True
    # Java / Kotlin / generisch — Verzeichnisheuristik
    if any(p in ('test', 'tests', '__tests__', 'spec', '__test__') for p in parts):
        # Aber: .py/.ts allein im Test-Dir → trotzdem als Test akzeptieren
        return True
    return False


def is_config_or_meta(path: str) -> bool:
    base = os.path.basename(path).lower()
    if base.startswith('.'):
        # Dotfiles wie .eslintrc, .prettierrc, .editorconfig
        return True
    config_exts = (
        '.md', '.markdown', '.txt', '.rst',
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
        '.lock', '.env', '.example',
        '.xml', '.html', '.htm', '.css', '.scss', '.sass',
        '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico',
        '.csv', '.tsv', '.sql',
    )
    if any(base.endswith(ext) for ext in config_exts):
        return True
    if base in ('dockerfile', 'makefile', 'jenkinsfile', 'vagrantfile'):
        return True
    return False


def find_project_root(file_path: str) -> str | None:
    """Geh nach oben bis ein Manifest gefunden ist. Stoppt am Filesystem-Root."""
    current = os.path.dirname(os.path.abspath(file_path))
    # Sicherheitslimit gegen unendliche Schleife
    for _ in range(40):
        for marker in ROOT_MARKERS:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


def has_spec_or_tests(project_root: str) -> bool:
    """Walk durch Projekt — gibt True zurück sobald Spec/Test-Hinweis gefunden."""
    spec_dir_names = {'tests', 'test', '__tests__', 'spec', 'specs', 'features'}
    spec_file_hints = (
        # Pydantic-Schemas / Verträge
        'schemas.py', 'schema.py', 'contracts.py', 'contract.py',
        'openapi.yaml', 'openapi.yml', 'openapi.json',
    )
    skip_dirs = {
        '.git', '.venv', 'venv', 'node_modules', '__pycache__',
        'dist', 'build', 'target', '.next', '.nuxt', '.cache',
    }
    for root, dirs, files in os.walk(project_root):
        # In-place Filter, damit os.walk gar nicht erst absteigt
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        # Spec-Verzeichnis als Hinweis
        for d in dirs:
            if d in spec_dir_names:
                # Verzeichnis muss mindestens eine Datei enthalten
                full = os.path.join(root, d)
                try:
                    if any(os.scandir(full)):
                        return True
                except OSError:
                    pass
        for f in files:
            # Test-Datei?
            full = os.path.join(root, f)
            if is_test_file(full):
                return True
            # Spec-Datei (Schema / Contract / OpenAPI)
            if f in spec_file_hints:
                return True
            # Gherkin
            if f.endswith('.feature'):
                return True
    return False


def block_response(reason: str) -> None:
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    if tool_name != 'Write':
        sys.exit(0)

    file_path = data.get('tool_input', {}).get('file_path', '')
    if not file_path:
        sys.exit(0)

    # Edit-artige Calls auf bestehende Dateien interessieren uns nicht
    if os.path.exists(file_path):
        sys.exit(0)

    # Pfad-basierte Skips
    norm = file_path.replace('\\', '/')
    if any(part in norm for part in SKIP_PATH_PARTS):
        sys.exit(0)

    base = os.path.basename(file_path)
    if base in SKIP_BASENAMES:
        sys.exit(0)

    # Config / Markdown / Assets ignorieren
    if is_config_or_meta(file_path):
        sys.exit(0)

    # Nur echte Code-Dateien behandeln
    _, ext = os.path.splitext(file_path)
    if ext.lower() not in CODE_EXTS:
        sys.exit(0)

    # Test-Dateien sind genau das, was wir wollen — durchlassen
    if is_test_file(file_path):
        sys.exit(0)

    # Projekt-Root finden
    project_root = find_project_root(file_path)
    if project_root is None:
        # Standalone-Skript ohne Projekt-Kontext — nicht blockieren
        sys.exit(0)

    # Acknowledge-Marker?
    if os.path.exists(os.path.join(project_root, ACK_MARKER)):
        sys.exit(0)

    # Spec / Tests bereits im Projekt vorhanden?
    if has_spec_or_tests(project_root):
        # Setze Marker, damit weitere Walks entfallen
        try:
            with open(os.path.join(project_root, ACK_MARKER), 'w') as f:
                f.write(
                    'SDD/TDD-Marker — Spec/Test-Dateien vorhanden, '
                    'weitere Implementierungs-Writes nicht mehr blockiert.\n'
                    'Loeschen, um den Hook erneut zu triggern.\n'
                )
        except OSError:
            pass
        sys.exit(0)

    # --- Blockieren ---
    rel = os.path.relpath(file_path, project_root)
    reason = (
        "SDD/TDD-Paradigma verletzt: Du legst eine neue Implementierungs-Datei "
        f"`{rel}` an, aber im Projekt `{os.path.basename(project_root)}` "
        "wurde keine Spec- oder Test-Datei gefunden.\n\n"
        "Pflicht-Reihenfolge:\n"
        "  1. Spec zuerst (Pydantic-Schema / Gherkin .feature / OpenAPI / "
        "Schnittstellenkontrakt)\n"
        "  2. Akzeptanztest rot (httpx / E2E)\n"
        "  3. Unit-Tests rot (innere TDD-Schleife)\n"
        "  4. Erst dann: minimale Implementierung\n\n"
        "Optionen:\n"
        f"  a) Spec/Test-Datei zuerst anlegen (z.B. `tests/test_<slice>.py` "
        f"oder `features/<name>/schemas.py`).\n"
        f"  b) Falls Spec/Test bereits aussserhalb des Projekt-Roots liegt "
        f"oder dies ein bewusstes Spike ist: Marker-Datei anlegen mit\n"
        f"     `touch '{os.path.join(project_root, ACK_MARKER)}'`\n\n"
        "Referenz: `03 Wissen/Softwareentwicklung/SDD-TDD.md` und "
        "`Vertical-Slicing.md`."
    )
    block_response(reason)


if __name__ == '__main__':
    main()

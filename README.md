# vault-scaffold

[![CI](https://github.com/donkdont/claude-vault-scaffold-installer/actions/workflows/ci.yml/badge.svg)](https://github.com/donkdont/claude-vault-scaffold-installer/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vault-scaffold)](https://pypi.org/project/vault-scaffold/)

CLI installer for [claude-vault-scaffold](https://github.com/donkdont/claude-vault-scaffold) — one command to set up Obsidian + Claude Code vault integration.

```bash
uvx vault-scaffold init
```

## What it does

1. Installs Python 3.12 via `uv` (avoids `sentence-transformers` breakage on 3.13/3.14)
2. Creates `.smart-env-tools/.venv` with all required dependencies
3. Patches `vault-describer.md` with your vault's absolute path
4. Runs `doctor` to verify the setup and prints a checklist for remaining GUI steps

## Requirements

- [`uv`](https://docs.astral.sh/uv/) installed on your system
- An Obsidian vault with [claude-vault-scaffold](https://github.com/donkdont/claude-vault-scaffold) structure

## Usage

```bash
# Install into current directory (vault root)
uvx vault-scaffold init

# Install into a specific path
uvx vault-scaffold init /path/to/your/vault

# Check an existing install
uvx vault-scaffold doctor
uvx vault-scaffold doctor /path/to/your/vault
```

## Commands

| Command | Description |
|---|---|
| `init [PATH]` | Idempotent full setup — safe to re-run |
| `doctor [PATH]` | Read-only health check, exit code ≠ 0 on failure |

## License

MIT

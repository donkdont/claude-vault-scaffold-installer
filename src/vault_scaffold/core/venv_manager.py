import subprocess
from pathlib import Path

from .manifest import VenvConfig


def venv_python(vault_root: Path, config: VenvConfig) -> Path:
    return vault_root / config.path / "bin" / "python"


def is_healthy(vault_root: Path, config: VenvConfig) -> bool:
    python = venv_python(vault_root, config)
    if not python.exists():
        return False
    try:
        result = subprocess.run(
            [str(python), "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return f"Python {config.python_version}" in result.stdout
    except Exception:
        return False


def create_venv(vault_root: Path, config: VenvConfig, uv: Path) -> None:
    venv_path = vault_root / config.path

    subprocess.run(
        [str(uv), "python", "install", config.python_version],
        check=True,
    )
    subprocess.run(
        [str(uv), "venv", "--python", config.python_version, str(venv_path)],
        check=True,
    )
    extra_index_args = [
        arg
        for url in config.extra_index_urls
        for arg in ("--extra-index-url", url)
    ]
    subprocess.run(
        [
            str(uv), "pip", "install",
            "--python", str(venv_python(vault_root, config)),
            *extra_index_args,
            *config.deps,
        ],
        check=True,
    )

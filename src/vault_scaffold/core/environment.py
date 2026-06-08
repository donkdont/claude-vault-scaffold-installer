import shutil
from pathlib import Path


def check_uv() -> Path:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "uv not found. Install it from https://astral.sh/uv or run:\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
    return Path(uv)

from pathlib import Path


def resolve_vault_root(path_arg: str) -> Path:
    p = Path(path_arg).expanduser().resolve()
    if not p.exists():
        raise ValueError(f"Path does not exist: {p}")
    if not p.is_dir():
        raise ValueError(f"Not a directory: {p}")
    return p

"""Load and expose the bundled manifest.toml."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class VenvConfig:
    path: str
    python_version: str
    deps: list[str]
    extra_index_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchSpec:
    file: str
    placeholder: str


@dataclass(frozen=True)
class ChecksConfig:
    mcp_command: str
    mcp_config: str
    embedding_dim: int
    model_key: str
    hook_scripts: list[str]
    no_hardcoded_paths: list[str]


@dataclass(frozen=True)
class Manifest:
    version: str
    description: str
    venv: VenvConfig
    patches: list[PatchSpec]
    checks: ChecksConfig

    @property
    def template_dir(self) -> Path:
        """Absolute path to the vendored template/ directory inside this package."""
        pkg = resources.files("vault_scaffold")
        return Path(str(pkg)) / "template"


def load() -> Manifest:
    """Read the bundled manifest.toml and return a typed Manifest."""
    pkg = resources.files("vault_scaffold")
    manifest_bytes = (pkg / "template" / "manifest.toml").read_bytes()
    raw = tomllib.loads(manifest_bytes.decode())

    scaffold = raw["scaffold"]
    venv_raw = raw["venv"]
    checks_raw = raw["checks"]

    return Manifest(
        version=scaffold["version"],
        description=scaffold["description"],
        venv=VenvConfig(
            path=venv_raw["path"],
            python_version=venv_raw["python_version"],
            deps=venv_raw["deps"],
            extra_index_urls=venv_raw.get("extra_index_urls", []),
        ),
        patches=[
            PatchSpec(file=p["file"], placeholder=p["placeholder"])
            for p in raw.get("patches", [])
        ],
        checks=ChecksConfig(
            mcp_command=checks_raw["mcp_command"],
            mcp_config=checks_raw["mcp_config"],
            embedding_dim=checks_raw["embedding_dim"],
            model_key=checks_raw["model_key"],
            hook_scripts=checks_raw["hook_scripts"],
            no_hardcoded_paths=checks_raw.get("no_hardcoded_paths", []),
        ),
    )

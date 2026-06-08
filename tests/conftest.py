import pytest
from vault_scaffold.core.manifest import ChecksConfig, VenvConfig

VENV_PATH = ".smart-env-tools/.venv"


@pytest.fixture
def vault_root(tmp_path):
    return tmp_path


@pytest.fixture
def venv_config():
    return VenvConfig(
        path=VENV_PATH,
        python_version="3.12",
        deps=["sentence-transformers>=2.7", "mcp>=1.0", "numpy>=1.26", "pyyaml>=6.0"],
    )


@pytest.fixture
def checks_config():
    return ChecksConfig(
        mcp_command=f"{VENV_PATH}/bin/python",
        mcp_config=".mcp.json",
        embedding_dim=384,
        model_key="sentence-transformers/all-MiniLM-L6-v2",
        hook_scripts=[".claude/scripts/hook_a.sh", ".claude/scripts/hook_b.py"],
        no_hardcoded_paths=[".claude/agents/vault-describer.md"],
    )


@pytest.fixture
def fake_venv_python(vault_root, venv_config):
    """Create a minimal venv bin/python symlink pointing at sys.executable."""
    import sys
    python = vault_root / venv_config.path / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    return python

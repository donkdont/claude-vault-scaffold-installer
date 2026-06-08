"""Tests for core/version_tracker.py."""
from vault_scaffold.core.version_tracker import read_installed_version, write_installed_version


def test_write_then_read(tmp_path):
    write_installed_version(tmp_path, "0.3.0")
    assert read_installed_version(tmp_path) == "0.3.0"


def test_read_missing(tmp_path):
    assert read_installed_version(tmp_path) is None


def test_write_creates_parent(tmp_path):
    write_installed_version(tmp_path, "1.0.0")
    version_file = tmp_path / ".claude" / "vault-scaffold-version"
    assert version_file.exists()
    assert version_file.read_text().strip() == "1.0.0"


def test_write_idempotent(tmp_path):
    write_installed_version(tmp_path, "0.2.0")
    write_installed_version(tmp_path, "0.3.0")
    assert read_installed_version(tmp_path) == "0.3.0"


def test_read_strips_whitespace(tmp_path):
    version_file = tmp_path / ".claude" / "vault-scaffold-version"
    version_file.parent.mkdir(parents=True)
    version_file.write_text("  0.2.0\n\n", encoding="utf-8")
    assert read_installed_version(tmp_path) == "0.2.0"

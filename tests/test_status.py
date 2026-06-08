"""Tests for commands/status.py."""
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vault_scaffold.cli import app
from vault_scaffold.core.version_tracker import write_installed_version

runner = CliRunner()


def test_status_up_to_date(tmp_path):
    write_installed_version(tmp_path, "0.3.0")
    with patch("vault_scaffold.commands.status.pkg_version", return_value="0.3.0"):
        result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "0.3.0" in result.output
    assert "Aktuell" in result.output


def test_status_update_available(tmp_path):
    write_installed_version(tmp_path, "0.2.0")
    with patch("vault_scaffold.commands.status.pkg_version", return_value="0.3.0"):
        result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 1
    assert "0.2.0" in result.output
    assert "0.3.0" in result.output
    assert "Update" in result.output


def test_status_not_installed(tmp_path):
    with patch("vault_scaffold.commands.status.pkg_version", return_value="0.3.0"):
        result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 1
    assert "Nicht installiert" in result.output


def test_status_invalid_path():
    result = runner.invoke(app, ["status", "/nonexistent/path/xyz"])
    assert result.exit_code == 1

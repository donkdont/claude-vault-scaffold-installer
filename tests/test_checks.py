"""Unit tests for vault_scaffold.core.checks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vault_scaffold.core import checks as c


# ── check_python_conflict ──────────────────────────────────────────────────────

def test_python_conflict_ok(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 12, 0, "final", 0))
    r = c.check_python_conflict()
    assert r.ok is True
    assert r.warn is False


def test_python_conflict_warn_313(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 13, 0, "final", 0))
    r = c.check_python_conflict()
    assert r.ok is True
    assert r.warn is True


def test_python_conflict_warn_314(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 14, 0, "final", 0))
    r = c.check_python_conflict()
    assert r.ok is True
    assert r.warn is True


# ── check_venv_exists ──────────────────────────────────────────────────────────

def test_venv_exists_found(vault_root, venv_config, fake_venv_python):
    r = c.check_venv_exists(vault_root, venv_config)
    assert r.ok is True


def test_venv_exists_missing(vault_root, venv_config):
    r = c.check_venv_exists(vault_root, venv_config)
    assert r.ok is False
    assert "Nicht gefunden" in r.message


# ── check_venv_python_version ──────────────────────────────────────────────────

def test_venv_python_version_correct(vault_root, venv_config, fake_venv_python):
    mock = MagicMock()
    mock.stdout = "Python 3.12.5\n"
    mock.stderr = ""
    with patch("subprocess.run", return_value=mock):
        r = c.check_venv_python_version(vault_root, venv_config)
    assert r.ok is True
    assert "3.12.5" in r.message


def test_venv_python_version_wrong(vault_root, venv_config, fake_venv_python):
    mock = MagicMock()
    mock.stdout = "Python 3.11.9\n"
    mock.stderr = ""
    with patch("subprocess.run", return_value=mock):
        r = c.check_venv_python_version(vault_root, venv_config)
    assert r.ok is False
    assert "3.11.9" in r.message


def test_venv_python_version_timeout(vault_root, venv_config, fake_venv_python):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 5)):
        r = c.check_venv_python_version(vault_root, venv_config)
    assert r.ok is False


def test_venv_python_version_no_venv(vault_root, venv_config):
    r = c.check_venv_python_version(vault_root, venv_config)
    assert r.ok is False
    assert "venv nicht gefunden" in r.message


# ── check_deps_importable ──────────────────────────────────────────────────────

def test_deps_importable_all_ok(vault_root, venv_config, fake_venv_python):
    mock = MagicMock()
    mock.returncode = 0
    with patch("subprocess.run", return_value=mock):
        r = c.check_deps_importable(vault_root, venv_config)
    assert r.ok is True


def test_deps_importable_one_missing(vault_root, venv_config, fake_venv_python):
    def side_effect(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 1 if "sentence_transformers" in cmd[-1] else 0
        return m

    with patch("subprocess.run", side_effect=side_effect):
        r = c.check_deps_importable(vault_root, venv_config)
    assert r.ok is False
    assert "sentence_transformers" in r.message


def test_deps_importable_no_venv(vault_root, venv_config):
    r = c.check_deps_importable(vault_root, venv_config)
    assert r.ok is False
    assert "venv nicht gefunden" in r.message


# ── check_mcp_command ──────────────────────────────────────────────────────────

def test_mcp_command_ok(vault_root, checks_config, fake_venv_python):
    mcp_json = vault_root / checks_config.mcp_config
    mcp_json.write_text(json.dumps({"mcpServers": {"sc": {"command": checks_config.mcp_command}}}))
    r = c.check_mcp_command(vault_root, checks_config)
    assert r.ok is True


def test_mcp_command_no_config(vault_root, checks_config, fake_venv_python):
    r = c.check_mcp_command(vault_root, checks_config)
    assert r.ok is False
    assert ".mcp.json" in r.message


def test_mcp_command_missing_python(vault_root, checks_config):
    mcp_json = vault_root / checks_config.mcp_config
    mcp_json.write_text(json.dumps({"mcpServers": {"sc": {"command": checks_config.mcp_command}}}))
    r = c.check_mcp_command(vault_root, checks_config)
    assert r.ok is False
    assert "mcp_command-Pfad fehlt" in r.message


def test_mcp_command_not_referenced(vault_root, checks_config, fake_venv_python):
    mcp_json = vault_root / checks_config.mcp_config
    mcp_json.write_text(json.dumps({"mcpServers": {"sc": {"command": "/some/other/python"}}}))
    r = c.check_mcp_command(vault_root, checks_config)
    assert r.ok is False
    assert "referenziert" in r.message


# ── check_no_placeholder ───────────────────────────────────────────────────────

def test_no_placeholder_clean(vault_root, checks_config):
    f = vault_root / ".claude/agents/vault-describer.md"
    f.parent.mkdir(parents=True)
    f.write_text("# Vault Describer\nSome content without placeholders.")
    r = c.check_no_placeholder(vault_root, checks_config)
    assert r.ok is True


def test_no_placeholder_found(vault_root, checks_config):
    f = vault_root / ".claude/agents/vault-describer.md"
    f.parent.mkdir(parents=True)
    f.write_text("path: {{VAULT_ROOT}}/.smart-env-tools")
    r = c.check_no_placeholder(vault_root, checks_config)
    assert r.ok is False
    assert "vault-describer.md" in r.message


def test_no_placeholder_file_absent(vault_root, checks_config):
    r = c.check_no_placeholder(vault_root, checks_config)
    assert r.ok is True


# ── check_hook_scripts ─────────────────────────────────────────────────────────

def test_hook_scripts_all_present(vault_root, checks_config):
    for rel in checks_config.hook_scripts:
        p = vault_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("#!/bin/bash\necho ok")
    r = c.check_hook_scripts(vault_root, checks_config)
    assert r.ok is True
    assert "2 Scripts" in r.message


def test_hook_scripts_one_missing(vault_root, checks_config):
    first = vault_root / checks_config.hook_scripts[0]
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("#!/bin/bash\necho ok")
    r = c.check_hook_scripts(vault_root, checks_config)
    assert r.ok is False
    assert "Fehlend" in r.message


def test_hook_scripts_all_missing(vault_root, checks_config):
    r = c.check_hook_scripts(vault_root, checks_config)
    assert r.ok is False

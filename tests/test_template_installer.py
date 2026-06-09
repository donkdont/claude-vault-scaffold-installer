"""Tests for core/template_installer.py"""
from pathlib import Path

import pytest

from vault_scaffold.core import manifest as manifest_mod
from vault_scaffold.core import template_installer
from vault_scaffold.core.manifest import TemplateSpec


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_manifest_with_templates(tmp_template_dir: Path, specs: list[str]) -> manifest_mod.Manifest:
    """Build a minimal Manifest pointing at a custom template_dir."""
    manifest = manifest_mod.load()
    # Patch template_dir via subclass to avoid modifying frozen dataclass
    class _TestManifest(manifest_mod.Manifest):
        @property
        def template_dir(self) -> Path:
            return tmp_template_dir

    return _TestManifest(
        version=manifest.version,
        description=manifest.description,
        venv=manifest.venv,
        patches=manifest.patches,
        templates=[TemplateSpec(file=f) for f in specs],
        checks=manifest.checks,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestInstallTemplates:
    def test_installs_missing_file(self, tmp_path):
        """A file absent in the vault is copied from the template dir."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / ".mcp.json"
        src.parent.mkdir(parents=True)
        src.write_text('{"mcpServers": {}}')

        manifest = _make_manifest_with_templates(template_dir, [".mcp.json"])
        results = template_installer.install_templates(vault_root, manifest)

        assert len(results) == 1
        dest, action = results[0]
        assert action == template_installer.INSTALLED
        assert dest == vault_root / ".mcp.json"
        assert dest.read_text() == '{"mcpServers": {}}'

    def test_skips_existing_file(self, tmp_path):
        """A file that already exists in the vault is not overwritten."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / ".mcp.json"
        src.parent.mkdir(parents=True)
        src.write_text('{"template": true}')

        existing = vault_root / ".mcp.json"
        existing.write_text('{"user": "customised"}')

        manifest = _make_manifest_with_templates(template_dir, [".mcp.json"])
        results = template_installer.install_templates(vault_root, manifest)

        assert len(results) == 1
        dest, action = results[0]
        assert action == template_installer.SKIPPED
        assert existing.read_text() == '{"user": "customised"}'

    def test_creates_parent_directories(self, tmp_path):
        """Nested destination directories are created automatically."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / ".claude" / "scripts" / "hook.py"
        src.parent.mkdir(parents=True)
        src.write_text("# hook")

        manifest = _make_manifest_with_templates(
            template_dir, [".claude/scripts/hook.py"]
        )
        results = template_installer.install_templates(vault_root, manifest)

        dest, action = results[0]
        assert action == template_installer.INSTALLED
        assert dest.exists()
        assert dest.read_text() == "# hook"

    def test_silently_skips_missing_template_file(self, tmp_path):
        """If the template source is missing, the entry is silently skipped."""
        template_dir = tmp_path / "tmpl"
        template_dir.mkdir()
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        manifest = _make_manifest_with_templates(template_dir, ["nonexistent.json"])
        results = template_installer.install_templates(vault_root, manifest)

        assert results == []

    def test_idempotent_on_second_run(self, tmp_path):
        """Running install twice leaves files unchanged and returns all skipped."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / "file.txt"
        src.parent.mkdir(parents=True)
        src.write_text("content")

        manifest = _make_manifest_with_templates(template_dir, ["file.txt"])

        # First run installs
        r1 = template_installer.install_templates(vault_root, manifest)
        assert r1[0][1] == template_installer.INSTALLED

        # Second run skips
        r2 = template_installer.install_templates(vault_root, manifest)
        assert r2[0][1] == template_installer.SKIPPED
        assert (vault_root / "file.txt").read_text() == "content"

    def test_multiple_files_mixed_state(self, tmp_path):
        """Correctly reports installed/skipped for a mix of new and existing files."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        for name in ["a.txt", "b.txt", "c.txt"]:
            f = template_dir / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(name)

        # Pre-create b.txt in vault
        (vault_root / "b.txt").write_text("existing")

        manifest = _make_manifest_with_templates(
            template_dir, ["a.txt", "b.txt", "c.txt"]
        )
        results = template_installer.install_templates(vault_root, manifest)

        by_name = {p.name: action for p, action in results}
        assert by_name["a.txt"] == template_installer.INSTALLED
        assert by_name["b.txt"] == template_installer.SKIPPED
        assert by_name["c.txt"] == template_installer.INSTALLED

    def test_bundled_manifest_has_templates(self):
        """The real bundled manifest.toml contains at least one [[templates]] entry."""
        manifest = manifest_mod.load()
        assert len(manifest.templates) > 0, "manifest.toml should define [[templates]]"

    def test_all_bundled_template_files_exist(self):
        """Every [[templates]] entry in the bundled manifest has a real source file."""
        manifest = manifest_mod.load()
        missing = [
            spec.file
            for spec in manifest.templates
            if not (manifest.template_dir / spec.file).exists()
        ]
        assert missing == [], f"Template source files missing: {missing}"

    def test_force_overwrites_existing_file(self, tmp_path):
        """With force=True, an existing vault file is overwritten from the template."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / ".mcp.json"
        src.parent.mkdir(parents=True)
        src.write_text('{"template": true}')

        existing = vault_root / ".mcp.json"
        existing.write_text('{"user": "customised"}')

        manifest = _make_manifest_with_templates(template_dir, [".mcp.json"])
        results = template_installer.install_templates(vault_root, manifest, force=True)

        assert len(results) == 1
        dest, action = results[0]
        assert action == template_installer.OVERWRITTEN
        assert dest.read_text() == '{"template": true}'

    def test_force_false_preserves_existing_file(self, tmp_path):
        """With force=False (default), an existing vault file is not overwritten."""
        template_dir = tmp_path / "tmpl"
        vault_root = tmp_path / "vault"
        vault_root.mkdir()

        src = template_dir / ".mcp.json"
        src.parent.mkdir(parents=True)
        src.write_text('{"template": true}')

        existing = vault_root / ".mcp.json"
        existing.write_text('{"user": "customised"}')

        manifest = _make_manifest_with_templates(template_dir, [".mcp.json"])
        results = template_installer.install_templates(vault_root, manifest, force=False)

        assert results[0][1] == template_installer.SKIPPED
        assert existing.read_text() == '{"user": "customised"}'

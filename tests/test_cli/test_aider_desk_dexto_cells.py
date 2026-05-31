"""Install-machinery tests for aider-desk + dexto config_file_folder cells.

TDD test battery for PR4 (#252): install→uninstall round-trip, both-scope /
global-only, foreign-guard + sentinel, idempotency, fail-loud on unwritable
base, and content parse-back (JSON for aider-desk, YAML for dexto).

Tests are written BEFORE the cells are enabled in skill_agents.py so they
drive the implementation (all will fail initially because
subagent_mechanism='none' in both entries).
"""
from __future__ import annotations

import json
import stat

import pytest
import yaml


# ── shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def agent_content(tmp_path):
    """A multi-line agent .md file for content parse-back tests."""
    content = tmp_path / "canonical" / "my-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(
        "---\nname: my-agent\ndescription: test agent\n---\n\n"
        "Line one.\nLine two.\nLine three with multiple\nparagraphs here.\n"
    )
    return content


# ══════════════════════════════════════════════════════════════════════════════
# aider-desk
# ══════════════════════════════════════════════════════════════════════════════

class TestAiderDeskInstallUninstallRoundTrip:
    """Task 1a — install→uninstall cleans up the per-slug subdir."""

    def test_aider_desk_install_uninstall_round_trip(self, tmp_path, agent_content):
        """Global install writes config.json + sentinel; uninstall removes both."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        result = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )

        subdir = tmp_path / ".aider-desk" / "agents" / "my-agent"
        cfg = subdir / "config.json"
        sentinel = subdir / ".config.json.attk"

        assert result == cfg
        assert cfg.exists(), "config.json not written"
        assert sentinel.exists(), ".config.json.attk sentinel not written"

        # Verify JSON content round-trips correctly.
        body = json.loads(cfg.read_text())
        assert body["name"] == "my-agent"
        assert body["subagent"]["enabled"] is True
        assert "Line one." in body["source"]
        assert "Line three" in body["source"]

        adapter.uninstall("my-agent", scope="global", home=tmp_path)

        assert not subdir.exists(), "subdir not removed on uninstall — orphan"
        assert not cfg.exists(), "config.json orphaned after uninstall"
        assert not sentinel.exists(), ".config.json.attk sentinel orphaned"

    def test_aider_desk_uninstall_is_idempotent_when_not_installed(
        self, tmp_path, agent_content
    ):
        """Uninstalling a slug that was never installed must not raise."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        # Should not raise even if subdir doesn't exist.
        adapter.uninstall("never-installed", scope="global", home=tmp_path)


class TestAiderDeskBothScopes:
    """Task 1b — both global and project scopes work end-to-end."""

    def test_aider_desk_global_scope(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        cfg = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert cfg.is_relative_to(tmp_path / ".aider-desk")
        assert cfg.exists()
        adapter.uninstall("my-agent", scope="global", home=tmp_path)
        assert not cfg.exists()

    def test_aider_desk_project_scope(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        project = tmp_path / "myproj"
        project.mkdir()
        adapter = config_file_folder.adapter_for("aider-desk")
        cfg = adapter.install(
            "my-agent", agent_content, scope="project", project=project
        )
        assert cfg.is_relative_to(project / ".aider-desk")
        assert cfg.exists()

        # Sentinel must also exist for the project-scope install.
        sentinel = project / ".aider-desk" / "agents" / "my-agent" / ".config.json.attk"
        assert sentinel.exists(), ".config.json.attk sentinel missing at project scope"

        adapter.uninstall("my-agent", scope="project", project=project)
        subdir = project / ".aider-desk" / "agents" / "my-agent"
        assert not subdir.exists(), "project-scope subdir orphaned"


class TestAiderDeskGuardForeign:
    """Task 1c — foreign-file guard with sentinel semantics."""

    def test_aider_desk_guard_foreign_raises_on_no_sentinel(
        self, tmp_path, agent_content
    ):
        """Pre-existing config.json WITHOUT .attk sentinel → install refuses."""
        from agent_toolkit_cli.agent_adapters import config_file_folder
        from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError

        subdir = tmp_path / ".aider-desk" / "agents" / "my-agent"
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "config.json").write_text('{"foreign": true}')
        # No .config.json.attk sentinel — this is a foreign file.

        adapter = config_file_folder.adapter_for("aider-desk")
        with pytest.raises((AgentProjectionConflictError, FileExistsError)):
            adapter.install(
                "my-agent", agent_content, scope="global", home=tmp_path
            )

        # Foreign file must remain untouched.
        assert json.loads(
            (subdir / "config.json").read_text()
        ) == {"foreign": True}

    def test_aider_desk_reinstall_over_own_sentinel_succeeds(
        self, tmp_path, agent_content
    ):
        """Re-install over our own file (sentinel present) succeeds without overwrite=True."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        # First install writes sentinel.
        adapter.install("my-agent", agent_content, scope="global", home=tmp_path)

        # Second install: sentinel present → recognised as our own → no raise.
        cfg = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert cfg.exists(), "re-install failed (sentinel-based re-install)"

    def test_aider_desk_guard_foreign_overwrite_bypasses_check(
        self, tmp_path, agent_content
    ):
        """overwrite=True allows clobbering even without a sentinel."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        subdir = tmp_path / ".aider-desk" / "agents" / "my-agent"
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "config.json").write_text('{"foreign": true}')

        adapter = config_file_folder.adapter_for("aider-desk")
        # overwrite=True means the facade vouches this is tool-owned.
        cfg = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path, overwrite=True
        )
        assert cfg.exists()
        body = json.loads(cfg.read_text())
        assert body["name"] == "my-agent"  # our file, not the foreign one


class TestAiderDeskIdempotent:
    """Task 1d — double install is a no-op (no error, no duplication)."""

    def test_aider_desk_idempotent(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        first = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert first.exists()
        # Second install should succeed (sentinel recognises our own file).
        second = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert second.exists()
        assert first == second


class TestAiderDeskFailLoud:
    """Task 1e — fail loud on unwritable base dir."""

    def test_aider_desk_fail_loud_unwritable_base(self, tmp_path, agent_content):
        """Install into an unwritable dir must raise, not silently skip."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        base = tmp_path / ".aider-desk"
        base.mkdir(parents=True)
        base.chmod(stat.S_IRUSR | stat.S_IXUSR)  # read + execute, no write

        adapter = config_file_folder.adapter_for("aider-desk")
        with pytest.raises((OSError, PermissionError)):
            adapter.install(
                "my-agent", agent_content, scope="global", home=tmp_path
            )

        base.chmod(stat.S_IRWXU)  # restore so tmp_path cleanup doesn't error


class TestAiderDeskContentParseBack:
    """Task 1f — installed JSON is well-formed and source round-trips."""

    def test_aider_desk_json_parse_back(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("aider-desk")
        cfg = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        body = json.loads(cfg.read_text())
        assert isinstance(body, dict)
        assert body["name"] == "my-agent"
        assert body["subagent"]["enabled"] is True
        # Multi-line source round-trips correctly.
        assert "Line one." in body["source"]
        assert "Line two." in body["source"]
        assert "Line three" in body["source"]


# ══════════════════════════════════════════════════════════════════════════════
# dexto
# ══════════════════════════════════════════════════════════════════════════════

class TestDextoInstallUninstallGlobal:
    """Task 2a — global-only round-trip + YAML block-scalar parse-back."""

    def test_dexto_install_uninstall_global(self, tmp_path, agent_content):
        """Global install → valid YAML with multi-line `source:` block → uninstall → GONE."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("dexto")
        result = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )

        subdir = tmp_path / ".dexto" / "agents" / "my-agent"
        yml = subdir / "my-agent.yml"
        sentinel = subdir / ".my-agent.yml.attk"

        assert result == yml
        assert yml.exists(), "my-agent.yml not written"
        assert sentinel.exists(), ".my-agent.yml.attk sentinel not written"

        # Parse YAML and assert source block round-trips correctly (multi-line).
        body = yaml.safe_load(yml.read_text())
        assert isinstance(body, dict)
        assert body["name"] == "my-agent"
        assert "Line one." in body["source"]
        assert "Line two." in body["source"]
        assert "Line three with multiple" in body["source"]
        # `source:` must be a real multi-line string, not a collapsed single line.
        assert "\n" in body["source"], "source block-scalar collapsed to single line"

        adapter.uninstall("my-agent", scope="global", home=tmp_path)

        assert not subdir.exists(), "dexto subdir orphaned after uninstall"
        assert not yml.exists(), "my-agent.yml orphaned"
        assert not sentinel.exists(), ".my-agent.yml.attk orphaned"

    def test_dexto_uninstall_idempotent_when_not_installed(self, tmp_path):
        """Uninstalling a slug that was never installed must not raise."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("dexto")
        adapter.uninstall("never-installed", scope="global", home=tmp_path)


class TestDextoProjectScopeRaises:
    """Task 2b — project scope raises ValueError, not a crash."""

    def test_dexto_project_scope_raises(self, tmp_path, agent_content):
        """Project-scope install must raise ValueError with a clear message."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        project = tmp_path / "myproj"
        project.mkdir()
        adapter = config_file_folder.adapter_for("dexto")
        with pytest.raises(ValueError, match="(?i)global.only|dexto"):
            adapter.install(
                "my-agent", agent_content, scope="project", project=project
            )

    def test_dexto_project_scope_destination_raises(self, tmp_path):
        """destination() at project scope must also raise (not return a path)."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        project = tmp_path / "myproj"
        project.mkdir()
        adapter = config_file_folder.adapter_for("dexto")
        with pytest.raises(ValueError, match="(?i)global.only|dexto"):
            adapter.destination("my-agent", scope="project", project=project)


class TestDextoGuardForeign:
    """Task 2c — foreign-file guard with sentinel semantics."""

    def test_dexto_guard_foreign_raises_on_no_sentinel(
        self, tmp_path, agent_content
    ):
        """Pre-existing .yml WITHOUT sentinel → install refuses."""
        from agent_toolkit_cli.agent_adapters import config_file_folder
        from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError

        subdir = tmp_path / ".dexto" / "agents" / "my-agent"
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "my-agent.yml").write_text("name: foreign\n")
        # No sentinel.

        adapter = config_file_folder.adapter_for("dexto")
        with pytest.raises((AgentProjectionConflictError, FileExistsError)):
            adapter.install(
                "my-agent", agent_content, scope="global", home=tmp_path
            )

    def test_dexto_reinstall_over_own_sentinel_succeeds(
        self, tmp_path, agent_content
    ):
        """Re-install over our own file (sentinel present) succeeds."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("dexto")
        adapter.install("my-agent", agent_content, scope="global", home=tmp_path)
        # Sentinel written on first install; second should not raise.
        yml = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert yml.exists()


class TestDextoIdempotent:
    """Task 2d — double install is a no-op (no error)."""

    def test_dexto_idempotent(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("dexto")
        first = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        second = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        assert first == second
        assert second.exists()


class TestDextoFailLoud:
    """Task 2e — fail loud on unwritable base dir."""

    def test_dexto_fail_loud_unwritable(self, tmp_path, agent_content):
        """Install into an unwritable dir must raise, not silently skip."""
        from agent_toolkit_cli.agent_adapters import config_file_folder

        base = tmp_path / ".dexto"
        base.mkdir(parents=True)
        base.chmod(stat.S_IRUSR | stat.S_IXUSR)  # no write

        adapter = config_file_folder.adapter_for("dexto")
        with pytest.raises((OSError, PermissionError)):
            adapter.install(
                "my-agent", agent_content, scope="global", home=tmp_path
            )

        base.chmod(stat.S_IRWXU)  # restore


class TestDextoContentParseBack:
    """Task 2f — YAML block-scalar round-trips for multi-line source."""

    def test_dexto_yaml_multiline_source_parse_back(self, tmp_path, agent_content):
        from agent_toolkit_cli.agent_adapters import config_file_folder

        adapter = config_file_folder.adapter_for("dexto")
        yml = adapter.install(
            "my-agent", agent_content, scope="global", home=tmp_path
        )
        body = yaml.safe_load(yml.read_text())
        assert body["name"] == "my-agent"
        # Every line of the multi-line body is preserved.
        for line in ("Line one.", "Line two.", "Line three with multiple", "paragraphs here."):
            assert line in body["source"], f"source block missing: {line!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Dispatcher-level: aider-desk + dexto must be enabled via config_file_folder
# ══════════════════════════════════════════════════════════════════════════════

class TestDispatcherEnablement:
    """aider-desk + dexto must be reachable via get_adapter() after PR4."""

    def test_aider_desk_get_adapter_returns_adapter(self):
        from agent_toolkit_cli.agent_adapters import get_adapter

        adapter = get_adapter("aider-desk")
        assert hasattr(adapter, "install")
        assert hasattr(adapter, "uninstall")

    def test_dexto_get_adapter_returns_adapter(self):
        from agent_toolkit_cli.agent_adapters import get_adapter

        adapter = get_adapter("dexto")
        assert hasattr(adapter, "install")
        assert hasattr(adapter, "uninstall")

    def test_codex_still_raises_unsupported(self):
        """codex must remain disabled (subagent_mechanism='none')."""
        from agent_toolkit_cli.agent_adapters import (
            UnsupportedMechanismError,
            get_adapter,
        )

        with pytest.raises(UnsupportedMechanismError):
            get_adapter("codex")

    def test_firebender_still_raises_unsupported(self):
        """firebender must remain disabled (subagent_mechanism='none')."""
        from agent_toolkit_cli.agent_adapters import (
            UnsupportedMechanismError,
            get_adapter,
        )

        with pytest.raises(UnsupportedMechanismError):
            get_adapter("firebender")

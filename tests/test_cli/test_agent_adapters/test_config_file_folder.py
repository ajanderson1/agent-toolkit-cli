"""config_file_folder mechanism: 3 cells with registry mutation.

  - aider-desk: per-slug config.json + order.json sort.
  - dexto: per-slug yml subdir; parent-allowedAgents edit is OUT OF SCOPE for PR2.
  - firebender: atomic firebender.json mutation; callable: true in markdown.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def fake_content(tmp_path):
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(
        "---\nname: test-agent\ndescription: test\n---\n\nBody text.\n"
    )
    return content


# ── aider-desk ───────────────────────────────────────────────────────────

def test_aider_desk_install_writes_per_slug_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".aider-desk" / "agents" / "test-agent" / "config.json"
    assert result.exists()
    body = json.loads(result.read_text())
    assert body["subagent"]["enabled"] is True


def test_aider_desk_uninstall_removes_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    subdir = tmp_path / ".aider-desk" / "agents" / "test-agent"
    assert subdir.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not subdir.exists()


# ── dexto ────────────────────────────────────────────────────────────────

def test_dexto_install_writes_yml_in_per_agent_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".dexto" / "agents" / "test-agent" / "test-agent.yml"
    assert result.exists()


def test_dexto_project_scope_raises_unsupported(tmp_path, fake_content):
    """Dexto has no project-scope convention per spec addendum."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(ValueError, match="dexto"):
        adapter.install("test-agent", fake_content, scope="project", project=project)


# ── firebender ───────────────────────────────────────────────────────────

def test_firebender_install_writes_md_with_callable_true(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".firebender" / "agents" / "test-agent.md"
    text = result.read_text()
    assert "callable: true" in text


def test_firebender_install_appends_to_firebender_json(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    fb_json = tmp_path / ".firebender" / "firebender.json"
    assert fb_json.exists()
    body = json.loads(fb_json.read_text())
    assert "agents" in body
    assert any("test-agent.md" in p for p in body["agents"])


def test_firebender_preserves_unrelated_json_keys(tmp_path, fake_content):
    """firebender.json may have other keys (mcp_servers, etc.); preserve them."""
    fb_dir = tmp_path / ".firebender"
    fb_dir.mkdir()
    fb_json = fb_dir / "firebender.json"
    fb_json.write_text(json.dumps({
        "agents": ["existing-agent.md"],
        "mcp_servers": {"foo": {"command": "bar"}},
    }, indent=2))

    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)

    body = json.loads(fb_json.read_text())
    # Both agents present
    assert any("existing-agent.md" in p for p in body["agents"])
    assert any("test-agent.md" in p for p in body["agents"])
    # Unrelated keys preserved
    assert body["mcp_servers"] == {"foo": {"command": "bar"}}


def test_firebender_uninstall_removes_from_json_and_file(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    md = tmp_path / ".firebender" / "agents" / "test-agent.md"
    assert md.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not md.exists()
    body = json.loads((tmp_path / ".firebender" / "firebender.json").read_text())
    assert not any("test-agent.md" in p for p in body["agents"])


# ── Fail-loud regression tests (per Task 8 lessons) ──

def test_adapter_for_unknown_harness_raises():
    from agent_toolkit_cli.agent_adapters import config_file_folder
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        config_file_folder.adapter_for("nonexistent-harness-xyz")


def test_install_with_invalid_scope_raises(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    with pytest.raises(ValueError, match="global.*project"):
        adapter.install("test", fake_content, scope="globall", home=tmp_path)


# ── Regression tests for code-quality review findings ──

def test_dexto_yml_is_parseable_yaml_with_multiline_body(tmp_path):
    """Regression: an earlier emitter used `source: |\\n  {text}` which only
    indented the first line of a multi-line body — every subsequent line
    started at column 0 and broke the YAML block-scalar contract. Verify
    the emitted .yml parses cleanly with a strict YAML loader."""
    import yaml  # pyyaml is a project dep
    content = tmp_path / "multi.md"
    content.write_text(
        "---\nname: multi-test\n---\n\n"
        "Line one.\nLine two.\nLine three with body that has\nmultiple paragraphs.\n"
    )
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    yml_path = adapter.install("multi-test", content, scope="global", home=tmp_path)
    body = yaml.safe_load(yml_path.read_text())
    assert body["name"] == "multi-test"
    assert "Line one." in body["source"]
    assert "Line three" in body["source"]


def test_firebender_install_replaces_callable_false_with_true(tmp_path):
    """Regression: install means 'make spawnable' — an existing
    `callable: false` in the input frontmatter must be overwritten, not
    silently preserved (which would leave the agent un-spawnable)."""
    content = tmp_path / "disabled.md"
    content.write_text("---\nname: x\ncallable: false\n---\n\nBody.\n")
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    md = adapter.install("x", content, scope="global", home=tmp_path)
    text = md.read_text()
    assert "callable: true" in text
    assert "callable: false" not in text


def test_firebender_project_scope_stores_relative_path_in_json(tmp_path, fake_content):
    """Regression: firebender.json entries must be relative to .firebender/
    so the project can be checked in and relocated. Absolute paths would
    break referential integrity across machines."""
    project = tmp_path / "myproj"
    project.mkdir()
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="project", project=project)
    fb_json = project / ".firebender" / "firebender.json"
    body = json.loads(fb_json.read_text())
    # Every entry must be a relative path (no leading / and no project root)
    for p in body["agents"]:
        assert not p.startswith("/"), f"absolute path in firebender.json: {p}"
        assert str(project) not in p, f"project root leaked into entry: {p}"
        assert p.startswith("agents/"), f"expected 'agents/<slug>.md', got: {p}"


# ── #368: codex/firebender sentinel write + cleanup ──────────────────────

def test_codex_install_writes_sentinel_and_uninstall_cleans_it(tmp_path, fake_content):
    """#368: codex's per-slug .toml gets the .attk sidecar; uninstall removes it."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    sidecar = _sentinel_path(dest)
    assert sidecar.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not dest.exists()
    assert not sidecar.exists(), "orphaned .attk after codex uninstall"


def test_codex_reinstall_self_authorizes_via_sentinel(tmp_path, fake_content):
    """#368 (F3): a second install over our own .toml succeeds with
    overwrite=False — the sidecar authorizes it."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    # No lock, no overwrite flag — must not raise:
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)


def test_firebender_install_writes_sentinel_and_uninstall_cleans_it(tmp_path, fake_content):
    """#368: firebender's per-slug .md gets the .attk sidecar; uninstall removes it."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    sidecar = _sentinel_path(dest)
    assert sidecar.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not dest.exists()
    assert not sidecar.exists(), "orphaned .attk after firebender uninstall"


def test_codex_uninstall_cleans_orphan_sidecar(tmp_path, fake_content):
    """#368 review F3: the per-slug file deleted out-of-band must not strand
    its sidecar — an orphan .attk would authorize a future silent clobber."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    dest.unlink()  # user removes the projection by hand
    assert _sentinel_path(dest).exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not _sentinel_path(dest).exists(), "orphan sidecar survived uninstall"


def test_cff_uninstall_accepts_canonical_content_kwarg(tmp_path, fake_content):
    """#368 Protocol uniformity: all four cff adapters tolerate the kwarg
    (and ignore it — their removal semantics are out of scope)."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    for harness in ("aider-desk", "codex", "dexto", "firebender"):
        adapter = config_file_folder.adapter_for(harness)
        adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
        result = adapter.uninstall(
            "test-agent", scope="global", home=tmp_path,
            canonical_content=fake_content,
        )
        assert result is None


# ---------------------------------------------------------------------------
# #373: guarded canonical reads — InstallError, never a raw traceback
# ---------------------------------------------------------------------------

CFF_HARNESSES = ["aider-desk", "codex", "dexto", "firebender"]


@pytest.mark.parametrize("harness", CFF_HARNESSES)
def test_install_missing_canonical_raises_install_error(harness, tmp_path):
    """#373: missing canonical → InstallError (translate F8 parity), not
    FileNotFoundError. firebender/codex are catalog-disabled, so construct
    the adapter directly."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for(harness)
    missing = tmp_path / "canonical" / "test-agent.md"
    with pytest.raises(InstallError, match="canonical content file missing"):
        adapter.install("test-agent", missing, scope="global", home=tmp_path)


@pytest.mark.parametrize("harness", CFF_HARNESSES)
def test_install_non_utf8_canonical_raises_install_error(harness, tmp_path):
    """#373: non-UTF8 canonical → InstallError, not UnicodeDecodeError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for(harness)
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True)
    content.write_bytes(b"\xff\xfe invalid utf8")
    with pytest.raises(InstallError):
        adapter.install("test-agent", content, scope="global", home=tmp_path)


def test_firebender_install_corrupt_registry_raises_install_error(
    tmp_path, fake_content
):
    """#373 (gap 4): corrupt firebender.json at install → InstallError,
    not a raw JSONDecodeError traceback."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    fb_dir = tmp_path / ".firebender"
    fb_dir.mkdir()
    (fb_dir / "firebender.json").write_text("{not json")
    with pytest.raises(InstallError, match="firebender"):
        adapter.install("test-agent", fake_content, scope="global", home=tmp_path)


def test_firebender_uninstall_corrupt_registry_raises_install_error(
    tmp_path, fake_content
):
    """#373 (gap 4): corrupt firebender.json at uninstall → InstallError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    (tmp_path / ".firebender" / "firebender.json").write_text("{not json")
    with pytest.raises(InstallError, match="firebender"):
        adapter.uninstall("test-agent", scope="global", home=tmp_path)


def test_codex_uninstall_corrupt_config_raises_install_error(
    tmp_path, fake_content
):
    """#373 (gap 4): unreadable config.toml at codex uninstall → InstallError
    (mirrors the firebender uninstall coverage)."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    # Make the read raise: read_text on a non-UTF8 config.toml.
    (tmp_path / ".codex" / "config.toml").write_bytes(b"\xff\xfe not utf8")
    with pytest.raises(InstallError, match="codex"):
        adapter.uninstall("test-agent", scope="global", home=tmp_path)

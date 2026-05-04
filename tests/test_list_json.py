"""Tests for the `_list-json` internal subcommand (consumed by `list --format=json`)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit.commands._list_json import list_json


def _seed(tmp: Path) -> None:
    (tmp / "schemas").mkdir()
    (tmp / "skills" / "alpha").mkdir(parents=True)
    (tmp / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha skill.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
    )


def test_unsupported_status_for_non_declared_harness(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    cells = [c for a in doc["assets"] if a["slug"] == "alpha" for c in a["cells"]]
    codex_cells = [c for c in cells if c["harness"] == "codex"]
    assert codex_cells, cells
    assert all(c["status"] == "unsupported" for c in codex_cells)


def test_linked_status_when_symlink_exists(tmp_path, monkeypatch):
    _seed(tmp_path)
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    src = (tmp_path / "skills" / "alpha").resolve()
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(src)
    # allowlist
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    cells = [c for a in doc["assets"] if a["slug"] == "alpha" for c in a["cells"]]
    cl_user = next(c for c in cells if c["harness"] == "claude" and c["scope"] == "user")
    assert cl_user["status"] == "linked", cl_user
    assert cl_user["allowlisted"] is True
    # `target` is the raw os.readlink value (consistent with the `broken` case),
    # so consumers see one shape regardless of status.
    assert cl_user["target"] == os.readlink(str(link_path)), cl_user


def test_unlinked_status_when_no_symlink(tmp_path, monkeypatch):
    _seed(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    cells = [c for a in doc["assets"] if a["slug"] == "alpha" for c in a["cells"]]
    cl_user = next(c for c in cells if c["harness"] == "claude" and c["scope"] == "user")
    assert cl_user["status"] == "unlinked", cl_user
    assert cl_user["target"] is None
    assert cl_user["allowlisted"] is False


def test_broken_status_when_symlink_target_missing(tmp_path, monkeypatch):
    _seed(tmp_path)
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    # symlink pointing somewhere outside the repo, doesn't matter if it exists
    (home / ".claude" / "skills" / "alpha").symlink_to("/nonexistent/path/alpha")
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    cells = [c for a in doc["assets"] if a["slug"] == "alpha" for c in a["cells"]]
    cl_user = next(c for c in cells if c["harness"] == "claude" and c["scope"] == "user")
    assert cl_user["status"] == "broken", cl_user
    assert cl_user["target"] == "/nonexistent/path/alpha"


def test_top_level_toolkit_root_and_harnesses(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    # toolkit_root is the resolved argv path so callers comparing against
    # their own resolved path see a stable value across platforms.
    assert doc["toolkit_root"] == str(tmp_path.resolve())
    assert doc["harnesses"] == ["claude", "codex", "opencode", "pi"]
    assert isinstance(doc["assets"], list)


def test_kind_filter_drops_other_kinds(tmp_path, monkeypatch):
    _seed(tmp_path)
    # Add an agent so we have something other than skill in the inventory
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "beta.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: beta\n"
        "  description: Beta agent.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path), "--kind", "skill"])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    kinds = {a["kind"] for a in doc["assets"]}
    assert kinds == {"skill"}, kinds


def test_mcp_kind_included_without_filter(tmp_path, monkeypatch):
    """MCPs appear in JSON output alongside other kinds (no longer excluded)."""
    _seed(tmp_path)
    # Walker discovers MCPs via config.json; frontmatter is read from sibling README.md.
    (tmp_path / "mcps" / "gamma").mkdir(parents=True)
    (tmp_path / "mcps" / "gamma" / "config.json").write_text(
        '{"type":"stdio","command":"npx"}\n'
    )
    (tmp_path / "mcps" / "gamma" / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: gamma\n"
        "  description: Gamma mcp.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    kinds = {a["kind"] for a in doc["assets"]}
    assert "mcp" in kinds, kinds


def test_asset_path_is_absolute(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--toolkit-repo", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    alpha = next(a for a in doc["assets"] if a["slug"] == "alpha")
    assert Path(alpha["path"]).is_absolute()


def test_list_json_includes_mcps(tmp_path, monkeypatch):
    """MCPs appear as kind=mcp entries in JSON output with status=unsupported per cell."""
    import json
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit),
         "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    mcps = [a for a in data["assets"] if a["kind"] == "mcp"]
    assert len(mcps) == 1
    assert mcps[0]["slug"] == "context7"
    # All cells should be unsupported (no adapter yet) but allowlisted on project
    project_claude = next(
        c for c in mcps[0]["cells"]
        if c["harness"] == "claude" and c["scope"] == "project"
    )
    assert project_claude["status"] == "unsupported"
    assert project_claude["allowlisted"] is True

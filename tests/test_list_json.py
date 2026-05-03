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
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
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
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
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
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
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
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    cells = [c for a in doc["assets"] if a["slug"] == "alpha" for c in a["cells"]]
    cl_user = next(c for c in cells if c["harness"] == "claude" and c["scope"] == "user")
    assert cl_user["status"] == "broken", cl_user
    assert cl_user["target"] == "/nonexistent/path/alpha"


def test_top_level_repo_root_and_harnesses(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    # repo_root is the verbatim argv path (not resolved) so callers can compare
    # against what they passed.
    assert doc["repo_root"] == str(tmp_path)
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
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path), "--kind", "skill"])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    kinds = {a["kind"] for a in doc["assets"]}
    assert kinds == {"skill"}, kinds


def test_mcp_kind_excluded_even_without_filter(tmp_path, monkeypatch):
    _seed(tmp_path)
    # Add an mcp asset — should be excluded from output
    (tmp_path / "mcps" / "gamma").mkdir(parents=True)
    (tmp_path / "mcps" / "gamma" / "mcp.json").write_text(
        json.dumps({
            "agent_toolkit": {
                "apiVersion": "agent-toolkit/v1alpha1",
                "metadata": {
                    "name": "gamma",
                    "description": "Gamma mcp.",
                    "lifecycle": "stable",
                },
                "spec": {
                    "origin": "first-party",
                    "vendored_via": "none",
                    "harnesses": ["claude"],
                },
            }
        })
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    kinds = {a["kind"] for a in doc["assets"]}
    assert "mcp" not in kinds, kinds


def test_asset_path_is_absolute(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    runner = CliRunner()
    res = runner.invoke(list_json, ["--repo-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    alpha = next(a for a in doc["assets"] if a["slug"] == "alpha")
    assert Path(alpha["path"]).is_absolute()

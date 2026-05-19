"""Tests for the `_list-json` internal subcommand (consumed by `list --format=json`)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.commands._list_json import list_json, user_scope_covered


def _seed(tmp: Path) -> None:
    (tmp / "schemas").mkdir()
    (tmp / "skills" / "alpha").mkdir(parents=True)
    (tmp / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
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
    assert doc["harnesses"] == ["claude", "codex", "opencode", "gemini", "pi"]
    assert isinstance(doc["assets"], list)


def test_kind_filter_drops_other_kinds(tmp_path, monkeypatch):
    _seed(tmp_path)
    # Add an agent so we have something other than skill in the inventory
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "beta.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
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
        "apiVersion: agent-toolkit/v1alpha2\n"
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
    """MCPs appear as kind=mcp entries in JSON output with status=unsupported per cell.

    Pi remains UnimplementedAdapter (Pi has no MCP support by design); using pi
    here keeps the unsupported-cell semantics stable across adapter additions.
    """
    import json
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - pi\n---\n"
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
    project_pi = next(
        c for c in mcps[0]["cells"]
        if c["harness"] == "pi" and c["scope"] == "project"
    )
    assert project_pi["status"] == "unsupported"
    assert project_pi["allowlisted"] is True


# ---------------------------------------------------------------------------
# MCP four-glyph status tests (codex adapter)
# ---------------------------------------------------------------------------

def _seed_mcp_toolkit(toolkit: Path, harnesses: list[str], *, has_args: bool = True) -> None:
    """Set up toolkit dir with context7 MCP for the given harnesses."""
    (toolkit / "schemas").mkdir(parents=True, exist_ok=True)
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    config = '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}' if has_args else '{"type":"stdio","command":"npx"}'
    (mcp_dir / "config.json").write_text(config + "\n")
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n"
        f"{harness_lines}\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )


def _seed_hook_toolkit(toolkit: Path, harnesses: list[str]) -> None:
    """Set up toolkit dir with demo-hook for the given harnesses."""
    import shutil
    (toolkit / "schemas").mkdir(parents=True, exist_ok=True)
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")

    # Copy the demo hook fixture to the toolkit.
    fixture_src = Path(__file__).resolve().parent / "_fixtures" / "hook_assets" / "codex-demo"
    hook_dir = toolkit / "hooks" / "demo-hook"
    hook_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_src, hook_dir, dirs_exist_ok=True)

    # Create the README.md with frontmatter.
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (hook_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: demo-hook\n  description: Demo hook.\n  kind: hook\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n"
        f"{harness_lines}\n"
        "  hook:\n    events: [PreToolUse]\n    command: check.sh\n    matcher: \"^Bash$\"\n    timeout: 10\n---\n"
    )


def test_list_json_mcp_codex_linked_matches_after_link(tmp_path, monkeypatch):
    """After linking, the codex/user cell reports linked-matches with the target path."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    _seed_mcp_toolkit(toolkit, ["codex"])

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    # Link to user scope
    rl = runner.invoke(
        main,
        ["link", "user", "codex", "mcp:context7",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert rl.exit_code == 0, rl.output

    # Read state via JSON
    rl2 = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert rl2.exit_code == 0, rl2.output
    data = json.loads(rl2.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "linked-matches"
    target = home / ".codex" / "config.toml"
    assert user_codex["target"] == str(target)
    assert user_codex["allowlisted"] is True


def test_list_json_mcp_codex_unlinked_allowlisted(tmp_path, monkeypatch):
    """Allow-listed but not installed → unlinked-allowlisted, target=None."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    # User-scope allow-list lists context7 but nothing is installed.
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    toolkit = tmp_path / "toolkit"
    _seed_mcp_toolkit(toolkit, ["codex"])

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "unlinked-allowlisted"
    assert user_codex["target"] is None


def test_list_json_mcp_codex_installed_not_allowlisted(tmp_path, monkeypatch):
    """Hand-rolled entry in codex config + absent from allow-list → installed-not-allowlisted."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    target = home / ".codex" / "config.toml"
    target.write_text(
        "[mcp_servers.context7]\ncommand = \"node\"\nargs = [\"hand-rolled.js\"]\n"
    )
    # No allow-list at all.

    toolkit = tmp_path / "toolkit"
    _seed_mcp_toolkit(toolkit, ["codex"])

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "installed-not-allowlisted"
    assert user_codex["target"] == str(target)
    assert user_codex["allowlisted"] is False


def test_list_json_mcp_codex_linked_drifted_after_handedit(tmp_path, monkeypatch):
    """Allow-listed + installed + structural drift → linked-drifted."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    _seed_mcp_toolkit(toolkit, ["codex"])

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    # Link first.
    rl = runner.invoke(
        main,
        ["link", "user", "codex", "mcp:context7",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert rl.exit_code == 0, rl.output

    # Hand-edit the installed entry to introduce drift.
    target = home / ".codex" / "config.toml"
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)

    # Re-read state.
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "linked-drifted"


def test_list_json_mcp_claude_unsupported(tmp_path, monkeypatch):
    """Cells for harnesses with UnimplementedAdapter still report 'unsupported'."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    _seed_mcp_toolkit(toolkit, ["claude", "codex"])

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_claude = next(c for c in mcp["cells"]
                       if c["harness"] == "claude" and c["scope"] == "user")
    assert user_claude["status"] == "unsupported"


# ---------------------------------------------------------------------------
# Hook four-glyph status tests (codex adapter)
# ---------------------------------------------------------------------------


def test_list_json_hook_codex_linked_drifted_after_handedit(tmp_path, monkeypatch):
    """Allow-listed + installed + config/script drift → linked-drifted."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    _seed_hook_toolkit(toolkit, ["codex"])

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    # Link first.
    rl = runner.invoke(
        main,
        ["link", "user", "codex", "hook:demo-hook",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert rl.exit_code == 0, rl.output

    # Hand-edit the config to introduce drift (e.g., change the timeout).
    target = home / ".codex" / "config.toml"
    text = target.read_text()
    # Mutate the config to introduce drift: change timeout from 10 to 20.
    modified_text = text.replace("timeout = 10", "timeout = 20")
    target.write_text(modified_text)

    # Re-read state.
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [hook] = [a for a in data["assets"] if a["kind"] == "hook"]
    user_codex = next(c for c in hook["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "linked-drifted"


def test_list_json_hook_codex_installed_not_allowlisted(tmp_path, monkeypatch):
    """Hand-installed hook + absent from allow-list → installed-not-allowlisted."""
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    _seed_hook_toolkit(toolkit, ["codex"])

    # Manually install a hook (script under agent-toolkit-hooks and config entry, without allowlisting).
    scripts_dir = home / ".codex" / "agent-toolkit-hooks" / "demo-hook"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "check.sh").write_text("#!/bin/bash\necho installed\n")

    target = home / ".codex" / "config.toml"
    target.write_text(
        "[[hooks.PreToolUse]]\n"
        "name = \"demo-hook\"\n"
        "command = \"agent-toolkit-hooks/demo-hook/check.sh\"\n"
        "matcher = \"^Bash$\"\n"
        "timeout = 10\n"
    )

    # No allow-list at all.

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    [hook] = [a for a in data["assets"] if a["kind"] == "hook"]
    user_codex = next(c for c in hook["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "installed-not-allowlisted"
    assert user_codex["target"] == str(target)
    assert user_codex["allowlisted"] is False


def test_cell_status_pi_agent_project_scope_unlinked_when_no_symlink(tmp_path):
    """#75: pi/agent at project scope is now SUPPORTED (dual-write to
    `.pi/agents/` AND `.agents/`). With no symlink present in either slot,
    the cell reports 'unlinked' (not 'unsupported')."""
    from agent_toolkit_cli.commands._list_json import _cell_status

    status, target = _cell_status(
        harness="pi",
        kind="agent",
        slug="any-slug",
        scope="project",
        expected_src=tmp_path / "ignored",
        toolkit_root_resolved=tmp_path / "ignored-toolkit",
        project_root=tmp_path,
    )
    assert status == "unlinked"
    assert target is None


_LINKED_STATUSES = ("linked", "linked-matches", "linked-drifted")
_NOT_LINKED_STATUSES = (
    "unlinked", "unsupported", "broken",
    "unlinked-allowlisted", "installed-not-allowlisted",
)


def _inv(*cells):
    """Build a minimal inventory dict containing one asset with given cells."""
    return {
        "assets": [
            {
                "slug": "foo",
                "kind": "skill",
                "cells": list(cells),
            }
        ]
    }


@pytest.mark.parametrize("status", _LINKED_STATUSES)
def test_user_scope_covered_true_for_linked_user_cell(status):
    inv = _inv({"harness": "claude", "scope": "user", "status": status})
    assert user_scope_covered(inv, slug="foo", harness="claude") is True


@pytest.mark.parametrize("status", _NOT_LINKED_STATUSES)
def test_user_scope_covered_false_for_non_linked_user_cell(status):
    inv = _inv({"harness": "claude", "scope": "user", "status": status})
    assert user_scope_covered(inv, slug="foo", harness="claude") is False


def test_user_scope_covered_ignores_project_scope_cells():
    inv = _inv(
        {"harness": "claude", "scope": "project", "status": "linked"},
        {"harness": "claude", "scope": "user", "status": "unlinked"},
    )
    assert user_scope_covered(inv, slug="foo", harness="claude") is False


def test_user_scope_covered_per_harness():
    inv = _inv(
        {"harness": "claude", "scope": "user", "status": "linked"},
        {"harness": "codex",  "scope": "user", "status": "unlinked"},
    )
    assert user_scope_covered(inv, slug="foo", harness="claude") is True
    assert user_scope_covered(inv, slug="foo", harness="codex") is False


def test_user_scope_covered_unknown_slug_returns_false():
    inv = _inv({"harness": "claude", "scope": "user", "status": "linked"})
    assert user_scope_covered(inv, slug="missing", harness="claude") is False


def test_user_scope_covered_unknown_harness_returns_false():
    inv = _inv({"harness": "claude", "scope": "user", "status": "linked"})
    assert user_scope_covered(inv, slug="foo", harness="opencode") is False

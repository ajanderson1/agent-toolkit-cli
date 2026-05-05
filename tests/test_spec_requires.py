"""Tests for spec.requires enforcement in the linker (Phase 2 task #8).

Covers:
  - parse_requires_entries and RequiresUnsatisfied unit tests
  - AssetRecord.requires field populated from frontmatter
  - project_from_file enforcement (enforce_requires=True)
  - CLI integration: bare, per-asset, --all, --plan modes
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SKILL_FM = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""

SKILL_FM_WITH_REQUIRES = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
  requires:
{requires_lines}
---
"""

AGENT_FM_WITH_REQUIRES = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} agent.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
  requires:
{requires_lines}
---
"""


def _make_toolkit(tmp_path: Path) -> Path:
    root = tmp_path / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    return root


def _seed_skill(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FM.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


def _seed_skill_with_requires(
    toolkit_root: Path,
    slug: str,
    harnesses: list[str],
    requires: dict[str, list[str]],
) -> Path:
    """Seed a skill with spec.requires entries."""
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    requires_lines = ""
    for harness, peers in requires.items():
        requires_lines += f"    {harness}:\n"
        for peer in peers:
            requires_lines += f"      - {peer}\n"
    (skill_dir / "SKILL.md").write_text(
        SKILL_FM_WITH_REQUIRES.format(
            slug=slug,
            harness_lines=harness_lines,
            requires_lines=requires_lines,
        )
    )
    return skill_dir


def _seed_agent_with_requires(
    toolkit_root: Path,
    slug: str,
    harnesses: list[str],
    requires: dict[str, list[str]],
) -> Path:
    """Seed an agent with spec.requires entries."""
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    requires_lines = ""
    for harness, peers in requires.items():
        requires_lines += f"    {harness}:\n"
        for peer in peers:
            requires_lines += f"      - {peer}\n"
    agent_file = agents_dir / f"{slug}.md"
    agent_file.write_text(
        AGENT_FM_WITH_REQUIRES.format(
            slug=slug,
            harness_lines=harness_lines,
            requires_lines=requires_lines,
        )
    )
    return agent_file


def _seed_pi_extension(toolkit_root: Path, slug: str) -> Path:
    """Seed a pi-extension asset."""
    ext_dir = toolkit_root / "extensions" / slug
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "extension.meta.yaml").write_text(
        f"apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} pi extension.\n"
        f"  lifecycle: stable\n"
        f"spec:\n"
        f"  origin: first-party\n"
        f"  vendored_via: none\n"
        f"  harnesses:\n"
        f"    - pi\n"
    )
    (ext_dir / "package.json").write_text(
        '{"name": "' + slug + '", "version": "1.0.0", "type": "module"}\n'
    )
    (ext_dir / "index.ts").write_text("export default function (pi: any) {}\n")
    return ext_dir


# ---------------------------------------------------------------------------
# Unit tests: parse_requires_entries
# ---------------------------------------------------------------------------


def test_parse_requires_entries_normal():
    from agent_toolkit._requires import parse_requires_entries

    result = parse_requires_entries(["pi-extension:pi-subagents", "skill:foo"])
    assert result == [("pi-extension", "pi-subagents"), ("skill", "foo")]


def test_parse_requires_entries_empty():
    from agent_toolkit._requires import parse_requires_entries

    assert parse_requires_entries([]) == []


def test_parse_requires_entries_malformed_no_colon():
    from agent_toolkit._requires import parse_requires_entries

    result = parse_requires_entries(["no-colon-here"])
    assert result == [("", "no-colon-here")]


def test_parse_requires_entries_first_colon_only():
    """Extra colons in slug should not cause problems."""
    from agent_toolkit._requires import parse_requires_entries

    result = parse_requires_entries(["skill:foo"])
    assert result == [("skill", "foo")]


# ---------------------------------------------------------------------------
# Unit tests: RequiresUnsatisfied
# ---------------------------------------------------------------------------


def test_requires_unsatisfied_carries_fields():
    from agent_toolkit._requires import RequiresUnsatisfied

    exc = RequiresUnsatisfied(
        asset_slug="ceo",
        asset_kind="agent",
        harness="pi",
        missing=[("pi-extension", "pi-subagents")],
    )
    assert exc.asset_slug == "ceo"
    assert exc.asset_kind == "agent"
    assert exc.harness == "pi"
    assert exc.missing == [("pi-extension", "pi-subagents")]
    assert "ceo" in str(exc)
    assert "pi-extension:pi-subagents" in str(exc)


# ---------------------------------------------------------------------------
# Unit tests: AssetRecord.requires field
# ---------------------------------------------------------------------------


def test_load_asset_record_no_requires(tmp_path):
    """Asset without spec.requires → requires == {}."""
    from agent_toolkit.walker import discover_assets, load_asset_record

    _seed_skill(tmp_path, "alpha", ["claude"])
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "skill"]
    record = load_asset_record(asset)
    assert record.requires == {}


def test_load_asset_record_with_requires(tmp_path):
    """Asset with spec.requires → requires populated."""
    from agent_toolkit.walker import discover_assets, load_asset_record

    _seed_skill_with_requires(
        tmp_path,
        "dependent",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "skill"]
    record = load_asset_record(asset)
    assert record.requires == {"pi": ["pi-extension:pi-subagents"]}


def test_load_asset_record_multi_harness_requires(tmp_path):
    """spec.requires with multiple harnesses is fully preserved."""
    from agent_toolkit.walker import discover_assets, load_asset_record

    _seed_skill_with_requires(
        tmp_path,
        "multi",
        ["claude", "pi"],
        {
            "claude": ["skill:helper"],
            "pi": ["pi-extension:pi-subagents"],
        },
    )
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "skill"]
    record = load_asset_record(asset)
    assert record.requires["claude"] == ["skill:helper"]
    assert record.requires["pi"] == ["pi-extension:pi-subagents"]


# ---------------------------------------------------------------------------
# Unit tests: project_from_file with enforce_requires
# ---------------------------------------------------------------------------


def test_project_from_file_no_requires_projects_fine(tmp_path, monkeypatch):
    """Asset without spec.requires → projects without error."""
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill(toolkit_root, "alpha", ["claude"])

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("skills:\n  - alpha\n")

    counters = LinkCounters()
    project_from_file(
        scope="user",
        harness="claude",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=io.StringIO(),
        enforce_requires=True,
    )
    assert counters.created == 1


def test_project_from_file_requires_satisfied_projects_fine(tmp_path, monkeypatch):
    """Asset with spec.requires peer in allowlist → projects without error."""
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)

    # dependent skill requires skill:helper on claude
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["claude"],
        {"claude": ["skill:helper"]},
    )
    _seed_skill(toolkit_root, "helper", ["claude"])

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    # Both dependent and helper are in the allowlist.
    allowlist.write_text("skills:\n  - dependent\n  - helper\n")

    counters = LinkCounters()
    # Should not raise.
    project_from_file(
        scope="user",
        harness="claude",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=io.StringIO(),
        enforce_requires=True,
    )
    assert counters.created == 2


def test_project_from_file_requires_not_satisfied_raises(tmp_path, monkeypatch):
    """Asset with spec.requires peer NOT in allowlist → RequiresUnsatisfied raised."""
    from agent_toolkit._requires import RequiresUnsatisfied
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".pi" / "agent" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)

    _seed_skill_with_requires(
        toolkit_root,
        "needs-ext",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    # The required pi-extension is NOT in the allowlist.
    allowlist.write_text("skills:\n  - needs-ext\n")

    counters = LinkCounters()
    with pytest.raises(RequiresUnsatisfied) as exc_info:
        project_from_file(
            scope="user",
            harness="pi",
            toolkit_root=toolkit_root,
            project_root=project_root,
            allowlist_path=allowlist,
            dry_run=False,
            counters=counters,
            stdout=io.StringIO(),
            enforce_requires=True,
        )
    exc = exc_info.value
    assert exc.asset_slug == "needs-ext"
    assert exc.asset_kind == "skill"
    assert exc.harness == "pi"
    assert ("pi-extension", "pi-subagents") in exc.missing


def test_project_from_file_requires_not_enforced_by_default(tmp_path, monkeypatch):
    """enforce_requires defaults to False → missing peer does not block projection."""
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".pi" / "agent" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)

    _seed_skill_with_requires(
        toolkit_root,
        "needs-ext",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("skills:\n  - needs-ext\n")

    counters = LinkCounters()
    # No enforce_requires=True → must not raise.
    project_from_file(
        scope="user",
        harness="pi",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=io.StringIO(),
    )
    assert counters.created == 1


# ---------------------------------------------------------------------------
# Integration tests: multi-harness requires — only the relevant harness is checked
# ---------------------------------------------------------------------------


def test_requires_only_relevant_harness_checked(tmp_path, monkeypatch):
    """spec.requires with multiple harnesses — projecting for claude only checks claude's peers."""
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)

    # Asset requires skill:helper on claude and pi-extension:pie on pi.
    # pi-extension:pie is NOT in the allowlist, but we're projecting for claude.
    _seed_skill_with_requires(
        toolkit_root,
        "multi",
        ["claude", "pi"],
        {
            "claude": ["skill:helper"],
            "pi": ["pi-extension:pie"],
        },
    )
    _seed_skill(toolkit_root, "helper", ["claude"])

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    # helper is in the allowlist; pi-extension:pie is NOT.
    allowlist.write_text("skills:\n  - multi\n  - helper\n")

    counters = LinkCounters()
    # Projecting for claude — only claude's requires are checked.
    # pi-extension:pie is not in the allowlist but not checked here.
    project_from_file(
        scope="user",
        harness="claude",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=io.StringIO(),
        enforce_requires=True,
    )
    assert counters.created == 2  # multi + helper


def test_requires_pi_harness_fails_when_pi_peer_missing(tmp_path, monkeypatch):
    """Projecting for pi with missing pi peer → RequiresUnsatisfied."""
    from agent_toolkit._requires import RequiresUnsatisfied
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".pi" / "agent" / "skills").mkdir(parents=True)
    toolkit_root = _make_toolkit(tmp_path)

    _seed_skill_with_requires(
        toolkit_root,
        "multi",
        ["claude", "pi"],
        {
            "claude": ["skill:helper"],
            "pi": ["pi-extension:pie"],
        },
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    # pi-extension:pie is NOT in the allowlist.
    allowlist.write_text("skills:\n  - multi\n")

    counters = LinkCounters()
    with pytest.raises(RequiresUnsatisfied) as exc_info:
        project_from_file(
            scope="user",
            harness="pi",
            toolkit_root=toolkit_root,
            project_root=project_root,
            allowlist_path=allowlist,
            dry_run=False,
            counters=counters,
            stdout=io.StringIO(),
            enforce_requires=True,
        )
    exc = exc_info.value
    assert exc.asset_slug == "multi"
    assert ("pi-extension", "pie") in exc.missing


# ---------------------------------------------------------------------------
# CLI integration tests (CliRunner)
# ---------------------------------------------------------------------------


def test_cli_link_bare_requires_satisfied(tmp_path, monkeypatch):
    """CLI bare-link with requires peer in allowlist → exit 0."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["claude"],
        {"claude": ["skill:helper"]},
    )
    _seed_skill(toolkit_root, "helper", ["claude"])

    (home / ".agent-toolkit.yaml").write_text("skills:\n  - dependent\n  - helper\n")
    (home / ".claude").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "claude"],
    )
    assert result.exit_code == 0, (result.output, getattr(result, "stderr", ""))
    assert (home / ".claude" / "skills" / "dependent").is_symlink()
    assert (home / ".claude" / "skills" / "helper").is_symlink()


def test_cli_link_bare_requires_missing_exits_2(tmp_path, monkeypatch):
    """CLI bare-link with requires peer missing → exit 2, structured stderr."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )

    (home / ".agent-toolkit.yaml").write_text("skills:\n  - dependent\n")
    (home / ".pi").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "pi"],
    )
    assert result.exit_code == 2
    assert "pi-extension:pi-subagents" in result.stderr
    assert "dependent" in result.stderr


def test_cli_link_per_asset_requires_missing_exits_2(tmp_path, monkeypatch):
    """CLI per-asset link with missing requires peer → exit 2."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )
    # pi-extension is NOT seeded or in any allowlist

    (home / ".pi").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "pi", "skill:dependent"],
    )
    assert result.exit_code == 2
    assert "pi-extension:pi-subagents" in result.stderr


def test_cli_link_per_asset_requires_satisfied_exits_0(tmp_path, monkeypatch):
    """CLI per-asset link with satisfied requires → exit 0."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["claude"],
        {"claude": ["skill:helper"]},
    )
    _seed_skill(toolkit_root, "helper", ["claude"])

    # Pre-populate allowlist with helper already there
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - helper\n")
    (home / ".claude").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "claude", "skill:dependent"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)


def test_cli_link_all_requires_missing_exits_2(tmp_path, monkeypatch):
    """CLI --all link with missing requires peer → exit 2."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )
    # pi-extension is NOT seeded — so --all won't add it to the snapshot.

    (home / ".pi").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "pi", "--all", "-y"],
    )
    assert result.exit_code == 2
    assert "pi-extension:pi-subagents" in result.stderr


def test_cli_link_plan_requires_missing_reports_error(tmp_path, monkeypatch):
    """CLI --plan link with missing requires peer → failure recorded in plan summary."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_skill_with_requires(
        toolkit_root,
        "dependent",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )

    (home / ".pi").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "pi", "--plan", "-"],
        input="skill:dependent\n",
    )
    # Plan mode collects errors and exits 1 when any entry fails.
    assert result.exit_code == 1
    combined = result.output + result.stderr
    assert "pi-extension:pi-subagents" in combined


# ---------------------------------------------------------------------------
# Error message content
# ---------------------------------------------------------------------------


def test_requires_error_names_missing_asset(tmp_path, monkeypatch):
    """The structured stderr message names the missing peer explicitly."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)

    toolkit_root = _make_toolkit(tmp_path)
    _seed_agent_with_requires(
        toolkit_root,
        "ceo",
        ["pi"],
        {"pi": ["pi-extension:pi-subagents"]},
    )

    (home / ".agent-toolkit.yaml").write_text("agents:\n  - ceo\n")
    (home / ".pi").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "pi"],
    )
    assert result.exit_code == 2
    # The error names the asset that has the dependency and the missing peer.
    assert "agent:ceo" in result.stderr
    assert "pi-extension:pi-subagents" in result.stderr
    assert "pi" in result.stderr

"""Standard agents projection adapter (#361): one .claude/agents/<slug>.md
slot covering every harness that natively reads that dir."""
from pathlib import Path

import pytest

from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError
from agent_toolkit_cli.agent_adapters.standard import (
    STANDARD_AGENT_READERS,
    adapter_for,
    agents_standard_covered,
)


def _canonical(tmp_path: Path) -> Path:
    c = tmp_path / "canonical"
    c.mkdir()
    f = c / "demo.md"
    f.write_text("---\nname: demo\ndescription: d\n---\nbody\n")
    return f


def test_readers_table_shape():
    assert set(STANDARD_AGENT_READERS) == {"global", "project"}
    for scope, names in STANDARD_AGENT_READERS.items():
        assert "claude-code" in names
        # cursor reads .claude/agents at BOTH scopes (cursor.com/docs/subagents,
        # re-verified 2026-06-10 — Task 0 delta vs the original spec sets).
        assert "cursor" in names
    # devin reads .claude/agents at project scope only (matrix evidence).
    assert "devin" not in STANDARD_AGENT_READERS["global"]
    assert "devin" in STANDARD_AGENT_READERS["project"]


def test_templates_match_claude_code_cell():
    """Template-drift guard (code review): the standard slot IS the claude-code
    symlink cell's destination — the whole dedupe-by-destination design assumes
    the two template tables stay identical."""
    from agent_toolkit_cli.agent_adapters import standard, symlink
    assert standard._TEMPLATES == symlink.CELLS["claude-code"]


def test_readers_are_real_catalog_harnesses():
    """Catalog drift guard (review finding): a renamed/removed harness in the
    table would otherwise silently regain a default install while the panel
    lists a ghost name."""
    from agent_toolkit_cli.skill_agents import AGENTS
    all_readers = frozenset().union(*STANDARD_AGENT_READERS.values())
    assert all_readers <= set(AGENTS)


def test_agents_standard_covered_accessor():
    assert agents_standard_covered("global") == STANDARD_AGENT_READERS["global"]
    with pytest.raises(KeyError):
        agents_standard_covered("nope")


def test_destination_is_claude_agents_slot(tmp_path):
    a = adapter_for()
    assert a.destination("demo", scope="global", home=tmp_path) == \
        tmp_path / ".claude" / "agents" / "demo.md"
    assert a.destination("demo", scope="project", project=tmp_path) == \
        tmp_path / ".claude" / "agents" / "demo.md"


def test_install_uninstall_roundtrip(tmp_path):
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    content = _canonical(tmp_path)
    a = adapter_for()
    out = a.install("demo", content, scope="global", home=tmp_path)
    assert out.read_text() == content.read_text()
    a.uninstall("demo", scope="global", home=tmp_path)
    assert not out.exists()
    assert not _sentinel_path(out).exists()  # sentinel cleaned up on detach


def test_adopt_if_identical(tmp_path):
    """A pre-existing byte-identical file (e.g. a prior claude-code install)
    is adopted silently — no conflict, sentinel written. (Adoption is safe:
    deleting an adopted file later loses nothing — its content is the
    canonical's by definition.)"""
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(content.read_text())  # identical, no sentinel
    a = adapter_for()
    out = a.install("demo", content, scope="global", home=tmp_path)
    assert out == dest
    assert _sentinel_path(dest).exists()  # contract: adoption claims ownership


@pytest.mark.parametrize("slug", ["../evil", "..\\evil", ".", "..", ""])
def test_destination_rejects_traversal_slugs(tmp_path, slug):
    """Defense for the new high-value target: a slug containing path
    separators (either flavor), dot-dirs, or nothing at all must not
    escape — or silently mangle — the agents dir."""
    a = adapter_for()
    with pytest.raises(ValueError):
        a.destination(slug, scope="global", home=tmp_path)


def test_foreign_different_content_conflicts(tmp_path):
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    with pytest.raises(AgentProjectionConflictError):
        a.install("demo", content, scope="global", home=tmp_path)


def test_facade_overwrite_flag_does_not_bypass_guard(tmp_path):
    """PM review (MAJOR 2): every CLI-installable slug has a global lock
    entry, so the facade passes overwrite=True — that must NOT authorize
    clobbering a sentinel-less user file in the shared dir."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    with pytest.raises(AgentProjectionConflictError):
        a.install("demo", content, scope="global", home=tmp_path, overwrite=True)


def test_uninstall_leaves_unowned_file(tmp_path, capsys):
    """PM review (MINOR 4): uninstall must not unlink a sentinel-less,
    content-divergent file — over-listing is NOT harmless in a shared dir."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    a.uninstall("demo", scope="global", home=tmp_path, canonical_content=content)
    assert dest.exists()  # left in place
    assert "not managed by this tool" in capsys.readouterr().err


def test_reinstall_refreshes_own_slot(tmp_path):
    """Re-install idempotency: the sentinel written by a prior install
    authorizes refreshing a now-divergent slot (canonical moved on), without
    any facade overwrite flag."""
    content = _canonical(tmp_path)
    a = adapter_for()
    out = a.install("demo", content, scope="global", home=tmp_path)
    content.write_text("---\nname: demo\ndescription: d2\n---\nnew body\n")
    out2 = a.install("demo", content, scope="global", home=tmp_path)
    assert out2 == out
    assert out.read_text() == content.read_text()


def test_uninstall_removes_sentinelless_content_match(tmp_path):
    """Pre-#361 claude-code installs wrote no sentinel; content matching the
    canonical is sufficient ownership evidence for detach."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(content.read_text())
    a = adapter_for()
    a.uninstall("demo", scope="global", home=tmp_path, canonical_content=content)
    assert not dest.exists()

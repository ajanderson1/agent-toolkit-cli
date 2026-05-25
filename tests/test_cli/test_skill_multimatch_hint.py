"""Error guidance for `_resolve_skill_name_to_subpath`.

When `--skill <name>` matches more than one SKILL.md (e.g. a repo that ships a
standalone copy under skills/ and a plugin-bundled copy under plugins/), the
error must not be a dead end: it should hand the user a copy-pasteable command
that addresses each match by explicit subpath.
"""
import click
import pytest

from agent_toolkit_cli.commands.skill import _resolve_skill_name_to_subpath

_SKILL_MD = "---\nname: {name}\ndescription: x\n---\nbody\n"


def _write_skill(parent, subpath, name):
    d = parent / subpath
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(_SKILL_MD.format(name=name))


def test_single_match_returns_subpath(tmp_path):
    _write_skill(tmp_path, "skills/youtube-transcript", "youtube-transcript")
    assert (
        _resolve_skill_name_to_subpath(tmp_path, "youtube-transcript")
        == "skills/youtube-transcript"
    )


def test_no_match_lists_available(tmp_path):
    _write_skill(tmp_path, "skills/foo", "foo")
    with pytest.raises(click.ClickException) as exc:
        _resolve_skill_name_to_subpath(tmp_path, "bar")
    assert "Available: foo" in str(exc.value)


def test_multi_match_suggests_subpath_commands(tmp_path):
    _write_skill(tmp_path, "skills/youtube-transcript", "youtube-transcript")
    _write_skill(
        tmp_path, "plugins/youtube-transcript/skills", "youtube-transcript"
    )
    with pytest.raises(click.ClickException) as exc:
        _resolve_skill_name_to_subpath(
            tmp_path, "youtube-transcript", source="intellectronica/agent-skills"
        )
    msg = str(exc.value)
    # Both subpaths must appear as concrete, copy-pasteable add commands.
    assert (
        "skill add intellectronica/agent-skills/skills/youtube-transcript" in msg
    )
    assert (
        "skill add intellectronica/agent-skills/plugins/youtube-transcript/skills"
        in msg
    )


def test_multi_match_without_source_falls_back_to_subpath_flag(tmp_path):
    """Local clones have no owner/repo; the message still names the subpaths."""
    _write_skill(tmp_path, "skills/youtube-transcript", "youtube-transcript")
    _write_skill(
        tmp_path, "plugins/youtube-transcript/skills", "youtube-transcript"
    )
    with pytest.raises(click.ClickException) as exc:
        _resolve_skill_name_to_subpath(tmp_path, "youtube-transcript")
    msg = str(exc.value)
    assert "skills/youtube-transcript" in msg
    assert "plugins/youtube-transcript/skills" in msg

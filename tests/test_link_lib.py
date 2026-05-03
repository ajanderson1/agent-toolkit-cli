import pytest

from agent_toolkit.commands._link_lib import (
    ALL_HARNESSES,
    MALFORMED,
    LinkCounters,
    format_summary,
    iter_plan_lines,
    validate_harness,
)


def test_counters_default_zero():
    c = LinkCounters()
    assert c.created == 0
    assert c.updated == 0
    assert c.removed == 0
    assert c.unchanged == 0
    assert c.would_link == 0
    assert c.would_unlink == 0


def test_counters_summary_dry_run_no_changes():
    c = LinkCounters()
    assert format_summary(c, dry_run=True) == "Nothing to change."


def test_counters_summary_dry_run_with_changes():
    c = LinkCounters(would_link=2, would_unlink=1)
    assert format_summary(c, dry_run=True) == (
        "3 changes pending (2 to link, 1 to remove). Re-run without --dry-run to apply."
    )


def test_counters_summary_real_run_already_in_sync():
    c = LinkCounters(unchanged=5)
    assert format_summary(c, dry_run=False) == (
        "Already in sync — 5 assets linked, nothing to change."
    )


def test_counters_summary_real_run_with_changes():
    c = LinkCounters(created=3, updated=1, removed=2, unchanged=4)
    assert format_summary(c, dry_run=False) == (
        "Linked 3 new, updated 1, removed 2 stale (4 already in sync)."
    )


def test_iter_plan_lines_skips_blanks_and_comments():
    text = "\n# leading comment\nskill:alpha\n\nskill:beta # trailing\n# tail\n"
    pairs = list(iter_plan_lines(text))
    assert pairs == [("skill", "alpha"), ("skill", "beta")]


def test_iter_plan_lines_yields_malformed_marker_for_bad_line():
    pairs = list(iter_plan_lines("garbage-no-colon\nskill:alpha\n"))
    assert pairs[0] == (MALFORMED, "garbage-no-colon")
    assert pairs[1] == ("skill", "alpha")


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_validate_harness_accepts_known(harness):
    import click

    ctx = click.Context(click.Command("noop"))
    validate_harness(ctx, harness)  # must not raise / exit


def test_validate_harness_rejects_unknown_with_message(capsys):
    import click

    ctx = click.Context(click.Command("noop"))
    with pytest.raises(click.exceptions.Exit) as exc:
        validate_harness(ctx, "banana")
    assert exc.value.exit_code == 2
    captured = capsys.readouterr()
    assert "unknown harness 'banana'" in captured.err
    for h in ALL_HARNESSES:
        assert h in captured.err


# ===========================================================================
# Issue #13 — harness_home_path helper
# ===========================================================================


def test_harness_home_path_uses_home_env(monkeypatch, tmp_path):
    from agent_toolkit.commands._link_lib import harness_home_path

    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("claude") == tmp_path / ".claude"
    assert harness_home_path("pi") == tmp_path / ".pi"


def test_harness_home_path_explicit_home_overrides_env(tmp_path):
    from pathlib import Path as _P
    from agent_toolkit.commands._link_lib import harness_home_path

    other = tmp_path / "other-home"
    assert harness_home_path("codex", home=other) == other / ".codex"
    assert harness_home_path("opencode", home=_P("/tmp/x")) == _P("/tmp/x/.opencode")

from agent_toolkit.commands._link_lib import LinkCounters


def test_counters_default_zero():
    c = LinkCounters()
    assert c.created == 0
    assert c.updated == 0
    assert c.removed == 0
    assert c.unchanged == 0
    assert c.would_link == 0
    assert c.would_unlink == 0


def test_counters_summary_dry_run_no_changes():
    from agent_toolkit.commands._link_lib import format_summary

    c = LinkCounters()
    assert format_summary(c, dry_run=True) == "Nothing to change."


def test_counters_summary_dry_run_with_changes():
    from agent_toolkit.commands._link_lib import format_summary

    c = LinkCounters(would_link=2, would_unlink=1)
    assert format_summary(c, dry_run=True) == (
        "3 changes pending (2 to link, 1 to remove). Re-run without --dry-run to apply."
    )


def test_counters_summary_real_run_already_in_sync():
    from agent_toolkit.commands._link_lib import format_summary

    c = LinkCounters(unchanged=5)
    assert format_summary(c, dry_run=False) == (
        "Already in sync — 5 assets linked, nothing to change."
    )


def test_counters_summary_real_run_with_changes():
    from agent_toolkit.commands._link_lib import format_summary

    c = LinkCounters(created=3, updated=1, removed=2, unchanged=4)
    assert format_summary(c, dry_run=False) == (
        "Linked 3 new, updated 1, removed 2 stale (4 already in sync)."
    )


def test_iter_plan_lines_skips_blanks_and_comments():
    from agent_toolkit.commands._link_lib import iter_plan_lines

    text = "\n# leading comment\nskill:alpha\n\nskill:beta # trailing\n# tail\n"
    pairs = list(iter_plan_lines(text))
    # iter_plan_lines yields ("skill", "alpha"), ("skill", "beta") and never raises
    assert pairs == [("skill", "alpha"), ("skill", "beta")]


def test_iter_plan_lines_yields_malformed_marker_for_bad_line():
    from agent_toolkit.commands._link_lib import iter_plan_lines, MALFORMED

    pairs = list(iter_plan_lines("garbage-no-colon\nskill:alpha\n"))
    assert pairs[0] == (MALFORMED, "garbage-no-colon")
    assert pairs[1] == ("skill", "alpha")

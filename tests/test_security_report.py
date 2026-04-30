"""Tests for security-review type and overall-verdict computation."""
from agent_toolkit.security.types import Verdict, CategoryResult, OverallReport


def test_verdict_ordering():
    assert Verdict.GREEN < Verdict.AMBER < Verdict.RED


def test_overall_red_when_any_red():
    cats = [
        CategoryResult(category="1", verdict=Verdict.GREEN, evidence="ok"),
        CategoryResult(category="2", verdict=Verdict.RED, evidence="bad"),
        CategoryResult(category="3", verdict=Verdict.AMBER, evidence="meh"),
    ]
    rep = OverallReport.compute(categories=cats, provenance="x")
    assert rep.overall == Verdict.RED


def test_overall_amber_when_two_amber():
    cats = [
        CategoryResult(category="1", verdict=Verdict.AMBER, evidence="a"),
        CategoryResult(category="2", verdict=Verdict.AMBER, evidence="b"),
        CategoryResult(category="3", verdict=Verdict.GREEN, evidence="ok"),
    ]
    rep = OverallReport.compute(categories=cats, provenance="x")
    assert rep.overall == Verdict.AMBER


def test_overall_green_when_at_most_one_amber():
    cats = [
        CategoryResult(category="1", verdict=Verdict.AMBER, evidence="a"),
        CategoryResult(category="2", verdict=Verdict.GREEN, evidence="b"),
        CategoryResult(category="3", verdict=Verdict.GREEN, evidence="c"),
    ]
    rep = OverallReport.compute(categories=cats, provenance="x")
    assert rep.overall == Verdict.AMBER


def test_report_renders_human_readable():
    from agent_toolkit.security.report import render_report
    cats = [
        CategoryResult(category="1. Repo identity & traction", verdict=Verdict.GREEN,
                       evidence="2.4k stars, active, 18 contributors."),
        CategoryResult(category="4. License & legal", verdict=Verdict.GREEN,
                       evidence="MIT. Compatible with our default."),
    ]
    rep = OverallReport.compute(categories=cats, provenance="from URL", upstream="https://example.com")
    out = render_report(rep)
    assert "[GREEN] 1." in out
    assert "OVERALL: GREEN" in out
    assert "https://example.com" in out

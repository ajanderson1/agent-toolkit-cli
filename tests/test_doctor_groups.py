"""Tests for doctor check-group modules."""
from agent_toolkit.doctor.result import GroupResult, Status


def test_group_result_overall_status_picks_worst():
    r = GroupResult(name="x", status=Status.WARN, summary="2 issues",
                    findings=["a", "b"])
    assert r.status == Status.WARN
    assert r.is_failure() is False
    assert r.is_warning() is True


def test_status_ordering():
    assert Status.OK < Status.WARN < Status.FAIL
    assert max([Status.OK, Status.WARN]) == Status.WARN

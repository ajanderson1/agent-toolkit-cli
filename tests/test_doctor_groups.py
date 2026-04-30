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


def test_environment_group_ok_in_real_repo(tmp_path):
    from agent_toolkit.doctor.environment import run

    # Synthesize a "valid enough" repo
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text("{}")
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    (tmp_path / ".gitmodules").write_text("")
    result = run(tmp_path)
    # We can't assert OK because gh/uv might not be on PATH in CI; just assert structure
    assert result.name == "environment"
    assert result.status in (Status.OK, Status.WARN)
    assert isinstance(result.findings, list)


def test_environment_group_fails_when_schema_missing(tmp_path):
    from agent_toolkit.doctor.environment import run
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    (tmp_path / ".gitmodules").write_text("")
    result = run(tmp_path)
    assert result.status == Status.FAIL
    assert any("schema" in f.lower() for f in result.findings)

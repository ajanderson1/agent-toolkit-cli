"""Tests for skill_doctor diagnose + fix engine."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.skill_doctor import FixAction, Finding


def test_finding_has_expected_fields():
    fa = FixAction(
        description="noop", shell_preview="true", apply=lambda: None,
    )
    f = Finding(
        kind="drifted_symlink", slug="demo", scope="global",
        path=Path("/tmp/x"), detail="example", fix_action=fa,
    )
    assert f.kind == "drifted_symlink"
    assert f.slug == "demo"
    assert f.scope == "global"
    assert f.path == Path("/tmp/x")
    assert f.detail == "example"
    assert f.fix_action is fa


def test_fix_action_apply_is_callable():
    calls: list[int] = []
    fa = FixAction(
        description="touch", shell_preview="touch x",
        apply=lambda: calls.append(1),
    )
    fa.apply()
    fa.apply()
    assert calls == [1, 1]

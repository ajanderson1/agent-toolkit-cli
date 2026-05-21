"""Tests that _apply_skill_pending calls ensure_project_canonical for project-scope entries.

The full Textual app lifecycle is exercise-tested in test_app.py. These tests
focus narrowly on the project-canonical-ensure step by running the apply flow
inside a minimal app and asserting that ensure_project_canonical is called (or
not) based on scope.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.runner import PlanResult


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def list_state(self) -> dict:
        return {"toolkit_root": "/r", "harnesses": [], "assets": []}

    def link_plan(self, *, scope, harness, entries, dry_run=False):
        return PlanResult(ok=len(entries), failed=0)

    def unlink_plan(self, *, scope, harness, entries, dry_run=False):
        return PlanResult(ok=len(entries), failed=0)


@pytest.mark.asyncio
async def test_apply_skill_pending_calls_ensure_for_project_scope(
    git_sandbox, tmp_path, monkeypatch,
):
    """_apply_skill_pending calls ensure_project_canonical for project-scope pending entries."""
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Seed the global lock so ensure_project_canonical can find the slug.
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, add_entry, write_lock
    global_lock_path = library_root.parent / "skills-lock.json"
    entry = LockEntry(
        source=str(git_sandbox.upstream),
        source_type="local",
        ref=None,
        skill_path="SKILL.md",
        upstream_sha=None,
        local_sha=None,
    )
    write_lock(global_lock_path, add_entry(LockFile(version=1, skills={}), "demo", entry))

    # Track calls to ensure_project_canonical.
    called_with: list[dict] = []

    def _fake_ensure(*, slug, project, global_lock_path, env):
        called_with.append({"slug": slug, "project": project})
        # Create the directory so engine_apply doesn't fail.
        canonical = project / ".agents" / "skills" / slug
        canonical.mkdir(parents=True, exist_ok=True)
        return canonical

    monkeypatch.setattr(
        "agent_toolkit_tui.app.ensure_project_canonical", _fake_ensure,
        raising=False,
    )
    # Also patch where it's imported inside _apply_skill_pending.
    import agent_toolkit_cli.skill_install as _si
    monkeypatch.setattr(_si, "ensure_project_canonical", _fake_ensure)

    # Patch Path.cwd() so the app resolves the project correctly.
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: project))

    runner = _FakeRunner()
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        # Inject a project-scope pending entry directly.
        grid._pending[("project", "claude-code", "demo")] = "link"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    # ensure_project_canonical must have been called with the demo slug.
    assert any(c["slug"] == "demo" for c in called_with), (
        f"ensure_project_canonical was not called for 'demo'; calls: {called_with}"
    )


@pytest.mark.asyncio
async def test_apply_skill_pending_skips_ensure_for_global_scope(
    tmp_path, monkeypatch,
):
    """_apply_skill_pending does NOT call ensure_project_canonical for global-scope entries.

    engine_apply is mocked to avoid touching real ~/.claude/skills paths.
    """
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    called_with: list[dict] = []

    def _fake_ensure(*, slug, project, global_lock_path, env):
        called_with.append({"slug": slug})
        return project / ".agents" / "skills" / slug

    import agent_toolkit_cli.skill_install as _si
    monkeypatch.setattr(_si, "ensure_project_canonical", _fake_ensure)

    # Mock engine_apply so global-scope apply doesn't touch real ~/.claude/skills.
    from agent_toolkit_cli.skill_install import InstallResult, InstallPlan
    def _fake_apply(plan, *, home=None, project=None, env=None):
        return InstallResult(
            plan=plan, canonical_path=library_root / plan.slug,
            created=(), removed=(), skipped=(), lock_action="unchanged",
        )
    monkeypatch.setattr(_si, "apply", _fake_apply)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = _FakeRunner()
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        # Inject a global-scope pending entry directly.
        grid._pending[("global", "claude-code", "demo")] = "link"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    # ensure_project_canonical must NOT have been called for global scope.
    assert called_with == [], (
        f"ensure_project_canonical must not be called for global scope; calls: {called_with}"
    )


@pytest.mark.asyncio
async def test_apply_skill_pending_surfaces_error_when_slug_not_in_library(
    tmp_path, monkeypatch,
):
    """_apply_skill_pending increments failed when ensure_project_canonical raises InstallError."""
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: project))

    # Don't seed the global lock — slug won't be found.

    runner = _FakeRunner()
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Static
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        grid._pending[("project", "claude-code", "ghost")] = "link"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        footer = app.query_one("#footer-pending", Static)
        text = str(footer.render())

    # The footer should show "failed" count > 0 or contain the error.
    assert "1 failed" in text or "apply error" in text, (
        f"expected failure indication in footer, got: {text!r}"
    )

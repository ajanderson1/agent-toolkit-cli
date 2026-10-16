"""Regressions for cross-kind identity and hidden project apply targets."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from textual.widgets import Static

from agent_toolkit_tui.app import ApplyResult, ConfirmDiscardScreen, TUIApp


KINDS = ("instruction", "command", "skill", "agent", "mcp", "pi-extension")


def _grid(app: TUIApp, kind: str):
    return app.query_one(f"#{'pi' if kind == 'pi-extension' else kind}-grid")


def _entries(kind: str, scopes: tuple[str, ...]):
    return {
        (scope, "shared") if kind == "pi-extension" else (scope, "standard", "shared"):
        "unlink" if kind in ("agent", "mcp") else "link"
        for scope in scopes
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("scopes", [("global",), ("project",), ("global", "project")])
async def test_same_slug_across_all_kinds_counts_diff_quit_and_revert(
    monkeypatch, tmp_path, scopes
):
    monkeypatch.chdir(tmp_path)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        for kind in KINDS:
            _grid(app, kind).restore_pending(_entries(kind, scopes))
        for kind in KINDS * 2:
            app.action_asset_type(kind)
            assert _grid(app, kind).pending_entries() == _entries(kind, scopes)

        total = 6 * len(scopes)
        assert len(app._get_all_pending_edits()) == total
        app.action_diff()
        label = str(app.query_one("#footer-pending", Static).render())
        assert f"diff: {4 * len(scopes)} would-link, {2 * len(scopes)} would-unlink" in label
        tag = " (6 global, 6 project)" if len(scopes) == 2 else ""
        assert tag in label

        app.action_quit()
        assert isinstance(app.screen, ConfirmDiscardScreen)
        assert app.screen._n_pending == total
        app.pop_screen()
        await pilot.pause()

        app.action_revert()
        assert all(not _grid(app, kind).pending_entries() for kind in KINDS)
        assert f"reverted: {total} pending cleared{tag}" in str(
            app.query_one("#footer-pending", Static).render()
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("active_scope", ["global", "project"])
async def test_hidden_command_and_mcp_real_facades_write_only_queued_scopes(
    monkeypatch, tmp_path, active_scope
):
    from agent_toolkit_cli import command_paths
    from agent_toolkit_cli.command_adapters import get_adapter
    from agent_toolkit_cli.command_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli.mcp_library import library_root

    home = tmp_path / "home"
    project = tmp_path / "project"
    other = tmp_path / "other-project"
    for path in (home, project, other):
        path.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(project)
    slugs = ("project-only", "global-only", "shared")
    for slug in slugs:
        command = command_paths.library_root() / slug
        command.mkdir(parents=True)
        (command / "COMMAND.md").write_text(f"# {slug}\n", encoding="utf-8")
        mcp = library_root(home) / slug
        mcp.mkdir(parents=True)
        (mcp / "config.json").write_text(
            json.dumps({"command": "never-executed-test-server"}), encoding="utf-8"
        )
    write_lock(
        command_paths.library_lock_path(),
        LockFile(version=1, skills={
            slug: LockEntry(
                source="o/r", source_type="github", ref="main", command_path="COMMAND.md"
            )
            for slug in slugs
        }),
    )
    queued = {
        ("project", "standard", "project-only"): "link",
        ("global", "standard", "global-only"): "link",
        ("project", "standard", "shared"): "link",
        ("global", "standard", "shared"): "link",
    }

    def entries(kind, op):
        return {
            (scope, "claude-code" if kind == "mcp" and scope == "global" else harness, slug): op
            for scope, harness, slug in queued
        }

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        for kind in ("command", "mcp"):
            app.action_asset_type(kind)
            app.action_scope("project")
            _grid(app, kind).restore_pending(entries(kind, "link"))
        app.action_asset_type("skill")
        app.action_scope(active_scope)
        app.action_apply()
        footer = str(app.query_one("#footer-pending", Static).render())
        assert all(not _grid(app, kind).pending_entries() for kind in ("command", "mcp")), footer
        assert "applied: 8 ok, 0 failed (4 global, 4 project)" in footer

        for scope, root, expected in (
            ("global", home, {"global-only", "shared"}),
            ("project", project, {"project-only", "shared"}),
        ):
            config_path = root / (".claude.json" if scope == "global" else ".mcp.json")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            assert set(config["mcpServers"]) == expected
            for slug in slugs:
                dest = get_adapter("standard").destination(
                    slug, scope=scope, home=home,
                    project=project if scope == "project" else None,
                )
                assert dest.is_file() == (slug in expected)
            assert command_paths.lock_file_path(
                scope=scope, home=home, project=project
            ).is_file()
        assert not list(other.iterdir())
        assert not (home / ".mcp.json").exists()
        assert not (project / ".claude.json").exists()

        for kind in ("command", "mcp"):
            _grid(app, kind).restore_pending(entries(kind, "unlink"))
        app.action_scope("global")
        app.action_apply()
        assert all(not _grid(app, kind).pending_entries() for kind in ("command", "mcp"))
        for scope, root in (("global", home), ("project", project)):
            config_path = root / (".claude.json" if scope == "global" else ".mcp.json")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            assert not config["mcpServers"]
            for slug in slugs:
                assert not get_adapter("standard").destination(
                    slug, scope=scope, home=home,
                    project=project if scope == "project" else None,
                ).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_kind", KINDS)
async def test_all_kind_save_partial_failure_retries_only_pending_kind(
    monkeypatch, tmp_path, failed_kind
):
    monkeypatch.chdir(tmp_path)
    app = TUIApp()
    calls = []
    failing = True
    async with app.run_test() as pilot:
        await pilot.pause()
        for kind in KINDS:
            _grid(app, kind).restore_pending(_entries(kind, ("global", "project")))

            def apply(kind=kind):
                grid = _grid(app, kind)
                keys = list(grid.pending_entries())
                if keys:
                    calls.append(kind)
                failed = kind == failed_kind and failing
                if not failed:
                    grid.clear_pending()
                return ApplyResult(
                    ok=0 if failed else len(keys),
                    failed=len(keys) if failed else 0,
                    errors=["injected failure"] if failed else [],
                    keys=keys,
                )

            method = "pi" if kind == "pi-extension" else kind
            monkeypatch.setattr(app, f"_apply_{method}_pending", apply)

        app.action_asset_type("skill")
        app.action_scope("global")
        app.action_apply()
        assert calls == list(KINDS)
        assert _grid(app, failed_kind).pending_entries() == _entries(
            failed_kind, ("global", "project")
        )
        assert all(
            not _grid(app, kind).pending_entries() for kind in KINDS if kind != failed_kind
        )
        assert "apply failed" in str(app.query_one("#footer-pending", Static).render())
        app.action_diff()
        assert len(app._get_all_pending_edits()) == 2
        assert "(1 global, 1 project)" in str(app.query_one("#footer-pending", Static).render())

        failing = False
        app.action_apply()
        assert calls == [*KINDS, failed_kind]
        assert all(not _grid(app, kind).pending_entries() for kind in KINDS)
        app.action_apply()
        assert calls == [*KINDS, failed_kind]


@pytest.mark.asyncio
async def test_command_handler_partial_failure_keeps_project_target_on_retry(monkeypatch, tmp_path):
    from agent_toolkit_cli import command_install
    from agent_toolkit_cli._install_core import InstallError

    monkeypatch.chdir(tmp_path)
    calls = []
    failing = True

    def apply(plan, **kwargs):
        calls.append((plan.scope, plan.slug, kwargs["project"]))
        if plan.scope == "project" and failing:
            raise InstallError("injected failure")
        return SimpleNamespace(created=["ok"], removed=[])

    monkeypatch.setattr(command_install, "apply", apply)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        command = _grid(app, "command")
        command.restore_pending({
            ("global", "standard", "shared"): "link",
            ("project", "standard", "shared"): "link",
        })
        app.action_asset_type("skill")
        app.action_scope("global")
        app.action_apply()
        assert calls == [("global", "shared", None), ("project", "shared", tmp_path)]
        assert command.pending_entries() == {("project", "standard", "shared"): "link"}
        assert "apply failed" in str(app.query_one("#footer-pending", Static).render())
        failing = False
        app.action_apply()
        assert calls == [
            ("global", "shared", None),
            ("project", "shared", tmp_path),
            ("project", "shared", tmp_path),
        ]
        assert not command.pending_entries()
        app.action_apply()
        assert len(calls) == 3

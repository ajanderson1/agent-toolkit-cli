"""Capture the real TUI using disposable local Git/assets, never operator state.

Run: uv run python scripts/capture_docs_tui.py
Requires rsvg-convert on PATH. No network or additional Python dependencies.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("brainstorm", "code-review", "debug", "git-worktrees", "plan", "release", "test")


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "-c", "user.name=Docs Fixture",
         "-c", "user.email=docs@example.invalid", *args], text=True,
    ).strip()


async def capture(output: Path) -> None:
    import agent_toolkit_cli
    import agent_toolkit_tui.app
    from click.testing import CliRunner
    from textual.widgets import Static
    from agent_toolkit_cli.cli import main
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path, parent_clone_path
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    for module in (agent_toolkit_cli, agent_toolkit_tui.app):
        assert Path(module.__file__).resolve().is_relative_to(ROOT / "src"), module.__file__
    home = Path.home()
    assert home.parent.name.startswith("atk-docs-fixture-"), home
    project = home.parent / "demo-project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    parent = parent_clone_path("example", "workflows", ref="main")
    parent.mkdir(parents=True)
    for name in NAMES:
        folder = parent / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Disposable {name} documentation example\n---\nFixture only.\n"
        )
    git(parent, "init", "-q", "-b", "main")
    git(parent, "add", ".")
    git(parent, "commit", "-qm", "Seed documentation fixture")
    # Fixture provenance is local; no fetch or live repository is involved.
    git(parent, "remote", "add", "origin", parent.as_uri())
    entries = {}
    for name in NAMES:
        canonical = library_skill_path(name)
        canonical.symlink_to(parent / name)
        entries[name] = LockEntry(
            source="example/workflows", source_type="github", ref="main",
            skill_path=name, parent_url=parent.as_uri(),
            upstream_sha=git(parent, "rev-parse", "HEAD"), read_only=True,
        )
    write_lock(library_lock_path(), LockFile(version=1, skills=entries))
    result = CliRunner().invoke(main, [
        "skills", "install", "--source", "example/workflows",
        "--agents", "standard", "--scope", "global",
    ])
    assert result.exit_code == 0, result.output
    actual = home / ".agents/skills"
    assert {p.name for p in actual.iterdir()} == set(NAMES)
    os.chdir(project)
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(150, 32)) as pilot:
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == len(NAMES) and grid.collection_count == 1
        grid.cursor_to_cell(row_slug="code-review", agent_name="standard")
        grid.action_toggle_cell()
        grid.cursor_to_cell(row_slug="plan", agent_name="claude-code")
        grid.action_toggle_cell()
        await pilot.pause()
        assert len(grid.pending_entries()) == 2
        assert (actual / "code-review").is_symlink(), "queued removal must not write"
        bar = str(app.query_one("#status-bar", Static).render())
        assert "7 linked" in bar and "2 pending" in bar, bar
        svg = app.export_screenshot(title="Agent Toolkit — disposable documentation fixture")
        # Rich embeds a per-run identifier; no host paths/configuration may ship.
        for private in (str(ROOT), str(home), "/Users/", "Bearer "):
            assert private not in svg, private
        visible_text = " ".join(ET.fromstring(svg).itertext()).replace("\u00a0", " ")
        for expected in ("Skills", "Instructions", "Commands", "Agents", "MCPs", "Pi Extensions", "REPO", "demo-project", "workflows", "code-review"):
            assert expected in visible_text, expected
        output.mkdir(parents=True, exist_ok=True)
        (output / "agent-toolkit-cli-tui.svg").write_text(svg)
    subprocess.run([
        "rsvg-convert", "-o", str(output / "agent-toolkit-cli-tui.png"),
        str(output / "agent-toolkit-cli-tui.svg"),
    ], check=True, timeout=30)
    assert (output / "agent-toolkit-cli-tui.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "assets")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        asyncio.run(capture(output))
        return
    if not shutil.which("rsvg-convert"):
        parser.error("rsvg-convert is required to rasterize the Textual SVG")
    with tempfile.TemporaryDirectory(prefix="atk-docs-fixture-", dir="/tmp") as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "AGENT_TOOLKIT_"))}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   CLAUDE_CONFIG_DIR=str(home / ".claude"), CODEX_HOME=str(home / ".codex"),
                   VIBE_HOME=str(home / ".vibe"), PYTHONPATH=str(ROOT / "src"),
                   AGENT_TOOLKIT_SKILLS_ROOT=str(home / ".agent-toolkit/skills"))
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--output", str(output)],
                       env=env, cwd=ROOT, check=True, timeout=60)
    if output == ROOT / "assets":
        published = ROOT / "docs/assets/screenshots"
        published.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / "agent-toolkit-cli-tui.png", published / "tui-overview.png")
    print("Captured source-asserted TUI; isolated HOME/local Git only; queued edits did not write.")


if __name__ == "__main__":
    main()

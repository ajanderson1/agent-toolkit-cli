#!/usr/bin/env python3
"""Disposable installed-wheel smoke. Run with the artifact venv's Python.

All writes are inside --work-dir (which must be absent or empty). No network:
ordinary Git insteadOf maps fake Gitea URLs to fresh local fixture remotes.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import importlib.resources
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if list(work.iterdir()):
        parser.error("--work-dir must be empty")
    home = work / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for key in ("AGENT_TOOLKIT_SKILLS_ROOT", "AGENT_TOOLKIT_TUI_SETTINGS", "PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               PI_CODING_AGENT_DIR=str(home / ".pi/agent"), CODEX_HOME=str(home / ".codex"),
               CLAUDE_CONFIG_DIR=str(home / ".claude"), VIBE_HOME=str(home / ".vibe"))
    cli = Path(sys.executable).parent / "agent-toolkit-cli"

    def run(command, *, cwd=work, ok=True):
        print("+", " ".join(map(str, command)), flush=True)
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout, end="", flush=True)
        assert (result.returncode == 0) == ok, (command, result.returncode, result.stdout)
        return result.stdout

    def git(root, *args):
        return run(["git", "-C", root, *args])

    def commit(root, message):
        git(root, "add", ".")
        git(root, "-c", "user.name=REGROUND fixture", "-c", "user.email=fixture@example.test", "commit", "-m", message)

    files = {
        "skill": {"skills/reground/SKILL.md": "---\nname: shared\ndescription: Fixture skill\n---\nUse references/detail.md\n", "skills/reground/references/detail.md": "Detail", "skills/reground/scripts/check.py": "print('skill helper works')\n"},
        "agent": {"AGENTS.md": "Fixture role. See MEMORY.md.\n", "MEMORY.md": "Before\n", "memory/detail.md": "Detail\n", ".pi/skills/expert/SKILL.md": "---\nname: expert\ndescription: Fixture expert\n---\nSee references/detail.md\n", ".pi/skills/expert/references/detail.md": "Expert detail", "scripts/check.py": "print('agent helper works')\n", "resources/data.txt": "Data"},
        "command": {"COMMAND.md": "---\nname: shared\ndescription: Fixture command\n---\nHello $ARGUMENTS\n"},
    }
    urls, sources = {}, {}
    gitconfig = []
    for kind, resources in files.items():
        source = work / f"source-{kind}"
        source.mkdir()
        sources[kind] = source
        git(source, "init", "-b", "main")
        for name, content in resources.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        commit(source, "fixture baseline")
        urls[kind] = f"http://gitea.fixture.invalid:3000/reground/{kind}.git"
        gitconfig.append(f'[url "file://{source}"]\n    insteadOf = {urls[kind]}\n')
    (home / ".gitconfig").write_text("\n".join(gitconfig))

    def command(kind, verb, project=None, *extra, ok=True):
        argv = [cli]
        if project:
            argv += ["--project", project]
        argv += [kind, verb]
        if verb == "add":
            argv += [urls[kind], "--slug", "shared", "--ref", "main"]
            if kind == "skill":
                argv += ["--path", "skills/reground"]
        else:
            argv += ["shared", "-p" if project else "-g"]
            if verb in ("install", "uninstall"):
                argv += ["--agents" if kind == "skill" else "--harnesses", "pi"]
        return run([*argv, *extra], ok=ok)

    central = {kind: home / f".agent-toolkit/{kind}s/shared" for kind in files}
    destinations = {"skill": ".agents/skills/shared", "agent": ".pi/agents/shared", "command": ".pi/prompts/shared.md"}
    projects = {}
    run([cli, "--version"])
    for kind in files:
        command(kind, "add")
        record = json.loads((home / f".agent-toolkit/{kind}s-lock.json").read_text())["skills"]["shared"]
        assert record.get("parentUrl", record["source"]) == urls[kind] and record["ref"] == "main"
        if kind == "skill":
            assert record["skillPath"] == "skills/reground"
        assert git(central[kind], "config", "--get", "remote.origin.url").strip() == urls[kind]
    for name in ("a", "b"):
        project = work / name
        project.mkdir()
        projects[name] = project
        for kind in files:
            command(kind, "install", project)
            target = project / destinations[kind]
            expected = central[kind] / "COMMAND.md" if kind == "command" else central[kind]
            assert target.is_symlink() and target.resolve() == expected.resolve()
    assert not (home / ".agent-toolkit/projects").exists()
    for kind in files:
        command(kind, "uninstall", projects["a"])
        assert not (projects["a"] / destinations[kind]).is_symlink()
        assert (projects["b"] / destinations[kind]).exists() and central[kind].exists()

    agent_link = projects["b"] / destinations["agent"]
    for name, content in files["agent"].items():
        assert (agent_link / name).read_text() == content
    run([sys.executable, agent_link / "scripts/check.py"])
    run([sys.executable, projects["b"] / destinations["skill"] / "scripts/check.py"])
    (sources["agent"] / "MEMORY.md").write_text("After learning\n")
    commit(sources["agent"], "fixture learning")
    command("agent", "update")
    assert (agent_link / "MEMORY.md").read_text() == "After learning\n"

    # Same-name skill and agent have independent backing at both layouts.
    config = home / ".agent-toolkit/config.json"
    config.write_text('{"projectBacking":"isolated","allowIsolatedProjects":true}')
    private_project = work / "private"
    private_project.mkdir()
    for kind in files:
        command(kind, "install", private_project)
    private = {kind: (private_project / dest).resolve() for kind, dest in destinations.items()}
    assert private["skill"] != private["agent"]
    config.write_text('{}')
    for kind in files:
        private_root = private[kind] if private[kind].is_dir() else private[kind].parent
        unique = private_root / "unique-detached-memory"
        unique.write_text("preserve private work")
        command(kind, "uninstall", private_project)
        command(kind, "install", private_project)  # reuse despite disabled NEW creation
        assert unique.read_text() == "preserve private work"
        unique.unlink()  # remove only this fixture marker to allow clean migration
        command(kind, "install", private_project, "--migrate-to-central")
        assert private[kind].exists(), "old backing lost"
        target = private_project / destinations[kind]
        expected = central[kind] / "COMMAND.md" if kind == "command" else central[kind]
        assert target.resolve() == expected.resolve()

    disabled = work / "disabled"
    disabled.mkdir()
    config.write_text('{"projectBacking":"isolated"}')
    for kind in files:
        output = command(kind, "install", disabled, ok=False)
        assert "disabled" in output
        assert not (disabled / f"{kind}s-lock.json").exists()
    config.write_text('{}')
    foreign = work / "foreign"
    foreign.mkdir()
    dest = foreign / destinations["skill"]
    dest.mkdir(parents=True)
    (dest / "unique").write_text("do not replace")
    command("skill", "install", foreign, ok=False)
    assert (dest / "unique").read_text() == "do not replace"
    assert not (foreign / "skills-lock.json").exists()

    # Package contents and actual installed TUI engines, not the source tree.
    os.environ.clear()
    os.environ.update(env)
    os.chdir(projects["b"])
    import agent_toolkit_cli
    from agent_toolkit_tui.app import TUIApp
    print("Installed package:", agent_toolkit_cli.__file__, importlib.metadata.version("agent-toolkit"))
    project_urls = importlib.metadata.metadata("agent-toolkit").get_all("Project-URL") or []
    assert "Repository, ssh://gitlab@broadpeak.tailbf2225.ts.net:2424/ajanderson/agent-toolkit-cli.git" in project_urls
    print("Packaged source URL:", project_urls)
    matrix = importlib.resources.files("agent_toolkit_cli.data").joinpath("harness-matrix.md")
    assert matrix.is_file()

    async def tui():
        app = TUIApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            for kind in files:
                grid = app.query_one(f"#{kind}-grid")
                for op in ("unlink", "link"):
                    grid.restore_pending({("project", "pi", "shared"): op})
                    result = getattr(app, f"_apply_{kind}_pending")()
                    assert result.failed == 0, result.errors
            assert (agent_link / "MEMORY.md").read_text() == "After learning\n"
    asyncio.run(tui())
    print("PASS: installed CLI/TUI, Gitea provenance, complete resources, central sharing, detach safety, isolation gate, preserved migration, foreign refusal and package data")


if __name__ == "__main__":
    main()

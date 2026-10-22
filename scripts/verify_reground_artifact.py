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

    def command(kind, verb, project=None, *extra, ok=True, targets="pi"):
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
                argv += ["--agents" if kind == "skill" else "--harnesses", targets]
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

    # Refused source refresh must not expose the prospective role symlink.
    before_head = git(central["agent"], "rev-parse", "HEAD").strip()
    before_lock = (home / ".agent-toolkit/agents-lock.json").read_bytes()
    foreign_role = work / "foreign-role.md"
    foreign_role.write_text("Outside role must not be loaded")
    entry = sources["agent"] / "AGENTS.md"
    entry.unlink()
    entry.symlink_to(foreign_role)
    commit(sources["agent"], "fixture unsafe prospective role")
    command("agent", "update", ok=False)
    assert git(central["agent"], "rev-parse", "HEAD").strip() == before_head
    assert (home / ".agent-toolkit/agents-lock.json").read_bytes() == before_lock
    assert not (agent_link / "AGENTS.md").is_symlink()
    assert (agent_link / "AGENTS.md").read_text() == files["agent"]["AGENTS.md"]
    git(sources["agent"], "reset", "--hard", before_head)  # only this disposable remote fixture

    # Do not cancel '..' before expanding an intermediate directory symlink.
    outside_data = work / "data.txt"
    outside_data.write_text("outside repository fixture")
    (sources["agent"] / "resources/back").symlink_to("..", target_is_directory=True)
    leak = sources["agent"] / "resources/leak"
    leak.symlink_to("back/../data.txt")
    assert leak.resolve(strict=True) == outside_data
    commit(sources["agent"], "fixture linked-directory parent traversal")
    command("agent", "update", ok=False)
    assert git(central["agent"], "rev-parse", "HEAD").strip() == before_head
    assert (home / ".agent-toolkit/agents-lock.json").read_bytes() == before_lock
    assert not (agent_link / "resources/leak").is_symlink()
    assert (agent_link / "resources/data.txt").read_text() == "Data"
    assert outside_data.read_text() == "outside repository fixture"
    git(sources["agent"], "reset", "--hard", before_head)

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
        if kind == "agent":
            baseline = git(central[kind], "rev-parse", "HEAD").strip()
            central_only = central[kind] / "central-only"
            central_only.write_text("central committed work")
            commit(central[kind], "fixture central-only commit")
            central_head = git(central[kind], "rev-parse", "HEAD").strip()
            (private_root / "private-only").write_text("explicit private reset fixture")
            commit(private_root, "fixture private-only commit")
            command("agent", "reset", private_project)
            assert not (private_root / "private-only").exists()
            assert central_only.read_text() == "central committed work"
            assert git(central[kind], "rev-parse", "HEAD").strip() == central_head
            git(central[kind], "reset", "--hard", baseline)  # restore only fixture data for migration
        command(kind, "install", private_project, "--migrate-to-central")
        assert private[kind].exists(), "old backing lost"
        target = private_project / destinations[kind]
        expected = central[kind] / "COMMAND.md" if kind == "command" else central[kind]
        assert target.resolve() == expected.resolve()

    # A failed first private install must clean only its own new state and
    # retry after removing ONLY the conflicting fixture, never deleting backing.
    config.write_text('{"projectBacking":"isolated","allowIsolatedProjects":true}')
    retry = work / "retry-private"
    retry.mkdir()
    for kind in files:
        dest = retry / (".claude/skills/shared" if kind == "skill" else destinations[kind])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("foreign fixture")
        targets = "claude-code" if kind == "skill" else "pi"
        command(kind, "install", retry, targets=targets, ok=False)
        assert dest.read_text() == "foreign fixture" and not (retry / f"{kind}s-lock.json").exists()
        dest.unlink()
        command(kind, "install", retry, targets=targets)
        assert dest.exists()

    # Keep an unlisted private consumer for a real TUI detach/re-register proof.
    unlisted = work / "unlisted-private"
    unlisted.mkdir()
    command("skill", "install", unlisted)
    unlisted_slot = unlisted / destinations["skill"]
    unlisted_backing = unlisted_slot.resolve()
    (unlisted_backing / "unique-memory").write_text("preserve unlisted work")
    skill_lock = home / ".agent-toolkit/skills-lock.json"
    data = json.loads(skill_lock.read_text())
    del data["skills"]["shared"]
    skill_lock.write_text(json.dumps(data))
    config.write_text('{}')

    disabled = work / "disabled"
    disabled.mkdir()
    config.write_text('{"projectBacking":"isolated"}')
    for kind in files:
        output = command(kind, "install", disabled, ok=False)
        assert "disabled" in output
        assert not (disabled / f"{kind}s-lock.json").exists()
    config.write_text('{}')
    # Temporarily restore membership for the ordinary foreign-slot check; the
    # unlisted detach below removes it again without touching either backing.
    command("skill", "add")
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
    installed = Path(agent_toolkit_cli.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in installed.parts
    print("Installed package:", installed, importlib.metadata.version("agent-toolkit"))
    project_urls = importlib.metadata.metadata("agent-toolkit").get_all("Project-URL") or []
    assert "Repository, ssh://gitlab@broadpeak.tailbf2225.ts.net:2424/ajanderson/agent-toolkit-cli.git" in project_urls
    print("Packaged source URL:", project_urls)
    matrix = importlib.resources.files("agent_toolkit_cli.data").joinpath("harness-matrix.md")
    assert matrix.is_file()

    async def tui():
        os.chdir(unlisted)
        data = json.loads(skill_lock.read_text())
        del data["skills"]["shared"]
        skill_lock.write_text(json.dumps(data))
        identity = (unlisted / "skills-lock.json").read_bytes()
        app = TUIApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#skill-grid").restore_pending({("project", "pi", "shared"): "unlink"})
            result = app._apply_skill_pending()
            assert result.failed == 0, result.errors
            assert not unlisted_slot.is_symlink()
            assert (unlisted / "skills-lock.json").read_bytes() == identity
        status = run([cli, "--project", unlisted, "skills", "list", "-p", "--agent", "pi", "--json"])
        assert json.loads(status) == []
        command("skill", "add")
        command("skill", "install", unlisted)
        assert unlisted_slot.resolve() == unlisted_backing
        assert (unlisted_backing / "unique-memory").read_text() == "preserve unlisted work"
        os.chdir(projects["b"])
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
    print("PASS: installed CLI/TUI, Gitea provenance, complete resources, central sharing, unlisted private TUI detach/reinstall, pre-checkout refresh refusal, private reset scope, failed first-install retry, isolation gate, preserved migration, foreign refusal and package data")


if __name__ == "__main__":
    main()

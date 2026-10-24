"""Installed-wheel npm workflow verification; disposable HOME, no extension execution.

Run with the installed interpreter and -I, passing --pi-package /path/to/Pi.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PI_PACKAGE: Path
NAME = "atk-native-npm-verification"
ORACLE = r"""
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [pi,home,cwd,trust]=process.argv.slice(1);
process.env.HOME=home;process.env.PI_CODING_AGENT_DIR=join(home,'.pi/agent');process.env.PI_OFFLINE='1';
const {SettingsManager}=await import(pathToFileURL(join(pi,'dist/core/settings-manager.js')).href);
const {DefaultPackageManager}=await import(pathToFileURL(join(pi,'dist/core/package-manager.js')).href);
const manager=new DefaultPackageManager({cwd,agentDir:join(home,'.pi/agent'),settingsManager:SettingsManager.create(cwd,join(home,'.pi/agent'),{projectTrusted:trust==='true'})});
manager.getLegacyGlobalNpmInstallPath=()=>undefined;
const resolved=await manager.resolve(async()=> 'skip');
console.log(JSON.stringify(Object.fromEntries(['extensions','skills','prompts','themes'].map(type=>[type,resolved[type].filter(e=>e.metadata.source.startsWith('npm:atk-native-npm-verification')).map(e=>({path:e.path,enabled:e.enabled}))]))));
"""


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def environment(home, project):
    home.mkdir(parents=True, exist_ok=True); project.mkdir(parents=True, exist_ok=True)
    for key, suffix in {"HOME": "", "USERPROFILE": "", "XDG_CONFIG_HOME": ".config", "CODEX_HOME": ".codex", "CLAUDE_CONFIG_DIR": ".claude", "VIBE_HOME": ".vibe", "PI_CODING_AGENT_DIR": ".pi/agent", "AGENT_TOOLKIT_NPM_GLOBAL_ROOT": "empty-global-npm"}.items():
        os.environ[key] = str(home / suffix)
    for key in ("AGENT_TOOLKIT_SKILLS_ROOT", "AGENT_TOOLKIT_TUI_SETTINGS", "PI_OFFLINE"):
        os.environ.pop(key, None)
    os.environ.update(AGENT_TOOLKIT_PI_PACKAGE=str(PI_PACKAGE), NPM_CONFIG_OFFLINE="true", NPM_CONFIG_IGNORE_SCRIPTS="true", NPM_CONFIG_AUDIT="false", NPM_CONFIG_FUND="false", NPM_CONFIG_UPDATE_NOTIFIER="false", NPM_CONFIG_LOGS_MAX="0")
    os.chdir(project)


def seed(home, project, *, configured=True):
    base = home / ".pi/agent"
    root = base / "npm/node_modules" / NAME
    put(root / "package.json", {"name": NAME, "version": "1.0.0", "pi": {"extensions": ["extensions/main.ts"], "skills": ["skills/review"]}})
    (root / "extensions").mkdir(); (root / "extensions/main.ts").write_text("throw new Error('Do not execute extension code')")
    (root / "skills/review").mkdir(parents=True)
    (root / "skills/review/SKILL.md").write_text("---\nname: review\ndescription: Disposable verification\n---\n")
    put(base / "npm/package.json", {"private": True, "dependencies": {NAME: "1.0.0"}})
    put(base / "settings.json", {"defaultProjectTrust": "always", "packages": [f"npm:{NAME}@1.0.0"] if configured else []})
    return root


def oracle(home, project, scope):
    return json.loads(subprocess.check_output(["node", "--input-type=module", "-e", ORACLE, str(PI_PACKAGE), str(home), str(project), str(scope == "project").lower()], text=True))


def enabled(home, project, scope):
    entries = oracle(home, project, scope)["extensions"]
    return bool(entries) and all(e["enabled"] for e in entries)


async def workflows():
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable, Static
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.pi_grid import PiGrid
    from agent_toolkit_cli import pi_npm

    def select(app, scope):
        app.action_asset_type("pi-extension"); app.action_scope(scope)
        grid = app.query_one("#pi-grid", PiGrid)
        table = grid.query_one("#pi-table", DataTable)
        table.cursor_coordinate = Coordinate(grid.row_slugs.index(NAME), 1); table.focus()
        return grid

    cases = ["global", "project", "project-on/global-off", "reset", "available", "mixed", "stale", "stale-inherited", "multi-scope", "missing"]
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="atk-npm-ui-") as directory:
            parent = Path(directory); home, project = parent / "home", parent / "project"
            environment(home, project)
            root = seed(home, project, configured=case != "available")
            source_bytes = (root / "extensions/main.ts").read_bytes()
            config = home / ".pi/agent/settings.json"
            scope = "project" if case in ("project", "project-on/global-off", "reset", "multi-scope", "stale-inherited") else "global"
            if case == "project-on/global-off":
                pi_npm.set_npm_enabled(identity=NAME, enabled=False, scope="global", home=home, project=project)
            if case in ("reset", "multi-scope"):
                pi_npm.set_npm_enabled(identity=NAME, enabled=False, scope="project", home=home, project=project)
            if case == "mixed":
                manifest = json.loads((root / "package.json").read_text()); manifest["pi"]["extensions"].append("extensions/second.ts")
                put(root / "package.json", manifest); (root / "extensions/second.ts").write_text("throw new Error('never execute')")
                data = json.loads(config.read_text()); data["packages"] = [{"source": f"npm:{NAME}@1.0.0", "extensions": ["-extensions/main.ts"]}]; put(config, data)
            if case == "missing":
                shutil.rmtree(root)
            before = config.read_bytes()
            app = TUIApp()
            async with app.run_test() as pilot:
                grid = select(app, "global" if case == "multi-scope" else scope)
                if case == "reset":
                    await pilot.press("r", "ctrl+d"); await pilot.pause()
                    assert "1 would-reset" in str(app.query_one("#footer-pending", Static).render())
                else:
                    await pilot.press("space")
                if case == "multi-scope":
                    grid = select(app, "project"); await pilot.press("space")
                if case in ("stale", "stale-inherited"):
                    app.action_scope("global"); app.action_scope(scope); app.action_refresh()
                    data = json.loads(config.read_text()); data["packages"] = [{"source": f"npm:{NAME}@1.0.0", "extensions": []}]; put(config, data)
                    before = config.read_bytes()
                await pilot.press("ctrl+s"); await pilot.pause()
                if case in ("stale", "stale-inherited", "missing"):
                    assert grid.pending_entries() and config.read_bytes() == before
                    if case == "stale-inherited":
                        assert not (project / ".pi/settings.json").exists()
                else:
                    assert not grid.pending_entries()
                    wanted = case not in ("global", "project")
                    assert enabled(home, project, scope) is wanted
                    if case == "available":
                        assert not any(e["enabled"] for e in oracle(home, project, "global")["skills"])
                    if case == "multi-scope":
                        assert not enabled(home, project, "global") and enabled(home, project, "project")
                    app.action_refresh(); await pilot.pause()
            if case not in ("missing",):
                assert (root / "extensions/main.ts").read_bytes() == source_bytes
            if scope == "project":
                assert not (project / ".pi/npm").exists()
            if case in ("global", "project"):
                app = TUIApp()
                async with app.run_test() as pilot:
                    grid = select(app, scope); await pilot.press("space", "ctrl+s"); await pilot.pause()
                    assert not grid.pending_entries() and enabled(home, project, scope)
            assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
            print("PASS TUI/native:", case)
    return len(cases)


def installations():
    from agent_toolkit_cli import pi_npm
    from agent_toolkit_cli.pi_npm_lifecycle import install_npm, remove_npm
    for route in ("pi", "npm", "toolkit", "external-npm"):
        with tempfile.TemporaryDirectory(prefix="atk-npm-install-") as directory:
            parent = Path(directory); home, project, source = parent / "home", parent / "project", parent / "source"
            environment(home, project)
            put(source / "package.json", {"name": NAME, "version": "1.0.0", "pi": {"extensions": ["index.ts"]}})
            (source / "index.ts").write_text("throw new Error('Do not execute extension code')")
            put(home / ".pi/agent/settings.json", {"defaultProjectTrust": "always"})
            specification = f"npm:{NAME}@file:{source}"
            if route == "toolkit":
                install_npm(source=specification, scope="global", home=home, project=project)
            else:
                argv = ["pi", "install", specification] if route == "pi" else ["npm", "install", "--prefix", str(home / ".pi/agent/npm"), specification.removeprefix("npm:")]
                if route == "external-npm":
                    prefix = parent / "external-prefix"
                    os.environ["AGENT_TOOLKIT_NPM_GLOBAL_ROOT"] = str(prefix / "lib/node_modules")
                    argv = ["npm", "install", "--global", "--prefix", str(prefix), specification.removeprefix("npm:")]
                subprocess.run(argv, check=True, capture_output=True, text=True, timeout=60)
            state = pi_npm.read_npm_states(home=home, project=project)[NAME]
            assert state.global_scope.installed and state.global_scope.enabled is (route in ("pi", "toolkit"))
            if route == "external-npm":
                pi_npm.set_npm_enabled(identity=NAME, enabled=True, scope="global", home=home, project=project)
                assert pi_npm.read_npm_states(home=home, project=project)[NAME].global_scope.enabled
            result = remove_npm(identity=NAME, scope="global", home=home, project=project, external=route == "external-npm")
            assert result.files_removed and not result.files_remain
            assert NAME not in pi_npm.read_npm_states(home=home, project=project)
            assert (source / "index.ts").read_text() == "throw new Error('Do not execute extension code')"
            assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
            print("PASS offline install/remove:", route)
    return 4


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-package", type=Path, required=True)
    PI_PACKAGE = parser.parse_args().pi_package.resolve()
    version = json.loads((PI_PACKAGE / "package.json").read_text())["version"]
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="atk-npm-bootstrap-") as bootstrap:
        base = Path(bootstrap); environment(base / "home", base / "project")
        try:
            assert subprocess.check_output(["pi", "--version"], text=True).strip() == version, "Pi CLI and selected SDK versions differ"
            cases = asyncio.run(workflows()) + installations()
            print(f"Verified {cases} installed native npm workflows against Pi {version}; disposable files only, no extension code executed.")
        finally:
            os.chdir(original)

"""Verify real local-extension TUI controls against an explicitly selected Pi install.

Run with: uv run python scripts/verify_pi_local_controls.py --pi-package PATH
Only disposable HOME/config/assets are used; extension code is never loaded.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile

PI_PACKAGE: Path

NODE_RESOLVER = """
import {join, dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
const [pi,home,cwd,trust] = process.argv.slice(1);
const agentDir=join(home,'.pi/agent');
process.env.HOME=home; process.env.PI_CODING_AGENT_DIR=agentDir; process.env.PI_OFFLINE='1';
const {SettingsManager}=await import(pathToFileURL(join(pi,'dist/core/settings-manager.js')).href);
const {DefaultPackageManager}=await import(pathToFileURL(join(pi,'dist/core/package-manager.js')).href);
const settingsManager=SettingsManager.create(cwd,agentDir,{projectTrusted:trust==='true'});
const resources=await new DefaultPackageManager({cwd,agentDir,settingsManager}).resolve();
console.log(JSON.stringify(Object.fromEntries(resources.extensions.filter(e=>e.path.startsWith(dirname(home)+'/')).map(e=>[e.path,e.enabled]))));
"""


def sandbox_environment(home):
    for variable, suffix in {
        "HOME": "", "USERPROFILE": "", "XDG_CONFIG_HOME": ".config",
        "CODEX_HOME": ".codex", "CLAUDE_CONFIG_DIR": ".claude",
        "VIBE_HOME": ".vibe", "PI_CODING_AGENT_DIR": ".pi/agent",
    }.items():
        os.environ[variable] = str(home / suffix)
    for variable in ("AGENT_TOOLKIT_SKILLS_ROOT", "AGENT_TOOLKIT_TUI_SETTINGS"):
        os.environ.pop(variable, None)
    os.environ["AGENT_TOOLKIT_NPM_GLOBAL_ROOT"] = str(home / "empty-global-npm")
    os.environ["AGENT_TOOLKIT_PI_PACKAGE"] = str(PI_PACKAGE)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def native(home, project, trusted):
    output = subprocess.check_output([
        "node", "--input-type=module", "-e", NODE_RESOLVER, str(PI_PACKAGE), str(home), str(project),
        str(trusted).lower(),
    ], text=True)
    return json.loads(output)


async def main():
    from rich.text import Text
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.pi_extension_state import build_pi_rows
    from agent_toolkit_cli.pi_local_extensions import read_local_extension_states
    from agent_toolkit_tui.widgets.pi_grid import PiGrid

    cases = [
        ("global file", "global", "file", "global", []),
        ("project file", "project", "file", "project", []),
        ("inherited global", "global", "file", "project", []),
        ("symlink file", "global", "symlink", "global", []),
        ("index directory", "global", "index", "global", []),
        ("symlink directory", "global", "symlink-directory", "project", []),
        ("mixed manifest", "global", "manifest", "global", ["-extensions/router/a.ts"]),
        ("inherited mixed manifest", "global", "manifest", "project", ["-extensions/router/a.ts"]),
        ("glob override", "global", "file", "global", ["!**/@(router|other).ts"]),
        ("project file referenced globally", "project", "file", "project", ["<source>", "-<source>"]),
        ("minimatch comment", "global", "hashfile", "global", ["!#router.ts"]),
        ("explicit second alias", "global", "explicit-alias", "global", ["extensions/router.ts"]),
        ("failed scope refresh", "global", "failed-refresh", "project", []),
        ("package overlap refusal", "global", "package-collision", "global", []),
        ("package autoload delta", "global", "package-delta", "project", []),
    ]
    for name, origin, shape, scope, selectors in cases:
        with tempfile.TemporaryDirectory(prefix="pi-tui-native-") as directory:
            sandbox = Path(directory).resolve()
            home, project = sandbox / "home", sandbox / "project"
            home.mkdir(); project.mkdir()
            sandbox_environment(home)
            os.chdir(project)
            root = home / ".pi/agent/extensions" if origin == "global" else project / ".pi/extensions"
            slug = "#router" if shape == "hashfile" else "router"
            source = root / ("router" if shape in ("index", "manifest", "symlink-directory", "package-delta") else slug + ".ts")
            source.parent.mkdir(parents=True, exist_ok=True)
            actual = sandbox / "target.ts" if shape in ("symlink", "explicit-alias") else sandbox / "target" if shape == "symlink-directory" else source
            files = []
            if shape in ("index", "manifest", "symlink-directory", "package-delta"):
                actual.mkdir()
                for filename in (["a.ts", "b.ts"] if shape in ("manifest", "package-delta") else ["index.ts"]):
                    target = actual / filename
                    target.write_text("throw new Error('Do not execute extension code')")
                    files.append(target)
                if shape in ("manifest", "package-delta"):
                    manifest = actual / "package.json"
                    manifest.write_text(json.dumps({"pi": {"extensions": ["a.ts", "b.ts"]}}))
                    files.append(manifest)
            else:
                actual.write_text("throw new Error('Do not execute extension code')")
                files.append(actual)
            if source != actual:
                source.symlink_to(actual, target_is_directory=actual.is_dir())
            if shape == "explicit-alias":
                (root / "aa-router.ts").symlink_to(actual)
            sources = {path: path.read_bytes() for path in files}
            global_settings, project_settings = home / ".pi/agent/settings.json", project / ".pi/settings.json"
            put(global_settings, json.dumps({"theme": "dark", "extensions": [s.replace("<source>", str(source)) for s in selectors]}))
            put(project_settings, json.dumps({"theme": "light"}))
            if shape == "package-delta":
                put(global_settings, json.dumps({"theme": "dark", "packages": [{"source": str(source), "extensions": []}]}))
                put(project_settings, json.dumps({"theme": "light", "packages": [{"source": str(source), "autoload": False}]}))
            other = project_settings if scope == "global" else global_settings
            other_before = other.read_bytes()

            def compare():
                rows = build_pi_rows(home=home, project=project)
                states = read_local_extension_states(home=home, project=project)
                for trusted, attribute in [(False, "global_entries"), (True, "project_entries")]:
                    model = {str(e.path): e.enabled for state in states.values() for e in getattr(state, attribute)}
                    assert model == native(home, project, trusted), (name, attribute, model)
                return rows

            rows = compare()
            if shape == "package-collision":
                app = TUIApp()
                async with app.run_test() as pilot:
                    app.action_asset_type("pi-extension"); app.action_scope("global")
                    grid = app.query_one("#pi-grid", PiGrid)
                    table = grid.query_one("#pi-table", DataTable)
                    table.cursor_coordinate = Coordinate(grid.row_slugs.index(slug), 1); table.focus()
                    await pilot.press("space")
                    assert grid.pending_entries() == {("global", slug): "unlink"}
                    put(global_settings, json.dumps({"theme": "dark", "packages": ["extensions/router.ts"]}))
                    before = global_settings.read_bytes()
                    await pilot.press("ctrl+s"); await pilot.pause()
                    assert global_settings.read_bytes() == before
                    assert grid.pending_entries() == {("global", slug): "unlink"}
                    assert native(home, project, False) == {str(source): True}
                    compare()
                    assert slug not in grid.row_slugs
                app = TUIApp()
                async with app.run_test() as pilot:
                    app.action_asset_type("pi-extension"); app.action_scope("global")
                    grid = app.query_one("#pi-grid", PiGrid)
                    assert grid.row_slugs == ["extensions/router.ts"]
                    table = grid.query_one("#pi-table", DataTable)
                    table.cursor_coordinate = Coordinate(0, 1); table.focus()
                    await pilot.press("space")
                    assert not grid.pending_entries()
                assert other.read_bytes() == other_before
                assert all(path.read_bytes() == original for path, original in sources.items())
                assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
                print("PASS: package overlap refusal: unchanged settings, retained intent, native selection preserved, no duplicate loose control")
                continue
            if shape == "package-delta":
                from agent_toolkit_cli.pi_local_extensions import set_local_extension_enabled
                from agent_toolkit_cli._pi_settings import PiSettingsError
                state = read_local_extension_states(home=home, project=project)[slug]
                assert not state.global_enabled and not state.project_enabled
                before = project_settings.read_bytes()
                try:
                    set_local_extension_enabled(slug=slug, enabled=True, scope="project", home=home, project=project, expected_paths=state.paths_for("project"))
                except PiSettingsError as error:
                    assert "packages[]" in str(error)
                else:
                    raise AssertionError("Package-owned resources accepted loose selectors")
                assert project_settings.read_bytes() == before
                app = TUIApp()
                async with app.run_test() as pilot:
                    app.action_asset_type("pi-extension"); app.action_scope("project")
                    grid = app.query_one("#pi-grid", PiGrid)
                    assert slug not in grid.row_slugs
                    table = grid.query_one("#pi-table", DataTable)
                    table.cursor_coordinate = Coordinate(0, 1); table.focus()
                    await pilot.press("space")
                    assert not grid.pending_entries()
                compare()
                assert other.read_bytes() == other_before
                assert all(path.read_bytes() == original for path, original in sources.items())
                print("PASS: package autoload delta: native global base retained; package controls remain separate")
                continue
            row = next(row for row in rows if row.slug == slug)
            initial = row.global_cell.global_loaded if scope == "global" else row.project_cell.project_loaded
            for desired in ([False, True] if initial else [True, False]):
                app = TUIApp()
                async with app.run_test() as pilot:
                    app.action_asset_type("pi-extension")
                    if shape == "failed-refresh":
                        app.action_scope("global")
                        original_project = project_settings.read_bytes()
                        project_settings.write_text("{broken")
                        app.action_scope("project")
                        project_settings.write_bytes(original_project)
                    else:
                        app.action_scope(scope)
                    grid = app.query_one("#pi-grid", PiGrid)
                    table = grid.query_one("#pi-table", DataTable)
                    table.cursor_coordinate = Coordinate(grid.row_slugs.index(slug), 1)
                    table.focus()
                    await pilot.press("space")
                    assert grid.pending_entries() == {(scope, slug): "link" if desired else "unlink"}, name
                    await pilot.press("ctrl+s")
                    await pilot.pause()
                    assert grid.pending_entries() == {}, name
                    app.action_refresh()
                    await pilot.pause()
                    glyph = Text.from_markup(str(table.get_cell_at(table.cursor_coordinate))).plain
                    assert ("✔" if desired else "☐") in glyph, (name, glyph)
                    compare()
                assert other.read_bytes() == other_before, name
                assert all(path.read_bytes() == original for path, original in sources.items()), name
                assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists(), name
                assert not (project / ".agent-toolkit/pi-extensions-lock.json").exists(), name
                if source != actual:
                    assert source.is_symlink() and source.resolve() == actual
            # A third fresh application must reconstruct the final state.
            app = TUIApp()
            async with app.run_test() as pilot:
                app.action_asset_type("pi-extension"); app.action_scope(scope)
                grid = app.query_one("#pi-grid", PiGrid)
                table = grid.query_one("#pi-table", DataTable)
                table.cursor_coordinate = Coordinate(grid.row_slugs.index(slug), 1)
                text = Text.from_markup(str(table.get_cell_at(table.cursor_coordinate))).plain
                assert ("✔" if desired else "☐") in text, name
                compare()
            print(f"PASS: {name}: real keys, apply, refresh, fresh app, native global/project resolution, source/other-scope/lock integrity")
    # Hold the real native settings lock in a separate Node process. Apply
    # must retain its failed intent, then succeed after the native writer exits.
    with tempfile.TemporaryDirectory(prefix="pi-tui-native-lock-") as directory:
        sandbox = Path(directory).resolve()
        home, project = sandbox / "home", sandbox / "project"
        home.mkdir(); project.mkdir()
        sandbox_environment(home); os.chdir(project)
        source = home / ".pi/agent/extensions/router.ts"
        put(source, "throw new Error('Do not execute extension code')")
        settings = home / ".pi/agent/settings.json"
        put(settings, '{"theme":"dark"}')
        locker_code = """
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
const [pi,path]=process.argv.slice(1);
const require=createRequire(pathToFileURL(join(pi,'package.json')));
const release=require('proper-lockfile').lockSync(path,{realpath:false});
console.log('LOCKED');
process.stdin.once('data',()=>{release();process.stdin.pause();});
"""
        locker = subprocess.Popen(["node", "--input-type=module", "-e", locker_code, str(PI_PACKAGE), str(settings)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert locker.stdout.readline().strip() == "LOCKED"
            app = TUIApp()
            async with app.run_test() as pilot:
                app.action_asset_type("pi-extension"); app.action_scope("global")
                grid = app.query_one("#pi-grid", PiGrid)
                table = grid.query_one("#pi-table", DataTable)
                table.cursor_coordinate = Coordinate(0, 1); table.focus()
                await pilot.press("space", "ctrl+s"); await pilot.pause()
                assert grid.pending_entries() == {("global", "router"): "unlink"}
                assert json.loads(settings.read_text()) == {"theme": "dark"}
                locker.communicate("release\\n", timeout=10)
                assert locker.returncode == 0
                await pilot.press("ctrl+s"); await pilot.pause()
                assert not grid.pending_entries()
                assert native(home, project, False) == {str(source): False}
        finally:
            if locker.poll() is None:
                locker.communicate("release\\n", timeout=10)
        print("PASS: native proper-lockfile contention: failed intent retained; retry after release succeeds")
    print(f"All {len(cases)} TUI/native cases and native lock interoperability passed. No extension code executed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-package", required=True, type=Path, help="Installed Pi package directory (contains package.json and dist/)")
    args = parser.parse_args()
    PI_PACKAGE = args.pi_package.resolve()
    if not (PI_PACKAGE / "dist/core/package-manager.js").is_file():
        parser.error("--pi-package must name an installed Pi package")
    print("Native Pi:", json.loads((PI_PACKAGE / "package.json").read_text())["version"])
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="pi-tui-bootstrap-") as bootstrap:
        sandbox_environment(Path(bootstrap))
        try:
            asyncio.run(main())
        finally:
            os.chdir(original_cwd)

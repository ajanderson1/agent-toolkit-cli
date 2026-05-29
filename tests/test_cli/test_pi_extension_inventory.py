import json
from pathlib import Path

from agent_toolkit_cli.pi_extension_inventory import build_inventory


def _pi_global(home: Path) -> Path:
    d = home / ".pi" / "agent" / "extensions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_loose_dir_with_index_is_untracked(tmp_path):
    ext = _pi_global(tmp_path) / "loose-ext"
    ext.mkdir()
    (ext / "index.ts").write_text("export default {}")
    # empty global lock
    (tmp_path / ".agent-toolkit").mkdir()
    (tmp_path / ".agent-toolkit" / "pi-extensions-lock.json").write_text(
        json.dumps({"version": 1, "skills": {}}) + "\n"
    )
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["loose-ext"]
    assert rec.origin == "untracked"
    assert rec.global_loaded is True


def test_loose_file_extension(tmp_path):
    (_pi_global(tmp_path) / "hooks.ts").write_text("// x")
    records = build_inventory(home=tmp_path)
    assert {r.slug for r in records} >= {"hooks"}
    assert {r.slug: r for r in records}["hooks"].origin == "untracked"


def test_npm_package_is_tracked_registry(tmp_path):
    s = tmp_path / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True)
    s.write_text(json.dumps({"packages": ["npm:@scope/rpiv-i18n"]}))
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["@scope/rpiv-i18n"]
    assert rec.origin == "npm"
    assert rec.source == "npm:@scope/rpiv-i18n"
    assert rec.global_loaded is True


def test_store_owned_from_lock(tmp_path, monkeypatch):
    # The global lock path resolves from $HOME (lock_file_path ignores the
    # `home` arg at global scope, matching skill_paths convention), so point
    # HOME at tmp_path for the lock to be discovered.
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({
        "version": 1,
        "skills": {"status-bar": {
            "source": "github.com/o/status-bar", "sourceType": "github",
            "piExtensionPath": "status-bar",
        }},
    }) + "\n")
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["status-bar"]
    assert rec.origin == "store-owned"
    assert rec.source == "github.com/o/status-bar"


def test_empty_machine_is_empty(tmp_path):
    assert build_inventory(home=tmp_path) == []


def _pi_project(project: Path) -> Path:
    d = project / ".pi" / "extensions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _seed_loose_dir(root: Path, slug: str) -> None:
    ext = root / slug
    ext.mkdir(parents=True)
    (ext / "index.ts").write_text("export default {}")


def _seed_packages(settings: Path, *specs: str) -> None:
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"packages": list(specs)}))


def test_project_scope_surfaces_project_rows(tmp_path, monkeypatch):
    """build_inventory with both scopes flags each row per the scope it was
    seeded in, and a slug present in BOTH scopes shows both flags.

    The global lock path resolves from $HOME, so point HOME at a dedicated
    home dir kept separate from the project tree."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Global fixtures: a loose dir + an npm package, both global-only.
    _seed_loose_dir(home / ".pi" / "agent" / "extensions", "global-loose")
    _seed_packages(home / ".pi" / "agent" / "settings.json", "npm:@scope/global-npm")

    # Project fixtures: a loose dir + an npm package, both project-only.
    _seed_loose_dir(_pi_project(project), "proj-loose")
    _seed_packages(project / ".pi" / "settings.json", "npm:@scope/proj-npm")

    # A slug present in BOTH scopes (loose dir in each).
    _seed_loose_dir(home / ".pi" / "agent" / "extensions", "shared-loose")
    _seed_loose_dir(_pi_project(project), "shared-loose")

    rows = {r.slug: r for r in build_inventory(home=home, project=project)}

    # Mirror the reviewer's manual check: (global_loaded, project_loaded).
    assert (rows["@scope/global-npm"].global_loaded,
            rows["@scope/global-npm"].project_loaded) == (True, False)
    assert (rows["@scope/proj-npm"].global_loaded,
            rows["@scope/proj-npm"].project_loaded) == (False, True)
    assert (rows["global-loose"].global_loaded,
            rows["global-loose"].project_loaded) == (True, False)
    assert (rows["proj-loose"].global_loaded,
            rows["proj-loose"].project_loaded) == (False, True)
    # Present in both -> both flags True.
    assert (rows["shared-loose"].global_loaded,
            rows["shared-loose"].project_loaded) == (True, True)


def test_npm_pass_does_not_downgrade_store_owned(tmp_path, monkeypatch):
    """A slug that is BOTH store-owned (lock) and listed as npm: in settings
    keeps origin='store-owned' and still records the npm presence flag."""
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({
        "version": 1,
        "skills": {"@scope/dual": {
            "source": "github.com/o/dual", "sourceType": "github",
            "piExtensionPath": "@scope/dual",
        }},
    }) + "\n")
    _seed_packages(tmp_path / ".pi" / "agent" / "settings.json", "npm:@scope/dual")

    rec = {r.slug: r for r in build_inventory(home=tmp_path)}["@scope/dual"]
    # Store-owned wins over npm: origin/source are NOT clobbered...
    assert rec.origin == "store-owned"
    assert rec.source == "github.com/o/dual"
    # ...but the npm presence is still recorded.
    assert rec.global_loaded is True

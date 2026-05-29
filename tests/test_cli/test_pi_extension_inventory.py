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

"""Disposable npm installation metadata; extension bodies must never execute."""
import json
from pathlib import Path


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def seed_package(home: Path, project: Path, *, scope="global", name="demo", version="1.0.0", entries=("extensions/main.ts",), configured=True):
    base = home / ".pi/agent" if scope == "global" else project / ".pi"
    root = base / "npm/node_modules" / name
    write_json(root / "package.json", {"name": name, "version": version, "pi": {"extensions": list(entries)}})
    write_json(base / "npm/package.json", {"private": True, "dependencies": {name: version}})
    for entry in entries:
        path = root / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("throw new Error('Toolkit must never execute this extension');")
    if configured:
        write_json(base / "settings.json", {"packages": [f"npm:{name}@{version}"]})
    return root


def display_state(identity, global_enabled=False, project_enabled=False):
    """Complete renderer-only state. Apply tests use real seed_package + Pi."""
    from agent_toolkit_cli.pi_npm import NpmState, NpmScope
    root = Path("/tmp/pi-npm-renderer") / identity
    entry = root / "index.ts"
    source = "npm:" + identity
    metadata = {"name": identity, "version": "1.0.0", "pi": {"extensions": ["index.ts"]}}
    shared = dict(source=source, root=root, version="1.0.0", metadata=metadata,
                  compatible=True, configured=True, resources=(entry,))
    global_scope = NpmScope(**shared, record=source if global_enabled else {"source": source, "extensions": []},
                           entries=((entry, global_enabled),), mode="owned", scope_root=root,
                           scope_version="1.0.0", scope_compatible=True)
    differs = global_enabled != project_enabled
    record = {"source": source, "autoload": False, "extensions": ["+index.ts" if project_enabled else "-index.ts"]} if differs else None
    project_scope = NpmScope(**shared, record=record, entries=((entry, project_enabled),), mode="override" if differs else "inherit")
    return NpmState(identity, global_scope, project_scope, f"renderer-{identity}-{global_enabled}-{project_enabled}")

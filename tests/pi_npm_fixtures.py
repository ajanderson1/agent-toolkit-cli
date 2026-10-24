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

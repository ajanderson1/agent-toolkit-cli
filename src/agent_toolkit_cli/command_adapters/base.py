from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Protocol

from agent_toolkit_cli._install_core import InstallError

Scope = Literal["global", "project"]


class CommandAdapter(Protocol):
    name: str
    def destination(self, slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path: ...
    def install(self, slug: str, source_file: Path, *, scope: Scope, home: Path | None, project: Path | None) -> Path: ...
    def uninstall(self, slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path | None: ...


def ensure_regular_command_file(source_file: Path) -> None:
    if source_file.is_symlink() or not source_file.is_file():
        raise InstallError(f"{source_file}: COMMAND.md must be a regular file")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sidecar_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".attk")


def write_sidecar(dest: Path, *, slug: str, harness: str, scope: str, canonical: Path, content: str) -> None:
    sidecar_path(dest).write_text(json.dumps({
        "tool": "agent-toolkit-cli",
        "asset_type": "command",
        "slug": slug,
        "harness": harness,
        "scope": scope,
        "canonical": str(canonical),
        "sha256": sha256_text(content),
    }, indent=2, sort_keys=True) + "\n")


def read_sidecar(dest: Path) -> dict | None:
    p = sidecar_path(dest)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def is_managed_file(dest: Path, *, slug: str, harness: str, content: str | None = None) -> bool:
    meta = read_sidecar(dest)
    if not meta:
        return False
    if meta.get("tool") != "agent-toolkit-cli" or meta.get("asset_type") != "command":
        return False
    if meta.get("slug") != slug or meta.get("harness") != harness:
        return False
    if content is not None and meta.get("sha256") != sha256_text(content):
        return False
    return True


def remove_managed_file(dest: Path, *, slug: str, harness: str) -> Path | None:
    if not dest.exists() and not dest.is_symlink():
        sidecar_path(dest).unlink(missing_ok=True)
        return None
    if is_managed_file(dest, slug=slug, harness=harness):
        dest.unlink(missing_ok=True)
        sidecar_path(dest).unlink(missing_ok=True)
        return dest
    return None

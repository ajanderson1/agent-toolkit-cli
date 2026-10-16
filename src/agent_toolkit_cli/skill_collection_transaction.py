"""Targeted, ownership-checked journal for collection projection changes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from agent_toolkit_cli import skill_lock
from agent_toolkit_cli.skill_install import InstallError


def link_state(path: Path) -> Path | None:
    if path.is_symlink():
        return path.readlink()
    if path.exists():
        raise InstallError(f"Ownership conflict: {path} is not a symlink")
    return None


def document(path: Path) -> dict:
    if not path.exists():
        return {"version": skill_lock.CURRENT_VERSION, "skills": {}}
    try:
        raw = json.loads(path.read_text())
        if (
            not isinstance(raw, dict)
            or raw.get("version") not in skill_lock.SUPPORTED_VERSIONS
        ):
            raise ValueError("unsupported lock document")
        if not isinstance(raw.get("skills"), dict):
            raise ValueError("invalid skills mapping")
        return raw
    except (OSError, ValueError) as exc:
        raise InstallError(f"Cannot safely read {path}: {exc}") from exc


def checked_lock(path: Path) -> skill_lock.LockFile:
    document(path)
    return skill_lock.read_lock(path)


def commit_document(path: Path, raw: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize only affected records; write_lock would refresh every v3 timestamp.
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as f:
        tmp = Path(f.name)
        try:
            f.write(json.dumps(raw, indent=2) + "\n")
            f.flush()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def patch(path: Path, expected: dict, values: dict) -> None:
    raw = document(path)
    if any(raw["skills"].get(k) != v for k, v in expected.items()):
        raise InstallError(f"Affected record ownership changed: {path}")
    for key, entry in values.items():
        if entry is None:
            raw["skills"].pop(key, None)
        else:
            raw["skills"][key] = entry
    commit_document(path, raw)


class Journal:
    def __init__(self) -> None:
        self.links: list[tuple[Path, Path | None, Path | None]] = []
        self.records: list[tuple[Path, dict, dict]] = []
        self.guards: list[tuple[Path, dict]] = []
        self.parents: dict[Path, Path] = {}

    def expect(self, path: Path, records: dict) -> None:
        self.guards.append((path, records))

    def expect_paths(self, paths) -> None:
        self.parents.update({p: p.parent.resolve() for p in paths})

    def link(self, path: Path, before: Path | None, after: Path | None) -> None:
        if path in self.parents and path.parent.resolve() != self.parents[path]:
            raise InstallError(f"Projection parent ownership changed: {path.parent}")
        for lock_path, expected in self.guards:
            lock = checked_lock(lock_path)
            if any(lock.skills.get(k) != v for k, v in expected.items()):
                raise InstallError(
                    f"Affected record ownership changed before link write: {lock_path}"
                )
        if link_state(path) != before:
            raise InstallError(f"Ownership changed immediately before write: {path}")
        if before == after:
            return
        self.links.append((path, before, after))
        if before is not None:
            path.unlink()
        if after is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path in self.parents and path.parent.resolve() != self.parents[path]:
                raise InstallError(
                    f"Projection parent ownership changed: {path.parent}"
                )
            if link_state(path) is not None:
                raise InstallError(
                    f"Ownership changed immediately before create: {path}"
                )
            path.symlink_to(after)

    def write(self, path: Path, before: dict, after: dict) -> None:
        lock = checked_lock(path)
        if any(lock.skills.get(k) != v for k, v in before.items()):
            raise InstallError(f"Affected record ownership changed: {path}")
        if before == after:
            return
        raw = document(path)
        serialize = (
            skill_lock._entry_to_dict_v3
            if raw["version"] == 3
            else skill_lock._entry_to_dict_v1
        )
        old = {k: raw["skills"].get(k) for k in before}
        new = {k: (serialize(v) if v is not None else None) for k, v in after.items()}
        self.records.append((path, old, new))
        patch(path, old, new)

    def rollback(self) -> list[str]:
        errors: list[str] = []
        for path, before, after in reversed(self.records):
            try:
                raw = document(path)
                current = {k: raw["skills"].get(k) for k in before}
                if current == before:
                    continue
                if current != after:
                    raise InstallError(f"affected record recovery conflict: {path}")
                patch(path, after, before)
            except (OSError, InstallError) as exc:
                errors.append(str(exc))
        for path, before, after in reversed(self.links):
            try:
                current = link_state(path)
                if current == before:
                    continue
                if current != after:
                    raise InstallError(f"link recovery conflict: {path} -> {current}")
                Journal().link(path, current, before)
            except (OSError, InstallError) as exc:
                errors.append(str(exc))
        return errors

    def fail(self, exc: Exception) -> InstallError:
        errors = self.rollback()
        suffix = (
            ("; RECOVERY FAILED: " + "; ".join(errors))
            if errors
            else "; targeted changes rolled back"
        )
        return InstallError(f"{exc}{suffix}")

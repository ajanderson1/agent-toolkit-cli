"""Optional live Git catalog. Listings never serve as an offline cache."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

from agent_toolkit_cli.behavior import _read_config
from agent_toolkit_cli.skill_git import _scrub
from agent_toolkit_cli.skill_source import ParsedSource, parse_source, sanitize_ref


@dataclass(frozen=True)
class CatalogSkill:
    key: str
    description: str
    source: ParsedSource


@dataclass(frozen=True)
class CatalogSnapshot:
    url: str
    revision: str = ""
    skills: tuple[CatalogSkill, ...] = ()
    error: str | None = None
    ref: str | None = None


def write_json(path: Path, value: dict) -> None:
    """Atomic small-state replacement, retaining symlink targets and file mode."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            os.chmod(tmp, mode)
            json.dump(value, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def safe_source(value: str) -> ParsedSource:
    if not isinstance(value, str) or not value or value.startswith("-"):
        raise ValueError("expected a Git source")
    parts = urlsplit(value)
    if parts.password or (parts.scheme in {"http", "https"} and parts.username) or parts.query or parts.fragment:
        raise ValueError("Git sources must not contain credentials, queries or fragments")
    return parse_source(value)


def parse_catalog(data: dict) -> tuple[CatalogSkill, ...]:
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("unsupported catalog version (expected 1)")
    if not isinstance(data.get("skills"), list):
        raise ValueError("catalog skills must be an array")
    skills: list[CatalogSkill] = []
    seen: set[str] = set()
    for item in data["skills"]:
        if not isinstance(item, dict):
            raise ValueError("catalog entry must be an object")
        key = item.get("key")
        description = item.get("description")
        path = item.get("path")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) or len(key) > 64 or key in seen:
            raise ValueError("invalid or duplicate catalog key")
        if not isinstance(description, str) or not description.strip() or len(description) > 1024:
            raise ValueError("catalog description must be nonempty and at most 1024 characters")
        if not isinstance(path, str) or not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or "\\" in path:
            raise ValueError("catalog path must be a safe repository-relative directory")
        source = safe_source(item.get("source"))
        if source.subpath is not None or source.skill_name is not None:
            raise ValueError("catalog source must be a repository; select its directory with path")
        ref = item.get("ref")
        if ref is not None:
            if not isinstance(ref, str):
                raise ValueError("catalog ref must be a string")
            ref = sanitize_ref(ref)
        skills.append(CatalogSkill(key, description.strip(), replace(source, subpath=PurePosixPath(path).as_posix(), ref=ref)))
        seen.add(key)
    return tuple(skills)


def run_git(args: list[str], *, cwd: Path | None = None) -> str:
    """Bounded, noninteractive Git for discovery/checking, never skill execution."""
    env = _scrub(None)
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    # Respect normal SSH routing/keys, but never wait for a password/host prompt.
    env["GIT_SSH_COMMAND"] = env.get("GIT_SSH_COMMAND", "ssh") + " -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes"
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=15)
    if result.returncode:
        # Git stderr may repeat authentication material from user configuration.
        raise ValueError("Git catalog/upstream request failed; check access, source and ref")
    return result.stdout.strip()


def fetch_catalog(url: str, ref: str | None = None) -> CatalogSnapshot:
    try:
        if ref is not None and not isinstance(ref, str):
            raise ValueError("catalog ref must be a string")
        parsed = safe_source(url)
        if parsed.subpath or parsed.skill_name:
            raise ValueError("catalog source must be a repository")
        selected = sanitize_ref(ref) if ref is not None else "HEAD"
        with tempfile.TemporaryDirectory(prefix="toolkit-catalog-") as tmp:
            root = Path(tmp)
            run_git(["init", "--bare", "--quiet"], cwd=root)
            run_git(["fetch", "--quiet", "--depth=1", "--", parsed.url, selected], cwd=root)
            revision = run_git(["rev-parse", "FETCH_HEAD"], cwd=root)
            body = run_git(["show", "FETCH_HEAD:catalog.json"], cwd=root)
            return CatalogSnapshot(url, revision, parse_catalog(json.loads(body)), ref=ref)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        message = "catalog request timed out" if isinstance(exc, subprocess.TimeoutExpired) else "catalog unavailable or invalid; check access and catalog.json"
        return CatalogSnapshot("(invalid source)" if _has_credentials(url) else url, error=message)


def _has_credentials(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return bool(parts.password or (parts.scheme in {"http", "https"} and parts.username))
    except ValueError:
        return True


def read_catalog(*, home: Path | None = None) -> CatalogSnapshot | None:
    try:
        config = _read_config(home).get("skillCatalog")
        if config is None:
            return None
        if not isinstance(config, dict) or not isinstance(config.get("url"), str) or (config.get("ref") is not None and not isinstance(config["ref"], str)):
            raise ValueError("invalid subscription")
        return fetch_catalog(config["url"], config.get("ref"))
    except (ValueError, OSError, RuntimeError):
        return CatalogSnapshot("(configuration)", error="invalid skill catalog subscription")


def configure_catalog(url: str | None, ref: str | None = None, *, home: Path | None = None) -> None:
    path = (home or Path.home()) / ".agent-toolkit/config.json"
    if url is None:
        config = _read_config(home)
        if "skillCatalog" in config:
            del config["skillCatalog"]
            write_json(path, config)
        return
    snapshot = fetch_catalog(url, ref)
    if snapshot.error:
        raise ValueError(snapshot.error)
    config = _read_config(home)
    config["skillCatalog"] = {"url": url, "ref": ref}
    write_json(path, config)

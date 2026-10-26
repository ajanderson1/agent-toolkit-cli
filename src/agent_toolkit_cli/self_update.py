"""Toolkit package updates (not asset updates), shared by CLI and TUI.

Only explicit updates build or replace anything. Startup checks are best-effort,
cache GitHub's stable release metadata, and never require Git or uv.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from email.parser import BytesParser
import hashlib
from http.client import HTTPException
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote, urldefrag
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from packaging.version import InvalidVersion, Version

REPOSITORY = "https://github.com/ajanderson1/agent-toolkit-cli"
API = "https://api.github.com/repos/ajanderson1/agent-toolkit-cli"
CACHE_SECONDS = 6 * 60 * 60
RETRY_SECONDS = 15 * 60
STARTUP_TIMEOUT = 1.0
EXPLICIT_TIMEOUT = 10.0
MAX_RESPONSE_BYTES = 1024 * 1024


class UpdateError(Exception):
    """An explicit check or update could not safely complete."""


@dataclass(frozen=True)
class Release:
    tag: str
    version: str


def installed_version() -> str:
    try:
        return metadata.version("agent-toolkit")
    except metadata.PackageNotFoundError:
        return "unknown"


def cache_path() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "agent-toolkit" / "update.json"


def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "agent-toolkit" / "updates"


def checks_disabled() -> bool:
    return os.environ.get("AGENT_TOOLKIT_NO_UPDATE_CHECK", "").lower() in {"1", "true", "yes"}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, RecursionError):
        return {}


def _write_json(path: Path, value: dict) -> None:
    """Atomic replacement, including when CLI and TUI check concurrently."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _api_json(endpoint: str, timeout: float) -> dict:
    request = Request(
        f"{API}/{endpoint}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "agent-toolkit-update"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (OSError, ValueError, HTTPException, RecursionError) as exc:
        raise UpdateError(f"Could not check GitHub for updates: {exc}") from exc


def _release(value: dict) -> Release:
    tag = value.get("tag_name")
    # ReleasePlease ships stable vMAJOR.MINOR.PATCH tags. Never interpolate
    # arbitrary API/cache content into Git commands or terminal output.
    if not isinstance(tag, str) or len(tag) > 64 or not re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise UpdateError("GitHub did not return a stable release tag.")
    if value.get("draft") or value.get("prerelease"):
        raise UpdateError("GitHub did not return a published stable release.")
    return Release(tag, str(Version(tag)))


def latest_release(*, force: bool = False, timeout: float = EXPLICIT_TIMEOUT) -> Release | None:
    """Failures are raised explicitly, but cached/backed off for startup callers."""
    path = cache_path()
    cached = _read_json(path)
    now = time.time()
    try:
        release = _release({"tag_name": cached.get("tag")})
    except (UpdateError, InvalidVersion):
        release = None
    checked_at = cached.get("checked_at")
    ttl = RETRY_SECONDS if cached.get("failed") else CACHE_SECONDS
    if not force and isinstance(checked_at, (float, int)) and 0 <= now - checked_at < ttl:
        return release
    try:
        release = _release(_api_json("releases/latest", timeout))
    except UpdateError:
        try:
            _write_json(path, {"checked_at": now, "tag": release.tag if release else None, "failed": True})
        except OSError:
            pass
        if force:
            raise
        return release
    try:
        _write_json(path, {"checked_at": now, "tag": release.tag, "failed": False})
    except OSError:
        pass
    return release


def is_newer(release: Release) -> bool:
    try:
        return Version(release.version) > Version(installed_version())
    except InvalidVersion:
        return False


def startup_notice() -> str | None:
    if checks_disabled():
        return None
    release = latest_release(timeout=STARTUP_TIMEOUT)
    if release and is_newer(release):
        return f"New update available: {installed_version()} → {release.version}. Run `atc update` to update."
    return None


def cli_startup_notice(args: tuple[str, ...]) -> None:
    """Keep pipes, JSON, help, completion and explicit update output pristine."""
    if not sys.stdout.isatty() or not sys.stderr.isatty():
        return
    if any(arg in {"update", "completion", "--json", "--format", "--help", "-h", "--version", "-V"}
           or arg.startswith(("--json=", "--format=")) for arg in args):
        return
    notice = startup_notice()
    if notice:
        import click
        click.echo(notice, err=True)


def resolve_commit(ref: str) -> str:
    value = _api_json(f"commits/{quote(ref, safe='')}", EXPLICIT_TIMEOUT)
    sha = value.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise UpdateError("GitHub returned an invalid source commit.")
    return sha


def _matches_installed_wheel(dist: metadata.Distribution, wheel: Path, sha256: str) -> bool:
    """uv omits archive hashes for local wheels: verify retained + installed bytes."""
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != sha256:
        return False
    with ZipFile(wheel) as archive:
        for name in archive.namelist():
            # Installers rewrite RECORD to include generated scripts/direct_url.
            if name.endswith("/") or name.endswith(".dist-info/RECORD"):
                continue
            if dist.locate_file(name).read_bytes() != archive.read(name):
                return False
    return True


def installed_commit() -> str | None:
    """Use installed provenance, never a version string or an unrelated receipt."""
    try:
        dist = metadata.distribution("agent-toolkit")
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        if direct.get("url", "").removesuffix(".git") == REPOSITORY:
            commit = direct.get("vcs_info", {}).get("commit_id")
            if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit):
                return commit
        # Our locally built wheel has a durable path. Match its installed hash
        # and URL to the adjacent receipt, not simply the most recent attempt.
        for receipt_path in state_dir().resolve().glob("*/receipt.json"):
            receipt = _read_json(receipt_path)
            wheel = receipt_path.parent / receipt.get("wheel", "")
            archive_info = direct.get("archive_info", {})
            installed_hash = archive_info.get("hashes", {}).get("sha256")
            if installed_hash is None and archive_info.get("hash", "").startswith("sha256="):
                installed_hash = archive_info["hash"].removeprefix("sha256=")
            expected_hash = receipt.get("wheel_sha256")
            if (urldefrag(direct.get("url", ""))[0] == wheel.as_uri()
                    and receipt.get("repository") == REPOSITORY
                    and isinstance(expected_hash, str)
                    and ((installed_hash is not None and installed_hash == expected_hash)
                         or (installed_hash is None and _matches_installed_wheel(dist, wheel, expected_hash)))):
                commit = receipt.get("commit")
                if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit):
                    return commit
    except (metadata.PackageNotFoundError, OSError, ValueError, TypeError, AttributeError, BadZipFile):
        pass
    return None


def _run(args: list[str], *, cwd: Path, timeout: int = 600) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.pop("VIRTUAL_ENV", None)
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        detail = (getattr(exc, "stderr", None) or str(exc))
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        raise UpdateError(f"{args[0]} failed: {detail[-4000:]}") from exc


def require_uv_install() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise UpdateError("Self-update requires uv. Install with `uv tool install --from git+" + REPOSITORY + " agent-toolkit`.")
    root = Path(_run([uv, "--no-config", "tool", "dir"], cwd=Path.home(), timeout=10))
    try:
        dist = metadata.distribution("agent-toolkit")
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        editable = direct.get("dir_info", {}).get("editable", False)
        managed = Path(sys.prefix).resolve() == (root / "agent-toolkit").resolve()
        if not managed or editable or (dist.read_text("INSTALLER") or "").strip() != "uv":
            raise UpdateError("Self-update only supports non-editable `uv tool` installations. This environment was not changed. Update it with its original package manager; for development use `git pull` and `uv sync`.")
    except (metadata.PackageNotFoundError, OSError, ValueError, TypeError, AttributeError) as exc:
        raise UpdateError("Cannot identify this installation; refusing to replace it.") from exc
    return uv


@contextmanager
def _update_lock():
    root = state_dir().resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".update-lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise UpdateError(f"Another update may be running. If it was interrupted, remove {lock} and retry.") from exc
    try:
        yield root
    finally:
        lock.rmdir()


def _wheel_version(wheel: Path) -> str:
    try:
        with ZipFile(wheel) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise UpdateError("Built wheel has ambiguous package metadata.")
            info = BytesParser().parsebytes(archive.read(names[0]))
            if info["Name"] != "agent-toolkit" or not info["Version"]:
                raise UpdateError("Built wheel is not agent-toolkit.")
            return str(Version(info["Version"]))
    except (BadZipFile, InvalidVersion) as exc:
        raise UpdateError(f"Built wheel is invalid: {exc}") from exc


def perform_update(*, main: bool = False) -> Path | None:
    """Build a verified canonical commit in isolation, retain its receipt, use uv.

    No checkout belonging to the operator is fetched, reset, or modified.
    """
    uv = require_uv_install()
    release = None if main else latest_release(force=True)
    if release and not is_newer(release):
        return None
    commit = resolve_commit("main" if main else release.tag)
    if main and installed_commit() == commit:
        return None
    with _update_lock() as root:
        with tempfile.TemporaryDirectory(prefix="agent-toolkit-update-") as temp:
            work = Path(temp)
            source = work / "source"
            git = shutil.which("git")
            if not git:
                raise UpdateError("Git is required to build updates from the canonical repository.")
            _run([git, "init", str(source)], cwd=work)
            _run([git, "-C", str(source), "-c", f"core.hooksPath={os.devnull}", "fetch", "--depth=1", REPOSITORY + ".git", commit], cwd=work)
            fetched = _run([git, "-C", str(source), "rev-parse", "FETCH_HEAD"], cwd=work)
            if fetched != commit:
                raise UpdateError("Fetched source does not match the resolved canonical commit.")
            _run([git, "-C", str(source), "-c", f"core.hooksPath={os.devnull}", "checkout", "--detach", commit], cwd=work)
            output = work / "dist"
            _run([uv, "--no-config", "build", "--wheel", "--no-sources", "--out-dir", str(output), str(source)], cwd=work)
            wheels = list(output.glob("*.whl"))
            if len(wheels) != 1:
                raise UpdateError("Build did not produce exactly one wheel.")
            version = _wheel_version(wheels[0])
            if release and version != release.version:
                raise UpdateError("Built wheel version does not match the selected release.")
            artifact_dir = Path(tempfile.mkdtemp(prefix=f"{commit[:12]}-", dir=root))
            wheel = artifact_dir / wheels[0].name
            shutil.copyfile(wheels[0], wheel)
            receipt = artifact_dir / "receipt.json"
            wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
            _write_json(receipt, {
                "repository": REPOSITORY, "commit": commit,
                "ref": "main" if main else release.tag, "version": version,
                "wheel": wheel.name, "wheel_sha256": wheel_sha256,
                "built_at": time.time(),
            })
            # Build finishes before replacement; dependencies are resolved by uv.
            # Keep the wheel for provenance and subsequent uv operations.
            _run([uv, "--no-config", "tool", "install", "--reinstall-package", "agent-toolkit", "--python", sys._base_executable,
                  "--from", f"agent-toolkit @ {wheel.as_uri()}#sha256={wheel_sha256}", "agent-toolkit"], cwd=work)
            return receipt

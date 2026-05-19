"""Shell-out wrapper around ``pi install`` / ``pi remove``.

The toolkit owns the config edit (settings.json + allowlist YAML); this
module only handles the fetch step — populating
``~/.pi/agent/npm/node_modules/`` (user) or ``<project>/.pi/npm/node_modules/``
(project). We isolate the subprocess call in one module so tests can
monkeypatch ``subprocess.run`` without touching CLI code.

Scope flag (Task 3.1 finding, 2026-05-19):
    ``pi install --help`` advertises only ``-l/--local`` (install into
    ``.pi/settings.json`` for project scope). There is no ``--scope=project``
    flag — the plan's placeholder was a guess. We use ``-l`` for project
    scope and bare ``pi install`` for user scope, in both cases also setting
    ``cwd`` to the appropriate directory so any path-relative resolution Pi
    performs stays correct.

If ``pi`` is not on PATH → :class:`PiNotFoundError`. Callers surface this
as an actionable CLI error.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class PiNotFoundError(RuntimeError):
    """Raised when the ``pi`` binary is not on PATH."""


def _build_install_cmd(source: str, scope: str) -> list[str]:
    cmd = ["pi", "install", source]
    if scope == "project":
        cmd.append("--local")
    return cmd


def _build_remove_cmd(source: str, scope: str) -> list[str]:
    cmd = ["pi", "remove", source]
    if scope == "project":
        cmd.append("--local")
    return cmd


def _resolve_cwd(scope: str, home: Path, project_root: Path) -> Path:
    return project_root if scope == "project" else home


def fetch_package(
    source: str, *, scope: str, home: Path, project_root: Path
) -> None:
    """Invoke ``pi install`` to populate node_modules for SOURCE.

    Raises :class:`PiNotFoundError` if ``pi`` is missing from PATH and
    :class:`RuntimeError` (with stderr embedded) on a non-zero exit.
    """
    try:
        result = subprocess.run(
            _build_install_cmd(source, scope),
            capture_output=True,
            text=True,
            cwd=str(_resolve_cwd(scope, home, project_root)),
        )
    except FileNotFoundError as exc:
        raise PiNotFoundError("`pi` binary not on PATH") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"pi install failed (exit {result.returncode}): "
            f"{(result.stderr or '').strip()}"
        )


def remove_package_fetched(
    source: str, *, scope: str, home: Path, project_root: Path
) -> None:
    """Invoke ``pi remove`` to purge node_modules for SOURCE.

    Raises :class:`PiNotFoundError` if ``pi`` is missing from PATH and
    :class:`RuntimeError` (with stderr embedded) on a non-zero exit. Callers
    decide whether to treat either as fatal.
    """
    try:
        result = subprocess.run(
            _build_remove_cmd(source, scope),
            capture_output=True,
            text=True,
            cwd=str(_resolve_cwd(scope, home, project_root)),
        )
    except FileNotFoundError as exc:
        raise PiNotFoundError("`pi` binary not on PATH") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"pi remove failed (exit {result.returncode}): "
            f"{(result.stderr or '').strip()}"
        )

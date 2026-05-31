"""Packaging guard for `instructions list` (#305).

The harness matrix is the human-facing SSOT at docs/agent-toolkit/harness-matrix.md.
`instructions list` reads it at runtime. On a packaged install the repo's docs/
tree is gone, so the matrix MUST be force-included into the wheel as package data
(see pyproject.toml [tool.hatch.build.targets.wheel.force-include]). Before #305
nothing tested the packaged path: CI ran from the source tree where the
repo-relative fallback masked the bug, so a wheel that shipped no matrix passed
CI and crashed for every real user.

These tests build an actual wheel via the project's build backend and assert the
matrix is bundled byte-identically with the SSOT. Drop the force-include block and
`test_wheel_bundles_harness_matrix` goes red — which is exactly the regression that
shipped in #305.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SSOT = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"
_WHEEL_MEMBER = "agent_toolkit_cli/data/harness-matrix.md"


def _build_wheel(out_dir: Path) -> Path:
    """Build a wheel into out_dir with `uv build`, the project's build driver.

    uv is the canonical tool for this repo (CI provisions it via setup-uv) and
    drives the hatchling backend without needing `build`/`hatchling` importable
    in the test venv. Skips (rather than fails) if uv is absent or the build
    can't run in the sandbox; when it does build, the asserts below are hard.
    """
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - env without uv on PATH
        pytest.skip("uv not on PATH; cannot build a wheel to check packaging")
    proc = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:  # pragma: no cover - sandbox/network constraints
        pytest.skip(f"wheel build failed (likely sandbox/network):\n{proc.stderr[-2000:]}")
    wheels = sorted(out_dir.glob("*.whl"))
    assert wheels, f"build produced no wheel: {proc.stdout}\n{proc.stderr}"
    return wheels[-1]


def test_wheel_bundles_harness_matrix(tmp_path):
    """The built wheel ships the matrix as package data, byte-identical to the SSOT.

    This is the test that would have caught #305: remove the force-include block
    from pyproject.toml and this assertion fails.
    """
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        assert _WHEEL_MEMBER in names, (
            f"{_WHEEL_MEMBER} missing from wheel — instructions list will crash on "
            f"packaged installs (#305). Wheel members: "
            f"{[n for n in names if 'data' in n or 'harness' in n]}"
        )
        wheel_bytes = zf.read(_WHEEL_MEMBER)
    assert wheel_bytes == _SSOT.read_bytes(), (
        "bundled harness-matrix.md differs from the docs/ SSOT — the wheel must "
        "ship the SSOT verbatim, not a copy"
    )


def test_instructions_list_runs_from_installed_wheel(tmp_path):
    """`instructions list` exits 0 from a real install, invoked outside the repo.

    Running from tmp_path (not the repo) means the source-tree fallback cannot
    fire, so success proves the packaged-resource path works — the actual #305 fix.
    """
    wheel = _build_wheel(tmp_path / "dist")
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, timeout=120)
    bindir = "Scripts" if sys.platform == "win32" else "bin"
    py = venv / bindir / ("python.exe" if sys.platform == "win32" else "python")
    pip = subprocess.run(
        [str(py), "-m", "pip", "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if pip.returncode != 0:  # pragma: no cover - sandbox/network constraints
        pytest.skip(f"pip install of wheel failed (likely sandbox/network):\n{pip.stderr[-2000:]}")

    cli = venv / bindir / "agent-toolkit-cli"
    for args in (["instructions", "list"], ["instructions", "list", "--format", "json"]):
        run = subprocess.run(
            [str(cli), *args],
            capture_output=True,
            text=True,
            cwd=tmp_path,  # outside the repo: no source-tree fallback possible
            timeout=60,
        )
        assert run.returncode == 0, f"{args} exited {run.returncode}: {run.stderr}"
        assert "claude-code" in run.stdout, f"{args} output missing claude-code: {run.stdout[:500]}"

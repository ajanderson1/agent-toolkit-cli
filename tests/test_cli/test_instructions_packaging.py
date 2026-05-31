"""Packaging guard for `instructions list` (#305).

The harness matrix is the human-facing SSOT at docs/agent-toolkit/harness-matrix.md.
`instructions list` reads it at runtime. On a packaged install the repo's docs/
tree is gone, so the matrix MUST be force-included into the wheel as package data
(see pyproject.toml [tool.hatch.build.targets.wheel.force-include]). Before #305
nothing tested the packaged path: CI ran from the source tree where the
repo-relative fallback masked the bug, so a wheel that shipped no matrix passed
CI and crashed for every real user.

These tests build real artifacts via the project's build driver and assert the
matrix survives packaging:

- the wheel ships it byte-identically with the SSOT (drop the force-include block
  and `test_wheel_bundles_harness_matrix` goes red — exactly the #305 regression);
- the sdist retains docs/ so the sdist→wheel rebuild can still find it;
- a real installed CLI, invoked from outside the repo, prints the matrix.

Skip-policy: only skip when the build *driver* is unavailable (uv not on PATH).
A build/install that actually runs and FAILS is a hard failure — a guard that
skip-greens on its own subject would be worthless (#305 review).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SSOT = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"
_WHEEL_MEMBER = "agent_toolkit_cli/data/harness-matrix.md"
_SDIST_DOC_SUFFIX = "docs/agent-toolkit/harness-matrix.md"


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - env without uv on PATH
        pytest.skip("uv not on PATH; cannot build artifacts to check packaging")
    return uv


def _build(target: str, out_dir: Path, glob: str) -> Path:
    """Build a wheel or sdist into out_dir with `uv build`.

    Skips only when uv is absent. If uv runs and the build returns non-zero, that
    is a hard failure: the build is the thing under test, so a broken build must
    not skip-green past the guard.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [_uv(), "build", f"--{target}", "--out-dir", str(out_dir)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"uv build --{target} failed (rc={proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    artifacts = sorted(out_dir.glob(glob))
    assert artifacts, f"build produced no {glob}: {proc.stdout}\n{proc.stderr}"
    return artifacts[-1]


def test_wheel_bundles_harness_matrix(tmp_path):
    """The built wheel ships the matrix as package data, byte-identical to the SSOT.

    This is the test that would have caught #305: remove the force-include block
    from pyproject.toml and this assertion fails.
    """
    wheel = _build("wheel", tmp_path, "*.whl")
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


def test_sdist_retains_matrix_for_wheel_rebuild(tmp_path):
    """The sdist keeps docs/agent-toolkit/harness-matrix.md.

    `pip install <sdist>` rebuilds the wheel, whose force-include reads the matrix
    from docs/. If a future include/exclude trims docs/ out of the sdist, that
    rebuild produces a matrix-less wheel and the #305 crash returns for sdist
    consumers — while the wheel-only test above stays green. This pins the
    sdist→wheel coupling.
    """
    sdist = _build("sdist", tmp_path, "*.tar.gz")
    with tarfile.open(sdist) as tf:
        members = tf.getnames()
    assert any(m.endswith(_SDIST_DOC_SUFFIX) for m in members), (
        f"{_SDIST_DOC_SUFFIX} missing from sdist — a wheel rebuilt from this sdist "
        f"cannot force-include the matrix (#305)."
    )


def test_instructions_list_runs_from_installed_wheel(tmp_path):
    """`instructions list` exits 0 from a real install, invoked outside the repo.

    Running with cwd outside the repo means the source-tree fallback cannot fire,
    so success proves the packaged-resource path works — the actual #305 fix. We
    assert the install genuinely can't see a repo doc (belt-and-braces: if the
    fallback could ever satisfy the command, this test would be testing the wrong
    path).
    """
    wheel = _build("wheel", tmp_path / "dist", "*.whl")
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
    assert pip.returncode == 0, f"pip install of the wheel failed:\n{pip.stderr}"

    # cwd is a tmp dir with no docs/ tree, so the parents[4] source-tree fallback
    # resolves to a non-existent path: the command can only succeed via the
    # packaged resource.
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()
    assert not (workdir / "docs").exists()

    cli = venv / bindir / "agent-toolkit-cli"
    for args in (["instructions", "list"], ["instructions", "list", "--format", "json"]):
        run = subprocess.run(
            [str(cli), *args],
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=60,
        )
        assert run.returncode == 0, f"{args} exited {run.returncode}: {run.stderr}"
        assert "claude-code" in run.stdout, f"{args} output missing claude-code: {run.stdout[:500]}"

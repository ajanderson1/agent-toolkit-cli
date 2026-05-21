"""Smoke test: `npx skills ls` can read a lock file written by us.

Skipped if `npx` is not on PATH. Network access required (npx fetches the
`skills` package). Skipped if AGENT_TOOLKIT_SKIP_INTEROP=1 is set, which
CI can use to opt out without removing the test.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main

_HAVE_NPX = shutil.which("npx") is not None
_SKIP_INTEROP = os.environ.get("AGENT_TOOLKIT_SKIP_INTEROP") == "1"
skip_no_npx = pytest.mark.skipif(
    not _HAVE_NPX or _SKIP_INTEROP,
    reason="npx not on PATH (or AGENT_TOOLKIT_SKIP_INTEROP=1)",
)


@skip_no_npx
def test_npx_skills_list_reads_our_lock(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("DISABLE_TELEMETRY", "1")

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])

    # Upstream `npx skills` reads ~/.agents/.skill-lock.json for the global
    # lock. We wrote the same file to the same path.
    proc = subprocess.run(
        ["npx", "--yes", "skills@latest", "ls", "-g"],
        capture_output=True, text=True,
        env={
            **git_sandbox.env,
            "HOME": str(fake_home),
            "DISABLE_TELEMETRY": "1",
            "PATH": os.environ.get("PATH", ""),
        },
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"npx skills ls failed (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "demo" in proc.stdout, (
        f"upstream CLI did not list our skill\nstdout:\n{proc.stdout}"
    )

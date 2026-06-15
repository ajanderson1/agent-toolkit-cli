"""Guard: the mcp command group works from a built wheel, run outside the repo.

Mirrors the #305 packaged-resource regression guard. The mcp kind derives its
library root from `home` (~/.agent-toolkit/mcps/), never relative to __file__,
so it SHOULD be immune to the parents[N]-walk crash that #305 inflicted on
instructions list. This test PROVES it: build the wheel, install it into an
isolated venv OUTSIDE the source tree, then run `mcp install` with an isolated
HOME and assert .mcp.json is written.

Skip-policy: skip ONLY when uv is absent (via the _uv helper, never
@pytest.mark.skipif) — a build/install that actually runs and FAILS must be a
hard failure, never a skip-green. A guard that skip-greens on its own subject
would be worthless (#305 review).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _uv(*args: str, **kwargs):
    """Run a uv command; skip the test only if uv itself is unavailable."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")
    return subprocess.run(["uv", *args], check=True, **kwargs)


def test_mcp_install_from_wheel(tmp_path):
    # Build the wheel
    dist = tmp_path / "dist"
    _uv("build", "--wheel", "-o", str(dist), cwd=REPO)
    wheel = next(dist.glob("*.whl"))

    # Install into an isolated venv OUTSIDE the repo tree
    venv = tmp_path / "venv"
    _uv("venv", str(venv))
    bin_dir = venv / ("Scripts" if (venv / "Scripts").exists() else "bin")
    _uv("pip", "install", "--python", str(bin_dir / "python"), str(wheel))

    # Seed a library entry under the isolated HOME, entirely outside the repo
    library = tmp_path / ".agent-toolkit" / "mcps"
    d = library / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","demo@1.0.0"]}\n'
    )
    (d / "README.md").write_text("# demo\n")
    (library / "demo.toolkit.yaml").write_text(
        "name: demo\ndescription: x.\ntransport: stdio\n"
        "install_method: npx\nresolved_version: 1.0.0\n"
    )
    project = tmp_path / "proj"
    project.mkdir()

    # PATH = bin_dir first, then the inherited PATH so the wheel's console
    # script can still resolve its own interpreter. HOME is isolated so the
    # library + lock live entirely outside the repo.
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
    }
    r = subprocess.run(
        [
            str(bin_dir / "agent-toolkit-cli"),
            "mcp",
            "install",
            "demo",
            "--harness",
            "claude-code",
            "-p",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads((project / ".mcp.json").read_text())
    assert "demo" in doc["mcpServers"]

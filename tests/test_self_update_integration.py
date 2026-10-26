"""Exercise the real uv replacement in a disposable tool directory and HOME."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable paths in disposable uv smoke")
def test_real_uv_self_replacement(tmp_path):
    uv = shutil.which("uv")
    git = shutil.which("git")
    if not uv or not git:
        pytest.skip("uv and git required")
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    home = tmp_path / "home"
    home.mkdir()
    env.update({
        "HOME": str(home), "USERPROFILE": str(home),
        "UV_TOOL_DIR": str(tmp_path / "tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "bin"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "AGENT_TOOLKIT_NO_UPDATE_CHECK": "1",
    })
    env.pop("VIRTUAL_ENV", None)
    repo = Path(__file__).resolve().parents[1]

    def run(args, cwd=tmp_path, extra_env=None):
        result = subprocess.run(args, cwd=cwd, env={**env, **(extra_env or {})}, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result.stdout.strip()

    # Bootstrap this source into an isolated real uv tool environment.
    dist = tmp_path / "dist"
    run([uv, "--no-config", "build", "--wheel", "--out-dir", str(dist), str(repo)])
    wheel, = dist.glob("*.whl")
    run([uv, "--no-config", "tool", "install", "--python", sys.executable, "--from", str(wheel), "agent-toolkit"])
    assert "version" in run([str(tmp_path / "bin/atc"), "--version"])
    assert "version" in run([str(tmp_path / "bin/att"), "--version"])
    for name in ("atc", "att", "agent-toolkit-cli", "agent-toolkit-tui"):
        variable = "_" + name.replace("-", "_").upper() + "_COMPLETE"
        result = run([str(tmp_path / "bin" / name)], extra_env={
            variable: "bash_complete", "COMP_WORDS": f"{name} up", "COMP_CWORD": "1",
        })
        assert "plain,update" in result

    # A local Git fixture stands in for canonical GitHub, only at the network
    # boundary. Production still resolves/verifies a SHA and builds it with uv.
    source = tmp_path / "upstream"
    package = source / "src/agent_toolkit_cli"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text('def main():\n    print("updated-fixture")\n')
    (source / "pyproject.toml").write_text('''[project]
name = "agent-toolkit"
version = "999.0.0"
requires-python = ">=3.12"
[project.scripts]
agent-toolkit-cli = "agent_toolkit_cli.cli:main"
agent-toolkit-tui = "agent_toolkit_cli.cli:main"
atc = "agent_toolkit_cli.cli:main"
att = "agent_toolkit_cli.cli:main"
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[tool.hatch.build.targets.wheel]
packages = ["src/agent_toolkit_cli"]
''')
    run([git, "init", str(source)])
    run([git, "-C", str(source), "add", "."])
    run([git, "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture"])
    sha = run([git, "-C", str(source), "rev-parse", "HEAD"])
    script = tmp_path / "update.py"
    script.write_text(f'''
import json
from agent_toolkit_cli import self_update as u
original = u._run

def network_fixture(args, **kwargs):
    args = [str({str(source)!r}) if arg == u.REPOSITORY + ".git" else arg for arg in args]
    return original(args, **kwargs)

u._run = network_fixture
u._api_json = lambda endpoint, timeout: {{"tag_name": "v999.0.0"}} if endpoint == "releases/latest" else {{"sha": {sha!r}}}
receipt = u.perform_update()
assert u.installed_commit() == {sha!r}
print(json.dumps({{"receipt": str(receipt)}}))
''')
    output = run([str(tmp_path / "tools/agent-toolkit/bin/python"), str(script)])
    receipt_path = Path(json.loads(output)["receipt"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["commit"] == sha
    assert receipt["repository"] == "https://github.com/ajanderson1/agent-toolkit-cli"
    retained_wheel = receipt_path.parent / receipt["wheel"]
    assert receipt["wheel_sha256"] == hashlib.sha256(retained_wheel.read_bytes()).hexdigest()
    for binary in ("atc", "att", "agent-toolkit-cli", "agent-toolkit-tui"):
        assert run([str(tmp_path / "bin" / binary)]) == "updated-fixture"

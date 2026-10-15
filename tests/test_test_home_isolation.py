"""Tests verifying that pytest runs are isolated from the user's real home and state.

See issue #513 and docs/specs/2026-10-15-pytest-user-state-isolation.md.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_pytest_startup_redirects_home_and_configuration_roots(tmp_path: Path) -> None:
    """Verify that pytest startup redirects home, toolkit, and harness roots away from outer HOME."""
    synthetic_outer_home = tmp_path / "synthetic_outer_home"
    synthetic_outer_home.mkdir(parents=True)

    # Seed sentinels in the synthetic outer home
    sentinel_lock = synthetic_outer_home / ".agent-toolkit" / "skills-lock.json"
    sentinel_lock.parent.mkdir(parents=True)
    sentinel_lock_bytes = b'{"version": 1, "sentinel": "DO_NOT_TOUCH"}\n'
    sentinel_lock.write_bytes(sentinel_lock_bytes)

    sentinel_skill = synthetic_outer_home / ".agent-toolkit" / "skills" / "sentinel-skill" / "SKILL.md"
    sentinel_skill.parent.mkdir(parents=True)
    sentinel_skill_bytes = b"---\nname: sentinel-skill\ndescription: Outer sentinel.\n---\n"
    sentinel_skill.write_bytes(sentinel_skill_bytes)

    sentinel_pi_settings = synthetic_outer_home / ".pi" / "agent" / "settings.json"
    sentinel_pi_settings.parent.mkdir(parents=True)
    sentinel_pi_bytes = b'{"sentinel": true}\n'
    sentinel_pi_settings.write_bytes(sentinel_pi_bytes)

    # Prepare probe test that executes inside pytest with synthetic outer environment
    probe_test_path = tmp_path / "test_probe.py"
    probe_test_code = """
import os
from pathlib import Path
import pytest

def test_isolation_probe():
    outer_home_str = os.environ.get("SYNTHETIC_OUTER_HOME")
    assert outer_home_str, "SYNTHETIC_OUTER_HOME must be set"
    outer_home = Path(outer_home_str).resolve()

    current_home = Path.home().resolve()
    # 1. Path.home() must NOT resolve to or under the synthetic outer home
    assert current_home != outer_home, f"Path.home() remained outer home: {current_home}"
    assert outer_home not in current_home.parents, f"Path.home() is inside outer home: {current_home}"
    assert current_home.exists(), f"Path.home() does not exist: {current_home}"

    # 2. Toolkit library roots for all kinds must not resolve under outer home
    from agent_toolkit_cli import skill_paths, agent_paths, command_paths, instructions_paths, pi_extension_paths
    from agent_toolkit_cli import mcp_library

    for name, helper in [
        ("skills", lambda: skill_paths.library_root()),
        ("agents", lambda: agent_paths.library_root()),
        ("commands", lambda: command_paths.library_root()),
        ("instructions", lambda: instructions_paths.library_root()),
        ("pi_extensions", lambda: pi_extension_paths.library_root()),
        ("mcps", lambda: mcp_library.library_root(Path.home())),
    ]:
        root = helper().resolve()
        assert outer_home not in root.parents and root != outer_home, (
            f"Toolkit root for {name} ({root}) resolves under outer home ({outer_home})"
        )

    # 3. Harness roots in skill_agents must not resolve under outer home
    from agent_toolkit_cli import skill_agents
    for name, harness_path in [
        ("HOME", skill_agents.HOME),
        ("CLAUDE_HOME", skill_agents.CLAUDE_HOME),
        ("CODEX_HOME", skill_agents.CODEX_HOME),
        ("VIBE_HOME", skill_agents.VIBE_HOME),
        ("XDG_CONFIG", skill_agents.XDG_CONFIG),
    ]:
        resolved = harness_path.resolve()
        assert outer_home not in resolved.parents and resolved != outer_home, (
            f"skill_agents.{name} ({resolved}) resolves under outer home ({outer_home})"
        )

    # 4. TUI settings path must not resolve under outer home
    from agent_toolkit_tui import settings
    tui_settings = settings.default_path().resolve()
    assert outer_home not in tui_settings.parents and tui_settings != outer_home, (
        f"TUI settings ({tui_settings}) resolves under outer home ({outer_home})"
    )

    # 5. Writing to Path.home() must not write into outer home
    probe_write = current_home / "probe_created.txt"
    probe_write.write_text("test data")
    assert not (outer_home / "probe_created.txt").exists()
"""
    probe_test_path.write_text(probe_test_code)

    # Construct outer environment with synthetic home and potential inherited overrides
    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["SYNTHETIC_OUTER_HOME"] = str(synthetic_outer_home)
    env["HOME"] = str(synthetic_outer_home)
    env["XDG_CONFIG_HOME"] = str(synthetic_outer_home / ".config")
    env["CODEX_HOME"] = str(synthetic_outer_home / ".codex")
    env["CLAUDE_CONFIG_DIR"] = str(synthetic_outer_home / ".claude")
    env["VIBE_HOME"] = str(synthetic_outer_home / ".vibe")
    env["PI_CODING_AGENT_DIR"] = str(synthetic_outer_home / ".pi" / "agent")
    env["AGENT_TOOLKIT_SKILLS_ROOT"] = str(synthetic_outer_home / "inherited_escape")
    env["AGENT_TOOLKIT_TUI_SETTINGS"] = str(synthetic_outer_home / "tui-settings.json")

    # Run pytest subprocess targeting the probe test, using the repo's conftest
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tests.conftest",
            str(probe_test_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )

    # In Step 1 & 2 of TDD, we expect this to FAIL because conftest has not yet implemented the sandbox.
    assert result.returncode == 0, f"Pytest probe failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # Verify sentinels are completely untouched
    assert sentinel_lock.read_bytes() == sentinel_lock_bytes
    assert sentinel_skill.read_bytes() == sentinel_skill_bytes
    assert sentinel_pi_settings.read_bytes() == sentinel_pi_bytes

    # Verify no new files were created in synthetic outer home
    assert not (synthetic_outer_home / "probe_created.txt").exists()
    assert not (synthetic_outer_home / "inherited_escape").exists()


def test_global_skill_install_does_not_touch_outer_home(tmp_path: Path) -> None:
    """Verify that a global skill install inside pytest writes only to the sandbox."""
    synthetic_outer_home = tmp_path / "synthetic_outer_home"
    synthetic_outer_home.mkdir(parents=True)

    sentinel_lock = synthetic_outer_home / ".agent-toolkit" / "skills-lock.json"
    sentinel_lock.parent.mkdir(parents=True)
    sentinel_lock_bytes = b'{"version": 1, "skills": {}}\n'
    sentinel_lock.write_bytes(sentinel_lock_bytes)

    probe_test_path = tmp_path / "test_install_probe.py"
    probe_test_code = """
import os
import subprocess
from pathlib import Path
from agent_toolkit_cli.skill_install import InstallPlan, apply
from agent_toolkit_cli.skill_source import ParsedSource

def test_install_in_sandbox(tmp_path):
    outer_home = Path(os.environ["SYNTHETIC_OUTER_HOME"]).resolve()
    current_home = Path.home().resolve()

    # Create dummy upstream repo
    upstream = tmp_path / "upstream.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(upstream)], check=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(seed)], check=True)
    (seed / "SKILL.md").write_text("---\\nname: isolated-skill\\ndescription: Isolated.\\n---\\n")
    subprocess.run(["git", "-C", str(seed), "add", "SKILL.md"], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(seed), "remote", "add", "origin", str(upstream)], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "origin", "main"], check=True)

    src = ParsedSource(type="local", url=str(upstream), owner_repo=None, ref=None, subpath=None)
    p = InstallPlan(
        slug="isolated-skill",
        scope="global",
        source=src,
        ref=None,
        add_agents=("pi",),
        remove_agents=(),
    )
    result = apply(p)
    assert "isolated-skill" in str(result.canonical_path)
    # The canonical must be inside the sandbox home, never in the outer home
    assert outer_home not in result.canonical_path.parents
    assert current_home in result.canonical_path.parents or str(current_home) in str(result.canonical_path)
"""
    probe_test_path.write_text(probe_test_code)

    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["SYNTHETIC_OUTER_HOME"] = str(synthetic_outer_home)
    env["HOME"] = str(synthetic_outer_home)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tests.conftest",
            str(probe_test_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Install probe failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # Verify synthetic outer home lockfile was NOT modified
    assert sentinel_lock.read_bytes() == sentinel_lock_bytes
    # Verify no skills directory was created in synthetic outer home
    assert not (synthetic_outer_home / ".agent-toolkit" / "skills").exists()


def test_sandbox_cleanup_on_pytest_exit(tmp_path: Path) -> None:
    """Verify that the temporary sandbox root is removed when pytest finishes."""
    probe_test_path = tmp_path / "test_sandbox_cleanup.py"
    probe_test_code = """
import os
from pathlib import Path

def test_print_sandbox():
    sandbox_home = Path.home()
    # Output the sandbox root parent (the directory created by mkdtemp)
    print(f"SANDBOX_ROOT:{sandbox_home.parent}")
"""
    probe_test_path.write_text(probe_test_code)

    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "outer")
    (tmp_path / "outer").mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-s",
            "-q",
            "-p",
            "tests.conftest",
            str(probe_test_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    sandbox_root = None
    for line in result.stdout.splitlines():
        if line.startswith("SANDBOX_ROOT:"):
            sandbox_root = Path(line.split(":", 1)[1].strip())
            break

    assert sandbox_root is not None, f"Could not find SANDBOX_ROOT in output:\n{result.stdout}"
    # The sandbox directory must have been cleaned up by pytest_unconfigure
    assert not sandbox_root.exists(), f"Sandbox root was not cleaned up: {sandbox_root}"


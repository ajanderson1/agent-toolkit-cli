"""PR2 of v3.0.0: agent facade + 28 projection adapters.

Throwaway scope guard — deleted at the start of PR3.
Includes pytest.skip fallback for shallow CI clones
(per feedback_ci_shallow_clone_scope_guard).
"""
from __future__ import annotations

import subprocess

import pytest


ALLOWED = {
    # New files (PR2 production):
    "src/agent_toolkit_cli/agent_paths.py",
    "src/agent_toolkit_cli/agent_install.py",
    "src/agent_toolkit_cli/agent_lock.py",
    "src/agent_toolkit_cli/agent_adapters/__init__.py",
    "src/agent_toolkit_cli/agent_adapters/symlink.py",
    "src/agent_toolkit_cli/agent_adapters/translate.py",
    "src/agent_toolkit_cli/agent_adapters/config_file_folder.py",
    # Modified existing files (PR2 minimal touch):
    "src/agent_toolkit_cli/_paths_core.py",
    "src/agent_toolkit_cli/_install_core.py",
    "src/agent_toolkit_cli/skill_install.py",
    "src/agent_toolkit_cli/skill_lock.py",
    "src/agent_toolkit_cli/skill_agents.py",
    # New test files:
    "tests/test_cli/test_agent_paths.py",
    "tests/test_cli/test_agent_install.py",
    "tests/test_cli/test_agent_install_e2e.py",
    "tests/test_cli/test_agent_lock.py",
    "tests/test_cli/test_paths_core_agent_binding.py",
    "tests/test_cli/test_lock_agent_path.py",
    "tests/test_cli/test_agent_adapters/__init__.py",
    "tests/test_cli/test_agent_adapters/test_dispatcher.py",
    "tests/test_cli/test_agent_adapters/test_symlink.py",
    "tests/test_cli/test_agent_adapters/test_translate.py",
    "tests/test_cli/test_agent_adapters/test_config_file_folder.py",
    "tests/test_cli/test_pr2_scope_guard.py",
    # Deleted (Task 1 cleanup):
    "tests/test_cli/test_pr1_scope_guard.py",
    # Modified existing tests:
    "tests/test_cli/test_skill_agents.py",
    "tests/test_subagent_matrix.py",
}

ALLOWED_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    "assets/verification/",
)


def test_pr2_did_not_modify_caller_modules():
    """PR2 acceptance criterion #8: stays within the kind-foundation seam.

    Skipped on shallow CI clones where origin/main is unavailable
    (per feedback_ci_shallow_clone_scope_guard memory).
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        pytest.skip("origin/main not available (likely a shallow clone)")
    changed = [p for p in proc.stdout.splitlines() if p]
    leaks = [
        p for p in changed
        if p not in ALLOWED
        and not any(p.startswith(pref) for pref in ALLOWED_PREFIXES)
    ]
    assert not leaks, (
        f"PR2 modified files outside its scope: {leaks}.\n"
        "If a change was intentional, add it to ALLOWED — but spec "
        "acceptance criterion #8 says PR2 stays within the kind-foundation "
        "seam. Reconsider."
    )

"""PR1 of v3.0.0: refactor-only, no caller moves.

This test is throwaway — delete it in PR2. It exists to catch a sloppy
diff that drifts beyond the seam-cutting scope while PR1 is in review.
"""
from __future__ import annotations

import subprocess


# Files PR1 is allowed to modify.
ALLOWED = {
    # New files:
    "src/agent_toolkit_cli/_paths_core.py",
    "src/agent_toolkit_cli/_install_core.py",
    # Refactored:
    "src/agent_toolkit_cli/skill_paths.py",
    "src/agent_toolkit_cli/skill_install.py",
    # Additive:
    "src/agent_toolkit_cli/skill_agents.py",
    # CLI-token validators (added late: fail-loud on general-skill synthetic).
    # In scope here because rejecting the half-wired synthetic at the validator
    # is a fail-loud guard, NOT the caller-logic refactor reserved for PR3.
    "src/agent_toolkit_cli/commands/skill/list_cmd.py",
    "src/agent_toolkit_cli/commands/skill/__init__.py",
    # Matrix-test synthetic exclusion (parallel to existing universal exclusion):
    "tests/test_subagent_matrix.py",
    # Tests:
    "tests/test_cli/test_paths_core.py",
    "tests/test_cli/test_install_core.py",
    "tests/test_cli/test_skill_facade_parity.py",
    "tests/test_cli/test_skill_agents.py",
    "tests/test_cli/test_pr1_scope_guard.py",
}

ALLOWED_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    "docs/agent-toolkit/",
    "assets/verification/",
)


def test_pr1_did_not_modify_caller_modules():
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, check=True,
    )
    changed = [p for p in proc.stdout.splitlines() if p]
    leaks = [
        p for p in changed
        if p not in ALLOWED
        and not any(p.startswith(pref) for pref in ALLOWED_PREFIXES)
    ]
    assert not leaks, (
        f"PR1 modified files outside its scope: {leaks}.\n"
        "If a caller move was intentional, add it to ALLOWED — but the spec "
        "(acceptance criterion #5) says PR1 doesn't move callers. Reconsider "
        "before adding."
    )

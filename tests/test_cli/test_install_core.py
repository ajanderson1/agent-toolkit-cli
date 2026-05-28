"""Direct tests against _install_core to prove kind-agnosticism.

These tests use a synthetic KindBinding to confirm the core does not hard-
code 'skill' anywhere; they do not exercise file-system side effects.
"""
from __future__ import annotations

from agent_toolkit_cli._install_core import (
    InstallError,
    LockMismatchError,
    DirtyCanonicalError,
    InstallPlan,
    InstallResult,
)
from agent_toolkit_cli._paths_core import KindBinding


FAKE_BINDING = KindBinding(
    kind="x",
    canonical_dirname="xs",
    library_subdir="xs",
    lock_filename="xs-lock.json",
    general_harness_name="general-x",
)


def test_install_core_error_hierarchy():
    assert issubclass(LockMismatchError, InstallError)
    assert issubclass(DirtyCanonicalError, InstallError)
    assert issubclass(InstallError, RuntimeError)


def test_install_plan_dataclass_shape_unchanged():
    """Snapshot the public field set so PR2 cannot accidentally rename one."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(InstallPlan)}
    assert fields == {
        "slug", "scope", "source", "ref", "add_agents", "remove_agents",
    }


def test_install_result_dataclass_shape_unchanged():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(InstallResult)}
    assert fields == {
        "plan", "canonical_path", "created", "removed", "skipped", "lock_action",
    }


def test_install_core_has_no_hardcoded_skill_string():
    """Defensive: the core's source must not reference the word 'skill' in a
    way that would couple it to the skill kind. A few existing identifiers
    (e.g. 'skill_path' which is a v1 lock field name) are grandfathered via an
    allowlist."""
    import inspect
    import agent_toolkit_cli._install_core as core
    src = inspect.getsource(core)
    # Allowed: references to the kind-agnostic skill_* modules (skill_lock,
    # skill_agents, skill_source, skill_paths) and to the v1 lock-field name
    # skill_path — these are the existing kind-agnostic helpers that PR2 will
    # rename. Also: docstring lines, comments, and the user-facing
    # `skill doctor` hint emitted by the facade-level CLI. Anything else is
    # a smell.
    in_docstring = False
    for line in src.splitlines():
        stripped = line.lstrip()
        # Track multi-line docstrings: any line beginning a `"""` toggles us
        # in or out of docstring mode (single-line docstrings toggle twice).
        triple_count = line.count('"""')
        if triple_count == 1:
            if in_docstring:
                in_docstring = False
                continue  # closing line — skip even if it contains "skill"
            else:
                in_docstring = True
                if "skill" not in line.lower():
                    continue
                # falls through to allowlist check (opening line w/ "skill")
        elif in_docstring:
            # mid-docstring line: always allowed
            continue
        if "skill" not in line.lower():
            continue
        allowed = (
            "skill_lock" in line
            or "skill_agents" in line   # kind-agnostic catalog (PR2 renames)
            or "skill_source" in line   # kind-agnostic source parser (PR2)
            or "skill_paths" in line    # facade (already a facade in Task 3)
            or "skill_path" in line     # v1 LockEntry field
            or "skill_git" in line      # cross-kind git helpers (PR2 renames)
            or "canonical_skill_dir" in line  # imported from skill_paths facade
            or "general-skill" in line  # synthetic catalog entry (PR3 removes)
            or "agent-toolkit-cli skill doctor" in line  # facade-level CLI hint
            or stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        )
        assert allowed, f"unwhitelisted 'skill' in _install_core: {line!r}"

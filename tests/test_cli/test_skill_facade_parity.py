"""Facade parity: the public-symbol surface of skill_paths / skill_install /
skill_lock must not regress during the kind-dimension refactor.

If a name is removed from this set, downstream callers (tests + CLI verbs)
will break. Renames or moves are a PR-level decision, not a refactor side
effect — fail loudly here so the diff has to be self-aware.
"""
from __future__ import annotations

SKILL_PATHS_PUBLIC = {
    "Scope",
    "canonical_skill_dir",
    "lock_file_path",
    "library_root",
    "library_skill_path",
    "library_lock_path",
    "project_id",
    "project_store_root",
    "project_parents_root",
    "parent_clone_path",
    "agent_projection_dir",
    "harness_projection_dir",
    "SUPPORTED_HARNESSES",
}


def test_skill_paths_public_surface_preserved():
    import agent_toolkit_cli.skill_paths as m
    actual = set(dir(m))
    missing = SKILL_PATHS_PUBLIC - actual
    assert not missing, f"skill_paths lost public names: {sorted(missing)}"

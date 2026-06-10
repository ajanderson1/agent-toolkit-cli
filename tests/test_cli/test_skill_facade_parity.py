"""Facade parity: the public-symbol surface of skill_paths / skill_install /
skill_lock must not regress during the asset-type-dimension refactor.

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


SKILL_INSTALL_PUBLIC = {
    "InstallError",
    "LockMismatchError",
    "DirtyCanonicalError",
    "InstallPlan",
    "InstallResult",
    "plan",
    "apply",
    "install",
    "uninstall",
    "migrate_project_canonical",
    "ensure_project_canonical",
    "_standard_bundle_link",     # used by tests + ensure_project_canonical
    "_project_standard_link",    # used by ensure_project_canonical
}


def test_skill_install_public_surface_preserved():
    import agent_toolkit_cli.skill_install as m
    actual = set(dir(m))
    missing = SKILL_INSTALL_PUBLIC - actual
    assert not missing, f"skill_install lost public names: {sorted(missing)}"


SKILL_LOCK_PUBLIC = {
    "LockEntry",
    "LockFile",
    "SUPPORTED_VERSIONS",
    "read_lock",
    "write_lock",
    "add_entry",
    "remove_entry",
    "clone_url_from_entry",
    "_apply_insteadof",  # private but referenced in skill_import tests
}


def test_skill_lock_public_surface_preserved():
    import agent_toolkit_cli.skill_lock as m
    actual = set(dir(m))
    missing = SKILL_LOCK_PUBLIC - actual
    assert not missing, f"skill_lock lost public names: {sorted(missing)}"

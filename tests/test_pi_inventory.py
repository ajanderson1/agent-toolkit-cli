from pathlib import Path

from agent_toolkit_cli._pi_inventory import build_pi_inventory
from agent_toolkit_cli._pi_paths import PiPaths


def _mkdir_p(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _paths(home: Path, project: Path) -> PiPaths:
    return PiPaths(home=home, project_root=project)


def test_first_party_user_loaded(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.slug == "status-bar"
    assert r.origin == "first-party"
    assert r.source == "extension:status-bar"
    assert r.user_loaded is True
    assert r.project_loaded is False
    assert r.toolkit_intent == "user"


def test_third_party_user_loaded_unmanaged(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.slug == "pi-subagents"
    assert r.origin == "third-party"
    assert r.source == "npm:pi-subagents"
    assert r.user_loaded is True
    assert r.toolkit_intent == "none"


def test_third_party_declared_but_not_resolved(tmp_path: Path):
    """`packages[]` declares it, but node_modules/ has no matching dir — not loaded."""
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules=set(),  # fetch hasn't happened yet
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=["npm:pi-subagents"],
        project_allowlist_pi_packages=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.user_loaded is False  # declared but not resolved
    assert r.toolkit_intent == "user"


def test_collision_first_party_wins(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/pi-subagents")

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        user_allowlist_pi_extensions=["pi-subagents"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=["npm:pi-subagents"],
        project_allowlist_pi_packages=[],
    )

    assert len(records) == 1
    assert records[0].origin == "first-party"


def test_git_source_slug_derivation(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["git:github.com/user/my-ext@v1"],
        project_packages=[],
        user_node_modules={"my-ext"},
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
    )

    assert len(records) == 1
    assert records[0].slug == "my-ext"
    assert records[0].source == "git:github.com/user/my-ext@v1"


def test_record_is_sorted_by_slug(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/zeta")
    _mkdir_p(home / ".pi/agent/extensions/alpha")

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["zeta", "alpha"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
    )

    assert [r.slug for r in records] == ["alpha", "zeta"]


def test_first_party_disabled_by_bang_override(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=["!status-bar"],
        project_extensions_overrides=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.user_loaded is True
    assert r.user_enabled is False
    assert r.project_enabled is True  # default when no override targets the slug


def test_first_party_default_enabled_no_overrides(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=[],
        project_extensions_overrides=[],
    )

    assert records[0].user_enabled is True
    assert records[0].project_enabled is True


def test_third_party_always_enabled(tmp_path: Path):
    """`extensions[]` override list does not target packages — `enabled` stays True."""
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=["!pi-subagents"],  # ignored for third-party
        project_extensions_overrides=[],
    )

    r = records[0]
    assert r.origin == "third-party"
    assert r.user_enabled is True
    assert r.project_enabled is True


def test_intent_both_when_in_user_and_project_allowlists(tmp_path: Path):
    """A slug allowlisted at both scopes yields toolkit_intent='both'."""
    home = tmp_path / "home"
    project = tmp_path / "proj"

    # first-party
    fp_records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=["status-bar"],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
    )
    assert len(fp_records) == 1
    assert fp_records[0].toolkit_intent == "both"

    # third-party
    tp_records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=["npm:pi-subagents"],
        project_allowlist_pi_packages=["npm:pi-subagents"],
    )
    assert len(tp_records) == 1
    assert tp_records[0].toolkit_intent == "both"

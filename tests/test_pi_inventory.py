from pathlib import Path

from agent_toolkit_cli._pi_inventory import PiRecord, build_pi_inventory  # noqa: F401


def _mkdir_p(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def test_first_party_user_loaded(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        allowlist_pi_extensions=["status-bar"],
        allowlist_pi_packages=[],
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
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=[],
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
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules=set(),  # fetch hasn't happened yet
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=["npm:pi-subagents"],
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
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        allowlist_pi_extensions=["pi-subagents"],
        allowlist_pi_packages=["npm:pi-subagents"],
    )

    assert len(records) == 1
    assert records[0].origin == "first-party"


def test_git_source_slug_derivation(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=["git:github.com/user/my-ext@v1"],
        project_packages=[],
        user_node_modules={"my-ext"},
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=[],
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
        home=home,
        project_root=project,
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        allowlist_pi_extensions=["zeta", "alpha"],
        allowlist_pi_packages=[],
    )

    assert [r.slug for r in records] == ["alpha", "zeta"]

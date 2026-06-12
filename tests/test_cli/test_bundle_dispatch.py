from __future__ import annotations

import pytest

from agent_toolkit_cli.bundle_dispatch import (
    INSTALLABLE_KINDS,
    DispatchError,
    install_member,
    resolve_member,
    uninstall_member,
)
from agent_toolkit_cli.bundle_manifest import BundleMember


def test_installable_kinds_are_the_three_source_backed():
    assert INSTALLABLE_KINDS == ("skill", "agent", "pi-extension")


def test_mcp_member_hard_fails_with_329(monkeypatch):
    member = BundleMember(asset_type="mcp", source="o/r/ctx7", slug="context7")
    with pytest.raises(DispatchError, match="#329"):
        resolve_member(member)
    with pytest.raises(DispatchError, match="#329"):
        install_member(member, scope="global")


def _stub_not_present(monkeypatch):
    """Lock-precheck always says 'not present' so install proceeds (F2)."""
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._lock_has_member",
        lambda member: False,
    )


def test_agent_member_builds_full_argv_with_g_flag(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="agent", source="o/r/agents/cr",
                     slug="cr", ref="v1"),
        scope="global",
    )
    assert calls[0] == ["agent", "add", "--slug", "cr", "--ref", "v1",
                        "--", "o/r/agents/cr"]
    assert calls[1] == ["agent", "install", "-g", "--", "cr"]


def test_skill_member_scope_project_threads_scope_not_p(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="skill", source="o/r/gw"),
        scope="project",
    )
    assert calls[0] == ["skill", "add", "--", "o/r/gw"]
    assert calls[1] == ["skill", "install", "--scope", "project", "--", "gw"]
    assert "-p" not in calls[1]
    assert "--agents" not in calls[1]


def test_pi_extension_member_omits_ref_and_uses_g_flag(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="pi-extension", source="o/r/tm", slug="tm"),
        scope="global",
    )
    assert calls[0] == ["pi-extension", "add", "--slug", "tm", "--", "o/r/tm"]
    assert "--ref" not in calls[0]
    assert calls[1] == ["pi-extension", "install", "-g", "--", "tm"]


def test_end_of_options_sentinel_precedes_positionals(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(BundleMember(asset_type="skill", source="o/r/gw"),
                   scope="global")
    assert calls[0][-2:] == ["--", "o/r/gw"]
    assert calls[1][-2:] == ["--", "gw"]


def test_project_scope_prepends_project_root(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="agent", source="o/r/agents/cr", slug="cr"),
        scope="project",
        project_root="/tmp/proj",
    )
    assert calls[0][:2] == ["--project", "/tmp/proj"]
    assert calls[1][:2] == ["--project", "/tmp/proj"]


def test_already_present_skips_add_and_returns_sentinel(monkeypatch):
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._lock_has_member",
        lambda member: True,
    )
    called = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: called.append(argv),
    )
    outcome = install_member(
        BundleMember(asset_type="skill", source="o/r/gw", slug="gw"),
        scope="global",
    )
    assert outcome == "already_present"
    assert called == []


def test_lock_has_member_reads_real_lock_shape(tmp_path, monkeypatch):
    from agent_toolkit_cli import bundle_dispatch
    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock

    lock_path = tmp_path / "skills-lock.json"
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "gw",
        LockEntry(source="o/r/gw", source_type="github", skill_path="SKILL.md"),
    ))
    monkeypatch.setattr(
        "agent_toolkit_cli._paths_core.library_lock_path_for_asset_type",
        lambda binding: lock_path,
    )
    assert bundle_dispatch._lock_has_member(
        BundleMember(asset_type="skill", source="o/r/gw", slug="gw")
    ) is True
    assert bundle_dispatch._lock_has_member(
        BundleMember(asset_type="skill", source="o/r/OTHER", slug="gw")
    ) is False


def test_dispatch_propagates_install_failure(monkeypatch):
    _stub_not_present(monkeypatch)

    def boom(argv):
        raise RuntimeError("clone failed")
    monkeypatch.setattr("agent_toolkit_cli.bundle_dispatch._invoke_cli", boom)
    with pytest.raises(DispatchError, match="clone failed"):
        install_member(
            BundleMember(asset_type="skill", source="o/r/gw"),
            scope="global",
        )


def test_uninstall_member_per_kind_argv(monkeypatch):
    calls = []
    monkeypatch.setattr("agent_toolkit_cli.bundle_dispatch._invoke_cli",
                        lambda argv: calls.append(argv))
    uninstall_member(BundleMember(asset_type="skill", source="o/r/gw", slug="gw"), scope="project")
    uninstall_member(BundleMember(asset_type="agent", source="o/r/a/cr", slug="cr"), scope="global")
    uninstall_member(BundleMember(asset_type="pi-extension", source="o/r/tm", slug="tm"), scope="global")
    assert calls[0] == ["skill", "remove", "--force", "--", "gw"]
    assert calls[1] == ["agent", "remove", "--force", "--", "cr"]
    assert calls[2] == ["pi-extension", "remove", "--force", "--", "tm"]


def test_uninstall_failure_wraps_in_dispatch_error(monkeypatch):
    def boom(argv): raise RuntimeError("unlink failed")
    monkeypatch.setattr("agent_toolkit_cli.bundle_dispatch._invoke_cli", boom)
    with pytest.raises(DispatchError, match="unlink failed"):
        uninstall_member(BundleMember(asset_type="skill", source="o/r/gw", slug="gw"), scope="global")


def test_uninstall_ignores_project_root_for_remove(monkeypatch):
    # `remove --force` is library/global-level — no --project prefix even when
    # project_root is passed (rollback is scope-independent).
    calls = []
    monkeypatch.setattr("agent_toolkit_cli.bundle_dispatch._invoke_cli",
                        lambda argv: calls.append(argv))
    uninstall_member(BundleMember(asset_type="skill", source="o/r/gw", slug="gw"),
                     scope="project", project_root="/tmp/proj")
    assert calls[0] == ["skill", "remove", "--force", "--", "gw"]

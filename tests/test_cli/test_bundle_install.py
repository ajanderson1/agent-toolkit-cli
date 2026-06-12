from __future__ import annotations

import pytest

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli.bundle_dispatch import DispatchError
from agent_toolkit_cli.bundle_install import BundleInstallError, run
from agent_toolkit_cli.bundle_manifest import BundleManifest, BundleMember


def _manifest(*types_sources) -> BundleManifest:
    members = tuple(
        BundleMember(asset_type=t, source=s) for t, s in types_sources
    )
    return BundleManifest(name="b", description="", members=members)


def test_happy_path_installs_every_member_in_order(monkeypatch):
    installed = []
    monkeypatch.setattr(bundle_install, "install_member",
                        lambda m, scope, project_root=None: installed.append(m.source))
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: pytest.fail("must not roll back"))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)
    run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
        scope="global", dry_run=False)
    assert installed == ["a", "b", "c"]


def test_failure_midrun_rolls_back_prior_and_inflight_member_newest_first(monkeypatch):
    """On failure at member c: a and b (prior) plus c itself (in-flight, whose
    `add` may have already landed) are all rolled back, newest-first.
    """
    rolled_back = []

    def fake_install(m, scope, project_root=None):
        if m.source == "c":
            raise DispatchError("boom on c")
        return None

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="boom on c"):
        run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
            scope="global", dry_run=False)
    # c (in-flight) is rolled back first, then b, then a — newest-first.
    assert rolled_back == ["c", "b", "a"]


def test_already_present_member_not_rolled_back(monkeypatch):
    """An 'already_present' member (pre-existing, not installed by us) is excluded
    from rollback; only the in-flight failing member b is rolled back.
    """
    rolled_back = []

    def fake_install(m, scope, project_root=None):
        if m.source == "a":
            return "already_present"
        if m.source == "b":
            raise DispatchError("boom on b")

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError):
        run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
            dry_run=False)
    # 'a' was already_present (not ours) — must NOT be rolled back.
    assert "a" not in rolled_back
    # 'b' is in-flight (its add may have landed) — IS rolled back.
    assert "b" in rolled_back


def test_rollback_failure_is_warned_not_swallowed(monkeypatch, capsys):
    def fake_install(m, scope, project_root=None):
        if m.source == "c":
            raise DispatchError("boom on c")
        return None

    def failing_uninstall(m, scope, project_root=None):
        raise DispatchError(f"uninstall of {m.source} blew up")

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member", failing_uninstall)
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="boom on c") as exc_info:
        run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
            scope="global", dry_run=False)
    assert "skill:a" in str(exc_info.value) and "agent:b" in str(exc_info.value)
    err = capsys.readouterr().err
    assert "warning: rollback" in err
    assert "skill:a" in err and "agent:b" in err


def test_failed_members_partial_add_is_rolled_back(monkeypatch):
    """BUG1: a member whose install_member raises is itself rolled back (its `add`
    may have already landed), not just the prior successfully-installed members.
    Newest-first: the failing member (b) is rolled back before the prior member (a).
    """
    rolled_back = []

    def fake_install(m, scope, project_root=None):
        if m.source == "b":
            raise DispatchError("install (projection) failed for b after add")
        return None

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="failed for b after add"):
        run(_manifest(("skill", "a"), ("agent", "b")), scope="global", dry_run=False)
    # BOTH the prior member 'a' AND the failing member 'b' are rolled back (b's add
    # may have landed already). Newest-first order: b then a.
    assert rolled_back == ["b", "a"]


def test_dry_run_resolves_but_installs_nothing(monkeypatch):
    resolved, installed = [], []
    monkeypatch.setattr(bundle_install, "resolve_member",
                        lambda m: resolved.append(m.source))
    monkeypatch.setattr(bundle_install, "install_member",
                        lambda m, scope, project_root=None: installed.append(m.source))
    report = run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
                 dry_run=True)
    assert resolved == ["a", "b"]
    assert installed == []
    assert report.ok is True


def test_dry_run_reports_failure_without_raising(monkeypatch):
    def fail_resolve(m):
        if m.source == "b":
            raise DispatchError("unresolvable b")

    monkeypatch.setattr(bundle_install, "resolve_member", fail_resolve)
    report = run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
                 dry_run=True)
    assert report.ok is False
    assert any("b" in f for f in report.failures)

"""Orchestrate a bundle: resolve all members, install in order, roll back on
failure. Shared by `bundle install` (dry_run=False) and `bundle validate`
(dry_run=True). Adds NO new install/rollback primitive — it sequences the
per-kind ones via bundle_dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import click

# Imported at module scope so tests can monkeypatch these names on this module.
from agent_toolkit_cli.bundle_dispatch import (
    DispatchError,
    install_member,
    resolve_member,
    uninstall_member,
)
from agent_toolkit_cli.bundle_manifest import BundleManifest, BundleMember

__all__ = ["BundleInstallError", "ValidateReport", "run"]


class BundleInstallError(RuntimeError):
    """A bundle install failed; prior members this run were rolled back."""


@dataclass
class ValidateReport:
    ok: bool
    checked: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def _label(member: BundleMember) -> str:
    return f"{member.asset_type}:{member.slug or member.source}"


def run(
    manifest: BundleManifest,
    scope: str,
    dry_run: bool,
    project_root: str | None = None,
) -> ValidateReport:
    """Resolve every member; if not dry_run, install in order with rollback.

    `project_root` (F8) is threaded to dispatch so project-scope child argv carry
    `--project <root>`.
    """
    report = ValidateReport(ok=True)

    # Resolve pass — shared by both verbs.
    for member in manifest.members:
        try:
            resolve_member(member)
            report.checked.append(_label(member))
        except DispatchError as exc:
            report.ok = False
            report.failures.append(str(exc))

    if dry_run:
        return report

    if not report.ok:
        # An unresolvable member must stop install before any disk change.
        raise BundleInstallError(
            "bundle did not resolve:\n  " + "\n  ".join(report.failures)
        )

    installed: list[BundleMember] = []
    for member in manifest.members:
        try:
            outcome = install_member(member, scope=scope, project_root=project_root)
        except DispatchError as exc:
            failed_rollbacks = _rollback(installed, scope, project_root)
            msg = str(exc)
            if failed_rollbacks:
                msg += (
                    "\n  NOTE: rollback failed for "
                    f"{', '.join(failed_rollbacks)} — manual cleanup may be needed."
                )
            raise BundleInstallError(msg) from exc
        # Only track members WE installed (not pre-existing no-ops) for rollback.
        if outcome != "already_present":
            installed.append(member)

    return report


def _rollback(
    installed: list[BundleMember], scope: str, project_root: str | None
) -> list[str]:
    """Roll back this run's installs, newest-first. F9: a rollback failure is
    WARNED (never swallowed) and the failed labels are collected and returned so
    the caller can name them in the propagated BundleInstallError.
    """
    failed: list[str] = []
    for prior in reversed(installed):
        label = _label(prior)
        try:
            uninstall_member(prior, scope=scope, project_root=project_root)
        except DispatchError as exc:
            click.echo(f"warning: rollback of {label} failed: {exc}", err=True)
            failed.append(label)
    return failed

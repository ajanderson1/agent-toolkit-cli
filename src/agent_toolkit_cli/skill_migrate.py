"""Pure core for `skill migrate-to-monorepo`.

Decides which owned per-skill lock entries can be re-homed into a monorepo
and computes the rewritten entry. No I/O beyond values passed in.
"""
from __future__ import annotations

import enum

from agent_toolkit_cli.skill_lock import LockEntry


def monorepo_subpath_for(slug: str) -> str:
    """Subpath a slug occupies in the owned monorepo: bare `skills/<slug>`.

    The standalone repos carried a `-skill` suffix; the monorepo dropped it,
    so the subpath is the slug verbatim.
    """
    return f"skills/{slug}"


def is_migratable(entry: LockEntry) -> bool:
    """True for an own-repo per-skill entry not yet re-homed.

    Own-repo shape: a per-skill clone (has `local_sha`, no `parent_url`).
    Tolerant of pre- or post-Track-A rename of `source`. Already-migrated
    monorepo entries and read-only third-party entries are excluded by the
    `parent_url is None` test.
    """
    return entry.local_sha is not None and entry.parent_url is None


class RefusalReason(enum.Enum):
    """Why a skill was skipped during migration. `.hint` is shown to the user.

    Ordering matters: `check_refusal` returns the FIRST reason that applies,
    most-fundamental first (absent from monorepo -> can't migrate at all).
    """

    NOT_IN_MONOREPO = "not yet in monorepo (fold it in first, then re-run)"
    SHA_DIVERGED = "local commits not in monorepo (reconcile, then re-run)"
    DIRTY_TREE = "uncommitted edits in clone (commit/push, then re-run)"
    CONTENT_DRIFT = (
        "monorepo copy differs from local (re-fold or push, then re-run)"
    )

    @property
    def hint(self) -> str:
        return self.value


def check_refusal(
    *,
    sha_match: bool,
    tree_clean: bool,
    content_matches: bool,
    in_monorepo: bool,
) -> RefusalReason | None:
    """Return the first refusal that applies, or None to proceed.

    Checks run most-fundamental first so the user sees the root blocker:
    a skill absent from the monorepo can't be evaluated for drift at all.
    """
    if not in_monorepo:
        return RefusalReason.NOT_IN_MONOREPO
    if not sha_match:
        return RefusalReason.SHA_DIVERGED
    if not tree_clean:
        return RefusalReason.DIRTY_TREE
    if not content_matches:
        return RefusalReason.CONTENT_DRIFT
    return None


def migrated_entry(
    old: LockEntry,
    *,
    slug: str,
    parent_source: str,
    parent_url: str,
    parent_sha: str | None,
) -> LockEntry:
    """Rewrite an own-repo entry to owned-monorepo-subpath shape.

    Mirrors what `_add_monorepo(..., owned=True)` writes: monorepo source,
    `skills/<slug>` subpath, parent_url set, upstream pinned to parent HEAD,
    `local_sha` dropped, `read_only=False` (owned). source_type preserved.
    """
    return LockEntry(
        source=parent_source,
        source_type=old.source_type,
        ref=old.ref,
        skill_path=monorepo_subpath_for(slug),
        upstream_sha=parent_sha,
        local_sha=None,
        parent_url=parent_url,
        read_only=False,
    )

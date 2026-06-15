"""Which monorepo parents are owned (writable) by default.

A monorepo is "owned" when its parent remote owner is in OWNED_OWNERS, or
when the user passes --owned to `skill add`. Owned monorepo lock entries are
written WITHOUT read_only, so `skill push` opens PRs against the parent
instead of refusing. This is the one place to extend ownership later.
"""
from __future__ import annotations

# Lower-cased GitHub owner logins that AJ authors skills under. Ownership is
# matched case-insensitively against this set.
OWNED_OWNERS: frozenset[str] = frozenset({"ajanderson1"})


def is_owned_owner(owner: str) -> bool:
    """True if `owner` is an owned (writable-by-default) monorepo parent owner."""
    return owner.lower() in OWNED_OWNERS

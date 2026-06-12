"""Standard agents projection (#361): the .claude/agents/<slug>.md slot.

`.claude/agents/` is the de-facto agents asset-type convergence dir — read natively
by multiple harnesses (per-scope table below). Installing `standard` writes
ONE file that all covered harnesses consume; it is the same file the
claude-code symlink-adapter cell writes (one artifact, one name — every scan
dedupes by destination and reports it as `standard`).
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path

# Harnesses that natively read the standard agents dir, per scope.
# Evidence: docs/agent-toolkit/research/subagent-fragments/ (re-verified for
# #361, 2026-06-10 — see the Task 0 commit, 0b89cb4). devin reads
# .claude/agents/*.md at project scope only; its global path is a profile-dir
# AGENT.md. cursor reads the dir at both scopes (cursor.com/docs/subagents,
# re-verified 2026-06-10; .cursor/ wins name conflicts).
STANDARD_AGENT_READERS: dict[str, frozenset[str]] = {
    "global":  frozenset({"claude-code", "kode", "neovate", "cortex", "cursor"}),
    "project": frozenset({"claude-code", "kode", "neovate", "cortex", "cursor", "devin"}),
}

_TEMPLATES = {
    "global": "{HOME}/.claude/agents/{SLUG}.md",
    "project": "{PROJECT}/.claude/agents/{SLUG}.md",
}


def agents_standard_covered(scope: str) -> frozenset[str]:
    """Covered set for a scope. KeyError on unknown scope (fail loud)."""
    return STANDARD_AGENT_READERS[scope]


class _StandardAdapter:
    """Install/uninstall the single standard agents slot."""

    harness = "standard"

    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        # Reuse the symlink adapter's template expansion (same fail-loud
        # semantics for missing home/project).
        from agent_toolkit_cli.agent_adapters.symlink import _expand
        if scope not in _TEMPLATES:
            raise ValueError(
                f"standard: scope must be 'global' or 'project', got {scope!r}"
            )
        if "/" in slug or "\\" in slug or slug in (".", "..") or not slug:
            raise ValueError(f"standard: invalid slug {slug!r}")
        return _expand(_TEMPLATES[scope], home=home, project=project, slug=slug)

    def install(
        self, slug: str, content_path: Path, *, scope: str,
        home: Path | None = None, project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self.destination(slug, scope=scope, home=home, project=project)
        # Fail loud on a missing canonical content file (PM review F8) —
        # BEFORE any filecmp/copy2 call raises a raw OSError mid-fan-out.
        # InstallError is the type install_cmd already catches and presents
        # as a clean ClickException.
        if not content_path.exists():
            raise InstallError(
                f"standard: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
        # Adopt-if-identical (#361): a pre-existing byte-identical file (e.g.
        # a prior `--harnesses claude-code` install) becomes tool-owned.
        if dest.exists() and not dest.is_symlink() and filecmp.cmp(
            content_path, dest, shallow=False,
        ):
            _sentinel_path(dest).write_text("")
            return dest
        # Ownership = SENTINEL, not lock (PM review): the facade passes
        # overwrite=True for any locked slug, but lock membership is not
        # evidence we own a file in the shared .claude/agents/ dir (users
        # hand-author agents there). Ignore the facade flag; only the
        # sentinel authorizes overwriting a divergent existing file.
        _guard_foreign(dest, harness="standard", overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # A symlink at the slot (e.g. a stale sentinel + a user-replaced
        # symlink) must be REPLACED, never written through — copy2 over a
        # symlink would write into its target (PM review F6).
        if dest.is_symlink():
            dest.unlink()
        shutil.copy2(content_path, dest)
        _sentinel_path(dest).write_text("")
        return dest

    def uninstall(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Detach the slot — ownership-guarded (PM review): unlink only when
        the sentinel exists OR the slot matches `canonical_content` (covers
        pre-#361 sentinel-less claude-code installs). A sentinel-less,
        content-divergent file is a user's — leave it and say so.

        Returns the destination path when removal was REFUSED (structured
        refusal, PM review F5 — callers like the TUI must be able to surface
        the left-in-place file instead of counting it as removed); None when
        the slot was removed or absent. The stderr notice stays for the CLI.
        """
        dest = self.destination(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        refused: Path | None = None
        if dest.exists() or dest.is_symlink():
            owned = sentinel.exists() or (
                canonical_content is not None
                and canonical_content.exists()
                and not dest.is_symlink()
                and filecmp.cmp(canonical_content, dest, shallow=False)
            )
            if owned:
                dest.unlink()
            else:
                refused = dest
                print(
                    f"standard: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()
        return refused


def adapter_for() -> _StandardAdapter:
    return _StandardAdapter()

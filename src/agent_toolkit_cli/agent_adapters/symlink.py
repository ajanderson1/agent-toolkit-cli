"""Symlink mechanism: write a single .md per agent to a harness-specific dir.

15 cells. Per-cell quirks (path-template, frontmatter rules, name-validation)
live in CELLS below. The adapter is a closure factory: adapter_for(harness)
returns a Protocol-conforming object with install/uninstall.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import sys
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path
from agent_toolkit_cli.skill_agents import UnknownAgentError


# Path templates per cell. {HOME}, {PROJECT}, {SLUG} are placeholders.
# {PI_AGENT_DIR} is a custom token for pi's env override.
# Sources: docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
# (Risk Resolution Addendum, symlink table, verified 2026-05-28).
CELLS: dict[str, dict[str, str]] = {
    "augment":      {"global": "{HOME}/.augment/agents/{SLUG}.md",
                     "project": "{PROJECT}/.augment/agents/{SLUG}.md"},
    "claude-code":  {"global": "{HOME}/.claude/agents/{SLUG}.md",
                     "project": "{PROJECT}/.claude/agents/{SLUG}.md"},
    "codebuddy":    {"global": "{HOME}/.codebuddy/agents/{SLUG}.md",
                     "project": "{PROJECT}/.codebuddy/agents/{SLUG}.md"},
    "command-code": {"global": "{HOME}/.commandcode/agents/{SLUG}.md",
                     "project": "{PROJECT}/.commandcode/agents/{SLUG}.md"},
    "cortex":       {"global": "{HOME}/.snowflake/cortex/agents/{SLUG}.md",
                     "project": "{PROJECT}/.cortex/agents/{SLUG}.md"},
    "cursor":       {"global": "{HOME}/.cursor/agents/{SLUG}.md",
                     "project": "{PROJECT}/.cursor/agents/{SLUG}.md"},
    "droid":        {"global": "{HOME}/.factory/droids/{SLUG}.md",
                     "project": "{PROJECT}/.factory/droids/{SLUG}.md"},
    "forgecode":    {"global": "{HOME}/.forge/agents/{SLUG}.md",
                     "project": "{PROJECT}/.forge/agents/{SLUG}.md"},
    "junie":        {"global": "{HOME}/.junie/agents/{SLUG}.md",
                     "project": "{PROJECT}/.junie/agents/{SLUG}.md"},
    "kode":         {"global": "{HOME}/.kode/agents/{SLUG}.md",
                     "project": "{PROJECT}/.claude/agents/{SLUG}.md"},
    "neovate":      {"global": "{HOME}/.neovate/agents/{SLUG}.md",
                     "project": "{PROJECT}/.neovate/agents/{SLUG}.md"},
    "pi":           {"global": "{PI_AGENT_DIR}/agents/{SLUG}.md",
                     "project": "{PROJECT}/.pi/agents/{SLUG}.md"},
    "pochi":        {"global": "{HOME}/.pochi/agents/{SLUG}.md",
                     "project": "{PROJECT}/.pochi/agents/{SLUG}.md"},
    "qoder":        {"global": "{HOME}/.qoder/agents/{SLUG}.md",
                     "project": "{PROJECT}/.qoder/agents/{SLUG}.md"},
    "rovodev":      {"global": "{HOME}/.rovodev/subagents/{SLUG}.md",
                     "project": "{PROJECT}/.rovodev/subagents/{SLUG}.md"},
}


def _expand(template: str, *, home: Path | None, project: Path | None, slug: str) -> Path:
    """Expand {HOME}/{PROJECT}/{SLUG}/{PI_AGENT_DIR} placeholders.

    Fail-loud: if the template needs {HOME} or {PROJECT} but the
    corresponding arg is None, raise ValueError rather than leaving the
    literal placeholder in the path (which would silently write to
    `./{HOME}/...` under cwd). Same rule for {PI_AGENT_DIR}: needs either
    PI_CODING_AGENT_DIR env or an explicit home= — never silently falls
    back to the real user's `Path.home()`.
    """
    out = template.replace("{SLUG}", slug)
    if "{HOME}" in out:
        if home is None:
            raise ValueError(
                f"symlink._expand: template {template!r} requires home= but None was passed"
            )
        out = out.replace("{HOME}", str(home))
    if "{PROJECT}" in out:
        if project is None:
            raise ValueError(
                f"symlink._expand: template {template!r} requires project= but None was passed"
            )
        out = out.replace("{PROJECT}", str(project))
    if "{PI_AGENT_DIR}" in out:
        env_path = os.environ.get("PI_CODING_AGENT_DIR")
        if env_path:
            out = out.replace("{PI_AGENT_DIR}", env_path)
        elif home is not None:
            out = out.replace("{PI_AGENT_DIR}", str(home / ".pi" / "agent"))
        else:
            raise ValueError(
                "symlink._expand: pi template needs either PI_CODING_AGENT_DIR "
                "env or an explicit home= argument; both are missing"
            )
    return Path(out)


_VALID_SCOPES = frozenset({"global", "project"})


class _SymlinkAdapter:
    """Per-harness adapter; install/uninstall by writing a single .md.

    Implementation note: we use a real file-copy (not a symlink) for
    portability — most harnesses do not chase symlinks recursively at load
    time, and a copy guarantees independent atomic updates per cell.
    """

    def __init__(self, harness: str):
        if harness not in CELLS:
            raise UnknownAgentError(harness)
        self.harness = harness
        self._cell = CELLS[harness]

    def _resolve_dest(
        self, slug: str, *, scope: str,
        home: Path | None, project: Path | None,
    ) -> Path:
        """Validate scope + expand the cell's template, fail-loud on bad input."""
        if scope not in _VALID_SCOPES:
            raise ValueError(
                f"{self.harness}: scope must be 'global' or 'project', got {scope!r}"
            )
        return _expand(self._cell[scope], home=home, project=project, slug=slug)

    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        """Return the on-disk path this adapter installs to. Read-only.

        Used by the facade's agent-aware 'currently linked' scan to test
        whether this harness already holds a projection (dest.exists()),
        since adapters write real files — never symlinks at the skill path.
        """
        return self._resolve_dest(slug, scope=scope, home=home, project=project)

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        # Fail loud on a missing canonical content file (standard-adapter F8
        # parity) BEFORE filecmp/copy2 raises a raw OSError mid-fan-out.
        if not content_path.exists():
            raise InstallError(
                f"{self.harness}: {slug}: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
        # Adopt-if-identical (#368): a pre-existing byte-identical file (e.g.
        # a pre-sentinel install by this tool) becomes tool-owned.
        if dest.exists() and not dest.is_symlink() and filecmp.cmp(
            content_path, dest, shallow=False,
        ):
            _sentinel_path(dest).write_text("")
            return dest
        # Ownership = SENTINEL, not lock (#368, standard-adapter parity): the
        # facade passes overwrite=True for any locked slug, but a lock entry
        # is per-slug, not per-destination — it is not evidence we own THIS
        # file (G5 harness-expansion clobber, waived from #362 to #368).
        _guard_foreign(dest, harness=self.harness, overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # A symlink at the slot must be REPLACED, never written through —
        # copy2 over a symlink would write into its target (F6 parity).
        if dest.is_symlink():
            dest.unlink()
        shutil.copy2(content_path, dest)
        _sentinel_path(dest).write_text("")
        return dest

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Ownership-guarded detach (#368, standard-adapter parity): unlink
        only when the sentinel exists OR the file byte-matches
        `canonical_content` (covers pre-sentinel installs). A sentinel-less,
        content-divergent file is the user's — leave it, return its path as
        a structured refusal. The sidecar is removed whenever the file is
        gone (orphan hygiene, #361/#366)."""
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        refused: Path | None = None
        if dest.exists() or dest.is_symlink():
            # filecmp.cmp can raise PermissionError (OSError) if dest is
            # unreadable (e.g. chmod 000).  Treat that as not-owned, mirroring
            # translate's equivalent OSError guard.
            try:
                content_match = (
                    canonical_content is not None
                    and canonical_content.exists()
                    and not dest.is_symlink()
                    and filecmp.cmp(canonical_content, dest, shallow=False)
                )
            except OSError:
                content_match = False
            owned = sentinel.exists() or content_match
            if owned:
                dest.unlink()
            else:
                refused = dest
                print(
                    f"{self.harness}: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()
        return refused


def adapter_for(harness: str) -> _SymlinkAdapter:
    """Return the symlink-mechanism adapter for `harness`."""
    return _SymlinkAdapter(harness)

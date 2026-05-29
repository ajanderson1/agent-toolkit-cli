"""Symlink mechanism: write a single .md per agent to a harness-specific dir.

15 cells. Per-cell quirks (path-template, frontmatter rules, name-validation)
live in CELLS below. The adapter is a closure factory: adapter_for(harness)
returns a Protocol-conforming object with install/uninstall.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

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

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> Path:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(content_path, dest)
        return dest

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> None:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        if dest.exists() or dest.is_symlink():
            dest.unlink()


def adapter_for(harness: str) -> _SymlinkAdapter:
    """Return the symlink-mechanism adapter for `harness`."""
    return _SymlinkAdapter(harness)

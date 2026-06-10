"""Migrate ajanderson1/skills (flat monorepo) into 8 category repos.

Drives shipped agent-toolkit-cli verbs in two ordered phases. No CLI source change.
Phase A = global library (skill remove/add — global-only). Phase B = project scopes
(skill uninstall -p / install -p — re-derive from global). Idempotent + dry-runnable +
transactional --apply. See docs/superpowers/specs/2026-06-10-skills-split-into-category-repos-design.md
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

OWNER = "ajanderson1"
SOURCE_REPO = "ajanderson1/skills"

CATEGORY_MAP: dict[str, list[str]] = {
    "skills-workflow": [
        "aj-flow", "aj-issue", "aj-run", "aj-bootstrap",
        "autonomous-run", "project-manager", "repo-recon",
    ],
    "skills-orchestration": ["cmux-pm", "claude-orchestrated-pi-agents"],
    "skills-authoring": ["agent-builder", "skill-builder", "conventions"],
    "skills-journal": ["journal", "journal-maintenance", "learn-for-me", "obsidian"],
    "skills-finance": ["outgoings-admin", "pocketsmith", "bank-statement-download"],
    "skills-infra": [
        "contexts", "dev-server", "kuma-uptime", "domain-manager",
        "mkdocs", "pypi", "bitwarden",
    ],
    "skills-comms": ["telegram", "whatsapp-backup"],
    "skills-android": ["android-driver", "apk-deep-audit", "apk-workbench"],
}

MIGRATED_SLUGS: set[str] = {s for slugs in CATEGORY_MAP.values() for s in slugs}

# `servers` is a broken same-subtree dup of `contexts` (no servers/ dir exists).
# Re-point its lock entries to contexts in skills-infra, keeping local slug `servers`.
ALIAS_REMAP: dict[str, tuple[str, str]] = {"servers": ("contexts", "skills-infra")}


def repo_for_slug(slug: str) -> str:
    for repo, slugs in CATEGORY_MAP.items():
        if slug in slugs:
            return repo
    raise KeyError(f"{slug} is not in the category map")


def _first_party_slugs(lock_paths: list[Path]) -> set[str]:
    found: set[str] = set()
    for lock in lock_paths:
        data = json.loads(lock.read_text())   # fail loud on parse error
        for slug, e in data.get("skills", {}).items():
            if e.get("source") == SOURCE_REPO:
                found.add(slug)
    return found


def unmapped_first_party_slugs(lock_paths: list[Path]) -> set[str]:
    """First-party slugs registered against the old source that are neither mapped
    nor a known alias — these would be silently stranded. Caller must fail loud."""
    return _first_party_slugs(lock_paths) - MIGRATED_SLUGS - set(ALIAS_REMAP)


def discover_lock_paths(roots: list[Path]) -> list[Path]:
    """All skills-lock.json under roots (recursive), excluding .worktrees/,
    Claude-managed .claude/worktrees/, and cache trees (.cache — a live uv
    git-checkout under ~/.cache/uv/ holds an old-source lock snapshot; cache
    copies are disposable, not scopes to migrate).
    Global lock is passed explicitly by the caller, not discovered here."""
    found: list[Path] = []
    for root in roots:
        for p in sorted(root.rglob("skills-lock.json")):
            parts = p.parts
            if ".worktrees" in parts or ".cache" in parts:
                continue
            if ".claude" in parts and "worktrees" in parts:
                continue
            found.append(p)
    return found


def find_lock_scopes_for_slug(slug: str, *, lock_paths: list[Path]) -> list[Path]:
    """Locks where `slug` is registered against the OLD source. Fails loud on
    unparseable locks (no silent skip — see conventions: fail loudly)."""
    hits: list[Path] = []
    for lock in lock_paths:
        data = json.loads(lock.read_text())
        entry = data.get("skills", {}).get(slug)
        if entry and entry.get("source") == SOURCE_REPO:
            hits.append(lock)
    return hits


@dataclass(frozen=True)
class Action:
    phase: str            # "A" (global) | "B" (project)
    verb: str             # remove | add | install | uninstall | needs-decision
    slug: str
    scope: Path
    new_source: str | None = None
    agents: tuple[str, ...] = field(default_factory=tuple)


def projected_agents(slug: str, scope: str, lock: Path) -> tuple[str, ...]:
    """Agent TOKENS (as accepted by `--agents`) whose on-disk projection
    symlink for `slug` exists at this scope.

    Lock entries do NOT record agents (LockEntry has no such field — parked
    #230), so the symlinks are the only source of truth. NOTE this is NOT a
    straight copy of remove_cmd's will_delete loop: that loop only enumerates
    paths to DELETE, so synthetic catalog names are harmless there — but THIS
    list is fed back into `--agents`, and _resolve_agents
    (commands/skill/__init__.py) hard-rejects synthetics like "general-skill".
    Two rules:
      1. skip ALL synthetic catalog entries, not just "universal";
      2. a universal-bundle link surfaces as the literal "universal" token —
         the only token that restores the bundle BY DESIGN (real agents like
         dexto sharing .agents/skills restore it only by coincidence) — and
         agents whose projection dir IS the bundle path collapse into it.
    """
    from agent_toolkit_cli.skill_paths import AGENTS, agent_projection_dir

    synthetic = {"universal", "general-skill", "general-agent"}
    project = None if scope == "global" else lock.parent
    bundle = agent_projection_dir("universal", slug, scope=scope, home=None, project=project)
    found: list[str] = []
    if bundle.is_symlink():
        found.append("universal")
    for name in AGENTS:
        if name in synthetic:
            continue
        link = agent_projection_dir(name, slug, scope=scope, home=None, project=project)
        if link.is_symlink() and link != bundle:
            found.append(name)
    return tuple(dict.fromkeys(found))


_SECRET_NAME_RE = re.compile(r"(credentials|learnings)\.md$", re.I)
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def scan_for_secrets(skill_tree: Path) -> list[Path]:
    """Files that match secret-bearing names OR contain a UUID (Bitwarden item id
    shape). The migration MUST halt for human review on any hit before publishing."""
    hits: list[Path] = []
    for f in skill_tree.rglob("*"):
        if not f.is_file():
            continue
        if _SECRET_NAME_RE.search(f.name):
            hits.append(f); continue
        try:
            if _UUID_RE.search(f.read_text(errors="ignore")):
                hits.append(f)
        except OSError:
            pass
    return sorted(set(hits))


def _global_entry(global_lock: Path, slug: str) -> dict | None:
    return json.loads(global_lock.read_text()).get("skills", {}).get(slug)


def build_action_plan(
    *, slugs: list[str], global_lock: Path, project_locks: list[Path],
    projected_agents: Callable[[str, str, Path], tuple[str, ...]] = projected_agents,
) -> list[Action]:
    """Phase A (global) for every slug FIRST, then Phase B (project).

    Global rule per slug: entry on NEW source -> no-op; entry on OLD source ->
    remove+add+install (the install restores the agent projections `remove
    --force` deletes and `add` does not recreate); entry MISSING -> prerequisite
    add (covers project-only slugs like apk-workbench AND the remove-succeeded/
    add-failed stranded state, so re-runs self-heal instead of skipping)."""
    a: list[Action] = []
    b: list[Action] = []
    for slug in slugs:
        new_source = f"{OWNER}/{repo_for_slug(slug)}"
        entry = _global_entry(global_lock, slug)
        if entry is None:
            a += [Action("A", "add", slug, global_lock, new_source)]
        elif entry.get("source") == SOURCE_REPO:
            agents = projected_agents(slug, "global", global_lock)
            a += [Action("A", "remove", slug, global_lock),
                  Action("A", "add", slug, global_lock, new_source)]
            if agents:
                a += [Action("A", "install", slug, global_lock, new_source, agents=agents)]
        for scope in find_lock_scopes_for_slug(slug, lock_paths=project_locks):
            agents = projected_agents(slug, "project", scope)
            if not agents:
                # projection-less old-source entry (live: whatsapp_sync et al.):
                # an uninstall/install pair would let `uninstall -p` destroy the
                # lock entry BEFORE any empty-agents guard can fire. Plan a
                # needs-decision marker instead; main() blocks --apply on these.
                b += [Action("B", "needs-decision", slug, scope)]
                continue
            b += [Action("B", "uninstall", slug, scope, agents=agents),
                  Action("B", "install", slug, scope, new_source, agents=agents)]
    return a + b

"""Migrate ajanderson1/skills (flat monorepo) into 8 category repos.

Drives shipped agent-toolkit-cli verbs in two ordered phases. No CLI source change.
Phase A = global library (skill remove/add — global-only). Phase B = project scopes
(skill uninstall -p / install -p — re-derive from global). Idempotent + dry-runnable +
transactional --apply. See docs/superpowers/specs/2026-06-10-skills-split-into-category-repos-design.md
"""
from __future__ import annotations
import json
from pathlib import Path

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

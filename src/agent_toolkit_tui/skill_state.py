"""Data model for the TUI's skill tab.

Reads the lock + filesystem to produce SkillRow records with per-(agent, scope)
cell state plus a working-tree state badge.

Row-universe contract (#360 — canonical statement, cross-referenced by
agent_state.py, pi_extension_state.py and instruction_state.py):
the row universe is the UNION of the library lock and the scope lock. At
global scope the two are the same file, so the union is a no-op. At project
scope: library-only slugs render as `library` (dim, available), slugs in both
locks render their installed state, and project-lock-only slugs render as
`unlisted` (warning) — installed and functional, but no longer tracked by the
library.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.paperclip_paths import detect_paperclip_company
from agent_toolkit_cli.skill_install import _should_skip_symlink
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir, canonical_skill_dir, library_lock_path,
    library_root, library_skill_path, lock_file_path, parent_clone_path,
    project_parents_root, project_store_root,
)
from agent_toolkit_tui.composition import skills_nonstandard_main

# "library" means the skill exists in the library but is not installed in this
# project (no project canonical at <project>/.agents/skills/<slug>/). This is
# the normal pre-install state and is rendered in dim/gray — not alarming.
# "unlisted" means the inverse: installed at project scope (project lock entry
# + working canonical) but the slug is missing from the library lock — e.g.
# after `skill remove <slug>` at global scope. Functional, rendered with a
# warning tint. See the module docstring for the row-universe contract.
State = Literal["clean", "dirty", "missing", "copy", "library", "unlisted"]
Scope = Literal["global", "project"]

def interactive_agents(
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Rendered skill cells, derived at call time from the user selection."""
    return ("standard",) + skills_nonstandard_main(selection)


@dataclass(frozen=True)
class SkillCell:
    linked: bool       # symlink resolves to canonical (or canonical exists for skipped)
    drift: bool        # symlink exists, points elsewhere, AND canonical exists at this scope
    skipped: bool      # standard-global: no symlink needed, canonical IS the dir
    stray: bool = False  # symlink exists but skill isn't installed at this scope
    available: bool = True  # False → the harness cannot be toggled in this context
    unavailable_reason: str = ""  # human-facing explanation when not available


@dataclass
class SkillRow:
    slug: str
    source: str
    ref: str
    state: State
    cells: dict[tuple[str, str], SkillCell] = field(default_factory=dict)
    description: str = ""


def _read_skill_description(canonical: Path) -> str:
    """Best-effort: read the `description:` from <canonical>/SKILL.md frontmatter.

    Returns "" for any failure mode (missing dir, missing file, no frontmatter,
    parse error, non-dict, missing key). Collapses whitespace so the cell stays
    single-line.
    """
    if not canonical.exists() or not canonical.is_dir():
        return ""
    skill_md = canonical / "SKILL.md"
    try:
        text = skill_md.read_text()
    except OSError:
        return ""
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return ""
    if not isinstance(fm, dict):
        return ""
    raw = fm.get("description")
    if raw is None:
        return ""
    return " ".join(str(raw).split())


def _standard_bundle_link(slug: str) -> Path:
    """Return the ~/.agents/skills/<slug> path for the standard-bundle install."""
    return Path.home() / ".agents" / "skills" / slug


def _project_standard_link(project: Path, slug: str) -> Path:
    """Return the <project>/.agents/skills/<slug> path for the project standard bundle."""
    return project / ".agents" / "skills" / slug


def _cell_for(
    slug: str, agent_name: str, *,
    scope: Scope, home: Path | None, project: Path | None,
    canonical: Path | None = None,
) -> SkillCell:
    # The synthetic "standard" token has its own detection logic: it does NOT
    # use _should_skip_symlink (that function doesn't understand "standard" as
    # an agent_name — the engine strips it before calling skip checks).
    if canonical is None:
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project,
        )
    if agent_name == "standard":
        # The standard bundle is one shared projection symlink that all
        # standard agents read through. Both scopes detect it the same way now:
        # linked iff the bundle link is a symlink resolving to the canonical
        # (which lives in the library at global scope, the external store at
        # project scope). Global: ~/.agents/skills/<slug>; project:
        # <project>/.agents/skills/<slug>.
        bundle_link = (
            _standard_bundle_link(slug)
            if scope == "global"
            else _project_standard_link(project, slug)  # type: ignore[arg-type]
        )
        if not bundle_link.is_symlink():
            return SkillCell(linked=False, drift=False, skipped=False)
        canonical_real = canonical.resolve() if canonical.exists() else canonical
        if bundle_link.resolve() == canonical_real:
            return SkillCell(linked=True, drift=False, skipped=False)
        # Symlink exists but points elsewhere — drifted.
        return SkillCell(linked=False, drift=True, skipped=False)

    if agent_name == "paperclip":
        # Global cells still need the caller's current company context to
        # explain whether the correction is “switch scope” or “open a company.”
        context_path = project or Path.cwd()
        context = detect_paperclip_company(context_path)
        if scope != "project" or context is None:
            if scope == "global" and context is not None:
                reason = (
                    "Paperclip is project-only; switch the TUI to Project scope."
                )
            else:
                reason = (
                    "Paperclip skills are company-scoped; open the TUI inside "
                    "~/.paperclip/instances/<instance>/companies/<company-id>."
                )
            return SkillCell(
                linked=False,
                drift=False,
                skipped=False,
                available=False,
                unavailable_reason=reason,
            )
        # Available company project cell: falls through to the standard
        # link/drift/stray probe below via agent_projection_dir().

    skip, _ = _should_skip_symlink(
        agent_name=agent_name, scope=scope, project=project,
    )
    if skip:
        return SkillCell(linked=canonical.exists(), drift=False, skipped=True)
    link = agent_projection_dir(
        agent_name, slug, scope=scope, home=home, project=project,
    )
    if not link.is_symlink():
        return SkillCell(linked=False, drift=False, skipped=False)
    canonical_real = canonical.resolve() if canonical.exists() else canonical
    if link.resolve() == canonical_real:
        return SkillCell(linked=True, drift=False, skipped=False)
    # Symlink points elsewhere. If the skill isn't installed at this scope
    # (no canonical on disk) treat it as 'stray' rather than 'drift' — there's
    # nothing to re-link to, the right fix is to remove the symlink.
    if not canonical.exists():
        return SkillCell(linked=False, drift=False, skipped=False, stray=True)
    return SkillCell(linked=False, drift=True, skipped=False)


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _discover_unmanaged_skills(root: Path) -> list[tuple[str, Path]]:
    """Bounded filesystem discovery of skills and bundle sub-skills under root.

    Discovers:
    - Standalone skills: <root>/<slug>/SKILL.md -> slug
    - Bundle containers: <root>/<bundle>/SKILL.md -> bundle
    - Nested bundle skills: <root>/<bundle>/skills/<subskill>/SKILL.md
      or <root>/<bundle>/<subskill>/SKILL.md -> f"{bundle}:{subskill}"

    Does not follow escaping symlinks or crash on dangling symlinks.
    Ignores _parents, hidden directories, and *.bak-* leftovers.
    """
    if not root.is_dir():
        return []
    results: list[tuple[str, Path]] = []
    seen_slugs: set[str] = set()
    try:
        children = sorted(root.iterdir())
    except OSError:
        return []

    for top in children:
        if top.name.startswith(".") or top.name == "_parents" or ".bak-" in top.name:
            continue
        try:
            if not top.exists() or not top.is_dir():
                continue
        except OSError:
            continue

        if top.is_symlink():
            try:
                target = top.resolve()
                if not target.exists() or not target.is_dir():
                    continue
            except OSError:
                continue

        # Check top-level SKILL.md
        top_skill = top / "SKILL.md"
        if top_skill.is_file():
            results.append((top.name, top))
            seen_slugs.add(top.name)

        # Bounded scan for nested skills inside top
        try:
            subdirs = sorted(top.iterdir())
        except OSError:
            subdirs = []

        for sub in subdirs:
            if sub.name.startswith(".") or sub.name == "_parents" or ".bak-" in sub.name:
                continue
            if sub.is_symlink() and not _is_inside(sub, top):
                continue
            try:
                if not sub.exists() or not sub.is_dir():
                    continue
            except OSError:
                continue

            if sub.name == "skills":
                try:
                    nested_dirs = sorted(sub.iterdir())
                except OSError:
                    nested_dirs = []
                for nested in nested_dirs:
                    if nested.name.startswith(".") or ".bak-" in nested.name:
                        continue
                    if nested.is_symlink() and not _is_inside(nested, top):
                        continue
                    try:
                        if not nested.exists() or not nested.is_dir():
                            continue
                    except OSError:
                        continue
                    if (nested / "SKILL.md").is_file():
                        slug = f"{top.name}:{nested.name}"
                        if slug not in seen_slugs:
                            results.append((slug, nested))
                            seen_slugs.add(slug)
            else:
                if (sub / "SKILL.md").is_file():
                    slug = f"{top.name}:{sub.name}"
                    if slug not in seen_slugs:
                        results.append((slug, sub))
                        seen_slugs.add(slug)

    return results


def build_skill_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    selection: tuple[str, ...] | None = None,
) -> list[SkillRow]:
    # Row universe = union(library lock, scope lock) + filesystem.
    # At global scope the library lock IS the scope lock, so the union is a
    # no-op. At project scope, project-lock-only slugs are `unlisted`.
    lib_lock = read_lock(library_lock_path(home=home))
    universe = dict(lib_lock.skills)
    unlisted: set[str] = set()
    if scope == "project":
        proj_lock = read_lock(
            lock_file_path(scope="project", home=home, project=project)
        )
        for slug, proj_entry in proj_lock.skills.items():
            if slug not in universe:
                universe[slug] = proj_entry
                unlisted.add(slug)
    harnesses = interactive_agents(selection)
    rows: list[SkillRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project,
        )
        if slug in unlisted:
            # Project-lock-only: functional install, library no longer tracks
            # it. Supersedes the git working-tree badge, like `library` does.
            # `unlisted` requires the project canonical on disk — a fresh
            # clone of a committed skills-lock.json has the entry but no
            # store canonical, which is a broken install: `missing` (G2).
            state: State = "unlisted" if canonical.exists() else "missing"
        elif not canonical.exists():
            # Project scope: slug is in the library but not yet installed here.
            # Global scope: library entry recorded but directory was deleted.
            state = "library" if scope == "project" else "missing"
        elif entry.parent_url is not None:
            # Monorepo skill — state lives in the parent clone, not the
            # symlinked subpath (which has no `.git/` of its own).
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
                root=project_parents_root(project) if scope == "project" else None,
            )
            if not skill_git.is_git_repo(parent_dir):
                # Parent clone missing — user `rm -rf`'d it, or
                # materialised: copy with no parent available.
                state = "copy"
            else:
                wt = skill_git.status(parent_dir, env=None)
                state = (
                    "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                    else "clean"
                )
        elif not skill_git.is_git_repo(canonical):
            # Plain-file install (e.g. `npx skills add --copy`).
            state = "copy"
        else:
            wt = skill_git.status(canonical, env=None)
            state = (
                "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                else "clean"
            )
        cells: dict[tuple[str, str], SkillCell] = {}
        for agent in harnesses:
            cells[(agent, scope)] = _cell_for(
                slug, agent, scope=scope, home=home, project=project,
            )
        # In project scope, also probe global so the SkillGrid can render
        # the globally-installed indicator (#188). Skipped when home is
        # None (callers that don't care about the indicator).
        if scope == "project" and home is not None:
            for agent in harnesses:
                cells[(agent, "global")] = _cell_for(
                    slug, agent, scope="global", home=home, project=None,
                )
        description = _read_skill_description(canonical)
        if not description and scope == "project":
            # Project canonical may be absent (state == "library") or missing
            # SKILL.md; fall back to the library copy, which is the source of
            # truth for the description anyway.
            description = _read_skill_description(library_skill_path(slug))
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "(default)",
            state=state, cells=cells,
            description=description,
        ))

    # Bounded filesystem discovery of unmanaged skills/bundles
    scan_root = (
        library_root(home=home)
        if scope == "global"
        else (project_store_root(project) if project is not None else None)
    )
    if scan_root is not None:
        for disc_slug, disc_path in _discover_unmanaged_skills(scan_root):
            if disc_slug in universe:
                continue
            cells = {}
            for agent in harnesses:
                cells[(agent, scope)] = _cell_for(
                    disc_slug, agent, scope=scope, home=home, project=project,
                    canonical=disc_path,
                )
            if scope == "project" and home is not None:
                for agent in harnesses:
                    cells[(agent, "global")] = _cell_for(
                        disc_slug, agent, scope="global", home=home, project=None,
                        canonical=disc_path,
                    )
            description = _read_skill_description(disc_path)
            rows.append(SkillRow(
                slug=disc_slug,
                source="untracked",
                ref="(untracked)",
                state="unlisted",
                cells=cells,
                description=description,
            ))

    return rows

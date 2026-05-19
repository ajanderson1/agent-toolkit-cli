"""Pure inventory builder for Pi extensions.

Caller resolves filesystem state for the third-party channel (node_modules sets)
and the allowlist sections; this module synthesises one PiRecord per unique
slug across both channels.

Note: first-party extension-dir discovery (iterating `~/.pi/agent/extensions/`)
is performed inside this module — a known mild impurity that keeps the
auto-discovery rule encapsulated. Third-party inputs (node_modules) remain
caller-provided sets.

Slug derivation:
- first-party: directory name under <home>/.pi/agent/extensions/<slug>/
- npm: source string after `npm:` is the package name. Slug = same.
- git: last path segment of the URL, after stripping `@<ref>` suffix.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Origin = Literal["first-party", "third-party"]
Intent = Literal["user", "project", "both", "none"]


@dataclass(frozen=True)
class PiRecord:
    slug: str
    origin: Origin
    source: str
    user_loaded: bool
    project_loaded: bool
    user_installed_at: str | None
    project_installed_at: str | None
    toolkit_intent: Intent

    def to_dict(self) -> dict:
        return asdict(self)


def _slug_from_source(source: str) -> str:
    """Derive a display slug from a `packages[]` source string.

    Rules (see module docstring):
    - `npm:foo` -> `foo`
    - `git:host/path/repo@ref` -> last segment of path, ref stripped
    - any other shape -> return source verbatim (caller may flag in doctor)
    """
    if source.startswith("npm:"):
        return source[len("npm:") :]
    if source.startswith("git:"):
        body = source[len("git:") :]
        body = body.split("@", 1)[0]  # strip @ref
        return body.rsplit("/", 1)[-1]
    return source


def _intent_for(*, in_user: bool, in_project: bool) -> Intent:
    if in_user and in_project:
        return "both"
    if in_user:
        return "user"
    if in_project:
        return "project"
    return "none"


def build_pi_inventory(
    *,
    home: Path,
    project_root: Path,
    user_packages: list[str],
    project_packages: list[str],
    user_node_modules: set[str],
    project_node_modules: set[str],
    allowlist_pi_extensions: list[str],
    allowlist_pi_packages: list[str],
) -> list[PiRecord]:
    """Build the unified inventory across both Pi extension channels.

    See module docstring for slug derivation rules.
    """
    # Resolve filesystem state for first-party (auto-discovery dirs).
    user_ext_dir = home / ".pi" / "agent" / "extensions"
    project_ext_dir = project_root / ".pi" / "extensions"

    user_ext_slugs: set[str] = (
        {p.name for p in user_ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
        if user_ext_dir.is_dir()
        else set()
    )
    project_ext_slugs: set[str] = (
        {p.name for p in project_ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
        if project_ext_dir.is_dir()
        else set()
    )

    # Index third-party sources by derived slug.
    user_third_party: dict[str, str] = {
        _slug_from_source(s): s for s in user_packages
    }
    project_third_party: dict[str, str] = {
        _slug_from_source(s): s for s in project_packages
    }

    # Index allowlist intent.
    allowlist_third_party_slugs: set[str] = {
        _slug_from_source(s) for s in allowlist_pi_packages
    }
    allowlist_first_party_slugs: set[str] = set(allowlist_pi_extensions)

    # Union of all slugs across both channels.
    all_first_party = (
        user_ext_slugs | project_ext_slugs | allowlist_first_party_slugs
    )
    all_third_party = (
        set(user_third_party) | set(project_third_party) | allowlist_third_party_slugs
    )

    out: list[PiRecord] = []

    for slug in sorted(all_first_party):
        user_loaded = slug in user_ext_slugs
        project_loaded = slug in project_ext_slugs
        intent = _intent_for(
            in_user=slug in allowlist_first_party_slugs,
            in_project=False,  # allowlist_pi_extensions is user-scope today; project-scope intent is future work
        )
        out.append(
            PiRecord(
                slug=slug,
                origin="first-party",
                source=f"extension:{slug}",
                user_loaded=user_loaded,
                project_loaded=project_loaded,
                user_installed_at=str(user_ext_dir / slug) if user_loaded else None,
                project_installed_at=str(project_ext_dir / slug)
                if project_loaded
                else None,
                toolkit_intent=intent,
            )
        )

    # Third-party — skip slugs that won (first-party collision).
    first_party_won = {r.slug for r in out}
    for slug in sorted(all_third_party - first_party_won):
        user_source = user_third_party.get(slug)
        project_source = project_third_party.get(slug)
        display_source = user_source or project_source or f"npm:{slug}"

        user_loaded = (slug in user_third_party) and (slug in user_node_modules)
        project_loaded = (slug in project_third_party) and (
            slug in project_node_modules
        )

        intent = _intent_for(
            in_user=any(
                _slug_from_source(s) == slug for s in allowlist_pi_packages
            ),
            in_project=False,
        )

        out.append(
            PiRecord(
                slug=slug,
                origin="third-party",
                source=display_source,
                user_loaded=user_loaded,
                project_loaded=project_loaded,
                user_installed_at=str(
                    home / ".pi/agent/npm/node_modules" / slug
                )
                if user_loaded
                else None,
                project_installed_at=str(
                    project_root / ".pi/npm/node_modules" / slug
                )
                if project_loaded
                else None,
                toolkit_intent=intent,
            )
        )

    return out

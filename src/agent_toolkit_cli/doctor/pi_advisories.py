"""Doctor advisories for Pi extensions.

Three checks (all read-only):
1. Hand-authored extension — a real (non-symlink) dir under
   ``~/.pi/agent/extensions/<slug>/``. Likely operator-authored content the
   toolkit didn't create. Surface so operator can decide.
2. Drift — ``pi_packages:`` declares an entry that has no matching
   ``settings.json`` ``packages[]`` entry OR no resolved
   ``node_modules/<slug>/``.
3. Slug collision — same slug appears in both ``pi_extensions:`` and
   ``pi_packages:`` (first-party wins for ``origin``, but the operator should
   know).

The advisory module returns a flat ``list[PiAdvisory]``. The doctor runner
aggregates these into a single ``GroupResult`` named ``pi-advisories`` for the
existing print pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli._pi_inventory import slug_from_source
from agent_toolkit_cli._pi_paths import PiPaths
from agent_toolkit_cli._pi_settings import read_extensions_overrides, read_packages
from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.harness_adapters.base import Scope


@dataclass(frozen=True)
class PiAdvisory:
    """A single advisory finding. ``level`` is ``"warn"`` for all current checks."""

    level: str
    message: str


def _hand_authored(pp: PiPaths) -> list[PiAdvisory]:
    out: list[PiAdvisory] = []
    for scope, ext_dir in (
        ("user", pp.user_extensions_dir),
        ("project", pp.project_extensions_dir),
    ):
        if not ext_dir.is_dir():
            continue
        for child in sorted(ext_dir.iterdir()):
            if child.is_symlink():
                continue
            if child.is_dir():
                out.append(
                    PiAdvisory(
                        level="warn",
                        message=(
                            f"Hand-authored extension {child.name!r} ({scope}) "
                            "— not a symlink. The toolkit didn't create this. "
                            "If intentional, ignore; otherwise consider `pi unload`."
                        ),
                    )
                )
    return out


def _drift(
    *,
    scope: Scope,
    declared_packages: list[str],
    settings_json: Path,
    node_modules_dir: Path,
) -> list[PiAdvisory]:
    out: list[PiAdvisory] = []
    resolved = read_packages(settings_json)
    if node_modules_dir.is_dir():
        node_modules_present = {
            p.name
            for p in node_modules_dir.iterdir()
            if p.is_dir() or p.is_symlink()
        }
    else:
        node_modules_present = set()

    for source in declared_packages:
        in_settings = source in resolved
        slug = slug_from_source(source)
        in_node_modules = slug in node_modules_present
        if in_settings and in_node_modules:
            continue
        missing = []
        if not in_settings:
            missing.append("settings.json")
        if not in_node_modules:
            missing.append("node_modules")
        out.append(
            PiAdvisory(
                level="warn",
                message=(
                    f"drift ({scope}): pi_packages declares {source!r} but missing from "
                    f"{', '.join(missing)}. "
                    f"Run `agent-toolkit-cli pi load {source} --scope {scope}` to reconcile."
                ),
            )
        )
    return out


def _slug_collisions(
    *, first_party: list[str], declared_packages: list[str]
) -> list[PiAdvisory]:
    fp = set(first_party)
    tp = {slug_from_source(s) for s in declared_packages}
    return [
        PiAdvisory(
            level="warn",
            message=(
                f"slug collision: {clash!r} appears in both pi_extensions and "
                "pi_packages. First-party wins for `origin`; remove one to "
                "disambiguate."
            ),
        )
        for clash in sorted(fp & tp)
    ]


def _orphaned_overrides(pp: PiPaths) -> list[PiAdvisory]:
    """Warn when an `extensions[]` entry targets a slug that doesn't exist.

    Globs (`*` / `?`) are exempt — too easy to false-positive against a
    well-intentioned wildcard like `status-*`.
    """
    out: list[PiAdvisory] = []
    for scope, ext_dir, settings_path in (
        ("user", pp.user_extensions_dir, pp.user_settings_json),
        ("project", pp.project_extensions_dir, pp.project_settings_json),
    ):
        overrides = read_extensions_overrides(settings_path)
        if not overrides:
            continue
        known = (
            {p.name for p in ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
            if ext_dir.is_dir()
            else set()
        )
        for entry in overrides:
            bare = entry
            for prefix in ("!", "+", "-"):
                if bare.startswith(prefix):
                    bare = bare[1:]
                    break
            if "*" in bare or "?" in bare:
                continue
            if bare in known:
                continue
            out.append(
                PiAdvisory(
                    level="warn",
                    message=(
                        f"orphaned settings.json extensions[] override "
                        f"{entry!r} ({scope}) — no auto-discovered extension "
                        f"with that name. Remove the entry from {settings_path}."
                    ),
                )
            )
    return out


def audit_pi(*, home: Path, project_root: Path) -> list[PiAdvisory]:
    """Run all Pi advisories and return findings (empty list when clean)."""
    pp = PiPaths(home=home, project_root=project_root)
    out: list[PiAdvisory] = []
    out.extend(_hand_authored(pp))

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    project_allow = read_allowlist(project_root / ".agent-toolkit.yaml")
    user_packages = list(user_allow.get("pi_packages", []))
    project_packages = list(project_allow.get("pi_packages", []))
    first_party = list(user_allow.get("pi_extensions", []))

    out.extend(
        _drift(
            scope="user",
            declared_packages=user_packages,
            settings_json=pp.user_settings_json,
            node_modules_dir=pp.user_node_modules_dir,
        )
    )
    out.extend(
        _drift(
            scope="project",
            declared_packages=project_packages,
            settings_json=pp.project_settings_json,
            node_modules_dir=pp.project_node_modules_dir,
        )
    )
    out.extend(
        _slug_collisions(first_party=first_party, declared_packages=user_packages)
    )
    out.extend(_orphaned_overrides(pp))
    return out


def run(*, home: Path, project_root: Path) -> GroupResult:
    """Doctor-runner adapter: aggregate ``audit_pi`` findings into a GroupResult."""
    advisories = audit_pi(home=home, project_root=project_root)
    if not advisories:
        return GroupResult(
            name="pi-advisories",
            status=Status.OK,
            summary="no hand-authored extensions, drift, or slug collisions",
        )
    return GroupResult(
        name="pi-advisories",
        status=Status.WARN,
        summary=f"{len(advisories)} advisory issue(s)",
        findings=[a.message for a in advisories],
        fix_hint="See each finding; advisories are read-only — no auto-fix.",
    )

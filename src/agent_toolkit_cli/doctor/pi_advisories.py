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
from agent_toolkit_cli._pi_settings import read_packages
from agent_toolkit_cli.doctor.result import GroupResult, Status


@dataclass(frozen=True)
class PiAdvisory:
    """A single advisory finding. ``level`` is ``"warn"`` for all current checks."""

    level: str
    message: str


def _hand_authored(pp: PiPaths) -> list[PiAdvisory]:
    out: list[PiAdvisory] = []
    for ext_dir in (pp.user_extensions_dir, pp.project_extensions_dir):
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
                            f"Hand-authored extension at {child} ({child.name}) "
                            "— not a symlink. The toolkit didn't create this. "
                            "If intentional, ignore; otherwise consider `pi unload`."
                        ),
                    )
                )
    return out


def _drift(pp: PiPaths, *, declared_packages: list[str]) -> list[PiAdvisory]:
    out: list[PiAdvisory] = []
    resolved = read_packages(pp.user_settings_json)
    node_modules_present: set[str]
    if pp.user_node_modules_dir.is_dir():
        node_modules_present = {
            p.name
            for p in pp.user_node_modules_dir.iterdir()
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
                    f"drift: pi_packages declares {source!r} but missing from "
                    f"{', '.join(missing)}. "
                    f"Run `agent-toolkit-cli pi load {source} --scope user` to reconcile."
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


def audit_pi(*, home: Path, project_root: Path) -> list[PiAdvisory]:
    """Run all Pi advisories and return findings (empty list when clean)."""
    pp = PiPaths(home=home, project_root=project_root)
    out: list[PiAdvisory] = []
    out.extend(_hand_authored(pp))

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    declared_packages = list(user_allow.get("pi_packages", []))
    first_party = list(user_allow.get("pi_extensions", []))

    out.extend(_drift(pp, declared_packages=declared_packages))
    out.extend(
        _slug_collisions(first_party=first_party, declared_packages=declared_packages)
    )
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

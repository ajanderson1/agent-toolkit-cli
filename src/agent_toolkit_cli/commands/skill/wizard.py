"""Interactive prompts for `skill add` / `skill remove`.

Built on questionary. Each public entry point accepts a `_io_for_test`
hook that bypasses real I/O for unit tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import questionary

from agent_toolkit_cli.skill_agents import (
    AGENTS, detect_installed_agents,
    get_non_universal_agents, get_universal_agents,
)


@dataclass(frozen=True)
class AgentSelection:
    """Result of select_agents_to_add."""
    agents: tuple[str, ...]
    scope: Literal["global", "project"]


@dataclass(frozen=True)
class SlugSelection:
    slugs: tuple[str, ...]


@dataclass(frozen=True)
class RemoveMode:
    mode: Literal["unlink", "full"]
    confirmed: bool


def select_agents_to_add(
    *, slug: str, canonical_path: Path,
    _io_for_test: AgentSelection | None = None,
) -> AgentSelection:
    """Two-section wizard: Universal (auto-listed) + Additional agents (checkbox)."""
    if _io_for_test is not None:
        return _io_for_test

    universal_agents = get_universal_agents()
    non_universal = get_non_universal_agents()
    detected = set(detect_installed_agents())

    questionary.print(
        "\n── Universal (.agents/skills) ── always included ──",
        style="bold fg:cyan",
    )
    for name in universal_agents:
        questionary.print(f"  • {AGENTS[name].display_name}")
    questionary.print(f"\n  Canonical clone: {canonical_path}\n")

    choices = []
    for name in non_universal:
        cfg = AGENTS[name]
        label = f"{cfg.display_name}    ({cfg.skills_dir.split('/')[0]}/skills/<slug>)"
        choices.append(questionary.Choice(
            label, value=name, checked=(name in detected),
        ))

    agents_choice = questionary.checkbox(
        f"Which additional agents do you want to install '{slug}' to?",
        choices=choices,
    ).ask()
    if agents_choice is None:
        return AgentSelection(agents=(), scope="global")

    # The universal agents always get "selected" — at global scope this
    # means just clone canonical (skip-rule fires); at project scope it
    # creates the <project>/.agents/skills/<slug> symlink.
    selected = tuple(universal_agents) + tuple(agents_choice)

    scope_choice = questionary.select(
        "Scope:",
        choices=[
            questionary.Choice("global  (~/.agents/skills/<slug>)", value="global"),
            questionary.Choice("project (./.agents/skills/<slug>)", value="project"),
        ],
        default="global",
    ).ask()
    if scope_choice is None:
        return AgentSelection(agents=(), scope="global")

    return AgentSelection(agents=selected, scope=scope_choice)


def select_slug_to_remove(
    *, installed_slugs: tuple[str, ...],
    slug_descriptions: dict[str, str],
    _io_for_test: SlugSelection | None = None,
) -> SlugSelection:
    if _io_for_test is not None:
        return _io_for_test
    if not installed_slugs:
        questionary.print("(no skills installed)", style="fg:yellow")
        return SlugSelection(slugs=())
    choices = [
        questionary.Choice(
            f"{slug}  ({slug_descriptions.get(slug, '')})",
            value=slug, checked=False,
        )
        for slug in installed_slugs
    ]
    answer = questionary.checkbox(
        "Which skills do you want to remove?", choices=choices,
    ).ask()
    if answer is None:
        return SlugSelection(slugs=())
    return SlugSelection(slugs=tuple(answer))


def select_remove_mode(
    *, slug: str, will_delete: tuple[str, ...],
    _io_for_test: RemoveMode | None = None,
) -> RemoveMode:
    if _io_for_test is not None:
        return _io_for_test
    mode_choice = questionary.select(
        f"How thoroughly to remove '{slug}'?",
        choices=[
            questionary.Choice(
                "Unlink from specific agents only (keep canonical + lock entry)",
                value="unlink"),
            questionary.Choice(
                "Full remove (canonical clone, lock entry, all symlinks)",
                value="full"),
        ],
        default="full",
    ).ask()
    if mode_choice is None:
        return RemoveMode(mode="full", confirmed=False)
    questionary.print("\nThis will delete:", style="bold fg:yellow")
    for p in will_delete:
        questionary.print(f"  {p}")
    confirmed = questionary.confirm("Confirm?", default=False).ask()
    return RemoveMode(mode=mode_choice, confirmed=bool(confirmed))

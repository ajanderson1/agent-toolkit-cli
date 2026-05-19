"""Unit tests for state.py — pure projection from runner output to InventoryState."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.runner import CLIRunner
from agent_toolkit_tui.state import (
    AssetRow,
    CellState,
    InventoryState,
    build_state,
)


class FakeRunner:
    def __init__(self, doc: dict):
        self._doc = doc

    def list_state(self) -> dict:
        return self._doc


def _doc(repo: str = "/r") -> dict:
    return {
        "toolkit_root": repo,
        "harnesses": ["claude", "codex", "opencode", "gemini", "pi"],
        "assets": [
            {
                "kind": "skill", "slug": "alpha",
                "origin": "first-party",
                "description": "Alpha skill.",
                "path": f"{repo}/skills/alpha/SKILL.md",
                "declared_harnesses": ["claude"],
                "cells": [
                    {"harness": "claude",   "scope": "user",    "status": "linked",
                     "target": f"{repo}/skills/alpha", "allowlisted": True},
                    {"harness": "claude",   "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex",    "scope": "user",    "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "codex",    "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "opencode", "scope": "user",    "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "opencode", "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "gemini",   "scope": "user",    "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "gemini",   "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "pi",       "scope": "user",    "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "pi",       "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                ],
            }
        ],
    }


def test_build_state_returns_one_row_per_asset():
    state = build_state(FakeRunner(_doc()))
    assert isinstance(state, InventoryState)
    assert len(state.rows) == 1
    assert state.rows[0].slug == "alpha"


def test_cells_keyed_by_harness_scope():
    state = build_state(FakeRunner(_doc()))
    row = state.rows[0]
    assert row.cells[("claude", "user")] == CellState(
        status="linked", target_path=Path("/r/skills/alpha"), allowlisted=True
    )
    assert row.cells[("codex", "user")].status == "unsupported"


def test_all_harnesses_populated_from_doc():
    state = build_state(FakeRunner(_doc()))
    assert state.all_harnesses == ("claude", "codex", "opencode", "gemini", "pi")


def test_rows_filter_by_kind():
    doc = _doc()
    doc["assets"].append({
        "kind": "agent", "slug": "builder",
        "origin": "first-party", "description": "Builder agent.",
        "path": "/r/agents/builder.md",
        "declared_harnesses": ["claude", "pi"],
        "cells": [],
    })
    state = build_state(FakeRunner(doc))
    skill_rows = [r for r in state.rows if r.kind == "skill"]
    agent_rows = [r for r in state.rows if r.kind == "agent"]
    assert len(skill_rows) == 1 and len(agent_rows) == 1

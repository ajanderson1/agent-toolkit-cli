"""Tests for the list --report formatter (issue #11)."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.generators.list_report import format_report


def _empty_inventory(toolkit: Path) -> dict:
    return {
        "toolkit_root": str(toolkit),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [],
    }


def test_empty_inventory(tmp_path):
    inv = _empty_inventory(tmp_path / "toolkit")
    out = format_report(inv, project_root=tmp_path / "project")
    assert "Asset inventory report" in out
    assert "(no assets discovered)" in out


def test_single_harness_linked(tmp_path):
    inv = {
        "toolkit_root": str(tmp_path / "toolkit"),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [
            {
                "kind": "skill",
                "slug": "alpha",
                "origin": "first-party",
                "description": "Alpha skill.",
                "path": str(tmp_path / "toolkit" / "skills" / "alpha" / "SKILL.md"),
                "declared_harnesses": ["claude"],
                "cells": [
                    {"harness": "claude", "scope": "user", "status": "linked",
                     "target": str(tmp_path / "toolkit" / "skills" / "alpha"),
                     "allowlisted": True},
                    {"harness": "claude", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    *[{"harness": h, "scope": s, "status": "unsupported",
                       "target": None, "allowlisted": False}
                      for h in ("codex", "opencode", "pi") for s in ("user", "project")],
                ],
            }
        ],
    }
    out = format_report(inv, project_root=tmp_path / "project")
    assert "claude" in out
    assert "user" in out and "project" in out
    assert "alpha" in out
    assert "linked" in out
    assert out.index("\nclaude") < out.index("\ncodex")


def test_multi_harness_multi_scope_grouping(tmp_path):
    inv = {
        "toolkit_root": str(tmp_path / "toolkit"),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [
            {
                "kind": "skill", "slug": "alpha",
                "origin": "first-party", "description": "",
                "path": str(tmp_path / "toolkit" / "skills" / "alpha"),
                "declared_harnesses": ["claude", "codex"],
                "cells": [
                    {"harness": "claude", "scope": "user", "status": "linked",
                     "target": "x", "allowlisted": True},
                    {"harness": "claude", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "user", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    *[{"harness": h, "scope": s, "status": "unsupported",
                       "target": None, "allowlisted": False}
                      for h in ("opencode", "pi") for s in ("user", "project")],
                ],
            },
        ],
    }
    out = format_report(inv, project_root=tmp_path / "project")
    assert "\nclaude" in out
    assert "\ncodex" in out
    assert out.count("alpha") >= 4


def test_deterministic_ordering(tmp_path):
    inv = _empty_inventory(tmp_path / "toolkit")
    inv["assets"].append({
        "kind": "skill", "slug": "alpha",
        "origin": "first-party", "description": "",
        "path": "x", "declared_harnesses": ["claude"],
        "cells": [{"harness": "claude", "scope": "user", "status": "unlinked",
                   "target": None, "allowlisted": False}],
    })
    a = format_report(inv, project_root=tmp_path / "project")
    b = format_report(inv, project_root=tmp_path / "project")
    assert a == b

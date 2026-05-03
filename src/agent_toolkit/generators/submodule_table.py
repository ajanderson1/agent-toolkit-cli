"""Render the submodule table embedded in AGENTS.md."""
from __future__ import annotations

import configparser
from pathlib import Path


def render_submodule_table(toolkit_root: Path) -> str:
    gitmodules = toolkit_root / ".gitmodules"
    if not gitmodules.exists():
        return "_(no submodules)_\n"
    parser = configparser.ConfigParser()
    parser.read(gitmodules)

    rows = ["| Submodule path | URL |", "|---|---|"]
    entries = []
    for section in parser.sections():
        path = parser[section].get("path", "")
        url = parser[section].get("url", "")
        if path and url:
            entries.append((path, url))
    for path, url in sorted(entries):
        rows.append(f"| {path} | {url} |")
    return "\n".join(rows) + "\n"

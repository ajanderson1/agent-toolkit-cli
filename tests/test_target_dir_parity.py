"""Drift detection: bash and Python target-dir tables MUST match.

The bash CLI defines harness_target_dir / project_target_dir in
bin/lib/common.sh. The Python CLI mirrors those tables in
src/agent_toolkit/commands/_list_json.py:_USER_TARGETS / _PROJECT_TARGETS.
This test parses common.sh's case statements and asserts the Python tables
are identical, so adding a new (harness, kind) row to one without the other
fails the lefthook gate.
"""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit.commands._list_json import _PROJECT_TARGETS, _USER_TARGETS

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = REPO_ROOT / "bin" / "lib" / "common.sh"

# Case-statement entries look like:
#   claude:skill)    echo "$HOME/.claude/skills" ;;
#   pi:plugin)       echo "$HOME/.pi/agent/extensions" ;;
# We parse them out of the harness_target_dir() and project_target_dir() functions.

_FN_RE = re.compile(
    r"^\s*(?P<harness>[a-z]+):(?P<kind>[a-z]+)\)\s+echo\s+\"(?P<path>[^\"]+)\"\s*;;",
    re.MULTILINE,
)


def _parse_function(name: str) -> dict[tuple[str, str], str]:
    text = COMMON_SH.read_text()
    # Find the function body
    fn_pat = re.compile(rf"^{name}\(\)\s*\{{(.*?)^\}}", re.MULTILINE | re.DOTALL)
    m = fn_pat.search(text)
    assert m, f"could not find {name}() in {COMMON_SH}"
    body = m.group(1)
    out: dict[tuple[str, str], str] = {}
    for entry in _FN_RE.finditer(body):
        out[(entry.group("harness"), entry.group("kind"))] = entry.group("path")
    return out


def test_user_targets_match_bash():
    bash_table = _parse_function("harness_target_dir")
    assert bash_table, "no entries parsed from harness_target_dir — did the function format change?"
    # Normalise the Python table (its values use {home} placeholder; the bash uses $HOME).
    py_normalised = {k: v.replace("{home}", "$HOME") for k, v in _USER_TARGETS.items()}
    assert py_normalised == bash_table, (
        f"target-dir tables drifted!\n"
        f"  bash-only: {set(bash_table) - set(py_normalised)}\n"
        f"  python-only: {set(py_normalised) - set(bash_table)}\n"
        f"  value mismatches: {[(k, py_normalised[k], bash_table[k]) for k in py_normalised if k in bash_table and py_normalised[k] != bash_table[k]]}"
    )


def test_project_targets_match_bash():
    bash_table = _parse_function("project_target_dir")
    assert bash_table, "no entries parsed from project_target_dir"
    assert _PROJECT_TARGETS == bash_table, (
        f"project target-dir tables drifted!\n"
        f"  bash-only: {set(bash_table) - set(_PROJECT_TARGETS)}\n"
        f"  python-only: {set(_PROJECT_TARGETS) - set(bash_table)}\n"
        f"  value mismatches: {[(k, _PROJECT_TARGETS[k], bash_table[k]) for k in _PROJECT_TARGETS if k in bash_table and _PROJECT_TARGETS[k] != bash_table[k]]}"
    )

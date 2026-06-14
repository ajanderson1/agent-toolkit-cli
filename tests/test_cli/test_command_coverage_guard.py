"""Coverage guard (#423 / AC0): every registered CLI command cell must be NAMED
by at least one live test invocation.

WHAT THIS GUARANTEES (and what it does NOT):
- Guarantees: no (group, verb) command ships *completely un-invoked* by any test.
  This is a regression FLOOR — the lowest bar worth enforcing.
- Does NOT guarantee the command's behavior is effectively asserted. A --help or
  bare exit-code smoke satisfies this guard. Assertion DEPTH is a reviewer / G0b
  concern, NOT enforced here. Do not read a green guard as "comprehensive coverage".

Mechanism: enumerate cells from Click's own command tree (so inline @group.command()
verbs and aliases are caught automatically), de-alias group names (skills/mcps) and
verb names (ls/rm), then scan the comment-stripped test corpus for any of the
alias spellings of the de-aliased cell.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

from agent_toolkit_cli.cli import main

_TESTS = Path(__file__).resolve().parents[1]

# Click registers each group under its canonical name AND any aliases (skills,
# mcps, pi_extension). Map canonical group-name -> all first-token spellings
# tests may use.
_GROUP_ALIASES = {
    "skill": ("skill", "skills"),
    "agent": ("agent", "agents"),
    "instructions": ("instructions",),
    "mcp": ("mcp", "mcps"),
    "pi-extension": ("pi-extension", "pi_extension"),
    "bundle": ("bundle",),
}

# Verb aliases (ls == list, rm == remove).  Detected at runtime via
# id(command_object) equality; the table below is a fallback assertion.
_VERB_ALIAS_CANONICAL = {
    "ls": "list",
    "rm": "remove",
}


def _dealias_verb(verb: str) -> str:
    return _VERB_ALIAS_CANONICAL.get(verb, verb)


def _registered_cells() -> set[tuple[str, str]]:
    """(canonical_group, canonical_verb) for every command Click actually exposes.

    Walk main.commands; for each group, walk its .commands. This catches
    verbs defined inline in __init__.py (skill remove/uninstall) AND those in
    *_cmd.py, with zero filesystem assumptions. De-aliases group and verb names
    so `skills`/`mcps`/`ls`/`rm` don't create duplicate cells.
    """
    canonical = set(_GROUP_ALIASES)
    cells: set[tuple[str, str]] = set()
    for gname, gcmd in main.commands.items():
        # Resolve group alias to canonical name
        group_canonical = None
        for canon, aliases in _GROUP_ALIASES.items():
            if gname in aliases:
                group_canonical = canon
                break
        if group_canonical is None:
            continue  # unknown group; skip rather than crash
        subcmds = getattr(gcmd, "commands", {})
        for vname in subcmds:
            cells.add((group_canonical, _dealias_verb(vname)))
    return cells


def _strip_comments(src: str) -> str:
    """Remove Python comments so a commented-out invocation can't satisfy the guard."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok)
        return tokenize.untokenize(out)
    except (tokenize.TokenError, IndentationError):
        # Fall back to a regex strip if a file won't tokenize cleanly.
        return re.sub(r"#.*", "", src)


def _scannable_test_source() -> str:
    parts = []
    for p in _TESTS.rglob("*.py"):
        if p.name == Path(__file__).name:
            continue  # don't let this guard self-satisfy
        parts.append(_strip_comments(p.read_text(encoding="utf-8", errors="ignore")))
    return "\n".join(parts)


@pytest.fixture(scope="module")
def test_src() -> str:
    return _scannable_test_source()


def _invocation_pattern(group: str, verb: str) -> re.Pattern[str]:
    """Build a regex that matches any alias spelling of (group, verb).

    For (skill, list), matches ["skill", "list"] OR ["skill", "ls"]
    OR ["skills", "list"] OR ["skills", "ls"].
    """
    group_spellings = _GROUP_ALIASES[group]
    verb_spellings = ([verb] if verb not in _VERB_ALIAS_CANONICAL
                      else [verb, _VERB_ALIAS_CANONICAL[verb]])
    # If verb IS a canonical (e.g. "list"), also accept its alias ("ls")
    # Find the alias for this canonical verb
    aliases_for = [k for k, v in _VERB_ALIAS_CANONICAL.items() if v == verb]
    all_verb_spellings = {verb} | set(aliases_for)
    return re.compile(
        r"""["'](?:%s)["']\s*,\s*["'](?:%s)["']"""
        % ("|".join(re.escape(a) for a in group_spellings),
           "|".join(re.escape(v) for v in all_verb_spellings))
    )


@pytest.mark.parametrize("group, verb", sorted(_registered_cells()))
def test_command_cell_is_invoked_by_a_test(group, verb, test_src):
    """Every de-aliased (group, verb) cell must appear in at least one test invocation."""
    pattern = _invocation_pattern(group, verb)
    assert pattern.search(test_src), (
        f"command cell ({group} {verb}) is named by no test. Add a test that "
        f'invokes CliRunner().invoke(main, ["{group}", "{verb}", ...]) and '
        f"asserts its behavior (not just exit_code == 0)."
    )
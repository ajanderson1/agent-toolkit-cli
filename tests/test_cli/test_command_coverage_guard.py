"""Coverage guard (#423 / AC0): every registered CLI command cell must be NAMED
by at least one live test invocation.

WHAT THIS GUARANTEES (and what it does NOT):
- Guarantees: no (group, verb) command ships *completely un-invoked* by any test.
  This is a regression FLOOR — the lowest bar worth enforcing.
- Does NOT guarantee the command's behavior is effectively asserted. A --help or
  bare exit-code smoke satisfies this guard. Assertion DEPTH is a reviewer / G0b
  concern, NOT enforced here. Do not read a green guard as "comprehensive coverage".

Mechanism: enumerate cells from Click's own command tree (so inline @group.command()
verbs and aliases are caught automatically), then scan the comment-stripped test
corpus for a literal ["<group-or-alias>", "<verb>"] invocation.

VERB-ALIASES collapse to their canonical command. `agent ls` and `agent list`
share one callback — they are the SAME behavioral cell, not two — so the guard
counts the command ONCE under its canonical (longest) spelling. Testing `list`
therefore satisfies `ls`. This keeps the guard a behavioral-coverage floor over
distinct commands, not a spell-checker over every alias surface form.
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
# mcps). Map canonical group-name -> all first-token spellings tests may use.
_GROUP_ALIASES = {
    "skill": ("skill", "skills"),
    "agent": ("agent", "agents"),
    "instructions": ("instructions",),
    "mcp": ("mcp", "mcps"),
    "pi-extension": ("pi-extension", "pi_extension"),
    "bundle": ("bundle",),
}


def _registered_cells() -> set[tuple[str, str]]:
    """(group, verb) for every DISTINCT command Click actually exposes.

    Walk main.commands; for each sub-group, walk its .commands. This catches
    verbs defined inline in __init__.py (skill remove/uninstall) AND those in
    *_cmd.py, with zero filesystem assumptions. De-aliases GROUP names so
    `skills`/`mcps` don't double-count.

    VERB-aliases (e.g. `ls` for `list`, `rm` for `remove`) share one callback
    with their canonical verb, so they are collapsed: per group, each distinct
    callback is counted ONCE under its longest spelling (canonical verbs are
    spelled out; aliases abbreviate). This makes the guard a coverage floor over
    distinct *commands*, not over every alias surface form.
    """
    canonical = set(_GROUP_ALIASES)
    cells: set[tuple[str, str]] = set()
    for gname, gcmd in main.commands.items():
        if gname not in canonical:
            continue  # skip the alias registrations (skills, mcps)
        subcmds = getattr(gcmd, "commands", {})
        # Group spellings that share a callback; keep the longest as canonical.
        spellings_by_callback: dict[object, list[str]] = {}
        for vname, vcmd in subcmds.items():
            cb = getattr(vcmd, "callback", None) or vname  # fall back to name
            spellings_by_callback.setdefault(cb, []).append(vname)
        for spellings in spellings_by_callback.values():
            cells.add((gname, max(spellings, key=len)))
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


@pytest.mark.parametrize("group, verb", sorted(_registered_cells()))
def test_command_cell_is_invoked_by_a_test(group, verb, test_src):
    aliases = _GROUP_ALIASES[group]
    # Match an invoke list opening: ["agent", "update"  or  ('agents', 'update'
    pattern = re.compile(
        r"""["'](?:%s)["']\s*,\s*["']%s["']"""
        % ("|".join(re.escape(a) for a in aliases), re.escape(verb))
    )
    assert pattern.search(test_src), (
        f"command cell ({group} {verb}) is named by no test. Add a test that "
        f'invokes CliRunner().invoke(main, ["{aliases[0]}", "{verb}", ...]) and '
        f"asserts its behavior (not just exit_code == 0)."
    )

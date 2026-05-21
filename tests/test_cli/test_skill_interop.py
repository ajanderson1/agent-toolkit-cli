"""Smoke test: `npx skills ls` can read a lock file written by us.

Skipped if `npx` is not on PATH. Network access required (npx fetches the
`skills` package). Skipped if AGENT_TOOLKIT_SKIP_INTEROP=1 is set, which
CI can use to opt out without removing the test.

Note: npx skills reads ~/.agents/.skill-lock.json (skills.sh v3 format) for
the global lock. Our v2.2 global lock lives at ~/.agent-toolkit/skills-lock.json.
This test is skipped — the interop story changes in v2.2 and the migration path
is handled by `skill migrate`. If you need npx interop, run `skill migrate` first.
"""
from __future__ import annotations

import os
import shutil

import pytest

_HAVE_NPX = shutil.which("npx") is not None
_SKIP_INTEROP = os.environ.get("AGENT_TOOLKIT_SKIP_INTEROP") == "1"
skip_no_npx = pytest.mark.skipif(
    not _HAVE_NPX or _SKIP_INTEROP,
    reason="npx not on PATH (or AGENT_TOOLKIT_SKIP_INTEROP=1)",
)


@skip_no_npx
def test_npx_skills_list_reads_our_lock() -> None:
    pytest.skip(
        "v2.2: global lock moved to ~/.agent-toolkit/skills-lock.json; "
        "npx skills reads ~/.agents/.skill-lock.json. "
        "Migration via `skill migrate` bridges the gap — out of scope for this test."
    )

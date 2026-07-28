# Boundary-scan judgment — #480 R7

- **Constants:** `MAIN_HARNESSES` and `_MCP_HARNESSES` have declaration sites only; all remaining hits iterate/filter immutable tuples. `DEFAULT_HARNESSES` is imported and filtered into a new tuple. No in-place mutation or reassignment exists.
- **CLI → TUI:** the required broad scan has one hit: a pre-existing comment in `src/agent_toolkit_cli/_support.py:7` (blame `3b2d7eb`; no branch diff). It is not an import or runtime reference. No CLI import of `agent_toolkit_tui` exists.
- **Import-time snapshots:** no `INTERACTIVE_AGENTS` or `INTERACTIVE_HARNESSES` hits remain in `src/` or `tests/`; the values are now call-time functions.
- **Dependencies:** `git diff origin/main -- pyproject.toml uv.lock` is empty.

**Verdict: PASS** — no #480 runtime CLI dependency, mutable shared constant, or lockfile/dependency change found.

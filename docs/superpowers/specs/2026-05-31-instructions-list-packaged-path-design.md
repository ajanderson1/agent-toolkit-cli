# Design — `instructions list` crashes on packaged installs (#305)

**Date:** 2026-05-31
**Issue:** #305
**Mode:** `--auto`

## Problem

`agent-toolkit-cli instructions list` crashes with `FileNotFoundError` on every
packaged install (wheel via `uv tool install` / `pip` / `pipx`). It only works
from a git source checkout.

Root cause — `src/agent_toolkit_cli/commands/instructions/list_cmd.py:12`:

```python
_DOC = Path(__file__).resolve().parents[4] / "docs/agent-toolkit/harness-matrix.md"
```

`_parse_matrix()` reads the harness matrix via a **repo-relative path**. In a
source checkout `parents[4]` is the repo root, where `docs/agent-toolkit/harness-matrix.md`
exists. In an installed wheel, `parents[4]` points inside `site-packages/` and
`docs/` is **not packaged** (`pyproject.toml` `[tool.hatch.build.targets.wheel]`
lists only `packages = [...]`, no data includes). So the read fails.

Same class as #283: a path that assumes the repo layout survives packaging.

## Scope (verified in #305 + reconnaissance)

- **Broken:** `instructions list` (table + json) — the only production reader of the matrix.
- **Not broken:** `instructions install / uninstall / doctor / status`, and `agent list` / `skill list` — they read lockfiles/adapters, never the matrix doc.
- **Tests that read the matrix** (`tests/test_instructions_matrix.py`, `tests/test_subagent_matrix.py`, `tests/test_cli/test_instructions_adapters/test_dispatcher.py`) resolve it relative to the test file and **only ever run from the source tree**, so they are *not* a production bug — but they are also why CI stayed green: no test exercises the **installed-package** path.

## Decision: ship the matrix as package data, load via `importlib.resources`

The matrix is **hand-maintained**, the documented **SSOT**, referenced from the
README and from parity tests. It must stay at `docs/agent-toolkit/harness-matrix.md`.
Two candidate fixes:

| Option | Verdict |
|---|---|
| **A. Embed parsed matrix as a Python module** (codegen or hand copy) | ✗ Rejected — introduces a second copy that drifts from the doc SSOT unless we add a generator + drift test. More machinery than the bug warrants. |
| **B. Ship the matrix doc inside the package, load via `importlib.resources`** | ✓ **Chosen** — keeps one source of truth, stops resolving repo-relative paths from installed code, standard packaging idiom. |

### Mechanism

1. **Bundle the doc as package data.** Place a copy of the harness matrix under
   `src/agent_toolkit_cli/data/harness-matrix.md` and add a hatch
   `force-include` so it ships in the wheel. The doc at
   `docs/agent-toolkit/harness-matrix.md` remains the human-facing SSOT
   (README links to it); the packaged copy is the runtime artifact.

   To avoid two-copy drift, the packaged copy is **generated from the SSOT**, not
   hand-maintained. Preferred: a hatch build hook copies `docs/.../harness-matrix.md`
   → `src/agent_toolkit_cli/data/harness-matrix.md` at build time, and a test
   asserts the two are byte-identical so drift fails CI. (If a build hook proves
   heavier than the bug warrants, fall back to committing the copy + the drift test —
   the test is the guard either way. Plan picks the lighter mechanism that passes.)

2. **Load via `importlib.resources`.** Replace the `parents[4]` path in
   `list_cmd.py` with:

   ```python
   from importlib import resources
   _matrix_text = (resources.files("agent_toolkit_cli.data") / "harness-matrix.md").read_text(encoding="utf-8")
   ```

   resolved lazily inside `_parse_matrix()` (not at import time) so import never
   touches the filesystem and tests can patch if needed.

## Acceptance criteria

1. `instructions list` and `instructions list --format json` **exit 0 and print the
   matrix** when run from an **installed wheel** (not just the source tree).
2. The harness-matrix content shipped in the wheel is **identical** to
   `docs/agent-toolkit/harness-matrix.md` (no drift; enforced by a test).
3. A **packaging-gap test** runs the `instructions list` code path in a way that
   would have caught this (loads the matrix via the packaged resource, with the
   repo-relative `docs/` path unavailable / not relied upon). The existing
   source-tree CLI tests (`test_instructions_cli.py`) continue to pass.
4. `docs/agent-toolkit/harness-matrix.md` stays the human-facing SSOT; README link
   unchanged.
5. No regression: `install / uninstall / doctor / status`, parity tests, full `pytest -q` green.

## Out of scope

- The test-only `parents[N]` reads in the three matrix-parity tests — they run from
  the source tree by construction and are not a production defect. Left as-is unless
  the chosen packaging mechanism makes pointing them at the packaged copy trivial.
- Any change to the matrix content itself.
- Auditing other kinds for the same bug — reconnaissance confirmed `instructions list`
  is the only production matrix reader.

## Verification

- `uv build` the wheel, install into a throwaway venv, run `instructions list`
  (both formats) → exit 0, expected harnesses present. Captured as a verification
  artifact.
- `uv run pytest -q` green, including the new drift + packaging-gap tests.

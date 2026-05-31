# Plan — `instructions list` packaged-path fix (#305)

**Spec:** `docs/superpowers/specs/2026-05-31-instructions-list-packaged-path-design.md`

## Mechanism (proven by build probe before planning)

`hatch force-include` can map the **SSOT doc itself** into the wheel:

```toml
[tool.hatch.build.targets.wheel.force-include]
"docs/agent-toolkit/harness-matrix.md" = "agent_toolkit_cli/data/harness-matrix.md"
```

Verified: `uv build --wheel` ships `agent_toolkit_cli/data/harness-matrix.md`, and
`importlib.resources.files("agent_toolkit_cli.data") / "harness-matrix.md"` reads
it (37732 chars) from a pip-installed wheel in a throwaway venv.

**Consequence:** there is exactly **one** matrix file (`docs/...`). The wheel
embeds *that file*, not a copy. So the spec's "drift test between two copies" is
unnecessary — there is nothing to drift. The packaging guard becomes simpler: a
test that the matrix is reachable as a packaged resource.

## Tasks (TDD; each is a commit)

### Task 1 — Bundle the matrix as package data
- **pyproject.toml:** add the `[tool.hatch.build.targets.wheel.force-include]` block
  mapping `docs/agent-toolkit/harness-matrix.md` → `agent_toolkit_cli/data/harness-matrix.md`.
- This is build config only; no runtime code yet. Editable installs (`uv sync`)
  will *not* materialise `data/` on disk — that's expected; runtime code (Task 2)
  must tolerate both editable-source and built-wheel layouts.

### Task 2 — Load the matrix via `importlib.resources` with a source-tree fallback
- **`src/agent_toolkit_cli/commands/instructions/list_cmd.py`:**
  - Remove the module-level `_DOC = Path(__file__)...parents[4]...` constant.
  - Add a `_read_matrix_text() -> str` helper that tries, in order:
    1. `importlib.resources.files("agent_toolkit_cli.data") / "harness-matrix.md"` — the packaged/wheel path.
    2. **Fallback** to the repo-relative `docs/agent-toolkit/harness-matrix.md`
       (`Path(__file__).resolve().parents[4] / ...`) for **editable/source-tree**
       runs where `data/` isn't materialised (this is what `uv sync` + the dev
       venv + the existing CLI tests use).
    - Fail loud with a clear `FileNotFoundError`/`click` error naming both
      attempted locations if neither resolves (per fail-loud principle).
  - `_parse_matrix()` calls `_read_matrix_text()` instead of `_DOC.read_text()`.
  - Resolution is **lazy** (inside the function), not at import time.

  > Why a fallback rather than resources-only: the dev workflow runs from an
  > editable install where `force-include` does not copy `data/` into the source
  > tree, so resources-only would break `uv run pytest`'s own CLI tests. The
  > fallback keeps source-tree dev green; the resources path is what real
  > (wheel) installs use. Try-packaged-first means a real install never touches
  > the (absent) repo path.

### Task 3 — Packaging-gap test (the test that would have caught #305)
- **New test** `tests/test_cli/test_instructions_packaging.py`:
  - **Test A (resource reachability):** the matrix is readable via
    `importlib.resources.files("agent_toolkit_cli.data") / "harness-matrix.md"`
    **only when the package data is present**. Since the dev env is editable
    (no `data/`), this test must be robust:
    - Preferred form: build a wheel into a tmp dir (`python -m build` /
      `subprocess` `uv build`), unzip, assert the wheel's namelist contains
      `agent_toolkit_cli/data/harness-matrix.md` and that its bytes equal
      `docs/agent-toolkit/harness-matrix.md`. This asserts the packaging contract
      directly and runs fully in CI without a network.
    - This is the regression guard: if someone drops the `force-include` block,
      this test goes red.
  - **Test B (loader robustness):** call `_read_matrix_text()` / `_parse_matrix()`
    and assert it returns a non-empty, well-formed row set (exercises the loader’s
    fallback in the source tree). Keeps the existing source-tree behaviour pinned.
- Keep the existing `test_instructions_cli.py::test_list_shows_verdict_per_harness`
  and `test_list_json_format` — they continue to validate the source-tree path.

### Task 4 — Verify on a real wheel + full suite
- `uv build`, install into a throwaway venv, run `instructions list` and
  `instructions list --format json` → exit 0, expected harnesses present.
- `uv run pytest -q` green.

## Acceptance (from spec, refined)

1. `instructions list` (table + json) exits 0 from an **installed wheel**. ✅ via Task 1+2, proven by Task 4 artifact.
2. Wheel ships the byte-identical SSOT matrix (one file, force-included — no copy to drift). ✅ via Task 3 Test A.
3. Packaging-gap test would have caught #305 (drop `force-include` → test red). ✅ Task 3 Test A.
4. `docs/...harness-matrix.md` stays the human SSOT; README link unchanged. ✅ untouched.
5. No regression across install/uninstall/doctor/status + parity tests + full pytest. ✅ Task 4.

## Risks / notes
- **Editable installs don't get `data/`.** Mitigated by the Task 2 source-tree
  fallback. Documented inline.
- **Test A builds a wheel** — adds a few seconds to the suite. Acceptable; it is
  the only test that proves the packaging contract. Mark it appropriately so it’s
  greppable, and keep the build in a tmp dir.
- The two **test-only** `parents[N]` matrix reads (`test_instructions_matrix.py`,
  `test_dispatcher.py`) are **out of scope** — they run from the source tree by
  construction and are not a production defect (spec § Out of scope).

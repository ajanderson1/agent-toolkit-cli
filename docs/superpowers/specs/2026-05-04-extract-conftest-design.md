# Extract test fixtures to `tests/conftest.py`

**Issue:** [#8](https://github.com/ajanderson1/agent-toolkit-cli/issues/8) — *Extract test fixtures to tests/conftest.py*
**Date:** 2026-05-04

## Problem

PR #5 added 4 new test files (`tests/test_cli_link.py`, `test_cli_unlink.py`, `test_cli_list.py`, `test_cli_diff.py`). Each duplicates ~48 lines:

- `SKILL_FRONTMATTER` template constant
- `_seed_toolkit(tmp)` helper
- `_seed_skill(toolkit_root, slug, harnesses)` helper
- `env` fixture (sets HOME under tmp_path, clears env vars, seeds toolkit)

That's ~190 lines of identical code across the four files. Drift risk is the real cost — if the toolkit-schema location moves, you must remember to update four files.

## Goals

1. Move the duplicated helpers + the `env` fixture into a single `tests/conftest.py`.
2. The 4 test files lose their duplicated headers entirely (~50 lines each).
3. Existing 290+ test suite remains green. No new tests; pure refactor.
4. **No-import contract for fixtures.** The `env` fixture is auto-discovered by pytest. The two helpers (`_seed_toolkit`, `_seed_skill`) become **factory fixtures** (`seed_toolkit`, `seed_skill`) that return the callable, so test bodies use them as fixture params, no `from conftest import ...` needed.

## Approach

Pytest convention: `conftest.py` is **auto-imported by pytest** but its module-level symbols are **not** available to test files unless explicitly imported. Only fixtures are auto-discovered. Therefore:

- `SKILL_FRONTMATTER` stays as a private module-level constant inside `conftest.py` (used only by `_seed_skill`'s implementation).
- `_seed_toolkit` and `_seed_skill` become **factory fixtures** named `seed_toolkit` and `seed_skill`, each returning the underlying callable. Tests that need them request the fixture as a parameter.
- `env` stays a regular fixture; behaviour unchanged.

### Naming

Drop the leading underscore — they're public test helpers now (the underscore was a "module-private" hint that no longer makes sense across files).

### Mechanical churn

~50 call-sites of `_seed_skill(toolkit, "alpha", ["claude"])` become `seed_skill(toolkit, "alpha", ["claude"])`, each in a function that gains a `seed_skill` parameter. Same for the ~5 `_seed_toolkit` call-sites that exist outside the `env` fixture (most usages live inside `env` itself).

### Files affected

| File | Edit |
|---|---|
| `tests/conftest.py` | **Create.** Hold `SKILL_FRONTMATTER`, `seed_toolkit` fixture, `seed_skill` fixture, `env` fixture. |
| `tests/test_cli_link.py` | Strip lines 14-61 (the duplicated block). Update `_seed_*` call-sites + add `seed_*` fixture params. |
| `tests/test_cli_unlink.py` | Same. |
| `tests/test_cli_list.py` | Same. The local `multi_env` fixture stays in this file (only consumer). |
| `tests/test_cli_diff.py` | Same. |

## Non-goals

- Renaming `env` itself (per issue: out of scope).
- Refactoring `multi_env` (lives only in `test_cli_list.py`; keep there).
- Moving any other fixture from any other test file (this PR scoped to those 4).
- Removing test-file docstrings (`"""Pytest port of …"""`) — they cite the bats files now deleted by PR #18, but they remain accurate historical attribution.

## Tests

No new tests. The existing 298 passing + 2 skipped suite (post-#18 main count) must remain green at the same numbers. Skipped count and the test-id list (`pytest --collect-only -q | wc -l`) must be identical pre/post.

## Risk

Tiny. The fixture-name change is mechanical (`s/_seed_skill/seed_skill/g` plus add `seed_skill` to the function-arg list of every test that uses it). Drift is the only failure mode — if I miss a call-site, the test will fail at collection time with `NameError`.

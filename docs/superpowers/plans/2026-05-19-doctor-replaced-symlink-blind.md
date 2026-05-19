# Plan — fix doctor symlink-integrity replaced-symlink blindness

Refer: spec `docs/superpowers/specs/2026-05-19-doctor-replaced-symlink-blind-design.md`. Closes #121.

## Task 1 — failing tests first (TDD)

File: `tests/test_doctor_groups.py`

1. Add helper `_make_asset_with_harnesses(toolkit_root, kind, slug, harnesses)` that:
   - kind=`skill` → calls existing `_make_skill_with_harnesses`.
   - kind=`agent` → writes `agents/<slug>/AGENT.md` with the same frontmatter shape.
   - kind=`command` → writes `commands/<slug>.md` with frontmatter (mirrors agent shape, single file).
   - kind=`plugin` → writes `plugins/<slug>/plugin.json` containing
     `{"agent_toolkit_cli": {"harnesses": ["claude"], "origin": "first-party", "vendored_via": "none", "lifecycle": "stable"}}`.

2. Add four tests, each:
   - Build fake repo with one asset declaring `["claude"]`.
   - Build fake `$HOME` mirror; create the slot as a real dir (or file, for the agent case) at the projected path — NOT a symlink.
   - `monkeypatch.setenv("HOME", str(fake_home))`.
   - Run `run_sl(tmp_path, harness="claude")`.
   - Assert `result.status == Status.FAIL`.
   - Assert any finding contains the slug AND "not a symlink".

Expected: all four tests fail against current code (silent), confirming the bug.

## Task 2 — minimal fix in `symlinks.py`

In `src/agent_toolkit_cli/doctor/symlinks.py`:

1. Add `fails: list[str] = []` next to `warns`.
2. Between the existing two branches (after the `is_symlink` block, before the alias loop), add:

   ```python
   elif check_path.exists():
       fails.append(
           f"{kind}/{slug}: slot exists but is not a symlink: {check_path}"
       )
       continue
   ```

   (Note: `elif` chains off `if not check_path.exists() and not check_path.is_symlink(): … continue` — restructure so the branches are mutually exclusive: missing → warn+continue, is_symlink → record, exists-but-not-symlink → fail+continue.)

3. At result-build time:
   - If `fails`: return `GroupResult(name=..., status=Status.FAIL, summary=f"{len(fails)} replaced symlink(s), {len(warns)} other issue(s) for harness={harness}", findings=findings + warns + fails, fix_hint=...)`.
   - Else if `warns`: existing WARN path.
   - Else: existing OK path.

## Task 3 — verify

Run `uv run pytest tests/test_doctor_groups.py -k symlinks -q` — expect 4 new tests pass plus existing 3 still green.

Run full suite: `uv run pytest -q`.

Run lint: `uv run ruff check .`.

## Task 4 — commit

Single conventional commit: `fix(doctor): detect symlink slots replaced by file or directory under claude`.

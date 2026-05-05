# Plan — extend translate machinery for directory-slot kinds (#40-B)

## Tasks

### 1. Lift `_scope_cache_root` to a per-harness table (TDD)

Test first: `tests/test_link_lib.py::test_scope_cache_root_supports_codex` — assert correct paths for `codex` user and project; assert `ValueError` for `pi` (unsupported translate harness).

Implementation: `_link_lib.py` — replace the `if harness != "opencode":` branch with a table-driven lookup. Keep `ValueError` for unknown harnesses.

### 2. Plumb directory-slot support through `_render_to_cache` and `maybe_link`

Test first: register a stub `(codex, skill)` translator at module import time in a fixture, call `_render_to_cache(harness="codex", kind="skill", ...)`, assert the returned tuple includes `slot_target == cache_path.parent` and the cache file is at `<cache_root>/skill/<slug>/SKILL.md`.

Implementation:

- `_translated_slot_filename(slug, kind, harness)` — for `(codex, skill)` (and any future directory-slot translate cell), return `slug` (no `.md` — the slot is a directory). Today it already returns bare `slug` for non-opencode-agent/command pairs, so no change needed unless we want to be explicit. Add a comment documenting the directory-slot case.
- `_render_to_cache` — widen the return signature to `(cache_path, slot_target, rendered_bytes)`. For file-slot kinds, `slot_target = cache_path`. For directory-slot kinds, `slot_target = cache_path.parent`. Determination: `slot_target == cache_path` when `_translated_slot_filename(...)` ends with `.md`, else `cache_path.parent`. (Drives off the same SSOT.)
- File-slot detection: `slug-as-filename` (`_translated_slot_filename` returns `<slug>` exactly) means directory-slot. `<slug>.md` means file-slot. The existing `_translated_slot_filename(slug, kind, harness)` returns `<slug>.md` for opencode/agent/command and `<slug>` for everything else. So the check is `slot_filename = _translated_slot_filename(slug, kind, harness); is_directory_slot = not slot_filename.endswith(".md")`.
- The cache file inside the directory is named after the asset's frontmatter file. For skills: `SKILL.md`. Today `_expected_source` returns `asset_path.parent` for skills (the directory) and the asset path itself for agents/commands (the file). The frontmatter filename is `asset_path.name` (i.e. `SKILL.md` for a skill — `asset_path` is the actual file in the directory, e.g. `<toolkit>/skills/<slug>/SKILL.md`). Good — `cache_path = cache_root / kind / slug / asset_path.name` works uniformly when paired with a directory-slot, while file-slot kinds use the existing `cache_path = cache_root / kind / f"{slug}.md"`.
- `maybe_link`: replace `source_path = cache_path` and the symlink line `link_path.symlink_to(source_path)` to use `slot_target`. The cache-staleness check `slot_correct = link_path.is_symlink() and Path(os.readlink(link_path)) == cache_path` becomes `... == slot_target`. Update the dry-run print to show `slot_target` (the relevant value) — but the existing format `"would-link: {link_path} -> {cache_path} (translated from {rel_asset})"` is informative because it shows what's being rendered. Keep `cache_path` in the print since that's the artifact; this matches existing tests' string expectations. Wait — `slot_target` for directory-slot is `cache_path.parent`. The print line should say `link_path -> slot_target` so users see what the symlink actually points at. Update the print and any tests that pin it.

Pre-update tests that match the existing dry-run line: `tests/test_cli_link.py:1022 (test_link_dry_run_opencode_agent_prints_translated_line_no_writes)` asserts `"(translated from"` which we keep, and reads other lines loosely. Should be fine.

### 3. Update `_prune_translated_slot` for directory caches

Test first: stub `(codex, skill)` link, then unlink, assert slot dir gone, cache `SKILL.md` gone, cache `<slug>/` dir gone, cache `skill/` dir intact.

Implementation: after `link_path.unlink()`, if `target.is_dir()` (it's a directory cache), iterate the directory, unlink files, `rmdir` the directory; for file caches, do the existing `target.unlink()`. Wrap rmdir in `try/except OSError: pass` for the tampering case.

Subtle: by the time we read `target` from the symlink, the symlink may already be unlinked. Resolve `target_resolved` (already done at line 553) before unlinking the slot, then operate on `target_resolved`. Double-check the existing flow — it uses `target` (unresolved) at line 567, which works because `os.readlink` returns the recorded target text not a live ref. Keep that, but add the directory branch.

### 4. Widen `_cell_status` to recognise translate-cell cache targets

Test first: upgrade PR-A's regression test to assert `status == "linked"` (currently `!= "unlinked"`). It should fail until step 4 lands.

Implementation: in `_cell_status`, after computing `resolved_target`, before the existing `expected_resolved` check, add a translate-cell branch:

```python
if (harness, kind) in TRANSLATORS:
    try:
        cache_root = _scope_cache_root(harness, scope, project_root).resolve()
    except ValueError:
        cache_root = None
    if cache_root is not None:
        try:
            resolved_target.relative_to(cache_root)
            return ("linked", target)
        except ValueError:
            pass
```

Falls through to the existing toolkit-repo check if not in cache (so a manually-tampered slot symlink to the toolkit still verifies via the existing path).

Imports needed: `from agent_toolkit._translators import TRANSLATORS` and `from agent_toolkit.commands._link_lib import _scope_cache_root`.

### 5. Run full suite

`uv run pytest -q` — expect green (492 + a handful of new tests).

### 6. Commit

Single conventional commit:

```
feat(#40): extend translate machinery for directory-slot kinds

The Phase-3 OpenCode translate path was designed for single-file
slots (agents, commands). Skills are directory assets, so codex
skill translation (PR-C) needs the machinery to handle:
  - per-harness cache layouts (was hardcoded to opencode)
  - directory-shaped cache (<cache>/<kind>/<slug>/<frontmatter>)
  - directory-shaped slot symlinks
  - cache-target recognition in _cell_status

Lifts _scope_cache_root to a per-harness table (codex added). Widens
_render_to_cache to return (cache_path, slot_target, bytes) so the
caller can symlink the slot at either the file (file-slot kinds) or
the directory (directory-slot kinds). _prune_translated_slot now
cleans up directory caches. _cell_status recognises the per-scope
cache root as a valid target for translate cells, so the cell now
reports "linked" instead of the misleading "broken" inherited from
the original toolkit-repo-only check.

Tests use a stub (codex, skill) translator registered/torn down via
fixture, so this PR remains independent of PR-C's actual codex
translator. Upgrades PR-A's regression test from `!= "unlinked"` to
`== "linked"`.

Refs #40
```

## Verification

- New unit + integration tests in `tests/test_link_lib.py` and `tests/test_translate_status_reporting.py`.
- Full pytest suite green.
- `flow.log` records preflight CI; `assets/verification/40-b/` holds the preflight log.

## Risks

- **Stub translator fixture leaking into other tests.** Use a `with`-style context manager or `monkeypatch.setitem(TRANSLATORS, ...)` so teardown is guaranteed even on test failure.
- **The dry-run print line change** (showing `slot_target` instead of `cache_path`) might break a snapshot or pinned-text test. Mitigate by checking each pinned test for the expected text. If any need updating, update them in the same commit and call out the diff in the PR body.
- **`_translated_slot_filename` is unchanged** — the directory-slot detection lives in `_render_to_cache` / `maybe_link`. This keeps the helper's contract narrow (it just maps slug+kind+harness → on-disk slot filename).

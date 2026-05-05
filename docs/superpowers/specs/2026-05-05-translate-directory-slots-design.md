# Spec — extend translate machinery for directory-slot kinds (#40-B)

## Problem

The translate mechanism added in commit `e867dbe` (Phase 3, OpenCode) was built for **single-file slots**: agents and commands project as `<slug>.md` files. The cache contains `<slug>.md`, the slot symlink points file→file, and `_prune_translated_slot` removes both.

Skills are **directory assets**: `<slug>/SKILL.md` lives inside a `<slug>/` directory. When a skill is symlinked into a harness today, the slot is a directory symlink: `~/.harness/skills/<slug>` → `<toolkit>/skills/<slug>/`. The harness reads `<slug>/SKILL.md` inside.

To translate codex skills (#40 PR-C), we need a translate path that:
- Renders a translated `SKILL.md` to a cache directory.
- Makes the harness slot directory symlink point at the cache directory.
- Unlinks both directory + cache file on `unlink`.

There is also a follow-on bug from PR-A: `_cell_status` reports translate cells as `"broken"` because the symlink target is outside the toolkit repo. PR-B widens that check to recognise the per-scope cache root as a valid target.

## Scope

This PR extends machinery only — it does NOT add a `(codex, skill)` translator or matrix entry. PR-C does that. PR-B's job is to make the machinery accept directory-slot kinds and per-harness cache layouts so that PR-C is a small drop-in.

## Approach

1. **Generalise `_scope_cache_root`** (`_link_lib.py:59-76`) into a per-harness lookup table:

   ```python
   _CACHE_LAYOUT: dict[str, dict[str, str]] = {
       "opencode": {"user": "{home}/.config/opencode/.agent-toolkit-cache",
                    "project": "{project_root}/.opencode/.agent-toolkit-cache"},
       "codex":    {"user": "{home}/.codex/.agent-toolkit-cache",
                    "project": "{project_root}/.codex/.agent-toolkit-cache"},
   }
   ```

   `_scope_cache_root(harness, scope, project_root)` looks up the table; `ValueError` for unknown harnesses (preserved). The table-of-cache-roots replaces the if/else and removes the codex blocker the scout brief flagged.

2. **Teach `_render_to_cache` about directory-slot kinds**:

   - File-slot kinds (today: agent, command): cache path = `<cache_root>/<kind>/<slug>.md`. Unchanged.
   - Directory-slot kinds (new: skill — and any other directory kind that gets a translator): cache path = `<cache_root>/<kind>/<slug>/<frontmatter-filename>`, where `<frontmatter-filename>` is `SKILL.md` for skills (mirrors the on-disk shape). Returned `cache_path` is the rendered file; the *slot* should point at the directory `<cache_root>/<kind>/<slug>/`.

   Today `_render_to_cache` returns `(cache_path, rendered_bytes)`. PR-B widens the return to `(cache_path, slot_target, rendered_bytes)` where `slot_target` is what the slot symlink should point at — equal to `cache_path` for file-slot kinds, equal to `cache_path.parent` for directory-slot kinds.

3. **Update `maybe_link`** (the only caller) to symlink to `slot_target` instead of `cache_path`. Cache-staleness check still byte-compares `cache_path`.

4. **Update `_prune_translated_slot`** to handle directory caches: if the link target is a directory and lives in the cache, remove the link, remove the cache file, then `rmdir` the now-empty cache directory (and any empty parent up to but not including the cache root). Keep the file-cache path intact.

5. **Widen `_cell_status` `inside_repo` check** (`_list_json.py:62-69`) to also accept the per-scope cache root as a valid target for translate cells. Algorithm:

   - If `(harness, kind)` is in `TRANSLATORS`, check whether `resolved_target` is inside `_scope_cache_root(harness, scope, project_root)`. If yes, treat as `linked`. If no, fall through to existing toolkit-repo check (which will report `broken`).
   - If `(harness, kind)` is NOT in `TRANSLATORS`, behaviour unchanged.

6. **Doctor `symlinks.py` stale-sweep `.md`-stripping** (`doctor/symlinks.py:73`): with cache-targets now considered "expected", the `target.relative_to(toolkit_root)` short-circuit at line 70-72 still fires for translate cells (cache targets aren't in the toolkit). The stale-sweep `.md`-stripping is therefore *still* unreachable for translate cells in PR-B. Defer until/unless we change the relative-to-cache check too. (Following PR-A's discipline: don't add code for paths that aren't reached.)

## Test strategy

Use a **temporary in-test translator registration** for `(codex, skill)`. The test:

1. Adds `(codex, skill)` to the `TRANSLATORS` dict via a fixture (autouse + teardown).
2. Adds `(codex, skill)` to the in-memory `_USER_TARGETS` if needed (skills already have a codex entry: `_support.py:29` `("codex", "skill")` → `~/.codex/skills`). Confirm.
3. Wait — the production `_support.py` table already has `(codex, skill) → ~/.codex/skills`. The test only needs to register a stub translator.
4. Runs `link user codex` against an opencode-only-with-stub-translator-for-codex skill. Wait — the asset's `spec.harnesses` controls projection. The fixture should declare `[codex]`.
5. Asserts cache file at `~/.codex/.agent-toolkit-cache/skill/<slug>/SKILL.md`.
6. Asserts slot directory symlink at `~/.codex/skills/<slug>/` → cache directory.
7. Reads `SKILL.md` through the slot and verifies it contains the rendered output.
8. Runs `unlink user codex --all`, asserts both slot and cache directory are gone.

Then a separate test:

9. With the stub translator still registered, `_build_inventory` for the same setup reports the cell `status == "linked"` (not `"broken"`). This is the inside-repo widening verification.

## Acceptance criteria

1. `_scope_cache_root("codex", "user", _)` returns `~/.codex/.agent-toolkit-cache` (no longer raises).
2. `_scope_cache_root("codex", "project", project_root)` returns `<project_root>/.codex/.agent-toolkit-cache`.
3. `_render_to_cache(harness="codex", kind="skill", …)` writes the rendered text to `<cache_root>/skill/<slug>/SKILL.md` and returns `(cache_path, slot_target, bytes)` with `slot_target == cache_path.parent`.
4. `maybe_link` symlinks `<harness_slot>/<slug>` → `<cache_root>/skill/<slug>/` (a directory→directory symlink).
5. `_prune_translated_slot` removes the slot symlink, the cache `SKILL.md`, and the cache `<slug>/` directory (leaves the cache `skill/` parent intact).
6. `_cell_status` returns `"linked"` for an integration-tested `(codex, skill)` cell whose slot points into the cache.
7. PR-A's regression test `test_list_json_finds_opencode_translated_agent` is **upgraded** to assert `status == "linked"` (it currently asserts `!= "unlinked"`).
8. Existing OpenCode agent/command translate tests still pass byte-for-byte.
9. `uv run pytest -q` passes.

## Out of scope

- Adding a real `(codex, skill)` translator. PR-C.
- Updating `harness-matrix.md` doc cell for codex/skill. PR-C.
- Updating `_TRANSLATE_PATH_RE` regex in `test_harness_matrix.py`. PR-C.
- The doctor stale-sweep `.md`-strip — still unreachable, deferred.

## Risks

- **The `maybe_link` cache-staleness check** today is `slot_correct = link_path.is_symlink() and Path(os.readlink(link_path)) == cache_path`. For directory-slot kinds, the slot points at `cache_path.parent`. The check needs to be `slot_correct = link_path.is_symlink() and Path(os.readlink(link_path)) == slot_target`. Trivial substitution.
- **The cache directory layout** (`<cache_root>/<kind>/<slug>/SKILL.md`) introduces a new directory level. Existing OpenCode agent/command caches at `<cache_root>/agent/<slug>.md` and `<cache_root>/command/<slug>.md` are unchanged.
- **Empty directory cleanup in `_prune_translated_slot`**: `rmdir` only removes empty directories; if any other file ended up in the cache `<slug>/` directory, the rmdir fails silently (catch `OSError`). Acceptable — that's a tampering case.

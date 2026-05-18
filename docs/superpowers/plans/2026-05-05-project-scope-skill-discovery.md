# Plan — project-scope skills work for opencode and pi (#41)

## Tasks (TDD; failing test first for each fix)

### 1. Pi project paths (smallest, lands first within the PR)

**Test (`tests/test_support.py`):**
- `test_pi_project_skill_path_is_under_dot_pi` — assert `slot_dir("pi", "skill", "project", root) == root / ".pi" / "skills"`. Fails on main with `.pi/agent/skills`.
- `test_pi_project_pi_extension_path_is_under_dot_pi` — assert `slot_dir("pi", "pi-extension", "project", root) == root / ".pi" / "extensions"`.

**Code (`_support.py`):**
- Line 47: `".pi/agent/skills"` → `".pi/skills"`.
- Line 49: `".pi/agent/extensions"` → `".pi/extensions"`.

`("pi", "agent")` project entry is left at `.pi/agent/agents` for this PR (see spec § "_support.py — pi project paths" for rationale).

### 2. OpenCode skill translator + new slot shape

**Test (`tests/test_translators.py`):**
- `test_translate_opencode_skill_emits_top_level_name_and_description`
- `test_translate_opencode_skill_preserves_wrapper_under_agent_toolkit_key`
- `test_translate_opencode_skill_appends_body`
- `test_translate_opencode_skill_round_trip_stable`
- `test_translators_dict_has_opencode_skill_entry`

Add `("skill", "opencode")` to the parametrized smoke test (line 133 of test_translators.py per PR-C).

**Code (`_translators.py`):**
- Add `_name(record)` helper.
- Add `_translate_opencode_skill(record, body)` returning bytes.
- Register `("opencode", "skill"): _translate_opencode_skill` in `TRANSLATORS`.

### 3. Third slot shape: dir-with-file-symlink

**Test (`tests/test_translate_directory_slots.py` — extend):**
- `test_render_to_cache_opencode_skill_uses_file_symlink_shape` — assert that `_render_to_cache(harness="opencode", kind="skill", ...)` returns a triple where `slot_target == cache_path` (NOT `cache_path.parent` like codex/skill). The slot will be a real directory; the file inside the slot will symlink to the cache file.
- `test_link_user_opencode_skill_creates_real_slot_dir_and_file_symlink` — end-to-end. Call `link user opencode` for an opencode-only skill. Assert:
  - `~/.config/opencode/skills/<slug>/` is a real directory (not a symlink).
  - `~/.config/opencode/skills/<slug>/SKILL.md` is a file symlink.
  - The symlink target is `~/.config/opencode/.agent-toolkit-cache/skill/<slug>/SKILL.md`.
  - Reading the file through the symlink yields the translated content.
- `test_unlink_user_opencode_skill_removes_file_symlink_and_cache_and_slot_dir` — end-to-end unlink cleanup.
- `test_cell_status_reports_linked_for_opencode_skill_with_file_symlink_slot` — `_build_inventory` reports the cell as `linked`, not `broken`.

**Code (`_link_lib.py`):**

Introduce a helper:

```python
def _translate_slot_layout(harness: str, kind: str) -> str:
    """Return the slot layout shape for a translate cell:
      - 'file'              — slot symlink → cache file (e.g. opencode agent/command)
      - 'dir-symlink'       — slot symlink → cache dir   (e.g. codex skill)
      - 'dir-with-file-symlink' — real slot dir + file symlink → cache file (e.g. opencode skill)
    """
    if harness == "opencode" and kind == "skill":
        return "dir-with-file-symlink"
    if _translated_slot_filename("x", kind, harness).endswith(".md"):
        return "file"
    return "dir-symlink"
```

(Keep `_translated_slot_filename` unchanged; it stays the source of truth for the slot's *name*.)

Update `_render_to_cache` to set `slot_target` according to the layout: `cache_path` for `file` and `dir-with-file-symlink`; `cache_path.parent` for `dir-symlink`. (Currently the rule is "ends with .md → file shape, else dir shape"; switching to the explicit helper.)

Update `maybe_link` to handle the new shape:
- For `dir-with-file-symlink`: ensure `link_path` is a real directory (mkdir if needed); the actual symlink lives at `link_path / asset_path.name`. The cache-staleness check + symlink replacement runs against this inner path.
- The dry-run print shows `link_path / asset_path.name → slot_target` (so the user sees the SKILL.md path).

Update `_prune_translated_slot` to handle the new shape:
- If the link_path is a real directory containing a file symlink to the cache, follow the symlink to find the cache file, remove the file symlink, remove the cache file, rmdir the cache `<slug>/`, rmdir the slot `<slug>/` if empty.

Update `_cell_status` (`_list_json.py`):
- For translate cells, if layout is `dir-with-file-symlink`, look at `link_path / <frontmatter_filename>.is_symlink()` instead of `link_path.is_symlink()`. The frontmatter filename can be derived from the asset path's name (the existing `_expected_source` logic for skills returns `asset_path.parent` — we need `asset_path.name` instead, which is the SKILL.md filename).

### 4. Matrix doc

**File:** `docs/agent-toolkit/harness-matrix.md`
- Update the `(opencode, skill)` cell from `symlink → ~/.config/opencode/skills/<slug>/` to `translate → ~/.config/opencode/skills/<slug>/SKILL.md (cache: ~/.config/opencode/.agent-toolkit-cache/skill/<slug>/SKILL.md) — emits opencode-shaped frontmatter with top-level name and description plus agent_toolkit_cli wrapper`.
- Update the project-scope path table further down to reflect pi changes.

The `_TRANSLATE_PATH_RE` regex (PR-C widened) already covers `skills/<slug>/SKILL.md`, so the parity test passes without regex change.

### 5. Run full suite + commit

`uv run pytest -q` — expect green. Single commit:

```
fix(#41): make project-scope skills work for opencode and pi

Two empirically-confirmed root causes:

1. Pi project paths used the user-scope `.pi/agent/...` convention
   when pi actually reads project-scope from `.pi/...` (no /agent/).
   Pi has no project-scope agents directory at all.

2. OpenCode silently drops SKILL.md files lacking top-level `name:`
   and `description:`, and its directory glob does not follow
   directory symlinks. Same root cause as #40 (codex), plus a
   discovery-walk constraint that makes PR-B's dir-symlink-to-cache
   slot shape unsuitable for opencode.

Changes:
- _support.py: pi project paths fixed (.pi/skills, .pi/extensions);
  ("pi", "agent") project entry removed (unsupported pair).
- _translators.py: new (opencode, skill) translator with top-level
  name + description.
- _link_lib.py: third slot shape for translate cells —
  "dir-with-file-symlink" — real slot directory containing a file
  symlink to the cache file. Used for (opencode, skill); codex skill
  keeps the dir-symlink shape.
- harness-matrix.md: opencode/skill cell updated to translate;
  project-scope table updated for pi.

Empirically verified against opencode 1.14.30 and pi 0.70.6.

Closes #41
```

## Risks

- **Test fixtures:** The new tests use `monkeypatch.setenv("HOME", ...)` and `seed_skill` — both already proven in the existing test suite.
- **Codex skill regression:** PR-B's `(codex, skill)` integration tests use the dir-symlink shape; they should still pass because the new `_translate_slot_layout` helper still returns `"dir-symlink"` for `(codex, skill)`. Run them explicitly.
- **`_cell_status` changes for translate cells with dir-with-file-symlink shape:** the existing inside-cache check in PR-B (resolve target, check `.relative_to(cache_root)`) still works — the symlink target IS in the cache; the only difference is which path level is the symlink. The check needs to look at the right level (the file inside the slot), not the slot itself.
- **Existing direct-symlink behaviour for opencode skills (`_PROJECT_TARGETS[("opencode","skill")]` was `.opencode/skills` and the link command currently makes a directory symlink there):** with the translator now in place, the same path becomes a real directory containing a file symlink. Any user with the old directory symlink in place needs to re-run `link` — the `maybe_link` "stale" check should detect the dir-symlink and replace it, but worth verifying.

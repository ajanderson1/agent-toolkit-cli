# Plan — fix bare-slug lookup for translate cells (#40-A)

## Tasks

### 1. Regression test (TDD — fails before the fix)

File: `tests/test_translate_status_reporting.py` (new).

Two tests:

**`test_list_json_finds_opencode_translated_agent`**
- Use `env` + `seed_agent` fixtures from `tests/conftest.py`.
- Seed an OpenCode-only agent `foo`.
- Allowlist it.
- Run `link user opencode`.
- Confirm slot exists at `~/.config/opencode/agents/foo.md`.
- Build the inventory via `commands._list_json._build_inventory`.
- Find the cell for `(harness=opencode, kind=agent, slug=foo, scope=user)`.
- Assert `cell["status"] != "unlinked"`. (Spec §"Out of scope" — broken-vs-linked is PR-B.)
- **This fails on main with `status == "unlinked"` because of the bare-slug bug.**

**`test_doctor_symlinks_finds_opencode_translated_agent`**
- Same setup as above.
- Run `doctor.symlinks.run(toolkit_root, harness="opencode")`.
- Assert no warning string contains `"expected symlink"` for `agent/foo`.
- Assert `findings` contains a string matching `"agent/foo: linked"`.
- **This fails on main because of the bare-slug bug.**

Run the suite — both new tests fail. Confirms the bug is real and the test exercises it.

### 2. Fix `_cell_status` in `_list_json.py`

Import `_translated_slot_filename` from `commands._link_lib`. Change line 47 from:

```python
link_path = slot / slug
```

to:

```python
link_path = slot / _translated_slot_filename(slug, kind, harness)
```

### 3. Fix `doctor/symlinks.py`

One substitution:

- Line 34 (`link_path = home / rel / asset.slug`) → use `_translated_slot_filename(asset.slug, asset.kind, harness)`.

The stale-sweep loop at lines 63-87 also iterates real filenames (so for opencode agents it sees `foo.md`), but is unreachable for translated cells today: line 70-72's `target.relative_to(toolkit_root)` check short-circuits because translated cells point into the cache dir, not the toolkit. PR-B will change the cache-vs-repo shape and need to add a `.md` strip there; PR-A leaves it alone.

### 4. Run regression tests + full suite

- `uv run pytest -q tests/test_translate_status_reporting.py` → 2 passed.
- `uv run pytest -q` → all green (current baseline = 344 on main, expecting 346 after — 2 new tests).

### 5. Commit

Single conventional commit:

```
fix(#40): use translated slot filename when probing link status

_list_json._cell_status and doctor/symlinks both built the slot
lookup path with a bare slug, missing OpenCode agent/command
translate cells whose actual filename is <slug>.md. Both now use
_link_lib._translated_slot_filename so the lookup matches reality.

This is the first of three PRs addressing #40 (codex skill loader
rejects v1alpha2 frontmatter). Ships independent value today —
OpenCode agent/command translate cells now report correct
link-vs-unlinked status in `list --format json` and `doctor
symlinks --harness opencode`. The remaining inside-repo check in
_cell_status (which still reports translate cells as "broken"
because the cache target is outside the toolkit repo) is the
subject of #40 PR-B.

Refs #40
```

Note: this commit does NOT use `Closes #40` — that comes with PR-C.

## Verification

- Test suite is the artifact (full pytest passes).
- No `.claude/testing.md`, no `verify.sh` — Step 9 falls back to "skip".
- `flow.log` records preflight CI; `assets/verification/40-a/` holds the preflight log.

## Risks

- **The `_translated_slot_filename` helper today returns `<slug>` for any non-(opencode, agent|command) pair**, so importing and using it for skill/hook/plugin/pi-extension cells is a no-op. No regression risk for those kinds.
- **The doctor stale-sweep change** (`entry.name` `.md`-stripping) needs to be careful not to strip the `.md` for harnesses where it isn't translated. Conditioning on `_translated_slot_filename("x", kind, harness) == "x.md"` keeps the conditional explicit and rooted in the same SSOT.
- **No CLI-output changes** — the lefthook pre-commit suite runs the same tests CI does, so any regression is caught at commit time.

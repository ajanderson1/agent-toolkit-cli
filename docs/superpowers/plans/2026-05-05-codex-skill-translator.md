# Plan — codex skill translator (#40-C)

## Tasks

### 1. Add the translator (`src/agent_toolkit_cli/_translators.py`)

```python
def _translate_codex_skill(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)
```

Register in `TRANSLATORS`:

```python
TRANSLATORS: ... = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
    ("codex", "skill"): _translate_codex_skill,
}
```

### 2. Update the matrix doc (`docs/agent-toolkit/harness-matrix.md`)

Find the codex/skill cell. Today it reads (per scout): `symlink → ~/.codex/skills/<slug>/`.

Change to: `translate → ~/.codex/skills/<slug>/SKILL.md`.

Note: the slot itself is a directory symlink to a cache directory; the `→` arrow in the matrix doc points at the file the harness reads. Match the existing translate-cell convention used for opencode agents/commands.

### 3. Update `_TRANSLATE_PATH_RE` (`tests/test_harness_matrix.py:307-309`)

Today: `r"(agents|commands)/<slug>\.md\s*$"` (or similar). Widen to also match `skills/<slug>/SKILL.md`. The path-shape parity test (`TestTranslateParity::test_translate_cell_path_matches_slot_convention`) reads this regex.

### 4. Add unit tests for the translator (`tests/test_translators.py`)

Mirror the OpenCode command tests:

- `test_translate_codex_skill_emits_top_level_description`
- `test_translate_codex_skill_preserves_wrapper_under_agent_toolkit_key`
- `test_translate_codex_skill_appends_body`
- `test_translate_codex_skill_round_trip_stable`
- `test_translators_dict_has_codex_skill_entry`

### 5. Refactor PR-B's stub-translator integration tests

`tests/test_translate_directory_slots.py` registered a stub `(codex, skill)` translator via `monkeypatch.setitem`. With the real translator now in place, the fixture is unnecessary for the integration tests — they can use the production translator. Remove the `codex_skill_translator` fixture and its usages, except where the test explicitly needs to verify behaviour against a deterministic stub (e.g. the `_render_to_cache` cache-shape tests can keep the stub for asserting bytes; the link/unlink/`_cell_status` tests should use the real translator).

Decision: keep the fixture for the unit-level `_render_to_cache` tests (they assert specific bytes and the real translator's bytes are equally deterministic — but using the stub keeps the test closer to a unit boundary). For the end-to-end link/unlink/cell-status tests, switch to the real translator. This makes the integration tests *also* exercise the real translator, which is what we want.

Concrete: in the three integration tests, drop the `codex_skill_translator` fixture parameter. Drop its registration in those test bodies. The stub fixture stays for the three `_render_to_cache`-level tests, but its definition is moved to a smaller scope (or kept unused; either is fine).

Cleanest: just remove the fixture from the integration tests (they no longer need it because TRANSLATORS now contains a real entry). Keep the fixture and the `_render_to_cache` tests. No other change needed — pytest's `monkeypatch.setitem` overrides the real entry for the fixture's lifetime, then restores it.

### 6. Verify the parity tests pass (PR-C-internal contract)

After the matrix doc and TRANSLATORS update:
- `test_every_translate_cell_has_translator_entry` → green (matrix says translate, `TRANSLATORS` has codex/skill).
- `test_every_translator_entry_has_translate_cell` → green (translator entry has matching matrix doc).
- `test_translate_cell_path_matches_slot_convention` → green (regex widened in step 3).
- `TestSymlinkParity::test_every_user_target_has_symlink_cell` → still green (it accepts both `symlink` and `translate`; `(codex, skill)` is still in `_USER_TARGETS`).

### 7. Run full suite

`uv run pytest -q` — expect green.

### 8. Commit

```
feat(#40): codex skill translator — top-level description for native loader

Codex's skill loader requires `description:` at the YAML top level of
every SKILL.md and rejects the toolkit's v1alpha2 wrapper at session
start with `failed to load skill ... missing field 'description'`.

Adds the (codex, skill) translator (description + agent_toolkit_cli
wrapper, mirroring _translate_opencode_command). Updates the matrix
doc to mark codex/skill as translate. Widens _TRANSLATE_PATH_RE to
match skills/<slug>/SKILL.md.

Empirically verified against codex 0.128.0 — see
assets/verification/40-c/codex-frontmatter-empirical.md. All three
codex skill ACs from issue #40 met:
  - no-error codex exec startup
  - skill discoverable by codex's description-match path

Closes #40
```

This is the commit that **`Closes #40`**.

## Verification

- Empirical verification (already done) is recorded in `assets/verification/40-c/codex-frontmatter-empirical.md`.
- New unit tests in `tests/test_translators.py`.
- PR-B's integration tests now exercise the real translator end-to-end.
- Full pytest suite green.

## Risks

- **The matrix doc edit must match the existing translate-cell formatting** for opencode agents/commands. If they have a specific "translate → <path>" syntax (vs. just text), copy it.
- **`_TRANSLATE_PATH_RE` regex** — be careful not to over-widen (e.g. matching `skills/foo` without `/SKILL.md`). Test with the existing opencode entries.
- **Stub fixture cleanup** — pytest `monkeypatch.setitem` restores the real value at teardown. If we leave both the real and stub registrations, the stub overrides the real one within the fixture's scope, which is what the stub-using tests want. No conflict.

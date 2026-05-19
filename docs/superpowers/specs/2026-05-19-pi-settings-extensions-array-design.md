# Spec — Pi: surface settings.json `extensions[]` enable/disable overrides

**Issue:** [#109](https://github.com/ajanderson1/agent-toolkit-cli/issues/109)
**Author:** agent (flow `--auto`, re-scoped after reading Pi source)
**Date:** 2026-05-19
**Status:** Draft for approval

> **Premise correction.** Issue #109 was filed under the assumption that `extensions[]` in `~/.pi/agent/settings.json` is a list of local-path extension references. Reading `@earendil-works/pi-coding-agent` `dist/core/package-manager.js` shows it is in fact an **enable/disable override list** applied to already-auto-discovered extension paths. This spec drops the original "local path" framing and adds the override surface to the inventory the right way.

## 1. Problem

The unified Pi inventory (#103/#106) treats every auto-discovered extension as `user_loaded=true` whenever the directory exists. Pi itself does not: `settings.json` `extensions: []` is a filter that can **disable** an auto-discovered extension (or, with `+`/`-` prefixes, force its state). The toolkit's inventory therefore mis-reports what Pi will actually load.

Concretely (`package-manager.js:1781-1854`):

- `globalSettings.extensions ?? []` and `projectSettings.extensions ?? []` are read into `userOverrides.extensions` / `projectOverrides.extensions`.
- For each auto-discovered path, `isEnabledByOverrides(path, overrides, baseDir)` (`:502`) is consulted to decide `enabled: true | false` on the resource record.
- Pattern grammar (`getOverridePatterns`, `:499`; `applyPatterns`, `:527`):
  - plain entry — include-filter (only matching paths are enabled when any include is present)
  - `!entry` — exclude
  - `+entry` — force-include (overrides excludes)
  - `-entry` — force-exclude (overrides force-includes)

If no overrides are present, all auto-discovered extensions are enabled by default.

## 2. Goal

Make `agent-toolkit-cli pi inventory` report what Pi will actually load by computing `enabled` per scope using Pi's own override semantics. The TUI Pi tab visibly dims disabled rows. The doctor flags overrides that don't match any auto-discovered path (orphans).

## 3. Acceptance criteria

1. With no `extensions` field (or an empty array) in `~/.pi/agent/settings.json`, every first-party record has `user_enabled=true`. Behaviour matches today.
2. With `settings.json` `{"extensions": ["!status-bar"]}`, the `status-bar` first-party record has `user_loaded=true`, `user_enabled=false`. Inventory JSON exposes both fields.
3. With `{"extensions": ["+foo"]}` and `foo` not auto-discovered, the override is reported as a **doctor advisory** ("orphaned override"). No phantom `PiRecord` is invented.
4. With `{"extensions": ["status-bar"]}` (plain include) and two extensions auto-discovered (`status-bar`, `other`), `status-bar` is enabled and `other` is **disabled** (Pi's include-filter semantics). This is non-obvious; doctor surfaces it once the first include lands.
5. TUI Pi tab renders disabled rows with a `disabled` style. The toggle keys still work; toggling re-runs inventory; no toolkit edits to `extensions[]` (out of scope).
6. Third-party records are unaffected — `extensions[]` does not apply to packages.

## 4. Design

### 4.1 PiRecord delta

Two new fields, both `bool`:

```python
user_enabled: bool      # default True; False iff override list disables this slug
project_enabled: bool   # default True; symmetric
```

`enabled` is only ever evaluated when the matching `*_loaded` is `True` (you can't disable what isn't there). For unloaded rows, the field is `True` by convention (it represents "would be enabled if loaded"), and the TUI renders the row by `*_loaded && *_enabled`.

### 4.2 Override evaluator

New module `_pi_overrides.py`:

```python
def is_enabled(*, slug: str, base_dir: Path, ext_dir: Path, overrides: list[str]) -> bool:
    """Mirror Pi's isEnabledByOverrides for one extension slug.

    `slug` is the auto-discovery directory name. The path Pi feeds into its
    matcher is `<ext_dir>/<slug>`. `base_dir` is `globalBaseDir` (the Pi base,
    e.g. `~/.pi/agent`). Override patterns:

      plain entry → include-filter (must match to enable when any plain present)
      !entry      → exclude
      +entry      → force-include
      -entry      → force-exclude
    """
```

Tests cover each branch verbatim against fixtures derived from `package-manager.js` behaviour. The Pi source is the authority — our test cases are direct transcriptions of its rules, not our own re-interpretation.

**Matching rule.** Pi uses `matchesAnyPattern` (regex/glob) for plain/`!`, `matchesAnyExactPattern` for `+`/`-`. For v1 we implement the **exact-name** case (slug equality) plus simple `*` globbing. Anything more elaborate (relative paths, nested globs) is recorded as a doctor advisory rather than silently mis-matched. We can widen later if real configs need it.

### 4.3 Settings reader

`_pi_settings.py` gains:

```python
def read_extensions_overrides(path: Path) -> list[str]:
    """Return `extensions[]` from settings.json (override-pattern list)."""
```

Schema-tolerant in the same way `read_packages` is: missing file → `[]`, missing key → `[]`, non-list → `[]`, raises on malformed JSON.

### 4.4 Inventory wiring

`build_pi_inventory` gains two new keyword arguments:

```python
user_extensions_overrides: list[str],
project_extensions_overrides: list[str],
```

For each first-party record, compute `user_enabled` and `project_enabled` by calling `is_enabled(...)` per scope. Third-party records always get `enabled=True` (the override list does not target packages).

The CLI inventory subcommand reads the new field via `read_extensions_overrides(paths.user_settings_json)` / `read_extensions_overrides(paths.project_settings_json)` and threads them into `build_pi_inventory`.

### 4.5 TUI Pi tab

Render `*_loaded && *_enabled` glyph in the U / P columns; a fourth display state (loaded-but-disabled) gets a distinct mark — `~` — so the operator can tell "Pi found it but won't run it." Tab footer surfaces the legend.

### 4.6 Doctor advisory

One new check: **Orphaned override.** For each entry in `extensions[]` (any scope):

- Strip the prefix (`!`, `+`, `-`) if present.
- If the remaining pattern is a plain slug (no glob), check whether an auto-discovered extension with that name exists in the corresponding `ext_dir`.
- If not, emit `orphaned-pi-extensions-override` with the entry verbatim, the scope, and the suggested fix (remove the entry).

Globs are exempt from this check — too easy to false-positive.

### 4.7 What is **not** in scope

- Editing `extensions[]` from the toolkit. `pi disable/enable <slug>` is a sensible future verb but does not land here. Out of scope by design — let one round of real use show the shape first.
- Sibling override fields (`skills`, `prompts`, `themes`). Same mechanism; ride later behind `_pi_overrides`.
- Re-implementing Pi's full glob matcher. Exact-name + `*` only.

## 5. Non-goals

- Building a generic Pi config editor. The toolkit reads `extensions[]`; it does not write it (yet).
- Folding `extensions[]` entries into `pi_packages` as `local:` sources — the original misread. Dropped.

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Pi widens override grammar in a future release | Tests pinned to `@earendil-works/pi-coding-agent@0.75.3`; advisory if the toolkit sees a pattern shape it can't match. |
| Operator already has `extensions: ["foo"]` (plain include) and is now surprised that `bar` is disabled | Doctor surfaces it the first time inventory runs against such a config: "include-filter active — these extensions are now disabled: …". One-time educational nudge. |
| `is_enabled` diverges from Pi | Fixtures in `tests/_pi_overrides_fixtures.py` are direct transcriptions of the pattern grammar; CI runs a sanity check that compares our matcher's output against a hand-rolled cross-check on a small corpus. |
| Empty/missing settings.json | Already handled by `_pi_settings.read_packages`; new reader follows the same defaults. |

## 7. Internal commit slicing

Single PR, three logical commits:

1. **Override evaluator + reader** — `_pi_overrides.py` with `is_enabled`; `_pi_settings.read_extensions_overrides`. Pure functions + fixtures.
2. **Inventory wiring** — extend `build_pi_inventory` signature, thread new args, populate `user_enabled` / `project_enabled` on first-party records. CLI `pi inventory` reads overrides and passes them in.
3. **TUI + doctor** — TUI renders the third display state; doctor's orphaned-override advisory.

## 8. References

- Issue: [#109](https://github.com/ajanderson1/agent-toolkit-cli/issues/109)
- Prior spec (PR 1/2/3): `docs/superpowers/specs/2026-05-19-pi-unified-extension-inventory-design.md`
- Pi source: `@earendil-works/pi-coding-agent@0.75.3` `dist/core/package-manager.js:499-517` (override grammar), `:1781-1854` (where applied)
- Toolkit inventory: `src/agent_toolkit_cli/_pi_inventory.py`
- Toolkit settings reader: `src/agent_toolkit_cli/_pi_settings.py`

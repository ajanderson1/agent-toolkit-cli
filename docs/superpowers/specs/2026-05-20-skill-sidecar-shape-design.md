# Skill sidecar shape — harness-facing frontmatter, toolkit-facing sidecar — design

**Issue:** [#150](https://github.com/ajanderson1/agent-toolkit-cli/issues/150)
**Date:** 2026-05-20
**Status:** refined for plan handoff (`/aj-workflow flow 150 --auto`)
**Repo scope:** Engineering work lands in `agent-toolkit-cli` (this PR, closes #150). Content migration (rewriting existing inline-frontmatter skills into the new shape) lands in `~/GitHub/agent-toolkit/` as a **separate, follow-up PR** delivered via the operator prompt at the end of this spec. Sequencing: CLI PR lands first; migration PR runs `migrate-skills` from the merged CLI release.

## Goal

Adopt a single canonical shape for `skill` assets in which:

- **`SKILL.md` frontmatter** carries the *harness-facing* metadata that every harness loader requires the same way: top-level `name` and `description` (the long, trigger-rich one used by harness loaders to decide when to activate the skill).
- **`<slug>.toolkit.yaml` sidecar** carries the *toolkit-facing* metadata: the full v1alpha2 wrapper (`apiVersion`, `metadata.lifecycle`, `spec.harnesses`, `spec.origin`, etc.), a separate concise CLI/TUI description shown in listings, and any per-harness optional fields.

This kills the current failure mode where pi (and silently, Claude/OpenCode) rejects skills because v1alpha2's nested `metadata.description` is invisible to every harness loader. It also clarifies a long-standing ambiguity in `metadata.description`: under the new shape that field is unambiguously the CLI-facing label, not a harness loader hint.

Builds directly on `2026-05-19-sidecar-metadata-discovery-design.md`, which introduced sidecars as the preferred (but not required) form for skill and mcp.

## Non-goals

- **No schema version bump.** `v1alpha2` is retained. The semantics of `metadata.description` are refined (it is now the CLI-facing label), but the shape is byte-identical. The toolkit is pre-1.0 with no external consumers; an apiVersion bump would be noise.
- **No changes to non-skill kinds.** Agent, command, hook, plugin, mcp, pi-extension are untouched. (mcp already uses sidecar shape and has no harness loader equivalent.)
- **No support for a third "inline-only-with-top-level-keys" shape.** Authors either use sidecar (new world) or have legacy inline v1alpha2 frontmatter (tolerated by the link path during one release cycle, then removed).

## Motivation

Three problems converge:

1. **Pi rejects toolkit skills.** `pi demands` reports `~/GitHub/explore/agent-toolkit-test-area/.pi/skills/android-termux/SKILL.md: description is required` (plus two others). Pi reads top-level `description`; the toolkit's v1alpha2 wrapper nests it under `metadata.description`.
2. **Claude has the same problem, but silently.** Claude's skill loader also reads top-level `name`/`description`. Toolkit-shape SKILL.md files are symlinked into `.claude/skills/<slug>/` and presumably load with no description visible to the model — undetected because Claude doesn't loudly error on missing metadata. Codex and OpenCode hit the same wall but already have emit-time translators (`_translate_codex_skill`, `_translate_opencode_skill`) papering over it.
3. **`metadata.description` has been doing double duty.** It's referenced both as "the description the harness uses to decide whether to load the skill" *and* as "the short label `agent-toolkit list` shows." These two descriptions want to be different lengths and tones. Treating them as one field forces a compromise that's bad for both.

The fix is structural rather than per-harness: stop pretending `metadata.description` is harness-facing. Put harness-facing metadata where harnesses look for it (SKILL.md top-level frontmatter), and keep toolkit metadata in the sidecar where it belongs.

## Design

### The two-file shape

For every new skill:

```
skills/<slug>/
    SKILL.md              ← harness-facing frontmatter + body
    references/ scripts/ … (skill content)
skills/<slug>.toolkit.yaml   ← toolkit-facing metadata
```

#### `SKILL.md` frontmatter

```yaml
---
name: <slug>
description: <long, trigger-rich, harness loader-facing description. Ends with a period.>
---
```

Only these two keys, both required. They are the union of what every harness loader reads identically. (Pi, Claude, Codex, OpenCode, and Gemini all consume `name` and `description` from top-level frontmatter the same way; nothing else has cross-harness agreement.) Anything optional or harness-specific lives in the sidecar.

Authors MAY add extra keys at top-level only if a real second harness consumes the same key the same way. If only one harness consumes it, it belongs in the sidecar (see "Per-harness optional fields" below).

#### `<slug>.toolkit.yaml` sidecar

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: <slug>
  description: <concise CLI/TUI label. ~one sentence. Distinct from SKILL.md's description.>
  lifecycle: experimental | stable | deprecated
  # keywords:, license:, notes: as today
spec:
  origin: first-party | third-party
  vendored_via: none | submodule | clone | symlink
  harnesses: [claude, codex, opencode, gemini, pi]
  # upstream:, fork:, requires:, …
  per_harness:                          # OPTIONAL, see below
    claude:
      # claude-specific optional fields, e.g. argument-hint
    pi:
      # pi-specific optional fields
```

`metadata.description` in the sidecar is the **CLI/TUI display label** — the one shown in `agent-toolkit list`, the TUI inventory, doctor output. The SKILL.md `description` is what the *harness model* reads to decide whether to invoke the skill. Different audiences, different content, different fields.

#### Per-harness optional fields

A new optional `spec.per_harness` block on the sidecar holds keys that are loader-specific. The exact key names per harness are not enumerated in this spec — they will be added incrementally as concrete needs arise. The schema declares this block `additionalProperties: true` for now; tightening happens later.

Initial known case: Pi accepts an `argument-hint` field in skill frontmatter (currently shoved into `metadata.notes` as a YAML-embedded string). With this design it moves to `spec.per_harness.pi.argument_hint`, and the pi translator (see "Emit-time translation" below) lifts it into the emitted SKILL.md frontmatter.

### Validation rules

The `check` command enforces:

1. **Sidecar mandatory for new skills.** A skill with toolkit-shape inline frontmatter (i.e., `apiVersion: agent-toolkit/...` inside `SKILL.md`) is **rejected** during the post-tolerance phase. During the one-release tolerance window (see "Legacy tolerance window" below), it is downgraded to an advisory.
2. **SKILL.md top-level frontmatter required.** If `SKILL.md` parses with empty or missing frontmatter, `check` fails with a clear pointer to this spec. Same rule for missing top-level `name` or `description` keys.
3. **Both descriptions present.** For every skill: `SKILL.md`'s top-level `description` AND `<slug>.toolkit.yaml`'s `metadata.description` must both be non-empty. No length rule, no "must differ" rule — just both present.
4. **Both descriptions end with a period.** The existing JSON Schema `"pattern": "\\.$"` on sidecar `metadata.description` is unchanged. The equivalent rule on SKILL.md top-level `description` is enforced in `check.py` directly (not in the schema, because the schema is applied to the sidecar's v1alpha2 frontmatter and SKILL.md's frontmatter has no `apiVersion`).
5. **`name` agreement.** SKILL.md's top-level `name` must equal `metadata.name` in the sidecar (which equals the slug). One source of truth, replicated only because the harness requires it inline.

### Emit-time translation: per-harness audit

With the new shape, SKILL.md already carries top-level `name`/`description`. So for any harness whose loader needs only those two keys, **no translation is required**: the link command can symlink the source SKILL.md directly into the harness slot directory. Translation is needed only where the harness wants additional fields (e.g., pi's `argument-hint`) or wants the toolkit's traceability wrapper preserved.

Per-harness conclusions:

| Harness | Loader requirements | Translation needed? | Rationale |
|---|---|---|---|
| **claude** | top-level `name`, `description` | **No** — symlink raw `SKILL.md` | Claude reads only the two keys; the sidecar is invisible to it, which is correct. |
| **codex** | top-level `description`, tolerates extras | **Yes** — keep `_translate_codex_skill` | Continues to inject `agent_toolkit_cli` wrapper for traceability + round-trip. Source: sidecar v1alpha2, not `metadata.description`. |
| **opencode** | top-level `name`, `description`, tolerates extras | **Yes** — keep `_translate_opencode_skill` | Same reasoning as codex. |
| **gemini** | tolerates anything | **No** — symlink raw `SKILL.md` | The gemini adapter comment already states "loader ignores unknown keys." Empirically re-verify (see "Open verifications" below). |
| **pi** | top-level `description` (per pi error message); `argument-hint` optional | **Yes** — new `_translate_pi_skill` | Emits top-level `name`/`description` (already present in SKILL.md, but the translator keeps the emit path uniform with codex/opencode); lifts `spec.per_harness.pi.argument_hint` to top level if present. |

The principle going forward: **translate iff a harness needs something beyond the SKILL.md's literal frontmatter** (a per-harness optional field, or a traceability wrapper we want preserved). Otherwise symlink the raw source.

Slot layout: `_translate_slot_layout` already returns `"dir-with-file-symlink"` for `(opencode, skill)`. Extend it to return the same for `(codex, skill)`, `(pi, skill)`. Claude and gemini stay on raw symlinks; their slot layout is unchanged.

### Translator implementation sketch

`_translate_pi_skill(record, body)` — new:

```python
def _translate_pi_skill(record: AssetRecord, body: str) -> bytes:
    """Pi skills require top-level `description` and accept `argument-hint`."""
    md = record.metadata  # sidecar v1alpha2 metadata
    pi_extras = (record.spec.get("per_harness") or {}).get("pi") or {}
    fm = {
        "name": record.slug,
        "description": record.harness_description,  # NEW field — see below
        "agent_toolkit_cli": _wrapper_block(record),
    }
    if "argument_hint" in pi_extras:
        fm["argument-hint"] = pi_extras["argument_hint"]
    return _render(fm, body)
```

This requires the walker / AssetRecord to expose **both descriptions** distinctly:

- `record.harness_description` — read from the SKILL.md's top-level `description`.
- `record.cli_description` — read from `<slug>.toolkit.yaml`'s `metadata.description`.

`_translate_codex_skill` and `_translate_opencode_skill` change their input source from `record.metadata["description"]` to `record.harness_description`. Behavior preserved.

### Scaffolder

`agent-toolkit new skill <slug>` (which already defaults to sidecar) is updated:

1. Sidecar template gets `metadata.description` populated with `"TODO concise one-line CLI label."`
2. Body template (`_BODY_TEMPLATE_NO_FRONTMATTER`) is replaced with one that includes the harness-facing frontmatter:
   ```markdown
   ---
   name: {slug}
   description: TODO write the harness-loader-facing description. Ends with a period.
   ---

   # {slug}

   TODO body.
   ```

The `--inline` flag is **removed** for `kind=skill` (still valid for `kind=mcp`). Attempting `agent-toolkit new skill <slug> --inline` exits 2 with a clear message pointing to this spec.

### Legacy tolerance window

Existing inline-frontmatter skills in `~/GitHub/agent-toolkit/skills/` will be migrated as part of this change (see "Content repo migration" below). After the migration PR lands, there should be **zero** inline-frontmatter skills in the toolkit content repo.

For one release cycle (i.e., until the next minor version after this change ships), the codebase retains:

- The legacy translator branch in `_translate_codex_skill` / `_translate_opencode_skill` that reads `metadata.description` from inline v1alpha2 frontmatter if SKILL.md has no top-level `description` (belt-and-braces for any third-party content the user has linked).
- A `check` advisory (warning, not error) on any inline-shape skill encountered: `"skill <slug> uses legacy inline frontmatter — migrate to sidecar shape (see docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md)"`.

In the release after this one, both the legacy translator branch and the advisory are removed, and `check` hard-fails on inline-shape skills.

### Content repo migration

A migration subcommand (delivered as part of this change, in `agent-toolkit-cli`) rewrites every inline-frontmatter skill in `~/GitHub/agent-toolkit/skills/` into the new sidecar shape. It is a first-class top-level subcommand discoverable via `agent-toolkit --help`:

```
agent-toolkit migrate-skills --content-repo ~/GitHub/agent-toolkit [--dry-run]
```

For each skill currently in inline shape:

1. Read the SKILL.md, parse its v1alpha2 frontmatter.
2. Write `<slug>.toolkit.yaml` next to the skill directory containing the v1alpha2 wrapper. `metadata.description` becomes the **concise CLI-facing** version — initially the original description verbatim; the author is expected to shorten it manually in a follow-up commit. (The migration script flags it with a YAML comment: `# TODO shorten — currently the same as SKILL.md description`.)
3. Rewrite SKILL.md frontmatter to contain only top-level `name` and `description`, where `description` is the original `metadata.description` verbatim.
4. Lift any pi-specific `argument-hint` currently stuffed inside `metadata.notes` (heuristic: scan `notes` for a leading `argument-hint:` line) into `spec.per_harness.pi.argument_hint`. Notes left otherwise.
5. Print a one-line summary per skill: `"migrated skills/<slug>/ (added sidecar, rewrote SKILL.md frontmatter)"`.

`--dry-run` shows the planned edits without writing.

**YAML round-trip and comment preservation.** Step 2 emits a `# TODO shorten` comment in the YAML. PyYAML (the standard library serializer) drops comments on load/dump. The migration command MUST use `ruamel.yaml` (already an optional dep, becomes mandatory for the migration codepath) or write the YAML via templated string assembly. Pick the simpler approach: **templated string assembly** — the wrapper schema is small and fixed; emit the YAML as a deterministic f-string-style template with the `# TODO shorten` line in a known position. No round-trip library required.

**Idempotency.** Re-running on an already-migrated skill is a no-op (detected by: sidecar file present AND SKILL.md frontmatter has no `apiVersion`).

**Symlink safety.** Existing harness symlinks like `~/.claude/skills/<slug>/SKILL.md` point at the *path* of the source SKILL.md, which is being rewritten in-place. File identity (inode) is preserved by an in-place edit, so symlinks continue to resolve. If the migration is reimplemented as a delete-and-recreate (different inode) it MUST be followed by `agent-toolkit link --re` to refresh stale symlinks. Default implementation uses in-place rewrite to avoid this.

The migration script lives in `agent-toolkit-cli` and is invoked from the content repo. **The actual rewrite of skill files happens in a separate PR against `~/GitHub/agent-toolkit/`**, delivered to the operator via the copy-paste prompt at the end of this spec. The CLI repo and content repo PRs are reviewed independently.

### Doctor advisory

Add a new advisory group `skill-shape` in `doctor/`:

- **fail**: skill found with toolkit-shape inline frontmatter AND no sidecar (after migration, this should never happen in the content repo; if it does, something has gone wrong).
- **warn**: skill found with both a sidecar AND non-toolkit-shape inline frontmatter where the inline `name`/`description` disagrees with the sidecar's `metadata.name` / SKILL.md's expected harness description (drift detector).

## Components changed

All Python paths are under `src/agent_toolkit_cli/` (the package name carries the `_cli` suffix; the binary is `agent-toolkit`).

1. **`_schemas/asset-frontmatter.v1alpha2.json`** — add `spec.per_harness` (object, `additionalProperties: true` for now). No other shape change. No corresponding `schema.py` file to edit — validation is driven directly off the JSON schema.
2. **`walker.py`** — extend `AssetRecord` with two new fields: `harness_description: str | None` (from SKILL.md top-level frontmatter) and `cli_description: str | None` (from sidecar `metadata.description`). The existing `metadata: dict` field is **not renamed** — there is no `AssetRecord.description` attribute today; consumers read `record.metadata["description"]`. Adjust `load_asset_record` for skills to read both files when the sidecar shape is present; leave inline-only legacy path returning `harness_description = metadata.get("description")` and `cli_description = None` during the tolerance window.
3. **`inventory.py` / `ingest/types.py`** — the existing `description` attribute on `InventoryEntry` and `IngestProposal` continues to mean the CLI-facing label, sourced from `cli_description` when present and falling back to legacy `metadata["description"]` during the tolerance window. No rename; behaviour preserved by the fallback.
4. **`_translators.py`** — add `_translate_pi_skill`; update `_translate_codex_skill` and `_translate_opencode_skill` to read `record.harness_description` (their `TRANSLATORS` registration is unchanged); register `(pi, skill)` in `TRANSLATORS`. Claude and gemini remain raw-symlink. Legacy fallback: if `record.harness_description is None` (inline-only legacy skill), all three translators fall back to `record.metadata.get("description")` and emit a `check`-level advisory through the existing advisory channel.
5. **`commands/_link_lib.py` — `_translate_slot_layout`** — extend to return `"dir-with-file-symlink"` for `(codex, skill)` and `(pi, skill)`. No change for claude/gemini (still raw symlink, no translator).
6. **`commands/new.py`** — update sidecar template; rewrite `_BODY_TEMPLATE_NO_FRONTMATTER` to include harness-facing frontmatter for skills; remove `--inline` support for skill kind (raises `SystemExit(2)` with a pointer to this spec).
7. **`commands/check.py`** — enforce new validation rules (sidecar mandatory, SKILL.md frontmatter required, both descriptions present, both end with period, name agreement).
8. **`doctor/skill_shape.py`** — new advisory module.
9. **`commands/migrate_skills.py`** — new top-level subcommand (`agent-toolkit migrate-skills`), registered in the CLI dispatch table and discoverable via `agent-toolkit --help`. Not hidden; this is a tool users may legitimately invoke against forks of the content repo.
10. **`~/GitHub/agent-toolkit/skills/agent-toolkit/SKILL.md`** — short doc note explaining the two-file shape, what goes where, and the rationale. **Lands in the follow-up content-repo PR, not this one.**

## Testing

Unit tests:

- `_translate_pi_skill`: sidecar fixture in/bytes out; asserts top-level `name`/`description`, asserts `argument-hint` lifted when `spec.per_harness.pi.argument_hint` present, asserts `agent_toolkit_cli` wrapper present.
- `_translate_codex_skill` / `_translate_opencode_skill`: now sourced from `record.harness_description` rather than `metadata.description`; existing test fixtures updated.
- Walker: `AssetRecord` exposes both descriptions distinctly; legacy inline-only fixture falls back correctly (legacy window).
- `check`: rejects inline-shape new skill; accepts sidecar+SKILL.md shape; fails when either description is missing or sans-period.
- `migrate-skills --dry-run`: golden-file test on a small fixture skills tree; idempotency test (run twice, second run reports no changes).

Integration:

- Link a fixture skill for each of the 5 harnesses with the new shape; assert claude/gemini slots are symlinks to the source SKILL.md, codex/opencode/pi slots are file symlinks into the per-scope translation cache with top-level keys present.
- Empirical re-verification against actual harness loaders (claude, pi, gemini) on a fixture skill — see "Open verifications."

## Open verifications

Three real-harness verifications gate merge. Each produces a concrete artifact stored in `assets/verification/150/` and referenced from the PR body.

| # | What | Method | Artifact |
|---|---|---|---|
| 1 | Claude reads top-level `description` from new-shape SKILL.md and activates the skill on a trigger phrase. | Link fixture skill into a clean `~/.claude/skills/` slot. Start `claude`. Issue a prompt matching the trigger. Confirm the model invokes the skill. | `assets/verification/150/claude-loader.log` — terminal transcript showing skill invocation. |
| 2 | Gemini discovers a new-shape skill (only `name` + `description` at top level, no `apiVersion`). | Link fixture skill into the gemini home. Run `gemini` and trigger activation. | `assets/verification/150/gemini-loader.log` — transcript. |
| 3 | Pi reads `argument-hint` lifted from `spec.per_harness.pi.argument_hint` into top-level SKILL.md frontmatter. | Link fixture skill with an `argument-hint` value. Run `pi demands` and check the hint surfaces. | `assets/verification/150/pi-arg-hint.log` — `pi` output showing the hint. |

If any verification fails, the spec needs revision **before plan acceptance**. Verifications 1 and 2 are about confirming the shape is harness-compatible; verification 3 is about the pi-specific translator. All three are run during the Verify step (flow Step 9) using the new `_translate_pi_skill` and the new SKILL.md scaffolder output.

If a verification cannot be run in the current environment (e.g., pi binary not installed locally), the spec is **NOT** revised — the verification is deferred to a post-merge follow-up issue and noted in the PR body. The codepath is shipped with unit tests covering the translator output; the empirical harness check is the safety net, not the only gate.

## Risks and trade-offs

- **Double the writing.** Authors maintain two descriptions per skill (CLI + harness). Mitigation: the CLI one is short and rarely needs updating; the harness one is where the real triggering effort goes anyway.
- **Migration script edge cases.** Hand-tuned `metadata.notes` containing free-form text that *looks like* `argument-hint: …` could be mis-extracted. Mitigation: the migration script's `argument-hint` lift is conservative (matches only `argument-hint: <single-line>` as the first non-blank line of `notes`).
- **Legacy translator branch carries complexity.** During the one-release tolerance window the codebase carries two read paths. Mitigation: tracked by a release-gated TODO comment; removal is a follow-up PR scheduled for the next minor version.
- **Discrepancy between repo state and emitted state.** Authors looking at `.claude/skills/<slug>/SKILL.md` will see the raw source (symlink), but authors looking at `.codex/skills/<slug>/SKILL.md` see translated cache output. This already exists for codex/opencode today; not a new problem.

## Out-of-scope follow-ups

- Tightening `spec.per_harness` schema once enough per-harness keys are known to enumerate.
- A `--shorten-cli-description` helper for `agent-toolkit fix` that proposes a sentence-trimmed CLI label from the harness description when the sidecar `metadata.description` is still flagged as TODO.
- Doctor check that warns when the harness description is unusually short (likely copied from CLI description by mistake) or unusually long for the CLI description (likely copied the other way).

## Content repo migration prompt

The CLI PR ships the `migrate-skills` subcommand. The content repo PR is created by running the following prompt in a fresh Claude Code session at `~/GitHub/agent-toolkit/`:

```
Run the agent-toolkit content-repo skill migration.

1. Confirm we are in ~/GitHub/agent-toolkit on a clean main branch.
2. Create a branch: `chore/migrate-skills-to-sidecar-shape`.
3. Run `agent-toolkit migrate-skills --content-repo . --dry-run` and show the plan.
4. If the plan looks right, run without --dry-run.
5. Review the diff. For each migrated skill, verify:
   - skills/<slug>/SKILL.md now has only `name` and `description` in frontmatter.
   - skills/<slug>.toolkit.yaml exists and carries the v1alpha2 wrapper.
   - The sidecar's `metadata.description` is flagged `# TODO shorten` if it
     was copied verbatim from the original harness description.
6. Run `agent-toolkit check`. It should pass cleanly.
7. Commit with message: `chore: migrate skills to sidecar+SKILL.md shape`.
8. Open a PR titled "Migrate skills to sidecar + harness-facing SKILL.md shape"
   with a body that links back to the design spec in agent-toolkit-cli.

Do NOT shorten the CLI descriptions in this PR. That is a follow-up review pass
where each `# TODO shorten` line is hand-tuned by a human.
```

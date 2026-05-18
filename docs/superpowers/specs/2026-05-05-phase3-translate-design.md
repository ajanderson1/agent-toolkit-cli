# Phase 3 — `translate` projection mechanism for OpenCode agents and commands

**Type:** feat · **Date:** 2026-05-05 · **Phase:** 3 of cross-harness rollout

## Goal

Introduce a fourth projection mechanism — **translate** — that generates a per-harness flavored markdown file in a CLI-managed cache, then symlinks the harness slot to the cache. Use it to project agents and commands into OpenCode, where the runtime frontmatter shape differs from the toolkit's wrapper. Keep the toolkit repo as the single source of truth.

## Scope

In scope:
- The `translate` mechanism end-to-end: dispatch table, render-to-cache helper, link/unlink integration, dry-run output, parity tests.
- Two specific cells flip from `unsupported (gap)` to `translate`:
  - `(opencode, agent)`
  - `(opencode, command)`
- Empirical verification that OpenCode tolerates the rendered frontmatter for both kinds.

Out of scope:
- Pi projection. The matrix says Pi gets symlinks today; no agents are currently projected to `~/.pi/agent/agents/` on the dev machine, so empirical verification is deferred to a follow-up. Phase 3 leaves Pi cells untouched.
- The follow-up sweep that adds `opencode` to every agent's and applicable command's `spec.harnesses` in the toolkit repo. That happens after Phase 3 lands and the empirical gates pass.
- Schema changes. Translation is a CLI mechanism, not an asset metadata change. Schema stays at `agent-toolkit/v1alpha2`.
- A separate `gc` command for stranded cache files. Punted to follow-up.

## Background

Existing projection mechanisms (per `docs/agent-toolkit/harness-matrix.md` § "Mechanisms"):

- **symlink** — driven by `_USER_TARGETS` in `_support.py`, dispatched per asset by `_link_lib.maybe_link`.
- **config_file** / **plugin_folder** — adapter Protocols in `harness_adapters/base.py`, registered via `harness_adapters/__init__.py:get_adapter`. Currently only the Codex MCP adapter is implemented.

Two cells in the matrix sit at `unsupported (gap)`:

- `(opencode, agent)` — slot exists at `~/.config/opencode/agents/<slug>.md`. OpenCode requires `mode: subagent` in frontmatter to register a drop-in as a subagent rather than a primary agent. Our wrapper frontmatter doesn't carry `mode`, so a direct symlink registers the agent as `mode: all` (primary), which silently mis-classifies it.
- `(opencode, command)` — slot exists at `~/.config/opencode/commands/<slug>.md`. OpenCode commands accept different frontmatter fields (`description`, `agent`, `model`, `subtask`, `template`) than Claude commands.

The matrix doc already names "Phase 3 `translate` adapter" as the planned remedy. This spec lands that mechanism.

## Empirical observations

Probed on the dev machine (`~/.config/opencode/`):

- `~/.config/opencode/agents/agent-native-reviewer.md` carries native frontmatter:
  ```yaml
  ---
  description: <text>
  mode: subagent
  temperature: 0.1
  ---
  ```
- `~/.config/opencode/commands/init_opencode.md` has **no frontmatter** — just markdown body. So at least one shipping OpenCode command works without any frontmatter at all. The translator MAY emit minimal frontmatter (just `description`); it MUST NOT depend on every native field being required.
- Pi reads its own shape (`name`, `description`, `tools`, `model`) — but Phase 3 doesn't touch Pi.
- No Phase-1-committed agent is currently projected into `~/.pi/agent/agents/` on this machine; Pi-via-symlink is unverified empirically (out of scope here, follow-up).

A prior session verified that dropping a markdown file with `mode: subagent` into `~/.config/opencode/agents/` makes `opencode agent list` register it correctly. Phase 3 re-verifies this with the *full* translator output (native keys + nested `agent_toolkit_cli:` block), since OpenCode's tolerance for extra top-level keys in agent frontmatter is the new bet.

## Design decisions

### D1. Cache location: per-scope, under the harness home

| Scope | Cache root |
|---|---|
| user | `~/.config/opencode/.agent-toolkit-cache/` |
| project | `<project>/.opencode/.agent-toolkit-cache/` |

Subdirectory by kind, then `<slug>.<ext>` matching the slot extension. Examples:

- `~/.config/opencode/.agent-toolkit-cache/agent/foo.md`
- `<project>/.opencode/.agent-toolkit-cache/command/bar.md`

**Rationale:** project-scope caches travel with the project clone naturally; `unlink` cleanup is local (cache file is in a sibling directory under the same scope root); discoverability is good (a user investigating the cache finds it adjacent to the slot they're already looking at). Trade-off accepted: if the same agent is linked into both user and project scope, we render twice and store twice — rare in practice, tiny disk cost.

### D2. Translator registration: flat dispatch dict

A new module `src/agent_toolkit_cli/_translators.py` exports:

```python
TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"):   _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
}
```

**Not** a third Protocol next to `PluginFolderAdapter`/`ConfigFileAdapter` — translation has exactly one operation (`(record, body) → bytes`). A Protocol for one method is ceremony. **Not** an extension to `_USER_TARGETS` either — that table holds slot paths for symlink-projected pairs, and conflating mechanism with path makes both harder to read. Translators live in their own table; the parity test enforces they don't drift from the matrix doc.

If Phase 4+ ever adds a *second* operation per (harness, kind) — say "validate round-trip" or "list managed cache files" — promote `TRANSLATORS` to a Protocol then. YAGNI for now.

### D3. Translation runs inline in `maybe_link`, not as a pre-pass

Add one branch at the top of `maybe_link`: if `(harness, kind) in TRANSLATORS`, the symlink target becomes the cache path; otherwise the existing `_expected_source` logic runs. The cache write happens just-in-time when we're about to symlink.

**Rationale:**
- Action counters (`created`/`updated`/`unchanged`) stay correct naturally — same control flow as the existing symlink branch.
- Dry-run is one branch: skip both the cache write and the symlink in one place.
- Failure semantics: a translator exception raises from inside the per-asset loop, with full asset context already on hand.

### D4. Cache-file cleanup on `unlink`: remove cache when slot is removed

When `unlink` removes a slot symlink whose target falls inside `<scope>/.agent-toolkit-cache/`, also remove the cache file. New helper `_prune_translated_slot` in `_link_lib.py`, sibling to `_prune_if_into_repo`. Detection is path-based: `os.readlink(slot)` resolves under the scope's cache root → both the slot and the cache file get deleted.

**Rationale:** per-scope caches (D1) mean exactly one slot symlink targets each cache file, so refcounting is unnecessary. Symmetric with link semantics: link writes cache + creates symlink in one operation; unlink reverses both. Avoids stranded cache files becoming a footgun on re-link six months later.

Edge case: cache file missing but symlink present (manual tampering) → silently delete the dangling symlink and move on. Same forgiving behaviour as `_prune_if_into_repo`.

### D5. `check` adds nothing translator-specific

Translator round-trip and output-shape validation lives in `tests/test_translators.py`. `check`'s job is asset/schema/AGENTS.md drift; it doesn't need to render every translator on every commit. Lefthook already runs pytest pre-commit, so coverage is achieved through the test suite.

### D6. Dry-run output: one line per asset, with translation noted

```
would-link: ~/.config/opencode/agents/foo.md -> ~/.config/opencode/.agent-toolkit-cache/agent/foo.md (translated from agents/foo.md)
```

One line per change, mirroring the existing `would-link:` shape. The parenthetical names the source asset for traceability without exploding output volume.

**Cache-staleness rule:** when the cache file already exists but its bytes differ from what the translator would now produce, treat the slot as `would-link` (will be updated) — not `unchanged`. The cache content is part of the symlink's effective state. Computed in-memory in dry-run by rendering and comparing.

### D7. Parity test: new `TestTranslateParity` class

Mirrors `TestSymlinkParity`. Three tests:
- Every doc cell marked `translate` has a `(harness, kind)` entry in `TRANSLATORS`.
- Every key in `TRANSLATORS` corresponds to a `translate` cell in the doc.
- Cache-path conventions match between doc and code: the path fragment after `→` in a `translate` cell matches the regex `\.agent-toolkit-cache/(agent|command)/<slug>\.md$` (after stripping `~/` and the user/project scope prefix).

`TRANSLATORS` is exported as a public name from `_translators.py` so the test imports it without reaching into private internals.

### D8. Translator output shape: native keys + `agent_toolkit_cli:` wrapper preservation

For both OpenCode agent and OpenCode command translators, the output frontmatter contains:
- The native top-level keys OpenCode reads (description, mode for agents).
- A nested `agent_toolkit_cli:` key holding the original `apiVersion`/`metadata`/`spec` block verbatim, for SSOT-traceability.

OpenCode skills already work via direct symlink with our wrapper frontmatter (per the matrix doc § "Frontmatter compatibility"), so tolerance for extra top-level keys is an existing bet for skills. Phase 3 carries it to agents and commands. Empirical re-verification gates (§ Test Plan) cover the new case.

## Components

### New files

- `src/agent_toolkit_cli/_translators.py` — `TRANSLATORS` dict + the two translator functions. Pure functions; no I/O.
- `tests/test_translators.py` — unit tests for the translator functions: output validity, round-trip stability, required-key invariants.

### Modified files

- `src/agent_toolkit_cli/commands/_link_lib.py`
  - Import `TRANSLATORS` from `_translators`.
  - Add `_render_to_cache(translator, asset_path, kind, slug, scope, project_root, dry_run) → Path`. Reads `asset_path`, splits frontmatter from body using the existing `walker._strip_frontmatter` helper (or equivalent), loads the `AssetRecord` via `walker.load_asset_record`, calls `translator(record, body) → bytes`, and writes atomically (tmp + rename) to the cache path. In `dry_run`, skips the write but still returns the cache path.
  - Modify `maybe_link` to dispatch through `TRANSLATORS` when applicable.
  - Add `_prune_translated_slot` helper used by unlink.
- `src/agent_toolkit_cli/commands/unlink.py` — call `_prune_translated_slot` when the slot symlink targets the per-scope cache.
- `docs/agent-toolkit/harness-matrix.md`
  - Flip `(opencode, agent)` and `(opencode, command)` cells from `unsupported (gap)` to `translate → <cache-path>`.
  - Add a "Translation" subsection under "Mechanisms" describing the cache layout and the SSOT-traceability property.
- `tests/test_harness_matrix.py` — add `TestTranslateParity` class.

### Unchanged

- `_support.py` (`_USER_TARGETS` doesn't gain entries; `translate` cells live in `TRANSLATORS`).
- `harness_adapters/` (translators don't go through `get_adapter`).
- `walker.py`, `schema.py`, `schemas/asset-frontmatter.v1alpha2.json`.
- All other commands and tests.

## Translator output specifications

### `(opencode, agent)` translator

Output frontmatter:
```yaml
---
description: <metadata.description; "" if absent>
mode: subagent
agent_toolkit_cli:
  apiVersion: agent-toolkit/v1alpha2
  metadata:
    name: <slug>
    description: <…>
    lifecycle: <…>
  spec:
    origin: <…>
    harnesses: [...]
    requires: { … }   # only if present in source
---
<body>
```

- `description` is duplicated from `metadata.description` so OpenCode reads what it expects. Multi-line source descriptions are collapsed to single-line.
- `mode: subagent` is a literal constant.
- The `agent_toolkit_cli:` block is a verbatim subset of source frontmatter — drops nothing, doesn't reformat key order.
- Output ends with exactly one `\n` after the body.

### `(opencode, command)` translator

Same shape as the agent translator, except:
- No `mode:` key (commands don't have a mode concept).
- Native top-level keys are `description` only. Other native fields (`agent`, `model`, `subtask`, `template`) are not derivable from our wrapper and not required per empirical evidence.

### Round-trip stability

Rendering the same input twice MUST produce byte-equal output. Guarded by a unit test. Required for the `unchanged` symlink-equality check to work reliably (otherwise every `link` run would re-link the slot).

## Acceptance criteria

1. `agent-toolkit link user opencode agent:<sample>` projects the agent: cache file written under `~/.config/opencode/.agent-toolkit-cache/agent/<sample>.md`, slot symlink at `~/.config/opencode/agents/<sample>.md` → cache.
2. `opencode agent list` shows the projected agent with `mode: subagent` (verified empirically).
3. `agent-toolkit link user opencode command:<sample>` does the same for a command, and OpenCode surfaces the command without errors.
4. `agent-toolkit unlink user opencode agent:<sample>` removes both the slot symlink and the cache file.
5. Re-running `agent-toolkit link …` after a no-op produces `unchanged` for the slot (no spurious updates).
6. Modifying the source asset's `metadata.description` and re-running `link` produces `updated` for the slot (cache-staleness detection works).
7. `agent-toolkit link --dry-run …` for a translated cell prints one line in the format `would-link: <slot> -> <cache> (translated from <toolkit-relative-path>)` and writes nothing to disk.
8. `agent-toolkit check --exit-code` continues to pass with the doc changes (parity test recognises `translate` cells).
9. All previously-passing tests still pass; new tests added for translator output and parity.
10. The matrix doc's two flipped cells use a `→` path fragment that satisfies the parity test's cache-convention regex.

## Test plan

### Unit tests (`tests/test_translators.py`)

- For each `(harness, kind)` in `TRANSLATORS`, given a sample `AssetRecord`:
  - Output parses as valid YAML frontmatter + body.
  - Required native keys are present (`description` always; `mode: subagent` for agents).
  - Nested `agent_toolkit_cli.apiVersion` equals `agent-toolkit/v1alpha2`.
  - Nested `agent_toolkit_cli.metadata.name` equals the source slug.
  - Round-trip stability: `translator(r, b)` called twice returns byte-equal output.
- A "render every shipping opencode-eligible asset" smoke test, parameterised over the toolkit repo's actual content. Catches metadata-shape bugs against real assets.

### Integration tests

Extend the existing link/unlink test suite (`tests/test_link.py`, `tests/test_unlink.py`) with cases for the two translated cells:
- Link writes cache + slot.
- Re-link with no source change is `unchanged`.
- Re-link with source change is `updated`.
- Unlink removes both.
- Dry-run prints the expected line and writes nothing.

### Parity tests (`tests/test_harness_matrix.py`)

`TestTranslateParity`:
- `test_every_translate_cell_has_translator_entry`
- `test_every_translator_entry_has_translate_cell`
- `test_translate_cell_path_matches_cache_convention`

### Empirical verification gates

Run once during Phase 3 implementation, **before** sweeping `opencode` into agent/command `harnesses` lists in the toolkit repo. Not automated in CI:

- **Gate A:** Render a translated agent file with the full output shape (native + nested wrapper). Drop in `~/.config/opencode/agents/`. Run `opencode agent list`. Confirm:
  - The agent appears in the list.
  - `mode: subagent` is shown (or implied by the listing's classification).
  - No errors or warnings about unrecognised frontmatter keys.
- **Gate B:** Render a translated command file. Drop in `~/.config/opencode/commands/`. Confirm:
  - OpenCode surfaces the command (e.g. via `/help` or its commands listing).
  - No errors about unrecognised frontmatter keys.

Both gate results are recorded in the implementation PR description. If either fails, the spec needs revision before the toolkit-repo sweep proceeds.

## Implementation strategy

Worktree at `~/GitHub/projects/agent-toolkit-cli/.worktrees/phase3-translate-<timestamp>/`, branch `feat/phase3-translate-<timestamp>`. Don't touch `main`.

Suggested commit sequence (one logical step per commit):
1. Add `_translators.py` with the two translator functions and `TRANSLATORS` dict.
2. Add `tests/test_translators.py` covering output shape and round-trip stability.
3. Wire `_render_to_cache` and translator dispatch into `_link_lib.maybe_link`.
4. Wire `_prune_translated_slot` into `unlink`.
5. Update `harness-matrix.md`: flip the two cells, add Translation subsection.
6. Add `TestTranslateParity` to `tests/test_harness_matrix.py`.
7. Run empirical gates A and B; record results in PR description.

All currently-passing tests must keep passing at every commit. Lefthook (pytest + schema-vendor-check) must stay green.

## Risks

- **OpenCode tolerance for extra top-level frontmatter keys on agents/commands.** Empirically verified for skills; gates A and B re-verify for the new cases. Fallback (if a gate fails): drop the nested `agent_toolkit_cli:` wrapper for the offending kind and replace with an HTML comment at body-top for traceability. Spec is revised before sweep proceeds.
- **Cache-path drift between matrix doc and code.** Mitigated by `TestTranslateParity::test_translate_cell_path_matches_cache_convention`.
- **Render output instability** (e.g., dict key order varying across Python versions). Mitigated by `yaml.safe_dump(..., sort_keys=False)` and a round-trip stability test.
- **Stale cache files after manual slot deletion.** Out of scope for Phase 3 (no `gc` command). Documented as a known follow-up.

## Follow-ups (not in this spec)

- Sweep `opencode` into `spec.harnesses` for every agent and applicable command in the toolkit repo. Gated on Phase 3 landing and gates A/B passing.
- Empirically verify Pi symlink projection works with the toolkit's wrapper frontmatter; if not, decide whether Pi gets `translate` too.
- Consider an `agent-toolkit gc` command for stranded cache files (caches whose slot symlink was manually deleted).
- Consider promoting `TRANSLATORS` to a Protocol if a second per-(harness, kind) operation arrives (validate round-trip, list managed files, etc.).

# Fix `(gemini, agent)` — translate, don't symlink

**Issue:** [#97](https://github.com/ajanderson1/agent-toolkit-cli/issues/97)
**Status:** spec (draft)
**Date:** 2026-05-19

## Context

PR #95 (issue #53) registered `(gemini, agent)` as a raw symlink cell — the asset's `.md` is linked into `~/.gemini/agents/<slug>.md` without translation, mirroring how `(claude, agent)` works.

Issue #97 was filed as a verification follow-up: confirm the raw-symlink cell actually works against a real `gemini` CLI binary. The host that built #53 didn't have `gemini` installed (binary required ≥ v0.39), so the check fell back to structural verification only.

## Empirical findings (2026-05-19)

Verified against `gemini` v0.40.1 + `agent-toolkit-cli` at commit `b33e6b3` (current `main`). Two bugs surfaced:

### Bug 1 — slot filename has no `.md` extension

`src/agent_toolkit_cli/commands/_link_lib.py::_slot_filename` returns:

- `<slug>.md` for `(opencode|claude, agent|command)`
- `<slug>.toml` for `(gemini, command)`
- `<slug>` (bare, no extension) for everything else — **including `(gemini, agent)`**

Concrete observation: `agent-toolkit-cli link user gemini agent:demo-agent` produced `~/.gemini/agents/demo-agent` (no extension).

Gemini CLI's loader globs `*.md` for agents (source: `docs/core/subagents.md` in `google-gemini/gemini-cli`, section "Agent definition files"). Bare-named files are silently invisible.

### Bug 2 — frontmatter shape mismatch

Even after fixing the extension, Gemini's loader requires **top-level** `name:` and `description:` in the YAML frontmatter. The toolkit's v1alpha2 wrapper nests these under `metadata.name` / `metadata.description` alongside `apiVersion` / `spec`. With the wrapper as written, the loader either rejects the agent or loads it with an empty name/description.

This is the same class of bug OpenCode hit for skills (#41) and Codex hit for skills (#40). Precedent: `_translate_opencode_agent`, `_translate_opencode_skill`, `_translate_codex_skill` all strip the wrapper to top-level and preserve full v1alpha2 metadata under an `agent_toolkit_cli` block.

## Out-of-scope

- Project-scope `(gemini, agent)` end-to-end manual test — covered by symmetric code paths; a single unit test for the project target is sufficient.
- Verifying agents actually invoke at runtime inside a `gemini` session (model dispatch / tool use) — structural visibility via `/agents list` is the contract this PR ships against. Runtime behavior is the asset's responsibility, not the toolkit's.
- Touching `(gemini, command)` or `(gemini, skill)` — they are already correct (#95).

## Decision

Change `(gemini, agent)` from `symlink` to `translate`. Implement `_translate_gemini_agent` analogous to `_translate_opencode_agent`. Extend `_slot_filename` to return `<slug>.md` for `(gemini, agent)` (translated slot is a file, not a directory).

## Architecture

Three coupled edits + matrix update + tests.

### Translator — `_translate_gemini_agent`

In `src/agent_toolkit_cli/_translators.py`, define analogous to `_translate_opencode_agent`:

```python
def _translate_gemini_agent(record: AssetRecord, body: str) -> bytes:
    """Gemini's loader requires top-level `name` and `description` in the YAML
    frontmatter. The toolkit's v1alpha2 wrapper nests these under metadata.*,
    so the loader either rejects the agent or loads it with an empty
    name/description (#97).

    Output mirrors `_translate_opencode_skill` — top-level `name` and
    `description` plus `agent_toolkit_cli` wrapper block for round-trip
    traceability. Empirically verified against gemini 0.40.1.
    """
    fm = {
        "name": _name(record),
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)
```

Note: OpenCode's agent variant injects `mode: subagent`. Gemini does not need a `mode` field — agents auto-load as delegable subagents. Per Gemini docs (`docs/core/subagents.md`) optional frontmatter fields (`tools`, `model`, `mcpServers`, `temperature`, etc.) are not synthesised by the toolkit; they remain authorable in the asset's spec block and propagate through the wrapper if the author included them.

Register in `TRANSLATORS`:

```python
("gemini", "agent"): _translate_gemini_agent,
```

### Slot filename — `_slot_filename`

In `src/agent_toolkit_cli/commands/_link_lib.py`, extend the `.md` branch to include `(gemini, agent)`:

```python
def _slot_filename(slug: str, kind: str, harness: str) -> str:
    if harness == "gemini" and kind == "command":
        return f"{slug}.toml"
    if (kind in {"agent", "command"} and harness in {"opencode", "claude"}) \
       or (harness == "gemini" and kind == "agent"):
        return f"{slug}.md"
    return slug
```

`_translate_slot_layout` already handles `(gemini, agent)` correctly via the `.endswith(".md")` branch returning `"file"` once `_slot_filename` is fixed — no separate edit needed.

### Cache path

`_render_to_cache` writes `f"{slug}.md"` for all file-slot kinds. Gemini-translated agents will land at `~/.gemini/.agent-toolkit-cache/agent/<slug>.md` and the slot symlinks to that cache file. Matches OpenCode's pattern.

### Matrix update

`docs/agent-toolkit/harness-matrix.md` agent row, gemini column:

**Before:** `symlink → ~/.gemini/agents/<slug>.md`

**After:** `translate → ~/.gemini/agents/<slug>.md (cache: ~/.gemini/.agent-toolkit-cache/agent/<slug>.md) — emits gemini-shaped frontmatter with top-level name and description plus agent_toolkit_cli wrapper block`

Also update the agent-row prose section below the matrix to note the empirical reason (loader requires top-level name/description, mirrors OpenCode).

The `harness_adapters/gemini.py` module docstring should gain a one-line note pointing at this issue for the agent-shape decision trail.

## Testing

### Unit tests

- `tests/test_translators.py` — three tests for `_translate_gemini_agent`:
  1. Round-trip a minimal record. Assert YAML frontmatter parses, has top-level `name` and `description` matching the record, has `agent_toolkit_cli.metadata` and `agent_toolkit_cli.spec` round-tripping the wrapper.
  2. Body preservation — body content arrives byte-identical after frontmatter.
  3. `TRANSLATORS` dict — assert `("gemini", "agent")` resolves to `_translate_gemini_agent`.

- `tests/test_link_lib.py` — extend gemini slot-filename tests:
  4. `_slot_filename("foo", "agent", "gemini") == "foo.md"` (was `"foo"`).
  5. `_translate_slot_layout("gemini", "agent") == "file"` (regression guard — derived from `_slot_filename`, but lock the contract).

- `tests/test_harness_matrix.py` — the matrix-parser test catches the row change automatically. Confirm the parametric assertion for `(gemini, agent)` updates from `symlink` to `translate` cleanly.

### Empirical verification (Step 9 of flow)

The same recipe used in the pre-flow check:

1. Temp-add `gemini` to `~/GitHub/agent-toolkit/agents/demo-agent.md` `harnesses:` list.
2. `agent-toolkit-cli link user gemini agent:demo-agent`.
3. Assert `~/.gemini/agents/demo-agent.md` exists (with `.md` extension) and its symlink resolves into the cache.
4. `head ~/.gemini/agents/demo-agent.md` — confirm top-level `name: demo-agent` and `description: …`.
5. Restore demo-agent.md.

Optionally, dispatch a `gemini` session and confirm `/agents list` surfaces the agent. Treated as nice-to-have; the file-shape assertions above are the contract.

Artifacts captured to `assets/verification/97/`:
- `link-output.txt` — output of the link command
- `slot-file.txt` — `ls -la ~/.gemini/agents/`
- `cache-head.txt` — `head -20` of the cache file
- `gemini-agents-list.txt` (if attempted)

## Acceptance

- All 685+ existing tests pass.
- New translator tests pass (3 new in test_translators.py, 2 new in test_link_lib.py).
- Harness-matrix row updated; doc test passes.
- Empirical link produces `~/.gemini/agents/<slug>.md` with top-level `name` and `description`.
- Self-review verdict: PASS or needs-changes-applied-and-resolved.

## Risks

- **Existing project-scope assets that declared `(gemini, agent)` and were linked under the broken cell** would have produced invisible bare-named files. These need cleanup post-merge. Mitigation: the toolkit's `link` is idempotent — re-running after merge with the same allowlist will translate to `.md` and the old bare-named files are stale links that `unlink`/relink prunes. Worth a one-line note in the PR body.
- No back-compat shim needed — the prior bare-named files never worked, so nobody is depending on the broken behaviour.

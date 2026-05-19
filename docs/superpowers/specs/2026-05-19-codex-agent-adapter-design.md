# (codex, agent) adapter — per-asset TOML translator

**Issue:** #140
**Date:** 2026-05-19
**Mode:** `--ship-it`

## Goal

Ship `(codex, agent)` as a supported `(harness, kind)` pair. A toolkit asset of `kind: agent` linked to the `codex` harness produces one TOML file per agent at `~/.codex/agents/<slug>.toml` (user scope) and `<project>/.codex/agents/<slug>.toml` (project scope), discoverable by Codex CLI's subagents runtime.

## On-disk shape (per developers.openai.com/codex/subagents)

- User scope: `~/.codex/agents/<name>.toml`
- Project scope: `<project>/.codex/agents/<name>.toml`
- Required TOML fields: `name` (string), `description` (string), `developer_instructions` (string — agent prompt body)
- Toolkit-provenance table: `[agent_toolkit_cli]` (mirrors the (gemini, command) pattern — JSON-encoded `metadata` and `spec` blocks for round-trip)
- Optional fields (deferred — out of scope for this PR): `nickname_candidates`, `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`

## Strategy

This pair fits the existing **symlink + per-asset translator** path used by `(codex, skill)`, `(opencode, *)`, and `(gemini, command)`. No new strategy class needed.

Concretely:
- Add `_translate_codex_agent(record, body) -> bytes` to `_translators.py` and register in `TRANSLATORS` for `("codex", "agent")`.
- Output mirrors `_translate_gemini_command`'s TOML emission: `_toml_basic_string` for scalars, `_toml_multiline_string` for `developer_instructions` (markdown body), JSON-encoded `metadata` and `spec` under `[agent_toolkit_cli]`.
- Linker writes the rendered TOML to the per-scope cache and the slot file `~/.codex/agents/<slug>.toml` is a symlink to that cache file (layout `file`).

### Changes to projection-time code

1. `_support.py`:
   - Add `("codex", "agent"): "{home}/.codex/agents"` to `_USER_TARGETS`.
   - Add `("codex", "agent"): ".codex/agents"` to `_PROJECT_TARGETS`.
   - Update the module docstring's "remaining gaps" comment.

2. `_translators.py`:
   - Add `_translate_codex_agent(record, body)` rendering the TOML shape above.
   - Register in `TRANSLATORS`.

3. `commands/_link_lib.py`:
   - `_slot_filename`: extend to return `<slug>.toml` for `(codex, agent)`.
   - `_translate_slot_layout`: `(codex, agent)` resolves to `"file"` automatically via the existing `_slot_filename().endswith(".md")` branch — but `.toml` does not end with `.md`. Need to extend the condition to also return `"file"` when the slot filename ends with `.toml`. Mirror what already happens for `(gemini, command)` via the explicit `if harness == "gemini" and kind == "command": return "file"` short-circuit; add the symmetric short-circuit for `(codex, agent)`.
   - `_render_to_cache`: the hardcoded `.md` extension at line 183 must derive from `_slot_filename(slug, kind, harness)` instead. This is a small, surgical change that the existing (gemini, command) cache already exercises but bugs through because the cache file extension currently doesn't actually need to match the slot extension for symlinked-file slots (the symlink target name is irrelevant). Verify this empirically — if (gemini, command) survives with a `.md` cache file pointed to from a `.toml` slot, then we can leave (codex, agent) the same way and there is no `_render_to_cache` change. **The plan will validate this against existing tests before deciding.**

## Tests

- `tests/test_translators.py`: unit test the new translator — required fields rendered, body becomes `developer_instructions`, `[agent_toolkit_cli]` table present with apiVersion + JSON-encoded metadata/spec.
- `tests/test_link_codex_agent.py` (new): link + unlink + drift + project scope, mirroring `tests/test_link_codex_skill.py`'s structure. Drift = hand-edit the TOML, re-link, verify the toolkit detects and re-writes.
- `tests/test_support.py`: add `(codex, agent)` to the expected SUPPORTED_PAIRS list.
- `tests/test_doctor_*.py`: any test that enumerates per-harness coverage gets the new row.

## Out of scope

- Optional fields beyond the three required (defer until a real asset needs them).
- Codex's top-level `[agents]` config-file table (separate surface — global agent settings, not per-agent definition).
- Bumping the support matrix for any other `(codex, *)` pair.
- Manual verification against a live `codex` install (the DoD asks for it; the `--ship-it` mode does an automated artifact check only — the PR body flags this for the human reviewer).

## Definition of done

- `(codex, agent)` rows present in both `_USER_TARGETS` and `_PROJECT_TARGETS`.
- Translator registered, tested, and produces valid TOML for codex's runtime shape.
- Link / unlink / list / doctor / inventory handle the pair without special-casing.
- Pre-flight CI green: lint + tests pass locally before push.
- Verification artifacts attached: rendered sample TOML from a fixture asset + link/unlink trace.
- PR body flags "human should manually verify against a real codex install" in the eyeball checklist.

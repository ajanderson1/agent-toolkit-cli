# Spec: `config_file` MCP adapters for Claude and OpenCode

**Issue:** #55
**Predecessor:** #29 — codex MCP adapter (CLI-PR-1) shipped the `ConfigFileAdapter` Protocol, dispatcher, ownership rules, and round-trip test pattern. This spec ports the same shape to two more harnesses.
**Date:** 2026-05-05
**Mode:** flow `--auto`

## Goal

Replace the `claude` and `opencode` adapter stubs with real `ConfigFileAdapter` implementations so `agent-toolkit link/unlink/fix/list/doctor mcps` work end-to-end against `~/.claude.json` (Claude) and `~/.config/opencode/opencode.json` (OpenCode), at both `user` and `project` scope.

After this PR, `pi` is the **only** remaining unimplemented MCP adapter.

## Why now

The audit on #32 confirmed that both gaps are closeable with the same `config_file` mechanism the codex adapter already uses — they were excluded from #32's scope by design ("Touching `_mcp_dispatch.py` is owned by the adapter PRs"), and #29 proved the pattern works. Closing the gaps unblocks two TUI cells (`claude/mcp`, `opencode/mcp`) and frees the `force` flag in `_mcp_dispatch.apply_link`.

## Non-goals

- **Pi MCP** — by design (no MCP support), see follow-up A item 3 from #32.
- **Codex `[hooks]` / `[agents]` adapters** — separate follow-up C.
- **Doc/matrix bug fixes from follow-up A** — the matrix line-18 fix lands here as a tightly-scoped consequence of this PR (the prose currently misnames Claude's MCP mechanism), but other follow-up A items remain separate.
- **TUI smoke testing in CI** — the issue's "TUI smoke test" check is a manual eyeball at PR review time; we will not invent CI for it in this PR.
- **No support for additional MCP transports** beyond what each harness natively handles (see Pre-flight refusals).

## What ships

### 1. `harness_adapters/claude.py` — full ConfigFileAdapter

Mutates a single JSON file via `json.loads` / `json.dumps(..., indent=2, sort_keys=True)`. Round-trip is **not byte-equal** for hand-edited files (JSON has no comments / formatting to preserve), but it **is** structurally idempotent: the same input → same output, every time.

| Aspect | Value |
|---|---|
| `name` | `"claude"` |
| `strategy` | `"config_file"` |
| User-scope target | `~/.claude.json` |
| Project-scope target | `<project>/.mcp.json` (only when `<project>/.mcp.json` exists OR project allowlist mentions an MCP — see below) |
| Managed key path | top-level `mcpServers.<name>` |
| Pre-flight refusal | none — Claude's MCP loader supports `stdio`, `sse`, `http` natively. The adapter accepts whatever transport the catalog declares; if the catalog grows non-Claude-compatible transports later, that is a catalog/policy issue, not an adapter issue. |
| Server entry shape | `{type, command, args?, env?, url?, headers?}` derived from `inner_config`. Shape mapping in **§ Entry shape mapping** below. |

**Project-scope subtlety.** Codex's project-scope rule is "only if `<project>/.codex/` exists." Claude's analogue is `<project>/.mcp.json` itself — there is no `.claude/` umbrella that gates it. The project file lives at the repo root. Rule used in `config_target`:

```python
def config_target(self, scope, project_root):
    if scope == "user":
        return Path(os.environ.get("HOME", "")) / ".claude.json"
    target = project_root / ".mcp.json"
    return target if target.is_file() else None
```

The `is_file()` gate keeps us from materialising `.mcp.json` in repos that have never opted in — same shape as codex's `.codex/` gate, just file-based instead of dir-based. If the user wants to enable project-scope Claude MCPs, they `touch .mcp.json` first.

**Why JSON, not the `claude mcp add` CLI.** The `claude` CLI's add-server command is interactive-ish and doesn't compose well with our diff/apply model. Direct JSON mutation matches what the codex adapter does for `~/.codex/config.toml` and gives us deterministic, testable behaviour.

### 2. `harness_adapters/opencode.py` — full ConfigFileAdapter

Same shape as Claude, mutating a different JSON file under a different key path.

| Aspect | Value |
|---|---|
| `name` | `"opencode"` |
| `strategy` | `"config_file"` |
| User-scope target | `~/.config/opencode/opencode.json` |
| Project-scope target | `<project>/.opencode/opencode.json` (only when `<project>/.opencode/` exists) |
| Managed key path | top-level `mcp.<name>` |
| Pre-flight refusal | none — OpenCode supports `stdio` (`type: "local"`) and HTTP/SSE (`type: "remote"`). Adapter maps catalog transport accordingly. |
| Server entry shape | `{type: "local", command: [...], environment: {...}, enabled: bool}` for stdio; `{type: "remote", url, headers, enabled}` for HTTP/SSE. See **§ Entry shape mapping**. |

**Project-scope dir-gate.** Mirrors codex precisely: `<project>/.opencode/` must already exist; we don't materialise it.

### 3. Registry wiring — `harness_adapters/__init__.py`

Add lazy-imported branches for `claude` and `opencode`, structured exactly like the existing codex branch:

```python
if harness == "codex":
    from agent_toolkit.harness_adapters.codex import CodexAdapter
    return CodexAdapter()
if harness == "claude":
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter
    return ClaudeAdapter()
if harness == "opencode":
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter
    return OpenCodeAdapter()
return UnimplementedAdapter(harness)
```

### 4. `_mcp_dispatch.py` — clean up the `force` flag comment

Line 57 currently:

```python
force: bool = False,  # noqa: ARG001 — CLI-PR-2 wires this for Claude; ignored here
```

The new claude adapter does **not** wire `force` — JSON mutation has no semantic equivalent to "force overwrite" beyond the existing diff (we always overwrite the managed `mcpServers.<name>` block; hand-rolled blocks elsewhere are preserved untouched, same ownership rule as codex). Update the comment to:

```python
force: bool = False,  # noqa: ARG001 — reserved; not wired by any current adapter
```

The flag stays in the signature for callers/CLI parity, but the comment no longer makes a forward promise that has now been actively decided against.

### 5. Matrix doc updates — `docs/agent-toolkit/harness-matrix.md`

Two edits, both line-bounded:

**Mechanisms section, line 17–18.** The current prose says:

> **plugin_folder** — adapter owns a whole subfolder (e.g. `~/.claude/plugins/agent-toolkit/`). Currently used for MCPs in Claude.

This sentence has been wrong since `plugin_folder` was first introduced — Claude MCPs do not live in `~/.claude/plugins/`, they live in `~/.claude.json` `mcpServers`. (The audit on #32 caught this.) Replace with:

> **plugin_folder** — adapter owns a whole subfolder (e.g. `~/.claude/plugins/agent-toolkit/`). Currently unused; reserved for future kinds that own a directory rather than a config file.

**Matrix table, mcp row.** Line 54 currently:

```
| **mcp** | unsupported (gap) — adapter not yet implemented | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | unsupported (gap) — adapter not yet implemented | unsupported (gap) — adapter not yet implemented |
```

Replace claude and opencode cells (pi cell stays as `unsupported (gap)` — pi MCP is a non-goal here):

```
| **mcp** | config_file → `~/.claude.json` `mcpServers.<name>` | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | config_file → `~/.config/opencode/opencode.json` `mcp.<name>` | unsupported (by design) — Pi has no MCP concept |
```

> **Pi cell change rationale.** The current "gap" wording for pi is wrong: pi has no MCP support at all, by design. Same audit caught this. Switching pi from `gap` to `by design` is on the path of "make the matrix honest" and the parity test (`test_harness_matrix.py`) passes either way as long as no adapter is registered for pi/mcp. Keeping it as `gap` would create a phantom todo. Marking it `by design` matches reality.

**"Why some pairs are by design" section, mcp bullet (line 137–139).** Current text:

> **mcp** is currently three gaps + one supported (codex). All four harnesses support MCP servers; the gaps are CLI work, not design limits.

Replace with:

> **mcp** is supported on three of four harnesses (claude, codex, opencode) via `config_file` adapters. Pi has no MCP concept — it loads tools from its own extension API instead, see the `pi-extension` row.

### 6. Tests (TDD)

Mirroring the codex test file's structure. Two new files, plus two surgical edits to existing files.

**New: `tests/test_mcp_adapters_claude.py`** — round-trip suite. Same coverage as codex:

- `test_claude_adapter_basic_attrs` — `name == "claude"`, `strategy == "config_file"`.
- `test_claude_user_config_target` — `~/.claude.json`.
- `test_claude_project_config_target_requires_file` — only when `<project>/.mcp.json` exists.
- `test_claude_can_install_accepts_all_transports` — stdio, sse, http all accepted (no refusal).
- `test_claude_diff_creates_file_when_missing` — produces a `create` action.
- `test_claude_diff_preserves_other_top_level_keys` — non-`mcpServers` keys (e.g. `numStartups`, `theme`) survive untouched.
- `test_claude_diff_unchanged_when_aligned` — second diff is `[]`.
- `test_claude_unlink_removes_managed_entry` — same `previously_allowed` semantics.
- `test_claude_unlink_does_not_touch_handrolled_entries` — names outside `previously_allowed | desired` preserved.
- `test_claude_link_unlink_round_trip_idempotent` — round-trip is structurally identical (same parsed JSON), even if not byte-equal.
- `test_claude_list_installed_returns_all_mcp_server_names` — every key in `mcpServers`.
- `test_claude_list_installed_missing_file_returns_empty`.
- `test_claude_entry_drift_false_when_aligned`, `test_claude_entry_drift_true_after_hand_edit`.
- `test_claude_re_link_byte_identical_when_already_linked` (same pattern as codex AC#2).
- `test_claude_project_target_uses_dot_mcp_json` — touches `<project>/.mcp.json`, confirms project-scope round-trip.
- `test_claude_diff_handles_http_transport` — entry with `transport: http` and `url:` produces `{type: "http", url: ..., headers: ...}`.
- `test_claude_diff_handles_sse_transport` — entry with `transport: sse` produces `{type: "sse", url: ...}`.

**New: `tests/test_mcp_adapters_opencode.py`** — same coverage, OpenCode-specific:

- Mirrors all of the above, paths swapped to `~/.config/opencode/opencode.json` and `<project>/.opencode/opencode.json`.
- Managed key path `mcp.<name>` (not `mcpServers.<name>`).
- Server entry shape: `type: "local"` with `command: [str, ...]` (single list, not separate `command + args`); `enabled: true` defaulted.
- Adds `test_opencode_local_entry_command_is_a_single_list` — mapping check, since opencode merges `command` + `args` into one array.
- Adds `test_opencode_remote_entry_for_http_transport` — `{type: "remote", url, headers, enabled: true}`.

**Edit: `tests/test_mcp_dispatch.py:226–240`** — `test_apply_link_unimplemented_adapter_is_silent_noop` currently uses `get_adapter("claude")` for the UnimplementedAdapter case. Switch to `get_adapter("pi")` (the only harness that remains unimplemented after this PR).

**Edit: `tests/test_doctor_mcps.py:216–230`** — `test_doctor_mcps_skips_unimplemented_harness` same swap: `harness="claude"` → `harness="pi"`. Test name + docstring updated to reference pi.

**Edit: `tests/test_harness_matrix.py`** — no edits expected. The matrix-doc edits described in §5 keep parity with the new adapters; the existing tests (`test_config_file_and_plugin_folder_cells_have_real_adapters`, `test_adapter_strategy_matches_doc_cell`) will pass automatically once the adapters are registered.

### 7. Entry shape mapping

A single helper per adapter, scoped to the adapter file. **Catalog inputs we expect:**

```json
// mcps/<slug>/config.json
{
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp"],
  "env": {"FOO": "bar"}
}
```

```yaml
# mcps/<slug>/README.md frontmatter
spec:
  mcp:
    transport: stdio   # or sse, http
    url: https://...   # if transport != stdio
    install_method: npx
```

**Claude output (stdio):**

```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp"],
  "env": {"FOO": "bar"}
}
```

**Claude output (http/sse):**

```json
{
  "type": "http",
  "url": "https://...",
  "headers": {}
}
```

(headers omitted if absent.)

**OpenCode output (local / stdio):**

```json
{
  "type": "local",
  "command": ["npx", "-y", "@upstash/context7-mcp"],
  "environment": {"FOO": "bar"},
  "enabled": true
}
```

**OpenCode output (remote / http or sse):**

```json
{
  "type": "remote",
  "url": "https://...",
  "headers": {},
  "enabled": true
}
```

OpenCode always sets `enabled: true` — the catalog implies "linked therefore enabled"; if a user wants to disable it they can hand-edit, and the ownership rule preserves that hand-edit because hand-edits within a managed entry produce a `entry_drift == True` diff, signalled to the user as a fix-eligible drift (same as codex).

Wait — that last sentence is actually wrong. Codex semantics on a managed entry that drifted: the next `link --fix` rewrites it back to template. Same here: if a user toggles `enabled: false` on a managed MCP, `agent-toolkit fix mcps` will set it back to `true`. **This is the documented codex behaviour and we keep it.** If users want to disable an MCP they remove it from the allowlist; toggling `enabled` is a hand-edit on a managed entry and gets stomped on the next reconcile. Document this in the OpenCode adapter's module docstring.

### 8. Why structural-not-byte-equal round-trip is acceptable

Codex pursues byte-equal round-trip because TOML files can carry hand-edits with comments and odd whitespace that matter. JSON has no comments — formatting is purely a function of `json.dumps` settings. Once we adopt `indent=2, sort_keys=True, ensure_ascii=False, separators=(",", ": ")` (matching what `claude` and `opencode` themselves emit), every read-then-write reproduces the same bytes for content the adapter touches. Hand-edited values (e.g. extra top-level keys) survive because we read → mutate → dump the whole document.

The only case where output differs from input byte-for-byte is when the user-on-disk JSON used a different formatter (4-space indent, no trailing newline, etc.). That is a one-time normalisation on first link; subsequent link/unlink cycles are stable. We document this in module docstrings.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `~/.claude.json` is shared with the Claude Code app (settings) — corruption could nuke the user's whole config | Atomic write (already implemented in `_mcp_dispatch._atomic_write_bytes`). Tests cover the round-trip and unchanged-key preservation. The whole-document read-mutate-dump approach means non-`mcpServers` keys are physically copied through, never reconstructed. |
| OpenCode `enabled` field "stomp on user disable" surprise | Documented in module docstring + matrix doc. Same semantics as codex hand-edits-within-managed-entries → fix re-aligns. Consistent across the family. |
| First-run normalisation rewrites the whole file even when only adding one MCP | Acceptable: same as codex. The diff still produces a single `update` action with the whole new content; the byte delta is the only visible artefact and is one-time per file. |
| Catalog adds a new transport (e.g. `websocket`) that one harness rejects | Pre-flight `can_install` is the right place to refuse. Today none of the three accepts something the others don't, so the adapters stay permissive. If a divergence appears, add a refusal there. |
| Project `.mcp.json` doesn't exist when user wants to enable it | `config_target` returns `None` → dispatcher silently no-ops. We do not auto-create the file. Document in CLI help that `touch .mcp.json` is the opt-in. (Symmetric to codex's `.codex/` requirement.) |

## Acceptance criteria

1. `get_adapter("claude")` returns a `ClaudeAdapter`, not `UnimplementedAdapter`.
2. `get_adapter("opencode")` returns an `OpenCodeAdapter`, not `UnimplementedAdapter`.
3. Round-trip `link → unlink → link` for both adapters, both scopes, leaves a managed `mcpServers.<name>` / `mcp.<name>` block functionally identical to first link (structural JSON equality).
4. Hand-rolled MCP entries (names not in `previously_allowed | desired`) survive unlink untouched.
5. Non-MCP keys at the top level of the config file (e.g. Claude's `theme`, OpenCode's `theme`, `model`) are preserved through link/unlink.
6. `agent-toolkit doctor mcps --harness claude` and `--harness opencode` recognise the adapters and produce the same status surface as codex.
7. `harness-matrix.md` reflects the new state; `tests/test_harness_matrix.py` passes.
8. `_mcp_dispatch.py` line-57 comment matches the new reality (no forward promise to wire `force`).
9. `tests/test_mcp_dispatch.py` and `tests/test_doctor_mcps.py` UnimplementedAdapter probes use `pi`, not `claude`.
10. Lint (`ruff`) and tests (`pytest`) green locally.

## Out of band

- TUI smoke test — manual eyeball at PR review time. The matrix doc + parity tests give the TUI strong typing for free; cells should become tickable automatically once `get_adapter()` returns real adapters. Note in PR body to verify by running the TUI and ticking each new cell.

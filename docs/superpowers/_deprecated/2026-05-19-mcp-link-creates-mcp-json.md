# Plan — fix: project-scope MCP link creates target when absent

Spec: `docs/superpowers/specs/2026-05-19-mcp-link-creates-mcp-json-design.md`.
Closes #125.

## Tasks

### T1. ClaudeAdapter.config_target — always return the path

File: `src/agent_toolkit_cli/harness_adapters/claude.py`.

- Replace lines 36-39 (the `if not target.is_file(): return None` branch)
  with an unconditional `return project_root / ".mcp.json"`.
- Keep the `scope == "user"` branch unchanged.

### T2. CodexAdapter.config_target — always return the path

File: `src/agent_toolkit_cli/harness_adapters/codex.py`.

- Replace lines 40-43 (the `if not codex_dir.is_dir(): return None` branch)
  with an unconditional `return project_root / ".codex" / "config.toml"`.
- Verify the write path in `diff()` / commit creates `.codex/` (parents) when
  the file doesn't yet exist. If not, add a `target.parent.mkdir(parents=True,
  exist_ok=True)` at the appropriate write site.

### T3. Tests for claude

File: `tests/harness_adapters/test_claude_mcp.py` (or wherever Claude MCP
adapter tests live — locate by grep).

Add: `test_diff_creates_mcp_json_when_absent`:
- Make a tmp project_root with **no** `.mcp.json`.
- Build a minimal `McpEntry` (stdio, command="/bin/true").
- Call `adapter.diff(scope="project", project_root=tmp, entries=[entry])`.
- Assert: returns one `WriteAction` with `op="create"` and `path` ending
  `.mcp.json`.

### T4. Tests for codex

Symmetric: `test_diff_creates_codex_config_when_absent` — same shape, expects
target ending `.codex/config.toml`.

### T5. Full preflight

- `uv run ruff check .`
- `uv run pytest -q`

All must pass.

## Order

T1 → T3 → T2 → T4 → T5. Each pair (impl + test) is one logical unit; do
claude first because it's the issue's direct subject.

## Out-of-scope reminders

- Do NOT touch gemini / opencode / codex_hook config_target methods.
- Do NOT change the Protocol return type in `base.py`.

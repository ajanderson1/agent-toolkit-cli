# MCP management — design

Status: draft
Date: 2026-05-04

## Problem

`agent-toolkit-cli` manages skills, commands, and agents as harness-agnostic assets. MCP (Model Context Protocol) servers are conspicuously missing. The toolkit catalog already contains an `mcps/` directory with ~20 MCP entries (`mcps/<name>/{config.json, README.md}`), but the CLI has no link/unlink/list/diff/doctor support for them.

The previous Claude-only project (`claude_tui_tools`) handled MCPs by owning `.mcp.json` outright — full overwrite on apply. That model breaks two ways under harness-agnosticism: (1) different harnesses store MCPs in different files and formats, and (2) "owning the file" loses hand-edits, which the new project's principles forbid.

The design must satisfy: harness-agnostic UX, idempotent writes, reliability under hand-edits, simplicity (no exotic machinery), transparency (loud writes), reversibility, and three-way coexistence between CLI, TUI, and hand-edits.

## Non-goals

- **Secrets management.** The tool never reads, writes, prompts for, or stores secret values. Env-var references in source `config.json` files are written through verbatim; the user sets the env var in their shell.
- **Translating substitution syntax across harnesses.** If `${VAR}` works on Claude but not Codex, that is a runtime concern of the user's harness, not a write-time concern of this tool. `doctor` may warn; the tool does not rewrite.
- **MCP runtime/lifecycle management.** Starting Docker containers, managing OAuth tokens, killing stuck stdio processes — out of scope.
- **MCPs not in the toolkit catalog.** Every MCP this tool installs comes from `<toolkit-repo>/mcps/<name>/`. Users with one-off MCPs use `agent-toolkit ingest` to add them to the catalog first.
- **Supporting harnesses other than Claude, Codex, OpenCode, Pi.** New harnesses are added via new adapter modules; the design accommodates this but does not predesign for unknown harnesses.

## Design

### Mental model

The user sees one uniform interface. The codebase has one uniform interface. The mechanism each adapter uses to satisfy that interface varies per harness, chosen to be the *least intrusive* path the harness sanctions. The user does not see which mechanism is in use.

```
USER: agent-toolkit link user claude mcps:context7
  │
  ▼
COMMAND LAYER: resolves allow-list, dispatches to adapter
  │
  ▼
ADAPTER (per harness): chooses mechanism
  │
  ├─► plugin folder strategy   (Claude — drops files into ~/.claude/plugins/agent-toolkit/)
  └─► config file strategy     (Codex/OpenCode/Pi — surgical edit of native config)
```

### The five rules

The whole design follows from these:

1. **Allow-list is the only authority on what we manage.** No sidecars, no provenance markers, no fences. If a `mcps:<name>` entry appears in the merged allow-list for `(scope, harness)`, we manage that named entry in the harness's MCP namespace. Otherwise we never touch it.

2. **Manage by name, never by file ownership.** We do not own `~/.codex/config.toml`. We own `[mcp_servers.context7]` *inside it*. Round-tripping parsers preserve everything else byte-for-byte.

3. **One mechanism per (harness, scope), chosen for least intrusion.** Each adapter picks plugin-folder if the harness sanctions it for MCPs at that scope, file-edit otherwise. Per-adapter detail; not visible above the adapter layer.

4. **Drift is structural equality, not text equality.** A managed entry is "in good shape" if the parsed structure equals the rendered template. Whitespace, key order, comment placement — irrelevant to drift detection.

5. **Loud, atomic, never-mid-flight writes.** Every adapter prints `→ writing <path>` before mutating. Every write is `tempfile.NamedTemporaryFile(dir=target.parent) → os.replace(target)` (same-directory staging guarantees atomicity across filesystems). For Claude user-scope (`~/.claude.json` is a live state file Claude rewrites continuously), `link`/`unlink` refuse if a `claude` process is running, with `--force` opt-out. (Note: `--force` here is distinct from `--strict` — `--strict` upgrades missing-harness warnings to errors; `--force` bypasses safety guards.)

### Components

#### Schema (`src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha1.json` → bumps to `v1alpha2`)

Adds optional `metadata.kind` (with walker-derived fallback when absent — chosen to avoid forcing a migration of every existing skill/command/agent file). When `kind == mcps`, `spec.mcp` is required (added under `properties.spec.properties` in the schema):

```json
"mcp": {
  "type": "object",
  "required": ["transport", "install_method"],
  "additionalProperties": false,
  "properties": {
    "transport":      { "enum": ["stdio", "http", "sse"] },
    "install_method": { "enum": ["npx", "uvx", "docker", "local", "remote"] },
    "command":        { "type": "string" },
    "env":            { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
    "optional_env":   { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
    "prerequisites":  { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
    "verify":         { "type": "string" }
  }
}
```

Both `transport` and `install_method` are required so adapters can dispatch correctly without inspecting the inner `config.json`. The `env` list is declarative — used by `doctor` for env-var presence checks.

#### Walker (`src/agent_toolkit_cli/walker.py`)

Adds `mcps` to recognized kinds. Each MCP asset record carries `mcp_spec` (parsed frontmatter under `spec.mcp`) and `inner_config` (the verbatim contents of `mcps/<name>/config.json`).

#### Harness adapters (`src/agent_toolkit_cli/harness_adapters/`)

New package. One module per harness plus a base `Protocol`:

```python
class HarnessMCPAdapter(Protocol):
    name: str                                    # "claude" | "codex" | "opencode" | "pi"
    strategy: Literal["plugin_folder", "config_file"]

    # ---- Plugin-folder strategy ----
    def plugin_target(self, scope: Scope, project_root: Path) -> Path:
        """Folder we own entirely. e.g. ~/.claude/plugins/agent-toolkit/"""
    def render_plugin(self, entries: list[McpEntry]) -> dict[Path, str]:
        """Returns {relative_path: content}. Caller writes atomically."""

    # ---- Config-file strategy ----
    def config_target(self, scope: Scope, project_root: Path) -> Path:
        """File we mutate (round-trip). e.g. ~/.codex/config.toml"""
    def read(self, path: Path) -> ParsedConfig:
        """Round-tripping parse. Missing file -> empty parsed structure."""
    def upsert(self, parsed: ParsedConfig, name: str, inner_config: dict) -> ParsedConfig:
        """Insert/replace ONE named entry. Translates inner_config to harness-native shape."""
    def remove(self, parsed: ParsedConfig, name: str) -> ParsedConfig:
        """Delete by name. No-op if absent."""
    def write(self, path: Path, parsed: ParsedConfig) -> None:
        """Atomic write via temp file in same dir + os.replace."""

    # ---- Both strategies ----
    def diff_managed(self, current_state: ParsedConfig | dict[Path, str],
                     desired_entries: list[McpEntry]) -> Diff:
        """Structural comparison. Returns add/remove/update list."""
    def can_install(self, mcp_spec: McpSpec) -> Result[None, str]:
        """Pre-flight refusal. e.g. Codex returns Err when transport=http and env has ${VAR}
        references that Codex won't expand."""
```

Per-harness module shapes (exact mechanism per (harness, scope) confirmed during implementation, not in this spec; defaults below):

| Adapter | Default strategy | Default target | Notes |
|---|---|---|---|
| `claude.py` | `plugin_folder` | `~/.claude/plugins/agent-toolkit/` (user) or `<project>/.claude/plugins/agent-toolkit/` (project) | Plugin manifest declares `mcpServers`. Pending verification that this loads cleanly; fallback is `config_file` to `.mcp.json` (project) / `~/.claude.json` (user). |
| `codex.py` | `config_file` | `~/.codex/config.toml` (user); `.codex/config.toml` (project, only if trusted) | TOML via `tomlkit`. Must mutate only `[mcp_servers.X]` tables; preserves all other tables and comments. |
| `opencode.py` | `config_file` | `~/.config/opencode/opencode.json` (user); `<project>/opencode.json` (project) | JSON/JSONC. Translates inner_config: `command:str + args[]` → `command:[exe, ...args]`, `env` key → `environment`, `${VAR}` → `{env:VAR}` (substring replace, conservative). Refuse if source uses `${VAR:-default}`. |
| `pi.py` | `config_file` | `~/.config/mcp/mcp.json` (user); `<project>/.pi/mcp.json` (project) | Pi reads `.mcp.json` for compat with Claude, but we write to `.pi/mcp.json` to keep harness ownership unambiguous. Each adapter writes only its own target; no shared files between adapters. |

#### Commands

- **`link`**: for each allow-listed MCP, call `adapter.can_install()`. On `Err`: print warning, skip. On `Ok`: dispatch by strategy. `plugin_folder` → render → atomic-write file tree. `config_file` → `read → upsert → write`. Loud per write. When the same MCP is allow-listed for two harnesses with different adapters, each adapter writes independently to its own target.
- **`unlink`**: dispatch by strategy. `plugin_folder` → re-render with the entry removed (file may shrink, may delete itself if empty). `config_file` → `read → remove → write`. Idempotent.
- **`list`**: per harness × scope, gather state via adapter. Status glyphs:
  - `[x]` allow-listed and installed and matches template
  - `[~]` allow-listed and installed but drifted from template
  - `[ ]` allow-listed but not installed
  - `[!]` installed but not allow-listed (hand-edit; we never touch)
- **`diff`**: dry-run output: per harness, per file, what `link` would write. Uses adapter's `diff_managed`.
- **`doctor`**: new group `mcps`. For each allow-listed MCP: drift detection (structural equality), env-var presence in current shell (warn-only), prerequisites on PATH, optional `verify:` exit code (only with `--verify` flag — verify commands run arbitrary shell, opt-in for safety).
- **`fix`**: re-run `upsert` for all allow-listed MCPs to reconcile drift.
- **`new`**: scaffold `mcps/<name>/{config.json, README.md}` in the toolkit repo with the v1alpha2 frontmatter shape.
- **`ingest`**: extending `ingest` to support MCP source URLs / config snippets is out of scope for this spec and covered in a follow-up. v1 of MCP support assumes catalog entries already exist (created via `new` or hand-authored).

#### TUI

`src/agent_toolkit_tui/` gains an MCPs section. Reads via the same adapters; writes via the same adapters. No parallel write logic — TUI is purely a view onto the same code path.

### Transparency

Per the "explicit when we write/modify" requirement:
- Every write prints `→ writing <path>` before, and `✓ wrote <path> (<bytes>B)` after.
- `--dry-run` flag on `link`/`unlink`/`fix` shows would-be writes without touching anything.
- All writes are atomic (temp file in same directory, then `os.replace`).
- `doctor` is read-only — never writes.
- `link`/`unlink` against `~/.claude.json` (user-scope Claude config-file fallback path) checks for running `claude` process and refuses with `--force` opt-out.

### Schema migration sequencing

Adding `metadata.kind` as a *required* field would break every existing skill/command/agent. To avoid bundling a migration with this work, `metadata.kind` is **optional** with walker-derived fallback. The walker continues to derive kind from directory name; if frontmatter declares `kind`, the validator cross-checks it matches the derivation. This is mild inconsistency in exchange for not gating MCP work behind a separate migration.

A future migration making `kind` required can be done independently; not blocked by this spec.

### Failure modes and recovery

| Failure | Behavior |
|---|---|
| Round-trip parse fails (corrupted JSON/TOML) | Refuse to write. Print parse error with file path. Suggest `agent-toolkit doctor` for diagnostics. |
| Atomic write succeeds, target file ends up with bad content | Cannot happen — round-trip parser validates content before serialization. |
| User edits inside a managed entry | Detected by `diff_managed` as drift. `list` shows `[~]`. `doctor` reports it. `fix` overwrites. No special "tampering" workflow needed. |
| Claude rewrites `~/.claude.json` between our read and write | Mitigated by check for running process + `--force` flag. Not eliminated. Acceptable per Q2 (iii). |
| Codex rewrites `config.toml` between our read and write | `tomlkit` round-trip preserves Codex's added sections. Race window exists but is small; mitigation by atomic write. |
| `claude_target_dir` doesn't exist (harness not installed) | `link` warns ("Claude does not appear to be installed at <path>; skipping"), exits 0. `--strict` flag turns warning into error. Consistent with existing `warn-missing-harness-home` behaviour. |
| Adapter's translation can't represent the source MCP (e.g. OpenCode receives `${VAR:-default}`) | `can_install` returns `Err`. Link skips with loud warning. User must adjust source or accept incompatibility. |

### What this design rejects, and why

- **Fenced markers (`# >>> agent-toolkit managed >>>`)** — unnecessary; manage-by-name + round-trip parsers suffice. Fences add a parsing burden and can be tampered with.
- **Provenance manifests / sidecars** — unnecessary; the allow-list is the manifest. A second source of truth invites drift.
- **One mechanism (plugin-only or file-only) across all harnesses** — Codex has no plugin model for MCPs, OpenCode/Pi unconfirmed. Forcing one mechanism either leaves harnesses unsupported or drives intrusiveness on harnesses that don't need it.
- **Sharing `.mcp.json` between Claude and Pi project scope** — Pi reads `.mcp.json` for compat, but having two adapters write the same file makes `unlink` ambiguous (does removing from Pi remove from Claude?). Each adapter writes its own target. Pi users who want Claude's catalog can install both.
- **Translating env-var substitution syntax across harnesses** — silently rewriting `${VAR}` to `{env:VAR}` for OpenCode is one thing (mechanical, single direction); broader translation (e.g. translating `${VAR}` references to Codex's `bearer_token_env_var = "VAR"` field) crosses into magic. We translate only what is mechanical and obvious; otherwise refuse with a clear message.
- **Custom IDs for MCP entries** — entries are identified by their toolkit-repo directory name. No separate ID, no aliasing.

### Open items resolved during implementation, not in this spec

These do not change the spec's mechanism but determine each adapter's strategy:

1. Confirm Claude Code plugin manifest's `mcpServers` field actually loads MCPs (vs only being honored by `claude mcp add`). If it doesn't, Claude adapter falls back to `config_file` strategy on `.mcp.json` / `~/.claude.json`.
2. Confirm OpenCode plugin model supports declaring MCPs (`.opencode/plugins/<name>.js`). Default assumption: it does not; OpenCode adapter uses `config_file`.
3. Confirm Pi project-scope target is `.pi/mcp.json` (per pi-mcp-adapter precedence rules) and that this is the right place to write rather than `.mcp.json`.
4. Confirm `tomlkit` round-trips Codex's `[notice.model_migrations]`, `[tui.model_availability_nux]`, etc. without churn. Test gate: a Codex `config.toml` byte-equal except for `[mcp_servers.X]` tables after a link/unlink round-trip.

These are validated empirically in the implementation plan's first phase and surface as adapter-internal choices.

## Acceptance criteria

A correct implementation:

1. `agent-toolkit link <scope> <harness> mcps:context7` installs the MCP via the harness's preferred mechanism without printing or storing secrets.
2. Re-running the same `link` command produces byte-identical files on disk (deterministic render order: entries sorted by name, stable JSON/TOML serialization).
3. `agent-toolkit unlink <scope> <harness> mcps:context7` removes only that named entry. Hand-rolled MCP entries with other names in the same file are byte-equal before and after.
4. `agent-toolkit list <harness>` shows MCP install state alongside skills/commands/agents using the four-glyph status.
5. `agent-toolkit diff <scope> <harness>` shows would-be changes per file, no writes.
6. `agent-toolkit doctor` reports drift for MCPs whose installed entry differs structurally from the rendered template, and warns on missing env vars / prerequisites.
7. `agent-toolkit fix` reconciles drift to canonical form.
8. For each adapter, a round-trip test asserts: source file with comments + unknown sections + hand-rolled MCP entries → `link` an unrelated MCP → `unlink` it → byte-equal to source.
9. Schema-drift CI passes against the bumped v1alpha2 schema.
10. The TUI's MCPs section reads and writes via the same adapter API as the CLI; no duplicate logic.

## References

- Research: per-harness MCP install mechanics (Codex/Claude/OpenCode/Pi) — internal report, 2026-05-04.
- Research: superpowers + claude_tui_tools comparative review — internal report, 2026-05-04.
- `claude_tui_tools` MCP write path: `packages/settings/src/claude_tui_settings/models/persistence.py` (`_build_mcp_json`, `_atomic_install`).
- Toolkit catalog convention: `<toolkit-repo>/mcps/<name>/{config.json, README.md}` with frontmatter (`name`, `description`, `status`, `install_method`, `command`, `prerequisites`, `verify`, `obsidian_note`).

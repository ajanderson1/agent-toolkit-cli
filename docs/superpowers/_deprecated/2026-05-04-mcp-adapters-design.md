# MCP adapters — design (Plan B)

Status: draft
Date: 2026-05-04

## Context

This is the follow-up to [`2026-05-04-mcp-management-design.md`](./2026-05-04-mcp-management-design.md). That spec laid out the full shape of MCP management; Plan A (commit `d44a98f`) shipped the foundations: walker, allow-list section, projection no-op, and surfacing in `list`/`diff`/`doctor` with status `unsupported` as a stand-in.

Plan B implements the actual write/read path: harness adapters, the `link`/`unlink` write paths, real `diff`, drift detection in `doctor`, `fix` reconciliation, the four-glyph status in `list`, the schema bump to v1alpha2, and the TUI light-up.

The "five rules" of the parent spec carry through unchanged: allow-list is sole authority, manage by name not file ownership, one mechanism per (harness, scope), drift is structural equality, loud atomic writes.

## Non-goals

Carried from the parent spec: secrets, substitution-syntax translation across harnesses, MCP runtime/lifecycle, MCPs not in the catalog, harnesses other than Claude/Codex/OpenCode/Pi. Additionally for this plan:

- **Catalog frontmatter migration** is an `agent-toolkit` content-repo PR that lands *before* this CLI PR. Not bundled.
- **`new mcp <name>` scaffolding** is deferred — small follow-up after adapters are proven.
- **`ingest` for MCPs** is a separate spec.

## Open items resolved by this design

The parent spec listed four open items deferred to implementation. This design fixes them where it can and earmarks the rest for plan-phase-0 spikes:

1. *Does Claude's plugin manifest `mcpServers` actually load MCPs?* → Empirical test in CLI-PR-2 phase 0. Protocol shape supports either outcome (PluginFolder or ConfigFile fallback) without redesign.
2. *Does OpenCode have a plugin model for MCPs?* → Default assumption: no. OpenCode adapter uses `config_file`. Confirmed during implementation phase 0.
3. *Pi project-scope target = `.pi/mcp.json`?* → Yes. Each adapter writes its own target; we explicitly do not share `.mcp.json` between Claude and Pi project scope.
4. *`tomlkit` round-trip stability on Codex configs?* → Phase-0 spike before Codex impl, with byte-equal test against a representative config.

## Design

### Adapter package layout

New package: `src/agent_toolkit_cli/harness_adapters/`

```
harness_adapters/
    __init__.py          # exports get_adapter(harness) → adapter instance
    base.py              # Protocol definitions, McpEntry, WriteAction
    claude.py            # PluginFolderAdapter (default); ConfigFileAdapter fallback if needed
    codex.py             # ConfigFileAdapter
    opencode.py          # ConfigFileAdapter
    pi.py                # ConfigFileAdapter
```

`get_adapter(harness: str) → PluginFolderAdapter | ConfigFileAdapter` is the only entry point above the package; CLI commands and the TUI runner do not import individual adapter modules.

### Two Protocols

Per the design discussion (Q1), one base + two strategy Protocols, not one fat Protocol with NotImplementedError stubs. Adapters implement exactly one strategy (Claude may implement both if its fallback path triggers).

```python
Scope = Literal["user", "project"]                       # matches existing string usage

@dataclass(frozen=True)
class McpEntry:
    name: str                                            # toolkit-repo dir name; canonical id
    inner_config: dict                                   # parsed mcps/<name>/config.json verbatim
    mcp_spec: dict                                       # parsed spec.mcp from sibling README.md

@dataclass(frozen=True)
class WriteAction:
    path: Path
    op: Literal["create", "update", "delete", "unchanged"]
    bytes_before: int | None                             # None on create
    bytes_after: int | None                              # None on delete
    contents: bytes | None                               # rendered desired bytes; None on delete

class CannotInstall(Exception):
    """Pre-flight refusal raised by adapters. Caller catches and skips one entry,
    proceeding with siblings. Matches the codebase's exception-raising pattern
    (see _yaml_edit.add_slug → ValueError, walker → yaml.YAMLError)."""

class _AdapterCommon(Protocol):
    name: str                                            # "claude" | "codex" | "opencode" | "pi"
    strategy: Literal["plugin_folder", "config_file"]

    def can_install(self, entry: McpEntry) -> None:
        """Pre-flight refusal. Adapter-specific. Raises CannotInstall(message)
        on refusal; returns None on success."""

    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        """Names currently present in this harness's MCP namespace.
        Used for [!] (installed-not-allowlisted) detection."""

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        """True if this single entry differs structurally from its template.
        Does NOT consider sibling entries' presence/absence."""

class PluginFolderAdapter(_AdapterCommon, Protocol):
    strategy: Literal["plugin_folder"]

    def plugin_target(self, scope: Scope, project_root: Path) -> Path:
        """Folder we own entirely."""

    def render(self, entries: list[McpEntry]) -> dict[Path, bytes]:
        """{absolute_path: content_bytes} for the full desired state.
        Empty entries → {} (caller deletes existing files; rmdir if empty)."""

    def diff(
        self, scope: Scope, project_root: Path, entries: list[McpEntry]
    ) -> list[WriteAction]:
        """Compare on-disk against render(entries). Each WriteAction's `contents`
        carries the bytes to write; `apply_link` does not re-render."""

class ConfigFileAdapter(_AdapterCommon, Protocol):
    strategy: Literal["config_file"]

    def config_target(self, scope: Scope, project_root: Path) -> Path:
        """File we mutate (round-trip)."""

    def read(self, path: Path) -> ParsedConfig:
        """Round-trip parse. Missing file → empty ParsedConfig."""

    def upsert(self, parsed: ParsedConfig, entry: McpEntry) -> ParsedConfig:
        """Insert/replace one named entry. Translates inner_config to harness-native shape."""

    def remove(self, parsed: ParsedConfig, name: str) -> ParsedConfig:
        """Delete by name. No-op if absent."""

    def render(self, parsed: ParsedConfig) -> bytes:
        """Serialise to bytes."""

    def diff(
        self, scope: Scope, project_root: Path, entries: list[McpEntry]
    ) -> list[WriteAction]:
        """At most one WriteAction (the config file) or empty if no change.
        The action's `contents` carries the rendered bytes."""
```

`ParsedConfig` is each adapter's own concrete type (TOMLDocument for Codex, dict for plain JSON, etc.). Opaque to callers.

### Dispatch

New module: `src/agent_toolkit_cli/commands/_mcp_dispatch.py`. Owns:

- The `apply_link` entry point used by both `link` and `unlink` (since both reduce to "reconcile harness state to current allow-list desired set").
- The atomic-write helper: `tempfile.NamedTemporaryFile(dir=target.parent, delete=False) → os.replace(target)` for writes, `os.unlink` (then optional `os.rmdir`) for deletes.
- The loud-write print contract, op-specialised:

| Op | Pre-write | Post-write |
|---|---|---|
| `create` | `→ creating <path>` | `✓ created <path> (<bytes_after>B)` |
| `update` | `→ updating <path>` | `✓ updated <path> (<bytes_before>B → <bytes_after>B)` |
| `delete` | `→ deleting <path>` | `✓ deleted <path> (was <bytes_before>B)` |
| `unchanged` | (no output) | (no output) |

`WriteAction` carries the rendered `contents` from `diff()` so the writer never re-renders. The dispatcher only knows how to write bytes atomically and delete files; adapter-internal logic (parse/upsert/render) all happens during `diff()`.

```python
def apply_link(
    adapter,
    scope: Scope,
    project_root: Path,
    entries: list[McpEntry],
    *,
    dry_run: bool,
    stdout: IO[str],
) -> list[WriteAction]:
    actions = adapter.diff(scope, project_root, entries)
    if dry_run:
        for act in actions:
            if act.op != "unchanged":
                print(f"would-{act.op}: {act.path}", file=stdout)
        return actions
    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act)              # writes act.contents atomically, or deletes
        _print_post(act, stdout)
    return actions
```

### Schema bump v1alpha1 → v1alpha2 (full replacement, no dual dispatch)

The current validator (`src/agent_toolkit_cli/schema.py:20`) hard-codes the v1alpha1 schema path. There is no version-dispatch infrastructure, and adding one for a single transitional version would be dead code the moment the catalog finishes migrating.

We **replace** v1alpha1 with v1alpha2. There is no period where both validate. The CLI ships v1alpha2 only; the catalog migrates in lockstep (PR ordering below).

#### File-level changes

- New: `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`. Mirrors v1alpha1 with the two changes below.
- Delete: `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha1.json`.
- `src/agent_toolkit_cli/schema.py:20` — points at the v1alpha2 file. No `apiVersion` dispatch.
- `src/agent_toolkit_cli/_repo_resolution.py:26` (`_SCHEMA = "schemas/..."`) — bump the path constant.
- `src/agent_toolkit_cli/doctor/environment.py:14,18` — bump the schema-presence check.
- `src/agent_toolkit_cli/doctor/per_resource.py:46` — update the "v1alpha1 valid" finding string.
- `src/agent_toolkit_cli/commands/new.py:24,79,95` — emit `apiVersion: agent-toolkit/v1alpha2` and add an `mcp` kind branch (see "new mcp scaffold" note below).
- `src/agent_toolkit_cli/ingest/types.py:46` — bump emitted `apiVersion`.
- `tests/conftest.py:12,32,34` — bump fixture text and schema path.
- Repo-level `schemas/asset-frontmatter.v1alpha2.json` (the SSOT copy referenced by `doctor/environment.py`) — replace alongside the bundled package copy.

#### Schema content changes

Two changes vs v1alpha1:

1. **`metadata.kind` becomes optional.** Walker derives kind from directory structure. If frontmatter declares `metadata.kind`, the validator cross-checks it matches the walker's derivation; mismatch is a validation error. Per parent spec, this avoids forcing changes to skill/command/agent *content* — only their `apiVersion` line bumps.

2. **`spec.mcp` block** (required when walker-derived kind is `mcp`, forbidden otherwise):

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

The conditional ("required when kind==mcp") is enforced via JSON Schema `allOf` + `if`/`then`, the same pattern v1alpha1 already uses for `origin`/`upstream`. The kind discriminator is `metadata.kind` if present, else taken from validator context (the validator passes the walker-derived kind down with the asset).

#### `new mcp <slug>` scaffold

`commands/new.py` currently scaffolds skill/agent/command/hook/plugin. The schema bump adds an `mcp` branch that writes a starter `mcps/<slug>/README.md` with v1alpha2 frontmatter (the catalog shape) and a stub `config.json`. Follow-up work; this PR ships the scaffold function but the broader "MCP authoring UX" is its own thing.

#### Catalog migration sequencing (two-PR cadence)

Because there is no transitional dual-validate window, the catalog has to be migrated *before* the CLI PR lands, but the migrated catalog can't validate against `agent-toolkit-cli` `main` (still v1alpha1). The cadence:

1. **Content repo PR (`agent-toolkit/mcps/*` + the rest)** — bumps every `apiVersion` from `v1alpha1` → `v1alpha2` and adds `spec.mcp` blocks to MCP READMEs. This PR breaks `agent-toolkit-cli` validation against the catalog by design. It does not need CI to pass against `main` of `agent-toolkit-cli`; the content repo's own checks pass.
2. **CLI PR-1 (this plan, Codex proof + full wiring)** — ships v1alpha2 schema. Once merged, the catalog and CLI agree again.

Order matters but the gap window only affects developers running `agent-toolkit check` against an in-flight tree. CI is unaffected — the CLI's own tests use a fixture catalog (`tests/conftest.py`) which migrates inside the CLI PR.

### Per-adapter targets and translation

#### `codex.py` — ConfigFileAdapter

| Field | Value |
|---|---|
| Target (user) | `~/.codex/config.toml` |
| Target (project) | `<project>/.codex/config.toml` (only if dir exists) |
| Round-trip parser | `tomlkit` |
| Managed namespace | `[mcp_servers.<name>]` tables |
| Translation | `inner_config.command` + `args[]` → `command = "..."`, `args = [...]`. `env` (dict) → `env = { ... }`. `type: "stdio"` → omitted. |
| Refusal cases | `transport != "stdio"` (Codex MCP support is stdio-only). |

`tomlkit` preserves `[notice.*]`, `[tui.*]`, comments, blank lines, key order. AC #8 round-trip test asserts byte-equality after link/unlink of an unrelated MCP.

#### `opencode.py` — ConfigFileAdapter

| Field | Value |
|---|---|
| Target (user) | `~/.config/opencode/opencode.json` |
| Target (project) | `<project>/opencode.json` (only if exists) |
| Round-trip parser | JSONC-preserving lib (concrete pick in plan phase 0; falls back to plain `json` with documented comment-loss warning if no good lib). |
| Managed namespace | `mcp.<name>` keys |
| Translation | `command:str + args:list` → `command:[exe, ...args]`. `env` key → `environment`. `${VAR}` → `{env:VAR}` (substring replace, single direction). |
| Refusal cases | `${VAR:-default}` syntax. `transport != "stdio"` if confirmed unsupported during phase 0. |

If no acceptable JSONC round-trip lib exists, the adapter degrades to plain JSON. First write loses comments, but a `doctor` warning surfaces this *before* any write happens.

#### `pi.py` — ConfigFileAdapter

| Field | Value |
|---|---|
| Target (user) | `~/.config/mcp/mcp.json` |
| Target (project) | `<project>/.pi/mcp.json` |
| Round-trip parser | plain `json` (Pi's mcp.json is generated; comment preservation not a concern) |
| Managed namespace | `mcpServers.<name>` |
| Translation | None — Pi's format matches the catalog `inner_config` shape directly. |
| Refusal cases | None known; plan phase 0 confirms. |

We **do not** share `<project>/.mcp.json` between Claude and Pi project scope. Each adapter writes its own target unambiguously.

#### `claude.py` — PluginFolderAdapter (default), with config_file fallback if needed

| Field | Value |
|---|---|
| Target (user, plugin) | `~/.claude/plugins/agent-toolkit/` |
| Target (project, plugin) | `<project>/.claude/plugins/agent-toolkit/` |
| Plugin manifest file | `agent-toolkit/plugin.json` carrying `mcpServers: { ... }` |
| Fallback target (user) | `~/.claude.json` (only if plugin loading doesn't work — phase 0 in CLI-PR-2) |
| Fallback target (project) | `<project>/.mcp.json` |

The plugin-vs-fallback decision is empirical (phase 0 in CLI-PR-2). Result drives whether `claude.py` exposes only `PluginFolderAdapter` or both.

Safety guards specific to Claude:

- Writes against `~/.claude.json` (only relevant if fallback): refuse if a `claude` process is running. `--force` to bypass.
- Plugin folder writes: no process check needed; Claude doesn't rewrite `~/.claude/plugins/`.

### Translation policy summary

The tool **mechanically translates only what is syntactic and obvious**:

- `command + args` ↔ flat `command` array (OpenCode).
- `env` key rename `env` → `environment` (OpenCode).
- `${VAR}` → `{env:VAR}` (OpenCode, single direction).

Anything else — defaults, ternaries, harness-specific bearer-token fields — causes `can_install` to raise `CannotInstall(message)` naming the offending construct.

### link / unlink wiring

`commands/_link_lib.py:212-223` is the no-op MCP branch added in Plan A. It is the *only* site that needs replacing. Both `link.py` (all four entry points: bare/per-asset/all/plan) and `unlink.py` flow through `project_from_file()` which contains this branch.

The replacement:

```python
if kind == "mcp":
    section = kind_to_section(kind)
    mcp_slugs = list(allowed.get(section, []))
    if not mcp_slugs:
        continue

    entries = _build_mcp_entries(toolkit_root, mcp_slugs)
    adapter = get_adapter(harness)
    actions = apply_link(
        adapter,
        scope=scope,
        project_root=project_root,
        entries=entries,
        dry_run=dry_run,
        stdout=stdout,
    )
    counters.merge(actions_to_counters(actions, dry_run))
    continue
```

`_build_mcp_entries` resolves each slug to `mcps/<slug>/{config.json, README.md}` and constructs `McpEntry`.

The unified semantics ("reconcile harness state to current allow-list desired set") means `link` and `unlink` use the *same* dispatch call. They differ only in how the allow-list YAML is mutated *before* the dispatch — which they already do today.

#### Failure isolation

- `adapter.can_install()` raises `CannotInstall` for one entry → that entry is skipped with a loud warning; siblings proceed.
- Adapter parse/I/O error → dispatcher raises; `link`/`unlink` exits non-zero. Same contract as skill projection.

#### Flag semantics

- `--dry-run` — already exists on `link`/`unlink`. `apply_link` returns the action list, prints `would-<op>: <path>` per non-`unchanged` action, makes no filesystem mutation.
- `--force` — **new flag introduced by this plan**, only relevant in PR-2 (Claude). Bypasses the running-`claude` guard when the fallback path mutates `~/.claude.json`. No-op for adapters whose target is not under live harness contention. Defined here, implemented in PR-2.

The parent spec also mentions `--strict` (promote missing-harness-home warning to error). That flag does not exist today and is **not introduced by Plan B** — it's orthogonal to MCP work. If `--strict` lands later it transparently affects all asset kinds; no special-casing for MCPs is anticipated.

### diff

`commands/diff.py` MCP branch:

```python
if kind == "mcp":
    entries = _build_mcp_entries(toolkit_root, mcp_slugs)
    adapter = get_adapter(harness)
    actions = adapter.diff(scope, project_root, entries)
    for act in actions:
        click.echo(format_diff_action(act))
```

Output shape:

```
codex / user / mcp:
  ~ ~/.codex/config.toml (4521B → 4612B)
    +mcp_servers.context7
```

`diff` is read-only.

### doctor

New group `mcps` joins the eight existing groups in `commands/doctor.py:23`:

```python
def run(toolkit_root, *, harness, scope, project_root) -> GroupResult:
    """For each allow-listed MCP under (harness, scope):
       - structural drift (call adapter.entry_drift; True = drift finding)
       - env var presence in current shell (warn-only on missing required env)
       - prerequisites on PATH (warn on missing)
       - optional verify command (only with --verify flag, runs arbitrary shell)
    """
```

Slots in alongside `environment`, `symlink-integrity`, ..., `allowlist-audit`. `doctor --group mcps` runs only this group. `doctor` never writes.

### fix

`commands/fix.py` MCP branch reconciles drift with a diff-first check (preserves mtime when nothing changed):

```python
if kind == "mcp":
    entries = _build_mcp_entries(toolkit_root, mcp_slugs)
    adapter = get_adapter(harness)
    actions = adapter.diff(scope, project_root, entries)
    nontrivial = [a for a in actions if a.op != "unchanged"]
    if not nontrivial:
        continue
    apply_link(adapter, scope, project_root, entries, dry_run=False, stdout=stdout)
```

### list — four-glyph status

Replace the `"unsupported"` overload in `commands/_list_json.py:160-179` for MCPs with the four real states:

| Status (JSON) | Glyph (text) | Meaning |
|---|---|---|
| `linked-matches` | `[x]` | allow-listed AND installed AND `entry_drift == False` |
| `linked-drifted` | `[~]` | allow-listed AND installed AND `entry_drift == True` |
| `unlinked-allowlisted` | `[ ]` | allow-listed AND not installed |
| `installed-not-allowlisted` | `[!]` | not allow-listed BUT entry exists in harness's namespace |

Four-state classification for one MCP:

```python
def per_entry_status(adapter, scope, project_root, entry, allowlisted, installed_names):
    is_installed = entry.name in installed_names
    if not allowlisted:
        return "installed-not-allowlisted" if is_installed else None
    if not is_installed:
        return "unlinked-allowlisted"
    return "linked-drifted" if adapter.entry_drift(scope, project_root, entry) \
        else "linked-matches"
```

`installed_names` comes from `adapter.list_installed(scope, project_root)`. The JSON `target` field per cell:

- `linked-matches` / `linked-drifted` → path of the harness-config file/folder
- `unlinked-allowlisted` → `null`
- `installed-not-allowlisted` → path of the file holding the unmanaged entry

### Drift detection mechanics

Per Q3, structural equality is "parse → re-render through the same renderer, compare bytes."

#### ConfigFileAdapter drift

```python
def diff(self, scope, project_root, entries):
    target = self.config_target(scope, project_root)
    if not target.exists():
        full = self._build_full(entries)
        return [WriteAction(target, "create", None, len(self.render(full)))]

    current = self.read(target)
    desired = current
    desired_names = {e.name for e in entries}

    for entry in entries:
        desired = self.upsert(desired, entry)
    for managed_name in self._managed_names(current) - desired_names:
        desired = self.remove(desired, managed_name)

    bytes_before = target.read_bytes()
    bytes_after = self.render(desired)

    if bytes_before == bytes_after:
        return []                                    # [x] — fully aligned
    return [WriteAction(target, "update",
                        len(bytes_before), len(bytes_after))]
```

The key insight: we compare **rendered desired output** to **current file bytes**. If round-trip is deterministic, `render(parse(current))` equals current bytes. A hand-edit reordering keys inside a managed table makes rendered desired differ — that's drift.

`_managed_names()`: every `[mcp_servers.X]` whose `X` is in our allow-list. No markers. Aligns with the parent spec's "manage by name" rule. (Per spec rejection of fenced markers: a comment marker would let the user opt out by deleting the marker, which contradicts allow-list-as-sole-authority.)

#### PluginFolderAdapter drift

```python
def diff(self, scope, project_root, entries):
    target_dir = self.plugin_target(scope, project_root)
    desired = self.render(entries)
    actions = []
    seen = set()

    for path, content in desired.items():
        seen.add(path)
        if not path.exists():
            actions.append(WriteAction(path, "create", None, len(content)))
        elif path.read_bytes() != content:
            actions.append(WriteAction(path, "update",
                                       path.stat().st_size, len(content)))

    if target_dir.exists():
        for existing in self._owned_files(target_dir):
            if existing not in seen:
                actions.append(WriteAction(existing, "delete",
                                           existing.stat().st_size, None))

    return actions
```

`_owned_files()` = plain enumeration of files in `target_dir` (the plugin folder is owned outright).

#### `unlink` end-state for plugin_folder (per Q4)

After `unlink`, re-render with the entry removed:

- File would be empty (no `mcpServers` entries left) → delete the file.
- Plugin folder ends up empty *and* no other agent-toolkit-owned content remains in it → `rmdir` the folder.
- Other agent-toolkit content (skills/commands/agents from a future Claude plugin) still present → leave the folder; only the now-empty `plugin.json` (or equivalent) goes.

#### `entry_drift` per-entry semantics

`list` and `doctor` need per-entry, not per-file, drift. Implementation:

- ConfigFileAdapter: extract just `mcp_servers.<entry.name>` table from current → re-render that single table via the template renderer → compare to template render of `entry`. Bytes-equal = no drift.
- PluginFolderAdapter: same, on the per-entry rendered output (the per-entry slice of `render([entry])`).

### TUI integration

Per Q5, the TUI shells out via the existing `runner.CLIRunner.link_plan` / `unlink_plan`. No new write code in the TUI.

Three small, targeted edits:

1. **`_list_json.py` JSON contract**: replace `"unsupported"` overload for MCPs with the four real statuses. The `target` field becomes one of the values listed above.

2. **TUI widget status rendering** (`src/agent_toolkit_tui/widgets/`): expand the status switch to map `[x] [~] [ ] [!]` for MCPs. The literal `unsupported` case (e.g. claude+pi-extension cells) keeps the dash.

3. **TUI interactivity rule**: non-interactive iff `status == "unsupported"` OR `status == "installed-not-allowlisted"` (we never touch hand-rolled entries). Other three MCP statuses are interactive — clicking toggles allow-list membership, which triggers `link_plan` / `unlink_plan`.

#### Verification (test, not new code)

Integration test: TUI calls `runner.link_plan(scope="user", harness="codex", entries=[("mcp", "context7")])`, then `runner.list_state()` shows `linked-matches`. Round-trip via real CLI and adapter, no mocks.

#### Out of scope for TUI

- TUI does not call adapter methods directly.
- TUI does not call `doctor --group mcps`. Drift remediation from the TUI = clicking a `[~]` cell → triggers a `link_plan` re-write (which fixes drift as a side effect of `apply_link`'s reconcile semantics).

### Phasing and acceptance criteria

#### Content-PR — catalog migration to v1alpha2

In `~/GitHub/agent-toolkit`. Bumps every `apiVersion` from `v1alpha1` → `v1alpha2`. Adds `spec.mcp` blocks to all MCP READMEs. Lands before CLI-PR-1, but it does not need to validate against `agent-toolkit-cli@main` mid-flight — see "Catalog migration sequencing" above.

#### CLI-PR-1 — Codex proof + full wiring (this plan)

Schema replacement (v1alpha1 → v1alpha2 across all the files listed in the schema-bump section) + Protocol package + Codex adapter + dispatcher + list/diff/doctor/fix wiring + TUI integration test. Test fixtures (`tests/conftest.py`) migrate to v1alpha2 in this PR.

Codex is fully working at end of PR. Claude / OpenCode / Pi print `no MCP adapter for harness X yet — skipping` (loud) and exit 0.

Satisfies:

- AC #1, #2, #3 for Codex (link / re-link byte-identical / unlink leaves siblings intact).
- AC #4, #5, #6, #7 for Codex (list, diff, doctor, fix).
- AC #8 round-trip test for Codex.
- AC #9 (v1alpha2 schema, no v1alpha1 leftover).
- AC #10 (TUI MCP cells flow through CLI; integration test green).

#### CLI-PR-2 — Claude adapter

Phase 0 spike: empirical test of Claude plugin manifest's `mcpServers` loading.

- If it loads: `claude.py` implements `PluginFolderAdapter` only.
- If it doesn't: `claude.py` implements `ConfigFileAdapter` against `.mcp.json` (project) / `~/.claude.json` (user). This PR introduces the `--force` flag and the running-`claude`-process guard.

AC #1–#8 satisfied for Claude.

#### CLI-PR-3 — OpenCode adapter

Phase 0 spike: pick JSONC round-trip lib or accept comment-loss with documented warning.

AC #1–#8 satisfied for OpenCode.

#### CLI-PR-4 — Pi adapter

AC #1–#8 satisfied for Pi.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| `tomlkit` round-trip churn on real Codex configs | Phase-0 spike before Codex impl: byte-equal test against representative `config.toml` with `[notice.*]`, `[tui.*]`, comments. If churn, document and pin tomlkit. |
| OpenCode JSONC round-trip lib doesn't exist | Phase-0 spike. Fall back to plain `json` with `doctor` warning, *or* drop OpenCode comment preservation as accepted limitation. |
| Claude plugin manifest doesn't load `mcpServers` | Phase-0 empirical test in CLI-PR-2. Protocol design supports the fallback path without redesign. |
| Catalog `inner_config` shape varies across the 20+ MCPs | Discovered when migrating; each adapter's translation layer documents what it accepts and rejects via `can_install`. |
| `list` per-entry drift check is N adapter calls | Acceptable cost — each `entry_drift` call is a parse + re-render of one small table. Cache the parse if it shows up in profiles. |

### What this design rejects

Inherited from the parent spec: fenced markers, sidecars, single mechanism across all harnesses, sharing `.mcp.json` between Claude and Pi, broad substitution-syntax translation, custom IDs.

Additional rejections from this design's discussion:

- **Single fat Protocol with NotImplementedError stubs.** Two Protocols force adapters to declare what they implement; type-checker enforces completeness on the chosen strategy.
- **TUI calling adapters directly.** Two write paths (CLI subprocess for skills, in-process call for MCPs) violates "no parallel write logic."
- **Comment marker `# managed by agent-toolkit` inside config tables.** Lets users opt out by deleting the marker, contradicting allow-list-as-sole-authority.

## Acceptance criteria

A correct implementation, after all four PRs:

1. `agent-toolkit link <scope> <harness> mcps:context7` installs the MCP via the harness's preferred mechanism without printing or storing secrets.
2. Re-running the same `link` command produces byte-identical files on disk (deterministic render order: entries sorted by name, stable JSON/TOML serialisation).
3. `agent-toolkit unlink <scope> <harness> mcps:context7` removes only that named entry. Hand-rolled MCP entries with other names in the same file are byte-equal before and after.
4. `agent-toolkit list <harness>` shows MCP install state alongside skills/commands/agents using the four-glyph status `[x] [~] [ ] [!]`.
5. `agent-toolkit diff <scope> <harness>` shows would-be changes per file, no writes.
6. `agent-toolkit doctor` reports drift for MCPs whose installed entry differs structurally from the rendered template, and warns on missing env vars / prerequisites.
7. `agent-toolkit fix` reconciles drift to canonical form. No write when already in sync.
8. For each adapter, a round-trip test asserts: source file with comments + unknown sections + hand-rolled MCP entries → `link` an unrelated MCP → `unlink` it → byte-equal to source.
9. Schema-drift CI passes against the v1alpha2 schema. The v1alpha1 schema file is removed; no `apiVersion: agent-toolkit/v1alpha1` strings remain in the codebase or the migrated catalog.
10. The TUI's MCPs section reads via `_list_json` and writes via `runner.link_plan`/`unlink_plan`. No adapter imports inside the TUI package.

## References

- Parent spec: [`2026-05-04-mcp-management-design.md`](./2026-05-04-mcp-management-design.md).
- Plan A implementation plan: [`../plans/2026-05-04-mcp-foundations.md`](../plans/2026-05-04-mcp-foundations.md).
- Plan A landing commit: `d44a98f` on `main`.
- Walker MCP discovery rule: `src/agent_toolkit_cli/walker.py:24` (`("mcp", "mcps", "config.json")`) and `frontmatter_path()` at `walker.py:37`.
- No-op site to replace: `src/agent_toolkit_cli/commands/_link_lib.py:212-223`.
- TODO marker for status overload: `src/agent_toolkit_cli/commands/_list_json.py:160-179`.
- TUI write path: `src/agent_toolkit_tui/runner.py:99` (`_plan` method).
- Toolkit catalog: `~/GitHub/agent-toolkit/mcps/<name>/{config.json, README.md}` — 20+ entries as of 2026-05-04.

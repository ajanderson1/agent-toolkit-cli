# Codex `config_file` adapter for `[hooks]`

**Status:** spec draft — pending user approval, then implementation plan.
**Issue:** [#56](https://github.com/ajanderson1/agent-toolkit-cli/issues/56)
**Branch:** `feat/56-codex-config-file-hooks`
**Mode:** `--guided`

## Goal

Project toolkit hook assets onto a Codex CLI install by writing both the user-level `~/.codex/config.toml` `[hooks]` table **and** the executable scripts referenced from it. Round-trip clean, ownership-safe, parity-test passing.

## Why this is bigger than "merge `[hooks.<slug>]` blocks"

The original issue (#56) framed Codex hook installation as merging per-slug TOML tables (`[hooks.<slug>]`). Reading openai/codex#18893 (merged 2026-04-23, shipped in CLI 0.125.0) confirms that's not how Codex hooks work. Codex stores hooks under a single `[hooks]` table whose value is `HookEventsToml` — six per-event arrays-of-tables, each holding "matcher groups" with optional regex matchers and ordered `command` handlers:

```toml
[hooks]

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "/Users/aj/.codex/agent-toolkit-hooks/no-rm-rf/check.sh"
timeout = 10
statusMessage = "guard-rails"
```

There is no slug in the file. Identity in the file is by content (the handler `command` path, plus matcher), not by name. Two consequences:

1. The MCP adapter's "manage by name" ownership rule (every `[mcp_servers.X]` whose `X ∈ previously_allowed ∪ entries` is ours) does not apply. We need a different ownership rule.
2. One toolkit hook asset can register on multiple events, producing multiple table entries pointing at the same script. The mapping is asset → many entries, not asset → one block.

This spec resolves both points.

## Scope

In scope:

- Schema change: add `spec.hook` to v1alpha2, required when `kind: hook`.
- New adapter `CodexHookAdapter` (strategy `config_file+folder`) at `src/agent_toolkit/harness_adapters/codex_hook.py`.
- Kind-aware adapter registry: `get_adapter(harness, kind="mcp")`.
- Hook dispatcher `src/agent_toolkit/commands/_hook_dispatch.py`.
- Routing in `_link_lib.py` so hook kinds reach the new dispatcher.
- `_support.py`: `("codex", "hook")` becomes a supported pair under user scope.
- Matrix update: `codex/hook` cell flips to `config_file+folder → ...`; `codex/agent` cell stays unsupported with refined rationale.
- One in-repo demo hook asset under `tests/_fixtures/hook_assets/codex-demo/` for round-trip and TUI smoke tests.
- Round-trip tests, TUI smoke test, schema validation tests, parity-test extension.
- Closing comment on issue #56 with the agents-deferral rationale and a follow-up issue for the agents investigation.

Out of scope (named explicitly so reviewers don't ask):

- Project-scope `[hooks]` at `<cwd>/.codex/config.toml`. User scope only this PR; follow-up after empirical confirmation that Codex reads project-local `[hooks]`.
- `[agents]` adapter. Investigated, deferred to a follow-up issue with rationale; matrix cell stays "by design."
- `HookHandlerConfig::Prompt` and `::Agent` variants. Upstream stubs them as empty; toolkit ships `::Command` only.
- Migrating existing hook assets in the sibling `agent-toolkit` toolkit repo to declare `codex` in `spec.harnesses` and carry `spec.hook` blocks. That's a separate PR against that repo.
- Removing the `kind="mcp"` default on `get_adapter()`. Stays for backward-compat; follow-up.
- Codex `requirements.toml` (enterprise-managed hooks). Not part of the toolkit's projection model.

## Locked decisions (from brainstorming)

| # | Decision | Rationale |
|---|---|---|
| 1 | Add `spec.hook` block to v1alpha2 schema; bump both vendored copies atomically. | First-class fields beat sidecar TOML; lefthook's `schema-vendor-check` enforces the bump. |
| 2 | User scope only for this PR. | Project-scope `[hooks]` support in Codex unverified; ship the smaller, certain piece. |
| 3 | Defer `[agents]` adapter; matrix cell stays "by design" with refined rationale; follow-up issue filed. | `kind: agent` (markdown + frontmatter) doesn't fit Codex's `[agents]` (TOML config of named agent declarations). |
| 4 | Per-asset opt-in via `spec.harnesses`. | Existing assets unchanged; toolkit author decides. |
| 5 | Ownership rule = path-prefix on the handler `command`. | Content-addressable, robust to user edits; comment markers are fragile. |
| 6 | Vendor scripts under `~/.codex/agent-toolkit-hooks/<slug>/`. | One link operation materialises both the script and the TOML; path prefix is then trivially reliable. |
| 7 | New strategy `config_file+folder`. | Adapter does both — parity test gets a third allowed mechanism so the matrix accurately describes what runs. |

## Architecture (3-layer change)

### Layer 1 — Schema

`src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json` and the mirror at `schemas/asset-frontmatter.v1alpha2.json`.

Add `spec.hook` to the `spec.properties` block:

```json
"hook": {
  "type": "object",
  "required": ["events", "command"],
  "additionalProperties": false,
  "properties": {
    "events": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {
        "enum": ["PreToolUse", "PostToolUse", "PermissionRequest",
                 "SessionStart", "UserPromptSubmit", "Stop"]
      }
    },
    "command":        { "type": "string" },
    "matcher":        { "type": "string" },
    "timeout":        { "type": "integer", "minimum": 1 },
    "async":          { "type": "boolean" },
    "status_message": { "type": "string" }
  }
}
```

Add a parallel `allOf` clause forcing `spec.hook` when `kind: hook` (mirroring the existing `kind: mcp → spec.mcp` clause):

```json
{
  "if": { "properties": { "metadata": { "properties": { "kind": { "const": "hook" } }, "required": ["kind"] } }, "required": ["metadata"] },
  "then": { "properties": { "spec": { "required": ["hook"] } } }
}
```

`spec.hook` is optional at the schema root for non-hook kinds. Both vendored copies must be updated in the same commit; lefthook's `schema-vendor-check` enforces this.

### Layer 2 — Adapter base

`src/agent_toolkit/harness_adapters/base.py`:

- New dataclass `HookEntry`:
  ```python
  @dataclass(frozen=True)
  class HookEntry:
      name: str                        # asset slug
      events: tuple[str, ...]          # codex events to bind to (subset of the 6 known)
      command: str                     # absolute path the toml will reference (under script_root)
      matcher: str | None = None
      timeout: int | None = None
      async_: bool = False
      status_message: str | None = None
      script_files: dict[Path, bytes] = field(default_factory=dict)
  ```
- New Protocol `ConfigFileFolderAdapter`:
  ```python
  @runtime_checkable
  class ConfigFileFolderAdapter(Protocol):
      name: str
      strategy: Literal["config_file+folder"]

      def can_install(self, entry) -> None: ...
      def list_installed(self, scope, project_root) -> set[str]: ...
      def entry_drift(self, scope, project_root, entry) -> bool: ...
      def config_target(self, scope, project_root) -> Path | None: ...
      def script_root(self, scope, project_root) -> Path | None: ...
      def render(self, entries) -> dict[Path, bytes]: ...
      def diff(self, scope, project_root, entries, *, previously_allowed=frozenset()) -> list[WriteAction]: ...
  ```

The `ConfigFileAdapter` Protocol stays as-is (still keyed to `McpEntry` because the MCP adapter and its tests rely on it). The new Protocol is independent.

### Layer 3 — Adapter implementation

`src/agent_toolkit/harness_adapters/codex_hook.py`:

```python
class CodexHookAdapter:
    name: str = "codex"
    strategy: Literal["config_file+folder"] = "config_file+folder"

    _EVENTS = ("PreToolUse", "PostToolUse", "PermissionRequest",
               "SessionStart", "UserPromptSubmit", "Stop")

    def config_target(self, scope, project_root): ...
    def script_root(self, scope, project_root): ...   # ~/.codex/agent-toolkit-hooks/
    def can_install(self, entry: HookEntry): ...      # validates events, command non-empty
    def list_installed(self, scope, project_root): ...# scans script_root for slug dirs
    def entry_drift(self, scope, project_root, entry): ...
    def render(self, entries): ...                    # → dict[Path, bytes] for scripts
    def diff(self, scope, project_root, entries, *, previously_allowed=frozenset()): ...
```

`diff()` algorithm (one method, six steps):

1. Resolve `script_root` and `target = config_target`. If `target is None` (project scope without `.codex/`), return `[]`.
2. **Script side.** For each entry, expected script files come from `entry.script_files` (paths already absolute under `script_root/<slug>/`). Compare each rendered byte stream against the on-disk file. Emit `WriteAction(create|update)` for differences.
3. **Removal side.** List slug directories under `script_root/`. For each slug in `(previously_allowed | desired_names) - desired_names`: emit `WriteAction(delete)` for every file in `script_root/<slug>/` plus a `delete` for the dir itself.
4. **Config side.** `_read(target)` (or `TOMLDocument()` if absent). Find or create `[hooks]`. For each event in `_EVENTS`:
   - Walk the existing array-of-tables for that event. Drop every matcher-group whose `command` (in any handler) starts with `script_root/`. (The "managed" filter.)
   - Append matcher-groups for each entry that lists this event, in slug-sorted order.
5. Render the TOML, byte-compare against the original, emit one `WriteAction(create|update)` for `config.toml` if changed. Apply the trailing `\n\n` strip already used in `codex.py:146`.
6. Return the action list.

Invariants:

- Round-trip property: `diff(link) → write → diff(link) == [] → diff(unlink) → write → bytes-equal-to-original`.
- Hand-rolled hook entries (handler `command` not under `script_root`) are never modified.
- Script files are pure bytes — file mode is set by the dispatcher, not the adapter.

### Layer 4 — Dispatch + routing

`src/agent_toolkit/commands/_hook_dispatch.py`:

```python
def _build_hook_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[HookEntry]:
    """Resolve slugs → HookEntry by reading hooks/<slug>/.meta.yaml + script files."""

def apply_link(adapter, *, scope, project_root, entries: list[HookEntry], dry_run, stdout, previously_allowed=frozenset()) -> list[WriteAction]:
    """Like _mcp_dispatch.apply_link but typed for HookEntry; chmods 0o755 after script writes."""
```

Two real differences from the MCP dispatcher:

1. After every `create`/`update` `WriteAction` whose path lives under `adapter.script_root(...)`, apply `os.chmod(path, 0o755)`.
2. `_build_hook_entries` reads the script body from the toolkit-side `hooks/<slug>/<command-path>` and packs it into `entry.script_files`, keyed by the destination absolute path. The dispatcher is the boundary between toolkit source-of-truth and harness-projected output; the adapter never reads the toolkit dir.

The shared write-action engine (`_atomic_write_bytes`, `_print_pre`/`_print_post`) stays in `_mcp_dispatch.py` and is imported by `_hook_dispatch.py`. Extracting it into a third module is YAGNI for now; revisit when a third dispatcher arrives.

`src/agent_toolkit/harness_adapters/__init__.py`:

```python
def get_adapter(harness: str, kind: str = "mcp"):
    if harness == "codex" and kind == "mcp":
        return CodexAdapter()
    if harness == "codex" and kind == "hook":
        return CodexHookAdapter()
    if harness in {"claude", "opencode", "pi"}:
        return UnimplementedAdapter(harness)
    raise ValueError(f"unknown harness: {harness}")
```

`src/agent_toolkit/commands/_link_lib.py`: small dispatch table at the link entry point with three branches — `kind == "mcp"` → `_mcp_dispatch.apply_link` (existing path); `kind == "hook"` → `_hook_dispatch.apply_link` (new); every other kind (skill, agent, command, plugin, pi-extension) → existing symlink/translate path, unchanged. Existing call sites that pass no kind to `get_adapter()` continue to receive the MCP adapter (default).

`src/agent_toolkit/_support.py`: extend `_USER_TARGETS` (or whichever table feeds `SUPPORTED_PAIRS`) so `is_supported("codex", "hook", scope="user")` returns `True`. Keep `("codex", "hook", "project")` unsupported for PR1.

## Demo asset

`tests/_fixtures/hook_assets/codex-demo/`:

```
codex-demo/
  .meta.yaml
  check.sh
```

`.meta.yaml`:
```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: codex-demo
  description: Demo hook used by round-trip and TUI smoke tests.
  kind: hook
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses: [codex]
  hook:
    events: [PreToolUse]
    command: check.sh
    matcher: "^Bash$"
    timeout: 10
```

`check.sh`:
```sh
#!/usr/bin/env bash
echo "codex-demo PreToolUse hook" >&2
exit 0
```

Kept under `tests/_fixtures/` rather than `hooks/` because the toolkit-repo migration of real assets is its own PR.

## Tests

| File | Purpose |
|---|---|
| `tests/test_codex_hook_adapter.py` | `can_install` accepts the six known events / refuses unknowns. `diff` round-trip (link → write → re-diff empty). Unlink reverses to byte-equal original. Drift detection. Hand-rolled groups preserved. Multi-event entry produces one matcher-group per event. |
| `tests/test_tomlkit_roundtrip.py` (extend) | New fixture `tests/_fixtures/codex_config_realistic_with_hooks.toml`: representative `config.toml` with `[mcp_servers]`, `[hooks]`, comments, hand-rolled groups. Asserts `tomlkit.dumps(tomlkit.parse(...))` is byte-equal. |
| `tests/test_hook_dispatch.py` | `apply_link` writes script files atomically and chmods them `0o755`. Dry-run prints `would-create`. CannotInstall propagates. |
| `tests/test_tui_hook_integration.py` | Mirror of `test_tui_mcp_integration.py`: seed → `link_plan(scope="user", harness="codex", entries=[("hook", "codex-demo")])` → assert `list_state("codex", "user", "hook") == "linked-matches"` → confirm `~/.codex/config.toml` and `~/.codex/agent-toolkit-hooks/codex-demo/check.sh` both exist with expected bytes (and the script is `+x`). |
| `tests/test_harness_matrix.py` (extend) | Parity test handles `config_file+folder` mechanism. `get_adapter("codex", "hook")` returns `CodexHookAdapter` with `strategy == "config_file+folder"`. |
| `tests/test_schema_hook.py` | kind:hook with `spec.hook` passes; without fails with a useful message; unknown event in `spec.hook.events` fails. |

`uv run pytest -q` is the CI gate (per `.github/workflows/test.yml`).

## Matrix update

`docs/agent-toolkit/harness-matrix.md`, Codex column:

- `hook` row: `unsupported (by design) — Codex has no hooks API at the user level` → `config_file+folder → ~/.codex/config.toml [hooks] + ~/.codex/agent-toolkit-hooks/<slug>/`
- `agent` row: keep as `unsupported (by design)` with refined text: *"Codex's `[agents]` config surface (added in CLI 0.128.0) is for harness-internal agent declarations, not toolkit-shape agents (markdown body + frontmatter). Refined per #56."*

The parity test (`tests/test_harness_matrix.py:TestAdapterParity`) is updated in the same commit so it accepts the new `config_file+folder` mechanism and looks up the adapter via `get_adapter(harness, kind)`.

## `[agents]` deferral — issue closing comment

Posted as a comment on issue #56 before close (Step 12 of `flow`):

> **`[agents]` deferred.** Codex 0.128.0's `[agents]` section is a TOML config surface for declaring named agent definitions (model + system prompt + optional MCP wiring) — not a directory of markdown agents. The toolkit's `kind: agent` is a markdown body with frontmatter; the two shapes don't translate without a new `spec.agent.codex_translation` projection. Filing follow-up issue for that investigation. Matrix cell `codex/agent` keeps "unsupported (by design)" with refined rationale citing the config-surface mismatch.

Follow-up issue title: *"Investigate Codex `[agents]` projection from kind:agent"*.

## Risks & open questions

- **Schema migration impact.** Adding `kind: hook → spec.hook` required is a v1alpha2 change. No existing in-repo asset declares `kind: hook`, so no in-repo asset breaks. Sibling toolkit-repo assets that declare `kind: hook` without `spec.hook` will start failing schema validation when the next CLI release lands. The toolkit-author migration is a separate, explicit PR; flagged in the issue close comment.
- **Determinism of TOML output.** Slug-sorted entry order keeps the rendered TOML stable across runs. We rely on tomlkit preserving array-of-tables ordering — already validated by the existing `test_tomlkit_roundtrip` fixture; we extend that fixture rather than introduce new round-trip risk.
- **Symlink vs copy of vendored scripts.** PR1 copies bytes (simple, atomic). A follow-up could symlink to keep edits in the source toolkit repo live; out of scope here.

## Acceptance

- `uv run pytest -q` green.
- Lefthook `schema-vendor-check` green (both schema copies updated).
- `tests/test_harness_matrix.py:TestAdapterParity` green for the new `config_file+folder` mechanism.
- Manual: `agent-toolkit link --scope=user --harness=codex hook:codex-demo` writes `~/.codex/config.toml` `[hooks]` block and the script file with `0o755`; running `agent-toolkit link` again is a no-op (re-diff empty); `agent-toolkit unlink` returns the file system byte-equal to its pre-link state.
- Issue #56 closed with the agents-deferral comment; follow-up issue filed.

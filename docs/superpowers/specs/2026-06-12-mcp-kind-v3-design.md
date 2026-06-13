# MCP asset kind (v3) — design

Status: agent-ready
Date: 2026-06-12
Issue: #329
Plan: [`docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md`](../plans/2026-06-07-mcp-kind-v3-foundations.md)

> **Clean-start note (2026-06-12).** This spec describes the **v3 library-model**
> build and supersedes the v1-era MCP design docs, which were written against the
> deleted v2.3.0 architecture (walker, allow-list authority, catalog repo,
> `link`/`unlink`/`diff`/`fix`/`new` verbs, plugin-folder strategy). Those docs
> are retired under `docs/superpowers/_deprecated/`; do not read them as the design
> for this work. Everything below is the mechanism the plan implements.

## Problem

`agent-toolkit-cli` re-ported skills, agents, instructions, and pi-extensions
into the v3 per-kind architecture but **MCP (Model Context Protocol) servers are
missing** — they were a shipped capability in the v1 codebase and were deleted in
the v2.3.0 refold (#160). MCP must come back as a first-class, lock-driven,
four-harness asset kind, with the same verb surface every other kind has.

MCP is **config-injection-shaped, not folder-shaped.** Skills and agents project
by symlinking or copying a markdown file into a harness directory. An MCP server
has no file to project — it is a named entry (`command`, `args`, `env`) that must
be **injected by name into each harness's own native config file**
(`~/.codex/config.toml`, `.mcp.json`, `opencode.json`, Pi's MCP config), leaving
every other byte of that file untouched. The harness owns the file; we own one
named entry inside it.

## User story (what we are building toward)

> As a developer, I keep a local **library** of MCP servers at
> `~/.agent-toolkit/mcps/`. I `mcp add` a server **once** — from an npm, PyPI,
> docker, URL, or local-path source — and the toolkit resolves its current version
> and records the entry. Then I `mcp install` that server into any of my four
> harnesses (Claude Code, Codex, OpenCode, Pi) at global or project scope; the
> toolkit surgically injects one named entry into each harness's config, and the
> resulting config works natively **without the toolkit** (a committed `.mcp.json`
> works for any collaborator). `mcp update` advances a server to its latest version
> across everywhere I've installed it. `mcp uninstall` pulls one projection;
> `mcp remove` pulls it everywhere and forgets it. MCPs I added by hand or that a
> harness installed natively are shown as `[!] unmanaged` and never touched.

## The four principles

The whole design follows from these. They are the philosophy, decided.

1. **The library answers WHICH version; the scope answers WHERE.** A single library
   entry per slug is the one version authority. Per-scope version pinning (holding
   one project at an older version on purpose) is an explicit non-goal — the library
   entry is the source of truth, and `update` advances it everywhere reachable.

2. **Version is transparency, not enforcement.** `add`/`update` best-effort resolve
   the current version and bake it into the projected config (`pkg@1.4.2`), so
   projections are effectively pinned underneath — sidestepping the sticky-stale
   `npx`/`uvx` caches that make unpinned invocations neither reproducible nor
   reliably latest. Resolution **never blocks**: offline or tool-absent → entry is
   stored `floating` with a loud note, exit 0.

3. **Manage by name, and coexist.** The lock (`mcps-lock.json`) is a pure ownership
   registry — slug, harness, scope, source, resolved pin. Entries **not** in our
   lock are shown by `list` as `[!] unmanaged` and are never written to or removed.
   The lock replaces the v1 allow-list as the sole authority on what we manage. The
   harness config stays self-describing and works without the toolkit installed.

4. **Loud, atomic, reversible, fail-loud.** Every write announces itself
   (`→ writing <path>`). Every write is atomic (temp file in the same directory →
   `os.replace`). Round-trip parsers preserve every neighbour. Secrets / env-var
   references are written through **verbatim** — never read, prompted for, or stored.
   A cross-harness `apply` rolls back same-call projections if a later adapter fails.

## Mechanism

### The substrate: a local library, not a repo clone

MCP entries live in a **library at `~/.agent-toolkit/mcps/`** — the same substrate
position as `~/.agent-toolkit/skills/`. It is **not** a managed clone of any repo,
and there is **no catalog-repo prerequisite.** The library root derives from `home`
(`home / ".agent-toolkit" / "mcps"`); `resolve_toolkit_root()` / `_repo_resolution.py`
/ marker files are **not used by this kind at all**. Tests seed a tmp `$HOME`.

Entry layout, at the library root:

```
~/.agent-toolkit/mcps/
  <slug>/
    config.json          # the inner MCP server config: {type, command, args, ...}  (NO mcpServers wrapper)
    README.md            # human prose; NOT parsed for metadata
  <slug>.toolkit.yaml    # metadata sidecar: name, description, transport, install_method, env, pin
```

### `add` authors; it does not clone

This is the key divergence from `skill add`. A skill's upstream is a git repo, so
`skill add` **clones**. An MCP's upstream is a package / image / URL / path, so
`mcp add` **authors the entry directly** from source flags:

```
mcp add <slug> --npx|--uvx|--docker|--url|--local <source>   # global-only, no -p
```

`add` writes `<slug>/config.json` + `<slug>.toolkit.yaml`, then best-effort resolves
the current version (`npm view <pkg> version`; PyPI JSON API; docker tag, digest when
cheap; git HEAD SHA for `--local` repos) and bakes the pin into the entry. Resolution
failure → stored `floating`, loud note, exit 0. Re-`add` of an existing slug errors.

v1 sources: `npx`, `uvx`, `docker`, `url` (remote HTTP), `local` (existing dir).
Git-clone-and-build sources are deferred — `uvx --from git+url@ref` and
`npx github:owner/repo#ref` already cover pinned git sources via the package managers.

### Projection: config injection by name

`mcp install <slug> [--harness ...] [-g|-p]` projects a library entry into one or
more harnesses. Each adapter round-trip-parses the harness's native config, **upserts
or removes exactly one named entry**, and writes atomically. No file is ever owned
wholesale; no fences, no sidecars, no provenance markers in the harness file.

**Where projections always point** (per harness × scope — hardcoded in the adapter
`CELLS`):

| Harness | Global (user) | Project | Format |
|---|---|---|---|
| **claude-code** | `~/.claude.json` | `<project>/.mcp.json` | JSON (`mcpServers.<name>`) |
| **pi** | `~/.pi/agent/mcp.json` (honors `$PI_CODING_AGENT_DIR`) | `<project>/.mcp.json` (shared) | JSON (`mcpServers.<name>`) |
| **opencode** | `~/.config/opencode/opencode.json` | `<project>/opencode.json` | JSON (`mcpServers.<name>`) |
| **codex** | `~/.codex/config.toml` | `<project>/.codex/config.toml` | TOML (`[mcp_servers.<name>]`, via `tomlkit`) |

> **Pi targets — VERIFIED EMPIRICALLY (2026-06-13), open item now CLOSED.** Pi has
> **no native MCP**; MCP is provided by the **`pi-mcp-adapter` extension**
> (`npm:pi-mcp-adapter`). The earlier assumed cells (`~/.config/mcp/mcp.json` /
> `.pi/mcp.json`) were wrong at the mechanism level — empirical probes (`pi -p` with
> each path present) returned `NO_MCP_SERVERS`. The adapter reads a precedence chain:
> `~/.config/mcp/mcp.json` (shared, cross-host) → `~/.pi/agent/mcp.json` (Pi-global
> override) → `.mcp.json` (shared project) → `.pi/mcp.json` (Pi project override).
>
> **Decision (AJ):** the Pi cell uses (user) `~/.pi/agent/mcp.json` — the Pi-owned
> global override, honoring `$PI_CODING_AGENT_DIR/mcp.json` — and (project) the
> **shared `.mcp.json`** (the "standard" cross-host file, the SAME file claude-code
> targets at project scope). Consequences the adapters/facade MUST honor:
> 1. **Pi project scope and claude-code project scope write the SAME file** (`.mcp.json`).
>    The write is a name-keyed upsert into the shared `mcpServers` doc — installing for
>    pi and claude-code at project scope touches `.mcp.json` once, idempotently; `doctor`
>    and `list` MUST de-duplicate the shared file across the harnesses that read it
>    (no double-count).
> 2. **Pi MCP is adapter-gated.** Pi's "installed" sentinel checks for the
>    `pi-mcp-adapter` extension (`~/.pi/agent/npm/node_modules/pi-mcp-adapter`), NOT
>    merely `~/.pi/`. If the adapter is absent, skip the Pi user-scope write with
>    `"pi-mcp-adapter not installed; skipping pi"` (no silent-green-breakage). (Project
>    scope writes the shared `.mcp.json` regardless, since that file serves all hosts.)

The **rejected** alternative was a shim/launcher model (a stable
`agent-toolkit-cli mcp run <slug>` stub dereferencing the library at spawn) — rejected
as a single point of failure in every harness's session-spawn path. We write the **real
resolved command** directly so configs stay self-describing.

### Format-family preservation guarantees

- **TOML family (Codex / `tomlkit`):** byte-equality. A round-trip test asserts a
  config with comments + unknown sections + hand-rolled MCP entries survives an
  install-then-uninstall of an unrelated MCP byte-equal.
- **JSON family (Claude / Pi / OpenCode / stdlib `json`):** structural equality +
  preserved entry order. Byte-level preservation is not achievable with a whole-document
  JSON dump and is explicitly scoped out for this family.

### OpenCode translation

OpenCode's config shape differs (`command: [exe, ...args]`, `environment` key,
`{env:VAR}` substitution). The adapter translates mechanically and **refuses**
`${VAR:-default}` (default-value substitution it cannot faithfully represent) with a
loud error and a facade rollback — never a silent mistranslation.

### Write safety on `~/.claude.json`

`~/.claude.json` is a live state file Claude rewrites continuously. Before any
**global-scope claude-code write**, the facade checks for a running `claude` process
(`pgrep -x claude`, best-effort) and refuses with a clear message; `--force` bypasses.
Absent `.mcp.json` is created as `{"mcpServers": {}}`; a bare `{}` (or any doc missing
the `mcpServers` key) is normalised to that shape before upsert — never written through
as invalid bare `{}`, never short-circuited as a silent no-op on absence.

## The lock: `mcps-lock.json`

An **independent, versioned `McpLockEntry`** — deliberately NOT the shared `LockEntry`
(a per-harness projection list per slug does not fit its one-canonical-path shape), but
aligned for the bundle composite's future grouping field. Global scope:
`~/.agent-toolkit/mcps-lock.json`. Project scope: `<project>/mcps-lock.json`. Fields:
slug, harness, scope, `source` (install-method provenance), `pin` (resolved version at
install time). Tolerant read reserves the bundle ADR's grouping field.

## Verb surface

`add` · `install` · `uninstall` · `remove` · `update` · `list` · `status` · `doctor`.

- **`uninstall` is non-destructive; `remove` is destructive.** `uninstall` removes the
  harness projection only and leaves the library + lock entry intact. `remove` =
  uninstall-everywhere + drop the lock entry (library entry kept). (Project memory: a
  misnamed `uninstall -g` once `rmtree`'d the canonical store — this contract exists to
  prevent recurrence.)
- **`update <slug>`** (flagless, greedy): re-resolve → rewrite the library entry →
  re-upsert every projection in the GLOBAL lock and the CURRENT PROJECT's lock in one
  run, refreshing pins; per-scope `old → new` output. Other projects' locks aren't
  discoverable — they catch up on their next `update`/re-`install`; `list`/`doctor` flag
  the staleness meanwhile (`pin (library: X — stale)`).
- **Read verbs** (`list`/`status`/`doctor`) pass `read_only=True` → default to global
  outside a project. **Write verbs** default to project when a project lock is present.
  `add` is global-only (no `-p`).
- **`doctor` is read-only** — reports orphan projections, missing projections,
  structural drift, and env-var presence **by name only** (a leak test guards that no
  value is ever printed). It never writes.

## Out of scope (deferred to follow-ups)

`fix` (drift reconciliation) and `diff` (dry-run) verbs; `push` / `reset` / `import`;
git-clone-and-build sources; cross-machine library sync; the TUI MCPs section (#39);
schema bump to `v1alpha2` / `metadata.kind` discriminator; `verify:` command execution;
paste-JSON `ingest`; the full running-`claude` guard machinery (a minimal pgrep+`--force`
guard ships in this slice); cross-kind four-glyph `list` integration; **per-scope version
pinning**; **doctor-adopt of unmanaged entries** (#337 precedent).

## Acceptance criteria

1. `mcp add <slug> --npx|--uvx|--docker|--url|--local …` authors a library entry at
   `~/.agent-toolkit/mcps/<slug>/` with best-effort version resolution baked in;
   resolution failure stores `floating` with a loud note (exit 0); re-`add` errors.
2. `mcp install <slug> [--harness ...] [-g|-p]` surgically upserts one named entry per
   harness; secrets/env written through verbatim; harnesses not installed are warned and
   skipped (sentinel check), never silently `mkdir -p`'d.
3. Re-running `install` is byte-idempotent. TOML family byte-preserves neighbours
   (comments + unknown sections round-trip); JSON family structurally preserves with
   entry order intact.
4. `uninstall` is non-destructive (projection + lock entry only; library untouched);
   `remove` = uninstall-everywhere + no lock residue (library entry kept). Cross-harness
   `apply` rolls back same-call projections on a later-adapter failure; upserting over an
   unmanaged same-name entry warns loudly.
5. `mcp update <slug>` (flagless, greedy) re-resolves, rewrites the library entry,
   re-upserts every projection in the global lock AND the current project's lock,
   refreshes pins, prints per-scope `old → new` (or `up to date`); one run from inside a
   project converges both reachable scopes.
6. **install → uninstall round-trip leaves no orphan projection and no residual lock
   entry, at BOTH global and project scope.**
7. Absent `.mcp.json` created as `{"mcpServers": {}}`; bare `{}` normalised before upsert.
8. OpenCode translation refuses `${VAR:-default}` (loud error, facade rollback).
9. Global-scope claude-code writes guarded by a minimal running-`claude` check with
   `--force` bypass.
10. `list` shows library slugs + resolved version (or `floating`) + install state per
    harness×scope, flags stale pins, and surfaces native/manual entries as `[!] unmanaged`
    (never touched — survival tested); `status` prints the lock; `doctor` reports orphans,
    missing projections, structural drift, and env-var presence by **name only**.
11. Library `config.json` structurally validated at load (command:str, args:list[str],
    env:dict[str,str]).
12. The `mcp` command works from a **built wheel run outside the source tree** (#305
    guard; library root derives from `HOME`, no env vars needed).
13. `uv run pytest -q` green, lint clean, roadmap + README updated.

## References

- Plan (authoritative task-by-task): [`docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md`](../plans/2026-06-07-mcp-kind-v3-foundations.md)
- Bundle ADR (sequences this as step 1): [`docs/solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md`](../../solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md)
- Landscape survey: [`docs/solutions/tooling-decisions/cross-harness-plugin-bundle-landscape-2026-06-10.md`](../../solutions/tooling-decisions/cross-harness-plugin-bundle-landscape-2026-06-10.md)
- Architecture template: the `agent` kind (`agent_adapters/`, `agent_install.py`,
  `commands/agent/`) — closest sibling; the rollback precedent is
  `commands/instructions/install_cmd.py`.
- Retired v1 design (do not follow): `docs/superpowers/_deprecated/2026-05-04-mcp-management-design.md`,
  `docs/superpowers/_deprecated/2026-05-04-mcp-adapters-design.md`,
  `docs/superpowers/_deprecated/2026-05-04-mcp-foundations.md`.

# Roadmap

This page separates **shipped capabilities** from **unshipped ideas**. It is not a
release promise; the [CLI](cli.md), [TUI](tui.md) and [six asset guides](../index.md#asset-types)
describe current behavior. Historical specs, plans and research retain their
original context rather than being rewritten as current reference.

## Shipped baseline

- Source-backed Skills, Agents, Commands and Pi extensions, with distinct
  library/projection operations and per-kind support limits.
- Lockless Instructions: user-owned canonical content, actual filesystem pointer
  truth, source-chain guards and opt-in doctor adoption.
- MCP global library manifest, four concrete config adapters, project-only
  Standard, explicit legacy migration and cross-machine import. Bearer-token
  environment-name authentication is Pi-only.
- Local bundle manifests for Skills, Agents and Pi extensions, structural
  validation and rollback attempts; no durable bundle membership.
- TUI queues across six kinds and both scopes, aggregate Apply/Diff/Revert,
  source/ref skill collections of real children, guarded legacy exposure
  reconciliation, clean plural sidebar and emphasized repository path.

These do not imply every adapter is enabled, every scope is supported, or Apply
is a global transaction. See [compatibility](../matrix.md) and recovery limits.

## Unshipped ideas

### Auto-push of self-improvements

A possible opt-in session-end hook for owned-source improvements. No such hook or
`autoPush` behavior ships today. Hook placement and failure reporting remain open;
manual `skills push` is the supported publishing path.

### skills.sh global write-through

New toolkit locks use v1; existing v3 locks retain their schema/metadata. Default
v3 emission and interoperability beyond tested serializer behavior remain ideas,
not a promise that both installers share identical paths or ownership semantics.

### Hooks, plugins and durable bundles

Standalone hook/plugin kinds remain unshipped. Bundle uninstall, durable group
membership/drift diagnosis, remote manifest fetching and source/ref reachability
checks during validate remain deferred. Commands, Instructions and MCP are not
installable bundle members today. See [bundle limits](bundles.md).

### Verb remap: `enable`/`disable` for projection { #verb-remap-enable-disable-for-projection }

**Idea, not committed or implemented.** The proposal would rename the projection
axis from install/uninstall to enable/disable while retaining add/remove for
library membership. Compatibility aliases, clarity and migration cost would need
a separate decision. Current scripts must continue using shipped verbs.

### Other open questions

- Surface dirty owned content at session end without obscuring more urgent state.
- A convenience skill diff command (not currently shipped).
- Explicit handling of other installers' copied assets beyond supported bounded
  unmanaged discovery/confirmed import.
- Additional harness adapters only when placement, ownership and verification
  evidence justify them; researched support alone does not enable an adapter.

## Existing non-goals

- No automatic submission of private sources to the public skills.sh catalog.
- No subprocess wrapper around `npx skills`; the toolkit implements its own path.
- No automatic team-wide propagation of local self-improvements.

Distribution/versioning remains the repository's release workflow responsibility;
this roadmap does not announce an unverified publication or replace release notes.

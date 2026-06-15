---
name: agent-toolkit
last_updated: 2026-06-14
---

# agent-toolkit Strategy

## Target problem

Skills installed for one project silently bleed into others — an agent picks up
a skill in a project where it shouldn't be active (contamination), and once you've
locally modified a third-party upstream skill, the standard tooling treats your copy
as disposable, so your edits can't safely persist or be managed. Existing installers
solve getting skills onto disk; they don't give you per-scope control or durable local
ownership after that.

## Our approach

Treat every installed skill as a first-class, owned git repository rather than a
disposable vendored copy — so local edits to even third-party upstream skills are real
commits that merge with upstream instead of being clobbered, and granular per-skill,
per-scope control is something you own rather than something the installer hides. A
Textual TUI makes that control immediate and visual, so toggling and scoping a skill
is a glance-and-click, not a CLI incantation.

## Who it's for

**Primary:** A multi-harness agent power-user managing a personal library of assets
(skills, agents, instructions, pi-extensions, MCP servers) across many projects. They're
hiring agent-toolkit to decide exactly which assets are active in a given project before
turning an agent loose, and to safely keep their own edits to upstream third-party skills
— without hand-managing symlinks or risking cross-project contamination.

**Secondary:** A small team adopting the same library and workflow. Now a real driver, not
a deferred one — the bundle manifest makes a curated, reproducible asset set shippable to
someone who isn't the author, which is the bridge from one-machine dogfooding to public
adoption.

## Key metrics

- **Local edits survived an update** - `skill update` runs that merge local commits
  cleanly vs. clobber them or leave a mid-merge conflict. Regresses when git-native
  ownership leaks. Observed via `skill update` outcome; qualitative today.
- **Contamination incidents** - times an agent in a project picked up an asset that
  shouldn't have been active there. Target zero; any nonzero is a scoping failure.
  Qualitative, observed during agent runs.
- **Time-to-scope** - how long it takes to get a project to exactly the intended asset
  set (TUI glance-and-click vs. fighting symlinks). Qualitative / felt today.
- **Asset-kind × harness parity** - how many of the six asset kinds (skill, agent,
  instructions, pi-extension, mcp, bundle) have full verb support across each supported
  harness. Measurable from the projection/adapter matrix; regresses when a new kind or
  harness ships with partial coverage.

## Tracks

### Git-native ownership

Every skill is a real owned repo: merge-aware `update`, `push`-back-upstream, monorepo
parent clones, SHA-pin-vs-observed-tip in the lockfile, and the lock as single source of
truth driving projection to disk.

_Why it serves the approach:_ It **is** the bet — durable local edits and granular
control both fall out of treating skills as owned repos.

### TUI control surface

The visual asset grid that makes scoping and toggling instant across harnesses — one tab
per asset kind (skills, agents, instructions, pi-extensions, MCP).

_Why it serves the approach:_ Granular control is only valuable if it's a
glance-and-click — the TUI is the access half of the approach.

### Robustness & projection integrity

`doctor` across every kind, projection/lock reconciliation, and no-surprise defaults so a
stranger's machine survives the edge cases the author's never hits. The least-invested
corner historically, and the load-bearing work standing between today and a public release.

_Why it serves the approach:_ Ownership and scoping are only trustworthy if the
projection on disk provably matches the lock — robustness is what makes the bet safe to
hand to someone else.

### Cross-harness reach

Breadth of supported asset kinds and harnesses, `skill import`, cross-machine library
sync, and bundles as a shareable, reproducible asset set.

_Why it serves the approach:_ Makes the owned library portable and consistent everywhere
you run agents — and bundles are the bridge that lets the control and ownership model
reach a second person, not just a second machine.

## Milestones

- **v4.0.0 (2026-06-13)** - MCP asset kind (config-injection across claude/codex/opencode/pi),
  toolkit-native bundle manifest (install/validate), and the kinds→asset-types rename.
- **v4.1.0 (2026-06-14)** - MCP "standard" projection (canonical `.mcp.json`/`mcpServers`)
  and the MCP tab in the TUI asset-types sidebar.
- **Public release** - PyPI distribution + docs so someone who isn't the author can adopt
  it. Gated on the Robustness & projection integrity track, not a calendar date.

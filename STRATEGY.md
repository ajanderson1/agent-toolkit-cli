---
name: agent-toolkit
last_updated: 2026-05-27
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

**Primary:** AJ Anderson — a multi-harness agent power-user managing a personal library
of skills across many projects. He's hiring agent-toolkit to decide exactly which skills
are active in a given project before turning an agent loose, and to safely keep his own
edits to upstream third-party skills — without hand-managing symlinks or risking
cross-project contamination.

**Secondary:** A small team adopting the same library and workflow later. Named, but
not yet a design driver.

## Key metrics

- **Local edits survived an update** - `skill update` runs that merge local commits
  cleanly vs. clobber them or leave a mid-merge conflict. Regresses when git-native
  ownership leaks. Observed via `skill update` outcome; qualitative today, could be
  surfaced through `skill status` later.
- **Contamination incidents** - times an agent in a project picked up a skill that
  shouldn't have been active there. Target zero; any nonzero is a scoping failure.
  Qualitative, observed during agent runs.
- **Time-to-scope** - how long it takes to get a project to exactly the intended skill
  set (TUI glance-and-click vs. fighting symlinks). Qualitative / felt today.

## Tracks

### Git-native ownership

Every skill is a real owned repo: merge-aware `update`, `push`-back-upstream, monorepo
parent clones, and the lockfile that acts as single source of truth driving projection
to disk.

_Why it serves the approach:_ It **is** the bet — durable local edits and granular
control both fall out of treating skills as owned repos. Still fickle and being
hardened through active dogfooding; `doctor` / projection reconciliation is the
least-invested corner and the likely next area of work.

### TUI control surface

The visual skill grid that makes scoping and toggling skills instant across harnesses.

_Why it serves the approach:_ Granular control is only valuable if it's a
glance-and-click — the TUI is the access half of the approach.

### Cross-machine / cross-harness reach

`skill import`, cross-machine library sync, and breadth of supported harnesses.

_Why it serves the approach:_ Makes the owned library portable and consistent
everywhere you run agents, so control and ownership don't stop at one machine.

## Milestones

- **v3.0.0 refold** - reintroduce the subagent `agent` kind, managed the same
  git-native, scoped way as skills. No fixed date.
- **MCP support (potential)** - extend the same ownership and scope model to MCP
  servers. Exploratory; not committed.

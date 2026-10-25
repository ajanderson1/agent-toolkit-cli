# Skills

Skills are `SKILL.md` folders with optional references, scripts and supporting files. **Add registers library content; install makes it visible.** Canonicals are standalone Git checkouts or symlinks into shared parent checkouts; harness projections point to those canonicals.

- Global library: `~/.agent-toolkit/skills/`; global lock: `~/.agent-toolkit/skills-lock.json`.
- New project projections share the central library; project lock: `<project>/skills-lock.json`. Recorded legacy private stores remain usable. See [project backing and explicit migration](../agent-toolkit/project-backing.md).
- Standard visibility: `.agents/skills/<slug>` (project), `~/.agents/skills/<slug>` (global). Other harnesses use their catalog-specific slots.
- `AGENT_TOOLKIT_SKILLS_ROOT` relocates the skills library and associated state; it is not an override for every kind.

## Use

```bash
agent-toolkit-cli skills add owner/repo --skill my-skill
agent-toolkit-cli skills install my-skill --scope project --agents standard
agent-toolkit-cli skills status my-skill -p
agent-toolkit-cli skills uninstall my-skill --scope project --agents standard
```

Scope defaults differ by verb; add/remove/import are library-only. Read/update/push/reset/doctor scope depends on the skills project lock; install/uninstall default global except for detected Paperclip companies. [Exact flags and defaults](../agent-toolkit/cli.md#scope-and-target-selection).

## Optional shared Git catalog

Subscribe to one user-global Git catalog without downloading or enabling its skills:

```bash
agent-toolkit-cli skills catalog subscribe ssh://git@example-tailnet/org/skill-catalog.git --ref main
agent-toolkit-cli skills catalog list
agent-toolkit-cli skills list -g
agent-toolkit-cli skills catalog add my-skill
agent-toolkit-cli skills catalog enable my-skill --scope project --agents standard
agent-toolkit-cli skills check -g
agent-toolkit-cli skills catalog unsubscribe
```

`catalog add` acquires library content only; `catalog enable` also enables the
explicit scope/harness targets. Existing `skills add` and `install` are unchanged.
The subscription lives in `~/.agent-toolkit/config.json` under `skillCatalog`.
No subscription means the existing CLI/TUI behavior with no catalog network calls.

Each inventory load/explicit refresh reads a fresh catalog revision. If access
fails or its manifest is invalid, catalog-only entries are hidden with a warning;
no stale listing fallback is used. Downloaded library skills remain visible and
usable. Removing a listing or subscription never deletes content or disables it.

The catalog repository supplies `catalog.json` with `version: 1` and a `skills`
array. Entries have a unique `key`, `description`, Git repository `source`, safe
relative `path` (`.` for root), and optional branch/tag/commit `ref`. No payloads,
credentials or activation state belong in the catalog. Nested children use their
exact directory and existing shared-parent machinery. Matching source/path/ref
reuses a library row; names alone never authorize replacement. Existing catalog
provenance also retains that association when a listing's selector changes; the
changed selector is reported rather than acquired a second time. In subscribed
CLI inventory, global-only library candidates retain their actual global record
scope rather than being labeled as project registrations. Explicit catalog
acquisition records provenance, while browsing does not mutate library records.

Advertised siblings and acquired children from the same normalized Git repository
and configured ref share one expandable TUI collection. Child identity includes
its relative directory, not just its name. Expanding acquires nothing; selecting
children and applying acquires only those missing children before enabling them.
Parent All/None includes supported collapsed/filter-hidden members from the observed
set; later advertisements do not silently join a queued selection. Failed selected
acquisition leaves that collection/scope's enablement unchanged across its requested
harnesses. Safely acquired library content remains, and failed selections stay queued.
Other independent collections may succeed. Local-only controls keep working offline.

`skills check [SLUGS...] -g|-p [--json]` checks registered Git-backed
skills, whether added directly or through the catalog, against their recorded upstream selector without updating content. Results
are timestamped in a private `skills-update-checks.json` beside the global library
lock, including observations keyed to individual project backings. This cache is
not project configuration and is not transported when a project moves. Unequal
commits mean the upstream revision differs, not proof of ancestry or a change in
that particular monorepo child. Local changes are preserved. A failed check is
unknown; changed local HEAD/source makes an old result stale. Fixed commit pins
remain pinned. Checks use the recorded Git selector and do not require a catalog subscription or association.

TUI Info displays those observations and CLI guidance; the TUI does not check
skill upstreams automatically or apply updates. Use `skills update SLUG -g|-p`
where existing backing/scope support permits. Catalog refresh never changes an
acquired source or ref. Doctor distinguishes catalog availability from local
corruption; it never acquires, enables or updates because of a catalog listing.

Removing unused library content leaves its shared catalog advertisement available.
Disable consumers before deleting shared library backing: the existing library
Remove path does not enumerate or clean up project links and can leave them broken.
This collection feature does not redesign that deletion policy.

LiteLLM, well-known endpoints, multiple catalogs, automatic checks and automatic
source/ref adoption are deliberately outside this feature.

## Collections and ownership

Repository-wide add registers all real children (including a genuine root); explicit subpaths, `--skill NAME` or `--path PATH` select one. `--path` selects the recorded repository-relative directory even when its slug differs from its frontmatter name; `--path .` selects a real root. This is library-only registration and cannot be combined with `--source`, `--skill` or a source child selector. Absolute/traversal/escaping paths and conflicting source/ref/path/slug identities are refused; local Git repositories use `file://`. Parent checkouts are shared by source/ref under `skills/_parents/`. A TUI collection groups these real entries rather than introducing another kind or lock schema. Source-batch install uses persisted membership, not future upstream discovery.

Owned monorepo push commits only the selected child subpath and opens a PR by default; third-party read-only parents refuse push. Update merges the configured target without discarding edits. `skills reset SLUG -g --force` is explicitly destructive: it fetches, then restores the exact commit pin, peeled tag or latest fetched branch tip without changing the recorded ref. For a monorepo it discards local commits and tracked edits across the **entire shared parent**, including siblings. It does not run `git clean`; unrelated untracked files are not purged. CLI/TUI child clean/dirty states inspect only that skill's directory, while the TUI parent reports the whole checkout (including changes outside child directories). Repeated add preserves local work and does not advance the shared checkout. Legacy rootless wrappers reconcile only during targeted install/selection-changing Apply. Missing `SKILL.md` is unhealthy; unsafe root+nested exposure combinations refuse before writes. [Storage/Git deep dive](../agent-toolkit/skill-lock.md) · [Collection controls and recovery](../agent-toolkit/tui.md#skill-collections).

## Support and unmanaged inventory

The catalog supplies skill paths, not proof that every harness supports every other kind. Standard readers share a slot; `--agents all` selects detected harnesses, not all catalog rows. Paperclip is **company/project-only** and requires a detected company; global Paperclip is unavailable. Hermes profile homes use their profile-local skill directory. See the [generated harness pages](../matrix.md) for placement.

Bounded local discovery is observational. Discovered files remain usable where they are; the TUI labels them `local` and excludes them from individual/All/None toggles, moving, registration and deletion. Info shows the actual path and manual removal guidance, warning before permanent file deletion and distinguishing symlinks from their targets. Remove only the selected child, not a shared checkout. Doctor never registers discovered local entries, even with `--repair`; unrelated repairs, ordinary source registration and lock-file import remain unchanged. `--no-fix` does not write. Foreign destinations are not silently replaced. Explicit single-child copy fallback remains supported, but collections do not promise filtered copies or independent exposure for every loader.

Use [Commands](commands.md) for a lightweight reusable prompt; use a skill for a workflow needing richer content or support files.

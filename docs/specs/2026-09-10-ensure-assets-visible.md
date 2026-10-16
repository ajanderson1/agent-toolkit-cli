Issue: #515

# Ensure Untracked Assets Remain Visible

## Intent

Every active asset found in supported configuration or on-disk inventory locations must be visible in the TUI and auditable through the relevant doctor command. Discovery is observational: it must not silently convert an unmanaged asset into a managed one.

## Goals

- Represent local Pi filesystem packages without classifying them as registry packages.
- Build skill, agent, and command rows from lockfile entries plus discoverable on-disk assets.
- Represent discovered assets absent from the lock as `unlisted` and visibly untracked.
- Discover nested skills inside bundle directories and show both bundle and individual skills with stable identifiers.
- Offer explicit, lossless import repair for unmanaged skill and Pi-extension assets.
- Make global skill lock path resolution honor a caller-provided home directory.

## Safety and constraints

- Inventory reads do not mutate assets, settings, or lockfiles.
- Doctor reporting is high visibility; repair is explicitly opt-in and confirmed, with `--no-fix` remaining read-only.
- Unknown upstreams are recorded as local sources; never infer or invent a remote.
- Repair must preserve the source directory/config entry and be safe to repeat.
- Continue existing schemas and per-kind architecture; no broad refactor or new dependency.

## Acceptance

1. Pi inventory represents local filesystem packages as visible, unmanaged local-package entries, retaining precedence against existing npm/store-owned entries.
2. Skills, agents, and commands TUI rows union lock-backed and discoverable filesystem assets; unmanaged assets are visibly unlisted.
3. Skill bundles show bundle and nested skills with stable, distinguishable identifiers.
4. Skill and Pi-extension doctor audits identify unmanaged supported assets. Explicit confirmed repair imports locally without changing asset contents/config; `--no-fix` is read-only.
5. Global skill lock path honors an explicit home while preserving default/environment behavior.
6. Tests cover visibility, bundle IDs, package precedence, repair/decline/report-only, error safety, and sandboxed paths; full suite passes.

## Scope boundary

The requested doctor commands are `skill doctor` and `pi-extension doctor`. Do not expand repair mutation into Pi runtime settings; report settings-only entries, and only modify configuration if the established package import contract explicitly requires and can preserve unrelated settings.

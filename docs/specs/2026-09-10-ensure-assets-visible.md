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

- Inventory reads do not mutate assets, Pi settings, or lockfiles.
- Doctor reporting is high visibility. Repair is explicitly requested with `--repair` and separately confirmed; decline is non-mutating and `--no-fix` is strictly report-only.
- Unknown upstreams are recorded as local sources; never infer or invent a remote.
- Repair is additive, repeat-safe, and preserves source directory/config entry byte-for-byte. Do not adopt files or foreign symlinks implicitly; adopt/repair only after explicit product confirmation and never overwrite a foreign path.
- Do not mutate Pi `settings.json` for inventory or repair. Settings-only/unsupported entries that cannot be represented without loss stay unmanaged and reported.
- Continue existing per-kind schemas and adapters; no broad refactor or new dependency.
- Do not delete, move, rewrite, or adopt unmanaged source paths. Repair only records supported local paths in the existing lock representation after checking collisions and losslessness.

## Acceptance

1. Pi inventory represents local filesystem packages visibly as unmanaged local packages, retaining precedence of lock-backed npm/store-owned entries and preserving package metadata.
2. Skills, agents, and commands TUI rows union lock-backed and bounded filesystem discovery; unmanaged assets are visibly `unlisted`, with stable IDs and actionable existing harness cells where supported.
3. Skill bundles show bundle containers and nested skills independently with stable, distinct IDs (for example `superpowers:brainstorming`); directory and symlink discovery stays within defined roots, does not follow escaping symlinks, and handles dangling/colliding links safely.
4. Skill and Pi-extension doctor audits report unmanaged supported assets in report-only runs. Explicit `--repair` plus confirmation imports supported assets locally and additively, without changing asset contents/configuration; default decline is non-mutating, `--no-fix` always read-only, lock-write errors leave sources/settings unchanged, repeat repair is safe. Unsupported or lossy settings-only records remain reported and unmanaged.
5. `skill_paths.lock_file_path(scope="global", home=home)` honors explicit home while preserving environment override and default behavior.
6. Tests cover filesystem-union inventory states and visible badges, bundle IDs, package origins/metadata and ownership precedence, repair/decline/report-only/repeat/error safety, and home sandboxing.
7. Run the full suite only after #514 is merged and its isolation is present in the tested base. Validate on a disposable HOME and isolated toolkit/config paths with sentinels, verify real-user asset/settings paths are untouched, and capture automated headless TUI grid/pilot-visible-state assertions for unmanaged skills, agents, commands, and local Pi packages. No Pi settings mutation is allowed by inventory or repair.

## Scope boundary

The requested doctor commands are `skill doctor` and `pi-extension doctor`. Do not expand repair mutation into Pi runtime settings; report settings-only entries, and only modify configuration if the established package import contract explicitly requires and can preserve unrelated settings.

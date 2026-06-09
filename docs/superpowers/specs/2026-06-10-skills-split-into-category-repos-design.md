# Split `ajanderson1/skills` into category repos — design

- **Issue:** [#341](https://github.com/ajanderson1/agent-toolkit-cli/issues/341)
- **Date:** 2026-06-10
- **Tier:** deep (new top-level repos ×8; breaking change to every first-party skill's published `source`; release machinery ×8; secrets domain — `bitwarden` + tracked credential files)
- **Status:** design approved 2026-06-10; corrected 2026-06-10 after critical review (ce-doc-review, 6 personas) verified against code.

## Problem

`ajanderson1/skills` is a flat monorepo holding **31 tracked first-party skill dirs** at
its root (`<repo>/<slug>/SKILL.md`). One PR stream, one release line, one settings surface
span everything from `journal` to `apk-deep-audit`.

AJ wants **better-defined repos** and **granular per-category PR / release control**. The
chosen fix is to split the monorepo into **8 independent private GitHub repos**, one per
skill category.

### The premise, stated honestly (so the bet is deliberate)

The critical review correctly observed that **the repo boundary is invisible to the
consumer**: ownership is owner-keyed (not repo-keyed), `agent-toolkit-cli` resolves skills
by `(source, skillPath, ref)`, and the spec's own "no CLI change required" finding proves a
folder boundary and a repo boundary are functionally identical to the tooling. For a
SHA-pinned single consumer, per-category SemVer lines are **inert** — nothing downstream
reads them. So the split's value is **workspace-level, not consumption-level**:

- separate clones (a 2–7 skill repo is a clean small checkout, vs one 31-dir tree),
- separate issue trackers / PR lists / stars / visibility per category,
- a smaller blast radius for any single-category mistake.

AJ was shown the cheaper rejected alternative (subfolders-in-one-repo: ~80% of the value,
keeps git history, reversible via `git mv`, no breaking `source` change) and **chose
separate-repos for the workspace benefits, accepting the 8× standing maintenance surface and
the loss of per-skill history.** This spec records that as a deliberate, eyes-open bet — not
a capability gap.

### Hard constraint

The migration **must not strand or break any installed skill.** Every registered skill must
keep resolving, applying, pushing, and doctoring after the migration — from its new repo.

### Blast radius (confirmed)

Consumers = **this machine, AJ only**. No other machines, no external consumers. So no
deprecation/redirect strategy and no multi-machine portability requirement.

**But scope spans many locks, including outside `~/GitHub`.** First-party skills are
registered in the **global lock + ~13 project locks** (scanned `$HOME/**/skills-lock.json`,
excluding `.worktrees/`, 2026-06-10):

| lock | first-party entries |
|---|---|
| `~/.agent-toolkit/skills-lock.json` (global library) | 30 |
| `~/GitHub/projects/whatsapp_sync` | 8 |
| `~/GitHub/projects/agent-toolkit-cli` | 6 |
| `~/GitHub/contexts/servers` | 3 (incl. broken `servers`) |
| `~/GitHub/agent-toolkit/conventions` | 1 (broken `servers`) |
| `~/GitHub/projects/ryanair_fares` | 3 |
| `~/GitHub/projects/Scottish_Property_Analysis` | 3 |
| `~/Journal` (**outside `~/GitHub`**) | 1 (`pocketsmith`) |
| `~/GitHub/POC/claude-dispatches-pi-chatterboxes`, `~/GitHub/APK/third_party_apks` (+ `BankID`, `Swish`), `~/GitHub/projects/whatsapp_chat_autoexport`, `~/GitHub/projects/cornelius_explore` | 1 each |

The migration MUST re-discover this set at run time from **`$HOME`** (not just `~/GitHub`),
exclude `.worktrees/`, and **fail loud on any unparseable lock** — never silently skip.

## Architecture

Eight new **private** repos under `ajanderson1/`, each a flat monorepo
(`<repo>/<slug>/SKILL.md`):

| repo | skills (count) |
|---|---|
| `skills-workflow` | aj-flow, aj-issue, aj-run, aj-bootstrap, autonomous-run, project-manager, repo-recon (7) |
| `skills-orchestration` | cmux-pm, claude-orchestrated-pi-agents (2) |
| `skills-authoring` | agent-builder, skill-builder, conventions (3) |
| `skills-journal` | journal, journal-maintenance, learn-for-me, obsidian (4) |
| `skills-finance` | outgoings-admin, pocketsmith, bank-statement-download (3) |
| `skills-infra` | contexts, dev-server, kuma-uptime, domain-manager, mkdocs, pypi, bitwarden (7) |
| `skills-comms` | telegram, whatsapp-backup (2) |
| `skills-android` | android-driver, apk-deep-audit, apk-workbench (3) |

**Totals:** 31 mapped skills (= the 31 tracked dirs) across 8 repos.

Placement reasoning for the ambiguous calls: `cmux-pm`+`claude-orchestrated-pi-agents` →
own `skills-orchestration` (running *other* agents); `conventions` → `skills-authoring`;
`bitwarden` → `skills-infra` (secrets/infra); `bank-statement-download` → `skills-finance`;
`pypi` → `skills-infra` (release/publishing).

### Two known data-quality items the migration must resolve (not blindly map)

1. **`telegram-botfather` is a local-only untracked stray.** Verified: it is **not on
   GitHub** (404, absent from the repo tree) and has **no lock entry** — it exists only as
   `?? telegram-botfather/` in the local parent clone. So it is **not a repo/migration
   object**: it is migrated nowhere and is **deleted by a local `rm`** of the untracked dir
   during cleanup. There is no `DELETED_SLUGS` repo operation.

2. **`servers` is a broken lock entry, not a real skill.** Verified: there is **no
   `servers/` dir and no `servers/SKILL.md`** in the repo (404, empty tree) — yet a
   `servers` entry (`skillPath: servers`, `source: ajanderson1/skills`) is live in **two**
   project locks (`~/GitHub/contexts/servers`, `~/GitHub/agent-toolkit/conventions`). It is
   the known `servers`/`contexts` same-subtree dup (both `name: contexts`). The migration
   MUST re-point those two `servers` entries onto **`ajanderson1/skills-infra/contexts`**
   (the real skill), preserving the local slug `servers` via `--slug servers` so existing
   references keep working — i.e. `servers` is an **alias re-registration of `contexts`**,
   not a 32nd skill. This is why the live registered-slug set is 32 (`31 dirs + servers`)
   while the dir count and map are 31.

Each new repo is self-contained, carrying its own scaffolding: `LICENSE`, `README.md`
(regenerated), `AGENTS.md` (regenerated — see §skill-content updates), `lefthook.yml`,
`scripts/` (only if the category needs them), `.gitignore` (**new** — see §Security),
`version.txt`, and `release-please-config.json` + `.release-please-manifest.json` +
`.github/workflows/release-please.yml`.

**Git history:** fresh start per repo (initial commit = current sanitized skill state). The
original `ajanderson1/skills` is **archived** read-only after verification — history
preserved, nothing resolves from it.

## Key feasibility findings (verified in code)

1. **Ownership is owner-keyed.** `skill_ownership.py:12` `OWNED_OWNERS = frozenset({"ajanderson1"})`.
   Every new `ajanderson1/skills-<category>` repo is automatically owned — `--owned` implied,
   `skill push` targets the new repo, **no CLI code change required** for resolution.

2. **`skillPath` stays single-segment** (flat-at-root repos). The migrated entry keeps
   `skillPath: <slug>`; what changes is **`source`** (+ derived `upstreamSha`, `parentUrl`).
   Pass `--ref main` on re-register to preserve the existing `ref: main` shape (26/30 global
   entries have it; bare `add` would normalize to `ref: null` — functionally OK via
   `resolve_ref`, but pass `--ref main` to avoid lock churn).

3. **`skill add` / `skill remove` are GLOBAL-ONLY (critical correction).** Verified: neither
   has a `-p`/`-g`/`--scope` flag; both always write the global library lock and ignore cwd.
   **Therefore project-scope re-registration CANNOT use `cd <project> && skill remove/add`.**
   The correct project-scope verbs are `skill uninstall <slug> -p` (drops the project lock
   entry — confirmed non-destructive at `__init__.py:~666`) then `skill install <slug> -p
   --agents <prior>` (re-derives the entry from the **global** lock via
   `ensure_project_canonical`). This imposes a hard **global-first phase ordering**.

4. **release-please is whole-repo** (`release-type: simple`, single `"."` package, default
   `GITHUB_TOKEN` with inline `permissions:` — no PAT/secret needed; fresh repos work). Each
   new repo gets the config but with **per-repo `package-name`** and a **deterministic
   starting version** (see §Open execution decisions).

## Migration mechanism (corrected — global-first, then per-scope)

Move-only is forbidden. The migration runs in **two ordered phases**:

**Phase A — global library (do ALL 31 slugs first).** For each mapped slug:
- ensure target repo exists + pushed (see plan Task 6).
- `agent-toolkit-cli skill remove <slug> --force` (global; `--force` for non-TTY).
- `agent-toolkit-cli skill add ajanderson1/skills-<category>/<slug> --owned --ref main`.

  *Note:* a few slugs (e.g. `apk-workbench`) exist **only at project scope**, not in the
  global library today. The migration must `skill add` them to the global library as a
  **prerequisite** so Phase B can re-derive them; decide afterward whether to drop the new
  global entry or keep it.

**Phase B — project scopes (only after Phase A is complete).** For each (slug, project lock):
- capture the slug's prior `--agents` set from the project lock **before** changing it.
- `( cd <project> && agent-toolkit-cli skill uninstall <slug> -p --agents all )`.
- `( cd <project> && agent-toolkit-cli skill install <slug> -p --agents <prior> )` — pulls
  the new `source` from the now-migrated global lock.
- For the two `servers` entries: `skill install contexts -p --slug servers` (alias re-point).

**Apply path is transactional + fail-loud.** The migration script implements `--apply` (not
a stub): per slug, **create+verify the new source resolves before any remove**, and on any
failure **re-add the old source and abort the whole run**. The lock-JSON snapshot alone does
NOT restore filesystem state (symlinks, parent clones); recovery leans on the still-live
archived old repo + the abort-on-first-failure contract. **Precondition: no active agent
sessions during the run** (remove unlinks projections before add/install recreates them).

A single **idempotent, dry-runnable** script driven by the slug→repo map is the deterministic
path. Idempotency gate: a second dry-run reports **zero actions** — valid only because
discovery is `$HOME`-wide and fail-loud (see Blast radius).

## Security (new section — critical-review finding)

**Verified real exposure in the CURRENT monorepo:** `bank-statement-download/references/credentials.md`
and `learnings.md` are **git-tracked** and contain real Bitwarden vault item UUIDs, a full
name/email/phone, and bank account numbers. Fresh-history does **not** sanitize them — they
would re-ship into `skills-finance`. **AJ chose: sanitize before migrating.** The migration MUST:

1. **Pre-copy scan gate.** Before populating any repo, scan each skill dir for
   `references/credentials.md`, `references/learnings.md`, and UUID/account-number patterns;
   **halt for human confirmation** of what will be published.
2. **Move secrets out of source.** Relocate the live vault UUIDs/account numbers into
   Bitwarden itself (or a gitignored local file); leave only non-secret instructions in the
   skill. Fix the existing exposure as part of this work.
3. **Add `.gitignore` to every new repo** (the source `.gitignore` is NOT in the verbatim
   scaffold list) covering at least `credentials.md`, `learnings.md` (where secret-bearing),
   `__pycache__/`, `*.pyc`, `.DS_Store`. Copy skill dirs with **`git archive`** (respects the
   source `.gitignore`) rather than `cp -R` (which would commit untracked `.pyc` bytecode).
4. **Visibility hard-check.** Every `gh repo create` MUST pass `--private`; verify each repo's
   visibility (`--json visibility`) after creation — a public repo with `credentials.md` is an
   immediate exposure.
5. **Branch protection is unavailable** on free-tier private repos (verified: the source
   repo's protection endpoint returns 403 "upgrade to Pro"). So there is **nothing to
   replicate** and the new repos will have none. Accepted mitigation: repos stay private; the
   single local token is the only push credential; `skill push` always uses PRs. Convention:
   **never force-push `main`; use revert commits.** (Retrofit protection if GitHub Pro is
   obtained.) Do NOT leave a false "replicate protection" expectation in the plan.

## Skill-content updates (new — feasibility finding)

`skill-builder` (→ `skills-authoring`) and several skills hardcode `ajanderson1/skills` and
the `_parents/ajanderson1/skills/` clone path as a **build/working target** (e.g.
`skill-builder/SKILL.md`, `skills/AGENTS.md`, `cmux-pm/README.md`, and working-clone refs in
`contexts`, `journal`, `journal-maintenance`, `obsidian`). After the split there is no single
default monorepo. The migration MUST include a task to update these references (at minimum:
`skill-builder` must ask which category repo to author into). This is skill **content** work,
not CLI code — but it IS a real consumption gap the "no CLI change" finding doesn't cover.

## Open execution decisions (settle in the plan)

- **Starting version per repo:** the source manifest is `{".":"0.1.0"}`. Pick ONE: reset all
  new repos to `0.0.0`, or carry `0.1.0`. Do not both "verbatim-copy" and overwrite to
  `0.0.0` (the prior plan contradicted itself). Set `package-name` per repo. Seed
  `bootstrap-sha`/`Release-As:` so the first release version is deterministic; assert the cut
  version in verification.

## Testing strategy

- **Per-repo resolution:** ≥1 moved skill from a representative repo loads + applies in a
  fresh session, resolving from its new `source`.
- **`skill push` round-trip:** `skill push <slug>` for ≥1 moved skill opens a PR against the
  **new** repo.
- **`skill doctor` clean:** zero findings for every moved slug — global + each affected project.
- **Lock assertions:** each migrated entry shows `source: ajanderson1/skills-<category>`,
  single-segment `skillPath`, `ref: main`, refreshed `upstreamSha`/`parentUrl`; **no entry
  anywhere (incl. `~/Journal`, excl. `.worktrees`) still has `source: ajanderson1/skills`**.
- **Unmapped-slug guard:** a test asserts `registered_first_party_slugs($HOME) - {alias:servers}`
  equals the map's slug set — any future unmapped slug fails the suite (fail-loud, not skip).
- **CLI suite green;** monorepo/nested source-parse tests still pass.
- **release-please:** verify **all 8** repos cut a release (or downgrade the DoD to "workflow
  present + valid" — pick one; don't claim "cuts a release" while checking only 3).

## Definition of done

- [ ] 8 repos created **private** (visibility-verified) + populated (via `git archive`,
      sanitized) + pushed `main`.
- [ ] Phase A: all 31 slugs re-registered in the global library (`source` updated, `ref: main`).
- [ ] Phase B: every project lock re-registered via `uninstall -p`/`install -p` with prior
      `--agents` preserved; the two `servers` entries re-pointed to `skills-infra/contexts`
      (`--slug servers`).
- [ ] **No lock anywhere under `$HOME` (excl. `.worktrees`) still references `ajanderson1/skills`.**
- [ ] Secrets sanitized: `credentials.md`/`learnings.md` scrubbed + gitignored; pre-copy scan
      gate ran; no secret-bearing file in any new repo.
- [ ] `telegram-botfather` local untracked dir removed.
- [ ] `skill doctor` clean — global + each affected project — zero findings for moved slugs.
- [ ] ≥1 moved skill loads + applies in a fresh session; `skill push <slug>` round-trips.
- [ ] `aj-workflow` + all third-party skills untouched and still resolving.
- [ ] skill-content monorepo references updated (`skill-builder` + the working-clone refs).
- [ ] All 8 repos' release-please valid + deterministic first version (or DoD downgraded).
- [ ] `ajanderson1/skills` archived (read-only) after the above pass.
- [ ] CLI test suite green; unmapped-slug guard present.

## Non-goals

- **No CLI code change for resolution** (owner-keyed ownership + flat-at-root cover it). Skill
  *content* updates (above) ARE in scope — they are not CLI code.
- **Not reorganising third-party skills**, and not moving `aj-workflow` (separate repo).
- **Not preserving per-skill commit history** in new repos (archived monorepo retains it).
- **Not building a redirect/deprecation layer** (single-consumer blast radius).
- **Not obtaining GitHub Pro / branch protection** in this pass (accepted-risk, documented).

## Superseded design

The original #341 write-up proposed **category subfolders inside one repo**
(`<repo>/<category>/<slug>/SKILL.md`, multi-segment `skillPath`, no new repos, history
preserved, reversible). The critical review judged it the cheaper/safer option (~80% value).
AJ re-confirmed separate-repos (2026-06-10) for the workspace benefits. The subfolder runbook
is preserved in the issue body under a collapsed "Superseded design" note for the record.

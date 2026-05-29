# Decision: `extensions[]` explicit-path classification for `pi-extension` (PR2)

- **Date:** 2026-05-30
- **Status:** Decided (auto-decidable; one fact AJ/PR2 must re-verify — see Caveat)
- **Milestone:** v3.2.0
- **Resolves:** §11 item 3 of `2026-05-29-pi-extension-kind-design.md`
  ("`extensions[]` (explicit-path) surface — open, low-stakes").
- **Scope:** classification rule for inventory + how PR2's write verbs treat
  `extensions[]`. READ-ONLY analysis; no `src/` or test changes.

---

## THE QUESTION

Pi's `settings.json` carries **two distinct per-scope arrays** (design §2):

- `packages[]` — registry/git refs (`npm:<spec>`, `git:<url>`) Pi resolves into
  its own npm dir. PR1 reads these; modelled as **registry-tracked** rows.
- `extensions[]` — described by the v3.2.0 design (§2) as **explicit local
  file/dir paths**, hand-authored by the Pi user, relative entries resolving
  against the scope base dir (`~/.pi/agent` global, `<cwd>/.pi` project).

PR1's `_pi_settings.py` reader reads the `extensions/` **directory**
(symlinks + loose `.ts` + `index.*` dirs + `package.json`-manifest dirs) and
both `settings.json` arrays. PR1 exposes `extensions[]` via
`read_extension_paths()` but the inventory builder (`build_inventory`) does
**not yet consume it** — that is the gap PR2 closes. PR2 must decide:

1. How is an `extensions[]` entry **classified** in the inventory?
2. How do PR2's write verbs (`install` / `uninstall` / `import` / `remove` /
   `doctor`) **treat** it — observe-only, or manage (add/edit/remove entries)?
3. When the toolkit adopts a store-owned extension, does it project via a
   **symlink into `extensions/`** (PR1's verified mechanism) or by writing an
   **`extensions[]` entry**?

---

## CAVEAT THE PR2 BUILDER MUST RESOLVE FIRST: the two specs disagree on what `extensions[]` *is*

This is the single most important finding of this analysis and it must be
re-verified before PR2 writes the classifier:

- **The v3.2.0 design (`2026-05-29`, targets Pi `0.77.0`) §2** says `extensions[]`
  is a list of **explicit local file/dir paths** — i.e. an *additive source* of
  extensions Pi loads by path.
- **The prior-gen #109 spec (`2026-05-19`, targeted Pi `0.75.3`,
  `feat/109-pi-settings-extensions-array`, PR #116 MERGED)** opens with an
  explicit **"premise correction"**: reading Pi's `dist/core/package-manager.js`
  showed `extensions[]` is in fact an **enable/disable override list** (a
  *filter* over already-auto-discovered extensions): plain entry =
  include-filter, `!entry` = exclude, `+entry` = force-include, `-entry` =
  force-exclude. It is NOT a list of paths-to-load. The shipped code reflects
  this: `_pi_overrides.is_enabled(...)` + the doctor "orphaned override" check.

These are materially different. Between `0.75.3` (#109, verified by source read)
and `0.77.0` (v3.2.0 design), the loader was rewritten (the design itself notes
project-first ordering reversed in 0.77.0). It is **plausible but unconfirmed**
that `extensions[]` semantics also changed from override-filter → path-list.
**The v3.2.0 design's "explicit local file/dir paths" claim is the one assertion
in §2 that is not backed by a cited `package-manager.js` line** (contrast the
`packages[]` claims, which cite `:673-676`, `:591-596`).

**Required PR2 action:** before writing the `extensions[]` classifier, re-read
`@earendil-works/pi-coding-agent@0.77.0` `dist/core/package-manager.js` to
confirm which semantics 0.77.0 actually has. The recommendation below is written
to be **safe under either reading** — but the inventory *rendering* differs:

- **If `extensions[]` is a PATH-LIST (0.77.0 design reading):** entries are an
  additive load source → classify as in the Resolution below (untracked/loose,
  importable).
- **If `extensions[]` is an OVERRIDE-FILTER (#109 reading still holds):** entries
  are NOT their own rows at all; they flip `enabled` on existing
  auto-discovered/store-owned rows. The toolkit should reuse the already-shipped
  `_pi_overrides`/`enabled` model, not invent `local:<path>` rows. The *write*
  rule (never mutate `extensions[]`) is **identical** either way.

The Safety section below holds under both readings and is the load-bearing part
of this decision.

---

## RECOMMENDED RESOLUTION

**Treat `extensions[]` as observe-only and never-managed. The toolkit's sole
projection channel for store-owned extensions is the symlink into `extensions/`
(PR1's verified mechanism). PR2 must never write, edit, or remove an
`extensions[]` entry.**

Classification of `extensions[]` *entries* depends on the Caveat:

**Under the path-list reading (the design's stated 0.77.0 model):**

For each `extensions[]` entry, per scope (global `~/.pi/agent/settings.json`,
project `<cwd>/.pi/settings.json`):

- Resolve the path against its scope base dir (per §2) and
  **realpath-canonicalize** it.
- **If it canonicalizes onto a path the toolkit already owns** (a store symlink
  target / same realpath as a store-owned row) → **fold into that store-owned
  row** (dedup; no second row). Pi's own dedup keys on realpath (§2), so this
  matches Pi and prevents a phantom duplicate.
- **Else** → classify as **`untracked` (loose)**, `Source = local:<path>`, row
  capability = **importable** (`import` adopts it into the store). This is the
  same `untracked` state §5 already defines for loose `extensions/` entries; the
  only addition is the `local:<path>` source label + "discovered via
  `extensions[]`" provenance for the `doctor` hint.
- **If the resolved path is absent on disk** → still surface as `untracked` but
  flagged `missing`/orphaned; `doctor` *reports* (never auto-removes — see
  Safety).

This adopts the design's own §11-item-3 **default** ("treat as
untracked-importable for symmetry with loose `extensions/` entries"), hardened
into a rule, plus the realpath-dedup refinement. The prior-gen #109
`source = local:<path>` *tracked-row* alternative is rejected as a classification
target: "tracked" implies a managed write channel the store-owns rule argues
against. Keep `local:<path>` only as a **source label on an untracked row**.

**Under the override-filter reading (#109 semantics still hold in 0.77.0):**

Do **not** create rows from `extensions[]`. Reuse the shipped `_pi_overrides`
model: each entry flips `enabled`/`disabled` on the corresponding
auto-discovered or store-owned row, and `doctor` keeps the existing "orphaned
override" advisory. No `local:<path>` rows are invented.

**Write-verb behaviour (identical under both readings):**

| Verb | Behaviour toward `extensions[]` |
|---|---|
| `install <slug>` | Project store-owned via **symlink into `extensions/`** only. **Never** add an `extensions[]` entry. |
| `uninstall <slug>` | Remove the **toolkit-owned symlink** only. **Never** touch `extensions[]`. |
| `import` | May **adopt** the dir an `extensions[]` entry points at *into the store* (clone/copy → owned repo + lock + `piExtensionPath`), like a loose dir. It **must not delete or rewrite** the user's `extensions[]` entry; entry + new store symlink can coexist (Pi's realpath dedup tolerates it). |
| `remove <slug>` | Drop the store copy + lock entry (dirty-guarded). Touches only toolkit-owned artifacts; **never** `extensions[]`. |
| `doctor` | **Reports** orphaned/missing `extensions[]` entries (per §6) + store-vs-projection drift. **Report-only** for `extensions[]`; no auto-fix that mutates it. |

`packages[]` write behaviour is unchanged from the design (§3, §6): the toolkit
**does** add/remove `packages[]` for npm rows — that is the agreed projection
channel for the registry-tracked category. The asymmetry is intentional
(justified below).

---

## WHY

**1. "The store owns what it can genuinely own" (§3) → symlink-only projection.**
The store *can* own a git/local extension and *can* own a symlink it minted in
`extensions/`. It **cannot** own an `extensions[]` entry: that array is a
hand-authored user config surface (a path the user typed, or — under the #109
reading — an enable/disable filter the user authored). Writing into it makes the
toolkit a co-author of a file it doesn't own. PR1 **verified** the symlink
channel loads identically to a hand-placed extension (§2 conclusion), so there is
**no functional need** for an `extensions[]` write channel — symlink-in-
`extensions/` already delivers full projection. A second channel would be the
"parallel tracked-path channel" the design explicitly says it prefers to avoid
(§11 item 3).

**2. The spec's own default already leans here** (§11 item 3:
"treat as untracked-importable for symmetry with loose `extensions/` entries").
This decision adopts and hardens that default.

**3. The config-mutation caution precedent — the deferred/disabled cells.** The
project has a demonstrated reluctance to mutate harness config files it doesn't
fully own. The Codex `[hooks]` work (`2026-05-05-codex-config-file-hooks`)
deliberately kept the Codex **`[agents]`** adapter **deferred ("by design")**
rather than rewrite a user-authored TOML config surface whose shape the toolkit
doesn't own; and per the project's recorded OpenSpec comparison, an independent
tool (Fission-AI/OpenSpec) *also* refused Codex `config.toml` mutation —
cross-validating that stance. `extensions[]` is the same hazard class: a
user-authored array inside a harness config file, where a removed/reordered entry
silently changes what Pi loads (and under the #109 reading, *silently re-enables
or disables* extensions). Symlinks are the opposite: toolkit-minted artifacts in
a toolkit-managed dir, trivially reversible and self-evidently ours. **Keep
`extensions[]` on the observe-only side of that line.** Note the shipped #109 PR
already chose exactly this ("no toolkit edits to `extensions[]`, out of scope" —
#109 §3.5/§4.7) — so observe-only is the *existing, shipped* posture, not a new
constraint.

**4. Justified asymmetry vs `packages[]`.** The toolkit *does* write `packages[]`
because it is the **only** projection channel for the npm category (npm
extensions aren't stored, so no symlink alternative exists — §3/§10), and the
entries it writes there are toolkit-minted refs it added on `install`, not
hand-authored content. `extensions[]` has a sufficient, lower-risk alternative
(the symlink), so it gets the conservative treatment. One principle ("write the
projection the harness reads") applied to whichever channel is both *sufficient*
and *lowest-risk* per category.

---

## WHAT PR2 SHOULD DO WITH `extensions[]` (summary)

1. **First, re-verify 0.77.0 semantics** (path-list vs override-filter — see
   Caveat). This selects the inventory *rendering*; it does not change the write
   rules.
2. **Read-only-observe** `extensions[]` (both scopes) in the inventory builder
   (`build_inventory` currently ignores the value `read_extension_paths()`
   already returns).
3. **Classify** per the applicable reading: path-list → fold-onto-store-owned
   else `untracked`/`local:<path>`/importable (+ `missing` flag); override-filter
   → reuse `_pi_overrides` `enabled` flips, no new rows.
4. **Adopt via `import`** into the store like a loose dir — **without** deleting
   or rewriting the user's `extensions[]` entry.
5. **Project store-owned via SYMLINK into `extensions/`** — **never** by writing
   `extensions[]`.
6. **`doctor` reports** orphaned/missing `extensions[]` entries; report-only.

---

## SAFETY — what PR2 must NEVER do to a user's `extensions[]` (holds under both readings)

1. **Never add** an `extensions[]` entry (projection is symlink-only).
2. **Never remove** an entry — not on `uninstall`, `remove`, `import` adoption,
   or as a `doctor` auto-fix. Missing/orphan entries are **reported**, never
   deleted.
3. **Never edit/reorder/rewrite** an existing entry (no path normalization, no
   relative→absolute rewrite, no dedup-by-deletion, no stripping of `!`/`+`/`-`
   prefixes under the override reading). The `_pi_settings.py` writer (PR2)
   touches **`packages[]` only**; any read-modify-write must **preserve
   `extensions[]` and all unknown keys byte-for-value** (design §8 "preserve
   unknown keys").
4. **Never cross scopes** (§8): global → `~/.pi/agent/settings.json`, project →
   `<cwd>/.pi/settings.json`; never read one scope's `extensions[]` and write it
   into the other.
5. **Fail loud, don't silently rewrite** (§8): malformed `settings.json` raises;
   the writer never "repairs" `extensions[]` to make a write succeed.

---

## CONFIDENCE

**High on the write rule (observe-only, never mutate `extensions[]`; symlink-only
projection).** It is the spec's own default (§11 item 3), the load-bearing §3
"store owns what it can own" rule, PR1's verified symlink projection (removing any
need for an `extensions[]` write channel), the established config-mutation caution
(Codex `[agents]` deferral + OpenSpec cross-validation), AND the *already-shipped*
#109 posture ("no toolkit edits to `extensions[]`"). All five point the same way.

**Medium on the inventory *rendering*** — solely because the two specs disagree on
what `extensions[]` *is* in 0.77.0 (path-list vs override-filter). The Caveat
makes this explicit; the recommendation is written to be correct under either,
and the one-line code re-verification resolves it cheaply.

**Auto-decidable: yes, for the write rule** — it resolves a "low-stakes" open item
toward the *more conservative* documented option and *removes* a write surface
rather than adding one; it satisfies both "simple defaults" and "fail loud / don't
mutate what you don't own," so there is no principle tension to surface.

**AJ confirmation:** not required for the write rule. The only thing PR2 *must*
do is the 0.77.0 `package-manager.js` re-read (a build-time fact-check, not a
product decision). AJ confirmation is *optional* and only relevant if he later
wants a richer managed-`extensions[]` UX (e.g. a `pi-extension enable/disable`
verb that edits the override list) — that would be a deliberate future opt-in to a
managed `extensions[]` channel, explicitly out of scope for PR2 and gated on
revisiting the config-mutation stance.

---

### Sources

Full `2026-05-29-pi-extension-kind-design.md` (§§2, 3, 5, 6, 8, 11); PR1 plan
`2026-05-29-pi-extension-kind-pr1-inventory.md` (confirms `_pi_settings.py` reads
both arrays; `build_inventory` does not yet consume `extensions[]`); prior-gen
`2026-05-19-pi-settings-extensions-array-design.md` (#109 — the override-filter
premise correction, shipped in PR #116) and
`2026-05-19-pi-unified-extension-inventory-design.md` (#103/#106 — `extensions[]`
deferral precedent); `2026-05-05-codex-config-file-hooks-design.md` (the
`[agents]` config-mutation deferral precedent). Existing shipped code referenced:
`src/agent_toolkit_cli/_pi_overrides.py`, `_pi_settings.py`,
`doctor/pi_advisories.py`.

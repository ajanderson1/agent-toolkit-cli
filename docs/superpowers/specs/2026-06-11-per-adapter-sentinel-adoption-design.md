# Per-adapter sentinel adoption — symlink/translate (+ codex/firebender) ownership sidecars (#368)

**Issue:** #368 · **Tier:** standard · **Date:** 2026-06-11
**Decided with PM (AFK picker, 4 forks):** include codex/firebender sentinel
write+cleanup; symlink/translate ignore the lock-derived overwrite flag
(standard parity); uninstall becomes ownership-guarded with structured
refusal; doctor cursor-shadow sentinel-gated fix is in scope.

## Problem

Only the standard agents adapter (`agent_adapters/standard.py`) and two of the
four config_file_folder cells (aider-desk, dexto) write `.attk` ownership
sidecars. The symlink (15 cells) and translate (10 cells) adapters project
plain files with no ownership record, and codex/firebender's per-slug files
are likewise sentinel-less. Confirmed downstream defects:

1. **F2 root cause (PR #366):** the doctor's cursor-shadow removal fix had to
   ship report-only — it gated on a sentinel cursor installs never write.
2. **F3 (recorded on #362):** project-scope re-installs conflict on the
   tool's *own* sentinel-less files; without a lock entry nothing
   self-authorizes a refresh.
3. **G5, waived from #362 to here (spec § Lock-entry semantics):**
   per-slug ownership (`overwrite=True` derived from any lock entry)
   authorizes clobbering a user-authored file at a destination the tool
   *never projected*. Per-destination sentinels are the real fix.
4. **Partial multi-harness failure (#362, accepted limitation 2):** adapter N
   succeeds, adapter N+1 raises → the successful sentinel-less projections
   make the retry conflict on our own files.

## The ownership contract (the invariant)

For every per-slug destination file `D` written by a file-writing agent
adapter (sidecar = `D.parent / f".{D.name}.attk"`, the existing `_sentinel_path`):

1. **Install writes the sidecar** beside `D` (empty file, as today's writers do).
2. **Adopt-if-identical:** a pre-existing, non-symlink `D` whose content
   byte-matches *what install would write now* is adopted — sidecar written,
   file untouched, success returned.
3. **Overwrite authority = sentinel only.** A divergent pre-existing `D`
   without a sidecar raises `AgentProjectionConflictError`, **regardless of
   the facade's lock-derived `overwrite=` flag** (parameter kept for Protocol
   stability; symlink/translate ignore it exactly as standard.py does).
4. **Symlink-at-destination is replaced, never written through** (standard's
   F6 guard): `if dest.is_symlink(): dest.unlink()` before writing; the
   adopt check skips symlinks.
5. **Uninstall is ownership-guarded:** remove `D` when the sidecar exists OR
   `D` content-matches what install would write now (content-match detach for
   pre-#368 projections); otherwise leave `D` in place and return its path as
   a **structured refusal** (`Path | None`, standard's F5 shape). The sidecar
   is removed whenever `D` is gone (orphan-sentinel hygiene, #366).

"What install would write now":
- **symlink cells** — the canonical `<slug>.md` bytes (`filecmp.cmp(..., shallow=False)`).
- **translate cells** — the emitter output over the parsed canonical
  (`_emitter(_parse_frontmatter(canonical_text))`), compared as text. On the
  install path an emitter `ValueError` stays an `InstallError` (existing
  behaviour). On the **uninstall** path an emitter failure (or a missing/None
  `canonical_content`) is treated as *no match* — detach must not crash; the
  sidecar alone then decides.

### Per-mechanism scope

| Mechanism | Change |
|---|---|
| `standard.py` | **No change** (already the reference implementation). |
| `symlink.py` (15 cells) | Full contract 1–5. |
| `translate.py` (10 cells) | Full contract 1–5; its uninstall additionally gains the orphan-sentinel cleanup symlink got in #366 (today it cleans nothing). |
| `config_file_folder.py` codex + firebender | Contract **1 only** plus sidecar unlink on uninstall — sentinel write beside the per-slug `.toml`/`.md`, sidecar removed in uninstall. Shared-registry mutation (`config.toml`, `firebender.json`) and their unconditional removal semantics are **unchanged**. |
| `config_file_folder.py` aider-desk + dexto | No change (sidecar already written; `rmtree` of the per-slug subdir removes it). |

devin note (translate): its destination is a fixed `AGENT.md` shared across
slugs. Per-destination ownership means "the tool owns this path"; a second
slug's install over the first's projection is authorized by the sidecar —
same net behaviour as today's lock-flag path, now explicit.

## Facade changes (`agent_install.py`)

- **Protocol unification:** `AgentAdapter.uninstall` gains
  `canonical_content: Path | None = None` and returns `Path | None` for all
  adapters (today only standard takes the kwarg / returns refusals). The
  `name == "standard"` special-casing in `apply()`'s remove loop and in
  `uninstall()` collapses; both thread `canonical_content` to every adapter.
  `uninstall()` collects refusals from every adapter; `apply()` keeps its
  `InstallResult` shape (refusals in its remove loop surface via the
  adapters' stderr notice — expanding `InstallResult` is YAGNI).
  config_file_folder adapters accept the kwarg and ignore it (their removal
  semantics are out of scope).
- `uninstall()`'s refusal return shape `tuple[(harness, dest), ...]` is
  unchanged — existing CLI stderr + TUI surfacing (F5 machinery) picks up the
  new refusals with no caller changes.
- `apply()` keeps passing `overwrite=`; it simply no longer grants clobber
  authority in symlink/translate (sentinels do).

## Doctor change (`doctor_cmd.py` 4b, cursor-shadow)

Sentinel-gated automatic fix, restoring F2's original intent now that the
gate can actually fire: when the shadowing `.cursor/agents/<slug>.md` has an
`.attk` sidecar → offer a `fix_action` that removes the file *and* its
sidecar; sentinel-less → today's report-only message, unchanged.
`cursor-shadow` **stays in `_INFORMATIONAL_TYPES`** — exit-code semantics do
not change (F1's exit-0 guarantee for hand-authored content holds).

## Migration

- Pre-#368 sentinel-less projections: **adopted** on the next install when
  identical (case 2) and **detached** on uninstall via content-match (case 5).
- Drifted pre-#368 projections (canonical updated since they were written):
  one-time install refusal with the existing clear conflict message; recover
  via `agent uninstall --harnesses <h>` → re-install, or delete the file.
  Accepted cost, mirrors #361's accepted edge for the standard slot.
- The #362 partial-failure limitation self-heals: succeeded projections now
  carry sidecars, so the retry is self-authorizing.

## Interaction with #362 (PR #378, awaiting merge)

Independent and order-insensitive. #362 derives `overwrite=True` from the
new project lock entry; this issue makes that flag inert for
symlink/translate destinations (per-destination authority supersedes
per-slug). No shared code beyond `apply()`'s loops; whichever merges second
rebases trivially.

## Acceptance criteria

1. Every symlink cell, every translate cell, and codex/firebender per-slug
   installs write `.{name}.attk` beside the destination file.
2. **F3 pin:** at project scope with an empty/no lock, re-installing over the
   tool's own prior projection succeeds (sentinel self-authorizes); a
   sentinel-less byte/emission-identical file is adopted without error.
3. **G5 pin:** with a lock entry present (`overwrite=True` from the facade),
   a divergent foreign file at a never-projected destination still raises
   `AgentProjectionConflictError` for symlink/translate cells.
4. **F6 parity:** a symlink at a symlink/translate destination is replaced,
   never written through.
5. Guarded uninstall (symlink/translate): sidecar present → removed (even if
   user-edited); sentinel-less + content-match → removed; sentinel-less +
   divergent → left in place, refusal surfaced through
   `agent_install.uninstall()`'s return (CLI stderr notice + TUI path).
6. No orphan sidecars: uninstall removes the sidecar in translate (new),
   codex and firebender (new); symlink behaviour (#366) preserved.
7. Doctor cursor-shadow offers the removal fix **only** when the shadowing
   file carries a sidecar, exercised through the REAL adapter (no
   hand-manufactured sentinel); sentinel-less stays report-only; `agent
   doctor` exit codes unchanged.
8. Standard adapter tests untouched and green; full suite green (the two
   known HOME-isolation local-only failures excepted).

## Out of scope

- Ownership for shared registries (`firebender.json`, codex `config.toml`)
  and aider-desk/dexto uninstall semantics.
- A doctor sweep for orphaned `.attk` sidecars across all adapter dirs
  (follow-up candidate).
- Other asset types (skills, instructions, pi-extension) — their projection
  models differ (symlink-at-path is self-identifying).
- Retroactive sidecar backfill for existing installs (adopt-on-touch only).

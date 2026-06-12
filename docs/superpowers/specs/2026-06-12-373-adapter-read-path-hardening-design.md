# Adapter read-path hardening — InstallError everywhere a canonical read can fail (#373)

**Issue:** #373 · **Tier:** standard · **Date:** 2026-06-12
**Decided with orchestrator (2 forks):** hybrid wrap (per-adapter guards +
facade-seam slug enrichment, InstallError-only at the seam); uniform posture
across all four config_file_folder adapters including catalog-disabled
firebender/codex; carry a gap-3 regression test pinning #368's dissolution
of the sentinel-less retry wedge.

## Problem

#370 (PR #372) typed translate-emitter frontmatter failures as `InstallError`
so the CLI exits clean. The PM's merge review found four residual gaps; #368
(PR #380, v3.9.0) has since changed the picture. Re-verified on main @ dba6d20:

1. **translate read partially guarded.** `install()` now fail-louds a missing
   canonical (`InstallError`, F8 parity) — but
   `raw = content_path.read_text()` (`agent_adapters/translate.py:402`) still
   executes **above** the try block. A non-UTF8 canonical raises
   `UnicodeDecodeError` (a `ValueError` subclass — it would be caught one line
   lower) as a raw traceback. `PermissionError` likewise escapes.
2. **config_file_folder reads fully unguarded.** All four cff adapters
   (aider-desk, dexto, firebender, codex) call `content_path.read_text()`
   with no missing-file check and no wrap; the facade seam
   (`agent_install.py:311`) has no wrap either. aider-desk and dexto are
   live (`subagent_mechanism: config_file_folder`); firebender and codex are
   catalog-disabled (`none`) but their write code shipped in #368 — flipping
   the catalog would inherit the raw-traceback paths. firebender's
   `json.loads(fb_json.read_text())` (install ~:233, uninstall ~:270) raw-
   tracebacks on a corrupt `firebender.json`.
3. **No wrapped message names the slug.** The #370 wrap re-raises as
   `InstallError(str(exc))`; emitter messages name harness + key but not
   which agent failed. With multi-agent fan-outs the slug matters.
4. **Gap 3 of the original issue (sentinel-less retry wedge) is DISSOLVED
   by #368** — sentinels are written at install time and adopt-if-identical
   covers emission-identical leftovers. This issue pins that with a
   regression test rather than carrying a guard.

## Design

### 1. translate.py — read inside the wrap

Move `raw = content_path.read_text()` inside the existing try; widen the
except to `(ValueError, OSError)`. `UnicodeDecodeError` and environment
failures (`PermissionError`) both become `InstallError`. The emitter cannot
raise `OSError`, so the widened catch stays data/environment-dependent.

Drop the slug from translate's existing F8 missing-file message
(`{harness}: {slug}: canonical content file missing…` →
`{harness}: canonical content file missing…`): the seam (§3) now adds the
slug for every mechanism, and keeping it would double it.

### 2. config_file_folder.py — uniform guard across all four adapters

For each adapter's `install()`:

- **Missing-canonical check** before the read, same message shape as
  translate's F8 check (minus slug): `InstallError(f"{harness}: canonical
  content file missing: {content_path} — re-run `agent add <slug>` to
  restore it")`.
- **Wrap the data-dependent reads/parses** in
  `except (ValueError, OSError) as exc: raise InstallError(f"{harness}:
  {exc}") from exc`:
  - `content_path.read_text()` (all four),
  - firebender's `json.loads(fb_json.read_text())`,
  - codex's `config_toml.read_text()`.

firebender's `uninstall()` registry read (`json.loads(fb_json.read_text())`)
gets the same wrap — a corrupt `firebender.json` must not raw-traceback an
uninstall.

Structural writes (`mkdir`, `write_text`, `_atomic_write`) stay unwrapped:
failures there are environment corruption the fail-loud principle wants as
tracebacks, matching translate's posture.

### 3. agent_install.py — seam slug enrichment, InstallError only

Around both `adapter.install(...)` and `adapter.uninstall(...)` in
`apply()`:

```python
try:
    out = adapter.install(...)
except InstallError as exc:
    raise type(exc)(f"{plan.slug}: {exc}") from exc
```

Catch **only `InstallError`** — unexpected exceptions still traceback
(fail-loud preserved). The slug is named exactly once for every mechanism,
current and future; adapters never format it themselves.

`AgentProjectionConflictError` is an `InstallError` subclass — re-raising as
plain `InstallError` would erase the subtype, which callers (e.g. the TUI
and #368's adoption flow) discriminate on. Hence `type(exc)(...)`, not
`InstallError(...)`.

### 4. Non-goals / out of scope

- Enabling firebender or codex in the catalog.
- Doctor changes (read paths there are separate; #314 lineage).
- symlink-adapter hardening (it performs no canonical content read).
- Retry/rollback semantics for partial fan-outs beyond what #368 shipped.

## Error-message contract (acceptance shape)

A data-dependent install failure surfaces as one clean line through the CLI:

```
Error: <slug>: <harness>: <cause>
```

e.g. `Error: my-agent: github-copilot: 'description' is required in
frontmatter but was not found` — no traceback, exit code ≠ 0.

## Test surface

All RED-first (TDD):

1. translate: non-UTF8 canonical → `InstallError`; via the seam the message
   contains the slug. (Direct adapter test + seam-level test.)
2. cff (aider-desk or dexto): missing canonical → `InstallError`;
   non-UTF8 canonical → `InstallError`.
3. firebender (direct adapter test — catalog-disabled, so construct via
   `config_file_folder.adapter_for("firebender")`): corrupt
   `firebender.json` at install → `InstallError`; corrupt at uninstall →
   `InstallError`.
4. Seam: multi-harness fan-out where one harness fails → error message names
   the slug; conflict errors keep their `AgentProjectionConflictError` type
   through the seam.
5. Gap-3 regression (pins #368): fan-out fails on harness B's frontmatter →
   fix the canonical → re-run succeeds with no
   `AgentProjectionConflictError`.
6. CLI level (mirrors #370's test): `agent install` with a failing canonical
   exits non-zero with a clean one-line error, no traceback.

## Links

- #370 / PR #372 (merge f0a29fd) — the wrap this hardens.
- #368 / PR #380 (7e39e71, v3.9.0) — dissolved original gap 3; F8 parity
  check this extends to cff.
- Seed: PM merge-review of PR #372, 2026-06-11.

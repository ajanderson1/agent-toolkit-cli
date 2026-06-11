# agent install: clean error for translate-emitter frontmatter failures — design

**Issue:** #370 · **Tier:** standard (escalated from the PM's requested `light`: classifier is the PM + plan touches >1 file) · **Date:** 2026-06-11

## Problem

`agent install <slug>` with the default fan-out crashes with a raw `ValueError`
traceback when the canonical agent file lacks frontmatter a translate emitter
requires. Verified on main @ 7e503b0:

- `_emit_github_copilot` raises `ValueError` when `description` is absent
  (`agent_adapters/translate.py:212-216`); `_emit_mistral_vibe_toml` raises on
  an invalid `safety` value (`translate.py:267-272`).
- `_TranslateAdapter.install` calls the emitter unguarded (`translate.py:395`),
  `agent_install.apply()`'s add loop calls `adapter.install` unguarded
  (`agent_install.py:285`), and `install_cmd.py:143` catches only
  `InstallError` — so the `ValueError` escapes Click as a traceback, exit 1.
- The default fan-out is `("standard", *sorted(non_covered))`, so every
  harness sorting before `github-copilot` has already been written when the
  crash hits. The success echo never runs: partial install, nothing reported.

## Decision (pre-made by the PM, 2026-06-11)

Type the failure at the adapter seam. `_TranslateAdapter.install` wraps the
parse + emit step:

```python
try:
    fm, body = _parse_frontmatter(raw)
    output = self._emitter(fm, body, slug)
except ValueError as exc:
    raise InstallError(str(exc)) from exc
```

- `InstallError` comes from `agent_toolkit_cli._install_core` — the same base
  `AgentProjectionConflictError` already subclasses, and exactly what
  `install_cmd.py:143` already converts to a clean `ClickException`. No CLI
  change needed.
- Emitters keep raising `ValueError` with messages that already name the
  harness and the offending key (`"github-copilot: 'description' is required
  in frontmatter but was not found"`) — the wrap preserves the message
  verbatim, so the user sees harness + key with no traceback.
- The contract becomes: **adapter `install()` raises `InstallError` (or a
  subclass) for all data-dependent failures**; raw `ValueError` from an
  adapter is a programming error. The symlink/standard/config-file adapters'
  ValueErrors are contract violations (missing `home=`, bad scope) fed by the
  facade, not by user data, and are out of scope here.

**Partial-install rollback is OUT of scope** (PM decision): harnesses written
before the failing one stay on disk. The clean error is the minimum bar;
rollback (or reporting the partial set on failure) is a possible follow-up.

## Test surface

Regression test mirroring the repro: a canonical agent `.md` with **no YAML
frontmatter**, installed via the CLI with **no `--harnesses`** (default
fan-out) in a HOME-isolated sandbox → exit code ≠ 0, output contains
`github-copilot` and `description`, no `Traceback` in output. At the adapter
level, the two **existing** tests covering these scenarios
(`test_translate.py:327-349`, currently asserting `pytest.raises(ValueError)`)
are retyped in place to assert `InstallError` — no duplicate tests added
(critical-review finding). The adjacent `requires home=` contract-error test
stays on `ValueError`: it fires in `_resolve_dest`, before the wrap.

Empirically confirmed on the unfixed baseline (sandbox HOME): the default
fan-out writes 13 files across 10 harnesses before the ValueError lands at
`github-copilot` (index 10), with empty CLI output.

## Acceptance criteria

1. Default fan-out over a frontmatter-less agent exits with a clean Click
   error naming the failing harness and the missing/invalid key.
2. Translate-emitter data failures surface as `InstallError` at the adapter
   boundary; `install_cmd`'s existing handler needs no change.
3. Regression test covers the exact repro (frontmatter-less + default
   fan-out → clean error, non-zero exit, no traceback) and the adapter-level
   raise.
4. Full suite green.

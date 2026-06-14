# #420 — surface which scope/lock was resolved for `pi-extension` (mirror #413)

**Issue:** #420 · **Size:** M · **Date:** 2026-06-14

## Problem

When a `pi-extension` read verb runs with no `-g`/`-p`, `scope_and_roots`
(`commands/pi_extension/_common.py`) resolves scope **implicitly**: a
`pi-extensions-lock.json` in `cwd` silently selects **project** scope; otherwise
it falls back to **global**. The resolution is invisible. Identical to the
opacity #413 fixed for `skill` (PR #417, commit `4d0eed1`); this is the fourth
and final sibling port (after `agent` #418/PR #424 and `mcp` #419/PR #426).

This is a **transparency / UX fix**, not a behaviour change.

## Cross-cutting decision: COPY, do not unify (the deferred #420 option)

#420 raised whether the four `scope_and_roots` + `scope_banner` copies (skill,
agent, mcp, pi-extension) should be **unified into one shared module** rather
than copy-pasted a fourth time. **Decision: keep the per-kind copy; do not unify
in this issue.** Rationale:

1. **The copies legitimately diverge.** Each is parametrised on a different
   `_LOCK_FILENAME`, carries a kind-specific noun (skill/agent/MCP server/pi
   extension), and the count expression differs (`len(lock.skills)` for
   skill/agent/pi vs `len(lock)` for mcp's dict lock). `mcp/_common.py` also
   carries scope-aware harness logic the others lack. A shared helper would need
   `lock_filename` + `noun` + `count_fn` parameters, re-introducing per-call
   config that erodes much of the dedup benefit.
2. **Independent issues, independent PRs.** #418/#419/#420 are three separate
   issues shipped as three separate PRs. Unifying would couple them and force a
   single change touching the already-merged `skill` helper — larger blast
   radius, against the per-issue framing.
3. **Convention — "Add flexibility only when a real second case forces it."**
   The copy is the boring default that always works; the unification is the
   speculative, larger change. With the pattern now proven identical across all
   four, a *follow-up* unification (its own issue) can be evaluated against the
   complete set rather than mid-rollout.

**Follow-up #427** evaluates unifying the four `scope_and_roots`/`scope_banner`
copies now that all four exist (cross-ref the broader "unify scope_and_roots and
roots" option noted in #420's own body).

## Decisions (inherited from #413; pi-specific deltas noted)

1. **Scope: `pi-extension` only** (the last of the four).
2. **Signal lives in `scope_and_roots`** — returns a 4th `implicit` element.
   `pi_extension/_common.py`'s helper is already typed (`Scope`, explicit tuple
   return) and parametrised on `_LOCK_FILENAME = PI_EXTENSION_BINDING.lock_filename`
   (`pi-extensions-lock.json`). The annotation becomes the 4-tuple.
3. **Banner on implicit-project only.** Silent on implicit-global / explicit.
4. **Noun: "pi extension" / "pi extensions".** Trailing clause stays "Pass -g
   for the global library."
5. **Count is `len(lock.skills)`.** pi's `read_lock` is the lenient
   `skill_lock.read_lock` re-export, returning a `LockFile` with `.skills`
   (empty on missing file — safe at implicit-global).
6. **pi delta — `list`/`status` are inventory-based, not lock-based.** Unlike
   skill/agent, pi `list` and `status` render `build_inventory(...)` records
   (store-owned + untracked + npm), **not** the lock. So for the banner count
   they get an **introduced** `read_lock(lock_path).skills` read (like the
   doctor pattern). The count is deliberately the **lock** entry count, not the
   inventory record count — the banner is about *which lock you are operating
   on* ("pass -g to switch lock"), so the lock count is the meaningful figure;
   the inventory may include untracked/npm extensions that no `-g` switch
   affects.
7. **`list` has `--json`; `status` does not.** `list` routes the banner to
   stderr on `--json` (`err=as_json`), keeping JSON stdout pristine — same as
   skill/agent. `status` and the other read verbs always go to stdout.

## Approach

### `scope_and_roots` → 4-tuple (`commands/pi_extension/_common.py`)

Append `implicit` to each return (False on explicit branches, True on both
fallthrough branches); widen the annotation to
`tuple[Scope, Path | None, Path | None, bool]`; add a docstring noting `implicit`.

### `scope_banner` helper (`commands/pi_extension/_common.py`)

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Emit a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project. Goes to stdout by default; callers emitting a machine stream
    (``list --json``) pass ``err=True``.
    """
    if not (implicit and scope == "project"):
        return
    noun = "pi extension" if count == 1 else "pi extensions"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

### Wiring

The six pi read verbs sharing `scope_and_roots` with `read_only=True` are
**`list`, `status`, `update`, `reset`, `push`, `doctor`**.

- **`list`**: inventory-based, no lock read. Introduce
  `lock_path = lock_file_path(scope=scope, home=home, project=project_root)` and
  call `scope_banner(scope, implicit=implicit, lock_path=lock_path,
  count=len(read_lock(lock_path).skills), err=as_json)` after `scope_and_roots`,
  before `build_inventory`. (Imports `read_lock` + `lock_file_path` — not
  currently imported in `list_cmd`.)
- **`status`**: inventory-based, no `--json`. Same introduced read, `err`
  defaulted (stdout), before `build_inventory`.
- **`update`, `reset`, `push`**: already read `lock = read_lock(lock_path)` with
  `lock_path` local. Call `scope_banner(scope, implicit=implicit,
  lock_path=lock_path, count=len(lock.skills))` after the read, before the
  per-slug loop. `reset` rejects a bare invocation with a `UsageError` *before*
  `scope_and_roots`, so its test must pass a slug.
- **`doctor`**: calls `diagnose(...)` with no body-level lock read. Introduce the
  standalone read for the count (mirrors agent/mcp doctor).

Write verbs (`install`, `uninstall`) absorb the 4th element as `_implicit`.

## Components & boundaries

| Unit | Change | Depends on |
|---|---|---|
| `scope_and_roots` | returns 4-tuple `(scope, home, project_root, implicit)`; annotation + docstring | nothing new |
| `scope_banner` | new helper, `err=` arg, implicit-project only, noun "pi extension(s)", `count=len(lock.skills)` | `click` |
| pi read verbs (`list`, `status`, `update`, `reset`, `push`, `doctor`) | unpack 4th element, call `scope_banner` pre-output (`list --json` passes `err=True`); `list`/`status`/`doctor` introduce a lock read for the count | the two above |

## Error handling

- Banner never raises and never changes exit codes — advisory output.
- Empty project lock (`count == 0`) still banners on the implicit path.
- pi `read_lock` is empty-on-missing (skill re-export), so the introduced reads
  are safe at implicit-global (where the banner is silent anyway).

## Out of scope

- `agent` (#418), `mcp` (#419) — already shipped.
- The unify-the-four refactor — deferred to a filed follow-up (see decision
  above).
- Changing scope-resolution rules; banner on implicit-global.
- pi has no monorepo-refusal message to reword (skill-specific in #413).

## Test surface

- `scope_and_roots` returns correct `implicit` across all four branches.
- `scope_banner`: prints on implicit-project; silent on implicit-global / explicit
  `-p` / explicit `-g`; singular/plural noun ("pi extension"/"pi extensions");
  `count == 0` still prints; `err=True` → stderr, default → stdout.
- `pi-extension list --json` stdout parses as JSON with the banner on **stderr**.
- Human read verbs (`status`/`update`/etc.): banner on **stdout**.
- End-to-end: a bare `pi-extension list`/`status` from a cwd with a project
  `pi-extensions-lock.json` prints the banner before the per-extension lines on
  stdout; from a cwd without one (global fallback, HOME-isolated) prints **no**
  banner.

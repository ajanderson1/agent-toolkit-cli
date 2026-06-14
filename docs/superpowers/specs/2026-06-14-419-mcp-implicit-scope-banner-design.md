# #419 — surface which scope/lock was resolved for `mcp` (mirror #413)

**Issue:** #419 · **Size:** M · **Date:** 2026-06-14

## Problem

When an `mcp` read verb runs with no `-g`/`-p`, `scope_and_roots`
(`commands/mcp/_common.py`) resolves scope **implicitly**: an `mcps-lock.json`
in `cwd` silently selects **project** scope; otherwise it falls back to
**global**. The resolution is invisible — nothing tells the user which lock was
picked. Identical to the opacity #413 fixed for `skill` (PR #417, commit
`4d0eed1`); this issue ports the transparency fix to the `mcp` asset type.

This is a **transparency / UX fix**, not a behaviour change. The scope
resolution itself is correct and stays as-is.

## Decisions (inherited from #413; mcp-specific deltas noted)

1. **Scope: `mcp` only.** Sibling ports: `agent` (#418, PR #424), `pi_extension`
   (#420). The four `scope_and_roots` copies are deliberately **not** unified
   here — see #420's spec for the recorded unify-vs-copy decision.
2. **Signal lives in `scope_and_roots`.** Returns a 4th element `implicit`
   (`True` iff neither `-g` nor `-p`). `mcp/_common.py`'s `scope_and_roots` is
   already typed (`Scope = Literal["project", "global"]`, explicit tuple return)
   and parametrised on `_LOCK_FILENAME = mcp_lock.LOCK_FILENAME`. The annotation
   becomes `tuple[Scope, Path | None, Path | None, bool]`.
3. **Banner on implicit-project only.** Silent on implicit-global, explicit
   `-g`, explicit `-p`.
4. **Noun: "MCP server" / "MCP servers".** Trailing clause stays the neutral
   "Pass -g for the global library."
5. **mcp delta — count is `len(lock)`, not `len(lock.skills)`.** `mcp_lock.read_lock`
   returns a plain `dict[str, list[McpLockEntry]]` (slug → harness entries), NOT
   a `LockFile` object. The natural "how many am I operating on" count is the
   number of tracked slugs, `len(lock)`.
6. **mcp delta — no `--json` read verb, so the banner is always stdout.** Unlike
   skill/agent `list`, mcp `list` and `status` have **no** `--json` flag and emit
   no machine stream. The banner therefore goes to **stdout** for all three mcp
   read verbs; no caller passes `err=True`. The helper keeps the `err=False`
   default argument for cross-type signature parity, but mcp never exercises the
   stderr branch.

## Approach

### `scope_and_roots` → 4-tuple (`commands/mcp/_common.py`)

```python
def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None, bool]:
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True
```

### `scope_banner` helper (`commands/mcp/_common.py`)

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Emit a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project. Goes to stdout by default; the ``err`` argument exists for
    cross-type parity but mcp has no --json read verb, so no caller passes
    ``err=True``.
    """
    if not (implicit and scope == "project"):
        return
    noun = "MCP server" if count == 1 else "MCP servers"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

### Wiring

The mcp read verbs sharing `scope_and_roots` with `read_only=True` are
**`list`, `status`, `doctor`**. Each unpacks the 4-tuple, then calls
`scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock))`
**before** its main output.

- **`list`**: reads `lock = read_lock(lock_path_for_scope(scope, home=effective_home,
  project=project_root))`. Hoist `lock_path` into a local, call the banner right
  after the read, before the per-slug `list_library` loop.
- **`status`**: same `read_lock(lock_path_for_scope(...))` shape. The banner must
  fire **before** the `if not lock: … return` empty-lock early-return, so a
  present-but-empty project lock (`count == 0`) still banners.
- **`doctor`**: has **no** body-level lock read (the lock is read inside
  `_diagnose`), so introduce a standalone `read_lock(lock_path_for_scope(...))`
  purely for the banner count, mirroring agent/skill doctor. It already imports
  `read_lock` and `lock_path_for_scope`. `mcp_lock.read_lock` returns `{}` on a
  missing file (safe at implicit-global), and only raises on a *malformed* lock —
  on the implicit-project path the lock file is present and well-formed (it was
  written by the toolkit), so this is safe.

**`mcp update` is NOT wired.** It does not call `scope_and_roots` at all — it
hard-codes `home = Path.home()`, takes a required `slug`, has no `-g`/`-p`, and
iterates both scopes directly. It has no implicit-scope opacity, so it is out of
scope for this banner port. **`install`, `uninstall`, `remove`** are write verbs;
they unpack the 4th element as `_implicit` but the banner does not fire for them.

## Components & boundaries

| Unit | Change | Depends on |
|---|---|---|
| `scope_and_roots` | returns 4-tuple `(scope, home, project_root, implicit)`; annotation updated | nothing new |
| `scope_banner` | new helper, `err=` arg (unused by mcp), implicit-project only, noun "MCP server(s)", `count=len(lock)` | `click` |
| mcp read verbs (`list`, `status`, `doctor`) | unpack 4th element, call `scope_banner` pre-output (always stdout) | the two above |

## Error handling

- Banner never raises and never changes exit codes — advisory output.
- Empty project lock (`count == 0`) still banners on the implicit path.
- `mcp_lock.read_lock` raises on a *malformed* lock (fail-loud by design); the
  banner read only happens on the implicit-project path where the lock is
  toolkit-written and well-formed, so this does not introduce a new failure mode.

## Out of scope

- `agent` (#418), `pi_extension` (#420) — sibling ports.
- Unifying the four `scope_and_roots`/`scope_banner` copies — decision recorded
  in #420.
- `mcp update` (no implicit-scope resolution).
- Changing scope-resolution rules; banner on implicit-global.
- mcp has no monorepo-refusal message to reword (skill-specific in #413).

## Test surface

- `scope_and_roots` returns correct `implicit` across all four branches
  (explicit `-g`, explicit `-p`, implicit→project, implicit→global).
- `scope_banner`: prints on implicit-project; silent on implicit-global,
  explicit `-p`, explicit `-g`; singular/plural noun ("MCP server"/"MCP servers");
  `count == 0` still prints; `err=True` routes to stderr (helper-level test, even
  though mcp never passes it). Tests use a bare `CliRunner()` (Click 8.2+ splits
  `result.stdout`/`result.stderr`).
- End-to-end: a bare `mcp list`/`status` from a cwd with a project
  `mcps-lock.json` prints the project banner before the per-slug lines on
  stdout; from a cwd without one (global fallback) prints **no** banner.
- `mcp doctor` over a project lock prints the banner (count from the introduced
  read).

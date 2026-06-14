# #418 — surface which scope/lock was resolved for `agent` (mirror #413)

**Issue:** #418 · **Size:** M · **Date:** 2026-06-14

## Problem

When an `agent` read verb runs with no `-g`/`-p`, `scope_and_roots`
(`commands/agent/_common.py`) resolves scope **implicitly**: an
`agents-lock.json` in `cwd` silently selects **project** scope; otherwise it
falls back to **global** (the read-only default). The resolution is invisible —
nothing tells the user which lock was picked. This is the identical opacity
#413 fixed for `skill` (merged in PR #417, commit `4d0eed1`); this issue ports
the same transparency fix to the `agent` asset type.

This is a **transparency / UX fix**, not a behaviour change. The scope
resolution itself is correct and stays as-is.

## Decisions (inherited from #413; agent-specific deltas noted)

1. **Scope: `agent` only.** `mcp` (#419) and `pi_extension` (#420) get their own
   sibling ports. The four `scope_and_roots` copies are deliberately **not
   unified** here — see #420's spec for the recorded unify-vs-copy decision.
2. **Signal lives in `scope_and_roots`.** It returns a 4th element, `implicit`
   (`True` iff neither `-g` nor `-p` was passed). All agent call sites that
   unpack the tuple gain the 4th element.
   - **Agent-specific:** `agent/_common.py`'s `scope_and_roots` is already typed
     (`Scope = Literal["project", "global"]`, explicit tuple return annotation).
     The annotation becomes `tuple[Scope, Path | None, Path | None, bool]`.
3. **Banner on implicit-project only.** When scope was resolved implicitly *and*
   landed on project, print a one-line reminder. Implicit-**global** stays quiet
   (the documented read-only default; not the reported pain).
4. **Banner goes to stdout for human-facing verbs; stderr only for a machine
   stream** (`list --json`). `scope_banner` takes `err: bool = False`; only
   `list --json` passes `err=True`, mirroring #413.
5. **Noun: "agent" / "agents".** The skill banner says "skill(s)"; the agent
   banner says "agent(s)". The trailing clause stays the neutral
   "Pass -g for the global library."

## Approach

### `scope_and_roots` → 4-tuple (`commands/agent/_common.py`)

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

`implicit` is `True` on both fallthrough branches and `False` on both
explicit-flag branches. Write-path verbs (`read_only=False`) still fall through
to implicit-project with `implicit=True`; they unpack the 4th element but the
banner only fires for read verbs (see Wiring).

### `scope_banner` helper (`commands/agent/_common.py`)

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Emit a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project. Goes to stdout by default (a human sees it inline with the verb
    output); callers emitting a machine stream pass ``err=True`` (today only
    ``list --json``).
    """
    if not (implicit and scope == "project"):
        return
    noun = "agent" if count == 1 else "agents"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

### Wiring

The agent **read verbs** that share `scope_and_roots` and produce human-facing
output unpack the 4-tuple, read their lock, then call `scope_banner(scope,
implicit=implicit, lock_path=lock_path, count=len(lock.skills))` **before** their
main output. Mirroring #413's choice to wire all six skill read verbs, the agent
read verbs wired are: **`list`, `status`, `update`, `reset`, `push`, `doctor`**.

- **`list`**: the human path calls `scope_banner(..., err=False)` (stdout); the
  `--json` path calls `scope_banner(..., err=True)` (stderr) so JSON stdout stays
  pristine. Banner fires after a successful `read_lock`, before emitting records.
- **The five non-`list` read verbs** call `scope_banner(...)` with default
  `err=False` (stdout), after their successful `read_lock`, before per-slug
  output.
- **Banner placement vs. early returns.** Agent read verbs bail early on
  `FileNotFoundError` (no lock at all). On the implicit-project path the lock
  file is present *by definition* (its presence selected project scope), so the
  `read_lock` succeeds and the banner fires after it. The `count` is then
  `len(lock.skills)` — the dict of entries on the shared `Lock` object (same
  `.skills` field agent/mcp/pi all use). An empty-but-present project lock
  (`count == 0`) still banners — it is still the surprising implicit-project
  case; the existing "no agents in the {scope} library" line follows the banner.
- **Write verbs are not wired.** `install`/`uninstall`/`add`/`remove`/`import`
  are write/mutation verbs; #413 wired only the six read verbs and left write
  verbs untouched. We match that. (`update`/`reset`/`push` count as read-shaped
  here because #413 wired them; they share the read-verb signature.)

## Components & boundaries

| Unit | Change | Depends on |
|---|---|---|
| `scope_and_roots` | returns 4-tuple `(scope, home, project_root, implicit)`; annotation updated | nothing new |
| `scope_banner` | new helper, `err=` arg, implicit-project only, noun "agent(s)" | `click` |
| agent read verbs (`list`, `status`, `update`, `reset`, `push`, `doctor`) | unpack 4th element, call `scope_banner` pre-output (`list --json` passes `err=True`) | the two above |

## Error handling

- Banner never raises and never changes exit codes — advisory output.
- Empty project lock (`count == 0`) still banners on the implicit path; the lock
  *file* exists (that is what selected project scope), it just has no entries.

## Out of scope

- `mcp` (#419), `pi_extension` (#420) — sibling ports, same pattern.
- Unifying the four `scope_and_roots` / `scope_banner` copies — decision +
  follow-up recorded in #420's spec.
- Changing the scope-resolution rules themselves (read-only default stands).
- Banner on implicit-**global** resolution.
- `agent` has no monorepo-refusal message to reword (that was skill-specific in
  #413); this port is the banner half only.

## Test surface

- `scope_and_roots` returns the correct `implicit` across all four branches
  (explicit `-g`, explicit `-p`, implicit→project, implicit→global).
- `scope_banner`: prints on implicit-project; silent on implicit-global,
  explicit `-p`, explicit `-g`; singular/plural noun ("agent"/"agents");
  `count == 0` still prints; `err=True` routes to stderr, default to stdout.
  (Tests use a bare `CliRunner()` — Click 8.2+ separates
  `result.stdout`/`result.stderr`; no `mix_stderr` constructor argument.)
- `agent list --json` stdout parses as JSON with the banner on **stderr**.
- For human read verbs (`status`/`update`/etc.) the banner is on **stdout**,
  inline with the verb output.
- End-to-end: a bare `agent list`/`status` from a cwd with a project
  `agents-lock.json` prints the project banner before the per-agent lines on
  stdout; from a cwd without one (global fallback) prints **no** banner.

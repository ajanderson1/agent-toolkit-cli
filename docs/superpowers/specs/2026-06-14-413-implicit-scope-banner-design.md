# #413 — surface which scope/lock was resolved when no `-g`/`-p` is given

**Issue:** #413 · **Size:** M · **Date:** 2026-06-14

## Problem

When a `skill` read-only verb runs with no `-g`/`-p`, `scope_and_roots`
(`commands/skill/_common.py`) resolves scope **implicitly**: a `skills-lock.json`
in `cwd` silently selects **project** scope; otherwise it falls back to
**global** (the documented #210 read-only default). The resolution is invisible —
nothing tells the user which lock was picked.

Combined with `update_cmd.py` refusing all monorepo entries at project scope
(`monorepo update only supported at global scope`), a bare `skill update` from a
directory whose project lock is all monorepo-backed (the common case — e.g.
`~/Journal`, a 6-skill project lock) is a **guaranteed `exit 1` no-op** with a
misleading message. The user reasonably reads it as "these need `-g`", but `-g`
does not re-scope those 6 entries — it switches to the **global** lock, a
different ~64-skill universe. Nothing surfaces (a) that they were in project
scope, (b) that the project lock holds 6 skills, (c) that `-g` targets a
different set.

This is a **transparency / UX fix**, not a behaviour change. The scope
resolution itself is correct and stays as-is.

## Decisions (settled in brainstorm)

1. **Scope: `skill` only.** The identical implicit-resolution pattern exists in
   `agent`, `mcp`, and `pi_extension` `_common.py`. Those get **follow-up
   issues**, not this change.
2. **Signal lives in `scope_and_roots`.** It returns a 4th element, `implicit`
   (`True` iff neither `-g` nor `-p` was passed). All 6 skill call sites unpack
   it. Only the `skill` helper changes; agent/mcp/pi stay 3-tuple.
3. **Banner on implicit-project only.** When scope was resolved implicitly *and*
   landed on project, print a one-line reminder. Implicit-**global** stays quiet
   (it is the documented default and was not the reported pain).
4. **Improve the monorepo refusal message** to explain what `-g`
   actually does (switches to the global library set), not just state the
   constraint. **Both** verbs that carry this refusal — `update` *and* `reset`
   (`reset_cmd.py:72` has a byte-identical message) — are reworded, so the
   lesson is consistent across the two refusing verbs.
5. **Banner goes to stdout for human-facing verbs; stderr only for a machine
   stream** (`list --json`). Routing the banner to stdout is what the *human*
   reader actually wants — under the common `skill update 2>/dev/null` habit a
   stderr banner would vanish, which is the exact #413 scenario. The only
   consumer that needs a pristine stdout is `list --json`; that one path emits
   the banner to stderr. `scope_banner` takes an `err: bool = False` argument;
   only `list --json` passes `err=True`. (Adversarial review caught the
   original blanket-stderr decision: its sole rationale — JSON cleanliness —
   applies to one of seven code paths, and it lost the reminder in the reported
   failure case.)

## Approach

### `scope_and_roots` → 4-tuple

```python
def scope_and_roots(global_, project, ctx_project, *, read_only=False):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False        # explicit
    if project:
        return "project", None, (ctx_project or Path.cwd()), False  # explicit
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / "skills-lock.json").exists():
        return "global", Path.home(), None, True          # implicit → global
    return "project", None, project_root, True            # implicit → project
```

`implicit` is `True` on both fallthrough branches and `False` on both
explicit-flag branches. The two write-path verbs that pass `read_only=False`
still fall through to implicit-project with `implicit=True`; they may ignore it.

### `scope_banner` helper (`commands/skill/_common.py`)

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False):
    """Emit a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly AND landed on project — the
    one case (#413) where the user got no signal about which lock was picked.

    Goes to stdout by default (the human reader wants to see it inline with
    the verb's output); callers emitting a machine stream pass ``err=True`` to
    route it to stderr instead. Today only ``list --json`` does so.
    """
    if not (implicit and scope == "project"):
        return
    noun = "skill" if count == 1 else "skills"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

**Channel: stdout for humans, stderr only for `--json`.** The banner is a
reminder a human is meant to *read*, so for the five human-facing verbs (and
`list` without `--json`) it shares the verb's stdout — which also makes the
"appears before the per-skill lines" ordering real, since it's the same stream.
The single exception is `list --json`: a machine-readable stdout that the banner
must not corrupt, so `list --json` passes `err=True` and the banner goes to
stderr there. There is existing `err=True` precedent in
`commands/skill/__init__.py`.

**Wording.** The trailing clause is the neutral "Pass -g for the global
library" — *not* "target the global library", which (paired with `update`'s
reworded refusal that says `-g` does **not** update these entries) would read as
a contradiction on the headline `~/Journal` run.

### Wiring

Each of the **six** read verbs sharing `scope_and_roots`
(`list`, `status`, `update`, `reset`, `push`, `doctor`) unpacks the 4-tuple,
reads its lock, then calls `scope_banner(scope, implicit=implicit,
lock_path=lock_path, count=len(lock.skills))` **before** its main output.

- `list`: human-table path calls `scope_banner(..., err=False)` (stdout); the
  `--json` path calls `scope_banner(..., err=True)` (stderr) so JSON stdout
  stays pristine. Call it before both `_emit_json` and `_emit_table`.
- The five non-`list` verbs call `scope_banner(...)` with the default
  `err=False` (stdout).
- `status`/`list` already print an *explicit*-`-p`-empty hint; that path has
  `implicit=False`, so no double message.

### `update` and `reset` monorepo refusal messages

Both `update_cmd.py:78` and `reset_cmd.py:72` carry a byte-identical refusal.
Rewrite **both** (current → new), substituting the verb noun (`update`/`reset`):

```
{slug}: monorepo update only supported at global scope
```
→
```
{slug}: monorepo skill — update it at global scope. Note: -g switches to the
  global library (a different set), it does not update this project entry.
```

(For `reset`, the same clause with "reset it at global scope".)

The banner (above) tells the user they are in project scope and how many skills
are here, using the neutral "Pass -g for the global library"; this refusal then
clears up the specific `-g` misconception for monorepo entries — that `-g`
operates on a *different set*, not a re-scope of these entries. The two messages
are deliberately complementary, not contradictory.

## Components & boundaries

| Unit | Change | Depends on |
|---|---|---|
| `scope_and_roots` | returns 4-tuple `(scope, home, project_root, implicit)` | nothing new |
| `scope_banner` | new helper, `err=` arg, implicit-project only | `click` |
| 6 read verbs | unpack 4th element, call `scope_banner` pre-output (`list --json` passes `err=True`) | the two above |
| `update_cmd` + `reset_cmd` refusals | reworded strings | — |

## Error handling

- Banner never raises and never changes exit codes — it is advisory output.
- Empty project lock (`count == 0`) still banners on the implicit path; that is
  still the surprising implicit-project case (the lock *file* exists — that is
  what selected project scope — it just has no entries). It does not collide
  with the existing explicit-`-p`-empty hint, which only fires when
  `project_flag` is set (i.e. `implicit=False`). The composed output for a bare
  `skill list` over an empty project lock is the banner line
  (`… (0 skills). Pass -g for the global library.`) followed by
  `(no skills installed)` — the banner adds *why* (you are in an empty project
  scope, not global), which is the intended signal, not noise.

## Out of scope

- `agent`, `mcp`, `pi_extension` (follow-up issues — same pattern, same fix).
- Changing the scope-resolution rules themselves (#210 behaviour stands).
- Banner on implicit-**global** resolution.

## Test surface

- `scope_and_roots` returns the correct `implicit` across all four branches
  (explicit `-g`, explicit `-p`, implicit→project, implicit→global).
- `scope_banner`: prints on implicit-project; silent on implicit-global,
  explicit `-p`, explicit `-g`; singular/plural noun; `count == 0` still prints;
  `err=True` routes to stderr, default routes to stdout. (Tests use a bare
  `CliRunner()` — Click 8.2+ separates `result.stdout`/`result.stderr` by
  default; there is **no** `mix_stderr` constructor argument.)
- `skill list --json` stdout parses as JSON with the banner present on
  **stderr** (the only stderr case).
- For human verbs (`status`/`update`/etc.) the banner is on **stdout**
  (`result.stdout`), inline with the verb output.
- `update` **and** `reset` monorepo-refusal wording asserted (both reworded).
- End-to-end: bare `skill update` from a cwd with a monorepo-backed project lock
  prints the project banner before the per-skill lines on stdout.
```

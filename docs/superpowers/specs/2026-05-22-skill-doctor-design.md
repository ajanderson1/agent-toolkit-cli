# `skill doctor` + TUI cell-info modal

Status: draft · 2026-05-22

## Problem

The TUI (v2.3.1, global scope) cannot repair v2.1→v2.2 migration drift. Concrete
case: `journal` skill at global scope.

On-disk state (after upgrading to v2.2 without migrating):

```
~/.agent-toolkit/skills/journal      ← real git tree (v2.2 library canonical)
~/.agents/skills/journal             ← real directory (should be: symlink → library)
~/.claude/skills/journal             ← symlink → ~/.agents/skills/journal (stale; should point to library)
```

The Claude Code cell renders `!` (drift glyph: `link.is_symlink()` true but
`link.resolve() != canonical.resolve()`). Toggling the cell queues a `link`
op (`cell.linked == False`). On apply, `skill_install.apply()` raises:

```
InstallError: journal/claude-code: conflicting symlink at
  /Users/<u>/.claude/skills/journal: points to /Users/<u>/.agents/skills/journal,
  expected /Users/<u>/.agent-toolkit/skills/journal
```

The check is intentional — it refuses to silently overwrite a symlink pointing
somewhere unexpected, in case it was deliberate. But that means a drifted cell
is **un-fixable from the TUI**: the `!` toggle always queues `link`, which
always fails the safety check.

## Solution

Add a `skill doctor` CLI command that diagnoses installation drift and offers
to repair it with explicit per-issue confirmation. Add an `i` keybinding to
the TUI's `SkillGrid` that opens a state-aware info modal — for drifted cells
the modal shows the exact `skill doctor …` command to run.

## CLI: `skill doctor`

### Synopsis

```
agent-toolkit-cli skill doctor [SLUG]... [-g/--global] [-p/--project] [--no-fix]
```

### Behavior

- No `SLUG` → scan every slug in the lock for the chosen scope.
- One or more `SLUG`s → scan only those.
- `-g/--global`, `-p/--project` flags match `list`/`status`/`update`/`push`.
  Default scope is **project** (consistent with skills.sh and our existing
  read-only commands).
- `--no-fix` → diagnose only; never prompt, never mutate.

### Output

```
$ agent-toolkit-cli skill doctor -g

journal · drifted_symlink (global)
  path:   /Users/<u>/.claude/skills/journal
  detail: symlink points to /Users/<u>/.agents/skills/journal,
          expected /Users/<u>/.agent-toolkit/skills/journal
  fix:    rm /Users/<u>/.claude/skills/journal && \
          ln -s /Users/<u>/.agent-toolkit/skills/journal /Users/<u>/.claude/skills/journal
  apply? [y/N/q]: y

journal · wrong_type_bundle (global)
  path:   /Users/<u>/.agents/skills/journal
  detail: expected symlink to library canonical; found directory
  fix:    mv /Users/<u>/.agents/skills/journal{,.bak-doctor-20260522} && \
          ln -s /Users/<u>/.agent-toolkit/skills/journal /Users/<u>/.agents/skills/journal
  apply? [y/N/q]: n

summary: 2 findings, 1 fixed, 1 skipped
```

Exit code: `0` if no findings or all findings fixed; `1` if any finding
skipped or remains. Matches `update`'s `had_conflict` pattern.

### Checks

All categories below run on every invocation. (`stale_lock` is folded into
`missing_canonical` — see table — so there are 7 distinct finding kinds.)
Findings are reported in fixed order (slug, then kind).

| Kind                   | Detection                                                                                            | Fix                                                                                |
| ---                    | ---                                                                                                  | ---                                                                                |
| `missing_canonical`    | slug in lock; canonical dir absent                                                                   | re-clone from `lock.entry.source`; OR remove lock entry. User picks via two prompts in sequence — `re-clone? [y/N]`, then if N: `remove lock entry? [y/N]`. Only one `Finding` is emitted per `(slug, scope)` in this state. |
| `stale_lock`           | _not emitted as its own finding_ — folded into `missing_canonical` above                             | —                                                                                  |
| `drifted_symlink`      | projection link `is_symlink()` true; `resolve()` not in `{canonical, library_canonical}`             | `unlink` then `symlink_to(canonical)`                                              |
| `wrong_type_bundle`    | global scope only; `~/.agents/skills/<slug>` exists as a real dir (not symlink), library exists      | move dir to `<path>.bak-doctor-<YYYYMMDD>`; `symlink_to(library)`                  |
| `orphan_symlink`       | projection link `is_symlink()` true; target does not exist                                           | unlink                                                                             |
| `foreign_symlink`      | projection link `is_symlink()` true; `resolve()` outside `library_root()` (global scope) or outside `<project>/.agents/skills/` (project scope). Links pointing at a *different* slug's canonical within those roots still count as foreign. | report-only by default; `--repair-foreign` flag unlinks |
| `dirty_tree`           | canonical exists, is a git repo, working tree dirty                                                  | report-only (already surfaced in `skill status`)                                   |
| `lock_source_mismatch` | canonical is a git repo; `lock.entry.source` doesn't match `git remote get-url origin` (normalised)  | report-only; remediation is `skill remove <slug> && skill add <new-source>`        |

`foreign_symlink` is conservative — a user may have intentionally pointed
their `~/.claude/skills/<slug>` at something hand-rolled. Doctor reports it
but doesn't touch it without `--repair-foreign`.

## Engine module: `skill_doctor.py`

New file `src/agent_toolkit_cli/skill_doctor.py`. Pure-ish library with these
public symbols.

```python
@dataclass(frozen=True)
class FixAction:
    description: str           # "Remove stale symlink and re-link to library"
    shell_preview: str         # "rm <a> && ln -s <b> <a>" — for user display only
    apply: Callable[[], None]  # the actual fix; raises on failure

@dataclass(frozen=True)
class Finding:
    kind: Literal[
        "missing_canonical", "drifted_symlink",
        "wrong_type_bundle", "orphan_symlink", "foreign_symlink",
        "dirty_tree", "lock_source_mismatch",
    ]
    slug: str
    scope: Scope
    path: Path
    detail: str
    fix_action: FixAction | None   # None = report-only

def diagnose(
    *, slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    repair_foreign: bool = False,
) -> list[Finding]: ...
```

`diagnose()` is pure (reads lock + filesystem; no mutation). Each `Finding`
carries its own `apply` closure so the CLI just invokes
`finding.fix_action.apply()` after `y`. The TUI never invokes fixes — it only
references `skill doctor` by name.

`apply` closures are responsible for being idempotent: a second `apply()`
call after a fix should detect that the situation no longer matches the
finding (e.g., the symlink no longer exists or now points to the right
place) and no-op. This keeps the contract simple for callers that might
re-diagnose between fixes.

## CLI command: `skill_doctor_cmd`

New file `src/agent_toolkit_cli/commands/skill/doctor_cmd.py`. Thin wrapper:

```python
@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt.")
@click.option("--repair-foreign", is_flag=True,
              help="Allow fixing foreign symlinks (non-default).")
@click.pass_context
def doctor_cmd(ctx, slugs, global_, project_flag, no_fix, repair_foreign):
    scope, home, project_root = scope_and_roots(global_, project_flag, ...)
    findings = diagnose(
        slugs=slugs or None, scope=scope,
        home=home, project=project_root,
        repair_foreign=repair_foreign,
    )
    if not findings:
        click.echo("✓ all clean")
        return
    fixed = skipped = 0
    for f in findings:
        click.echo(_format_finding(f))
        if f.fix_action is None or no_fix:
            skipped += 1
            continue
        ans = click.prompt("  apply?", default="N",
                           type=click.Choice(["y", "N", "q"]))
        if ans == "y":
            try:
                f.fix_action.apply()
                fixed += 1
            except Exception as exc:
                click.echo(f"  fix failed: {exc}")
                skipped += 1
        elif ans == "q":
            break
        else:
            skipped += 1
    click.echo(f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped")
    if skipped > 0 or fixed < len(findings):
        ctx.exit(1)
```

Wire into `__init__.py` via `skill.add_command(doctor_cmd)`.

## TUI: `i` cell-info modal

### Keybinding

Add to `SkillGrid`:

```python
BINDINGS = [
    Binding("space", "toggle_cell", "Toggle", priority=True),
    Binding("a", "toggle_column", "All/None", priority=True),
    Binding("i", "info", "Info", priority=True),
]
```

### Modal

New `CellInfoScreen(ModalScreen)` in `src/agent_toolkit_tui/screens/cell_info.py`
(creating the `screens/` subpackage if absent). Same dismiss-on-escape pattern
as `ConfirmDiscardScreen`.

Construction signature:

```python
CellInfoScreen(
    title: str,            # "{slug} · {agent} @ {scope}"
    body_markup: str,      # Rich-markup string with paths, doctor command, etc.
)
```

`action_info()` reads `table.cursor_coordinate`, derives the row's `SkillRow`
and the column's agent (or `None` for slug/state columns), looks up the
`SkillCell`, and computes `body_markup` from a state→template map.

### Content by cell state

For agent cells:

| Cell state                     | Body                                                                                                                                              |
| ---                            | ---                                                                                                                                               |
| `drift` (`!`)                  | `Symlink drift.` <br> `points to: <resolved>` <br> `expected:   <canonical>` <br> `` <br> `Fix:` <br> `agent-toolkit-cli skill doctor <slug> <-g\|-p>` |
| `linked` (`✔`)                | `Linked.` <br> `<projection-path> → <canonical>`                                                                                                  |
| `unlinked` (`☐`) no-pending  | `Not linked. Press space to queue link.`                                                                                                          |
| pending link (`+`)             | `Pending: link <projection-path> → <canonical>.` <br> `Press ^s to apply.`                                                                        |
| pending unlink (`-`)           | `Pending: unlink <projection-path>.` <br> `Press ^s to apply.`                                                                                    |
| `skipped` (`●`)               | `Universal agent — no symlink needed.` <br> `Skill lives at <canonical>.`                                                                          |

For slug + state columns:

| Column     | Body                                                                                                                                              |
| ---        | ---                                                                                                                                               |
| `slug`     | `Skill <slug>.` <br> `Source: <source>` <br> `Ref: <ref>` <br> `Canonical: <canonical>` <br> `State: <state>`                                     |
| `state`    | `<state>` line plus a state-specific hint (e.g., for `missing`: "library entry exists but directory is gone — run `skill doctor <slug>` to repair") |

The exact `-g`/`-p` flag in the doctor command line is chosen from the
current TUI scope, so the user can copy-paste verbatim. Modal renders the
command in a single Rich-markup `[b]…[/]` block on its own line for clean
copy-paste.

### Out of scope for this change

- Mouse-hover affordance (Textual's hover model on `DataTable` cells is not
  reliable across terminals; keyboard `i` is the only entry point).
- Auto-execution of doctor from the TUI (deliberate: keeping fixes CLI-only
  forces the user to acknowledge the change in a non-interactive context where
  the prompts and shell preview are visible).

## Testing

### Unit (`tests/test_cli/test_skill_doctor.py`)

For each finding kind, build a `tmp_path` fixture that reproduces the
condition (drifted symlink, missing canonical, real dir at bundle path,
dirty tree, …). Assert:

- `diagnose()` returns exactly the expected `Finding` (right `kind`, `slug`,
  `path`, `detail`).
- Calling `finding.fix_action.apply()` brings the filesystem to the expected
  state (e.g., for `drifted_symlink`, link now resolves to canonical).
- A second `apply()` is a no-op (idempotency).

### Integration (`tests/test_cli/test_cli_skill_doctor.py`)

Drive the Click command via `CliRunner` with the same fixtures:

- `--no-fix` → exit code 1, output lists all findings, filesystem unchanged.
- `--no-fix` against a clean tree → exit 0, output `✓ all clean`.
- Default + simulated `y` responses → fixes applied, exit 0.
- Default + `n` responses → exit 1, filesystem unchanged.
- `q` mid-loop → remaining findings untouched, exit 1.
- `--repair-foreign` → `foreign_symlink` becomes fixable (otherwise report-only).

### TUI (`tests/test_tui/test_cell_info.py`)

Use `App.run_test()` (Textual's test harness) to:

- Position cursor on each cell state; press `i`; assert modal pushed.
- Assert modal body contains the expected substrings (path, doctor command,
  correct scope flag).
- Press Escape; assert modal dismissed.

## Out of scope (separately tracked)

1. **Realigning `install`/`uninstall` scope flags.** Currently they use
   `--scope global|project` defaulting to global; everything else uses
   `-g/-p` defaulting to project. Worth aligning, but a separate PR.
2. **Cross-scope doctor.** A single invocation handles one scope. Users with
   drift in both scopes run twice: `skill doctor` then `skill doctor -g`.
3. **Auto-migration on startup.** The TUI / CLI does not auto-run doctor when
   v2.1-shaped state is detected. Doctor is the explicit, opt-in migration.
4. **Network-touching repairs.** `missing_canonical` fixes re-clone from the
   lock's recorded source URL; we do not validate the remote is reachable
   before prompting — if the clone fails, the prompt loop reports it and
   moves on.

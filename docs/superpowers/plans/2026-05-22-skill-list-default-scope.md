# Plan — skill list default scope

## 1. `_common.scope_and_roots`

Add an optional `read_only: bool = False` parameter. When `True` and neither
flag is set, look for `<ctx_project or cwd>/skills-lock.json`:

- Present → return `("project", None, project_root)`.
- Absent → return `("global", Path.home(), None)`.

When `read_only=False`, behave unchanged.

## 2. Wire `list_cmd` and `status_cmd`

Pass `read_only=True` from `list_cmd.py` and `status_cmd.py`. No other caller
changes.

## 3. Empty-result messaging

- `list_cmd._emit_table`: if `scope == "project"` and `project_flag` was
  explicit and lock is empty → print the hint instead of `(no skills installed)`.
  Easiest path: detect "explicit -p" by passing `project_flag` through, or by
  checking the resolved lock path's existence.
- `status_cmd`: same shape when `-p` is explicit, no slugs, and no project lock.

## 4. Tests

Add to `tests/test_cli/test_cli_skill_list.py`:

- `test_skill_list_no_flag_outside_project_shows_global` — add a skill globally
  (no `--project` pointer), `cwd` is `tmp_path` with no `skills-lock.json`, run
  `skill list` (no flag), assert slug appears.
- `test_skill_list_project_flag_outside_project_shows_hint` — run
  `skill list -p` in `tmp_path` without a project lock, assert hint text.
- `test_skill_list_no_flag_inside_project_uses_project_lock` — pre-create a
  `skills-lock.json` in `cwd` and assert that scope wins.

Mirror two of those in `test_cli_skill_status.py`:

- `test_skill_status_no_flag_outside_project_uses_global` — add a global skill,
  run `skill status <slug>` from a `cwd` with no project lock, assert
  `clean`/`dirty` rather than `(not in lock)`.

## 5. Don't regress

- Confirm `lefthook` pre-commit (`uv run pytest -q`) still green.
- Existing tests already use explicit `-g` / `-p` flags + `--project`, so they
  remain deterministic.

## 6. Docs touch

- `epilog` strings in `list_cmd` and `status_cmd`: clarify "default: global
  when no project lock in cwd, else project".

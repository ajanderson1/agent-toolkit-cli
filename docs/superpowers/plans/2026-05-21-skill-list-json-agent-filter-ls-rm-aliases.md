# Implementation plan — `skill list --json`, `--agent` filter, `ls`/`rm` aliases

Issue: #169 · Spec: `docs/superpowers/specs/2026-05-21-skill-list-json-agent-filter-ls-rm-aliases-design.md`

Mode: `--ship-it` (no plan-acceptance gate; build proceeds via
`superpowers:subagent-driven-development`).

## Pre-flight context

- This is a Click-based Python CLI. Use `uv run pytest -q` (lefthook also
  runs it on pre-commit).
- The v2.X skill subcommand surface lives at
  `src/agent_toolkit_cli/commands/skill/` (a package). Do **not** edit the
  stale untracked `src/agent_toolkit_cli/commands/skill.py`.
- Sister flow #170 is editing the same package; conflicts are possible at
  `commands/skill/__init__.py`. Budget one rebase retry.
- The repo has `bare = true` in `.git/config` for the main worktree. We are
  inside a `git worktree add` worktree, so `git` works normally here. Do
  not touch the bare flag.

## Task graph

Tasks are sequential — each builds on the previous and lands one
focused commit. No parallel subagents (the change is small and centred on
two files).

### Task 1 — write failing tests for JSON output

Files added: `tests/test_cli/test_cli_skill_list_json.py`

Tests (red first; mirror the test plan in the spec):

1. `test_skill_list_json_empty_lock_emits_array` — fresh tmp library →
   `skill list --json -g` exits 0, stdout parses to `[]`.
2. `test_skill_list_json_shape_keys` — seed one skill via `skill add` +
   `skill install --agents claude-code`, then `skill list --json -g` →
   exactly one object with keys `{slug, source, ref, upstream_sha,
   local_sha, scope}`. Assert `scope == "global"`.
3. `test_skill_list_json_full_sha_no_short_form` — assert
   `len(obj["upstream_sha"]) > 7` when seeded with a real SHA (i.e. we are
   not slicing `[:7]` like the human table).
4. `test_skill_list_json_sorted_by_slug` — seed `b-skill` and `a-skill`,
   assert array order is `[a-skill, b-skill]`.

Fixtures reused from `tests/conftest.py` (`git_sandbox`) and existing
patterns in `test_cli_skill_list.py`.

**Verify red:** `uv run pytest tests/test_cli/test_cli_skill_list_json.py -x`
must fail with “unrecognised arguments” / missing `--json` flag.

### Task 2 — implement `--json` (make Task 1 green)

Edit: `src/agent_toolkit_cli/commands/skill/list_cmd.py`

Changes:

- Add `--json` Click flag (`is_flag=True`, dest `as_json`).
- Refactor body into two private helpers `_emit_table(...)` and
  `_emit_json(...)` that take `(lock, slugs, scope)` (and `agent` for the
  table’s “no skills linked” message in Task 3).
- `_emit_json`: build a list of dicts with snake_case keys per spec, sort
  by slug, `click.echo(json.dumps(out))`.
- `_emit_table`: same output as today (slug, source, ref, short-sha
  columns); add the empty-lock / empty-filter messages from the spec.
- Add `import json` at top.

**Verify green:** `uv run pytest tests/test_cli/test_cli_skill_list_json.py -x`
all pass; previous `test_cli_skill_list.py` still green.

### Task 3 — write failing tests for `-a/--agent` filter

Files added: extend `tests/test_cli/test_cli_skill_list_json.py` with
filter tests (single file, no extra import noise):

1. `test_skill_list_agent_filter_keeps_only_linked` — add two skills, install
   `demo-a` for `claude-code`, install `demo-b` for `pi`; assert
   `skill list -a claude-code -g` (text mode) lists only `demo-a`.
2. `test_skill_list_agent_filter_unknown_agent_errors` —
   `skill list -a nonsense -g` exits non-zero with `unknown agent:` in
   stderr/stdout.
3. `test_skill_list_agent_filter_with_json` — combine `-a claude-code
   --json -g`, parse JSON, assert single-element array with the expected
   slug.
4. `test_skill_list_agent_filter_universal_token` — install with
   `--agents universal` at global scope, assert `-a universal` keeps the
   skill.

**Verify red:** the four tests fail with “no such option: -a” or
“unknown agent”.

### Task 4 — implement `-a/--agent` filter (make Task 3 green)

Edit: `src/agent_toolkit_cli/commands/skill/list_cmd.py`

Changes:

- Add `-a/--agent <name>` Click option (`default=None`).
- After reading the lock, validate agent name (catalog or `universal`)
  before iterating, raising `click.UsageError("unknown agent: <name>")`.
- Filter `sorted(lock.skills)` through
  `agent_toolkit_cli.skill_install._current_linked_agents` per spec.
- Import the helper at the top of the module.

**Verify green:** both new test files pass; old list test still passes.

### Task 5 — write failing tests for `ls` / `rm` aliases

Files added: `tests/test_cli/test_cli_skill_aliases.py`

Tests:

1. `test_skill_ls_is_list` — invoke `skill list -g` and `skill ls -g` against
   the same seeded lock; assert stdout equal.
2. `test_skill_rm_is_remove` — add a skill, then `skill rm demo --force`;
   assert lock entry gone and library dir absent (mirroring
   `test_cli_skill_remove.py` patterns).
3. `test_skill_ls_shows_up_in_group_help` — `skill --help` output contains
   both `list` and `ls`, and both `remove` and `rm`.

**Verify red:** `ls` and `rm` are unknown subcommands.

### Task 6 — register aliases (make Task 5 green)

Edit: `src/agent_toolkit_cli/commands/skill/__init__.py`

Changes (place near existing `skill.add_command(list_cmd)` at the end of
the file):

```python
skill.add_command(list_cmd, name="ls")
skill.add_command(remove_cmd, name="rm")
```

`remove_cmd` is defined in this file via `@skill.command("remove")` — we
reference the bound function. If naming the underlying function is awkward
because of the decorator, use the explicit form:

```python
skill.add_command(skill.commands["remove"], name="rm")
```

(The `Group.commands` dict is the registered command map; `name="rm"`
simply adds a second key pointing at the same command object — no
duplicate logic.)

**Verify green:** all three alias tests pass.

### Task 7 — docs + run-and-confirm

Edit: `docs/agent-toolkit/cli.md` (and `AGENTS.md` code-map section if
needed) — add one line each for `ls`, `rm`, `--json`, `--agent` so the
human-readable reference is in sync. If `cli.md` does not yet exist with a
list section, skip this step rather than scaffold prose; the help text is
the source of truth.

Manual sanity:

```bash
uv sync --all-extras
uv run agent-toolkit-cli skill --help          # ls + rm visible
uv run agent-toolkit-cli skill list --json -g   # JSON to stdout
uv run agent-toolkit-cli skill ls -g            # alias works
```

(Output captured to `assets/verification/169/run.log` during the Verify
step, not here.)

## Pre-flight CI

After every task green:

```bash
uv run pytest -q
```

Workflow at `.github/workflows/ci.yml` (parsed by flow Step 8) runs the
same. No lint command is currently in CI for this repo (no `ruff`/`biome`
target — see `~/.conventions/conventions/default-stack.md` § Manifest
detection fallback).

## Out of scope (do not touch this run)

- camelCase JSON variant.
- `find`, `restore`, `upgrade` alias, `-a` on `install`/`remove`.
- Anything in `commands/skill.py` (stale untracked legacy file).
- Bare-flag fix in `.git/config` of the parent repo.

## Acceptance

Tasks 1–6 green, Task 7 docs ack’d, `uv run pytest -q` all green, the
three manual commands above produce the expected output.

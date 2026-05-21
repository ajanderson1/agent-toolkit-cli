# skill: `list --json`, `--agent` filter, and `ls`/`rm` aliases

Status: drafted (auto, --ship-it)
Issue: #169
Milestone: v2.3.0

## Goal

Align our `skill` CLI surface with `vercel-labs/skills`' npx surface so muscle
memory carries over:

1. `skill list --json` emits a JSON array suitable for piping into `jq`.
2. `skill list -a/--agent <name>` filters the listing to skills currently
   symlinked into that named agent.
3. `skill ls` and `skill rm` are registered as aliases that invoke the same
   callbacks as `list` and `remove`.

The verbs already do the right thing — this PR is **surface alignment**, not
behaviour change.

## Non-goals

Tracked separately (see issue #169 “Out of scope”):

- `find`, `restore` (their `experimental_install`).
- `upgrade` alias for `update`.
- `-a/--agent` flag-name alignment on `install`/`remove`.

## Background

`npx -y skills list --json` prints a JSON array, and `npx -y skills ls -a <agent>`
filters by an installed agent. Our v2.X `skill list` (in
`src/agent_toolkit_cli/commands/skill/list_cmd.py`) currently prints a
tab-separated four-column table:

```
<slug>\t<source>\t<ref>\t<short-sha>
```

It accepts `-g/--global` and `-p/--project` to choose the lock. There is no
JSON mode and no agent filter. The `remove` command is registered as `remove`
only — no `rm` alias.

## Definition of done (from #169)

- `skill list --json` prints a JSON array of installed skills with `slug`,
  `source`, `ref`, `upstream_sha`, `local_sha`, `scope`.
- `skill list -a/--agent <name>` filters output to skills currently symlinked
  into that agent.
- `skill ls` and `skill rm` invoke the same callbacks as `list` and `remove`.
- Tests cover the JSON shape, the agent filter, and both aliases.

## Surface

### `skill list [-g|-p] [-a/--agent <name>] [--json]`

Flags (additions in **bold**):

| Flag                          | Behaviour                                                                 |
|-------------------------------|---------------------------------------------------------------------------|
| `-g/--global`                 | Read the global library lock (unchanged).                                 |
| `-p/--project`                | Read the project lock at `<project>/skills-lock.json` (unchanged).        |
| **`-a/--agent <name>`**       | Keep only skills currently symlinked into that named agent at the scope.  |
| **`--json`**                  | Emit a JSON array to stdout instead of the human table.                   |

`<name>` must be in the agent catalog (`AGENTS`) **or** the special token
`universal`. Unknown names raise `click.UsageError` with the standard
`unknown agent: <name>` message used elsewhere in the package.

If filtering produces an empty list:

- Human mode: `(no skills installed)` for empty lock, otherwise `(no skills
  linked into <agent>)`.
- JSON mode: empty array `[]` with newline, exit 0.

### JSON shape

A JSON array of objects, sorted by `slug` ascending, written via
`click.echo(json.dumps(...))`. One object per skill in the (possibly filtered)
lock:

```json
[
  {
    "slug": "demo",
    "source": "octo/demo-skill",
    "ref": "main",
    "upstream_sha": "abc1234abc1234abc1234abc1234abc1234abc12",
    "local_sha": "abc1234abc1234abc1234abc1234abc1234abc12",
    "scope": "global"
  }
]
```

Field rules:

- `slug` — lock key.
- `source` — `LockEntry.source` as stored.
- `ref` — `LockEntry.ref` or `null` (never coerced to `"main"`; the human
  table coerces for display only).
- `upstream_sha` — full SHA from the lock or `null` (no shortening).
- `local_sha` — full SHA or `null`.
- `scope` — `"global"` or `"project"`, matching whichever lock was read.

We deliberately use snake_case in keys to match the DoD wording in #169. The
TypeScript surface uses camelCase, but we treat that as a separate alignment
question and don’t conflate it with this PR — see issue #169 “Out of scope”.

### Aliases — `ls` and `rm`

Implemented at the Click group level by registering the same command object
under a second name:

```python
skill.add_command(list_cmd, name="ls")
skill.add_command(remove_cmd, name="rm")
```

This shares the callback (no duplicate code), shares help text, and respects
any future flag we add to `list` or `remove`. `--help` for `ls`/`rm` will show
the same text as `list`/`remove`. We accept that minor surface oddity rather
than introduce a hand-rolled alias wrapper.

## Agent filter — semantics

When `-a/--agent <name>` is passed:

1. Validate `<name>` (catalog or `universal`).
2. Read the lock for the resolved scope.
3. For each lock entry, call the existing helper
   `skill_install._current_linked_agents(slug=…, scope=…, home=…, project=…)`
   to compute which agents currently have a symlink pointing at the canonical.
4. Keep only entries whose linked-agents tuple contains `<name>`.

This reuses the canonical helper that already powers `skill status` and the
TUI grid — no new traversal logic.

`home` is `Path.home()` at global scope (matching `scope_and_roots`), `None`
at project scope. `project` is the resolved project root at project scope,
`None` at global.

## Edge cases

- **Empty lock + filter**: empty list / `(no skills installed)`. Human-mode
  message reuses the existing one to avoid churn for the common case.
- **Filter excludes everything**: empty array in JSON; `(no skills linked
  into <agent>)` in human mode.
- **Unknown agent name**: `click.UsageError("unknown agent: <name>")`.
- **`universal` filter**: returns skills whose `~/.agents/skills/<slug>`
  bundle symlink (global) or project canonical (project) exists — exactly
  what `_current_linked_agents` already reports for the `universal` token.
- **`ls` / `rm` discoverability**: `skill --help` will list `list`, `ls`,
  `remove`, `rm` as separate-looking entries; the Click group lists every
  registration. Acceptable.

## Test plan (TDD)

New test file `tests/test_cli/test_cli_skill_list_json.py`:

- `test_skill_list_json_empty_lock_emits_array` — empty lock → `[]`.
- `test_skill_list_json_shape_keys` — one skill, assert keys
  `{slug, source, ref, upstream_sha, local_sha, scope}` and values match
  the seeded `LockEntry`.
- `test_skill_list_json_full_sha_no_short_form` — value of `upstream_sha`
  is the full string (no `[:7]` shortening like the human table).
- `test_skill_list_json_sorted_by_slug` — multiple skills come out sorted.
- `test_skill_list_agent_filter_keeps_only_linked` — install one skill into
  `claude-code`, install another only into `pi`, `--agent claude-code` keeps
  the first, drops the second.
- `test_skill_list_agent_filter_unknown_agent_errors` — bogus name →
  `UsageError`.
- `test_skill_list_agent_filter_with_json` — agent filter + `--json`
  composes; result is JSON-of-filtered-list.
- `test_skill_list_agent_filter_universal_token` — `--agent universal`
  returns skills present in `~/.agents/skills/<slug>` at global scope.

New test file `tests/test_cli/test_cli_skill_aliases.py`:

- `test_skill_ls_is_list` — `skill ls` produces the same stdout as
  `skill list` for the same fixture lock.
- `test_skill_rm_is_remove` — `skill rm <slug> --force` removes the skill
  exactly as `skill remove <slug> --force` would (assert lock entry gone +
  library dir removed).

Existing tests in `test_cli_skill_list.py` continue to pass — surface change
is purely additive.

## Implementation sketch

`src/agent_toolkit_cli/commands/skill/list_cmd.py`:

```python
@click.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("-a", "--agent", "agent", default=None,
              help="Filter to skills currently symlinked into this agent.")
@click.option("--json", "as_json", is_flag=True,
              help="Emit JSON array instead of the human table.")
@click.pass_context
def list_cmd(ctx, global_, project_flag, agent, as_json):
    scope, home, project_root = scope_and_roots(...)
    if agent is not None and agent != "universal" and agent not in AGENTS:
        raise click.UsageError(f"unknown agent: {agent}")
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))

    slugs = sorted(lock.skills)
    if agent is not None:
        slugs = [
            s for s in slugs
            if agent in _current_linked_agents(
                slug=s, scope=scope, home=home, project=project_root,
            )
        ]

    if as_json:
        _emit_json(lock, slugs, scope)
        return

    _emit_table(lock, slugs, agent)
```

Two private helpers — `_emit_json` and `_emit_table` — keep the command body
small and let the tests target them via the CLI rather than reaching in.

`src/agent_toolkit_cli/commands/skill/__init__.py`:

```python
skill.add_command(list_cmd)
skill.add_command(list_cmd, name="ls")
skill.add_command(remove_cmd, name="rm")
```

(`list_cmd` is already imported; `remove_cmd` is declared in the same file
via `@skill.command("remove")` so we additionally call
`skill.add_command(remove_cmd, name="rm")` after the decorator.)

## Risk / blast radius

- Pure additive at the CLI surface. No behaviour change to existing flags.
- Sister flow on #170 (`skill reset`) touches `commands/skill/__init__.py`.
  We add two `add_command(..., name=)` calls — no overlap with reset
  registration. Rebase-and-retry once if `auto-merge` collides.
- No lockfile schema change.

## References

- Issue: https://github.com/ajanderson1/agent-toolkit-cli/issues/169
- Helper reused: `agent_toolkit_cli.skill_install._current_linked_agents`
- Lock model: `docs/agent-toolkit/skill-lock.md`

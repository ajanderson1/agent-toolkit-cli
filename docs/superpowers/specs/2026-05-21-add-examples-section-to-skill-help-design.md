# Design — Add `Examples:` section to `skill --help` (#168)

## Goal

`agent-toolkit-cli skill --help` ends with a curated `Examples:` section modelled after `npx -y skills --help`. Each `skill <subcmd> --help` includes at least one runnable example as well, so users can copy-paste real invocations instead of assembling syntax from prose.

## Context

`skills.sh` ends its top-level `--help` with ~20 copy-pasteable lines that cover the common shapes of every subcommand. We don't do this — we list subcommands and options but stop short of concrete invocations, so a new user has to read each `skill <subcmd> --help` and assemble the call themselves.

Click already supports a per-command `epilog=` keyword that renders below the options block, so this is a content-only change to the existing decorators in:

- `src/agent_toolkit_cli/commands/skill/__init__.py` — `@click.group()` `skill`, plus `add`, `install`, `uninstall`, `remove` inline commands.
- `src/agent_toolkit_cli/commands/skill/list_cmd.py`
- `src/agent_toolkit_cli/commands/skill/status_cmd.py`
- `src/agent_toolkit_cli/commands/skill/update_cmd.py`
- `src/agent_toolkit_cli/commands/skill/push_cmd.py`

The deprecated pre-v2 commands (`check`, `link`, `doctor`, ...) are gone — no examples should reference them. The frozen v1 surface lives at the `v1.0.0` tag and is **out of scope** for this issue.

## Examples to ship (top-level `skill --help` epilog)

Modelled after `skills.sh` ordering: introduce each verb with the most common invocation, then surface useful variants. Real commands only — no placeholders that don't resolve.

```
Examples:
  # Add a skill to the global library (clone only — no symlinks yet)
  $ agent-toolkit-cli skill add anthropics/skills

  # Pin to a branch or tag
  $ agent-toolkit-cli skill add anthropics/skills --ref main
  $ agent-toolkit-cli skill add anthropics/skills --ref v1.2.0

  # Override the local slug
  $ agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal

  # Make it visible to a specific agent (claude-code) or all universal agents
  $ agent-toolkit-cli skill install journal --agents claude-code
  $ agent-toolkit-cli skill install journal --agents universal
  $ agent-toolkit-cli skill install journal --agents all

  # Project-scope install (canonical lives under <project>/.agents/skills/)
  $ agent-toolkit-cli skill install journal --agents claude-code -p

  # List, status, update, push
  $ agent-toolkit-cli skill list                       # global by default
  $ agent-toolkit-cli skill list -p                    # project scope
  $ agent-toolkit-cli skill status                     # show clean/dirty/missing per skill
  $ agent-toolkit-cli skill update                     # fetch + merge upstream for all
  $ agent-toolkit-cli skill update journal             # one skill only
  $ agent-toolkit-cli skill push journal               # self-improvements upstream

  # Take down agent visibility but keep the canonical clone
  $ agent-toolkit-cli skill uninstall journal --agents claude-code

  # Remove a skill completely (interactive picker if no slug given)
  $ agent-toolkit-cli skill remove journal
  $ agent-toolkit-cli skill remove                     # interactive
  $ agent-toolkit-cli skill remove journal --force     # discard dirty changes
```

## Per-subcommand examples

Each subcommand's `epilog=` carries 1–3 example invocations focused on that verb. The goal is enough to get unstuck without scrolling back to the top-level help.

| Subcommand | Epilog examples (numbered for plan reference) |
|---|---|
| `add` | E1: `skill add anthropics/skills` · E2: `skill add anthropics/skills --ref v1.2.0` · E3: `skill add ajanderson1/journal-skill --slug journal` |
| `install` | E1: `skill install journal --agents claude-code` · E2: `skill install journal --agents universal` · E3: `skill install journal --agents claude-code -p` |
| `uninstall` | E1: `skill uninstall journal --agents claude-code` · E2: `skill uninstall journal --agents all` |
| `list` | E1: `skill list` · E2: `skill list -p` |
| `status` | E1: `skill status` · E2: `skill status journal` |
| `update` | E1: `skill update` · E2: `skill update journal` |
| `push` | E1: `skill push` · E2: `skill push journal` |
| `remove` | E1: `skill remove journal` · E2: `skill remove` (interactive) · E3: `skill remove journal --force` |

## Implementation shape

For each Click command, add an `epilog=` keyword argument containing a heredoc-style string. Click renders `epilog` below the options block automatically.

```python
@skill.command("add", epilog="""\
Examples:

  agent-toolkit-cli skill add anthropics/skills
  agent-toolkit-cli skill add anthropics/skills --ref v1.2.0
  agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal
""")
```

For the top-level `@click.group()` `skill`, the `epilog=` carries the longer block from "Examples to ship" above.

## Definition of done

- `uv run agent-toolkit-cli skill --help` ends with the `Examples:` block above.
- Each `uv run agent-toolkit-cli skill <subcmd> --help` (for `add`, `install`, `uninstall`, `list`, `status`, `update`, `push`, `remove`) ends with an `Examples:` block carrying at least one runnable example.
- Every example uses **only** currently-supported v2 commands and flags — no `check`, `link`, `doctor`, `--harness`, etc.
- No flag changes, no command renames, no restructuring of the Usage / Options / Commands sections.
- `uv run pytest -q` is green.
- A new test (`tests/test_cli_help.py` or a sibling) asserts the `Examples:` literal appears in the top-level `skill --help` output and in each subcommand's `--help` output, so the section can't silently disappear in a future refactor.

## Out of scope

- Updating the `README.md` "Commands" block (it shows a stale `--harness` flag and a stale `-g|-p` on `skill add`). Worth a follow-up issue, but not this one.
- Changing flag names, command names, or section structure.
- Adding examples to `agent-toolkit-cli --help` (top-level group) — current spec is `skill --help` and its descendants.

## Risk / non-obvious bits

- Click's `epilog` text **is dedented** but **does not preserve leading blank lines** — start with a `\n` after the triple-quote or use `epilog="""\` to control rendering. The implementation snippet above uses `epilog="""\` which puts `Examples:` on the first emitted line as intended.
- The top-level `skill --help` is invoked via the `@click.group()` decorator. Pass `epilog=` to `@click.group(epilog=...)` — same kwarg as on `@click.command`.

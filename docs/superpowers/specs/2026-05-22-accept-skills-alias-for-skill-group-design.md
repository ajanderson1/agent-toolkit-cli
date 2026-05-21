# Spec — accept `skills` as alias for `skill` command group

**Issue:** #180
**Type:** feat
**Date:** 2026-05-22

## Goal

Typing `agent-toolkit-cli skills ...` invokes the same Click group as `agent-toolkit-cli skill ...`, so muscle-memory plurals (the form used by `npx -y skills`) work without surprise.

## Context

The CLI exposes a single user-facing command group, `skill`, registered in `src/agent_toolkit_cli/cli.py` via `main.add_command(skill)`. The `skill` group already has surface aliases for its own subcommands — `ls` for `list` and `rm` for `remove` — registered at the bottom of `src/agent_toolkit_cli/commands/skill/__init__.py` to match `npx -y skills` muscle memory (#169). This issue extends the same idea one level up: alias the group itself.

## Approach

Click's `add_command` accepts a `name=` argument that overrides the command's own `name`. Registering the same `skill` group object under both `"skill"` (default) and `"skills"` (explicit) gives the CLI two surface entries pointing at the **same group instance**, so every subcommand, option, help text, and future addition is shared automatically — no parallel maintenance.

Concretely, `cli.py` already has:

```python
main.add_command(skill)
```

Add one line after it:

```python
main.add_command(skill, name="skills")
```

This mirrors the existing pattern at the subcommand level (`skill.add_command(list_cmd, name="ls")`).

## Behaviour

- `agent-toolkit-cli skills --help` → same help body as `skill --help`.
- `agent-toolkit-cli skills list` (and every other subcommand) → identical behaviour to the `skill` form.
- `agent-toolkit-cli --help` → root help lists both `skill` and `skills` as available commands (Click renders both alphabetically).
- `skill ...` invocations → unchanged. No deprecation, no warning, no migration. The singular remains canonical in docs and examples.

## Out of scope

- Renaming `skill` to `skills`. The canonical name stays singular in docs, examples, and the epilog.
- Aliasing any other root-level groups (`doctor`, `ingest`, etc. — `doctor` and `ingest` aren't user-facing groups today anyway).
- Lockfile / data-structure fields named `skills` (in `skill_lock.py`). Internal, unaffected.
- Reverse alias (`skills` → `skill`) in source files, READMEs, or shell completion scripts.

## Definition of done

- `agent-toolkit-cli skills --help` exits 0 and prints the same body as `skill --help` (modulo the command name in the usage line, which Click derives at runtime).
- `agent-toolkit-cli skills list -g` returns the same output as `skill list -g` on the same fixture.
- Existing `skill ...` invocations continue to work unchanged (all current tests still pass).
- A new CLI test in `tests/test_cli/test_cli_skill_aliases.py` covers:
  1. `skills` resolves to the same group as `skill` (`skills --help` exit 0, contains expected subcommand verbs).
  2. A representative subcommand (`skills list`) behaves identically to its `skill list` counterpart.
- Root `agent-toolkit-cli --help` lists `skills` alongside `skill`.

## Risk notes

- **Help-text inflation.** Adding a duplicate root entry doubles the visible top-level surface from one to two. Acceptable — the whole point is discoverability, and the duplicate is clearly the alias when read alongside the singular.
- **Click group identity.** Registering the same group instance twice means callbacks, options, and context are genuinely shared (Click stores commands by name in the parent's `commands` dict, but the value is the same object). No risk of state divergence.
- **Shell completion.** Click's bash/zsh completion will see both names. Both will complete subcommands. Fine.

## Why not a custom `Group` subclass?

A custom `AliasGroup` that resolves multiple names to the same command (e.g. Click's documented `AliasedGroup` recipe) would let us declare aliases inline. We don't need it for one alias — `add_command(..., name=...)` is the existing in-repo pattern (`ls`, `rm`) and matches the principle "prefer simple defaults over flexible systems." If the alias count grows, revisit.

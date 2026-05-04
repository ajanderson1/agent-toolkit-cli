# list: add `--report` for human-readable inventory output

**Issue:** [#11](https://github.com/ajanderson1/agent-toolkit-cli/issues/11)
**Date:** 2026-05-04

## Problem

Today's `agent-toolkit list` is tabular and JSON-friendly (slug + cells encoded compactly per-line). That is the right default for scanning state; it is awkward for "show me what is installed in the harness X scope" — the use case for CI logs, README screenshots, and onboarding walkthroughs. The old `claude-tui-tools` had three text-report commands (`--summary`, `--report`, `--effective`); the new CLI has none of that.

## Decision

Add `--report` to `list` as a third format alongside `text` (default tabular) and `json`. It re-uses the existing inventory pipeline (the `--format=json` data plus the cell-status logic already in `_list_json.py`); the formatter is the only new code.

`--report` and `--format` are mutually exclusive — pass either, not both.

## Output shape

Grouped: harness → scope → kind → asset entries. Per-asset line shows: slug, status, optional source path. Deterministic ordering: harnesses in `ALL_HARNESSES` order, scopes user-then-project, kinds in `ALL_KINDS` order, assets sorted by slug.

Example, single-harness inventory:

```
Asset inventory report

Toolkit:  /Users/aj/GitHub/agent-toolkit
Project:  /Users/aj/code/myproj

claude
  user
    skill
      alpha       linked    /Users/aj/GitHub/agent-toolkit/skills/alpha
      beta        unlinked
      gamma       unsupported
    agent
      (none)
  project
    skill
      alpha       linked    /Users/aj/GitHub/agent-toolkit/skills/alpha

codex
  user
    skill
      beta        unsupported
  project
    skill
      (none)
```

Empty inventory (no assets at all):

```
Asset inventory report

Toolkit:  /Users/aj/GitHub/agent-toolkit
Project:  /Users/aj/code/myproj

(no assets discovered)
```

Honour `--quiet`: suppresses only the trailing `Done.` summary line on stderr (header continues — it's the report itself, not chrome). Honour positional `KIND`/`HARNESS` filters: scope the report to matching dimensions only.

## Affected files

| File | Change |
|---|---|
| `src/agent_toolkit/commands/list.py` | Add `--report` flag (mutually exclusive with `--format=json`). When set, build inventory by calling the same data path used for `--format=json`, then dispatch to a new formatter. |
| `src/agent_toolkit/generators/list_report.py` | **Create.** Pure formatter: `(inventory_dict, project_root) -> str`. Same data shape as `--format=json` output. |
| `tests/test_list_report.py` | **Create.** Tests for the formatter against three scenarios from the issue. |
| `tests/test_cli_list.py` | Add CLI smoke tests for the flag (one per scenario). |
| `docs/agent-toolkit/cli.md` | One paragraph + example output showing `--report`. |

## Tests

Per issue body:

- **Empty inventory:** `--report` emits the header + `(no assets discovered)`.
- **Single-harness inventory:** one asset, declared for `claude` only, linked under user scope. Report shows the asset under `claude > user > skill`, marked `linked`.
- **Multi-harness multi-scope inventory:** three assets across two harnesses, mixed scopes. Output is grouped, deterministic, no harness or scope omitted.

Plus:

- `--report --format=json` is rejected with exit 2.
- `--report --quiet` suppresses `Done.` chrome but report body remains.

## Non-goals

- Markdown / HTML export — plain text only.
- Replacing the default tabular output (this is opt-in).
- Changing the JSON output shape.
- Showing "would-link" diffs — that's `diff`'s job.

## Risk

Tiny. The formatter consumes the same inventory dict the JSON path produces. Worst case the formatter produces something ugly — caught by the snapshot/string-equality tests. No mutation, no I/O, no symlinks touched.

## Determinism

The JSON path already sorts assets by `(kind, slug)`. The report path:
- iterates harnesses in `ALL_HARNESSES` (tuple order), 
- scopes in fixed order `("user", "project")`, 
- kinds in `ALL_KINDS` (tuple order),
- assets per (harness, scope, kind) sorted by slug.

This means two runs against the same repo state produce byte-identical output — diffable in CI.

# AGENTS.md — agent-toolkit-cli

This repo is the **tooling** for the `agent-toolkit` asset library. The Python CLI (`src/agent_toolkit`) and the Textual TUI (`src/agent_toolkit_tui`) live here. Asset content lives in the sibling toolkit repo.

**Data source:** `~/GitHub/agent-toolkit/` (default). Override via `--toolkit-repo` flag or `AGENT_TOOLKIT_REPO` env var. Discovery walks up from CWD looking for `.agent-toolkit-source`.

**Schema:** Bundled at `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json` (vendored from the toolkit repo's `schemas/`). The bundled copy is what the CLI validates against at runtime; the toolkit-repo copy is the SSOT humans edit. CI (`.github/workflows/schema-drift.yml`) fails on drift.

**Drift gate (toolkit repo):** `lefthook.yml` in the toolkit repo shells out to whichever `agent-toolkit` is on `$PATH`. CI in the toolkit repo installs this CLI before running pre-commit. (The `agent-toolkit` script is the Python entry point installed by `uv tool install` or `uv sync`.)

## Two-flag contract

Every subcommand observes the same two flags. The literal `--repo-root` flag and the variable name `repo_root` do not appear anywhere in this repo.

| Flag | Means | Default |
|---|---|---|
| `--toolkit-repo PATH` | The agent-toolkit SSOT (the library) | four-step order: flag → `AGENT_TOOLKIT_REPO` env → walk-up `.agent-toolkit-source` → `~/GitHub/agent-toolkit/` |
| `--project PATH` | The consumer project being acted on | `.` (CWD) |

Subcommand applicability:

| Subcommand | `--toolkit-repo`? | `--project`? |
|---|---|---|
| `check`, `fix`, `new`, `doctor`, `inventory`, `ingest` | yes | no |
| `link`, `unlink`, `list`, `diff` | yes | yes |

Internal parameter names: `toolkit_root` (when value is the SSOT) or `project_root` (when value is the consumer).

## Code map

```
src/agent_toolkit/                 Python package: validator, walker, generators,
                                   ingest, security, doctor, command implementations.
  _repo_resolution.py              Four-step resolver: resolve_toolkit_root().
  _schemas/                        Bundled v1alpha1 schema (vendored).
  schema.py                        Validator (loads bundled schema via importlib.resources).
  walker.py                        Asset discovery (path-driven, skips submodules).
  cli.py                           Click group with --toolkit-repo option.
  commands/                        check, fix, doctor, new, inventory, ingest,
                                   link, unlink, list, diff, _list_json, _yaml_edit.
  generators/                      Pure functions: (assets, repo_state) → string.
src/agent_toolkit_tui/             Textual TUI (sibling package, [tui] extra).
schemas/                           Top-level vendored schema (mirrors _schemas, used by
                                   schema-drift CI as the diff target).
docs/agent-toolkit/cli.md          Command reference (human-readable).
tests/                             pytest.
```

## Layered contract (do not invert)

1. **Schema** is the source of truth. Bundled at `src/agent_toolkit/_schemas/`.
2. **Walker** is the only thing that knows how to discover assets and parse frontmatter.
3. **Validator** enforces schema + cross-asset rules. Returns errors; does not print or exit.
4. **Commands** orchestrate (call walker → validator → generators → I/O).
5. **Generators** are pure: `(assets, repo_state) → string`.

## Development workflow

```bash
uv sync --all-extras
uv run pytest -q
uv run agent-toolkit --toolkit-repo ~/GitHub/agent-toolkit check --exit-code
```

Lefthook runs lint + tests on pre-commit. CI runs the full suite plus schema-drift and install-smoke workflows.

## Schema sync

When the toolkit-repo schema (`~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha1.json`) changes:

```bash
cp ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha1.json schemas/
cp ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha1.json src/agent_toolkit/_schemas/
diff schemas/asset-frontmatter.v1alpha1.json src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json
git add schemas src/agent_toolkit/_schemas
git commit -m "chore(schema): sync vendored copy with toolkit repo"
```

CI's schema-drift workflow will catch any forgotten sync.

## Adding a new harness / asset kind / CLI subcommand

See the spec at `docs/superpowers/specs/2026-05-03-agent-toolkit-cli-tui-split-design.md` in the toolkit repo for the layered contract and extension seams. (The spec was written there during the split; future docs may move here.)

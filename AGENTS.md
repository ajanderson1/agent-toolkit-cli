# AGENTS.md — agent-toolkit-cli

This repo is the **tooling** for the `agent-toolkit` asset library. The Python CLI (`src/agent_toolkit_cli`) and the Textual TUI (`src/agent_toolkit_tui`) live here. Asset content lives in the sibling toolkit repo.

**Data source:** `~/GitHub/agent-toolkit/` (default). Override via `--toolkit-repo` flag or `AGENT_TOOLKIT_REPO` env var. Discovery walks up from CWD looking for `.agent-toolkit-source`.

**Schema:** Bundled at `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` (vendored from the toolkit repo's `schemas/`). The bundled copy is what the CLI validates against at runtime; the toolkit-repo copy is the SSOT humans edit. The pre-commit `schema-vendor-check` hook (lefthook) ensures the two vendored copies in this repo (`schemas/` and `src/agent_toolkit_cli/_schemas/`) stay in lockstep. Drift against the toolkit-repo SSOT is caught at sync time by the procedure in "Schema sync" below.

**Drift gate (toolkit repo):** `lefthook.yml` in the toolkit repo shells out to whichever `agent-toolkit-cli` is on `$PATH`. CI in the toolkit repo installs this CLI before running pre-commit. (The `agent-toolkit-cli` script is the Python entry point installed by `uv tool install` or `uv sync`.)

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
src/agent_toolkit_cli/                 Python package: validator, walker, generators,
                                   ingest, security, doctor, command implementations.
  _repo_resolution.py              Four-step resolver: resolve_toolkit_root().
  _schemas/                        Bundled v1alpha2 schema (vendored).
  schema.py                        Validator (loads bundled schema via importlib.resources).
  walker.py                        Asset discovery (path-driven, skips submodules).
  cli.py                           Click group with --toolkit-repo option.
  commands/                        check, fix, doctor, new, inventory, ingest,
                                   link, unlink, list, diff, _list_json, _yaml_edit.
  generators/                      Pure functions: (assets, repo_state) → string.
src/agent_toolkit_tui/             Textual TUI (sibling package).
schemas/                           Top-level vendored schema (mirrors _schemas;
                                   pre-commit `schema-vendor-check` keeps both copies in lockstep).
docs/agent-toolkit/cli.md          Command reference (human-readable).
tests/                             pytest.
```

## Layered contract (do not invert)

1. **Schema** is the source of truth. Bundled at `src/agent_toolkit_cli/_schemas/`.
2. **Walker** is the only thing that knows how to discover assets and parse frontmatter.
3. **Validator** enforces schema + cross-asset rules. Returns errors; does not print or exit.
4. **Commands** orchestrate (call walker → validator → generators → I/O).
5. **Generators** are pure: `(assets, repo_state) → string`.

## Development workflow

```bash
uv sync --all-extras
uv run pytest -q
uv run agent-toolkit-cli --toolkit-repo ~/GitHub/agent-toolkit check --exit-code
```

Lefthook runs lint + tests on pre-commit (including `schema-vendor-check` to keep the two vendored schema copies in lockstep). CI runs the full suite plus the install-smoke workflow.

## Schema sync

When the toolkit-repo schema (`~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json`) changes:

```bash
cp ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json schemas/
cp ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json src/agent_toolkit_cli/_schemas/
diff schemas/asset-frontmatter.v1alpha2.json src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
git add schemas src/agent_toolkit_cli/_schemas
git commit -m "chore(schema): sync vendored copy with toolkit repo"
```

The pre-commit `schema-vendor-check` hook (lefthook) blocks any commit where the two vendored copies (`schemas/` and `src/agent_toolkit_cli/_schemas/`) diverge. There is no separate CI workflow that diffs against the toolkit-repo SSOT — that would require cross-repo read access, which the repo doesn't currently provide. Instead, the human running this procedure verifies the sync at copy time.

## Asset identity

- **Slug equality** — `metadata.name` MUST equal the on-disk slug.
- **One asset, one metadata location.** Every asset carries metadata in
  exactly one place:
  - **skill** — sidecar `skills/<slug>.toolkit.yaml` (preferred) OR inline
    frontmatter in `skills/<slug>/SKILL.md` (legacy). Never both.
  - **mcp** — sidecar `mcps/<slug>.toolkit.yaml` (post-PR-3, the only form).
  - **agent**, **command** — inline frontmatter in `<slug>.md`.
  - **hook**, **pi-extension** — dedicated `.meta.yaml` sidecar.
  - **plugin** — sidecar `plugins/<slug>.toolkit.yaml` (preferred) OR inline
    `agent_toolkit_cli` JSON key in `plugin.json` (legacy; emits a deprecation
    warning during `check`). Never both.
- **Mutex rule** — if both sidecar AND inline metadata exist for the same
  slug, `agent-toolkit-cli check` exits 2. Lefthook pre-commit blocks the
  commit until one is removed.

## Adding a new harness / asset kind / CLI subcommand

See the spec at `docs/superpowers/specs/2026-05-03-agent-toolkit-cli-tui-split-design.md` in the toolkit repo for the layered contract and extension seams. (The spec was written there during the split; future docs may move here.)

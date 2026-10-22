# AGENTS.md — agent-toolkit-cli

Python 3.12+ Click CLI and Textual TUI for six asset kinds: skills, agents,
commands, instructions, Pi extensions and MCP servers. Bundles are an
installation utility, not a seventh kind. Canonical CLI groups are plural;
singular aliases remain accepted.

## Source and delivery

Source remote is private Broadpeak Gitea:
`ssh://gitlab@broadpeak.tailbf2225.ts.net:2424/ajanderson/agent-toolkit-cli.git`.
Use the reviewed source commit and wheel SHA to identify a deployment, not the
package version alone. Deployment is coordinated separately; do not infer
permission to push, publish, upgrade a live installation or change services.
Legacy GitHub workflow/release files are not the current delivery authority.

## Commands

- Bootstrap: `uv sync --all-extras`.
- CLI: `uv run agent-toolkit-cli --help`.
- TUI: `uv run agent-toolkit-tui` (terminal interface, not a web server).
- Test: `uv run pytest -q`.
- Build: `uv build`; strict docs: `make docs-build`.
- Installed-wheel smoke: run the disposable environment's Python with
  `scripts/verify_reground_artifact.py --work-dir <new-empty-directory>`.
- No dedicated lint/format/typecheck script is configured.
- `lefthook.yml` currently runs pytest on pre-push; this is not deployment.

## Code map

- `src/agent_toolkit_cli/cli.py`: plural groups and singular aliases.
- `commands/{skill,agent,command,instructions,pi_extension,mcp,bundle}/`: verb surfaces.
- `<kind>_install.py`, adapters, source/path/lock modules: shared CLI/TUI behavior.
- `behavior.py`, `project_backing.py`: backing configuration, legacy preservation
  and explicit central migration. New isolation is disabled by default.
- Skills/agents/commands/Pi extensions use source-backed locks. Instructions use
  canonical-file pointers, no installation lock. MCP authority is
  `mcps-library.json`; per-scope locks record projections.
- `src/agent_toolkit_tui/`: inventory, grids and pending queues; `settings.py`
  persists presentation only, not CLI behavior.
- `docs/agent-toolkit/`, `docs/asset-types/`: current reference.
- `docs/agent-toolkit/harness-matrix.md`: packaged compatibility data;
  `scripts/gen_harness_docs.py` generates matrix/harness pages and nav.
- `tests/`: pytest; headless Textual checks are in `tests/test_tui/`.

## Verification and maintenance

Use disposable HOME/config/assets and local Git remotes, never the live toolkit
installation. `tests/conftest.py` also strips inherited `GIT_*` variables to
prevent hook subprocesses accessing the outer repository. Legacy-private tests
explicitly select that mode; default/disabled creation must remain covered.

Preserve unrelated edits and source originals. Keep generated harness views in
sync through their generator; do not rewrite historical reports or release
notes as current documentation. Directory projection is not proof of native Pi
role, memory or skill loading; verify that separately in the chosen Pi setup.

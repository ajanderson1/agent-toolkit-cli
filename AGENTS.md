# AGENTS.md — agent-toolkit-cli

Python Click CLI and Textual TUI for managing six asset kinds across coding
harnesses: Skills, Agents, Commands, Instructions, Pi extensions and MCP servers.
Bundles is a separate installation utility, not a seventh kind. Canonical CLI
groups are plural; singular aliases remain accepted.

## Terminology — read first

Read [GLOSSARY.md](GLOSSARY.md) before discussing, documenting or changing lifecycle
behavior. **Add/remove** means global library membership; **enable/disable** means
harness exposure. Use those terms in explanations, not install/uninstall. Preserve
exact shipped command tokens in runnable examples and distinguish per-kind
exceptions; terminology does not imply an unimplemented CLI rename.

## Source of truth

This checkout and `https://github.com/ajanderson1/agent-toolkit-cli` are the
canonical CLI/TUI source. Build and install from verified canonical commits;
the separate REGROUND checkout is historical, not another development authority.
Record the source commit and wheel hash: the version string alone is insufficient.

## Operation

- Project-default trust: **L3 (Conditional)**; raise on plan divergence,
  out-of-scope blast radius or low confidence (shared aj-workflow trust ladder).
- L4+ raise timeout: **30 minutes**; park and escalate to AJ on timeout.
- `main` has no branch protection; squash merges land immediately. Recheck branch
  and base after long sessions; release work may move main.
- ReleasePlease owns package version/CHANGELOG; do not hand-author release bumps.

## Commands

- dev: `uv run agent-toolkit-tui` (local terminal interface, not a web server).
- build: `uv build`; docs: `make docs-build` (strict).
- test: `uv run pytest -q`; bootstrap: `uv sync --all-extras`.
- lint/format/typecheck: no dedicated project script configured.
- deploy: n/a for local CLI/TUI; GitHub workflows own release assets/docs publication.
- Run `make hooks` once per clone. The fail-closed **pre-push** gate checks every
  outgoing ref in Linux using `scripts/local_ci.py`: locked sync, full pytest,
  strict docs and wheel/sdist builds. Docker is required; use `make ci` for
  committed HEAD. Do not bypass hooks or push first to discover CI failures.
- GitHub test uses the same gate. Remote publishing/permissions and bot commits
  remain remote checks, not guarantees a local run can make.

## Code map

- `src/agent_toolkit_cli/cli.py`: plural group registration and singular aliases.
- `commands/{skill,agent,command,instructions,pi_extension,mcp,bundle}/`: actual verb surfaces.
- `<kind>_install.py`, adapter packages and source/path/lock modules: per-kind facades.
- Skills/Agents/Commands/Git-backed Pi extensions use source-backed locks. Pi npm
  uses native Pi settings/direct npm installations, **no Toolkit npm registry**;
  `pi_npm.py`, `pi_npm_lifecycle.py` and `data/pi_npm_bridge.mjs` share CLI/TUI behavior.
  Instructions uses actual canonical-file pointers, **no installation lock**. MCP library authority
  is `mcps-library.json`; its per-scope locks record projections.
- `behavior.py`, `project_backing.py`: shared CLI/TUI backing configuration;
  new projects use central sources by default, preserving existing private copies.
- `src/agent_toolkit_tui/`: inventory, six grids, cross-kind pending queues;
  `settings.py` persists presentation only, never CLI targets.
- `docs/agent-toolkit/`, `docs/asset-types/`: current public reference.
- `docs/agent-toolkit/harness-matrix.md`: packaged machine-read data;
  `scripts/gen_harness_docs.py` generates matrix/harness views/nav. Never hand-edit outputs.
- `docs/solutions/`: historical decisions/fixes; specs/plans/reviews are not current reference.
- `tests/`: pytest; TUI behavior in `tests/test_tui/`.

## Testing and maintenance

`tests/conftest.py` strips inherited `GIT_*` variables before each test to prevent
hook subprocesses writing into the outer repository. Set identity variables only
when a test needs them. Use disposable HOME/config/assets for CLI/TUI tests or media;
`scripts/capture_docs_tui.py` captures the real source-asserted documentation UI.
Register new verbs in their per-kind group and add behavior/help coverage. Update
the current docs with behavior changes; preserve historical reports and release notes.

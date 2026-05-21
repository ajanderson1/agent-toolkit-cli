# Deprecate all legacy (pre-v2) CLI commands; keep only `skill`

**Issue:** [#160](https://github.com/ajanderson1/agent-toolkit-cli/issues/160) — type:chore, milestone v2.3.0
**Flow mode:** `--auto`
**Author:** flow-agent (drafted from issue body + AGENTS.md + recent commit history)

## Goal

Strip the `agent-toolkit-cli` Python CLI down to a single top-level command (`skill`), so that `main` carries only what is intentionally part of the v2 universal-agent model. Every other top-level command — the pre-v2 surface — is removed from `main`, with its module **and** its test file deleted. The frozen v1 surface lives on at the existing `v1.0.0` tag; nothing new needs to be cut.

This is a destructive housekeeping change, not a refactor. The intent is to clear the deck so the v2 surface can be re-introduced piece by piece in follow-up issues, with each new command landing as a deliberate addition rather than carrying forward by inertia.

## Context

### Why now

`main` currently advertises 13 top-level commands. Only one — `skill` — was designed for the v2 universal-agent model that landed in PRs #156 / #157 / #158 (v2.0.0 → v2.1.0 → v2.2). The rest (`check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink`) predate that model and assume a world where assets are projected from a sibling toolkit repo into per-harness allow-lists. That world is no longer the primary use case; v2 says "install a skill from any source; harnesses are universal-or-not based on `skillsDir == .agents/skills`."

Leaving the legacy surface in place creates three drags:

1. **Discoverability noise.** `agent-toolkit-cli --help` lists 13 commands; a new user has no way to tell which are real for v2 and which are vestigial. The README already needs a confusing "v2.0.0" parenthetical to flag the new commands inside the larger surface.
2. **Maintenance overhead.** Every refactor of `_repo_resolution`, the schema vendoring contract, or the link/unlink allow-list touches code paths nobody on the v2 trajectory uses.
3. **Test-suite mass.** The test directory has 40+ `test_*.py` files for the legacy commands. They pass, but every test that exists must be maintained, run on every CI invocation, and considered when refactoring. Deleting them is a real reduction in surface area.

### What "v1.x is frozen" means in practice

The issue body asks for "a final v1.x tag cut on main." That phrasing implies a fresh tag, but the repo already has `v1.0.0` at commit `2c3a930` ("chore(main): release 1.0.0 (#152)"), which sits **before** the v2 worktree-strip merge (`da825b0`). That tag already captures the last commit where the legacy CLI was the *only* CLI — no v2 universal-agent code, no skill catalog port, no TUI strip. It is exactly the freeze point the issue describes.

**Decision:** the spec adopts `v1.0.0` as the "final v1.x" freeze tag. No new tag is cut. The DoD bullet "A final v1.x tag is cut on main" is reinterpreted as "the existing `v1.0.0` tag is documented as the v1 freeze point." If a user wants the old CLI, they install from that tag.

This avoids the ambiguity of cutting a fake v1.x off a `main` that already contains v2 code (which would not actually freeze a working v1 CLI — it would freeze a hybrid).

### Code map

The Python CLI is a `click.group` defined in `src/agent_toolkit_cli/cli.py`. Each top-level command is registered via `main.add_command(<x>)`. The commands themselves live in `src/agent_toolkit_cli/commands/`:

```
commands/
  __init__.py
  check.py            # remove
  diff.py             # remove
  doctor.py           # remove (delegates to commands/doctor/ subpackage; remove both)
  fix.py              # remove
  ingest.py           # remove (delegates to commands/ingest/ subpackage; remove both)
  inventory.py        # remove
  link.py             # remove
  list.py             # remove
  migrate_skills.py   # remove
  new.py              # remove
  pi.py               # remove (delegates to ../_pi_*; see below)
  skill/              # KEEP — only v2-native command
  unlink.py           # remove
  _hook_dispatch.py   # internal — KEEP unless transitively unused after removal
  _link_lib.py        # internal — remove (used by link/unlink only)
  _list_json.py       # internal — KEEP, registered as `list-json` hidden command
  _mcp_dispatch.py    # internal — remove (used by link/unlink/doctor for MCPs)
  _plugin_dispatch.py # internal — remove (used by link/unlink for plugins)
  _yaml_edit.py       # internal — KEEP, registered as `yaml-edit` hidden command
```

There are also several `_pi_*.py` modules at `src/agent_toolkit_cli/` level (`_pi_fetch.py`, `_pi_inventory.py`, `_pi_overrides.py`, `_pi_paths.py`, `_pi_settings.py`) supporting `commands/pi.py`. They go too.

Sibling-level support modules at `src/agent_toolkit_cli/` (`_allowlist.py`, `_repo_resolution.py`, `_requires.py`, `_support.py`, `_translators.py`, `_ui.py`, `schema.py`, `walker.py`, `inventory.py`, `skill_*.py`, etc.) need a transitive-reachability pass after the commands are removed:

- `skill_*.py` modules — **KEEP** (only `skill` depends on them).
- `schema.py`, `walker.py`, `_schemas/`, `inventory.py` (top-level), `_repo_resolution.py`, `_allowlist.py`, `_translators.py`, `_requires.py`, `_support.py`, `_ui.py`, `harness_adapters/`, `generators/`, `security/`, `doctor/`, `ingest/` — **probably remove**, but only after grep confirms `skill` and TUI don't import them. The build phase does the actual reachability check.

The `list-json` and `yaml-edit` subcommands are hidden internals — they don't appear in `--help` and are used by lefthook / scripting. They stay registered but their files are already on the keep list (`_list_json.py`, `_yaml_edit.py`). If their dependencies (schema, walker) go away, they go away too — we will know during the reachability pass.

### Tests

`tests/` has a top-level `test_cli_*.py` for each removed command (e.g. `test_cli_diff.py`, `test_cli_link.py`, `test_cli_list.py`, `test_cli_pi.py`, `test_cli_unlink.py`, `test_check*.py`, `test_doctor_*.py`, `test_claude_plugin_adapter.py`, `test_codex_hook_adapter.py`, …). All of these go.

The `test_cli_help.py` file stays but its expectations get updated to assert that `agent-toolkit-cli --help` lists exactly `skill` (plus the two hidden internals if they survive).

The `tests/integration/` and `tests/aj-workflow/` and `tests/audit/` directories are inspected per-file; anything that exercises a removed command goes, anything exercising `skill` stays.

### TUI

The TUI (`src/agent_toolkit_tui/`) is **explicitly out of scope** per the issue body. We do not touch it. If the TUI imports any legacy module that the CLI removal would orphan, we leave the module in place — the TUI removal is a separate v2.x cycle.

In practice the v2.1 TUI strip already narrowed the TUI to skill-grid, claude-code, and pi. We will grep `src/agent_toolkit_tui/` for imports from `agent_toolkit_cli.*` and treat anything imported there as a keep, regardless of CLI-side reachability.

### Docs

- `README.md` — the "Commands" section currently lists all 13 commands. It gets rewritten to list only `skill` (plus a "v1.x legacy CLI" pointer to the `v1.0.0` tag). The "Skills (new in v2.0.0 …)" subsection stays; the "Other asset kinds" subsection goes.
- `docs/agent-toolkit/cli.md` — the human-readable command reference. Each removed command's section goes; the file's intro and the `skill` section stay.
- `AGENTS.md` — the "Code map", "Two-flag contract", "Layered contract", "Schema sync", "Asset identity", and "Adding a new harness / asset kind / CLI subcommand" sections all reference the legacy surface. They get pruned to what is still true after the removal. The `--toolkit-repo` / `--project` two-flag contract is mostly legacy-only (link/unlink/list/diff use both flags; skill uses neither), so this section will likely shrink to a one-paragraph note rather than a table.
- `docs/superpowers/specs/2026-05-03-agent-toolkit-cli-tui-split-design.md` — referenced from AGENTS.md, lives in the toolkit repo, not this repo. Not touched here.

### CI and release

- `.github/workflows/test.yml` — runs `uv run pytest`. After test deletions, this should still pass with a smaller suite. No workflow change needed.
- `.github/workflows/release.yml` and `release-please.yml` — release-please manifest may reference the package version; the version in `pyproject.toml` (`2.1.0`) is independent. We don't bump to v2.3.0 in this PR; that bump is its own release-please commit when the v2.3 milestone is finished. The DoD says "milestone v2.3.0," not "release v2.3.0."
- `lefthook.yml` — likely runs `schema-vendor-check`, lint, tests on pre-commit. If schema-vendor-check depends on removed code, it goes.

## Approach

A deletion-first plan with reachability sweep:

1. **Confirm `v1.0.0` is the v1 freeze tag.** No new tag cut. Document this in the PR body.
2. **Unregister.** Remove all `main.add_command(<x>)` lines from `cli.py` except `skill`, `yaml_edit`, `list_json`. Update the docstring/help text. Remove the now-unused `--toolkit-repo` and `--project` group-level options if neither surviving command needs them. (`skill` does not use them; `yaml-edit`/`list-json` are hidden internals — check their bodies.)
3. **Delete command modules and command-private internals.** Remove every `commands/<x>.py`, the `commands/doctor/` and `commands/ingest/` subpackages, and the `commands/_link_lib.py`, `_mcp_dispatch.py`, `_plugin_dispatch.py` internal helpers.
4. **Delete `_pi_*.py` siblings.**
5. **Reachability sweep.** `grep -rE 'from agent_toolkit_cli\.(_repo_resolution|_allowlist|schema|walker|inventory|...) import' src/ tests/` for every candidate module. Anything no longer imported (after step 3 & 4) is deleted, including the `_schemas/`, `harness_adapters/`, `generators/`, `security/`, `doctor/`, `ingest/` directories at `src/agent_toolkit_cli/` level if confirmed unreferenced.
6. **TUI safety check.** `grep -r 'from agent_toolkit_cli' src/agent_toolkit_tui/`. Any module imported by the TUI is kept regardless of step 5.
7. **Delete tests.** Per-file pass: every `test_*.py` whose target command is removed goes. `test_cli_help.py` is rewritten to match the new help output.
8. **Update docs.** README, `docs/agent-toolkit/cli.md`, AGENTS.md.
9. **Update lefthook.** Remove `schema-vendor-check` and any other hook that depends on removed code; keep ruff / mypy / pytest hooks.
10. **Run pre-flight CI.** `uv sync --all-extras && uv run pytest -q && uv run ruff check && uv run mypy src/`. Anything red is fixed before PR.

## Out of scope

- Rebuilding any of the deprecated commands. Each comes back (or doesn't) in its own follow-up issue.
- The TUI (`src/agent_toolkit_tui/`). Untouched.
- The `skill` command itself. Untouched.
- Cutting a fresh v1.x tag. `v1.0.0` already exists at `2c3a930` and is the freeze point.
- Bumping the pyproject version to v2.3.0. Release-please owns the bump when v2.3.0 is ready to ship.
- Cleaning up the toolkit repo (sibling repo). Out of repo.
- Branch-protection rules, GitHub release notes prose, or end-user migration guides. Each can be its own follow-up if needed.

## Definition of done (mapped to the issue DoD)

| Issue DoD bullet | This spec's interpretation |
|---|---|
| Final v1.x tag cut on main | `v1.0.0` (existing, at `2c3a930`) is documented in the PR body as the v1 freeze. No new tag. |
| Removed top-level commands: check, diff, doctor, fix, ingest, inventory, link, list, migrate-skills, new, pi, unlink — modules and tests deleted | Step 3 + step 7 above. |
| `agent-toolkit --help` shows only `skill` (plus global flags) | After step 2, `--help` lists `skill` and the two hidden internals (which don't appear in user-facing help). `test_cli_help.py` enforces this. |
| README and in-repo docs no longer reference removed commands | Step 8 above. |
| Existing tests for removed commands are deleted; remaining suite passes | Step 7 + step 10 above. |
| Follow-up tracker issue (or labels-as-tracker) lists what needs to be rebuilt for v2 | Filed as a separate `gh issue create` in the build phase, linked from the PR body. Title: "Rebuild v2-native replacements for deprecated CLI commands (tracker)." Body lists each removed command and notes whether a v2 replacement is desired, deferred, or dropped. |

## Risks and unknowns

1. **`yaml-edit` / `list-json` may transitively depend on removed schema/walker code.** If they do, they get removed too, the lefthook config gets pruned, and `--help` shows only `skill`. Resolved during step 5 reachability sweep.
2. **TUI may import legacy modules we want to delete.** Step 6 guards against this. Worst case: a `_*.py` module survives unreferenced from the CLI but imported by the TUI. That is acceptable; the TUI cleanup is its own issue.
3. **CI workflows or lefthook hooks may shell out to a removed command.** Step 9 catches this in lefthook; step 10's pre-flight catches it in CI. Any external (toolkit-repo) lefthook that shells out to `agent-toolkit-cli check` is **the toolkit repo's problem to fix in its own PR**; we don't fix cross-repo callers here, but the PR body should call this out as a known consequence.
4. **Editable installs that already shadow `uv tool install` (see README note + issue #61)** will break loudly after removal — `ImportError: cannot import name 'check'`. This is the intended failure mode; the README note already warns about it. No further mitigation needed.
5. **`migrate-skills` was a one-shot migration tool** (it rewrites legacy inline-frontmatter skills into the sidecar form, per the v1.0.0 release that introduced the split). If anyone hasn't migrated yet, they install `agent-toolkit==1.0.0` from PyPI / git tag and run it once. PR body notes this.

## Verification plan (preview of Step 9)

The CLI binary has no web surface; this is a terminal recipe. Suggested artifacts in `assets/verification/160/`:

- `helptext-before.txt` — `agent-toolkit-cli --help` on `main` (captured pre-removal for diff).
- `helptext-after.txt` — `agent-toolkit-cli --help` on the branch (must show only `skill`).
- `pytest.log` — full `uv run pytest -q` output (must be all green).
- `ruff.log` — `uv run ruff check src/ tests/` output.
- `tree-before.txt` / `tree-after.txt` — `tree src/agent_toolkit_cli/` before and after, to show the file-level reduction.

No screenshot recipe; no dev server.

## PR shape

- Single PR closing #160.
- Conventional-commit message: `chore!: deprecate pre-v2 CLI commands; keep only \`skill\`` (note the `!` — this is a breaking change to the public CLI surface).
- PR body lists the removed commands and links to `v1.0.0` for the frozen surface.
- Follow-up tracker issue filed during the build phase, linked from the PR body.

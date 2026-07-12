# Issue #469 verification manifest

## Code revision under test

- Exact code revision: `ad9f9b1018bf8576319f26a80f57f39bcd5df239`
- Evidence relationship: the verification artifacts are committed after this code revision. They validate that exact code revision; this manifest intentionally does not claim to self-record the SHA of its own evidence commit.
- Scope: Hermes Agent support in the Textual Skills grid; unsupported asset surfaces remain absent.

## Documentation audit

No compatibility-document edits were needed. `docs/harnesses/hermes-agent.md` and `docs/agent-toolkit/harness-matrix.md` already agree with the implementation:

- instructions: native `AGENTS.md` reader;
- skills: project `.hermes/skills`, global `~/.hermes/skills`;
- subagents: unsupported by design (`delegate_task` is runtime-only);
- commands: unknown, with no public evidence;
- MCP: no toolkit adapter;
- Pi extensions: not applicable because they are Pi-only.

The nearby developer documentation in `src/agent_toolkit_tui/widgets/skill_grid.py` was materially stale because it enumerated only Standard, Claude, and Pi. It now describes the derived non-standard main-harness columns and names Hermes.

## Commands and results

| Exit | Command | Evidence |
|---:|---|---|
| 1 (expected red) | `uv run pytest -q tests/test_tui/test_skill_grid_column_info.py::test_full_header_row tests/test_tui/test_status_counters.py::test_footer_pending_counts_three_harnesses tests/test_tui/test_status_counters.py::test_apply_counts_per_harness_write tests/test_tui/test_status_counters.py::test_apply_failed_count_is_symmetric` against the pre-fix test expectations | `red-stale-expectations.txt` |
| 0 | `uv run pytest -q tests/test_tui/test_skill_grid_column_info.py::test_full_header_row tests/test_tui/test_skill_grid_new_columns.py::test_source_column_is_last tests/test_tui/test_status_counters.py::test_footer_pending_counts_four_harnesses tests/test_tui/test_status_counters.py::test_apply_counts_per_harness_write tests/test_tui/test_status_counters.py::test_apply_failed_count_is_symmetric` | `green-integration-fixes.txt` |
| 0 | `uv run pytest -q tests/test_tui/test_composition.py tests/test_tui/test_display_names.py tests/test_tui/test_skill_state.py tests/test_tui/test_skill_grid_apply.py tests/test_tui/test_skill_grid_new_columns.py tests/test_tui/test_skill_grid_column_info.py tests/test_tui/test_status_counters.py tests/test_tui/test_command_state.py tests/test_tui/test_mcp_state.py tests/test_tui/test_pi_grid.py` | `focused-tests.txt` — 125 passed |
| 0 | `uv run pytest tests/test_tui -q` | `full-tui-tests.txt` — 363 passed |
| 0 | `uv run python assets/verification/issue-469/capture_hermes_skill_grid.py --output assets/verification/issue-469/hermes-skill-grid.svg` | `capture-svg.txt`, `hermes-skill-grid.svg` |
| 0 | repeat capture to a temporary file, then `cmp` with the committed SVG | `svg-reproducibility.txt` — byte-identical |
| 0 | `git diff --check 2e5f950687651eb09871596f0aa62d9e7b9402fe..HEAD` | `git-diff-check.txt` |
| 0 | `grep -R -n --exclude=manifest.md -E '/Users/|\.pi-subagents|\.superpowers' assets/verification/issue-469` | no matches in evidence files outside `manifest.md`; the manifest is excluded because it must document this command |

`uv.lock` was restored after verification.

## Artifacts

- `hermes-skill-grid.svg` — deterministic Textual SVG generated from an in-memory `SkillGrid` hosted by `App.run_test(size=(140, 24))`; it does not read or write user toolkit state.
- `capture_hermes_skill_grid.py` — reproducible capture command.
- `hermes-skill-grid-grep.txt` — machine-readable excerpt proving the SVG contains the rendered column labels.
- `svg-sha256.txt` — SHA-256 checksum for the normalized SVG.
- `focused-tests.txt` and `full-tui-tests.txt` — final green automated verification.
- `red-stale-expectations.txt` and `green-integration-fixes.txt` — red/green evidence for integration expectations exposed by the full suite.

SHA-256 for `hermes-skill-grid.svg`: `b6cffe1ff03f40834b5e0524cae4f5b5d916fa09290b1f86b175999de1920e58`.

## Visual judgment

**Pass.** The SVG visibly renders the Skills header in this order: Skill, Standard (13), Claude, Pi, **Hermes**, State, Source. The Hermes label and info glyph are fully readable, do not overlap adjacent columns, and the sample row remains aligned beneath the headers.

Unsupported Hermes surfaces remain absent based on automated tests: command state excludes `hermes-agent`, MCP composition excludes it at project and global scope, agent composition excludes it because its subagent mechanism is `none`, and the Pi-extension grid has no Hermes column. The visual artifact intentionally shows only the supported Skills surface.

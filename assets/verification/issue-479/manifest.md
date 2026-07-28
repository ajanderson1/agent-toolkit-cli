# Issue #479 verification manifest

- **Captured:** `2026-07-28T09:03:20Z`
- **Rung:** R0 — pytest plus deterministic Textual `run_test()` capture.
- **Product tree:** `b90878339de2e9d66dc00cfa95a2db67baba0182`.
- **Checkpoint:** `46b0d0e` was verified and reissued as `7c87d68d0b72b2b6e6f47fef52893301539ba82f` solely to repair its malformed `Device:` trailer; the Git tree is identical.
- **Lockfile:** `uv.lock` was restored after every `uv run`; no lockfile diff remains.

## Fresh commands

| Check | Command | Result |
|---|---|---|
| Visual capture | `uv run python assets/verification/issue-479/capture_visual_evidence.py` | exit 0; `capture-visual.txt` |
| Glyph scan | `rg -n '_INFO_GLYPH' src/agent_toolkit_tui/widgets` | exit 0; `dead-affordance-scans.txt` |
| Registry-caller scan | `rg -n 'get_column_info|COLUMN_INFO' src/agent_toolkit_tui` | exit 0; `dead-affordance-scans.txt` |
| TUI suite | `uv run pytest tests/test_tui/test_asset_info_key.py tests/test_tui -q` | 452 passed in 85.01s; `tui-suite.txt` |
| Full suite | `uv run pytest -q` | 2119 passed, 2 skipped in 186.91s; `full-suite.txt` |

## Screenshot inventory

- Six global/project grid captures: `skills-grids-global-project.png`, `instructions-grids-global-project.png`, `agents-grids-global-project.png`, `mcps-grids-global-project.png`, `commands-grids-global-project.png`, and `pi-extensions-grids-global-project.png`.
- Standard-panel captures: `skills-standard-project.png`, `instructions-standard-project.png`, `agents-standard-global.png`, `agents-standard-project.png`, and `mcps-standard-project.png`.
- Scroll proof: `instructions-standard-project-scrolled-bottom.png`.
- Contact sheet: `visual-contact-sheet.png`.
- Reproduction/check artifacts: `capture_visual_evidence.py`, `capture-visual.txt`, `visual-checks.txt`, `dead-affordance-scans.txt`, `tui-suite.txt`, `full-suite.txt`, and `modal-scroll-focused.txt`.

## Visual verdict

**PASS.** I inspected the six grid captures, contact sheet, and Instructions Standard panel at both its top and bottom. Headers, labels, and every visible `ⓘ` remain readable with no observed truncation; Source stays glyph-free. The 39-harness Instructions panel exposes its final explanatory and project-marker lines after scrolling, without clipping. The deterministic capture also exercised every glyphed header at both scopes, passive headers, three `i` cursor positions, no-description fallback, zero-row no-op, and the Agents Standard 5-to-6 scope change.

## Requirement and plan audit

| Requirement | Evidence |
|---|---|
| Header click explains a column; Source/asset-name headers are passive | `test_header_click_info.py`, all-scope capture, and `visual-checks.txt` |
| Every glyphed rendered header has content; every registered pair is rendered | `test_column_info_coverage.py`; current scan and 26-pair registry |
| `i` always explains the selected asset, including Commands | `test_asset_info_key.py`, `app.action_info_pass()`, and capture assertions |
| Unknown `(asset_type, column)` fails loudly | `test_unregistered_pair_is_loud` and direct `COLUMN_INFO[(asset_type, column)]` lookup |
| Authored Standard, harness, State, and Origin copy is retained | `test_column_info.py` exact-copy assertions; panel captures |
| Instructions panel is scrollable in a constrained terminal | `test_long_modal_body_scrolls_in_a_small_terminal`; top/bottom scroll screenshots |
| No column-set change or keyboard column-info binding | branch file audit; six grid captures; no `src/agent_toolkit_cli/` delta |
| Task plan | all 24 implementation checkboxes are marked complete in `docs/superpowers/plans/2026-07-28-479-column-info-affordances.md` |

## Scan judgment

The refreshed glyph scan contains only actual rendered header constructions; the stale passive Pi Extension width reference is absent. `get_column_info()` is called only from click handlers and raises for unknown pairs; handlers return early only for passive slug/Source columns, not from a missing registry value.

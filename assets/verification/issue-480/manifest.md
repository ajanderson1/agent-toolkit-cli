# Verification manifest — issue #480

- **Source code under test:** `2ad1bfa71ea1d58cdeea60fcc14bf294c1b73bd0`
- **Final verification head:** `93fd8e140fbb4876a8963f2026deaf045d6466ad` (no source-code change after the source commit).
- **Final full suite:** `uv run --frozen --no-sync pytest -q` — `2143 passed, 2 skipped`; `full-suite-final.txt`.
- **Required rung:** no project `TESTING.md` or issue gate declares one. Evidence is local Textual in-process verification (R1) plus manual visual judgment.

| Check | Command / evidence | Exit | Result |
|---|---|---:|---|
| Constant / boundary scan | `boundary-scans.txt`, `boundary-scan-judgment.md` | 0 / expected `rg` no-hit 1 | PASS |
| CLI determinism | `cli-determinism.txt` — `skill list` + `skill status`, temporary non-default settings, byte `cmp` | 0 | PASS |
| Focused red regression | `status-bar-red.txt` | 1 (expected) | Confirmed missing content row |
| Focused green regression | `status-bar-green.txt` | 0 | PASS |
| Affected TUI suite | `tui-suite-after-status-fix.txt` | 0 | `476 passed` |
| Visual capture | `capture-visual.txt`, `visual-checks.txt`, `visual-contact-sheet.png` | 0 | PASS |
| Visual judgment | `visual-judgment.md` | n/a | PASS |
| R6 divergence record | `status-bar-divergence.md` | n/a | Fixed: two-row status bar |

## Artifacts

- Capture script: `capture_visual_evidence.py`
- PNG evidence: palette, settings, theme, Pi-removal, empty-selection, malformed/unknown-settings, and contact-sheet PNGs in this directory.
- Unknown-key retention: `ghost-settings-after-theme-save.json`.

## PR #487 data-steward follow-up

`pr-487-data-steward-follow-up.md` records the compatibility remediation at `4ccc573dab60e1169bb6a13220ce105a9e3a71cb`: focused regressions, the complete TUI suite, and the full gate all passed.

**Overall verdict: PASS.**

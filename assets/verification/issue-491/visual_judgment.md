# Visual Judgment — Issue #491

**Surface:** agent-toolkit-tui

**Expectation:**
Main harness command palette allows direct toggle of any real catalog harness and applies columns live without settings modal.

**Verdict:** PASS

**Evidence:**
1. `01_main_harnesses_palette.svg` — Command palette shows 'Main harnesses' with `[x]` / `[ ]` checked state markers for catalog harnesses.
2. `02_theme_palette.svg` — Command palette shows 'Theme' list with immediate persistent application.
3. `03_long_tail_toggled_skills.svg` — Long-tail harness `aider-desk` toggled on skills grid.
4. `04_long_tail_toggled_commands.svg` — Support-aware column composition on commands grid.
5. `05_pending_discard_confirmation.svg` — Confirmation modal protects queued pending edits before discarding and updating main harnesses.

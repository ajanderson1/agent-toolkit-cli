# Plan — Rebind scope toggle `s` → `ctrl+g` (#320)

Spec: `docs/superpowers/specs/2026-06-07-rebind-scope-toggle-design.md`

Tiny fix. TDD: write the failing behavioral test first, then flip the binding.

## Task 1 — failing test first

Add to `tests/test_tui/test_scope_toggle.py` (app-level, uses real `TUIApp`):

- `test_s_key_in_filter_does_not_toggle_scope`: `TUIApp().run_test()`, pause
  (focus auto-lands in `#skill-filter`), record `app._scope`, `pilot.press("s")`,
  assert `app._scope` unchanged AND the `#skill-filter` Input value contains
  `"s"`.
- `test_ctrl_g_toggles_scope`: open, record `app._scope`, `pilot.press("ctrl+g")`,
  assert `app._scope` flipped (project↔global).

Run → the `ctrl+g` test fails (binding is still `s`), the `s` test may already
pass-by-accident; both lock the contract.

## Task 2 — flip the binding

In `src/agent_toolkit_tui/app.py` `TUIApp.BINDINGS` (line 126):

```python
-        Binding("s", "scope_toggle", "toggle scope"),
+        Binding("ctrl+g", "scope_toggle", "toggle scope", priority=True),
```

`priority=True` so it fires past a focused Input (matches ctrl+s/d/r/z).

## Task 3 — verify

- `uv run pytest tests/test_tui/test_scope_toggle.py -q` green (new + existing).
- `uv run pytest -q` full suite green (no regression — `s` was only bound here).
- Headless smoke → `assets/verification/320/run.log`.

## Risks

- **Footer/help text:** Textual's Footer renders BINDINGS labels; the label
  "toggle scope" now shows under `^g` instead of `s` automatically — no extra
  edit needed, but eyeball the smoke output.
- **`priority=True`:** required so a focused Input doesn't swallow it; without
  it the chord might not reach the App. The test for `ctrl+g`-while-filter-
  focused is the guard.

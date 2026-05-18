# Spec — Show user-scope indicator on project-scope asset views (#86)

Date: 2026-05-18
Issue: [#86](https://github.com/ajanderson1/agent-toolkit-cli/issues/86)
Related: #69 (cross-scope deconfliction — broader follow-up; this spec is the read-only slice)
Mode: aj-workflow flow `--auto`

## 1. Goal

In project-scope views (TUI asset grid, CLI `at list`, `agent-toolkit doctor`), surface a visual indicator on each `(asset, harness)` cell that is *also* linked at user (global) scope. Read-only hint. No policy enforcement, no drift detection, no auto-fix.

## 2. Why now

The CLI and TUI render project- and user-scope state independently. From inside a project-scope view, an asset already covered globally looks identical to one not linked anywhere. The operator can't see "you don't need this at project scope, it's already global" without manually toggling scope. This is friction we hit constantly while curating project-scope assets; it gets worse as user-scope coverage grows.

#69 will eventually block redundant installs and detect drift. This spec is deliberately narrower: it ships the *visual* part now, in isolation, so the operator gets immediate signal without committing to the larger policy decisions in #69.

## 3. Non-goals (out of scope)

- Blocking, warning, or erroring on a project-scope link when the asset is also at user scope — that's #69.
- Drift detection beyond surfacing the indicator (no "you should remove this" guidance).
- Any change to how scope is selected, to the `--project` / `--toolkit-repo` flags, or to the `link`/`unlink` semantics.
- Inverse indicator (project-scope assets *not* covered at user scope). Possible follow-up; not in this PR.
- Pi-extension at project scope: it has no project slot (`_PROJECT_TARGETS` excludes `("pi", "pi-extension")`), so it never appears in the project grid view and is therefore not affected.

## 4. Background — code map

Grounded in the existing layered contract (AGENTS.md § Layered contract):

| Concern | Module |
|---|---|
| Asset discovery from toolkit repo | `src/agent_toolkit_cli/walker.py` (7 `_KIND_RULES`, l.19) |
| Per-scope target slot paths | `src/agent_toolkit_cli/_support.py` (`_USER_TARGETS` l.24, `_PROJECT_TARGETS` l.39) |
| **Shared JSON inventory** — already emits per-`(harness, scope)` cells for both scopes | `src/agent_toolkit_cli/commands/_list_json.py` (`_build_inventory` l.144, `_cell_status` l.45) |
| Hook / MCP installs via config-file adapters | `src/agent_toolkit_cli/harness_adapters/*.py` (`list_installed(scope, project_root)`) |
| CLI `at list` text-mode | `src/agent_toolkit_cli/commands/list.py` (`_install_state` l.36; row format l.235) |
| TUI grid render | `src/agent_toolkit_tui/widgets/asset_grid.py` (`_GLYPH` l.13, `_rebuild` l.203) |
| TUI state — cells keyed by `(harness, scope)` with **both scopes** populated | `src/agent_toolkit_tui/state.py` (`AssetRow.cells` l.34) |
| `doctor` orchestration | `src/agent_toolkit_cli/commands/doctor.py` (`_GROUPS` l.23, `_run_global` l.92) |
| Doctor group modules | `src/agent_toolkit_cli/doctor/*.py` (each exposes `run(...) -> GroupResult`) |

**Key recon finding:** the data is already there. `_build_inventory()` already produces both `user` and `project` cells for every `(asset, harness)`. The TUI already has user-scope cells in memory while rendering project scope; it simply ignores them. For the TUI and JSON consumers, this issue is a pure render-time change — no new data path.

Only two surfaces need fresh computation:
1. `commands/list.py` text mode, which uses a lighter parallel `_install_state()` path and bypasses the shared inventory.
2. The new doctor group module.

## 5. Design

### 5.1 The check, normalised

For a given `(asset_slug, harness, kind)` in the project-scope view:

> "Linked at user scope" = the corresponding user-scope cell from `_build_inventory()` has `status` ∈ {linked-status-values} for that harness.

We do **not** invent a new check. We reuse the per-cell `status` field that `_build_inventory()` already produces. For symlink kinds this is the symlink-presence check (`_cell_status`); for hook/mcp kinds it's the harness adapter's `list_installed("user", project_root)` call. Either way: the inventory is the single source of truth.

### 5.2 The indicator — per-cell, per-harness

The indicator is **per `(asset, harness)`**, not per asset. An asset linked at user scope for `claude` but not for `codex` should show the indicator on the `claude` column and not on the `codex` column. This avoids the multi-harness collapse ambiguity the scout flagged.

**Glyph choice:** `🌐` (globe) — visually distinct, unicode-safe, conveys "global / wider scope". Verified against the existing `_GLYPH` table to avoid collision. Falls back gracefully in monochrome terminals (still renders as a glyph).

Per `feedback_textual_render_methods` (avoid `_render_*` method names colliding with internals), all new render helpers use unambiguous names like `_user_scope_marker_for` or inline-only logic.

### 5.3 Three surfaces

#### 5.3.1 TUI asset grid (`src/agent_toolkit_tui/widgets/asset_grid.py`)

In `_rebuild()`, when `self._scope == "project"`, after composing the project-scope cell text, also look up `row.cells.get((h, "user"))`. If that user cell's `status` is a "linked" state, suffix or overlay the project-cell text with the `🌐` glyph.

No state-model change — `AssetRow.cells` already holds both scopes.

Decision: **suffix glyph** rather than replacement, so the operator still sees the project-scope status of the cell. Example cell text: `✓ 🌐` instead of `✓`. Width budget: cells already accommodate two-glyph composites in tests, but verify against current width constants.

When `self._scope == "user"`, the indicator does not render. This is scope-symmetric: the indicator means "covered at user scope", which is only informative *when looking at project scope*. (The inverse — project-only assets seen from user scope — is a different feature.)

#### 5.3.2 CLI `at list` text mode (`src/agent_toolkit_cli/commands/list.py`)

Current row format (l.235):

```
{slug:<20} {h_display:<30} user:{state} project:{state}
```

The user-scope state is already in the line. The change is to suffix the `project:{state}` segment with `🌐` when `user:{state}` is a linked state. Two execution options:

**A. Pure-text suffix.** Compute the marker once per row from the same `_install_state(..., "user", ...)` already called for the `user:` field. No structural rewrite.

**B. Switch text mode to consume the shared inventory.** Cleaner; aligns CLI text mode with TUI and JSON output. Larger diff, touches the `_install_state` parallel path the scout flagged as incomplete for hooks/MCPs.

**Choosing A** for this PR. Rationale: option B is desirable but is its own refactor (covers hook/MCP-correctness in text mode, which is a latent bug independent of #86). Filing it as a follow-up keeps this PR focused. Add a TODO comment pointing at the follow-up issue we'll file.

#### 5.3.3 `agent-toolkit doctor` group (`src/agent_toolkit_cli/doctor/user_scope_coverage.py` — new)

New doctor group: `"user-scope-coverage"`. Module returns a `GroupResult` listing each `(asset, harness)` pair that has a project-scope link AND a user-scope link. One line per pair. No severity — this is informational, not a finding (since by spec it's not drift).

Wire it into `commands/doctor.py` `_GROUPS` (l.23) as the new last entry. Default visibility: shown by default (doctor groups have no per-group enable flag; if one is wanted later, that's #69's job).

### 5.4 Shared helper

Per the scout's recommendation, the natural home is **inside `commands/_list_json.py`**, exposed as a small pure function:

```python
def user_scope_covered(inventory: Inventory, slug: str, harness: str) -> bool:
    """True iff the (slug, harness) user-scope cell is in a linked state."""
```

This is used by:
- TUI `_rebuild()` — already builds inventory via the same path.
- Doctor `user_scope_coverage` group — calls `_build_inventory()` once, then walks the cells.
- CLI text `list.py` — option A means we don't call this directly here; we reuse the existing `_install_state(..., "user", ...)` for symmetry with the rest of `list.py`. (If we later move text-mode to inventory, this helper becomes the shared codepath.)

Single helper, three call sites, no duplication.

## 6. Definition of done

- TUI: project-scope rows show `🌐` suffix on cells whose `(harness, user)` cell is linked. User-scope view unchanged.
- CLI `at list` text mode: project-scope rows show `🌐` suffix on the `project:` segment when user-scope is linked. `--format=json` unchanged (data already present per-cell).
- New doctor group `user-scope-coverage` lists each `(asset, harness)` pair linked at both scopes.
- Shared helper `user_scope_covered(inventory, slug, harness)` lives in `commands/_list_json.py`, used by TUI and doctor.
- All 7 asset kinds (skill, agent, command, hook, mcp, plugin, pi-extension) covered. Pi-extension only shows the indicator in user-scope views, by definition; verified explicitly in tests.
- Tests:
  - Unit: `user_scope_covered` returns correct bool for each `(kind, scope-combo)` permutation per harness.
  - TUI: render test confirms `🌐` appears on project-scope cells when user-scope is linked, and does **not** appear on user-scope cells or unlinked project cells. Glyph passes the `Text.from_markup(...).plain` regression check (`tests/test_tui/test_asset_grid_glyphs.py`).
  - CLI text: `at list` golden-line test for a fixture where the same asset is linked at both scopes (claude harness), one scope only, and neither.
  - Doctor: fixture with mixed installs, assert group output line count and contents.
- Pre-commit `schema-vendor-check` passes (no schema changes expected).

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `🌐` glyph mangled by some terminals / Rich markup. | Add to `test_asset_grid_glyphs.py` regression suite (Rich-markup round-trip). Pick a fallback ASCII marker only if Rich strips it — current evidence says it won't. |
| Cell width overflow in TUI when suffix is added. | Inspect width constants in `asset_grid.py`; if needed, trim trailing whitespace before suffixing, or expand width by 2 columns globally. Verify under the existing grid-render tests. |
| Hook/MCP text-mode false negatives (the scout-flagged latent bug). | Acknowledged in spec § 5.3.2 option A; not fixed here; filed as follow-up. The TUI and doctor surfaces are correct because they use `_build_inventory()`. |
| `(pi, agent)` dual-write — slug counted as linked from either of two slots. | Already handled by `_cell_status()` via `_slot_dirs()`. Indicator inherits this behaviour for free. |
| Per-harness ambiguity ("at user scope for which harness?"). | Indicator is per `(asset, harness)` not per asset. Resolved by design. |

## 8. Test strategy summary

Following `~/.conventions/conventions/testing.md` floor:

- **Unit** — helper `user_scope_covered`: 1 test, parameterised over 7 kinds × 3 harnesses (claude / codex / opencode) × 4 scope-combos (neither, user-only, project-only, both).
- **CLI** — `tests/test_cli_list.py`: 1 new test seeding both-scope claude link for a skill, asserting the `🌐` marker is in the project segment of the row.
- **TUI** — new test in `tests/test_tui/`: build inventory with one row having user + project links for one harness, assert the rendered cell text contains the marker; check absence cases too. Add `🌐` to `test_asset_grid_glyphs.py`.
- **Doctor** — `tests/test_doctor_user_scope_coverage.py`: 1 test, fixture with three assets in three configurations, assert output lines.

No fragile screenshot tests; all tests are deterministic string-or-state assertions.

## 9. Open questions

None blocking. All design choices above are recorded with rationale. The "option A vs B" choice for `list.py` text-mode (§ 5.3.2) is explicit; if review prefers B, that's a scope expansion, not a redesign.

## 10. Sequence (preview of plan)

1. Add `user_scope_covered()` helper to `commands/_list_json.py` + unit test.
2. Wire TUI `_rebuild()` to render `🌐` when project-scope view + user-scope cell linked. Add render tests + glyph regression entry.
3. Wire CLI text `list.py` to suffix `🌐` on project segment based on user-scope `_install_state`. Add CLI test.
4. New `doctor/user_scope_coverage.py` returning `GroupResult`; register in `commands/doctor.py._GROUPS`. Add doctor test.
5. Update `docs/agent-toolkit/cli.md` (one paragraph + an example row).
6. Verify against `.claude/testing.md` recipes (if present) or the verify menu.

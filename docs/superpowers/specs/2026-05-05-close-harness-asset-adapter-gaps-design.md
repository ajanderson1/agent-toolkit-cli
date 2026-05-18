# Close harness/asset adapter gaps; hard-stop on unsupported pairs

**Issue:** [#30](https://github.com/ajanderson1/agent-toolkit-cli/issues/30) · **Type:** fix · **Date:** 2026-05-05

## Scope note

Issue #30 originally bundled two workstreams: (a) close silent-skip on unsupported `(harness, kind)` pairs and (b) add missing adapters where the matrix has gaps that *should* exist. Workstream (b) — upstream-doc research and per-harness adapter ports — is split into follow-up issue **#32**. This PR delivers (a) only.

## Goal

Make the existing harness/asset support matrix the **single source of truth** for what `(harness, kind)` pairs are valid, and turn every silent-skip on an unsupported pair into a loud, structured failure. Users must not be able to queue a change that will silently no-op.

## Background

The current support matrix lives in `src/agent_toolkit_cli/commands/_list_json.py:26-49` (`_USER_TARGETS` / `_PROJECT_TARGETS`):

|          | skill | agent | command | hook | plugin | mcp | pi-extension |
|----------|:-----:|:-----:|:-------:|:----:|:------:|:---:|:------------:|
| claude   |  ✔   |  ✔   |   ✔    |  ✔  |   ✔   |  *  |              |
| codex    |  ✔   |      |        |     |       |  *  |              |
| opencode |  ✔   |      |        |     |       |  *  |              |
| pi       |  ✔   |  ✔   |        |     |       |     |      ✔       |

(`*` = handled separately via `_mcp_dispatch.py` per-harness adapters; not affected here.)

`_link_lib.py` redefines its own `ALL_HARNESSES` and re-imports `_USER_TARGETS` / `_PROJECT_TARGETS` from `_list_json.py` — so the matrix is *de facto* shared, but there's no named helper "is this pair supported?" and no structured exception when an unsupported pair flows through.

### The two visible failure modes

1. **Apply path silent-skip.** `_link_lib.project_from_file()` line 264-266:
   ```python
   target_dir = harness_target_dir(harness, kind, scope, project_root)
   if target_dir is None:
       continue
   ```
   For an unsupported pair this looks "successful": no counter increments, no error, no message. A user can run `link --harness opencode` with an `agent: foo` allow-list line and the command exits 0 with nothing written.

2. **TUI surface.** `AssetGrid._toggle_at` already guards `unsupported` cells (asset_grid.py lines 120, 136, 180, 253) — so the keyboard path *is* hard-stopped. But the issue notes a "Opencode gap / Codex gap" footer hint as a workaround; a `grep` of the current source finds **no such string**, so the workaround appears to have been removed already (likely during the four-glyph list refactor, commit `08134e1`). AC#7 below verifies this.

## Acceptance criteria

| # | AC | Verification |
|---|---|---|
| 1 | A new module `src/agent_toolkit_cli/_support.py` exports `SUPPORTED_PAIRS: frozenset[tuple[str, str]]`, `is_supported(harness, kind) -> bool`, and `UnsupportedPair(Exception)`. | unit test |
| 2 | `_USER_TARGETS` and `_PROJECT_TARGETS` move to `_support.py`. `_list_json.py` and `_link_lib.py` import from there; the keys of either dict define `SUPPORTED_PAIRS` (no second source of truth). | grep finds one definition, two import sites |
| 3 | `_link_lib.project_from_file()` no longer does `if target_dir is None: continue` for the supported-pair branch. The branch is unreachable because the loop iterates over `(kind for kind in KINDS_FOR_PROJECTION if is_supported(harness, kind))`. The defensive `assert target_dir is not None` documents the invariant. | unit test |
| 4 | `_link_lib.maybe_link()` — and any other entry-point that takes `(harness, kind)` directly — call `is_supported(harness, kind)` and `raise UnsupportedPair(harness, kind)` if false. | unit test asserts the raise |
| 5 | `link --harness codex --plan -` with stdin `agent: foo` exits 2 with a message naming the pair and the supported pairs for that harness. (Today: exits 0, writes nothing.) | CliRunner integration test |
| 6 | `_list_json` cells continue to emit `status: "unsupported"` for unsupported pairs (no JSON contract change). | existing `test_list_json` tests still pass |
| 7 | TUI regression test: pressing Space on an `unsupported` cell yields no `AssetToggled`, no pending entry, and the rendered glyph stays `──`. | new test in `tests/test_tui/` |
| 8 | A grep of `src/` and `tests/` for `"Opencode gap"`, `"Codex gap"`, `"opencode gap"`, `"codex gap"` returns zero hits. | shell check in CI / verify recipe |
| 9 | Full `uv run pytest -q` passes. | pre-flight CI |
| 10 | `agent-toolkit doctor` continues to pass (no new doctor checks added in this PR). | smoke run |

## Non-goals

- Adding new adapters (filed as #32).
- Changing `_mcp_dispatch.py`'s adapter pattern.
- Rewriting allow-list semantics or the asset model.

## Verification plan

- Unit: `tests/test_support.py` covers the SSOT, `is_supported`, `UnsupportedPair`.
- Unit: `tests/test_link_lib.py` adds a case for the raise.
- Integration: `tests/test_cli.py` (or `test_link.py`) adds the CliRunner case.
- TUI: `tests/test_tui/test_asset_grid.py` adds the unsupported-toggle regression.
- Manual smoke: `agent-toolkit list --format=json --harness opencode` for an asset that declares `harnesses: [opencode]` but kind=agent → cell `unsupported`, no error.

## Notes for implementers

- Codex MCP adapter was added in `e06dc1c`; nothing to do on the MCP path.
- The "Mirror of bin/lib/common.sh" comment in `_list_json.py` is historical (bash CLI retired per `2026-05-04-retire-bash-cli-design.md`) — clean it up while editing.
- `validate_harness()` in `_link_lib.py` validates the harness *string*; we want a sibling that validates the *pair*. Reuse the same Click-exit pattern (exit 2, stderr message).
- Prefer making the loop in `project_from_file` filter by `is_supported` rather than catching `UnsupportedPair` inside it — the goal is a clean fail-fast at boundaries, not exception-driven control flow.

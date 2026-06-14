# Coverage spec: unit tests for every verb × asset_type × harness

**Date:** 2026-06-14
**Status:** spec (no code yet)
**Goal as stated:** "comprehensive and effective unit tests for every verb for every
asset_type and every harness."

## TL;DR — the feasibility verdict

The literal request ("every verb × every asset_type × every harness") naively expands
to **~8,200 combinations** (6 asset_types × 12 verbs × 57 harnesses × 2 scopes). That
product is the wrong target: it is mostly **impossible cells** (verbs an asset_type
doesn't have), **redundant cells** (57 harnesses collapse to 4 adapter mechanisms), and
would yield a slow, brittle suite with near-zero marginal defect detection.

When you audit the *real* matrix, the headline is the opposite of what it looks like:

- **At the (asset_type, verb) cell level the suite is already ~98% complete.** Of ~44
  registered command cells, **exactly one has zero test invocation: `agent update`.**
- The honest remaining work is therefore **not "fill empty cells"** — it is **depth
  inside cells**: error paths, project-scope coverage, and parametrizing the harness
  dimension where a verb currently hard-codes one representative harness.

So: **feasible and worth doing — but reframed.** Close the one real gap, then deepen the
thin cells. Do *not* build the literal product.

## How the matrix actually collapses

### Dimension 1 — asset_types × verbs is SPARSE (~44 real cells, not 72)

Registered commands per asset_type (from `src/agent_toolkit_cli/commands/<at>/*_cmd.py`,
plus skill's `install`/`add` which live in `skill_install.py`/wizard, not the commands
dir):

| verb       | skill | agent | instructions | pi-extension | mcp | bundle |
|------------|:---:|:---:|:---:|:---:|:---:|:---:|
| add        | ✓ | ✓ | — | ✓ | ✓ | — |
| install    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| list       | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| status     | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| push       | ✓ | ✓ | — | ✓ | — | — |
| doctor     | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| remove     | ✓ | ✓ | — | ✓ | ✓ | — |
| import     | ✓ | ✓ | — | ✓ | — | — |
| update     | ✓ | ✓ | — | ✓ | ✓ | — |
| reset      | ✓ | ✓ | — | ✓ | — | — |
| uninstall  | — | ✓ | ✓ | ✓ | ✓ | — |
| validate   | — | — | — | — | — | ✓ |

`uninstall` is not a skill verb (skill `remove` covers it); bundle has only `install` +
`validate`. Empty cells are *structural*, not gaps.

### Dimension 2 — 57 harnesses collapse to 4 adapter mechanisms

`src/agent_toolkit_cli/skill_agents.py` `AGENTS` has 57 entries, but every one routes
through one `subagent_mechanism`:

- `symlink` ×15 · `translate` ×9 · `config_file_folder` ×2 · `none` ×31 (unsupported /
  by-design).

Testing one representative harness per mechanism **is** testing the behavior. The other
56 are config-table rows, not code paths. The correct test of "all 57 harnesses" is a
**table-integrity test** (every harness maps to a valid adapter + reachable dir) — which
`tests/test_subagent_matrix.py` already does — plus per-mechanism behavioral tests, which
`tests/test_cli/test_agent_adapters/{test_symlink,test_translate,test_config_file_folder}.py`
already do via `@pytest.mark.parametrize`. MCP has its own 4-harness set
(claude-code / codex / opencode / pi); instructions has its own small set.

**Effective behavioral matrix ≈ 44 cells × ~4 mechanism-classes × 2 scopes**, a few
hundred meaningful tests — most of which already exist (baseline: ~1,316 `def test_`
functions, ~1,670 cases incl. parametrization).

## Audit result — where coverage actually stands

Authoritative per-cell audit (a regex over `tests/**.py` for every
`["<group>", "<verb>"]` CliRunner invocation, run 2026-06-14):

> **Every registered (asset_type, verb) cell is exercised by at least one test, EXCEPT
> `agent update`.**

This directly **corrects an earlier exploratory pass** that reported `uninstall`
untested across 5 asset_types and `agent` missing 6 verbs. Direct grep disproved it:
`agent` push/reset/import/uninstall/status all have tests; `uninstall` is covered for
agent/instructions/mcp/pi-extension. Treat the cell matrix as **done bar one cell.**

The real, defensible gaps are about **depth**, established by reading the cells:

| # | Gap | Evidence | Severity |
|---|-----|----------|----------|
| G1 | `agent update` has **zero** tests | only untested registered cell; cmd is ~90 lines w/ lock-read, per-slug fetch/merge, SHA write, 3 error branches | **High** — real logic, real bug surface |
| G2 | `skill install` / `mcp install` **hard-code `claude-code`** | `test_cli_skill_install.py` (claude-code/universal only); `test_cli_mcp.py` no per-harness parametrization | Medium — adapter regressions per mechanism go unseen |
| G3 | **Project scope** thin for agent / instructions / mcp / pi-extension | e2e tests cover global only | Medium |
| G4 | **Error paths** sparse across cells | few tests for dirty-canonical, lock-mismatch, missing-canonical, not-in-lock, bad-slug | Medium |
| G5 | git-state fixtures (`make_behind/ahead/diverged/conflict/dirty`) used **only by skill** | `conftest.py` defines them; agent/mcp/pi update+push don't reuse | Low–Medium |

## Scope of this work (per the chosen target: "close the real gaps")

Five deliverables. **G0 is the centerpiece** — it converts the one-off audit behind this
spec into a permanent CI invariant, which is the durable meaning of "comprehensive."

**In scope:**

0. **G0 — coverage-guard meta-test** *(centerpiece)*. A test that **enumerates every
   registered command cell** — `src/agent_toolkit_cli/commands/<at>/*_cmd.py` plus skill's
   `install`/`add` (which live in `skill_install.py` / wizard, not the commands dir) —
   and asserts each is invoked by ≥ 1 test (the same `["<group>","<verb>"]` invocation
   scan used for the audit, hardened against false negatives). Against the tree today it
   would fail on exactly one cell: `agent update`. After G1 it passes, and from then on
   **any newly-registered cell that ships without a test fails CI.** This institutionalizes
   the "every cell covered" invariant so it cannot silently regress. Must handle command
   aliases (`skills`/`mcps`/`pi-extension`) and skill's off-dir verbs without false gaps.
1. **G1 — `agent update` test file.** Clone the pi-extension update test
   (`tests/test_cli/test_cli_pi_extension_lifecycle.py` update cases) — `agent update`
   explicitly "mirrors pi-extension update_cmd." Cover: happy-path fetch+merge updates
   lock SHA; `slug not in lock`; `no .git in canonical`; no-lock-found; behind/ahead via
   the existing git-state fixtures. Landing G1 is what turns G0 green.
2. **G2 — parametrize the harness dimension where hard-coded.** Add a per-mechanism
   representative parametrization to `skill install` and `mcp install`, mirroring the
   agent-adapter pattern that already works. **One representative per mechanism, not all
   57:**
   - `skill install`: **claude-code** (symlink), **gemini-cli** (translate),
     **aider-desk** (config_file_folder).
   - `mcp install`: all **4** MCP harnesses (**claude-code, codex, opencode, pi**) — MCP's
     full harness set, not a sample.
3. **G3 — project-scope variants** for the verbs that mutate scope-specific state
   (install / uninstall / status / update) on agent / instructions / mcp / pi-extension
   (today these e2e paths cover global scope only).
4. **G4 — error-path tests** for each mutating verb: dirty canonical, lock mismatch,
   missing canonical, not-in-lock, invalid slug. Reuse `InstallError`-family assertions.

**Explicitly OUT of scope (diminishing returns or separate concern — documented so each
is a decision, not an omission):**

- Per-harness behavioral tests for all 57 agents on every verb. Table-integrity +
  per-mechanism tests already cover the risk; 57× parametrization buys ~0 defects for
  large runtime cost.
- New verbs for bundle (it has only install/validate by design).
- `uninstall`/`reset` for asset_types that structurally lack them.
- A `TESTING.md` rung-ladder declaration. That is the `/aj-test-plane` concern and a
  separate issue if wanted; bundling it here would be scope creep.

## Why this is low-risk to execute

- **Infrastructure is already excellent.** `conftest.py` provides `git_sandbox` +
  `make_behind/ahead/diverged/conflict/dirty` + `installed_skill` / `monorepo_skill` /
  `copymode_skill`. A typical CLI verb test is ~20–30 lines.
- **The work is template replication, not novel design.** Every gap has a proven
  sibling test to clone (skill→agent, pi-extension→agent, agent-adapters→skill/mcp).
- **Collapse points keep it small.** `_install_core.py` + parallel per-asset facades
  mean one mechanism test stands in for many harnesses.

## Estimated size

- G0: 1 guard meta-test (+ small enumeration helper), ~1–2 h.
- G1: 1 file, ~6–8 tests, ~1–2 h.
- G2: ~2 parametrized additions, ~7 cases (3 skill + 4 mcp), ~2 h.
- G3: ~8 scope-variant tests, ~1–2 h.
- G4: ~15–20 error-path tests spread across cells, ~3–4 h.

**Total ≈ 45–65 new tests + 1 guard, ~1 focused day.** Leaves the cell matrix complete,
the thin cells deepened, and the invariant enforced by CI — the real meaning of
"comprehensive," without the 8,200-cell trap.

## Decisions locked (2026-06-14)

1. **G0 coverage guard: IN.** Highest-leverage single addition; it's the centerpiece, not
   an optional extra.
2. **G2 representatives: one per mechanism.** skill → claude-code (symlink) / gemini-cli
   (translate) / aider-desk (config_file_folder); mcp → all 4 (claude-code, codex,
   opencode, pi). Not all 57.
3. **TESTING.md: OUT.** Separate `/aj-test-plane` concern; out of scope here.

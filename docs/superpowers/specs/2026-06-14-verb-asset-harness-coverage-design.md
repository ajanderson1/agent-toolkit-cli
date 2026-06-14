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

- **At the (asset_type, verb) cell level, every cell is _invoked_ by at least one test
  except one: `agent update`.** (Audit run 2026-06-14 over a ~1,527-function suite.)
- **Caveat — invocation ≠ effective coverage.** That audit proves a `["group","verb"]`
  invocation string exists in the test source; it does **not** prove the verb's behavior
  is meaningfully asserted. A `--help`-only test or a bare `assert exit_code == 0` smoke
  counts as "invoked" while verifying almost nothing. The user asked for *comprehensive
  **and effective*** tests — so the real work has two halves: (a) close the genuinely
  empty cell, and (b) confirm the *thin* cells (whose only coverage is a smoke/help test)
  actually assert behavior, deepening those that don't.
- The remaining work is therefore **not just "fill the one empty cell"** — it is **depth
  inside cells**: a thin-cell assertion audit, error paths, project-scope coverage, and
  parametrizing the harness dimension where a verb currently hard-codes one representative
  harness — plus a CI guard that prevents a cell from ever shipping *completely untested*.

So: **feasible and worth doing — but reframed.** Close the one real gap, audit the thin
cells, deepen where needed, and install the regression floor. Do *not* build the literal
8,200-cell product.

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
| uninstall  | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| validate   | — | — | — | — | — | ✓ |

bundle has only `install` + `validate`. **Correction (review):** `skill` *does* have
both `remove` and `uninstall` registered (as inline `@skill.command()` in
`commands/skill/__init__.py`, not `*_cmd.py` files) — the table shows skill `uninstall` as
`—` in error; it is a real, tested verb. Other empty cells are *structural*, not gaps.

### Dimension 2 — 57 harnesses collapse to 4 adapter mechanisms (with a caveat)

`src/agent_toolkit_cli/skill_agents.py` `AGENTS` has 57 entries, but every one routes
through one `subagent_mechanism`:

- `symlink` ×15 · `translate` ×9 · `config_file_folder` ×2 · `none` ×31 (unsupported /
  by-design).

Testing one representative harness per mechanism exercises the **projection algorithm**
for that mechanism. **Honest caveat (review):** the collapse is real for the *algorithm*
but **not** for *per-harness path config* — each harness carries its own `skills_dir` /
`global_skills_dir`, and a few (e.g. `_openclaw_skills_dir()`) compute their dir with live
branching. A per-mechanism test on claude-code does **not** exercise another symlink
harness's path computation. We accept that residual risk deliberately: the existing
`tests/test_subagent_matrix.py` already asserts every harness maps to a valid adapter +
cited path at the *catalog* level, and per-harness *runtime* path resolution for all 57 is
out of scope (a cheap optional path-well-formedness parametrization is noted under
follow-ups, not built here). The per-mechanism behavioral tests live in
`tests/test_cli/test_agent_adapters/{test_symlink,test_translate,test_config_file_folder}.py`
(via `@pytest.mark.parametrize`). MCP has its own 4-harness set
(claude-code / codex / opencode / pi); instructions has its own small set.

**Effective behavioral matrix ≈ 44 cells × ~4 mechanism-classes × 2 scopes**, a few
hundred meaningful tests — most of which already exist (baseline: ~1,527 `def test_`
functions incl. parametrization, measured 2026-06-14).

## Audit result — where coverage actually stands

Authoritative per-cell audit (a regex over `tests/**.py` for every
`["<group>", "<verb>"]` CliRunner invocation, run 2026-06-14):

> **Every registered (asset_type, verb) cell is exercised by at least one test, EXCEPT
> `agent update`.**

This **corrects an earlier exploratory pass** that reported `uninstall` untested across 5
asset_types and `agent` missing 6 verbs. Direct grep disproved it: `agent`
push/reset/import/uninstall/status all have tests; `uninstall` is covered for
agent/instructions/mcp/pi-extension. The cell matrix is **invoked bar one cell** — but
"invoked" is the weak claim (see the TL;DR caveat); *effectiveness* is audited separately
under G0b below.

The real, defensible gaps are about **depth**, established by reading the cells:

| # | Gap | Evidence | Severity |
|---|-----|----------|----------|
| G1 | `agent update` has **zero** tests | only un-invoked registered cell; cmd is ~90 lines w/ lock-read, per-slug fetch/merge, SHA write, 3 error branches | **High** — real logic, real bug surface |
| G0b | thin cells (only coverage is a `--help` / `exit_code==0` smoke) verify almost nothing | the user asked for *effective*, not just *invoked*, tests | Medium — appearance of coverage without substance |
| G2 | `skill install` / `mcp install` **hard-code `claude-code`** | `test_cli_skill_install.py` (claude-code/universal only); `test_cli_mcp.py` no per-harness parametrization | Medium — adapter regressions per mechanism go unseen |
| G3 | **Project scope** thin for agent / instructions / mcp / pi-extension | e2e tests cover global only (**note:** `mcp update` is global-only by design — no `-p`) | Medium |
| G4 | **Error paths** sparse across cells | few tests for dirty-canonical, lock-mismatch, missing-canonical, not-in-lock, bad-slug | Medium |
| G5 | git-state fixtures (`make_behind/ahead/diverged/conflict/dirty`) used **only by skill** | `conftest.py` defines them; agent/mcp/pi update+push don't reuse | Low–Medium |

## Scope of this work (per the chosen target: "close the real gaps")

Six deliverables. **G0 is the centerpiece** — it converts the one-off audit behind this
spec into a permanent CI regression floor. It is **not** a comprehensiveness guarantee: it
guarantees *no cell ships completely un-invoked*, which is the lowest bar worth enforcing,
not proof that any cell is effectively tested. G0b is what addresses *effectiveness*.

**In scope:**

0. **G0 — coverage-guard meta-test** *(centerpiece — honest framing)*. A test that
   **enumerates every registered command cell via Click introspection**
   (`main.commands` → each group's `.commands`), NOT a filesystem glob — so inline
   `@skill.command()` verbs (`remove`, `uninstall`) and any future inline registration are
   caught automatically (the glob approach missed two skill verbs — review finding).
   For each `(group, verb)` it asserts ≥ 1 test *names* it, by scanning the test corpus
   **with comments stripped** (a commented-out or dead invocation must NOT satisfy the
   guard — review finding) for a literal `["<group-or-alias>","<verb>"]` invocation.
   Against the tree today it fails on exactly one cell: `agent update`; after G1 it passes.
   Its **docstring must state honestly** what it guarantees: *"asserts every CLI command
   cell is named by at least one live test invocation; it does NOT assert the cell's
   behavior is verified — assertion depth is a reviewer/G0b concern, not enforced here."*
   Handles aliases (`skills`/`mcps`/`pi-extension`). The invariant it institutionalizes is
   **"no cell ships completely untested,"** worded that way — not "comprehensive."
0b. **G0b — thin-cell assertion audit** *(addresses "effective")*. Identify cells whose
   ONLY coverage is a `--help` invocation or a behaviorless `assert exit_code == 0` smoke
   (the audit's blind spot). For each, read the test and judge: does it assert real
   behavior? Produce a short findings list in the PR description; for any cell that is
   genuinely thin, add a behavior-asserting test (reusing the existing fixtures). This is
   the half of the work that answers the user's *effective* (not merely *invoked*) ask. It
   is bounded: only cells flagged thin by the audit, not a blanket rewrite.
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
   (today these e2e paths cover global scope only). **Exclude `mcp update` — it is
   global-only by design (no `-p` flag; review finding); do not write a `-p` test for it.**
4. **G4 — error-path tests**, **bounded** (review finding — the production tree has ~95
   raise sites; this is NOT "cover them all"): for each of the four core asset types,
   add the **not-in-lock** and **invalid-slug** cases for `update`/`push`/`reset`/`uninstall`,
   plus a **dirty-canonical** case *only* for verbs whose production code actually guards
   on a dirty tree (confirm by grep first; `agent update` has no such guard — do not assert
   one). Each error test asserts the **specific** production message string, never a
   permissive `exit≠0 OR "no" in output` disjunction (review finding — that is the
   "green checkmark without substance" the user is wary of).

**Explicitly OUT of scope (diminishing returns or separate concern — documented so each
is a decision, not an omission):**

- Per-harness *runtime* path-resolution tests for all 57 agents. Per-mechanism tests cover
  the projection algorithm; per-harness `skills_dir`/computed-dir divergence is accepted
  residual risk (a cheap path-well-formedness parametrization is a possible follow-up, not
  built here — review finding). 57× behavioral parametrization buys ~0 defects for large
  runtime cost.
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

- G0: 1 guard meta-test (Click-introspection enumeration + comment-stripped scan), ~1–2 h.
- G0b: thin-cell assertion audit + any behavior tests it surfaces, ~1–2 h.
- G1: 1 file, ~6–8 tests, ~1–2 h.
- G2: ~2 parametrized additions, ~7 cases (3 skill + 4 mcp), ~2 h.
- G3: ~6–8 scope-variant tests (excl. `mcp update`), ~1–2 h.
- G4: bounded error-path tests (~not-in-lock + invalid-slug × 4 asset types + the few
  real dirty guards), specific-message assertions, ~2–3 h.

**Total ≈ 45–65 new tests + 1 guard, ~1 focused day.** The high-value core is **G0+G0b+G1**
(close the one empty cell, install the honest regression floor, prove the thin cells are
effective) at ~4–6 h; G2–G4 are the depth tail. Leaves no cell un-invoked, the thin cells
audited for *effectiveness*, and the floor enforced by CI — answering "comprehensive **and
effective**" honestly, without the 8,200-cell trap.

## Decisions locked (2026-06-14, incl. critical-review)

1. **G0 coverage guard: IN, honestly framed.** Centerpiece, but it enforces *"no cell
   ships completely untested,"* not "comprehensive." Enumerate via **Click introspection**
   (not glob) and **strip comments** before scanning, per review.
2. **G0b thin-cell audit: ADDED.** The audit measures invocation, not behavior; G0b is the
   half that answers the user's *effective* ask. (Review: adversarial + product-lens.)
3. **G2 representatives: one per mechanism.** skill → claude-code (symlink) / gemini-cli
   (translate) / aider-desk (config_file_folder); mcp → all 4. Not all 57.
4. **Scope: full G0–G4, every review finding applied** (vs. trimming to the core). Per AJ.
5. **TESTING.md: OUT.** Separate `/aj-test-plane` concern.

## Critical review (2026-06-14)

`ce-doc-review` over spec + plan: coherence, feasibility, scope-guardian, adversarial,
product-lens. Findings resolved:

- ✓ **[HIGH] invocation ≠ effective coverage** (adversarial + product-lens) — reframed the
  TL;DR + guard docstring; added **G0b thin-cell audit**.
- ✓ **[HIGH] `agent update` no-lock test asserts a message that never prints** (feasibility,
  verified by running the code: `read_lock` swallows `FileNotFoundError`, so the no-lock
  path exits 0 with empty output) — plan test corrected to assert exit 0 + empty output.
- ✓ **[MED] guard under-enumerates (`skill remove`/`uninstall`)** (scope-guardian) — switch
  enumeration to **Click introspection**; matrix table corrected.
- ✓ **[MED] `mcp update` has no `-p` flag** (scope-guardian) — G3 excludes it explicitly.
- ✓ **[MED] 57→4 collapse is algorithm-only, not path-config** (adversarial) — narrowed the
  claim + moved per-harness path risk to OUT-of-scope as accepted residual.
- ✓ **[MED] guard gameable / passes on dead code** (adversarial) — strip comments; honest
  docstring naming the weak guarantee.
- ✓ **[MED] opportunity cost / padding** (product-lens) — surfaced the G0+G0b+G1 core vs
  G2–G4 tail in the estimate; AJ chose full scope deliberately.
- ✓ **[LOW] G1 non-git test seeds via wrong helper** (adversarial + feasibility — proven
  equal at global scope) — plan seeds at `library_agent_path` and states the equality as
  fact, dropping the hedge.
- ✓ **[LOW] permissive error-assertion disjunction** (product-lens) — G4 mandates
  specific-message assertions.
- ✓ **[LOW] stale baseline (1316→1527)** — corrected throughout.

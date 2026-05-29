# Decision: the 4 disabled `config_file_folder` agent cells

- **Date:** 2026-05-30
- **Issue:** #252 (agent / subagent kind, v3.1.0)
- **Status:** DECISION — two cells auto-actionable; one keep-disabled; one needs AJ confirmation
- **Author:** planning agent
- **Evidence base (ground truth, not assumption):** the merged PR2 adapter `src/agent_toolkit_cli/agent_adapters/config_file_folder.py` (read from `origin/main` `aff5467`), the dispatcher `agent_adapters/__init__.py`, the catalog `skill_agents.py`, the codex research fragment `docs/agent-toolkit/research/subagent-fragments/batch-4-codex-openai.md` (re-verified 2026-05-27 against live codex-rs source), and memory note `project_openspec_comparison_findings`.

## TL;DR (per-cell, one line each)

| Cell | Recommendation | Confidence | Auto-actionable? |
|---|---|---|---|
| `aider-desk` | **ENABLE** — pure self-owned per-slug file, no shared-file mutation | High | Yes — agent may build |
| `dexto` | **ENABLE (global-only)** — pure self-owned per-slug file, no shared-file mutation | High | Yes — agent may build |
| `firebender` | **KEEP DISABLED** — mutates a hot-reloaded shared `firebender.json` | Medium-High | N/A — needs AJ to overturn |
| `codex` | **NEEDS AJ DECISION** — registry-gated; no safe escape hatch exists; only path is mutating shared `config.toml` | Medium | No — AJ decides config-mutation question |

**Key correction to earlier assumptions:** the merged adapters do NOT edit free-form user config or `allowedAgents` arrays. **aider-desk and dexto write only into per-slug subdirectories under a dedicated dot-dir** (`.aider-desk/agents/<slug>/config.json`, `.dexto/agents/<slug>/<slug>.yml`) — they touch no shared file at all, exactly like `translate`. Only **firebender** (append-merges `.firebender/firebender.json`) and **codex** (section-edits `.codex/config.toml`) mutate a shared registry. This splits the four cleanly: two are trivially safe, two are the genuinely-shared-file cases.

**Headline:** enable `aider-desk` + `dexto` now (they are mislabelled — they are effectively translate-shaped self-owned writes, the PR2 disable was over-cautious for these two). Keep `firebender` disabled (hot-reloaded shared file). For `codex`, the OpenSpec `$CODEX_HOME/prompts/` escape hatch does **NOT** work — Codex's loader is registry-gated, so a self-owned file without a `config.toml` `[agents.<role>]` block is never loaded; AJ must decide whether to authorize shared-`config.toml` mutation or leave codex disabled.

## Background

PR2 (#268, merged `98257bb`) shipped symlink (15) + translate (9), 24 supported paths, plus `agent_install.py`, `agent_lock.py`, `agent_paths.py`, `agent_adapters/`. It deferred the 4 `config_file_folder` cells at `subagent_mechanism="none"`; the adapter code + ~13 unit tests are landed but the dispatcher (`get_adapter`) raises `UnsupportedMechanismError` for `"none"`. `test_pr2_disabled_cells_skip_cleanly` fails loud if a cell is re-enabled without leaving the disabled set.

The PR2 disable rationale was "mutating third-party config files is higher blast-radius." That is **correct for firebender and codex** but **over-broad for aider-desk and dexto**, whose merged adapters turned out to write only self-owned per-slug files (no shared mutation). The merged code already includes the right primitives: `_atomic_write` (write-temp + `os.replace`), and `_guard_foreign` (refuses to clobber a file lacking our `.<name>.attk` sidecar sentinel unless `overwrite=True`).

## The danger axis (now grounded in the merged code)

1. **Does the adapter mutate a SHARED file** (one holding unrelated entries owned by the user/another tool)? aider-desk: NO. dexto: NO. firebender: YES (`firebender.json`). codex: YES (`config.toml`).
2. **Is that shared file hot-reloaded by a running app?** firebender: YES (IntelliJ plugin). codex: the CLI re-reads on next invocation, not continuously, so lower contention than firebender — but still a shared global.

A cell is safe to enable when (1) is NO. Both shared-file cells additionally fail on the blast-radius/round-trip axes below.

## Per-cell evidence and decision

### `aider-desk` — ENABLE (High confidence, auto-actionable)

- **What the merged adapter does:** writes `<base>/.aider-desk/agents/<slug>/config.json` (base = `home` global / `project` project) containing `{"name", "subagent": {"enabled": true}, "source": <file text>}`. Removes the per-slug subdir on uninstall. **No shared file touched.** Guarded by `_guard_foreign`.
- **Danger:** essentially none — this is a self-owned per-slug write, mechanically identical to a `translate` cell. The "config file mutation" framing in the PR2 disable does not apply: there is no foreign config to corrupt.
- **Decision:** ENABLE.
- **Safety bar before merge:**
  - install→uninstall round-trip leaves `.aider-desk/agents/` clean (no orphan subdir).
  - both-scope (global + project) round-trip; lock records correct scope.
  - `_guard_foreign` honoured: refuse to clobber a pre-existing foreign `config.json` unless `overwrite=True`; install writes the `.config.json.attk` sentinel so a re-install is recognised as ours.
  - idempotency (double-install = one subdir, no error on the second when sentinel present).
  - fail-loud on unwritable base dir.

### `dexto` — ENABLE, GLOBAL-ONLY (High confidence, auto-actionable)

- **What the merged adapter does:** writes `home/.dexto/agents/<slug>/<slug>.yml` — a self-owned YAML with `name`, `description`, and a `source: |` block scalar (the PR2 review already fixed the block-scalar indentation via `textwrap.indent`). **Global-only by construction**: `install` and `destination` raise `ValueError("dexto: no project-scope convention exists; global-only writes")` for project scope; `uninstall` no-ops project scope. **No shared file touched.**
- **Danger:** none — self-owned per-slug write. Same shape as aider-desk.
- **Decision:** ENABLE, but **global-only** — match the adapter's existing contract (like `skill add` is global-only by construction, memory `project_skill_add_global_only`). Do NOT try to add project support; the adapter deliberately refuses it.
- **Safety bar before merge:**
  - global install→uninstall round-trip; YAML is valid (parse it back in the test, assert `source` block round-trips a multi-line agent file).
  - project-scope install raises (assert the `ValueError`); the agent facade/CLI must surface this as "dexto: global-only," not crash.
  - `_guard_foreign` + sentinel + idempotency + fail-loud as above.

### `firebender` — KEEP DISABLED (Medium-High confidence)

- **What the merged adapter does:** writes a per-slug `.firebender/agents/<slug>.md` (self-owned, fine) BUT ALSO **append-merges a relative path into the shared `.firebender/firebender.json` `agents` array** via `_atomic_write`. The PR2 review already caught + fixed two bugs here (silent `callable: false` preserve; project-scope absolute paths) — corroborating this is the fiddliest cell.
- **Danger:** the `firebender.json` mutation is the disqualifier. Per the PR2 disable rationale (and the upstream reality), `firebender.json` is **hot-reloaded by the running IntelliJ/JetBrains plugin**. Our atomic write reduces partial-read risk, but does not solve the deeper problem: the plugin may re-serialise the file on its own schedule (reordering/normalising keys, dropping our entry), and the file sits at a project/IDE root where a botched write is highly visible and may be committed. OpenSpec ships no firebender adapter either.
- **Escape-hatch search:** none. No documented runtime-discoverable agents drop-dir that avoids `firebender.json`.
- **Decision:** KEEP DISABLED. Leave `subagent_mechanism="none"`; surface the reason ("would mutate a hot-reloaded IDE registry, firebender.json") in doctor/capability output rather than silently omitting it.
- **Reopen trigger:** firebender ships a discoverable per-file agents dir that does NOT require editing `firebender.json` → revisit.
- **Note:** if AJ judges the atomic-write + relative-path + append-only (not clobber) design sufficient and accepts the hot-reload risk, this is a defensible ENABLE — hence "needs AJ to overturn," not a hard no. Lean disabled because it is the one cell with both a shared file AND a continuous live writer.

### `codex` — NEEDS AJ DECISION (Medium confidence; the escape hatch does NOT exist)

- **What the merged adapter does:** writes a self-owned `.codex/agents/<slug>.toml` (fine) AND **section-edits the shared `.codex/config.toml`** to add/replace an `[agents.<slug>]` block (with `description` + `config_file = "agents/<slug>.toml"`) via regex + `_atomic_write`.
- **Why config.toml mutation is unavoidable (the escape hatch is a dead end):** the codex research fragment (re-verified 2026-05-27 against live `codex-rs/config/src/config_toml.rs:649-691`) states plainly: *"Discovery is registry-gated: an agents/<role>.toml with NO matching config.toml block is NOT loaded… codex's loader only enumerates roles declared in config.toml."* So the OpenSpec `$CODEX_HOME/prompts/` pattern — drop a self-owned file in a scanned dir — **does not apply to codex subagents.** Prompts/commands may be discovered that way, but a *subagent* is only loaded if registered in `config.toml`. There is no safe, non-mutating path to a working codex subagent. (This corrects the earlier "enable via escape hatch" hypothesis: investigation shows it is impossible.)
- **Blast radius:** `config.toml` is the Codex CLI's global shared config (model/provider/unrelated settings). The merged adapter mutates it by regex section-replace (`\[agents\.<slug>\][^\[]*`, DOTALL) and re-serialises via raw string ops — which preserves the rest of the file textually (good) but is brittle: the regex assumes `[agents.<slug>]` sections are `[`-delimited and that no array-of-tables or nested `[agents.<slug>.x]` exists; a malformed edit breaks the whole CLI (strict TOML).
- **Decision:** **AJ DECISION REQUIRED.** This is the genuine product call the convention reserves for the user: *do we ever mutate a user's shared global config file?* Two honest options:
  1. **Enable codex** with the existing section-edit adapter, hardened: add a real round-trip-preserve test (unrelated keys/sections/comments survive), test the array-of-tables and nested-subtable cases the regex could mangle, and a "config.toml stays valid TOML after install AND uninstall" parse test. Accept that we mutate a shared global config (firebender then becomes harder to justify keeping disabled — they're the same class).
  2. **Keep codex disabled** — consistent with "never mutate a shared global config"; surface the reason "codex subagents require registering in the shared config.toml; not auto-enabled." This is OpenSpec's effective posture (they refused config.toml mutation and codex subagents are not the prompts-dir feature they support).
- **Recommendation:** lean toward option 2 (keep disabled) unless AJ wants codex subagents enough to accept shared-config mutation, because the regex-based TOML edit is the highest-fragility code path of the four and there is no escape hatch to fall back on. Either way it is AJ's call, not the agent's.

## Auto-actionable vs needs AJ

- **Auto-actionable (build under the plan, PR4):** `aider-desk`, `dexto` — self-owned per-slug writes, no shared mutation, adapter + tests already exist, safety bar mechanically checkable. dexto is global-only.
- **Needs AJ confirmation:**
  - `codex` — decide option 1 (authorize shared `config.toml` mutation, harden + enable) vs option 2 (keep disabled). The "escape hatch" is confirmed non-viable.
  - `firebender` — recommendation KEEP DISABLED (shared + hot-reloaded); needs AJ only to overturn. If AJ enables codex (option 1), revisit firebender for consistency.

This honours "config mutation is high-stakes — lean toward AJ-confirm for the genuinely dangerous ones." The two non-mutating cells proceed; the two shared-registry cells wait for AJ.

## Cross-cutting safety contract for any enabled cell

1. **Install → uninstall round-trip** leaves the harness dir clean (self-owned cells) or the shared file byte-equivalent modulo our entry (shared cells).
2. **Both-scope** except cells global-only by construction (dexto).
3. **Config-preserve** (shared cells only): unrelated keys/sections/comments/order survive — required before any codex/firebender enable.
4. **Foreign-guard:** `_guard_foreign` + `.<name>.attk` sentinel already implemented; tests must assert it refuses foreign files and recognises our own.
5. **Atomic write** (`_atomic_write`) already used for shared-file writes; keep it.
6. **Idempotency:** double-install is a no-op beyond the first.
7. **Fail loud** on unwritable dirs / malformed existing files / unexpected schema — never silently skip a cell.

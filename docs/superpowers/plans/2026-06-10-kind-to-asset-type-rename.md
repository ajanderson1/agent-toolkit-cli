# Kind → Asset-Type Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the "kind" terminology to "asset" / "asset type" throughout code and living docs with zero behavioural or serialized-format change (issue #355, spec `docs/superpowers/specs/2026-06-10-kind-to-asset-type-rename-design.md`).

**Architecture:** Pure mechanical rename in 6 commits: core path/lock seam → doctors → TUI → remaining src/tests sweep → living docs + site generator → final audit. The existing test suite is the safety net (no new behaviour, so no new TDD cycles); each task ends with the full suite green. A baseline CLI-output snapshot taken first proves byte-identical output at the end.

**Tech Stack:** Python 3.12, Click, Textual, pytest, mypy --strict, ruff, MkDocs Material.

**Branch:** work in a worktree at `.worktrees/355-asset-type-rename`, branched from current `main`.

---

## Global rename contract (applies to every task)

| Old | New |
|---|---|
| `KindBinding` | `AssetTypeBinding` |
| `KindBinding.kind` (field) | `asset_type` |
| `library_root_for_kind` | `library_root_for_asset_type` |
| `library_lock_path_for_kind` | `library_lock_path_for_asset_type` |
| `kind_noun` | `asset_type_noun` |
| `FindingKind` | `FindingType` |
| `Finding.kind` (field, all 3 doctor Finding classes) | `finding_type` |
| TUI `Kind` (Literal alias) | `AssetType` |
| TUI `_active_kind` / `action_kind` / `_show_kind` | `_active_asset_type` / `action_asset_type` / `_show_asset_type` |
| TUI `_KIND_LABELS` / `kind_label` (app.py l.48, l.918, l.939) | `_ASSET_TYPE_LABELS` / `asset_type_label` |
| test function/file names containing `kind` (e.g. `test_kind_sidebar_lists_three_kinds`, `test_kind_binding_is_frozen_dataclass`) | `asset_type` equivalents |
| DOM/CSS ids `kinds-sidebar`, `kinds-list`, `kind-<x>` | `asset-types-sidebar`, `asset-types-list`, `asset-type-<x>` |
| prose "kind" / "asset kind" (this taxonomy) | "asset type" |
| prose "the four kinds" / "per-kind" / "cross-kind" | "the four asset types" / "per-asset-type" / "cross-asset-type" |

**NEVER touch (the no-breaking-changes allowlist):**

1. `src/agent_toolkit_cli/agent_adapters/translate.py` — the `"kind"` string in the
   frontmatter passthrough tuple (~line 190). It is a FOREIGN key from external
   agent frontmatter formats. Leave the line byte-identical.
2. The four classifier **values** `"skill"`, `"agent"`, `"instructions"`,
   `"pi-extension"` — load-bearing strings (library dirs, lock filenames).
3. Lockfile content/keys — no `kind` key exists; if you find yourself editing a
   `*-lock.json`, stop: you are off-plan.
4. CLI command names, flags, exit codes. (No `--kind` flag exists.)
5. Historical dated docs: `docs/superpowers/specs/`, `docs/superpowers/plans/`,
   `docs/solutions/`, `docs/audit/`, `docs/agent-toolkit/research/`.
6. English uses of "kind" that are NOT this taxonomy (e.g. "some kind of",
   "kindly") — judge each docs hit; only the asset-classifier sense renames.
7. The serialized `kind:` metadata-block key and quoted schema examples in
   `docs/agent-toolkit/schema.md` (e.g. `kind: plugin`) — that file documents
   an on-disk format real artifacts carry, exactly like translate.py's
   passthrough key. Its surrounding PROSE may rename; the format-key lines and
   YAML examples stay byte-identical and count as tolerated grep survivors.

---

### Task 1: Worktree + baseline snapshot

**Files:** none modified.

- [ ] **Step 1: Create the worktree**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli
git worktree add .worktrees/355-asset-type-rename -b 355-asset-type-rename main
cd .worktrees/355-asset-type-rename
```

- [ ] **Step 2: Verify suite green at baseline**

Run: `uv run pytest -q`
Expected: all pass (note the exact pass count for later comparison; one known local-only flake: `test_empty_machine_is_empty` may fail outside CI — ignore it if it is the sole failure).

- [ ] **Step 3: Capture baseline CLI output in a sandbox HOME**

An empty sandbox produces trivially-empty list/doctor output that would diff
clean even across a broken rename — seed it with one real skill first so the
snapshots exercise library-root derivation, lock reads, and table rendering.
`instructions list` is the highest-risk command (it parses
`docs/agent-toolkit/harness-matrix.md`, which Task 5/6 edit) — capture it
explicitly.

```bash
export SANDBOX=/tmp/355-baseline && mkdir -p "$SANDBOX/home"
# Seed: install one skill globally into the sandbox HOME (any small public
# skill repo works; use an existing local fixture if offline).
HOME="$SANDBOX/home" uv run agent-toolkit-cli skill add https://github.com/anthropics/skills --skill document-skills/pdf 2>&1 | tail -2
for noun in skill agent instructions pi-extension; do
  HOME="$SANDBOX/home" uv run agent-toolkit-cli $noun --help > "$SANDBOX/$noun-help.txt" 2>&1 || true
  HOME="$SANDBOX/home" uv run agent-toolkit-cli $noun list -g > "$SANDBOX/$noun-list.txt" 2>&1 || true
  HOME="$SANDBOX/home" uv run agent-toolkit-cli $noun doctor -g > "$SANDBOX/$noun-doctor.txt" 2>&1 || true
done
HOME="$SANDBOX/home" uv run agent-toolkit-cli instructions list > "$SANDBOX/instructions-list-cwd.txt" 2>&1 || true
```

Expected: files created; `skill-list.txt` shows the seeded skill (non-empty).
These are diffed in Task 7.

---

### Task 2: Core seam — `_paths_core.py`, facades, `_install_core.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py`
- Modify: `src/agent_toolkit_cli/skill_paths.py`, `src/agent_toolkit_cli/agent_paths.py`, `src/agent_toolkit_cli/instructions_paths.py`, `src/agent_toolkit_cli/pi_extension_paths.py`
- Modify: `src/agent_toolkit_cli/_install_core.py`
- Test (update only): `tests/test_cli/test_paths_core.py`, `tests/test_cli/test_paths_core_agent_binding.py`, `tests/test_cli/test_paths_core_instructions_binding.py`, `tests/test_cli/test_paths_core_pi_extension_binding.py`, `tests/test_cli/test_install_core.py`, `tests/test_cli/test_agent_list_table.py`, `tests/test_cli/test_skill_list_table.py`

- [ ] **Step 1: Rename in `_paths_core.py`**

The dataclass and helpers become (docstrings updated to "asset type" prose; structure otherwise unchanged):

```python
"""Asset-type-agnostic path/lock-filename core. Bound by per-asset-type facades."""

@dataclass(frozen=True)
class AssetTypeBinding:
    asset_type: str            # "skill" | "agent" | ...
    ...                        # remaining fields unchanged

SKILL_BINDING = AssetTypeBinding(
    asset_type="skill",
    ...
)
# same for INSTRUCTIONS_BINDING (asset_type="instructions"),
# AGENT_BINDING (asset_type="agent"), PI_EXTENSION_BINDING (asset_type="pi-extension")

def library_root_for_asset_type(binding: AssetTypeBinding, env: dict[str, str] | None = None) -> Path:
    ...
    if binding.asset_type == "skill":
        ...

def library_lock_path_for_asset_type(binding: AssetTypeBinding, env: dict[str, str] | None = None) -> Path:
    ...
    return library_root_for_asset_type(binding, env).parent / binding.lock_filename
```

The string VALUES (`"skill"` etc.) and all other fields/logic stay byte-identical.

- [ ] **Step 2: Update the four facades + `_install_core.py`**

In each of `skill_paths.py`, `agent_paths.py`, `instructions_paths.py`,
`pi_extension_paths.py`: update the imports/calls
`library_root_for_kind` → `library_root_for_asset_type`,
`library_lock_path_for_kind` → `library_lock_path_for_asset_type`.
In `_install_core.py`: `KindBinding` → `AssetTypeBinding`, parameter/variable
`kind_noun` → `asset_type_noun` (the f-string output text
`"\n  Run: agent-toolkit-cli {asset_type_noun} doctor {flag}  (removes stray symlinks)"`
is unchanged because it interpolates the value).

- [ ] **Step 3: Update the listed test files** — same identifier map, including any
`kind=` kwargs in test fixture `AssetTypeBinding(...)` constructions → `asset_type=`.

- [ ] **Step 4: Verify no stragglers, suite green**

```bash
grep -rn "KindBinding\|library_root_for_kind\|library_lock_path_for_kind\|kind_noun" src/ tests/
```
Expected: zero hits.
Run: `uv run pytest -q` → same pass count as baseline.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: rename core kind seam to asset type (#355)"
```

---

### Task 3: Doctors — `FindingType` / `finding_type`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py` (FindingKind def ~l.29, `Finding.kind` ~l.46, ~14 `kind=` constructor sites)
- Modify: `src/agent_toolkit_cli/pi_extension_doctor.py` (FindingKind def ~l.41, field ~l.60, ~6 `kind=` sites)
- Modify: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py` (local `Finding.kind: str` ~l.36, 4 `kind=` sites, echo ~l.166)
- Modify: `src/agent_toolkit_cli/commands/skill/doctor_cmd.py` (echo ~l.44), `src/agent_toolkit_cli/commands/pi_extension/doctor_cmd.py` (echo ~l.62)
- Test (update only): `tests/test_cli/test_skill_doctor.py` + any test referencing `.kind` on findings (`grep -rn "\.kind\b" tests/`)

- [ ] **Step 1: Rename type alias + field in the three Finding classes**

```python
FindingType = Literal[ ... ]   # values unchanged

@dataclass
class Finding:
    finding_type: FindingType   # was: kind
    ...
```

All `Finding(kind=...)` constructor sites become `Finding(finding_type=...)`;
the Literal VALUES ("stray_symlink", "missing-canonical", …) are unchanged.

- [ ] **Step 2: Update the three echo sites**

```python
click.echo(f"{f.slug} · {f.finding_type} ({f.scope})")
```

Output is byte-identical (the value prints, not the field name).

- [ ] **Step 3: Update tests touching `.kind` / `kind=` on findings**, verify, commit

```bash
grep -rn "FindingKind\|finding\.kind\|f\.kind\b" src/ tests/   # expect zero hits
uv run pytest -q                                               # baseline pass count
git add -A && git commit -m "refactor: rename doctor FindingKind to FindingType (#355)"
```

---

### Task 4: TUI

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (Literal alias l.46, `_active_kind`, `_show_kind`, `action_kind`, sidebar Option ids l.143-148, DOM ids, comments l.11-18)
- Modify: `src/agent_toolkit_tui/css/app.tcss` (`#kinds-sidebar` → `#asset-types-sidebar`, `#kinds-list` → `#asset-types-list`, all 6 selectors)
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py` (info-pane strings l.192, l.209: "the kind lock" → "the asset-type lock")
- Modify: `src/agent_toolkit_tui/agent_state.py` l.4, `src/agent_toolkit_tui/instruction_state.py` l.4 (docstring prose)
- Test (update only): `tests/test_tui/test_sidebar_highlight_sync.py`, `tests/test_tui/test_scope_toggle.py`, `tests/test_tui/test_agent_grid.py`, `tests/test_tui/test_instruction_grid.py`, `tests/test_tui/test_pi_grid.py`, `tests/test_tui/test_pi_apply_roundtrip.py`, `tests/test_tui/test_status_counters.py` (any that query `#kinds-list` / option ids / call `action_kind`)

- [ ] **Step 1: app.py rename**

```python
AssetType = Literal["instruction", "skill", "pi-extension", "agent"]
...
self._active_asset_type: AssetType = "skill"
...
with Vertical(id="asset-types-sidebar"):
    ...
    Option("instruction", id="asset-type-instruction"),
    Option("─────────────", id="asset-type-separator", disabled=True),
    Option("skill", id="asset-type-skill"),
    Option("pi-extension", id="asset-type-pi-extension"),
    Option("agent", id="asset-type-agent"),
    id="asset-types-list",
...
def _show_asset_type(self, asset_type: AssetType) -> None: ...
def action_asset_type(self, asset_type: str) -> None: ...
```

Every internal reference (`get_option_index(f"asset-type-{asset_type}")`, the
option-selected handler's id comparisons, `self._active_asset_type` reads)
follows. Visible option labels ("skill", …) unchanged.
`action_asset_type` is only called directly in code (verified — no Textual
`Binding("…", "kind(...)")` strings exist), so the action rename is safe.

The sidebar's rail header (app.py l.157) is the ONE intended visible TUI text
change on this PR:

```python
Static("Asset type", classes="rail-header")   # was: Static("Kind", ...)
```

The `.rail-header` class selector in `app.tcss` is unchanged. Eyeball the
sidebar width after the change (`uv run agent-toolkit-tui`): "Asset type" is
10 chars vs 4 — if it truncates, widen `#asset-types-sidebar` in `app.tcss`
by the difference.

- [ ] **Step 2: app.tcss + pi_grid strings + state-module docstrings** per the file list above.

- [ ] **Step 3: Update TUI tests, verify, commit**

```bash
grep -rn "kinds-sidebar\|kinds-list\|kind-\|action_kind\|_active_kind\|_show_kind\|Kind\b" src/agent_toolkit_tui/ tests/test_tui/
```
Expected: zero hits (case-sensitive `Kind` — `AssetType` replaces it).
Run: `uv run pytest tests/test_tui -q` then `uv run pytest -q` → baseline pass count.

```bash
git add -A && git commit -m "refactor: rename TUI kind surfaces to asset type (#355)"
```

---

### Task 5: Remaining src + tests sweep

**Files:**
- Modify (prose/comments/help only): `src/agent_toolkit_cli/commands/instructions/__init__.py` (docstring), `src/agent_toolkit_cli/commands/instructions/list_cmd.py` (help string → `"Per-harness verdict for the instructions asset type."`), `src/agent_toolkit_cli/instructions_adapters/symlink.py` (docstring l.7, comment l.31, error message l.146 → `f"unknown harness for instructions asset type: {harness!r}"`), `src/agent_toolkit_cli/instructions_adapters/__init__.py`, `src/agent_toolkit_cli/agent_adapters/__init__.py` (comments l.13, l.29), `src/agent_toolkit_cli/agent_install.py`, `src/agent_toolkit_cli/agent_lock.py`, `src/agent_toolkit_cli/instructions_lock.py`, `src/agent_toolkit_cli/pi_extension_install.py`, `src/agent_toolkit_cli/pi_extension_inventory.py`, `src/agent_toolkit_cli/pi_extension_lock.py`, `src/agent_toolkit_cli/skill_git.py` (any residual "kind" prose found by grep)
- Rename: `tests/test_cli/test_kind_architecture.py` → `tests/test_cli/test_asset_type_architecture.py` (`git mv`, plus internal prose/identifiers)
- Modify: remaining test files from the inventory (`tests/test_cli/test_agent_general_rename.py`, `test_agent_install_roundtrip.py`, `test_agent_lock.py`, `test_cli_agent_group.py`, `test_instructions_adapters/*`, `test_lock_agent_path.py`, `test_relocate_project_canonical.py`, `test_skill_facade_parity.py`, `test_skill_nested_monorepo.py`, `tests/test_instructions_matrix.py`, `tests/test_skill_git_resolve_ref.py`, `tests/test_subagent_matrix.py`)
- Modify (parse contract — see Step 0): `docs/agent-toolkit/harness-matrix.md` lines 54 and 163 ONLY (the two section headings)

- [ ] **Step 0: Atomically rename the load-bearing matrix headings (code + tests + doc together)**

Two literal heading strings are a byte-match PARSE CONTRACT between code and
`docs/agent-toolkit/harness-matrix.md` — `_parse_matrix()` does
`text.split(_SECTION_HEADING, 1)[1]`, so renaming one side without the other
makes `instructions list` raise IndexError and fails the matrix tests. All six
occurrences change in THIS commit, never split across commits:

| String | Sites |
|---|---|
| `## Instruction-file (\`instructions\` kind) support — all harnesses` → `## Instruction-file (\`instructions\` asset type) support — all harnesses` | `src/agent_toolkit_cli/commands/instructions/list_cmd.py:22`, `tests/test_instructions_matrix.py:38`, `tests/test_cli/test_instructions_adapters/test_dispatcher.py:17`, `docs/agent-toolkit/harness-matrix.md:163` |
| `## Subagent (agent kind) support — all harnesses` → `## Subagent (agent asset type) support — all harnesses` | `tests/test_subagent_matrix.py:37`, `docs/agent-toolkit/harness-matrix.md:54` |

After editing, prove the contract held:

Run: `uv run pytest tests/test_instructions_matrix.py tests/test_subagent_matrix.py -q && uv run agent-toolkit-cli instructions list >/dev/null && echo CONTRACT-OK`
Expected: tests pass, `CONTRACT-OK` prints.

(Task 6 then renames only the REMAINING harness-matrix.md prose — the headings
are already done.)

- [ ] **Step 1: Sweep every remaining `kind` hit in `src/` and `tests/`**

```bash
grep -rniw "kind\|kinds" src/ tests/ --include="*.py" --include="*.tcss"
```

For each hit, apply the global contract; the ONLY permitted survivor is the
foreign `"kind"` key line in `agent_adapters/translate.py`. The error message
in `symlink.py` l.146 changes text — if any test asserts on that message
(check with `grep -rn "unknown harness for instructions" tests/`), update the
assertion in the same commit.

- [ ] **Step 2: Verify, commit**

```bash
grep -rniw "kind\|kinds" src/ tests/ --include="*.py" --include="*.tcss" | grep -v "agent_adapters/translate.py"
```
Expected: zero lines.
Run: `uv run pytest -q && uv run mypy src/ --strict && uv run ruff check .`
Expected: all green, baseline pass count.

```bash
git add -A && git commit -m "refactor: sweep remaining kind terminology from src and tests (#355)"
```

---

### Task 6: Living docs + site generator

**Files:**
- Modify: `scripts/gen_harness_docs.py` (27 hits: legend l.191, kind-page links l.233-237, prose l.259-298, glossary anchor link `glossary.md#kind` → `glossary.md#asset-type`, "## The kinds" → "## The asset types")
- Rename: `docs/kinds/` → `docs/asset-types/` (`git mv`; 5 files inside keep their names)
- Modify: `mkdocs.yml` (nav l.122-128: section label `Kinds:` → `Asset types:`, paths `kinds/*.md` → `asset-types/*.md`)
- Modify: `docs/glossary.md` (rename the "kind" entry/heading to "asset type", keep a one-line pointer: *"kind — former name for asset type"*), `docs/matrix.md` + `docs/harnesses/*.md` (regenerated), `docs/agent-toolkit/harness-matrix.md` (remaining prose uses — the two section headings were already renamed atomically in Task 5 Step 0), `docs/agent-toolkit/roadmap.md`, `docs/agent-toolkit/schema.md` (prose ONLY — allowlist entry 7 keeps the serialized `kind:` key lines and YAML examples byte-identical), `docs/agent-toolkit/skill-lock.md`, `docs/index.md` (if it links kinds/), the 5 files now in `docs/asset-types/` (internal prose)
- DO NOT touch: `docs/superpowers/`, `docs/solutions/`, `docs/audit/`, `docs/agent-toolkit/research/`

- [ ] **Step 1: `git mv docs/kinds docs/asset-types`**, update `mkdocs.yml` nav.

- [ ] **Step 2: Edit `scripts/gen_harness_docs.py`** per the contract (link targets
`asset-types/<x>.md`, prose "asset type"), then regenerate:

Run: `uv run python scripts/gen_harness_docs.py`
Expected: `docs/matrix.md` + `docs/harnesses/*.md` rewritten with no `kinds/` links and no taxonomy-sense "kind".

- [ ] **Step 3: Hand-edit the non-generated living docs** listed above (taxonomy sense only — ordinary-English "kind" stays).

- [ ] **Step 4: Verify + build + commit**

```bash
grep -rniw "kind\|kinds" docs/ mkdocs.yml scripts/ \
  | grep -v "superpowers/\|solutions/\|audit/\|research/" \
  | grep -vi "kind of\|kindly\|former name"
uv run mkdocs build --strict
uv run pytest tests/test_instructions_matrix.py tests/test_subagent_matrix.py -q
```
Expected: grep shows only deliberate survivors (the glossary pointer line and
schema.md's serialized-key lines per allowlist entry 7); mkdocs build passes
with no broken-link warnings; the matrix-parity tests stay green (they are the
only automated check that the harness-matrix.md edits stayed in sync with the
code's parse strings).

```bash
git add -A && git commit -m "docs: rename kind terminology to asset type across living docs (#355)"
```

---

### Task 7: Final audit + PR

**Files:** none (verification only, unless the audit finds stragglers).

- [ ] **Step 1: Byte-identical output check vs Task 1 baseline**

```bash
export SANDBOX=/tmp/355-baseline
for noun in skill agent instructions pi-extension; do
  for verb in help list doctor; do
    case "$verb" in
      help) cmd="$noun --help" ;;
      *)    cmd="$noun $verb -g" ;;
    esac
    HOME="$SANDBOX/home" uv run agent-toolkit-cli $cmd > "/tmp/355-after-$noun-$verb.txt" 2>&1 || true
    diff "$SANDBOX/$noun-$verb.txt" "/tmp/355-after-$noun-$verb.txt" || echo "DIFF in $noun $verb"
  done
done
HOME="$SANDBOX/home" uv run agent-toolkit-cli instructions list > /tmp/355-after-instructions-list-cwd.txt 2>&1 || true
diff "$SANDBOX/instructions-list-cwd.txt" /tmp/355-after-instructions-list-cwd.txt || echo "DIFF in instructions list"
```

Expected: all `list` / `doctor` outputs byte-identical (including the seeded
skill rows and the matrix-parsed `instructions list` table); `--help` diffs
limited to exactly two help-prose renames — the `instructions` group docstring
("Root for the instructions-…") and the `instructions list` short help. Any
other diff line is a regression: stop and investigate before the PR.

- [ ] **Step 2: Full gate**

Run: `uv run pytest -q && uv run mypy src/ --strict && uv run ruff check .`
Expected: green, baseline pass count.

- [ ] **Step 3: Final grep audit (the acceptance criterion)**

Two passes — `-w` alone is blind to underscore-joined identifiers
(`_KIND_LABELS`, `kind_label`, `test_kind_*` names) because grep treats `_` as
a word character, so the non-word pass is the one that actually proves the
identifiers died:

```bash
grep -rniw "kind\|kinds" src/ tests/ | grep -v "agent_adapters/translate.py"
grep -rni "kind" src/ tests/ | grep -v "agent_adapters/translate.py"
```
Expected: zero lines from BOTH passes.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin 355-asset-type-rename
gh pr create --title "refactor: rename 'kind' terminology to 'asset type'" \
  --body "Closes #355. Mechanical rename per spec docs/superpowers/specs/2026-06-10-kind-to-asset-type-rename-design.md. No serialized formats, CLI contracts, or classifier values touched; doctor/list output byte-identical (verified against sandbox baseline)."
```

Expected: PR opens; CI green. `refactor:` type → release-please cuts no feature release.

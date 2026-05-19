# Claude command/agent `.md` suffix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent-toolkit link` write Claude command and agent symlinks with a `.md` filename suffix so Claude Code's discovery (`*.md` glob) actually picks them up.

**Architecture:** Promote the file-slot naming rule out of `_translated_slot_filename` (which is gated by `is_translated`) into a function that's a pure property of `(harness, kind)`. Apply it at the link call site regardless of translation status. Helper is already used by `doctor/symlinks.py` and `commands/_list_json.py`, so widening it fixes everything atomically.

**Tech Stack:** Python 3, pytest, `uv` for env management. Pre-commit runs `pytest` + a schema vendor check.

---

### Task 1: Failing test — claude command links with `.md` suffix

**Files:**
- Modify: `tests/test_link_lib.py` (append at end)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_link_lib.py`:

```python
from pathlib import Path
from io import StringIO

from agent_toolkit_cli.commands._link_lib import (
    LinkCounters,
    maybe_link,
)


def _make_md_asset(tmp_path: Path, kind_dir: str, slug: str) -> Path:
    """Create a minimal asset file with `claude` declared in spec.harnesses."""
    root = tmp_path / "toolkit" / kind_dir / slug
    root.mkdir(parents=True)
    p = root / f"{slug}.md"
    p.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# body\n",
        encoding="utf-8",
    )
    return p


def test_claude_command_slot_uses_md_suffix(tmp_path):
    asset = _make_md_asset(tmp_path, "commands", "demo-cmd")
    target_dir = tmp_path / ".claude" / "commands"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="command",
        slug="demo-cmd",
        asset_path=asset,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-cmd.md"
    assert expected.is_symlink(), (
        f"expected {expected} to exist as a symlink; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
    assert expected.resolve() == asset.resolve()
    assert not (target_dir / "demo-cmd").exists()


def test_claude_agent_slot_uses_md_suffix(tmp_path):
    asset = _make_md_asset(tmp_path, "agents", "demo-agent")
    target_dir = tmp_path / ".claude" / "agents"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="agent",
        slug="demo-agent",
        asset_path=asset,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-agent.md"
    assert expected.is_symlink()
    assert expected.resolve() == asset.resolve()


def test_claude_skill_slot_remains_bare_slug(tmp_path):
    """Regression: skills are directory-shaped and must NOT get a .md suffix."""
    root = tmp_path / "toolkit" / "skills" / "demo-skill"
    root.mkdir(parents=True)
    sk = root / "SKILL.md"
    sk.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# body\n",
        encoding="utf-8",
    )
    target_dir = tmp_path / ".claude" / "skills"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="skill",
        slug="demo-skill",
        asset_path=sk,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-skill"
    assert expected.is_symlink(), (
        f"expected bare-slug symlink at {expected}; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
    # Skill source is the directory containing SKILL.md
    assert expected.resolve() == root.resolve()
    assert not (target_dir / "demo-skill.md").exists()
```

- [ ] **Step 2: Run tests to verify the two new ones fail and the skill test passes**

Run: `uv run pytest tests/test_link_lib.py -k "claude_command_slot or claude_agent_slot or claude_skill_slot" -v`

Expected:
- `test_claude_command_slot_uses_md_suffix` — **FAIL** (symlink created at `.claude/commands/demo-cmd`, not `demo-cmd.md`)
- `test_claude_agent_slot_uses_md_suffix` — **FAIL** (same shape)
- `test_claude_skill_slot_remains_bare_slug` — **PASS** (skills are unaffected by the upcoming change)

If the skill test fails too, the planned fix is over-broad; stop and re-scope.

---

### Task 2: Widen the slot-filename rule and apply unconditionally

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:96-107` (function body)
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:347` (call site)

- [ ] **Step 1: Extend `_translated_slot_filename` to cover claude commands and agents**

Replace the body of `_translated_slot_filename` at `src/agent_toolkit_cli/commands/_link_lib.py:96-107`:

```python
def _translated_slot_filename(slug: str, kind: str, harness: str) -> str:
    """Return the filename used for the slot symlink in this (harness, kind).

    File-slot kinds get `<slug>.md` — these are slots where the harness
    discovers content by globbing `*.md` files in the slot directory.
    Currently that's `(opencode, agent|command)` and `(claude, agent|command)`.
    Directory-slot kinds — and any unsupported pair — get the bare `<slug>`.

    Callers can detect the slot shape from the result: `endswith(".md")` ⇒
    file-slot; otherwise directory-slot or non-translated.
    """
    if kind in {"agent", "command"} and harness in {"opencode", "claude"}:
        return f"{slug}.md"
    return slug
```

The name `_translated_slot_filename` is now a misnomer (it covers non-translated cells too), but renaming would touch four files for no behavioural gain — leaving as-is and updating only the docstring.

- [ ] **Step 2: Drop the `is_translated` gate at the link call site**

At `src/agent_toolkit_cli/commands/_link_lib.py:347`, replace:

```python
    slot_filename = _translated_slot_filename(slug, kind, harness) if is_translated else slug
```

with:

```python
    slot_filename = _translated_slot_filename(slug, kind, harness)
```

Do **not** touch the existing `is_translated` logic elsewhere in `maybe_link` — that drives the translate-cache path, which is correct for the cells where it's True and irrelevant for `(claude, agent|command)`.

- [ ] **Step 3: Run the new tests — both should now pass**

Run: `uv run pytest tests/test_link_lib.py -k "claude_command_slot or claude_agent_slot or claude_skill_slot" -v`

Expected: 3 PASSED.

If the skill test now fails, the change is over-broad — revert and revisit.

- [ ] **Step 4: Run the full pytest suite**

Run: `uv run pytest -q`

Expected: all green (was 689 passed, 1 skipped before this change). The doctor/symlinks and list_json modules already call `_translated_slot_filename` unconditionally, so they pick up the new behaviour automatically; any test that was asserting bare-slug paths for claude commands/agents will fail and reveal a stale expectation that needs updating in this same task. If any test fails, update the expectation to `<slug>.md` (do not work around the new behaviour).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "fix(#82): link claude command/agent slots with .md suffix

Claude Code discovers commands and agents by globbing *.md in
~/.claude/commands and ~/.claude/agents. The linker was writing bare-slug
symlinks for these cells, so linked commands/agents were silently invisible.

Widens _translated_slot_filename to cover (claude, agent|command) and drops
the is_translated gate at the link call site so the rule applies to direct
symlinks too (claude commands/agents have no translator)."
```

---

### Task 3: End-to-end reproduction of the issue's repro

**Files:**
- No code changes; verification only.

- [ ] **Step 1: Reproduce the original bug scenario in a tmp dir**

Run in a fresh shell, from the worktree root:

```bash
set -euo pipefail
WORK="$(mktemp -d)"
cd "$WORK"
mkdir -p .agent-toolkit
cat > .agent-toolkit.yaml <<'YAML'
skills: []
agents: []
commands: []
hooks: []
plugins: []
mcps: []
pi_extensions: []
YAML
echo "$WORK"
```

(We don't actually need to populate `commands:` with a real toolkit slug for the test — the unit tests above cover the projection algorithm. This step just confirms the CLI runs to completion against a trivial repo.)

Run: `uv run agent-toolkit link project claude --dry-run`

Expected: exit 0, "Nothing to change." (no commands declared, nothing to project).

- [ ] **Step 2: Save artifact**

Capture the output of Step 1 to `assets/verification/82/repro-cli.log` so the PR body can reference it.

Run from the worktree root:

```bash
mkdir -p assets/verification/82
{
  echo "## CLI smoke test (issue #82)"
  echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  cd "$(mktemp -d)" || exit 1
  cat > .agent-toolkit.yaml <<'YAML'
skills: []
agents: []
commands: []
hooks: []
plugins: []
mcps: []
pi_extensions: []
YAML
  uv run --project "$OLDPWD" agent-toolkit link project claude --dry-run
} > assets/verification/82/repro-cli.log 2>&1
echo "exit=$?"
```

Expected: a `repro-cli.log` showing "Nothing to change." and exit 0. The real behavioural assertion lives in the unit tests added in Task 1.

---

### Task 4: Audit other harness slots for the same `*.md`-discovery trap

**Files:**
- No code changes. This is a reading task that either confirms no further fix is needed or surfaces a follow-up issue.

- [ ] **Step 1: Re-read `_PROJECT_TARGETS` and `_USER_TARGETS` in `src/agent_toolkit_cli/_support.py`**

Cross-reference each `(harness, kind)` pair against its discovery rule:

| Pair | Discovery rule | After fix |
|---|---|---|
| `(claude, command)` | `*.md` | ✓ `.md` (this PR) |
| `(claude, agent)` | `*.md` | ✓ `.md` (this PR) |
| `(claude, skill)` | dir | ✓ bare slug, unchanged |
| `(claude, hook)` | settings.json (not a file slot) | unchanged |
| `(opencode, command|agent)` | `*.md` | ✓ already correct |
| `(opencode, skill)` | dir-with-file-symlink | unchanged |
| `(codex, skill)` | dir-symlink | unchanged |
| `(codex, hook)` | config_file+folder adapter | unchanged |
| `(pi, skill|agent)` | dir-symlink (no `*.md` glob) | unchanged |
| `(pi, pi-extension)` | dir | unchanged |

- [ ] **Step 2: Decide if a follow-up issue is needed**

If any pair surfaces a `*.md`-globbed slot still receiving a bare-slug symlink, file a separate issue and link from the PR body. Otherwise, note "no further harness fixes required" in the PR body's verification section.

- [ ] **Step 3: No commit** (audit-only task).

---

## Self-review

- **Spec coverage:** Tasks 1+2 implement the root-cause fix described in the spec. Task 3 reproduces the CLI scenario. Task 4 covers the "audit other harnesses" non-goal that was called out in the spec.
- **Placeholder scan:** No TBDs, no "add appropriate handling", every step shows code or an exact command.
- **Type consistency:** `_translated_slot_filename(slug, kind, harness)` signature unchanged. The single call site change (line 347) preserves the surrounding `slot_filename` variable name and downstream usage.

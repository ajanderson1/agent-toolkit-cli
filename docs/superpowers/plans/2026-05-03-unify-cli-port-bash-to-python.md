# Unify CLI — Port Bash Subcommands to Python — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four bash subcommands (`link`, `unlink`, `list`, `diff`) with Python Click commands wired into the existing `agent-toolkit` entry point, then delete the bash CLI, the bats suite, and the parity test in the same PR.

**Architecture:** New modules `src/agent_toolkit_cli/commands/{link,unlink,list,diff}.py` plus a shared helper module `commands/_link_lib.py` (pure logic — projection, action counters, summary strings, plan-mode parsing). All four commands reuse existing Python primitives: `walker.discover_assets`, `_allowlist.read_allowlist`, `_repo_resolution.resolve_toolkit_root`, `_yaml_edit._load/_dump/SECTIONS`, `commands/_list_json._USER_TARGETS/_PROJECT_TARGETS/_cell_status`. The TUI runner switches from "find `bin/agent-toolkit`" to `shutil.which("agent-toolkit")` with a worktree fallback. Bash, bats, and the cross-language parity test are deleted in the final commit.

**Tech Stack:** Python 3.12+, Click, hatchling, pytest, ruamel.yaml, uv

---

## Plan-level risks (read before starting any task)

1. **Output-string preservation contract.** The bats `assert_output --partial '…'` lines pin specific human-visible strings. The pytest replacements MUST assert on the same substrings. Where a substring change is unavoidable, justify it inline in the task and update both the docs and the assertion in the same commit.

2. **stderr/stdout split fidelity.** Bats tests verify that headers/summaries land on stderr while data lands on stdout. `click.testing.CliRunner` merges streams unless you pass `mix_stderr=False`. For tests that assert on the split, pass `mix_stderr=False` and read `result.stderr` separately, OR drive the installed entry point through `subprocess.run(..., capture_output=True, text=True)`. The plan calls out which tests need which approach per task.

3. **TTY detection in `--all` confirm-prompt.** Bash uses `[ -t 0 ] && [ -t 1 ]`. The Python equivalent is `sys.stdin.isatty() and sys.stdout.isatty()`. Tests cover the non-TTY-without-`-y` case (must error) and the empty-file case (must NOT prompt).

4. **Conventions subcommand routing (open question).** The bash dispatcher routes `link/unlink/list/diff user conventions` to `bin/lib/conventions.sh`. The design spec does NOT mention conventions. Task 0 documents the decision and Tasks 2, 3, 4 carry conventions handling forward only if Task 0 says yes. **Default decision (encoded below): port conventions in Task 5.5** — failing to port it would be a regression for `link user conventions` users, even though the spec was silent.

5. **Submodule paths and resolved-vs-unresolved targets.** `walker.discover_assets()` already skips submodule paths. `_list_json` already handles `/private/tmp` vs `/tmp` resolution on macOS. The new `link` projection logic must use the **unresolved** `asset.path.parent` for skill/mcp/plugin sources (matching what the bash version writes via `ln -s`) so existing symlinks stay byte-identical.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `src/agent_toolkit_cli/commands/_link_lib.py` | Create | Pure helpers: `LinkCounters` dataclass, projection algorithm, summary formatter, plan-mode line iterator. No Click. |
| `src/agent_toolkit_cli/commands/link.py` | Create | Click command for `link`. Wraps `_link_lib`. |
| `src/agent_toolkit_cli/commands/unlink.py` | Create | Click command for `unlink`. Reuses `_link_lib._link_project_from_file` for re-projection on per-asset. |
| `src/agent_toolkit_cli/commands/list.py` | Create | Click command for `list`. Text format inline; JSON delegates to existing `_list_json.list_json`. |
| `src/agent_toolkit_cli/commands/diff.py` | Create | Thin wrapper that calls `link` with `dry_run=True` and the `Previewing` header swap. |
| `src/agent_toolkit_cli/commands/_conventions.py` | Create | Pure helpers for the conventions Layer 2/3 projection (not a Click command — invoked from `link`/`unlink`/`list`/`diff` when third arg is `conventions`). |
| `src/agent_toolkit_cli/cli.py` | Modify | Register the four new commands. |
| `src/agent_toolkit_tui/runner.py` | Modify | `_locate_bash_cli` → `_locate_cli` using `shutil.which("agent-toolkit")` with a worktree-fallback for source checkouts. |
| `tests/test_link_lib.py` | Create | Unit tests for the pure helpers. |
| `tests/test_cli_link.py` | Create | Replaces `tests/bats/test_link.bats`, `test_link_per_asset.bats`, `test_link_all_prompt.bats`, `test_link_user_optin.bats`. |
| `tests/test_cli_unlink.py` | Create | Replaces `tests/bats/test_unlink.bats` and `test_unlink_grammar.bats`. |
| `tests/test_cli_list.py` | Create | Replaces `tests/bats/test_list.bats` and `test_list_new_grammar.bats`. |
| `tests/test_cli_diff.py` | Create | Replaces `tests/bats/test_diff.bats`. |
| `tests/test_cli_conventions.py` | Create | Replaces `tests/bats/test_conventions.bats`. |
| `tests/test_tui/test_runner.py` | Modify | Update `_locate_bash_cli` references to `_locate_cli`; add fallback-resolution test. |
| `bin/agent-toolkit`, `bin/lib/*.sh` | Delete | Final commit. |
| `tests/bats/` (entire dir) | Delete | Final commit. |
| `tests/test_target_dir_parity.py` | Delete | Final commit. |
| `lefthook.yml` | Modify | Drop the `bats:` command. |
| `.github/workflows/test.yml` | Modify | Drop the `bats:` job. |
| `AGENTS.md` | Modify | Strike "bash side / zero-dep" language. |
| `docs/agent-toolkit/cli.md` | Modify | Remove "Bash subcommands run with zero dependencies" wording; keep flag tables identical. |

---

## Task 0: Decide conventions scope

**Files:** none (decision-recording task).

- [ ] **Step 1: Read the conventions bats file**

Read `tests/bats/test_conventions.bats` (~230 lines, ~25 tests). Note that the bash dispatcher in `bin/agent-toolkit` lines 130–138 routes `link/unlink/list/diff user conventions` to `bin/lib/conventions.sh`'s `conventions_*_main` functions, bypassing the asset-projection path entirely.

- [ ] **Step 2: Record decision**

Decision (encoded in this plan): **port conventions** as Task 5.5 (after `diff`, before TUI rewire) so `agent-toolkit link user conventions` keeps working. The conventions logic is independent of asset allowlists and uses a simpler Layer 2 → Layer 3 symlink chain. If the user explicitly scopes conventions OUT, skip Task 5.5 and add a follow-up issue.

---

## Task 1: Scaffold `_link_lib.py` — pure helpers (no Click)

**Files:**
- Create: `src/agent_toolkit_cli/commands/_link_lib.py`
- Test: `tests/test_link_lib.py`

- [ ] **Step 1: Write the failing test for LinkCounters dataclass**

```python
# tests/test_link_lib.py
from agent_toolkit_cli.commands._link_lib import LinkCounters

def test_counters_default_zero():
    c = LinkCounters()
    assert c.created == 0
    assert c.updated == 0
    assert c.removed == 0
    assert c.unchanged == 0
    assert c.would_link == 0
    assert c.would_unlink == 0

def test_counters_summary_dry_run_no_changes():
    from agent_toolkit_cli.commands._link_lib import format_summary
    c = LinkCounters()
    assert format_summary(c, dry_run=True) == "Nothing to change."

def test_counters_summary_dry_run_with_changes():
    from agent_toolkit_cli.commands._link_lib import format_summary
    c = LinkCounters(would_link=2, would_unlink=1)
    assert format_summary(c, dry_run=True) == (
        "3 changes pending (2 to link, 1 to remove). Re-run without --dry-run to apply."
    )

def test_counters_summary_real_run_already_in_sync():
    from agent_toolkit_cli.commands._link_lib import format_summary
    c = LinkCounters(unchanged=5)
    assert format_summary(c, dry_run=False) == (
        "Already in sync — 5 assets linked, nothing to change."
    )

def test_counters_summary_real_run_with_changes():
    from agent_toolkit_cli.commands._link_lib import format_summary
    c = LinkCounters(created=3, updated=1, removed=2, unchanged=4)
    assert format_summary(c, dry_run=False) == (
        "Linked 3 new, updated 1, removed 2 stale (4 already in sync)."
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```
uv run pytest tests/test_link_lib.py -v
```
Expected: ImportError — module does not exist.

- [ ] **Step 3: Implement `_link_lib.py` skeleton**

```python
# src/agent_toolkit_cli/commands/_link_lib.py
"""Pure helpers for link/unlink/diff subcommands.

No Click, no I/O orchestration — just projection algorithm, action counting,
output-string formatters, and the plan-mode line iterator. Each function is
unit-tested in tests/test_link_lib.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class LinkCounters:
    created: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    would_link: int = 0
    would_unlink: int = 0


def format_summary(c: LinkCounters, dry_run: bool) -> str:
    if dry_run:
        total = c.would_link + c.would_unlink
        if total == 0:
            return "Nothing to change."
        return (
            f"{total} changes pending ({c.would_link} to link, "
            f"{c.would_unlink} to remove). Re-run without --dry-run to apply."
        )
    changed = c.created + c.updated + c.removed
    if changed == 0:
        return f"Already in sync — {c.unchanged} assets linked, nothing to change."
    return (
        f"Linked {c.created} new, updated {c.updated}, removed "
        f"{c.removed} stale ({c.unchanged} already in sync)."
    )
```

- [ ] **Step 4: Run the test, verify it passes**

```
uv run pytest tests/test_link_lib.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Add the projection helper test**

```python
# Append to tests/test_link_lib.py
def test_iter_plan_lines_skips_blanks_and_comments():
    from agent_toolkit_cli.commands._link_lib import iter_plan_lines
    text = "\n# leading comment\nskill:alpha\n\nskill:beta # trailing\n# tail\n"
    pairs = list(iter_plan_lines(text))
    # iter_plan_lines yields ("skill", "alpha"), ("skill", "beta") and never raises
    assert pairs == [("skill", "alpha"), ("skill", "beta")]

def test_iter_plan_lines_yields_malformed_marker_for_bad_line():
    from agent_toolkit_cli.commands._link_lib import iter_plan_lines, MALFORMED
    pairs = list(iter_plan_lines("garbage-no-colon\nskill:alpha\n"))
    assert pairs[0] == (MALFORMED, "garbage-no-colon")
    assert pairs[1] == ("skill", "alpha")
```

- [ ] **Step 6: Implement `iter_plan_lines` and `MALFORMED`**

Append to `_link_lib.py`:

```python
MALFORMED = "__malformed__"


def iter_plan_lines(text: str) -> Iterator[tuple[str, str]]:
    """Yield (kind, slug) pairs from --plan stdin text.

    - Strips `#`-comments (anything from `#` to end-of-line).
    - Skips blank-after-strip lines.
    - For lines without a colon, yields (MALFORMED, raw_line) so the caller
      can report and continue.
    """
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            yield (MALFORMED, raw)
            continue
        kind, _, slug = line.partition(":")
        yield (kind.strip(), slug.strip())
```

- [ ] **Step 7: Run tests, commit**

```
uv run pytest tests/test_link_lib.py -v
```
Expected: 7 passed.

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "feat(cli): add _link_lib pure helpers (counters, summary, plan parser)"
```

---

## Task 2: Port `link` subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/link.py`
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py` (add `project_from_file` and `maybe_link`)
- Modify: `src/agent_toolkit_cli/cli.py` (register the new command)
- Test: `tests/test_cli_link.py`

The pytest file MUST assert every behaviour the four bats files cover. Below, each step lists exactly which bats test (file:line) is replaced and the exact assertion to port.

### Bats coverage matrix for `link`

| Bats test | File | Bats line | pytest equivalent |
|---|---|---|---|
| creates per-entry symlink for claude-compatible skill | test_link.bats | 41–46 | test_link_user_claude_creates_symlink |
| is idempotent | test_link.bats | 48–53 | test_link_user_claude_idempotent |
| skips skill not tagged for codex | test_link.bats | 55–59 | test_link_user_codex_skips_incompatible |
| removes stale symlink when harnesses change | test_link.bats | 61–69 | test_link_removes_stale_when_harness_changes |
| --dry-run does not create symlink | test_link.bats | 71–76 | test_link_dry_run_no_symlink_emits_would_link |
| emits a header on stderr | test_link.bats | 78–82 | test_link_emits_linking_header_on_stderr |
| summary mentions 'Linked' on first run | test_link.bats | 84–88 | test_link_summary_says_linked_on_first_run |
| summary says 'Already in sync' on second run | test_link.bats | 90–95 | test_link_summary_already_in_sync_on_second_run |
| --dry-run summary mentions pending changes | test_link.bats | 97–101 | test_link_dry_run_summary_pending_or_nothing |
| AGENT_TOOLKIT_QUIET=1 only emits would-link on stdout | test_link.bats | 103–108 | test_link_quiet_env_suppresses_chrome |
| skill:alpha creates file and links it | test_link_per_asset.bats | 49–55 | test_link_per_asset_creates_yaml_and_symlink |
| skill:alpha then skill:beta keeps both | test_link_per_asset.bats | 57–65 | test_link_per_asset_keeps_both |
| skill:alpha is idempotent | test_link_per_asset.bats | 67–75 | test_link_per_asset_idempotent_no_dup |
| skill:nonexistent errors | test_link_per_asset.bats | 77–82 | test_link_per_asset_unknown_slug_errors |
| skill:codex-only errors with harness incompatibility | test_link_per_asset.bats | 84–90 | test_link_per_asset_harness_incompat_errors |
| mcp:foo errors clearly | test_link_per_asset.bats | 92–96 | test_link_per_asset_mcp_errors |
| project claude skill:alpha creates project file | test_link_per_asset.bats | 98–104 | test_link_project_per_asset |
| skill:alpha --all errors with mutual-exclusion | test_link_per_asset.bats | 106–110 | test_link_per_asset_plus_all_rc2 |
| skill:alpha --dry-run reports would-link without mutating YAML | test_link_per_asset.bats | 112–118 | test_link_per_asset_dry_run_no_yaml_write |
| --plan - applies multiple slugs from stdin | test_link_per_asset.bats | 120–125 | test_link_plan_multi_slugs |
| --plan - ignores comments and blank lines | test_link_per_asset.bats | 127–131 | test_link_plan_ignores_comments_and_blanks |
| --plan - reports per-entry failure but continues | test_link_per_asset.bats | 133–138 | test_link_plan_partial_failure_rc1 |
| --plan - rejects combination with --all | test_link_per_asset.bats | 140–143 | test_link_plan_with_all_rc2 |
| --plan - rejects combination with skill:slug | test_link_per_asset.bats | 145–148 | test_link_plan_with_per_asset_rc2 |
| --all rejects combination with --plan - | test_link_per_asset.bats | 150–153 | test_link_all_with_plan_rc2 |
| --plan with no following arg returns rc=2 | test_link_per_asset.bats | 155–159 | test_link_plan_no_arg_rc2 |
| --plan with non-dash arg returns rc=2 | test_link_per_asset.bats | 161–165 | test_link_plan_non_dash_rc2 |
| --all creates file with every compatible slug | test_link_all_prompt.bats | 33–41 | test_link_all_yes_creates_yaml_with_slugs |
| --all overwrites existing populated file with -y | test_link_all_prompt.bats | 43–56 | test_link_all_yes_overwrites |
| --all in non-TTY without -y refuses | test_link_all_prompt.bats | 58–71 | test_link_all_non_tty_no_yes_refuses |
| --all on empty existing file does not prompt | test_link_all_prompt.bats | 73–78 | test_link_all_empty_file_no_prompt |
| --all --dry-run reports would-be slugs (not old file) | test_link_all_prompt.bats | 80–96 | test_link_all_dry_run_no_write |
| no allowlist YAML errors with hint | test_link_user_optin.bats | 31–38 | test_link_bare_no_yaml_hints_with_all_and_kind_slug |
| empty allowlist succeeds and links nothing | test_link_user_optin.bats | 40–45 | test_link_bare_empty_yaml_links_nothing |
| allow-listed slug links it | test_link_user_optin.bats | 47–59 | test_link_bare_allowlisted_links |
| does NOT link slug missing from allow-list | test_link_user_optin.bats | 61–72 | test_link_bare_skips_unlisted |
| prunes symlink when slug removed from allow-list | test_link_user_optin.bats | 74–95 | test_link_bare_prunes_when_removed |
| prunes orphan symlink for asset removed from repo | test_link_user_optin.bats | 97–131 | test_link_bare_prunes_orphan |

### Implementation

- [ ] **Step 1: Add the projection-and-maybe-link primitives to `_link_lib`**

Append to `src/agent_toolkit_cli/commands/_link_lib.py`:

```python
import os
from pathlib import Path
from typing import Iterable

from agent_toolkit_cli._allowlist import SECTIONS, kind_to_section, read_allowlist
from agent_toolkit_cli.commands._list_json import _USER_TARGETS, _PROJECT_TARGETS
from agent_toolkit_cli.walker import discover_assets, extract_frontmatter, Asset

KINDS_FOR_PROJECTION: tuple[str, ...] = ("skill", "agent", "command", "hook", "plugin")


def harness_target_dir(harness: str, kind: str, scope: str, project_root: Path) -> Path | None:
    """Mirror of bash harness_target_dir / project_target_dir."""
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        if not tmpl:
            return None
        home = os.environ.get("HOME", "")
        return Path(tmpl.format(home=home))
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None


def _expected_source(asset_path: Path, kind: str) -> Path:
    if kind in {"skill", "mcp", "plugin"}:
        return asset_path.parent
    return asset_path


def _asset_harnesses(asset_path: Path) -> list[str]:
    fm = extract_frontmatter(asset_path) or {}
    spec = fm.get("spec") or {}
    return list(spec.get("harnesses") or [])


def maybe_link(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    target_dir: Path,
    toolkit_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout,  # file-like
) -> None:
    """Create/replace/skip a symlink for one asset; update counters.

    Direct port of bash _maybe_link in bin/lib/link.sh:430.
    """
    source_path = _expected_source(asset_path, kind)
    link_path = target_dir / slug
    declared = _asset_harnesses(asset_path)
    if harness not in declared:
        if link_path.is_symlink():
            if dry_run:
                print(f"would-unlink: {link_path}", file=stdout)
                counters.would_unlink += 1
            else:
                link_path.unlink()
                counters.removed += 1
        return

    if link_path.is_symlink() and Path(os.readlink(str(link_path))) == source_path:
        counters.unchanged += 1
        return

    if dry_run:
        print(f"would-link: {link_path} -> {source_path}", file=stdout)
        counters.would_link += 1
        return

    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
        counters.updated += 1
    else:
        counters.created += 1
    link_path.symlink_to(source_path)


def project_from_file(
    *,
    scope: str,
    harness: str,
    toolkit_root: Path,
    project_root: Path,
    allowlist_path: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout,
) -> None:
    """Walk every asset kind. Project allow-listed slugs, prune the rest."""
    allowed = read_allowlist(allowlist_path)
    by_kind: dict[str, list[Asset]] = {k: [] for k in KINDS_FOR_PROJECTION}
    for asset in discover_assets(toolkit_root):
        if asset.kind in by_kind:
            by_kind[asset.kind].append(asset)

    for kind in KINDS_FOR_PROJECTION:
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            continue
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        section = kind_to_section(kind)
        allowed_slugs = set(allowed.get(section, []))
        discovered_slugs: set[str] = set()
        for asset in by_kind[kind]:
            discovered_slugs.add(asset.slug)
            if asset.slug in allowed_slugs:
                maybe_link(
                    harness=harness, kind=kind, slug=asset.slug,
                    asset_path=asset.path, target_dir=target_dir,
                    toolkit_root=toolkit_root, dry_run=dry_run,
                    counters=counters, stdout=stdout,
                )
            else:
                _prune_if_into_repo(
                    target_dir / asset.slug, toolkit_root, dry_run, counters, stdout,
                )
        # Sweep orphan symlinks (slug in target dir but no asset in repo)
        if target_dir.is_dir():
            for entry in target_dir.iterdir():
                if not entry.is_symlink():
                    continue
                if entry.name in discovered_slugs:
                    continue
                _prune_if_into_repo(entry, toolkit_root, dry_run, counters, stdout)


def _prune_if_into_repo(
    link_path: Path, toolkit_root: Path, dry_run: bool,
    counters: LinkCounters, stdout,
) -> None:
    if not link_path.is_symlink():
        return
    target = os.readlink(str(link_path))
    try:
        Path(target).resolve().relative_to(toolkit_root.resolve())
    except (ValueError, FileNotFoundError, OSError):
        return
    if dry_run:
        print(f"would-unlink: {link_path}", file=stdout)
        counters.would_unlink += 1
    else:
        link_path.unlink()
        counters.removed += 1
```

- [ ] **Step 2: Write the failing test for the simplest bare-form case**

```python
# tests/test_cli_link.py
"""Pytest port of tests/bats/test_link*.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations
import os
from pathlib import Path
from click.testing import CliRunner
import pytest

from agent_toolkit_cli.cli import main


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit(tmp: Path) -> Path:
    """Create a minimal valid toolkit repo at `tmp/toolkit`."""
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    return root


def _seed_skill(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}


def test_link_user_claude_creates_symlink(env):
    """Replaces tests/bats/test_link.bats:41-46."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    link = home / ".claude" / "skills" / "alpha"
    assert link.is_symlink()
    assert os.readlink(str(link)) == str(toolkit / "skills" / "alpha")
```

- [ ] **Step 3: Run test, verify it fails**

```
uv run pytest tests/test_cli_link.py::test_link_user_claude_creates_symlink -v
```
Expected: FAIL — `link` is not a registered subcommand.

- [ ] **Step 4: Implement `commands/link.py`**

```python
# src/agent_toolkit_cli/commands/link.py
"""link — project allow-listed assets as symlinks per (scope, harness)."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import click

from agent_toolkit_cli import _ui
from agent_toolkit_cli._allowlist import SECTIONS, kind_to_section, read_allowlist
from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli.commands._link_lib import (
    KINDS_FOR_PROJECTION,
    LinkCounters,
    MALFORMED,
    _asset_harnesses,
    format_summary,
    iter_plan_lines,
    project_from_file,
)
from agent_toolkit_cli.walker import discover_assets


@click.command("link")
@click.argument("scope", type=click.Choice(["user", "project"]))
@click.argument("harness")  # accept any string; conventions/etc dispatched by sibling cmd
@click.argument("target", required=False, default=None)
@click.option("--all", "all_flag", is_flag=True, default=False)
@click.option("--plan", "plan_flag", default=None,
              help="Read kind:slug entries from FILE (only '-' for stdin is supported).")
@click.option("-y", "--yes", "assume_yes", is_flag=True, default=False)
@click.option("--dry-run", "dry_run", is_flag=True, default=False)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.option("--toolkit-repo", "toolkit_repo",
              type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--project", "project_flag",
              type=click.Path(file_okay=False, path_type=Path), default=None)
@click.pass_context
def link(ctx, scope, harness, target, all_flag, plan_flag, assume_yes,
         dry_run, quiet, toolkit_repo, project_flag) -> None:
    """Project assets per the allow-list. Bare form reads the file."""
    if quiet:
        os.environ["AGENT_TOOLKIT_QUIET"] = "1"

    # Mode resolution + mutex checks
    if plan_flag is not None and plan_flag != "-":
        click.echo("--plan currently supports only '-' (stdin)", err=True)
        ctx.exit(2)
    modes_set = sum(bool(x) for x in (all_flag, plan_flag is not None, target is not None))
    if modes_set > 1:
        # Build the same error wording bash uses
        if plan_flag is not None and all_flag:
            click.echo("cannot combine --all with plan mode", err=True)
        elif plan_flag is not None and target is not None:
            click.echo("cannot combine plan with per-asset mode", err=True)
        elif all_flag and target is not None:
            click.echo(f"cannot combine --all with per-asset mode", err=True)
        ctx.exit(2)

    # Resolve toolkit_root via group context, flag, or four-step
    toolkit_root = (ctx.obj or {}).get("toolkit_root") if ctx.obj else None
    if toolkit_repo is not None:
        try:
            toolkit_root = resolve_toolkit_root(toolkit_repo)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True); ctx.exit(2)
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(None)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True); ctx.exit(2)

    project_root = Path(project_flag).resolve() if project_flag else Path.cwd()
    allowlist_path = (
        Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
        if scope == "user"
        else project_root / ".agent-toolkit.yaml"
    )

    counters = LinkCounters()

    if all_flag:
        _do_all(scope, harness, toolkit_root, project_root,
                allowlist_path, assume_yes, dry_run, counters, ctx)
        return
    if plan_flag is not None:
        _do_plan(scope, harness, toolkit_root, project_root,
                 allowlist_path, dry_run, counters, ctx)
        return
    if target is not None:
        _do_per_asset(scope, harness, target, toolkit_root, project_root,
                      allowlist_path, dry_run, counters, ctx)
        return
    _do_bare(scope, harness, toolkit_root, project_root,
             allowlist_path, dry_run, counters, ctx)
```

Continue with `_do_bare`, `_do_per_asset`, `_do_all`, `_do_plan` — each follows the bash semantics in `bin/lib/link.sh:103–303`. Excerpt for `_do_bare`:

```python
def _do_bare(scope, harness, toolkit_root, project_root,
             allowlist_path, dry_run, counters, ctx):
    if not allowlist_path.is_file():
        msg = (
            f"no {allowlist_path} found.\n"
            f"  agent-toolkit link {scope} {harness} --all                  → snapshot every compatible asset, then project\n"
            f"  agent-toolkit link {scope} {harness} <kind>:<slug>          → add one asset, then project\n"
            f"  $EDITOR {allowlist_path}                                  → author by hand, then re-run\n"
        )
        click.echo(msg, err=True)
        ctx.exit(2)
    if dry_run:
        _ui.header(f"Previewing {scope}-scope changes for {harness} (no files will be modified)...")
    else:
        _ui.header(f"Linking {scope}-scope assets for {harness} from {allowlist_path}...")
    project_from_file(
        scope=scope, harness=harness, toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist_path,
        dry_run=dry_run, counters=counters, stdout=sys.stdout,
    )
    _ui.summary(format_summary(counters, dry_run))
```

`_do_per_asset` mirrors `bin/lib/link.sh:124–183`. It must:
1. Reject `kind == "mcp"` with stderr `"mcps are not yet scope-routed — edit the harness's mcp.json directly"` and exit 2.
2. Find the asset; on miss emit `"no {kind} named '{slug}' found. Run 'agent-toolkit list {kind}' to see what's available."` and exit 1.
3. Read `_asset_harnesses`; if `harness` not in declared, emit `"{kind}:{slug} doesn't support harness '{harness}' (declares: {csv}). Use a different harness or pick another asset."` and exit 1.
4. Mutate the YAML (idempotent add); on dry-run write to a tempfile copy of the existing allowlist (or new empty one) and project from that tempfile.
5. Project from the (real or temp) allowlist; emit summary.

`_do_all` mirrors `bin/lib/link.sh:186–247`:
1. If allowlist exists and has any slug: bail unless `assume_yes` or stdin+stdout are TTYs and the user types `y`/`Y`/`yes`.
2. On non-TTY without `-y`: emit `"no TTY available — pass --yes/-y to confirm overwrite of existing {allowlist_path}."` and exit 2.
3. On TTY: emit `"{path} already has {N skills, M agents, ...}.\n--all will replace this with every compatible asset for {harness}.\nContinue? [y/N] "` and read; reject anything except y/Y/yes/YES.
4. Build the snapshot: walk every kind, write `<section> <slug>` to a tempfile, call the snapshot logic from `_yaml_edit` (move it to a callable function — see Step 5).
5. Project from the snapshot file (real or tmp under dry-run). Emit summary.

`_do_plan` mirrors `bin/lib/link.sh:254–303`:
1. Read all of stdin.
2. For each `(kind, slug)` from `iter_plan_lines`: if marker is `MALFORMED`, increment failed; else invoke `_do_per_asset`-equivalent code path inline (with `AGENT_TOOLKIT_QUIET=1` for chrome suppression, and stderr captured per-line).
3. Always emit `_ui.summary(f"Plan applied: {ok} ok, {failed} failed (of {total} entries).")` to stderr.
4. Exit 1 if any failed, else 0. Grammar errors (combined with `--all`/`<kind>:<slug>`/missing `-`) are exit 2 (already enforced above).

- [ ] **Step 5: Refactor `_yaml_edit.snapshot_cmd` to expose a Python-callable helper**

In `commands/_yaml_edit.py`, add a public function the new `link.py` imports rather than spawning a subprocess:

```python
def write_snapshot(path: Path, entries: list[tuple[str, str]]) -> None:
    """Replace `path` with sections built from (section, slug) entries.

    Same logic as the `snapshot` Click subcommand but callable in-process.
    """
    doc = _empty_doc()
    for section, slug in entries:
        if section not in SECTIONS:
            raise ValueError(f"unknown section in snapshot: {section!r}")
        if slug not in list(doc[section]):
            doc[section].append(slug)
    _dump(doc, path)
```

Then have `snapshot_cmd` call `write_snapshot`. Hidden Click command stays for back-compat (one bats test exercises it indirectly; that test is going away).

Similarly add `add_slug(path, section, slug)` and `remove_slug(path, section, slug)` as in-process callables for `_do_per_asset` / unlink to use.

- [ ] **Step 6: Register `link` in `cli.py`**

In `src/agent_toolkit_cli/cli.py` add:

```python
from agent_toolkit_cli.commands.link import link
...
main.add_command(link)
```

- [ ] **Step 7: Run the test, fix until it passes**

```
uv run pytest tests/test_cli_link.py::test_link_user_claude_creates_symlink -v
```
Expected: PASS. Iterate on the implementation until green.

- [ ] **Step 8: Add the remaining bare-form tests**

For each row of the bats coverage matrix above (37 tests for `link`), add a test in `tests/test_cli_link.py`. Each test:
- Has a docstring of the form `"""Replaces tests/bats/<file>.bats:<lines>."""`.
- Asserts on the same substrings the bats test asserts on (e.g. for line 80 of test_link_per_asset.bats, assert `"no skill named 'nonexistent'"` appears in stderr).
- Uses `CliRunner(mix_stderr=False)` and reads `result.stderr` for header/summary assertions; `result.output` for stdout-only data.

Example for the harness-incompatibility case:

```python
def test_link_per_asset_harness_incompat_errors(env):
    """Replaces tests/bats/test_link_per_asset.bats:84-90."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "codex-only", ["codex"])
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:codex-only"],
    )
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "doesn't support harness 'claude'" in combined
    assert "codex" in combined
    assert not (home / ".agent-toolkit.yaml").exists()
```

Critical preservation strings to assert (from the bats files — DO NOT change):
- `"would-link"` (test_link.bats:75, test_link_per_asset.bats:115, test_diff.bats:43)
- `"Linking"` (test_link.bats:81)
- `"Linked"` in summary (test_link.bats:87)
- `"Already in sync"` (test_link.bats:94)
- `"pending"` OR `"Nothing to change"` (test_link.bats:100)
- `f"no {HOME}/.agent-toolkit.yaml"` (test_link_user_optin.bats:34)
- `"--all"` and `"<kind>:<slug>"` in the bare-no-yaml hint (test_link_user_optin.bats:35-36)
- `"no skill named 'nonexistent'"` (test_link_per_asset.bats:80)
- `"doesn't support harness 'claude'"` (test_link_per_asset.bats:87)
- `"mcps are not yet scope-routed"` (test_link_per_asset.bats:95)
- `"cannot combine --all with"` (test_link_per_asset.bats:109)
- `"no TTY"` (test_link_all_prompt.bats:69)

For the non-TTY test, the bats test pipes `</dev/null` to the CLI. With `CliRunner` we can pass `input=""` and additionally monkeypatch `sys.stdin.isatty` and `sys.stdout.isatty` to return False. Document this in the test's docstring.

For the TTY-prompt confirmation test, monkeypatch `isatty` to return True and pass `input="y\n"`.

- [ ] **Step 9: Run all link tests, verify all pass**

```
uv run pytest tests/test_cli_link.py -v
```
Expected: 37 passed.

- [ ] **Step 10: Commit**

```bash
git add src/agent_toolkit_cli/commands/link.py src/agent_toolkit_cli/commands/_link_lib.py \
        src/agent_toolkit_cli/commands/_yaml_edit.py src/agent_toolkit_cli/cli.py \
        tests/test_cli_link.py
git commit -m "feat(cli): port link subcommand to Python (Click)"
```

---

## Task 3: Port `unlink` subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/unlink.py`
- Modify: `src/agent_toolkit_cli/cli.py`
- Test: `tests/test_cli_unlink.py`

### Bats coverage matrix for `unlink`

| Bats test | File | Bats line | pytest equivalent |
|---|---|---|---|
| --all removes symlinks pointing into the repo | test_unlink.bats | 33–37 | test_unlink_all_removes_into_repo |
| --all leaves unrelated symlinks untouched | test_unlink.bats | 39–44 | test_unlink_all_leaves_unrelated |
| --all emits header and summary on stderr | test_unlink.bats | 46–51 | test_unlink_all_header_and_summary |
| (bare) errors with hint | test_unlink_grammar.bats | 41–48 | test_unlink_bare_errors_with_hint |
| --all clears symlinks but preserves YAML | test_unlink_grammar.bats | 50–56 | test_unlink_all_preserves_yaml |
| skill:alpha removes from file and prunes symlink | test_unlink_grammar.bats | 58–63 | test_unlink_per_asset_removes_yaml_and_symlink |
| skill:alpha is idempotent on second run with diagnostic | test_unlink_grammar.bats | 65–70 | test_unlink_per_asset_idempotent_diag |
| skill:alpha when YAML missing errors | test_unlink_grammar.bats | 72–77 | test_unlink_per_asset_no_yaml_errors |
| --all leaves unrelated symlinks alone | test_unlink_grammar.bats | 79–83 | test_unlink_all_unrelated_alone |
| --plan - removes multiple slugs | test_unlink_grammar.bats | 85–120 | test_unlink_plan_multi |
| --plan - rejects combination with --all | test_unlink_grammar.bats | 122–125 | test_unlink_plan_with_all_rc2 |
| --plan with no following arg returns rc=2 | test_unlink_grammar.bats | 127–131 | test_unlink_plan_no_arg_rc2 |
| --plan with non-dash arg returns rc=2 | test_unlink_grammar.bats | 133–137 | test_unlink_plan_non_dash_rc2 |

### Implementation

- [ ] **Step 1: Write the failing test for the bare-error-hint case**

```python
# tests/test_cli_unlink.py
def test_unlink_bare_errors_with_hint(env):
    """Replaces tests/bats/test_unlink_grammar.bats:41-48."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude"],
    )
    assert result.exit_code == 2
    assert "unlink requires a target" in result.stderr
    assert "--all" in result.stderr
    assert "<kind>:<slug>" in result.stderr
    assert link_path.is_symlink()  # untouched
```

- [ ] **Step 2: Run, verify FAIL**

```
uv run pytest tests/test_cli_unlink.py::test_unlink_bare_errors_with_hint -v
```
Expected: FAIL — `unlink` not registered.

- [ ] **Step 3: Implement `commands/unlink.py`**

Same shape as `link.py`. Modes: `bare` (error hint, rc=2), `--all` (remove every symlink in `(scope, harness, kind)` target dirs whose `os.readlink` resolves into `toolkit_root`), `<kind>:<slug>` (remove from YAML, then re-project — reuses `project_from_file` from `_link_lib`), `--plan -` (loop with quieting).

Key strings to preserve:
- bare error: `"unlink requires a target. Did you mean:\n  agent-toolkit unlink {scope} {harness} --all                  → remove all symlinks for {harness} (preserves {allowlist_path})\n  agent-toolkit unlink {scope} {harness} <kind>:<slug>          → remove one asset (also removes from {allowlist_path})\nRun 'agent-toolkit list {harness}' to see what's currently linked."`
- per-asset YAML missing: `f"no {allowlist_path} — nothing to unlink."` (rc=1)
- per-asset slug not in YAML: `f"{kind}:{slug} not in {allowlist_path} — nothing to remove."` (rc=0, idempotent diagnostic)
- `--all` headers: `f"Removing {scope}-scope {harness} symlinks pointing into {toolkit_root}..."` (real run) / `f"Previewing removal of {scope}-scope {harness} symlinks pointing into {toolkit_root}..."` (dry-run)
- `--all` summary: `f"Removed {N} symlinks."` / `f"{N} symlinks would be removed."`
- per-asset header: `f"Unlinking {scope}-scope {kind}:{slug} for {harness}..."`

- [ ] **Step 4: Register in `cli.py`, run all 13 tests**

```
uv run pytest tests/test_cli_unlink.py -v
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/unlink.py src/agent_toolkit_cli/cli.py tests/test_cli_unlink.py
git commit -m "feat(cli): port unlink subcommand to Python (Click)"
```

---

## Task 4: Port `list` subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/list.py`
- Modify: `src/agent_toolkit_cli/cli.py`
- Test: `tests/test_cli_list.py`

Click already has a `list_json` hidden command. The new `list` is a top-level command that, when `--format=json`, calls `list_json` (refactored to be callable via `ctx.invoke` rather than a subprocess).

### Bats coverage matrix for `list`

| Bats test | File | Bats line | pytest equivalent |
|---|---|---|---|
| shows alpha as user:✓ | test_list.bats | 33–46 | test_list_shows_user_check |
| emits header and summary on stderr | test_list.bats | 48–53 | test_list_header_and_summary_on_stderr |
| quiet env suppresses output | test_list.bats | 55–59 | test_list_quiet_env_silent |
| --format=json valid JSON | test_list.bats | 61–73 | test_list_json_valid |
| --format=json marks unsupported cells | test_list.bats | 75–79 | test_list_json_unsupported_cells |
| no args shows every asset with cols | test_list_new_grammar.bats | 50–62 | test_list_no_args_all_with_cols |
| `list skill` filters | test_list_new_grammar.bats | 64–71 | test_list_kind_filter |
| `list claude` filters | test_list_new_grammar.bats | 73–80 | test_list_harness_filter |
| `list skill claude` combines | test_list_new_grammar.bats | 82–89 | test_list_kind_and_harness |
| outside a project — project:— | test_list_new_grammar.bats | 91–96 | test_list_outside_project |
| rejects unknown positional | test_list_new_grammar.bats | 98–103 | test_list_rejects_unknown_positional |
| project YAML present — project:✓ | test_list_new_grammar.bats | 105–120 | test_list_project_check |
| `list mcp` emits note | test_list_new_grammar.bats | 122–131 | test_list_mcp_note |

### Implementation

- [ ] **Step 1: Write the failing test for the simplest case**

```python
def test_list_shows_user_check(env):
    """Replaces tests/bats/test_list.bats:33-46."""
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "user:✓" in result.output
```

- [ ] **Step 2: Run — expect FAIL**

```
uv run pytest tests/test_cli_list.py::test_list_shows_user_check -v
```

- [ ] **Step 3: Implement `commands/list.py`**

Two positionals (free-form, disambiguated by membership): `kind_or_harness_1`, `kind_or_harness_2`. `--format` choice `text|json` (default text). `--quiet`/`-q`. Pass-through `--toolkit-repo`/`--project`.

Logic (mirroring `bin/lib/list.sh`):
- Disambiguate positionals against `_KNOWN_KINDS = {skill, agent, command, hook, plugin, mcp}` and `_KNOWN_HARNESSES = {claude, codex, opencode, pi}`.
- On unknown positional: stderr `f"unknown filter '{arg}' — expected one of: skill agent command hook plugin mcp or claude codex opencode pi"`; exit 2.
- On `--format=json`: invoke `list_json` via `ctx.invoke(list_json, toolkit_root=toolkit_root, project_root=project_root, kind=kind_filter, harness=harness_filter)`.
- On `kind_filter == "mcp"`: emit `_ui.header("Asset inventory (filter: kind=mcp):")` then `_ui.summary("MCPs are configured via the harness's mcp.json, not symlinks — not shown here.")`; exit 0.
- Otherwise: emit `_ui.header(f"Asset inventory (filter: kind={kind_filter or 'any'}, harness={harness_filter or 'any'}):")`. For each kind in projection order, build rows by calling `discover_assets` + `read_allowlist` + symlink existence at `harness_target_dir(harness, kind, scope, project_root) / slug`. Print section header `f"{KIND_TITLE} ({count})"` (uppercase: `SKILLS`, `AGENTS`, etc.), then rows formatted as `f"  {slug:<20} {harness_brackets:<30} user:{state} project:{state}"` where state is `✓` if YAML lists slug AND symlink exists, else `—`. Conclude with `_ui.summary("Done.")`.

- [ ] **Step 4: Register, iterate until tests pass (13 tests)**

```
uv run pytest tests/test_cli_list.py -v
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/list.py src/agent_toolkit_cli/cli.py tests/test_cli_list.py
git commit -m "feat(cli): port list subcommand to Python (Click)"
```

---

## Task 5: Port `diff` subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/diff.py`
- Modify: `src/agent_toolkit_cli/cli.py`
- Test: `tests/test_cli_diff.py`

### Bats coverage matrix for `diff`

| Bats test | File | Bats line | pytest equivalent |
|---|---|---|---|
| shows what link would create | test_diff.bats | 40–44 | test_diff_shows_would_link |
| emits 'Previewing' header on stderr | test_diff.bats | 46–50 | test_diff_previewing_header |

### Implementation

- [ ] **Step 1: Write tests**

```python
def test_diff_shows_would_link(env):
    """Replaces tests/bats/test_diff.bats:40-44."""
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "would-link" in result.output


def test_diff_previewing_header(env):
    """Replaces tests/bats/test_diff.bats:46-50."""
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0
    assert "Previewing" in result.stderr
```

- [ ] **Step 2: Implement `commands/diff.py` as a thin alias**

```python
# src/agent_toolkit_cli/commands/diff.py
"""diff — preview what `link` would change. Alias for `link --dry-run`."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.commands.link import link


@click.command("diff")
@click.argument("scope", type=click.Choice(["user", "project"]))
@click.argument("harness")
@click.option("--toolkit-repo", "toolkit_repo",
              type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--project", "project_flag",
              type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.pass_context
def diff(ctx, scope, harness, toolkit_repo, project_flag, quiet) -> None:
    """Preview what `link` would change (alias for `link --dry-run`)."""
    args = [scope, harness, "--dry-run"]
    if toolkit_repo:
        args += ["--toolkit-repo", str(toolkit_repo)]
    if project_flag:
        args += ["--project", str(project_flag)]
    if quiet:
        args.append("--quiet")
    ctx.invoke(link, scope=scope, harness=harness,
               target=None, all_flag=False, plan_flag=None, assume_yes=False,
               dry_run=True, quiet=quiet,
               toolkit_repo=toolkit_repo, project_flag=project_flag)
```

The "Previewing" header is already emitted by `link`'s bare-form code path under `dry_run=True`. The bats coverage of "Previewing" is satisfied because `_do_bare` emits exactly that wording.

- [ ] **Step 3: Run tests, register, commit**

```
uv run pytest tests/test_cli_diff.py -v
```
Expected: 2 passed.

```bash
git add src/agent_toolkit_cli/commands/diff.py src/agent_toolkit_cli/cli.py tests/test_cli_diff.py
git commit -m "feat(cli): port diff subcommand to Python (Click)"
```

---

## Task 5.5: Port `conventions` projection (link/unlink/list/diff user conventions)

**Files:**
- Create: `src/agent_toolkit_cli/commands/_conventions.py`
- Modify: `src/agent_toolkit_cli/commands/{link,unlink,list,diff}.py` (route on `harness == "conventions"`)
- Test: `tests/test_cli_conventions.py`

### Bats coverage matrix for `conventions`

Every test in `tests/bats/test_conventions.bats` (~25 tests) maps 1:1. Each pytest test has docstring `"""Replaces tests/bats/test_conventions.bats:<line>."""`. Highlights:

- `link user conventions exits 0` (line 24)
- creates Layer 2 symlinks (line 29)
- Layer 2 idempotent (line 38)
- refuses to clobber a real file at `~/.conventions/CONVENTIONS.md` — exact error: `"refuses to overwrite"` (line 53)
- refuses if `~/.conventions` exists as a file — `"refuses to proceed"` (line 60)
- creates Claude Layer 3 when `~/.claude` exists (line 64)
- creates Codex Layer 3 (line 74) — slot is `~/.codex/AGENTS.md` → `~/.conventions/CONVENTIONS.md`
- creates OpenCode Layer 3 (line 82)
- creates Pi Layer 3 (line 90)
- skips harnesses whose dir does not exist (line 98)
- Layer 3 idempotent (line 107)
- creates all Layer 3 slots when every harness dir exists (line 118)
- `unlink user conventions` removes Layer 3 only (line 133)
- `list user conventions` shows Layer 3 → Layer 2 → Layer 1 chain (line 150)
- `list user conventions` handles missing slots gracefully (line 162)
- `unlink user conventions` does NOT touch unrelated symlinks at slot paths (line 169)
- `diff user conventions` reports would-link without creating (line 190)
- `link user conventions` replaces stale Layer 2 symlink pointing elsewhere (line 199)
- `link user conventions` replaces stale Layer 3 symlink pointing at old Layer 1 (line 208)
- `unlink user conventions --dry-run` prints would-unlink (line 220)

### Implementation

- [ ] **Step 1: Write 4 representative failing tests, then implement**

`_conventions.py` has 4 entry points (`do_link`, `do_unlink`, `do_list`, `do_diff`) that mirror the four bash functions. Use the same Layer 2 + Layer 3 symlink table:

```python
# src/agent_toolkit_cli/commands/_conventions.py
def layer3_slots(home: Path) -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    if (home / ".claude").is_dir():
        out.append((home / ".claude" / "CONVENTIONS.md", home / ".conventions" / "CONVENTIONS.md"))
        out.append((home / ".claude" / "conventions", home / ".conventions" / "conventions"))
    if (home / ".codex").is_dir():
        out.append((home / ".codex" / "AGENTS.md", home / ".conventions" / "CONVENTIONS.md"))
    if (home / ".config" / "opencode").is_dir():
        out.append((home / ".config" / "opencode" / "AGENTS.md", home / ".conventions" / "CONVENTIONS.md"))
    if (home / ".pi" / "agent").is_dir():
        out.append((home / ".pi" / "agent" / "AGENTS.md", home / ".conventions" / "CONVENTIONS.md"))
    return out
```

- [ ] **Step 2: Route from each command**

In `link.py`'s `link()`, before mode dispatch:

```python
if harness == "conventions":
    from agent_toolkit_cli.commands._conventions import do_link
    do_link(scope=scope, toolkit_root=toolkit_root, dry_run=dry_run, ctx=ctx)
    return
```

Same pattern in `unlink`, `list`, `diff`.

- [ ] **Step 3: Run all conventions tests**

```
uv run pytest tests/test_cli_conventions.py -v
```
Expected: ~22 passed.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/commands/_conventions.py \
        src/agent_toolkit_cli/commands/{link,unlink,list,diff}.py \
        tests/test_cli_conventions.py
git commit -m "feat(cli): port conventions projection to Python"
```

---

## Task 6: Rewire TUI runner

**Files:**
- Modify: `src/agent_toolkit_tui/runner.py`
- Modify: `tests/test_tui/test_runner.py`

- [ ] **Step 1: Write the failing test for the new resolver behaviour**

Add to `tests/test_tui/test_runner.py`:

```python
def test_locate_cli_uses_shutil_which(monkeypatch, tmp_path):
    """After the unification, runner.py must find the installed `agent-toolkit`
    via PATH, not by walking up to bin/agent-toolkit."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cli = fake_bin / "agent-toolkit"
    fake_cli.write_text("#!/bin/sh\n")
    fake_cli.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.delenv("AGENT_TOOLKIT_BASH_CLI", raising=False)
    from agent_toolkit_tui.runner import _locate_cli
    assert _locate_cli() == fake_cli


def test_locate_cli_falls_back_to_worktree(monkeypatch, tmp_path):
    """When `agent-toolkit` is not on PATH, fall back to walking up for
    pyproject.toml (development from a source checkout)."""
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("AGENT_TOOLKIT_BASH_CLI", raising=False)
    # Should still resolve because we're being run from inside the source tree
    from agent_toolkit_tui.runner import _locate_cli
    p = _locate_cli()
    assert p.name == "agent-toolkit" or p.name.startswith("agent-toolkit")
```

Delete the obsolete tests `test_locate_bash_cli_walks_up_to_source_tree` and `test_runner_default_cli_path_does_not_use_toolkit_root` and `test_locate_bash_cli_honours_env_override` and `test_locate_bash_cli_rejects_invalid_override` (they test the deleted `_locate_bash_cli`). Replace with the two above.

- [ ] **Step 2: Run, FAIL**

```
uv run pytest tests/test_tui/test_runner.py -v
```

- [ ] **Step 3: Update `runner.py`**

Replace `_locate_bash_cli` with `_locate_cli`:

```python
import shutil
from pathlib import Path


def _locate_cli() -> Path:
    """Find the `agent-toolkit` CLI to shell out to.

    Resolution order:
      1. $AGENT_TOOLKIT_BASH_CLI override (kept for back-compat with old test fixtures).
      2. shutil.which("agent-toolkit") — what `uv tool install` puts on PATH.
      3. Walk up from this module to find a sibling pyproject.toml; if found,
         expect `uv run agent-toolkit` to be runnable from there. Return that
         resolved-via-uv path.
      4. Raise FileNotFoundError.
    """
    import os
    override = os.environ.get("AGENT_TOOLKIT_BASH_CLI")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise FileNotFoundError(f"$AGENT_TOOLKIT_BASH_CLI={override} is not a file")

    found = shutil.which("agent-toolkit")
    if found:
        return Path(found)

    # Fallback: development from source checkout — walk up to find pyproject.toml
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            # Look for an installed entrypoint inside .venv
            venv_bin = parent / ".venv" / "bin" / "agent-toolkit"
            if venv_bin.is_file():
                return venv_bin
    raise FileNotFoundError(
        "Cannot locate `agent-toolkit` — install with `uv tool install agent-toolkit`, "
        "or set $AGENT_TOOLKIT_BASH_CLI to override."
    )
```

Update `CLIRunner.__init__` to call `_locate_cli` instead of `_locate_bash_cli`. Update the docstring on `CLIRunner` to drop "bash" wording.

- [ ] **Step 4: Run all TUI runner tests, verify pass**

```
uv run pytest tests/test_tui/test_runner.py -v
```
Expected: 6 passed (4 unchanged + 2 new + replacements).

- [ ] **Step 5: Smoke-test the TUI test suite**

```
uv run pytest tests/test_tui -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/runner.py tests/test_tui/test_runner.py
git commit -m "refactor(tui): resolve CLI via PATH after Python-only unification"
```

---

## Task 7: Wire-through smoke test (subprocess against real entry point)

**Files:**
- Modify: `tests/test_cli_link.py` (add one subprocess-driven test)
- Modify: `tests/test_cli_list.py` (same)

The bats tests run the CLI as a subprocess, which captures real stderr/stdout split fidelity. `CliRunner` mostly suffices, but add ONE end-to-end test per command that invokes `uv run agent-toolkit ...` via `subprocess.run` to validate the post-install user experience.

- [ ] **Step 1: Add the smoke test**

```python
def test_link_subprocess_smoke(env, monkeypatch):
    """End-to-end smoke: invoke through `uv run agent-toolkit` to verify
    stderr/stdout split as a real user would see it."""
    import subprocess
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        ["uv", "run", "--project", str(repo_root), "agent-toolkit",
         "--toolkit-repo", str(toolkit), "link", "user", "claude"],
        capture_output=True, text=True, env={**os.environ, "HOME": str(home)},
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "Linking" in proc.stderr
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
```

- [ ] **Step 2: Run, commit**

```
uv run pytest tests/test_cli_link.py::test_link_subprocess_smoke -v
```

```bash
git add tests/test_cli_link.py tests/test_cli_list.py
git commit -m "test: add subprocess-driven smoke tests for stderr/stdout split"
```

---

## Task 8: Delete bash, bats, parity test, drift gates

**Files:**
- Delete: `bin/agent-toolkit`, `bin/lib/_ui.sh`, `bin/lib/common.sh`, `bin/lib/conventions.sh`, `bin/lib/diff.sh`, `bin/lib/link.sh`, `bin/lib/list.sh`, `bin/lib/unlink.sh`, `bin/lib/` (dir empty), `bin/` (dir empty)
- Delete: `tests/bats/` (entire directory, 17 files including `helpers.bash`)
- Delete: `tests/test_target_dir_parity.py`
- Modify: `lefthook.yml`
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: Verify all bats coverage is now in pytest**

Run a quick audit: every `@test "..."` line across `tests/bats/*.bats` should map to a pytest `test_...` function in the new files. Cross-check the matrices in Tasks 2-5.5.

- [ ] **Step 2: Delete the bash CLI tree**

```bash
git rm -r bin/
```

- [ ] **Step 3: Delete the bats tree**

```bash
git rm -r tests/bats/
```

- [ ] **Step 4: Delete the parity test**

```bash
git rm tests/test_target_dir_parity.py
```

- [ ] **Step 5: Update `lefthook.yml`**

Remove the `bats:` block:

```yaml
pre-commit:
  parallel: true
  commands:
    pytest:
      run: uv run pytest -q
      stage_fixed: false
    schema-vendor-check:
      run: diff schemas/asset-frontmatter.v1alpha1.json src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha1.json
      stage_fixed: false
```

- [ ] **Step 6: Update `.github/workflows/test.yml`**

Remove the `bats` job entirely; keep only the `pytest` job:

```yaml
name: test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run pytest -q
```

- [ ] **Step 7: Run full pytest, verify green**

```
uv run pytest -q
```
Expected: all green; no references to deleted modules.

- [ ] **Step 8: Commit**

```bash
git add lefthook.yml .github/workflows/test.yml
git commit -m "chore: remove bash CLI, bats suite, and parity test"
```

---

## Task 9: Update docs

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/agent-toolkit/cli.md`

- [ ] **Step 1: Update `AGENTS.md`**

Replace the "Code map" tree to remove `bin/agent-toolkit` and `bin/lib/` entries; replace with a single-language description. Strike the "Bash CLI is for filesystem operations (symlinks). Stays zero-dep." line under "Layered contract". Replace the "Development workflow" `bats tests/bats` line with nothing (just `uv run pytest -q` remains).

Specifically:

```markdown
## Code map

```
src/agent_toolkit_cli/                 Python package: validator, walker, generators,
                                   ingest, security, doctor, command implementations.
  _repo_resolution.py              Four-step resolver: resolve_toolkit_root().
  _schemas/                        Bundled v1alpha1 schema (vendored).
  schema.py                        Validator (loads bundled schema via importlib.resources).
  walker.py                        Asset discovery (path-driven, skips submodules).
  cli.py                           Click group with --toolkit-repo option.
  commands/                        check, fix, doctor, new, inventory, ingest,
                                   link, unlink, list, diff, _list_json, _yaml_edit.
  generators/                      Pure functions: (assets, repo_state) → string.
src/agent_toolkit_tui/             Textual TUI (sibling package, [tui] extra).
schemas/                           Top-level vendored schema (mirrors _schemas, used by
                                   schema-drift CI as the diff target).
docs/agent-toolkit/cli.md          Command reference (human-readable).
tests/                             pytest suite.
```
```

Drop point 6 in "Layered contract" (the bash-CLI bullet).

- [ ] **Step 2: Update `docs/agent-toolkit/cli.md`**

In the file's preamble (line 1-7), change:

> Bash subcommands (`link`, `unlink`, `list`, `diff`) run with zero dependencies. Python subcommands (`check`, `fix`, `doctor`, `new`) require `uv` and the installed package.

to:

> All subcommands run as a single Click-based Python CLI installed via `uv tool install`.

Throughout the doc, replace example invocations of `bin/agent-toolkit` with `agent-toolkit` (the user-facing entry point on PATH after install). Keep flag tables identical.

- [ ] **Step 3: Run `agent-toolkit check` to ensure AGENTS.md drift gate is happy**

```
uv run agent-toolkit check --exit-code
```
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md docs/agent-toolkit/cli.md
git commit -m "docs: reflect single-language CLI after bash port"
```

---

## Task 10: Final smoke test

**Files:** none.

- [ ] **Step 1: Reinstall the CLI and run the published bootstrap recipe**

```bash
uv tool install . --reinstall
agent-toolkit list
agent-toolkit link user claude --all -y --toolkit-repo ~/GitHub/agent-toolkit
```
Expected: both succeed, no `Error: No such command 'link'`, symlinks under `~/.claude/skills` reflect every claude-compatible skill.

- [ ] **Step 2: Smoke-test the TUI write-side**

```bash
agent-toolkit-tui --headless --apply --plan /tmp/plan.txt --scope user --harness claude --op link --toolkit-repo ~/GitHub/agent-toolkit
```
Expected: rc=0; the plan applies; no `RunnerError: link --plan grammar error (rc=2)`.

- [ ] **Step 3: Run full pytest, verify green**

```
uv run pytest -q
```

- [ ] **Step 4: Final commit (only if anything changed)**

```bash
git status
# If nothing to commit, skip.
```

---

## Done when

- All 9+ commits land on the feat-1 branch in order: scaffold → link → unlink → list → diff → conventions → tui → delete-bash → docs.
- `pytest -q` is green and covers everything bats covered.
- `uv tool install . --reinstall && agent-toolkit list` works.
- `bin/`, `tests/bats/`, `tests/test_target_dir_parity.py` are gone.
- `lefthook.yml` and `.github/workflows/test.yml` no longer reference bats.
- TUI write-side works post-install.

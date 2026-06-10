# Standard Agents Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `standard` a real, installable projection for the agents kind — one file in `.claude/agents/` covering every harness that natively reads that dir — and give the TUI agents tab its Standard column.

**Architecture:** A new `agent_adapters/standard.py` holds the per-scope coverage table (`STANDARD_AGENT_READERS`) and a `_StandardAdapter` whose destination is the `.claude/agents/<slug>.md` slot (the same file the claude-code adapter writes — one artifact, one name). The dispatcher special-cases `get_adapter("standard")`; every disk scan (facade linked-scan, status, doctor) dedupes by destination so the slot is reported once, as `standard`. The TUI derives the agents-tab columns from `MAIN_HARNESSES` minus per-scope coverage (no long-tail pseudo-column — CLI-only, post-#351 decision). No lock schema change (the agents lock records no harness tokens).

**Tech Stack:** Python 3.12, Click, Textual, pytest. Run tests with `uv run pytest`.

**Worker notes:**
- Spec: `docs/superpowers/specs/2026-06-10-standard-agents-projection-design.md`. Issue: #361.
- #351/PR #359 is MERGED (728414f) — `composition.py` with `MAIN_HARNESSES`, kind-agnostic `_standard_info`, and the coverage-guard test pattern all exist on main. If `src/agent_toolkit_tui/composition.py` is missing, stop and rebase.
- The pre-commit hook runs the full pytest suite; `test_empty_machine_is_empty` fails locally only (green on CI) — `--no-verify` is sanctioned when it is the only failure. Every commit carries a `Device: <hostname -s>` trailer.
- TUI pilot-test trap (#351 lesson): the grids' `space`/`i` priority bindings resolve from the FOCUSED widget's ancestor chain — call `table.focus()` after any direct `cursor_coordinate` assignment or the keys go elsewhere.

---

### Task 0: Research re-verification (web) — coverage evidence

Re-verify which harnesses read `.claude/agents/` before the coverage table is
written. Output: updated research fragments + matrix, and a confirmed (or
amended) value for `STANDARD_AGENT_READERS` used in Task 1.

**Files:**
- Modify: `docs/agent-toolkit/research/subagent-fragments/` (per-batch files as findings require)
- Modify: `docs/agent-toolkit/harness-matrix.md` (agent-kind rows + the § Cross-harness convergence note)

- [ ] **Step 1: Re-verify the five known readers.** For each of `claude-code`,
  `kode`, `neovate`, `cortex`, `devin`: WebFetch the citation already in the
  matrix row (e.g. `code.claude.com/docs/en/sub-agents`,
  `github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md`,
  `neovateai/neovate-code:src/agent/agentManager.ts`,
  `docs.snowflake.com/en/user-guide/cortex-code/extensibility`,
  `cli.devin.ai/docs/subagents`) and confirm: does it still read
  `~/.claude/agents/` (global) and/or `.claude/agents/` (project)? Record
  scope-level evidence per harness.

- [ ] **Step 2: Sweep the rest of the supported set for new compat layers.**
  For each of `augment`, `codebuddy`, `command-code`, `cursor`, `droid`,
  `forgecode`, `junie`, `mux`, `pochi`, `qoder`, `rovodev`, `aider-desk`,
  `dexto`, `firebender`, `gemini-cli`, `github-copilot`, `kilo`, `kiro-cli`,
  `mistral-vibe`, `opencode`, `qwen-code`: WebSearch
  `"<harness>" ".claude/agents" subagents` + check the official docs cited in
  the matrix. A harness joins the covered set ONLY with a citable source
  stating it reads `.claude/agents/` by default (no flags/config).

- [ ] **Step 3: Record findings.** Update the touched fragment files'
  matrix rows + "What I checked" notes, and the harness-matrix § Cross-harness
  convergence note, with citations and today's date. If the verified sets
  differ from the spec's (global: claude-code, kode, neovate, cortex;
  project: + devin), use the VERIFIED sets in Task 1 and note the delta in the
  PR description.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/
git commit -m "docs(research): re-verify .claude/agents readers for the standard agents projection (#361)

Device: $(hostname -s)"
```

---

### Task 1: Coverage table + standard adapter (TDD)

**Files:**
- Create: `src/agent_toolkit_cli/agent_adapters/standard.py`
- Create: `tests/test_cli/test_agent_standard_adapter.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Standard agents projection adapter (#361): one .claude/agents/<slug>.md
slot covering every harness that natively reads that dir."""
from pathlib import Path

import pytest

from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError
from agent_toolkit_cli.agent_adapters.standard import (
    STANDARD_AGENT_READERS,
    adapter_for,
    agents_standard_covered,
)


def _canonical(tmp_path: Path) -> Path:
    c = tmp_path / "canonical"
    c.mkdir()
    f = c / "demo.md"
    f.write_text("---\nname: demo\ndescription: d\n---\nbody\n")
    return f


def test_readers_table_shape():
    assert set(STANDARD_AGENT_READERS) == {"global", "project"}
    for scope, names in STANDARD_AGENT_READERS.items():
        assert "claude-code" in names
    # devin reads .claude/agents at project scope only (matrix evidence).
    assert "devin" not in STANDARD_AGENT_READERS["global"]
    assert "devin" in STANDARD_AGENT_READERS["project"]


def test_readers_are_real_catalog_harnesses():
    """Catalog drift guard (review finding): a renamed/removed harness in the
    table would otherwise silently regain a default install while the panel
    lists a ghost name."""
    from agent_toolkit_cli.skill_agents import AGENTS
    all_readers = frozenset().union(*STANDARD_AGENT_READERS.values())
    assert all_readers <= set(AGENTS)


def test_agents_standard_covered_accessor():
    assert agents_standard_covered("global") == STANDARD_AGENT_READERS["global"]
    with pytest.raises(KeyError):
        agents_standard_covered("nope")


def test_destination_is_claude_agents_slot(tmp_path):
    a = adapter_for()
    assert a.destination("demo", scope="global", home=tmp_path) == \
        tmp_path / ".claude" / "agents" / "demo.md"
    assert a.destination("demo", scope="project", project=tmp_path) == \
        tmp_path / ".claude" / "agents" / "demo.md"


def test_install_uninstall_roundtrip(tmp_path):
    content = _canonical(tmp_path)
    a = adapter_for()
    out = a.install("demo", content, scope="global", home=tmp_path)
    assert out.read_text() == content.read_text()
    a.uninstall("demo", scope="global", home=tmp_path)
    assert not out.exists()


def test_adopt_if_identical(tmp_path):
    """A pre-existing byte-identical file (e.g. a prior claude-code install)
    is adopted silently — no conflict, sentinel written. (Adoption is safe:
    deleting an adopted file later loses nothing — its content is the
    canonical's by definition.)"""
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(content.read_text())  # identical, no sentinel
    a = adapter_for()
    out = a.install("demo", content, scope="global", home=tmp_path)
    assert out == dest
    assert _sentinel_path(dest).exists()  # contract: adoption claims ownership


def test_destination_rejects_traversal_slugs(tmp_path):
    """Defense for the new high-value target: a slug containing path
    separators must not escape the agents dir."""
    a = adapter_for()
    with pytest.raises(ValueError):
        a.destination("../evil", scope="global", home=tmp_path)


def test_foreign_different_content_conflicts(tmp_path):
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    with pytest.raises(AgentProjectionConflictError):
        a.install("demo", content, scope="global", home=tmp_path)


def test_facade_overwrite_flag_does_not_bypass_guard(tmp_path):
    """PM review (MAJOR 2): every CLI-installable slug has a global lock
    entry, so the facade passes overwrite=True — that must NOT authorize
    clobbering a sentinel-less user file in the shared dir."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    with pytest.raises(AgentProjectionConflictError):
        a.install("demo", content, scope="global", home=tmp_path, overwrite=True)


def test_uninstall_leaves_unowned_file(tmp_path):
    """PM review (MINOR 4): uninstall must not unlink a sentinel-less,
    content-divergent file — over-listing is NOT harmless in a shared dir."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("something the user wrote\n")
    a = adapter_for()
    a.uninstall("demo", scope="global", home=tmp_path, canonical_content=content)
    assert dest.exists()  # left in place


def test_uninstall_removes_sentinelless_content_match(tmp_path):
    """Pre-#361 claude-code installs wrote no sentinel; content matching the
    canonical is sufficient ownership evidence for detach."""
    content = _canonical(tmp_path)
    dest = tmp_path / ".claude" / "agents" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(content.read_text())
    a = adapter_for()
    a.uninstall("demo", scope="global", home=tmp_path, canonical_content=content)
    assert not dest.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli/test_agent_standard_adapter.py -q`
Expected: FAIL — `ModuleNotFoundError: ...agent_adapters.standard`.

- [ ] **Step 3: Implement** (`agent_adapters/standard.py`)

```python
"""Standard agents projection (#361): the .claude/agents/<slug>.md slot.

`.claude/agents/` is the de-facto agents-kind convergence dir — read natively
by multiple harnesses (per-scope table below). Installing `standard` writes
ONE file that all covered harnesses consume; it is the same file the
claude-code symlink-adapter cell writes (one artifact, one name — every scan
dedupes by destination and reports it as `standard`).
"""
from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path

# Harnesses that natively read the standard agents dir, per scope.
# Evidence: docs/agent-toolkit/research/subagent-fragments/ (re-verified for
# #361 — see Task 0 commit). devin reads .claude/agents/*.md at project scope
# only; its global path is a profile-dir AGENT.md.
STANDARD_AGENT_READERS: dict[str, frozenset[str]] = {
    "global":  frozenset({"claude-code", "kode", "neovate", "cortex"}),
    "project": frozenset({"claude-code", "kode", "neovate", "cortex", "devin"}),
}

_TEMPLATES = {
    "global": "{HOME}/.claude/agents/{SLUG}.md",
    "project": "{PROJECT}/.claude/agents/{SLUG}.md",
}


def agents_standard_covered(scope: str) -> frozenset[str]:
    """Covered set for a scope. KeyError on unknown scope (fail loud)."""
    return STANDARD_AGENT_READERS[scope]


class _StandardAdapter:
    """Install/uninstall the single standard agents slot."""

    harness = "standard"

    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        # Reuse the symlink adapter's template expansion (same fail-loud
        # semantics for missing home/project).
        from agent_toolkit_cli.agent_adapters.symlink import _expand
        if scope not in _TEMPLATES:
            raise ValueError(
                f"standard: scope must be 'global' or 'project', got {scope!r}"
            )
        if "/" in slug or "\\" in slug or slug in (".", ".."):
            raise ValueError(f"standard: invalid slug {slug!r}")
        return _expand(_TEMPLATES[scope], home=home, project=project, slug=slug)

    def install(
        self, slug: str, content_path: Path, *, scope: str,
        home: Path | None = None, project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self.destination(slug, scope=scope, home=home, project=project)
        # Adopt-if-identical (#361): a pre-existing byte-identical file (e.g.
        # a prior `--harnesses claude-code` install) becomes tool-owned.
        if dest.exists() and not dest.is_symlink() and filecmp.cmp(
            content_path, dest, shallow=False,
        ):
            _sentinel_path(dest).touch()
            return dest
        # Ownership = SENTINEL, not lock (PM review): the facade passes
        # overwrite=True for any locked slug, but lock membership is not
        # evidence we own a file in the shared .claude/agents/ dir (users
        # hand-author agents there). Ignore the facade flag; only the
        # sentinel authorizes overwriting a divergent existing file.
        _guard_foreign(dest, harness="standard", overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(content_path, dest)
        _sentinel_path(dest).touch()
        return dest

    def uninstall(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> None:
        """Detach the slot — ownership-guarded (PM review): unlink only when
        the sentinel exists OR the slot matches `canonical_content` (covers
        pre-#361 sentinel-less claude-code installs). A sentinel-less,
        content-divergent file is a user's — leave it and say so."""
        dest = self.destination(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        if dest.exists() or dest.is_symlink():
            owned = sentinel.exists() or (
                canonical_content is not None
                and canonical_content.exists()
                and not dest.is_symlink()
                and filecmp.cmp(canonical_content, dest, shallow=False)
            )
            if owned:
                dest.unlink()
            else:
                import sys
                print(
                    f"standard: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()


def adapter_for() -> _StandardAdapter:
    return _StandardAdapter()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli/test_agent_standard_adapter.py -q`
Expected: PASS (6 tests). If Task 0 amended the reader sets, update
`test_readers_table_shape` to match the verified evidence.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/standard.py tests/test_cli/test_agent_standard_adapter.py
git commit -m "feat(agent): standard projection adapter + per-scope coverage table (#361)

Device: $(hostname -s)"
```

---

### Task 2: Dispatcher + facade integration (dedupe-by-destination)

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/__init__.py:174-193` (`get_adapter`)
- Modify: `src/agent_toolkit_cli/agent_install.py:78-122` (`_current_linked_agents`)
- Test: `tests/test_cli/test_agent_install.py` (extend)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cli/test_agent_install.py`)

```python
# --- #361: standard slot ---------------------------------------------------

def test_get_adapter_standard_returns_adapter():
    from agent_toolkit_cli.agent_adapters import get_adapter
    a = get_adapter("standard")
    assert a.harness == "standard"


def test_linked_scan_reports_standard_once(tmp_path, monkeypatch):
    """The .claude/agents slot is reported as `standard` only — harnesses
    whose destination is the SAME file (claude-code globally; also kode/
    neovate project-side) are deduped, or plan() would compute a remove for
    claude-code that deletes the shared file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import _current_linked_agents
    linked = _current_linked_agents(
        slug="demo", scope="global", home=tmp_path, project=None,
    )
    assert "standard" in linked
    assert "claude-code" not in linked


def test_plan_standard_to_standard_is_noop(tmp_path, monkeypatch):
    """Re-installing standard over an existing slot computes an empty delta."""
    monkeypatch.setenv("HOME", str(tmp_path))
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="demo", scope="global", target_agents=("standard",),
             home=tmp_path)
    assert "standard" not in p.add_agents
    assert "claude-code" not in p.remove_agents


def test_linked_scan_dedupe_kode_project_scope(tmp_path):
    """kode's PROJECT cell IS {PROJECT}/.claude/agents/<slug>.md — the same
    file as the standard slot. Without project-scope dedupe the scan would
    double-report and a delta could delete the shared file (review finding)."""
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import _current_linked_agents
    linked = _current_linked_agents(
        slug="demo", scope="project", home=None, project=tmp_path,
    )
    assert "standard" in linked
    assert "kode" not in linked


def test_uninstall_covered_token_routes_to_standard_adapter(tmp_path):
    """Destination-based normalization in the facade (review finding): the
    production deletion path is agent_install.uninstall()'s DIRECT adapter
    loop, not plan(). A covered token whose destination IS the slot (kode at
    project scope) must route to the standard adapter so the .attk sentinel
    is cleaned up with the file."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std
    from agent_toolkit_cli.agent_install import uninstall

    canonical = tmp_path / "c"
    canonical.mkdir()
    content = canonical / "demo.md"
    content.write_text("x\n")
    std = _std()
    out = std.install("demo", content, scope="project", project=tmp_path)
    assert _sentinel_path(out).exists()
    uninstall(slug="demo", scope="project", home=None, project=tmp_path,
              harnesses=("kode",))
    assert not out.exists()
    assert not _sentinel_path(out).exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli/test_agent_install.py -q -k standard`
Expected: FAIL — `UnsupportedMechanismError` for
`test_get_adapter_standard_returns_adapter`; plain AssertionError for the two
scan tests (the pre-change scan reports `claude-code` for the slot, so
`"standard" in linked` fails without raising).

- [ ] **Step 3: Implement.** In `get_adapter` insert BEFORE the catalog lookup:

```python
    if harness_name == "standard":
        # #361: the standard agents projection — a real slot, dispatched
        # ahead of the catalog (whose "standard" entry is the skills bundle
        # pseudo-agent with mechanism='none').
        from agent_toolkit_cli.agent_adapters import standard
        return standard.adapter_for()
```

In `_current_linked_agents`, replace the loop body with a dedupe-by-destination
scan where the standard slot wins:

```python
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std

    linked: list[str] = []
    seen_dests: set[Path] = set()

    # Standard slot first — it owns the .claude/agents/<slug>.md destination;
    # any harness cell resolving to the same file is deduped below (#361).
    std = _std()
    try:
        std_dest = std.destination(slug, scope=scope, home=home, project=project)
    except ValueError:
        std_dest = None
    if std_dest is not None:
        seen_dests.add(std_dest)
        if std_dest.exists() or std_dest.is_symlink():
            linked.append("standard")

    for name in _AGENTS:
        if name == "standard":
            continue  # already handled above (get_adapter now intercepts it)
        if name in synthetic_names or name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        try:
            dest = adapter.destination(
                slug, scope=scope, home=home, project=project,
            )
        except (ValueError, _UnknownAgentError):
            continue
        if dest in seen_dests:
            continue  # same artifact as the standard slot — already reported
        if dest.exists() or dest.is_symlink():
            linked.append(name)
    return tuple(linked)
```

Also update the module docstring sentence "No standard-bundle concept exists
for agents" to: "The agents kind's standard projection is the
`.claude/agents/<slug>.md` slot (#361) — `standard_bundle_link` stays None
because the slot is an adapter, not a core bundle link."

Destination-based normalization goes on **BOTH facade paths** (PM review
MAJOR 3: name-based install normalization alone leaves `--harnesses kode -p`
writing the slot through the sentinel-unaware symlink cell — no sentinel, no
adopt — recreating the second writer). Extract one helper used by both:

```python
def _normalize_to_standard(
    name: str, slug: str, *, scope: Scope,
    home: Path | None, project: Path | None,
) -> str:
    """Return 'standard' when `name`'s destination IS the standard slot
    (claude-code everywhere; kode at project scope), else `name` (#361)."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std

    if name == "standard":
        return name
    try:
        std_dest = _std().destination(slug, scope=scope, home=home, project=project)
        adapter = agent_adapters.get_adapter(name)
        if adapter.destination(slug, scope=scope, home=home, project=project) == std_dest:
            return "standard"
    except (ValueError, _UnknownAgentError, UnsupportedMechanismError):
        pass
    return name
```

In `apply()`'s add loop, normalize before dispatch:

```python
    for name in plan.add_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        name = _normalize_to_standard(
            name, plan.slug, scope=plan.scope, home=home, project=project,
        )
        ...
```

and add the pinning test (append to the Task 2 tests):

```python
def test_install_kode_project_scope_routes_to_standard_adapter(tmp_path):
    """PM review (MAJOR 3): kode's project cell IS the slot — installing it
    must go through the standard adapter (sentinel written, adopt logic)."""
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli import agent_install

    canonical = tmp_path / ".agents" / "agents" / "demo"  # adapt to canonical_agent_dir's project layout
    canonical.mkdir(parents=True)
    (canonical / "demo.md").write_text("x\n")
    p = InstallPlan(slug="demo", scope="project", source=None, ref=None,
                    add_agents=("kode",), remove_agents=())
    agent_install.apply(p, project=tmp_path)
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    assert slot.exists()
    assert _sentinel_path(slot).exists()
```

In `agent_install.uninstall()`, use the same helper at the top of the adapter
loop (the production deletion paths — uninstall_cmd, the TUI apply,
remove_cmd — all call this DIRECT loop, not plan(), so the dedupe must live
here too):

```python
    canonical_content = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    ) / f"{slug}.md"
    for name in harnesses:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        name = _normalize_to_standard(
            name, slug, scope=scope, home=home, project=project,
        )
        try:
            adapter = agent_adapters.get_adapter(name)
        except (UnsupportedMechanismError, _UnknownAgentError):
            continue
        try:
            if name == "standard":
                # Ownership-guarded detach (PM review MINOR 4): pass the
                # scope canonical so sentinel-less pre-#361 installs detach
                # by content match, while user files are left in place.
                adapter.uninstall(
                    slug, scope=scope, home=home, project=project,
                    canonical_content=canonical_content,
                )
            else:
                adapter.uninstall(slug, scope=scope, home=home, project=project)
        except ValueError:
            continue
```

And make sentinel cleanup destination-generic in `_SymlinkAdapter.uninstall`
(`agent_adapters/symlink.py`) so non-normalized paths (e.g. `agent remove`'s
legacy all-enabled list) never orphan a sentinel that would later authorize a
silent clobber (review finding — the orphaned `.attk` defeats `_guard_foreign`):

```python
    def uninstall(self, slug, *, scope, home=None, project=None) -> None:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        sentinel = _sentinel_path(dest)
        if sentinel.exists():
            sentinel.unlink()
```

(add `from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path`
to symlink.py's imports — `_guard_foreign` is already imported there.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli/test_agent_install.py tests/test_cli/test_agent_standard_rename.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/__init__.py src/agent_toolkit_cli/agent_install.py tests/test_cli/test_agent_install.py
git commit -m "feat(agent): dispatch + linked-scan for the standard slot, dedupe by destination (#361)

Device: $(hostname -s)"
```

---

### Task 3: CLI boundaries — token, default fan-out, status dedupe

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/install_cmd.py:24-48`
- Modify: `src/agent_toolkit_cli/commands/agent/uninstall_cmd.py:21-35`
- Modify: `src/agent_toolkit_cli/commands/agent/remove_cmd.py` (`_all_enabled_harnesses` gains `("standard",)` — see Step 3)
- Modify: `src/agent_toolkit_cli/commands/agent/status_cmd.py:11-33`
- Create: `tests/test_cli/test_agent_cli_standard.py`

- [ ] **Step 1: Write the failing tests**

```python
"""CLI boundaries for the standard agents projection (#361)."""
import pytest


def test_resolve_harnesses_accepts_standard():
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    assert _resolve_harnesses("standard", "global") == ("standard",)


def test_resolve_harnesses_normalizes_claude_code():
    """claude-code names the same slot; normalizing prevents a dual-name
    delta where plan() removes one alias while installing the other."""
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    assert _resolve_harnesses("claude-code", "global") == ("standard",)
    assert _resolve_harnesses("claude-code,cursor", "global") == ("standard", "cursor")


def test_default_fanout_standard_plus_noncovered():
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    from agent_toolkit_cli.commands.agent.install_cmd import _default_harnesses
    got = _default_harnesses("global")
    assert got[0] == "standard"
    covered = agents_standard_covered("global")
    assert not (set(got[1:]) & covered)
    assert "cursor" in got and "pi" in got  # non-covered supported harnesses stay


def test_projected_harnesses_reports_standard_once(tmp_path):
    from pathlib import Path
    from agent_toolkit_cli.commands.agent.status_cmd import _projected_harnesses
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    found = _projected_harnesses("demo", "global", tmp_path, None)
    assert "standard" in found
    assert "claude-code" not in found


def test_cli_install_conflicts_on_foreign_slot_file(tmp_path, monkeypatch):
    """PM review (MINOR 6): the CLI-layer pin for the ownership contract —
    a hand-authored, content-divergent ~/.claude/agents/<slug>.md must fail
    loud through `agent install`, even though the slug has a global lock
    entry (the facade's overwrite=True must not reach the guard)."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    monkeypatch.setenv("HOME", str(tmp_path))
    # arrange: library canonical + global lock entry per the module's
    # existing fixture pattern (see test_agent_install.py helpers), then:
    foreign = tmp_path / ".claude" / "agents" / "demo.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("hand-authored\n")
    r = CliRunner().invoke(main, ["agent", "install", "demo", "-g",
                                  "--harnesses", "standard"])
    assert r.exit_code != 0
    assert "refusing to overwrite" in r.output
    assert foreign.read_text() == "hand-authored\n"


def test_cli_install_refreshes_sentineled_slot(tmp_path, monkeypatch):
    """Sentineled (tool-owned) slots refresh silently through the CLI."""
    from click.testing import CliRunner
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.cli import main
    monkeypatch.setenv("HOME", str(tmp_path))
    # arrange canonical+lock as above; pre-write a stale slot WITH sentinel:
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("stale tool copy\n")
    _sentinel_path(slot).touch()
    r = CliRunner().invoke(main, ["agent", "install", "demo", "-g",
                                  "--harnesses", "standard"])
    assert r.exit_code == 0, r.output
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli/test_agent_cli_standard.py -q`
Expected: FAIL (signature change: `_resolve_harnesses`/`_default_harnesses`
gain a scope argument; normalization missing).

- [ ] **Step 3: Implement.**

`install_cmd.py` — `_default_harnesses` and `_resolve_harnesses` gain `scope`:

```python
def _default_harnesses(scope: str) -> tuple[str, ...]:
    """standard + every enabled harness NOT covered by the standard slot."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    covered = agents_standard_covered(scope)
    result = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none" or name in covered:
            continue
        try:
            get_adapter(name)
            result.append(name)
        except (UnsupportedMechanismError, Exception):
            pass
    return ("standard",) + tuple(sorted(result))


def _resolve_harnesses(harnesses_str: str | None, scope: str) -> tuple[str, ...]:
    """Expand comma-separated harness names or return defaults.

    `standard` is the .claude/agents slot (#361); `claude-code` names the
    same slot and is normalized to it. Deprecated #350 spellings are aliased
    via resolve_agent_token().
    """
    if harnesses_str is None:
        return _default_harnesses(scope)
    parts = [resolve_agent_token(p.strip()) for p in harnesses_str.split(",") if p.strip()]
    parts = ["standard" if p == "claude-code" else p for p in parts]
    unknown = [p for p in parts if p != "standard" and p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    return tuple(dict.fromkeys(parts))  # de-dupe, preserve order
```

Add explicit synthetic-token rejection (review finding: AC7's "rejected"
was previously a silent no-op — `standard-agent` is in AGENTS so it passed
validation and apply() skipped it while the CLI printed "installed"):

```python
    # Reject ALL synthetic catalog names, not just the agent kind's own
    # (PM review MINOR 5): "standard-skill" is in AGENTS too and would
    # otherwise degrade to a silent no-op. #350 aliases (general-skill,
    # general-agent) resolve to these via resolve_agent_token first.
    _SYNTHETIC_REJECT = frozenset({"standard-skill", "standard-agent"})
    synthetic = [p for p in parts if p in _SYNTHETIC_REJECT]
    if synthetic:
        raise click.UsageError(
            f"{', '.join(synthetic)}: synthetic catalog name(s); use 'standard'"
        )
```

Tests: assert UsageError for BOTH `standard-agent` and `standard-skill`
(and that `general-skill` — aliased by #350 — is rejected the same way).

Update the call sites in `install_cmd.py`'s command body explicitly (PM
validator: prose-only call-site changes get missed → TypeError). The body
currently runs `scope_and_roots` FIRST, so `scope` is in hand; the change is:

```python
    # before:
    #     target_harnesses = _resolve_harnesses(harnesses)
    # after (scope from the scope_and_roots call above):
    try:
        target_harnesses = _resolve_harnesses(harnesses, scope)
    except click.UsageError:
        raise
```

(and `_default_harnesses(scope)` is only called from inside
`_resolve_harnesses` — no other call sites exist; verify with
`grep -rn "_default_harnesses(" src/`).

`uninstall_cmd.py`'s `_resolve_harnesses_for_uninstall` gets the
claude-code→standard normalization and the synthetic rejection, but its
**no-flag default stays MAXIMAL**: `("standard",) + all enabled harnesses`
(no covered filter — review finding: pre-#361 default installs wrote real
files at kode/neovate/cortex's OWN dirs, and a covered-aware uninstall
default would strand them forever; adapters are idempotent so over-listing
is harmless per the facade docstring). Only the INSTALL default is
covered-aware. Add a test: default uninstall after a pre-#361-style
all-harness install leaves no projection files.

`remove_cmd.py` (review finding — it was missing from the plan): its
`_all_enabled_harnesses()` helper gains `("standard",)` prepended, so
`agent remove` cleans the slot + sentinel via the standard adapter (the
facade's destination normalization covers the claude-code entry it also
lists). Add `Modify: src/agent_toolkit_cli/commands/agent/remove_cmd.py`
to this task's Files list, plus a test asserting `agent remove` after a
`--harnesses standard` install leaves no `.attk` file in `.claude/agents/`.

`status_cmd.py` — `_projected_harnesses` gains the same dedupe as the facade
scan (standard first, skip same-destination cells):

```python
def _projected_harnesses(slug: str, scope: str, home: object, project: object) -> list[str]:
    """Harness names with a live projection on disk; the .claude/agents slot
    is reported once, as `standard` (#361)."""
    from pathlib import Path
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std
    from agent_toolkit_cli.skill_agents import AGENTS

    home_p = home if isinstance(home, Path) else None
    project_p = project if isinstance(project, Path) else None
    found: list[str] = []
    seen: set[Path] = set()
    std = _std()
    try:
        std_dest = std.destination(slug, scope=scope, home=home_p, project=project_p)
        seen.add(std_dest)
        if std_dest.exists() or std_dest.is_symlink():
            found.append("standard")
    except ValueError:
        pass
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none" or name == "standard":
            continue
        try:
            adapter = get_adapter(name)
            dest = adapter.destination(slug, scope=scope, home=home_p, project=project_p)
            if dest in seen:
                continue
            if dest.exists() or dest.is_symlink():
                found.append(name)
        except (UnsupportedMechanismError, ValueError, Exception):
            pass
    return sorted(found)
```

- [ ] **Step 4: Run the new tests + the agent CLI tests**

Run: `uv run pytest tests/test_cli/test_agent_cli_standard.py tests/test_cli/test_cli_agent*.py tests/test_cli/test_agent_install.py -q`
Expected: PASS. Pre-existing tests that called `_default_harnesses()` /
`_resolve_harnesses(str)` without scope, or asserted claude-code in defaults,
need updating to the new signatures/semantics — they are contract updates,
not regressions; list each in the commit body.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/ tests/test_cli/
git commit -m "feat(agent): standard token at CLI boundaries; covered-aware default fan-out; status dedupe (#361)

Device: $(hostname -s)"
```

---

### Task 4: TUI agents tab — Standard column + info dispatch

**Files:**
- Modify: `src/agent_toolkit_tui/composition.py` (add `agents_nonstandard_main`; update the module docstring — its "Kinds without a standard concept (agents, pi-extensions)" sentence becomes false with this task, PM review MINOR 8)
- Modify: `src/agent_toolkit_tui/column_info.py` (`extra_lines` + kind-aware title — Step 5c)
- Modify: `src/agent_toolkit_tui/agent_state.py:26-34` + cell builder
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py` (Standard column, dispatch trio)
- Test: `tests/test_tui/test_composition.py` (extend), `tests/test_tui/test_agent_grid_standard.py` (new), `tests/test_tui/test_grid_group_regressions.py` (re-scope)

- [ ] **Step 1: Write the failing composition + guard tests** (append to `tests/test_tui/test_composition.py`)

```python
def test_agents_nonstandard_main_today():
    from agent_toolkit_tui.composition import agents_nonstandard_main
    # claude-code is standard-covered; codex is unsupported-by-design;
    # cursor/pi/gemini-cli/opencode keep their own columns.
    # MAIN_HARNESSES declaration order, filtered — same convention as the
    # skills/instructions helpers.
    assert agents_nonstandard_main("global") == ("gemini-cli", "opencode", "pi", "cursor")
    assert agents_nonstandard_main("project") == ("gemini-cli", "opencode", "pi", "cursor")


def test_agents_coverage_guard():
    """Every main harness that supports the agent kind is covered: in the
    standard readers set or a rendered column."""
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    from agent_toolkit_cli.skill_agents import AGENTS
    from agent_toolkit_tui.composition import MAIN_HARNESSES, agents_nonstandard_main
    for scope in ("global", "project"):
        covered = agents_standard_covered(scope)
        rendered = set(agents_nonstandard_main(scope))
        for h in MAIN_HARNESSES:
            if AGENTS[h].subagent_mechanism == "none":
                continue  # e.g. codex: unsupported by design — exempt
            assert h in covered or h in rendered, (
                f"{h} is neither standard-covered nor rendered on the agents tab ({scope})"
            )
```

- [ ] **Step 2: Implement `agents_nonstandard_main`** (append to `composition.py`)

```python
def agents_nonstandard_main(scope: str) -> tuple[str, ...]:
    """Main harnesses that need their own agents column at `scope`:
    support the agent kind (mechanism != 'none') and are not covered by
    the standard .claude/agents slot (#361)."""
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

    covered = agents_standard_covered(scope)
    return tuple(
        h for h in MAIN_HARNESSES
        if AGENTS[h].subagent_mechanism != "none" and h not in covered
    )
```

Run: `uv run pytest tests/test_tui/test_composition.py -q` → PASS.

- [ ] **Step 3: `agent_state.py`** — derive the rendered set and add the
standard cell. Replace the pinned tuple:

```python
from agent_toolkit_tui.composition import agents_nonstandard_main

# Rendered columns (#361): the standard slot first, then the non-covered
# main harnesses (derived per scope; the two scopes happen to yield the
# same set today because devin is not a MAIN harness). Cells are still
# keyed by (scope, harness). The long tail is CLI-only.
INTERACTIVE_HARNESSES: tuple[str, ...] = ("standard",) + agents_nonstandard_main("global")
```

In the cell builder (`_cell_for` / `build_agent_rows`), the `standard`
harness resolves its destination via
`agent_adapters.standard.adapter_for().destination(...)` — same
exists-on-disk check as other cells. `get_adapter("standard")` works after
Task 2, so if the builder goes through `get_adapter`, no special case is
needed — verify and keep whichever path the module already uses.

- [ ] **Step 4: Write the failing grid tests** (`tests/test_tui/test_agent_grid_standard.py`)

```python
"""Standard column on the agents tab (#361)."""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid


def _row(slug: str = "demo") -> AgentRow:
    cells = {(h, "global"): AgentCell(linked=False) for h in INTERACTIVE_HARNESSES}
    return AgentRow(slug=slug, source=f"x/{slug}", ref="main", cells=cells)


class _A(App):
    def compose(self) -> ComposeResult:
        yield AgentGrid([_row()], id="g")


@pytest.mark.asyncio
async def test_columns_standard_first_then_noncovered_main():
    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[1] == "Standard ⓘ"
        assert not any("Claude Code" in l for l in labels)  # absorbed
        assert any("Cursor" in l for l in labels)
        assert any("OpenCode" in l for l in labels)
        assert not any("… +" in l or "\n" in l for l in labels)


@pytest.mark.asyncio
async def test_press_i_on_standard_column_opens_registry_modal():
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        assert "agents" in body
        assert "kode" in body and "neovate" in body and "cortex" in body
        # global-scope panel (the grid default) carries the devin
        # project-only note; after grid.set_scope("project") + reopen, the
        # note must be absent (devin is simply covered there) — add a second
        # assertion block for that scope flip.
        assert "devin" in body
```

- [ ] **Step 5: Implement in `agent_grid.py`.** Mirror the #351
instruction-grid port (it has the same shape — a grid WITHOUT the dispatch
trio):

(a) imports: `from agent_toolkit_tui.column_info import get_column_info`,
`from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal`,
`from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered`.

(b) Columns in `_rebuild`: first data column becomes `Standard ⓘ` (the
`INTERACTIVE_HARNESSES` change in Step 3 does this if the grid renders
display names — special-case the label exactly like skill_grid:
`base = "Standard" if harness == "standard" else AGENTS[harness].display_name`).

(c) Dispatch trio (mirror instruction_grid post-#351):
`_column_key_for_index(col)` → `"standard"` for the standard column index,
else None; `_context_for(key)` → for `"standard"`:

```python
        if key == "standard":
            covered = sorted(agents_standard_covered(self._scope))
            lines_extra = []
            if self._scope == "global":
                lines_extra = ["", "devin reads .claude/agents at project scope only."]
            return {
                "kind": "agents",
                "names": tuple(covered),
                "extra_lines": tuple(lines_extra),
            }
```

and route `action_info` through the registry first (exact pattern of
`instruction_grid.action_info` post-#351). `_standard_info` in
`column_info.py` gains optional `extra_lines` appended after the bullets AND
a kind-aware title (PM review MINOR 8 — "Standard bundle" is the skills-kind
name; the agents slot is an adapter, not a bundle link):

```python
    extra = [str(l) for l in ctx.get("extra_lines", ())]
    title = "Standard slot (agents)" if kind == "agents" else "Standard bundle"
    ...
    return ColumnInfo(
        title=title,
        lines=description + bullets + indicator_note + extra,
    )
```

(Existing skills/instructions tests pin "Standard"-prefixed titles via
`startswith("standard")` case-insensitively — verify they stay green.)

(d) The standard cell toggles like any other (queue link/unlink on the slot;
apply path goes through `agent_install` which resolves the `standard`
adapter after Task 2).

- [ ] **Step 6: Re-scope the regression guard.**
`tests/test_tui/test_grid_group_regressions.py` currently asserts the agents
grid is untouched by the matrix-groups work — #361 deliberately touches it
now. Keep the pi-grid guard as-is; replace the agents guard with:

```python
@pytest.mark.asyncio
async def test_agent_grid_has_standard_but_no_pseudo_column():
    """#361 gives agents a Standard column; the long tail stays CLI-only."""
    app = _A()  # the _GridApp/_row pattern from test_agent_grid_standard.py
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert any("Standard" in l for l in labels)
        assert not any("… +" in l or "STANDARD" in l or "NON-STD" in l
                       or "\n" in l for l in labels)
```

The regression-guard file's `_agent_row()` fixture must also change (PM
validator: it keys cells on the old first column):

```python
def _agent_row(slug: str = "demo") -> AgentRow:
    from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES
    return AgentRow(
        slug=slug, source=f"ajanderson1/{slug}", ref="main",
        cells={(INTERACTIVE_HARNESSES[0], "global"): AgentCell(linked=True)},
    )
```

- [ ] **Step 7: Run the TUI suite; update pre-existing agent-grid layout tests**

Run: `uv run pytest tests/test_tui/ -q`
Expected: failures only in `test_agent_grid.py` assertions pinned to the old
4-column layout (claude-code first, no opencode) — update them to the new
`INTERACTIVE_HARNESSES` (standard, gemini-cli, opencode, pi, cursor — the
MAIN_HARNESSES-order derivation); they are layout-contract updates, listed
in the commit body. PM validator note: `test_agent_grid.py` carries ~8
hardcoded `"claude-code"` literals (cell keys + cursor positioning, roughly
lines 407-470 and 572-575 at plan-writing time — re-grep, don't trust the
numbers): replace the COLUMN-targeting ones with `INTERACTIVE_HARNESSES[0]`
/ `"standard"`; leave any that genuinely test the claude-code HARNESS token
semantics (none are expected to remain). Then: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_tui/ tests/test_tui/
git commit -m "feat(tui): Standard column + info dispatch on the agents tab (#361)

Device: $(hostname -s)"
```

---

### Task 5: Doctor — standard-slot drift/orphan findings

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py:43-133` (`_diagnose`)
- Test: `tests/test_cli/test_agent_doctor.py` (extend; create if absent)

- [ ] **Step 1: Write the failing tests**

```python
# --- #361: standard slot findings -------------------------------------------

def _setup_locked_agent(tmp_path):
    """Library canonical + lock entry for slug 'demo' at global scope."""
    import json
    home = tmp_path
    lib = home / ".agent-toolkit" / "agents" / "demo"
    lib.mkdir(parents=True)
    (lib / "demo.md").write_text("canonical\n")
    lock = home / ".agent-toolkit" / "agents-lock.json"
    lock.write_text(json.dumps({"version": 1, "skills": {"demo": {
        "source": "x/demo", "sourceType": "github", "agentPath": "demo.md"
    }}}))
    return home


def test_doctor_flags_standard_slot_drift(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home = _setup_locked_agent(tmp_path)
    slot = home / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("DIFFERENT\n")
    from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose
    findings = _diagnose(slugs=None, scope="global", home=home, project=None)
    assert any(f.kind == "standard-slot-drift" and f.slug == "demo" for f in findings)


def test_doctor_clean_when_slot_matches(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home = _setup_locked_agent(tmp_path)
    slot = home / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("canonical\n")
    from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose
    findings = _diagnose(slugs=None, scope="global", home=home, project=None)
    assert not any(f.kind.startswith("standard-slot") for f in findings)
```

(Adapt `_setup_locked_agent` to the module's existing fixture helpers if it
already has them — the contract is the two assertions.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -q -k standard`
Expected: FAIL (no such finding kind).

- [ ] **Step 3: Implement.** In `_diagnose`'s per-slug loop, after the
"missing content file" check. **The comparison baseline is scope-aware**
(review finding: `_diagnose`'s `canonical = library_agent_path(slug)` is the
GLOBAL library; a project slot is seeded from the PROJECT canonical and may
legitimately differ from the global library — comparing against the wrong
baseline reports false drift and the fix would install the wrong version):

```python
        # 5. Standard-slot drift (#361): the .claude/agents/<slug>.md slot
        # exists but differs from the scope-appropriate canonical.
        from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std
        from agent_toolkit_cli.agent_paths import canonical_agent_dir
        scope_content = canonical_agent_dir(
            slug, scope=scope, home=home, project=project,
        ) / f"{slug}.md"
        if scope_content.exists():
            try:
                slot = _std().destination(slug, scope=scope, home=home, project=project)
            except ValueError:
                slot = None
            if slot is not None and slot.exists() and not filecmp.cmp(
                scope_content, slot, shallow=False,
            ):
                findings.append(Finding(
                    slug=slug, kind="standard-slot-drift", scope=scope,
                    path=slot,
                    detail="standard slot differs from canonical — local "
                           f"edits to {slot} will be DISCARDED by the fix "
                           f"(baseline: {scope_content})",
                    fix_action=FixAction(
                        shell_preview=f"diff {slot} {scope_content}; cp {scope_content} {slot}",
                        apply=lambda c=scope_content, s=slot: shutil.copy2(c, s),
                    ),
                ))
```

Add `import filecmp` to the module imports.

After the per-slug loop (beside the existing orphan-canonical sweep), add the
**standard-slot orphan sweep** (review finding: spec AC requires drift AND
orphan; the per-slug loop structurally cannot see slot files for slugs absent
from the lock):

```python
    # 6. Standard-slot sweep (#361, sentinel-aware — PM review MAJOR 1):
    # .claude/agents/ is the PRIMARY dir where users hand-author Claude Code
    # subagents (this repo's advisor bench lives there), so "no lock entry"
    # must NEVER imply an rm fix. Ownership evidence is the .attk sidecar.
    if not slugs:
        from agent_toolkit_cli.agent_adapters import _sentinel_path
        from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std
        try:
            agents_dir = _std().destination(
                "__probe__", scope=scope, home=home, project=project,
            ).parent
        except ValueError:
            agents_dir = None
        if agents_dir is not None and agents_dir.is_dir():
            lock_slugs = set(lock.skills.keys())
            for child in sorted(agents_dir.glob("*.md")):
                if child.stem in lock_slugs:
                    continue
                if _sentinel_path(child).exists():
                    # Tool-written, lock entry gone → true orphan.
                    orphan = child
                    findings.append(Finding(
                        slug=child.stem, kind="standard-slot-orphan", scope=scope,
                        path=orphan,
                        detail="tool-written standard slot file (sentinel "
                               "present) has no lock entry",
                        fix_action=FixAction(
                            shell_preview=f"rm {orphan}",
                            apply=lambda p=orphan: p.unlink(),
                        ),
                    ))
                else:
                    # User-authored (or pre-toolkit) — report only, NO fix
                    # (the #337 doctor posture: adopt/report, never delete).
                    findings.append(Finding(
                        slug=child.stem, kind="standard-slot-unmanaged",
                        scope=scope, path=child,
                        detail="file in the standard agents dir is not "
                               "managed by agent-toolkit-cli (no sentinel, "
                               "no lock entry) — informational only",
                        fix_action=None,
                    ))
            # Dangling sidecars (PM review MINOR 7): a sentinel whose main
            # file is gone would later authorize a silent clobber of a new
            # same-named user file via _guard_foreign — reclaim it.
            for side in sorted(agents_dir.glob(".*.attk")):
                main = agents_dir / side.name[1:-len(".attk")]
                if not main.exists():
                    dangling = side
                    findings.append(Finding(
                        slug=main.stem, kind="standard-slot-dangling-sidecar",
                        scope=scope, path=dangling,
                        detail="ownership sidecar exists but its slot file "
                               "is gone; stale sidecar would authorize a "
                               "future silent overwrite",
                        fix_action=FixAction(
                            shell_preview=f"rm {dangling}",
                            apply=lambda p=dangling: p.unlink(),
                        ),
                    ))
```

Add the matching tests to Step 1's file:

```python
def test_doctor_flags_sentineled_orphan_only(tmp_path, monkeypatch):
    """PM review (MAJOR 1): rm is offered ONLY for tool-written (sentineled)
    files; a hand-authored agent gets a report-only 'unmanaged' notice."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    monkeypatch.setenv("HOME", str(tmp_path))
    home = _setup_locked_agent(tmp_path)
    agents = home / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    tool_stray = agents / "tool-stray.md"
    tool_stray.write_text("x\n")
    _sentinel_path(tool_stray).touch()          # tool-written, lock entry gone
    user_agent = agents / "my-advisor.md"
    user_agent.write_text("hand-authored\n")    # user's file, no sentinel
    from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose
    findings = _diagnose(slugs=None, scope="global", home=home, project=None)
    orphan = [f for f in findings if f.kind == "standard-slot-orphan"]
    unmanaged = [f for f in findings if f.kind == "standard-slot-unmanaged"]
    assert [f.slug for f in orphan] == ["tool-stray"]
    assert orphan[0].fix_action is not None
    assert [f.slug for f in unmanaged] == ["my-advisor"]
    assert unmanaged[0].fix_action is None       # NEVER rm a user file


def test_doctor_flags_dangling_sidecar(tmp_path, monkeypatch):
    """PM review (MINOR 7): a sidecar without its main file is reclaimed —
    a stale sentinel would otherwise authorize a future silent clobber."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = _setup_locked_agent(tmp_path)
    agents = home / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / ".gone.md.attk").touch()
    from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose
    findings = _diagnose(slugs=None, scope="global", home=home, project=None)
    assert any(f.kind == "standard-slot-dangling-sidecar" for f in findings)


def test_doctor_project_drift_uses_project_canonical(tmp_path, monkeypatch):
    """Project doctor compares the slot against the PROJECT canonical — a
    project slot matching its project canonical is clean even when the
    global library has moved on (review finding)."""
    project = tmp_path / "proj"
    canonical = project / ".agents" / "agents" / "demo"  # adapt to canonical_agent_dir's actual project layout
    canonical.mkdir(parents=True)
    (canonical / "demo.md").write_text("project version\n")
    slot = project / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("project version\n")
    # ...write a project lock entry for demo per the module's fixture pattern...
    from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose
    findings = _diagnose(slugs=None, scope="project", home=None, project=project)
    assert not any(f.kind == "standard-slot-drift" for f in findings)
```

(Adapt the project-canonical path in the second test to what
`canonical_agent_dir(slug, scope="project", project=project)` actually
returns — verify before writing the fixture.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/doctor_cmd.py tests/test_cli/test_agent_doctor.py
git commit -m "feat(agent): doctor flags standard-slot drift with a copy fix (#361)

Device: $(hostname -s)"
```

---

### Task 6: Docs + final verification

**Files:**
- Modify: `docs/agent-toolkit/cli.md` (agent section)
- Modify: `docs/agent-toolkit/harness-matrix.md` (§ Cross-harness convergence)

- [ ] **Step 1: `cli.md`** — in the agent commands section, document:
`--harnesses standard` (the `.claude/agents` slot + covered set, per-scope),
the claude-code normalization, and the covered-aware default fan-out. One
sentence each, beside the existing examples.

- [ ] **Step 2: `harness-matrix.md`** — update the § Cross-harness
convergence note: the single-symlink optimization is now implemented as the
standard agents projection (#361); point at
`agent_adapters/standard.py::STANDARD_AGENT_READERS` as the SSOT.

- [ ] **Step 3: Full suite + smoke**

Run: `uv run pytest -q`
Expected: PASS (modulo the known-local `test_empty_machine_is_empty`).

Smoke (sandbox HOME):
```bash
H=$(mktemp -d)
HOME=$H uv run agent-toolkit-cli agent add /tmp/demo-agent --slug demo-agent 2>/dev/null || true
HOME=$H uv run agent-toolkit-cli agent install demo-agent -g --harnesses standard
ls "$H/.claude/agents/"            # demo-agent.md present
HOME=$H uv run agent-toolkit-cli agent status   # shows: standard
HOME=$H uv run agent-toolkit-cli agent uninstall demo-agent -g --harnesses standard
ls "$H/.claude/agents/" 2>/dev/null  # empty / gone
```

(If `/tmp/demo-agent` is absent, create it: a git repo containing
`demo-agent.md` with name/description frontmatter.)

- [ ] **Step 4: Commit + PR**

```bash
git add docs/agent-toolkit/
git commit -m "docs(agent): standard projection — cli.md + harness-matrix convergence note (#361)

Device: $(hostname -s)"
```

The runner opens a PR per its own flow, conventional title
`feat(agent): standard agents projection (.claude/agents) + Standard column on the agents tab`
so release-please cuts a minor.

# Split `ajanderson1/skills` into category repos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the flat `ajanderson1/skills` monorepo into 8 independent private category repos, re-registering all 31 mapped skills across the global library + ~13 project locks (incl. `~/Journal`), sanitizing tracked secrets, re-pointing the broken `servers` alias, removing the local `telegram-botfather` stray, and archiving the old repo — with zero broken skills.

**Architecture:** A test-driven, idempotent, **transactional** Python migration script (`scripts/migrate_skills_split.py`) owns the deterministic logic AND a real `--apply` path that DRIVES the shipped `agent-toolkit-cli` verbs in two ordered phases — **Phase A global library** (`skill remove`/`add`, which are global-only), then **Phase B project scopes** (`skill uninstall -p`/`install -p`, which re-derive from the global lock; the driver purges any preserved project canonical still pointing at the old monorepo cache first, because `uninstall -p` is non-destructive and `ensure_project_canonical` links only "if absent"). No CLI source change (ownership is owner-keyed via `OWNED_OWNERS={"ajanderson1"}`). A pre-copy security scan gates repo population; repos are filled via `git archive` (respects `.gitignore`). Repo creation + archive are operational `gh` steps gated by explicit verification.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `gh` CLI, `git`, `agent-toolkit-cli`.

---

## Pre-flight (do once, before any task)

- [ ] **Confirm clean baseline.** `cd ~/GitHub/projects/agent-toolkit-cli && git status --short` (revert any spurious `uv.lock`). On `main`, up to date with origin.
- [ ] **Confirm no active agent sessions** (cmux-pm / aj-run panes) — `skill remove` unlinks projections before re-install recreates them; a live session would see skills vanish mid-run.
- [ ] **Confirm the old parent clones are safe to lose — there are TWO** (`skills` AND `skills@main`; every `ref=main` library canonical resolves through the latter, so any in-place skill edit lands in `skills@main`'s working tree). Check EACH:

```bash
for C in ~/.agent-toolkit/skills/_parents/ajanderson1/skills*; do
  echo "== $C =="
  git -C "$C" status --short
  git -C "$C" log --branches --not --remotes --oneline
done
```

`skills` must show ONLY `?? telegram-botfather/` (the known stray); `skills@main` must be fully clean with no unpushed commits. Anything else: STOP and rescue it first. The orphan sweep inside `skill remove` will `rm -rf` each clone the moment its last referencing slug is removed in Task 7 — silently destroying uncommitted work (`--force` bypasses the dirty-tree guard; this exact trap has bitten before). It also means Task 8 Step 2 is usually a no-op by then.
- [ ] **Test the pre-commit hook** (decide `--no-verify`): make a trivial no-op commit on a scratch branch. If the schema-check hook aborts it (known-broken: removed `--toolkit-repo` option), keep `--no-verify` on the commit steps below. If it passes, DROP `--no-verify` everywhere. Record which.
- [ ] **Snapshot every lock under `$HOME`** (rollback insurance — note: restores lock JSON only, NOT symlinks/clones):

```bash
mkdir -p /tmp/skills-split-backup
cp ~/.agent-toolkit/skills-lock.json /tmp/skills-split-backup/global-skills-lock.json
for f in $(find "$HOME" -name skills-lock.json 2>/dev/null | grep -v '/.worktrees/'); do
  cp "$f" "/tmp/skills-split-backup/$(echo "$f" | sed 's#/#_#g')"
done
ls /tmp/skills-split-backup
```

- [ ] **Confirm OWNED_OWNERS.** `grep -n OWNED_OWNERS src/agent_toolkit_cli/skill_ownership.py` → `frozenset({"ajanderson1"})`. If it ever loses `ajanderson1`, STOP — the no-CLI-change assumption is void.

---

## File Structure

| File | Responsibility |
|---|---|
| Create: `scripts/migrate_skills_split.py` | Pure logic (map, scope enumeration, action plan, unmapped-slug guard) + a real transactional `--apply` driver (Phase A then Phase B). |
| Create: `tests/test_cli/test_migrate_skills_split.py` | Unit tests for the pure logic against fixture locks (map completeness, `$HOME`-wide discovery, phase-ordered plan, idempotency, unmapped-slug guard). |
| Create (×8, on GitHub): `ajanderson1/skills-<category>` | Target repos, populated by operational tasks (sanitized, `git archive`, `.gitignore`). |
| Modify (skill content): `skill-builder`, `skills/AGENTS.md`, working-clone refs | Update hardcoded `ajanderson1/skills` build targets (Task 9, Step 5). |

Pure functions (testable, no I/O) + thin I/O wrappers (the live driver). Tests cover the pure functions + fixture-lock discovery; the live driver is exercised by the operational verification gates (Tasks 6–9).

---

## Task 1: Canonical map + counts + unmapped-slug guard

**Files:** Create `scripts/migrate_skills_split.py`, `tests/test_cli/test_migrate_skills_split.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_migrate_skills_split.py
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "migrate_skills_split",
    Path(__file__).parents[2] / "scripts" / "migrate_skills_split.py",
)
mss = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mss)


def test_map_covers_31_mapped_skills_exactly_once():
    placed = [slug for slugs in mss.CATEGORY_MAP.values() for slug in slugs]
    assert len(placed) == len(set(placed)), "a slug is placed in two repos"
    assert set(placed) == mss.MIGRATED_SLUGS
    assert len(mss.MIGRATED_SLUGS) == 31          # 31 tracked dirs
    assert not hasattr(mss, "DELETED_SLUGS")       # botfather is a local rm, not a repo op


def test_servers_is_an_alias_of_contexts_not_a_skill():
    # `servers` lock entries re-point to contexts in skills-infra (broken dup)
    assert mss.ALIAS_REMAP == {"servers": ("contexts", "skills-infra")}


def test_repo_for_slug_and_owner():
    assert mss.OWNER == "ajanderson1"
    assert mss.repo_for_slug("journal") == "skills-journal"
    assert all(r.startswith("skills-") for r in mss.CATEGORY_MAP)


def test_unmapped_slug_guard_lists_strays(tmp_path):
    lock = tmp_path / "skills-lock.json"
    lock.write_text(
        '{"version":1,"skills":{'
        '"journal":{"source":"ajanderson1/skills","skillPath":"journal"},'
        '"servers":{"source":"ajanderson1/skills","skillPath":"servers"},'
        '"newthing":{"source":"ajanderson1/skills","skillPath":"newthing"}}}'
    )
    strays = mss.unmapped_first_party_slugs([lock])
    assert strays == {"newthing"}   # journal mapped, servers is a known alias, newthing is a stray
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/GitHub/projects/agent-toolkit-cli && uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: FAIL — module/symbols not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/migrate_skills_split.py
"""Migrate ajanderson1/skills (flat monorepo) into 8 category repos.

Drives shipped agent-toolkit-cli verbs in two ordered phases. No CLI source change.
Phase A = global library (skill remove/add — global-only). Phase B = project scopes
(skill uninstall -p / install -p — re-derive from global). Idempotent + dry-runnable +
transactional --apply. See docs/superpowers/specs/2026-06-10-skills-split-into-category-repos-design.md
"""
from __future__ import annotations
import json
from pathlib import Path

OWNER = "ajanderson1"
SOURCE_REPO = "ajanderson1/skills"

CATEGORY_MAP: dict[str, list[str]] = {
    "skills-workflow": [
        "aj-flow", "aj-issue", "aj-run", "aj-bootstrap",
        "autonomous-run", "project-manager", "repo-recon",
    ],
    "skills-orchestration": ["cmux-pm", "claude-orchestrated-pi-agents"],
    "skills-authoring": ["agent-builder", "skill-builder", "conventions"],
    "skills-journal": ["journal", "journal-maintenance", "learn-for-me", "obsidian"],
    "skills-finance": ["outgoings-admin", "pocketsmith", "bank-statement-download"],
    "skills-infra": [
        "contexts", "dev-server", "kuma-uptime", "domain-manager",
        "mkdocs", "pypi", "bitwarden",
    ],
    "skills-comms": ["telegram", "whatsapp-backup"],
    "skills-android": ["android-driver", "apk-deep-audit", "apk-workbench"],
}

MIGRATED_SLUGS: set[str] = {s for slugs in CATEGORY_MAP.values() for s in slugs}

# `servers` is a broken same-subtree dup of `contexts` (no servers/ dir exists).
# Re-point its lock entries to contexts in skills-infra, keeping local slug `servers`.
ALIAS_REMAP: dict[str, tuple[str, str]] = {"servers": ("contexts", "skills-infra")}


def repo_for_slug(slug: str) -> str:
    for repo, slugs in CATEGORY_MAP.items():
        if slug in slugs:
            return repo
    raise KeyError(f"{slug} is not in the category map")


def _first_party_slugs(lock_paths: list[Path]) -> set[str]:
    found: set[str] = set()
    for lock in lock_paths:
        data = json.loads(lock.read_text())   # fail loud on parse error
        for slug, e in data.get("skills", {}).items():
            if e.get("source") == SOURCE_REPO:
                found.add(slug)
    return found


def unmapped_first_party_slugs(lock_paths: list[Path]) -> set[str]:
    """First-party slugs registered against the old source that are neither mapped
    nor a known alias — these would be silently stranded. Caller must fail loud."""
    return _first_party_slugs(lock_paths) - MIGRATED_SLUGS - set(ALIAS_REMAP)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): map + alias remap + unmapped-slug guard (#341)

Device: $(hostname -s)"
```

---

## Task 2: `$HOME`-wide lock discovery (fail-loud, worktree-excluded)

**Files:** Modify `scripts/migrate_skills_split.py`, test file

- [ ] **Step 1: Write the failing test**

```python
def test_discover_lock_paths_scans_home_excludes_worktrees(tmp_path):
    (tmp_path / "proj").mkdir()
    a = tmp_path / "proj" / "skills-lock.json"; a.write_text('{"skills":{}}')
    deep = tmp_path / "proj" / "sub" / "deep"; deep.mkdir(parents=True)
    b = deep / "skills-lock.json"; b.write_text('{"skills":{}}')
    wt = tmp_path / "proj" / ".worktrees" / "run-1"; wt.mkdir(parents=True)
    c = wt / "skills-lock.json"; c.write_text('{"skills":{}}')
    cache = tmp_path / ".cache" / "uv" / "git-v0" / "checkouts" / "abc"; cache.mkdir(parents=True)
    d = cache / "skills-lock.json"; d.write_text('{"skills":{}}')
    cwt = tmp_path / "proj" / ".claude" / "worktrees" / "feat-x"; cwt.mkdir(parents=True)
    e = cwt / "skills-lock.json"; e.write_text('{"skills":{}}')

    found = mss.discover_lock_paths([tmp_path])
    assert a in found and b in found
    assert c not in found, ".worktrees locks must be excluded"
    assert d not in found, ".cache locks (uv git checkouts) are disposable snapshots, not scopes"
    assert e not in found, ".claude/worktrees locks must be excluded"


def test_find_lock_scopes_filters_to_source_repo(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text(
        '{"skills":{'
        '"journal":{"source":"ajanderson1/skills","skillPath":"journal"},'
        '"grill-me":{"source":"mattpocock/skills","skillPath":"x"}}}'
    )
    assert mss.find_lock_scopes_for_slug("journal", lock_paths=[glob]) == [glob]
    assert mss.find_lock_scopes_for_slug("grill-me", lock_paths=[glob]) == []


def test_parse_error_fails_loud(tmp_path):
    bad = tmp_path / "skills-lock.json"; bad.write_text("{ not json")
    import pytest
    with pytest.raises(json.JSONDecodeError):
        mss.find_lock_scopes_for_slug("journal", lock_paths=[bad])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "discover or find_lock or parse_error" -v`
Expected: FAIL — functions not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
def discover_lock_paths(roots: list[Path]) -> list[Path]:
    """All skills-lock.json under roots (recursive), excluding .worktrees/,
    Claude-managed .claude/worktrees/, and cache trees (.cache — a live uv
    git-checkout under ~/.cache/uv/ holds an old-source lock snapshot; cache
    copies are disposable, not scopes to migrate).
    Global lock is passed explicitly by the caller, not discovered here."""
    found: list[Path] = []
    for root in roots:
        for p in sorted(root.rglob("skills-lock.json")):
            parts = p.parts
            if ".worktrees" in parts or ".cache" in parts:
                continue
            if ".claude" in parts and "worktrees" in parts:
                continue
            found.append(p)
    return found


def find_lock_scopes_for_slug(slug: str, *, lock_paths: list[Path]) -> list[Path]:
    """Locks where `slug` is registered against the OLD source. Fails loud on
    unparseable locks (no silent skip — see conventions: fail loudly)."""
    hits: list[Path] = []
    for lock in lock_paths:
        data = json.loads(lock.read_text())
        entry = data.get("skills", {}).get(slug)
        if entry and entry.get("source") == SOURCE_REPO:
            hits.append(lock)
    return hits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "discover or find_lock or parse_error" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): \$HOME-wide fail-loud lock discovery (#341)

Device: $(hostname -s)"
```

---

## Task 3: Phase-ordered action plan (global before project; idempotent)

**Files:** Modify `scripts/migrate_skills_split.py`, test file

- [ ] **Step 1: Write the failing test**

```python
def _fake_agents(slug, scope, lock):
    # injectable projection scanner: lock entries do NOT record agents (parked
    # #230) — live capture scans on-disk projection symlinks, tests stub it
    return ("claude",)


def test_action_plan_orders_global_before_project(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    proj = tmp_path / "p" / "skills-lock.json"; proj.parent.mkdir()
    proj.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')

    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[proj], projected_agents=_fake_agents)
    phases = [a.phase for a in plan]
    assert phases == sorted(phases), "all phase-A actions precede phase-B"
    a_verbs = [(a.verb, a.scope) for a in plan if a.phase == "A"]
    # remove -> add -> install: the trailing install restores the GLOBAL agent
    # projections that `skill remove --force` deletes and `skill add` does NOT
    # recreate (add only recreates the library dir + lock entry)
    assert a_verbs == [("remove", glob), ("add", glob), ("install", glob)]
    b_verbs = [(a.verb, a.scope, a.agents) for a in plan if a.phase == "B"]
    assert b_verbs == [("uninstall", proj, ("claude",)), ("install", proj, ("claude",))]
    assert all(a.new_source == "ajanderson1/skills-journal" for a in plan if a.verb in ("add", "install"))


def test_action_plan_noop_when_already_migrated(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    assert plan == []


def test_action_plan_project_only_slug_gets_prerequisite_global_add(tmp_path):
    # apk-workbench shape: registered in project locks, ABSENT from the global
    # lock (live count: 30 global first-party slugs, not 31). Phase B install -p
    # re-derives from the global entry, so a prerequisite Phase A add is
    # mandatory (spec mandate) — without it, uninstall -p drops the project
    # entry and install -p raises "not in global library", stranding the slug.
    glob = tmp_path / "global-lock.json"; glob.write_text('{"skills":{}}')
    proj = tmp_path / "p" / "skills-lock.json"; proj.parent.mkdir()
    proj.write_text('{"skills":{"apk-workbench":{"source":"ajanderson1/skills","skillPath":"apk-workbench"}}}')
    plan = mss.build_action_plan(slugs=["apk-workbench"], global_lock=glob,
                                 project_locks=[proj], projected_agents=_fake_agents)
    a_verbs = [a.verb for a in plan if a.phase == "A"]
    assert a_verbs == ["add"], "no remove (nothing registered), but the prerequisite add MUST be planned"


def test_action_plan_recovers_stranded_slug_after_failed_add(tmp_path):
    # mid-apply abort state: remove succeeded, add failed -> slug on NO source.
    # Re-run must re-emit the add, not silently skip the slug (an old-source-only
    # predicate would make a stranded slug vanish from the plan forever).
    glob = tmp_path / "global-lock.json"; glob.write_text('{"skills":{}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    assert [(a.phase, a.verb) for a in plan] == [("A", "add")]


def test_projected_agents_collapses_bundle_to_universal_token(tmp_path):
    # the captured list is fed straight into `--agents`, and _resolve_agents
    # (commands/skill/__init__.py) hard-rejects synthetic catalog names
    # ("general-skill"/"general-agent", which share skills_dir .agents/skills)
    # — a universal-bundle link must surface as the literal "universal" token
    # (accepted first-class) and the synthetics must NEVER appear
    proj = tmp_path / "p"
    lock = proj / "skills-lock.json"
    bundle = proj / ".agents" / "skills"; bundle.mkdir(parents=True)
    canon = proj / ".canonical-journal"; canon.mkdir()
    (bundle / "journal").symlink_to(canon)
    lock.write_text('{"skills":{}}')
    agents = mss.projected_agents("journal", "project", lock)
    assert "universal" in agents
    assert not {"general-skill", "general-agent"} & set(agents)


def test_action_plan_flags_projectionless_scope_for_manual_decision(tmp_path):
    # live state: several project locks (whatsapp_sync et al.) hold old-source
    # entries with ZERO projection symlinks. A planned uninstall/install pair
    # would let `uninstall -p` destroy the lock entry BEFORE any empty-agents
    # guard fires, and the journal would replay the doomed install forever.
    # Plan a needs-decision marker instead; main() blocks --apply on these.
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}')
    proj = tmp_path / "p" / "skills-lock.json"; proj.parent.mkdir()
    proj.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[proj],
                                 projected_agents=lambda *a: ())
    assert [(a.phase, a.verb) for a in plan] == [("B", "needs-decision")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "action_plan or projected_agents" -v`
Expected: FAIL — `Action`/`build_action_plan` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Action:
    phase: str            # "A" (global) | "B" (project)
    verb: str             # remove | add | install | uninstall | needs-decision
    slug: str
    scope: Path
    new_source: str | None = None
    agents: tuple[str, ...] = field(default_factory=tuple)


def projected_agents(slug: str, scope: str, lock: Path) -> tuple[str, ...]:
    """Agent TOKENS (as accepted by `--agents`) whose on-disk projection
    symlink for `slug` exists at this scope.

    Lock entries do NOT record agents (LockEntry has no such field — parked
    #230), so the symlinks are the only source of truth. NOTE this is NOT a
    straight copy of remove_cmd's will_delete loop: that loop only enumerates
    paths to DELETE, so synthetic catalog names are harmless there — but THIS
    list is fed back into `--agents`, and _resolve_agents
    (commands/skill/__init__.py) hard-rejects synthetics like "general-skill".
    Two rules:
      1. skip ALL synthetic catalog entries, not just "universal";
      2. a universal-bundle link surfaces as the literal "universal" token —
         the only token that restores the bundle BY DESIGN (real agents like
         dexto sharing .agents/skills restore it only by coincidence) — and
         agents whose projection dir IS the bundle path collapse into it.
    """
    from agent_toolkit_cli.skill_paths import AGENTS, agent_projection_dir

    synthetic = {"universal", "general-skill", "general-agent"}
    project = None if scope == "global" else lock.parent
    bundle = agent_projection_dir("universal", slug, scope=scope, home=None, project=project)
    found: list[str] = []
    if bundle.is_symlink():
        found.append("universal")
    for name in AGENTS:
        if name in synthetic:
            continue
        link = agent_projection_dir(name, slug, scope=scope, home=None, project=project)
        if link.is_symlink() and link != bundle:
            found.append(name)
    return tuple(dict.fromkeys(found))


def _global_entry(global_lock: Path, slug: str) -> dict | None:
    return json.loads(global_lock.read_text()).get("skills", {}).get(slug)


def build_action_plan(
    *, slugs: list[str], global_lock: Path, project_locks: list[Path],
    projected_agents: Callable[[str, str, Path], tuple[str, ...]] = projected_agents,
) -> list[Action]:
    """Phase A (global) for every slug FIRST, then Phase B (project).

    Global rule per slug: entry on NEW source -> no-op; entry on OLD source ->
    remove+add+install (the install restores the agent projections `remove
    --force` deletes and `add` does not recreate); entry MISSING -> prerequisite
    add (covers project-only slugs like apk-workbench AND the remove-succeeded/
    add-failed stranded state, so re-runs self-heal instead of skipping)."""
    a: list[Action] = []
    b: list[Action] = []
    for slug in slugs:
        new_source = f"{OWNER}/{repo_for_slug(slug)}"
        entry = _global_entry(global_lock, slug)
        if entry is None:
            a += [Action("A", "add", slug, global_lock, new_source)]
        elif entry.get("source") == SOURCE_REPO:
            agents = projected_agents(slug, "global", global_lock)
            a += [Action("A", "remove", slug, global_lock),
                  Action("A", "add", slug, global_lock, new_source)]
            if agents:
                a += [Action("A", "install", slug, global_lock, new_source, agents=agents)]
        for scope in find_lock_scopes_for_slug(slug, lock_paths=project_locks):
            agents = projected_agents(slug, "project", scope)
            if not agents:
                # projection-less old-source entry (live: whatsapp_sync et al.):
                # an uninstall/install pair would let `uninstall -p` destroy the
                # lock entry BEFORE any empty-agents guard can fire. Plan a
                # needs-decision marker instead; main() blocks --apply on these.
                b += [Action("B", "needs-decision", slug, scope)]
                continue
            b += [Action("B", "uninstall", slug, scope, agents=agents),
                  Action("B", "install", slug, scope, new_source, agents=agents)]
    return a + b
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "action_plan or projected_agents" -v`
Expected: PASS (all six).

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): phase-ordered idempotent action plan (#341)

Device: $(hostname -s)"
```

---

## Task 4: Security pre-copy scan gate

**Files:** Modify `scripts/migrate_skills_split.py`, test file

- [ ] **Step 1: Write the failing test**

```python
def test_secret_scan_flags_credential_files_and_uuids(tmp_path):
    skill = tmp_path / "bank-statement-download" / "references"; skill.mkdir(parents=True)
    (skill / "credentials.md").write_text(
        "N26 vault item: 3f2a9c14-1b2d-4e6a-9f01-aabbccddeeff\nacct 51412937\n"
    )
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "SKILL.md").write_text("name: journal\n")

    hits = mss.scan_for_secrets(tmp_path)
    files = {str(h.relative_to(tmp_path)) for h in hits}
    assert "bank-statement-download/references/credentials.md" in files
    assert not any("journal" in f for f in files)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k secret_scan -v`
Expected: FAIL — `scan_for_secrets` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
import re

_SECRET_NAME_RE = re.compile(r"(credentials|learnings)\.md$", re.I)
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def scan_for_secrets(skill_tree: Path) -> list[Path]:
    """Files that match secret-bearing names OR contain a UUID (Bitwarden item id
    shape). The migration MUST halt for human review on any hit before publishing."""
    hits: list[Path] = []
    for f in skill_tree.rglob("*"):
        if not f.is_file():
            continue
        if _SECRET_NAME_RE.search(f.name):
            hits.append(f); continue
        try:
            if _UUID_RE.search(f.read_text(errors="ignore")):
                hits.append(f)
        except OSError:
            pass
    return sorted(set(hits))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k secret_scan -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): pre-copy secret scan gate (#341)

Device: $(hostname -s)"
```

---

## Task 5: CLI entry point — dry-run default, transactional `--apply`

**Files:** Modify `scripts/migrate_skills_split.py`, test file

- [ ] **Step 1: Write the failing test**

```python
def test_render_plan_groups_by_phase(tmp_path, capsys):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    mss.render_plan(plan)
    out = capsys.readouterr().out
    assert "Phase A" in out and "remove journal" in out and "ajanderson1/skills-journal" in out


def test_main_dryrun_fails_loud_on_unmapped(tmp_path, monkeypatch, capsys):
    # an unmapped first-party slug must abort the dry-run, not be skipped
    glob = tmp_path / "skills-lock.json"
    glob.write_text('{"skills":{"newthing":{"source":"ajanderson1/skills","skillPath":"newthing"}}}')
    import pytest
    with pytest.raises(SystemExit):
        mss.main(["--global-lock", str(glob), "--roots", str(tmp_path)])
    assert "unmapped" in capsys.readouterr().out.lower()


def test_main_excludes_global_lock_from_project_scopes(tmp_path, monkeypatch, capsys):
    # ~/.agent-toolkit/skills-lock.json matches the $HOME rglob; treating it as
    # a project scope would have Phase B `uninstall -p` (cwd=~/.agent-toolkit)
    # strip the just-migrated GLOBAL entries, then `install -p` fail and strand
    # hermetic: stub the scanner + journal so this never reads real $HOME state
    # (a real mid-migration journal would inject phantom Phase B rows and
    # spuriously fail the "Phase B" assertion below)
    monkeypatch.setattr(mss, "projected_agents", _fake_agents)
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    glob = tmp_path / ".agent-toolkit" / "skills-lock.json"; glob.parent.mkdir()
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    mss.main(["--global-lock", str(glob), "--roots", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Phase B" not in out, "global lock must never appear as a Phase B scope"


def test_journal_pending_installs_reemits_unpaired_uninstall(tmp_path, monkeypatch):
    # crash/abort between Phase B uninstall and install drops the project lock
    # entry — without the journal, re-run planning (which keys on lock entries)
    # would silently strand that project scope
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    mss._journal_append({"event": "uninstalled", "slug": "journal",
                         "scope": str(tmp_path / "p" / "skills-lock.json"),
                         "agents": ["claude"]})
    pending = mss.journal_pending_installs()
    assert [(x.verb, x.slug, x.agents) for x in pending] == [("install", "journal", ("claude",))]


def test_journal_pending_installs_skips_empty_agents(tmp_path, monkeypatch, capsys):
    # a journaled uninstall with agents=[] must NOT be replayed as a live
    # install — it would hit the empty-agents refusal on every re-run (an
    # infinite abort loop fixable only by hand-editing the journal). Skip it
    # loudly and leave the scope for manual re-install.
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    mss._journal_append({"event": "uninstalled", "slug": "journal",
                         "scope": str(tmp_path / "p" / "skills-lock.json"),
                         "agents": []})
    assert mss.journal_pending_installs() == []
    assert "manual re-install required" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "render_plan or dryrun or excludes_global or journal" -v`
Expected: FAIL — `render_plan`/`main`/`JOURNAL` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
import argparse
import os
import subprocess


def render_plan(plan: list[Action]) -> None:
    if not plan:
        print("nothing to do (all scopes already migrated)"); return
    for ph in ("A", "B"):
        rows = [a for a in plan if a.phase == ph]
        if not rows:
            continue
        print(f"Phase {ph} ({'global library' if ph=='A' else 'project scopes'}):")
        for a in rows:
            tail = f" -> {a.new_source}" if a.new_source else ""
            ag = f" [agents={','.join(a.agents)}]" if a.agents else ""
            print(f"  {a.verb} {a.slug} @ {a.scope}{tail}{ag}")
    print(f"\n{len(plan)} actions, {len({a.scope for a in plan})} locks, {len({a.slug for a in plan})} skills")


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)   # fail loud — non-zero raises


# Phase B crash journal: a crash/abort between uninstall -p and install -p drops
# the project lock entry, and re-run planning keys on lock entries — without a
# journal that scope would be silently stranded. Lives OUTSIDE /tmp on purpose.
JOURNAL = Path(os.path.expanduser("~/.agent-toolkit/skills-split-journal.jsonl"))


def _journal_append(event: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a") as f:
        f.write(json.dumps(event) + "\n")


def journal_pending_installs() -> list[Action]:
    """Phase B uninstalls whose paired install never completed — re-emitted on
    re-run so no project scope is stranded by a crash window."""
    if not JOURNAL.exists():
        return []
    done: set[tuple[str, str]] = set()
    started: dict[tuple[str, str], dict] = {}
    for line in JOURNAL.read_text().splitlines():
        e = json.loads(line)
        key = (e["slug"], e["scope"])
        if e["event"] == "uninstalled":
            started[key] = e
        elif e["event"] == "installed":
            done.add(key)
    pending: list[Action] = []
    for key, e in started.items():
        if key in done:
            continue
        if not e.get("agents"):
            # never replay an empty-agents install — it would hit the refusal
            # in apply_action on every re-run (infinite abort loop)
            print(f"WARN: skipping journaled install for {e['slug']} @ {e['scope']}: "
                  f"no agents recorded — manual re-install required")
            continue
        pending.append(Action("B", "install", e["slug"], Path(e["scope"]),
                              f"{OWNER}/{repo_for_slug(e['slug'])}", tuple(e["agents"])))
    return pending


def apply_action(a: Action) -> None:
    """Execute one action via the shipped CLI. Rollback on failure is handled
    by the caller via _rollback() — see main()."""
    if a.phase == "A" and a.verb == "remove":
        _run(["agent-toolkit-cli", "skill", "remove", a.slug, "--force"])
    elif a.phase == "A" and a.verb == "add":
        _run(["agent-toolkit-cli", "skill", "add",
              f"{a.new_source}/{a.slug}", "--owned", "--ref", "main"])
    elif a.phase == "A" and a.verb == "install":
        # restore the GLOBAL agent projections deleted by `remove --force`
        # (`skill add` recreates only the library dir + lock entry, NOT the
        # ~/.claude/skills/<slug> etc. symlinks; doctor can't detect the gap — #230)
        _run(["agent-toolkit-cli", "skill", "install", a.slug,
              "--scope", "global", "--agents", ",".join(a.agents)])
    elif a.phase == "B" and a.verb == "uninstall":
        _journal_append({"event": "uninstalled", "slug": a.slug,
                         "scope": str(a.scope), "agents": list(a.agents)})
        _run(["agent-toolkit-cli", "skill", "uninstall", a.slug, "-p", "--agents", "all"],
             cwd=a.scope.parent)
    elif a.phase == "B" and a.verb == "install":
        # uninstall -p preserves the project canonical, and ensure_project_canonical
        # links only "if absent" (skill_install.py) — purge a canonical still
        # resolving into the OLD monorepo cache so install re-derives from the
        # new source instead of freezing content against the soon-archived repo
        from agent_toolkit_cli.skill_paths import canonical_skill_dir
        stale = canonical_skill_dir(a.slug, scope="project", project=a.scope.parent)
        if stale.is_symlink():
            target = str(stale.resolve())
            if "/_parents/ajanderson1/skills/" in target or "/_parents/ajanderson1/skills@" in target:
                stale.unlink()
        if not a.agents:
            raise RuntimeError(
                f"{a.slug} @ {a.scope}: no prior agent projections found — refusing "
                f"to default to --agents all (known over-install trap); investigate")
        _run(["agent-toolkit-cli", "skill", "install", a.slug, "-p",
              "--agents", ",".join(a.agents)], cwd=a.scope.parent)
        _journal_append({"event": "installed", "slug": a.slug, "scope": str(a.scope)})


def _rollback(failed: Action) -> None:
    """Spec mandate: on failure re-add the old source and abort, so no slug is
    left registered nowhere. The old repo is still live (archive is Task 9, last).
    Even if this rollback ALSO fails, re-run planning self-heals: a missing
    global entry replans as an add (see build_action_plan)."""
    if failed.phase == "A" and failed.verb == "add":
        try:
            _run(["agent-toolkit-cli", "skill", "add",
                  f"{SOURCE_REPO}/{failed.slug}", "--owned", "--ref", "main"])
        except subprocess.CalledProcessError:
            print(f"rollback re-add failed for {failed.slug} — safe: re-run "
                  f"replans the missing entry as an add to the new source")
    # A-remove failed: nothing changed. A-install / B-install failed: lock entry
    # exists (journal re-emits B installs). B-uninstall failed: entry intact.


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Split ajanderson1/skills into category repos")
    p.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    p.add_argument("--global-lock", default=os.path.expanduser("~/.agent-toolkit/skills-lock.json"))
    p.add_argument("--roots", nargs="*", default=[os.path.expanduser("~")])
    args = p.parse_args(argv)

    global_lock = Path(args.global_lock)
    # the global lock matches the $HOME rglob — it must NEVER be a project scope
    # (Phase B against cwd=~/.agent-toolkit would strip just-migrated entries)
    project_locks = [
        pl for pl in discover_lock_paths([Path(r) for r in args.roots])
        if pl.resolve() != global_lock.resolve()
    ]

    strays = mss_unmapped(project_locks + [global_lock])
    if strays:
        print(f"ABORT: unmapped first-party slugs would be stranded: {sorted(strays)}")
        raise SystemExit(2)

    plan = build_action_plan(
        slugs=sorted(MIGRATED_SLUGS), global_lock=global_lock,
        project_locks=project_locks,
        # pass the module-level scanner EXPLICITLY: a def-time keyword default
        # binds the original function object, so tests monkeypatching
        # mss.projected_agents would silently not take effect through main()
        projected_agents=projected_agents,
    )
    seen = {(x.slug, str(x.scope)) for x in plan}
    plan += [x for x in journal_pending_installs() if (x.slug, str(x.scope)) not in seen]
    render_plan(plan)
    undecided = [x for x in plan if x.verb == "needs-decision"]
    if undecided:
        print("\nNEEDS MANUAL DECISION (projection-less old-source entries — choose an")
        print("agent set or drop the lock entry by hand, then re-run):")
        for x in undecided:
            print(f"  {x.slug} @ {x.scope}")
    if not args.apply:
        print("\n(dry-run; pass --apply to execute)")
        return 0
    if undecided:
        print("ABORT: unresolved needs-decision scopes above — nothing was changed.")
        raise SystemExit(3)
    for a in plan:
        try:
            apply_action(a)
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            _rollback(a)
            print(f"FAILED at {a.verb} {a.slug} @ {a.scope}: {exc}. "
                  f"Rolled back to a re-runnable state; aborting. Fix the cause and "
                  f"re-run — planning self-heals (missing global entry -> add; "
                  f"journaled unpaired uninstalls -> re-emitted installs).")
            raise SystemExit(1) from exc
    return 0


# local alias so main() reads cleanly
mss_unmapped = unmapped_first_party_slugs

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: PASS (all). Confirm the full new test file is green.

- [ ] **Step 5: Dry-run against LIVE locks (read-only)**

Run: `uv run python scripts/migrate_skills_split.py`
Expected: prints Phase A (global: remove+add+install triples for the **30** slugs currently registered globally, plus a bare prerequisite `add` for project-only slugs — e.g. `apk-workbench`, which lives only in the 3 APK project locks; 31 mapped total) + Phase B (project scopes); **no unmapped-slug ABORT** (servers is a known alias, handled separately in Task 7); ends "(dry-run...)". **Eyeball scope count vs the spec's lock table (incl. `~/Journal`), and confirm `~/.agent-toolkit/skills-lock.json` does NOT appear as a Phase B scope.** Expect a **NEEDS MANUAL DECISION** list of projection-less scopes (live examples: `whatsapp_sync`, `ryanair_fares`, `Scottish_Property_Analysis`, `~/GitHub/contexts/servers` (domain-manager/kuma-uptime), this repo's own committed lock) — resolve each by hand BEFORE `--apply` (choose an agent set and install, or drop the entry; dropping is right for disposable/archived checkouts). The uv-cache lock must be absent thanks to the `.cache` exclusion. No files changed.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): transactional --apply + fail-loud unmapped guard (#341)

Device: $(hostname -s)"
```

---

## Task 6: Create + populate the 8 target repos (operational, SANITIZED)

**Files:** GitHub (creates 8 repos). Uses `git archive` (respects `.gitignore`) + security scan.

- [ ] **Step 1: Scratch-clone source + run the secret scan FIRST (gate)**

```bash
SRC=/tmp/skills-split-src
rm -rf "$SRC" && git clone git@github.com:ajanderson1/skills.git "$SRC"
uv run python -c "
from pathlib import Path; import importlib.util
s=importlib.util.spec_from_file_location('m','scripts/migrate_skills_split.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
hits=m.scan_for_secrets(Path('$SRC'))
print('SECRET-BEARING FILES (review before publishing):')
[print(' ', h) for h in hits]
"
```

**STOP.** Expect THREE hits at current source HEAD: `bank-statement-download/references/credentials.md` and `bank-statement-download/references/learnings.md` (live vault UUIDs/account numbers — move them into Bitwarden FIRST), plus `whatsapp-backup/references/learnings.md` (filename-rule hit only — verified to contain no UUIDs; no Bitwarden step, but it must still be renamed/removed or this gate and Step 4 flag it forever). A different hit set than these three: investigate before proceeding. For each hit: `git rm` the file from the source repo entirely, folding any non-secret instructions into the skill's SKILL.md or a differently-named reference file. (In-place sanitization cannot pass this gate: `scan_for_secrets` flags these FILENAMES unconditionally, so a sanitized `credentials.md` re-flags forever — and Task 6 Step 4 would fire LEAK on it too.) Commit to the **source** repo and push (fixes the existing exposure at HEAD), then refresh the scratch clone and re-scan until clean:

```bash
git -C "$SRC" pull --ff-only   # $SRC was cloned BEFORE sanitization — without this,
                               # Step 2's `git archive HEAD` exports the PRE-sanitization
                               # tree, credentials included
# re-run the scan block above — MUST print zero hits before Step 2
```

- [ ] **Step 2: For EACH category — create private, populate via `git archive`, add `.gitignore`, push**

```bash
CAT=skills-journal
SLUGS="journal journal-maintenance learn-for-me obsidian"

gh repo create "ajanderson1/$CAT" --private --description "AJ skills: ${CAT#skills-}"
DST=/tmp/$CAT && rm -rf "$DST" && git init "$DST"
# copy only TRACKED files (git archive respects .gitignore; no __pycache__/.pyc/.DS_Store)
for s in $SLUGS; do
  ( cd "$SRC" && git archive HEAD -- "$s" ) | tar -x -C "$DST"
done
cd "$DST"
git remote add origin "git@github.com:ajanderson1/$CAT.git"
# .gitignore (NEW — source .gitignore not auto-carried). NOTE: '**/' prefix is
# required — a root-anchored 'references/credentials.md' would NOT match
# <skill>/references/credentials.md (gitignore patterns with a slash anchor to root)
printf '__pycache__/\n*.pyc\n.DS_Store\n**/references/credentials.md\n**/references/learnings.md\n' > .gitignore
# verbatim scaffold. scripts/validate-skill.sh MUST ride along: lefthook.yml
# invokes it under `set -e`, so the first hooked commit in skills-workflow
# would otherwise fail on a missing script (inert in repos whose guarded
# skill dirs don't exist)
for f in LICENSE lefthook.yml scripts/validate-skill.sh release-please-config.json .github/workflows/release-please.yml; do
  mkdir -p "$(dirname "$f")"; ( cd "$SRC" && git archive HEAD -- "$f" 2>/dev/null ) | tar -x -C "$DST" 2>/dev/null || true
done
# per-repo release-please config: set package-name + deterministic version (0.0.0)
python3 - "$CAT" <<'PY'
import json, sys
cfg=json.load(open("release-please-config.json"))
cfg["packages"]["."]["package-name"]=sys.argv[1]
json.dump(cfg, open("release-please-config.json","w"), indent=2)
json.dump({".":"0.0.0"}, open(".release-please-manifest.json","w"))
PY
echo "0.0.0" > version.txt
# regenerated README + AGENTS (templated, NOT hand-trimmed)
printf '# %s\n\nAJ first-party skills (split from ajanderson1/skills): %s\n' "$CAT" "$SLUGS" > README.md
printf '# AGENTS\n\nCategory repo `%s`. Skills: %s.\nResolution: ~/.agent-toolkit/skills/_parents/ajanderson1/%s/<slug>\n' "$CAT" "$SLUGS" "$CAT" > AGENTS.md

git add -A && git commit --no-verify -m "feat: initial $CAT (split from ajanderson1/skills) (#341)

Device: $(hostname -s)"
git branch -M main && git push -u origin main
cd -
```

Repeat for all 8 (slug lists from the spec map). `git archive` exports every file **tracked at source HEAD** — it guarantees no untracked `.pyc`/`.DS_Store`, but credential safety depends ENTIRELY on the Step 1 gate having passed (files `git rm`'d at source HEAD) and `$SRC` reflecting that HEAD (the `pull --ff-only` above). The destination `.gitignore` only prevents future accidental re-tracking; it does NOT filter what `git archive` exports.

- [ ] **Step 3: Verify each repo — SKILL.md count AND visibility**

```bash
# NB: flat CAT:N pairs, not `declare -A` — associative arrays are invalid in
# macOS /bin/bash 3.2 and `"${!want[@]}"` is a bad substitution in zsh; this
# gate guards PRIVATE visibility and must not fail open on a shell error
for PAIR in skills-workflow:7 skills-orchestration:2 skills-authoring:3 \
            skills-journal:4 skills-finance:3 skills-infra:7 skills-comms:2 skills-android:3; do
  CAT=${PAIR%%:*}; WANT=${PAIR##*:}
  n=$(gh api "repos/ajanderson1/$CAT/git/trees/main?recursive=1" \
        -q '[.tree[].path|select(endswith("SKILL.md"))]|length' 2>/dev/null)
  v=$(gh repo view "ajanderson1/$CAT" --json visibility -q .visibility 2>/dev/null)
  ok="ok"; [ "$n" = "$WANT" ] || ok="WRONG COUNT (want $WANT)"; [ "$v" = "PRIVATE" ] || ok="$ok / NOT PRIVATE"
  echo "$CAT: $n SKILL.md, $v -> $ok"
done
```

Expected: every line `ok`. **STOP and fix any WRONG/NOT PRIVATE.**

- [ ] **Step 4: Confirm no secret-bearing file leaked into any new repo**

```bash
# ALL 8 repos — a Step 1 false-negative could leak into any category, not just
# the three with known credential history. FAIL-LOUD: an API/auth/network error
# must STOP the gate, never read as "clean" (no 2>/dev/null, no `|| true`).
LEAKS=0
for CAT in skills-workflow skills-orchestration skills-authoring skills-journal \
           skills-finance skills-infra skills-comms skills-android; do
  out=$(gh api "repos/ajanderson1/$CAT/git/trees/main?recursive=1" \
          -q '[.tree[].path|select(test("credentials\\.md|learnings\\.md"))]|join("\n")') \
    || { echo "API ERROR for $CAT — gate did NOT run; STOP"; exit 1; }
  [ -z "$out" ] || { echo "LEAK in $CAT: $out"; LEAKS=1; }
done
[ "$LEAKS" = 0 ] && echo "all 8 repos verified clean" || { echo "STOP: fix the leaks above"; exit 1; }
```

*(Branch protection: NOT applied — unavailable on free-tier private repos, accepted risk per spec. Convention: never force-push main; PRs only.)*

---

## Task 7: Apply the re-registration (Phase A then Phase B) + servers alias

**Files:** global lock + ~13 project locks (incl. `~/Journal`); agent projections re-created.

- [ ] **Step 1: Final dry-run, eyeball Phase A/B, then apply**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
uv run python scripts/migrate_skills_split.py            # dry-run; confirm phases + scope count
uv run python scripts/migrate_skills_split.py --apply    # transactional; aborts on first failure
```

- [ ] **Step 1b: Assert project canonicals re-derived from the NEW source** (the stale-canonical purge in `apply_action` must have worked — `uninstall -p` preserves canonicals and `ensure_project_canonical` links only "if absent", so without the purge every project would keep resolving through the old monorepo cache, frozen dead once Task 9.7 archives it)

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
from agent_toolkit_cli.skill_paths import canonical_skill_dir
glob = Path(os.path.expanduser("~/.agent-toolkit/skills-lock.json"))
bad = []
for L in Path(os.path.expanduser("~")).rglob("skills-lock.json"):
    if (".worktrees" in L.parts or ".cache" in L.parts
            or (".claude" in L.parts and "worktrees" in L.parts) or L == glob):
        continue
    for slug, e in json.loads(L.read_text()).get("skills", {}).items():
        if not e.get("source", "").startswith("ajanderson1/skills-"):
            continue
        c = canonical_skill_dir(slug, scope="project", project=L.parent)
        t = str(c.resolve()) if c.is_symlink() else ""
        if "/_parents/ajanderson1/skills/" in t or "/_parents/ajanderson1/skills@" in t:
            bad.append((str(L), slug, t))
print("STALE canonicals (still resolving into the OLD monorepo cache):", bad or "NONE")
PY
```

Expected: `NONE`. **STOP on any hit** — those projects' content would silently freeze against the archived repo.

- [ ] **Step 2: Re-point the broken `servers` alias** (not in MIGRATED_SLUGS — handled explicitly)

```bash
# 1) register the alias in the GLOBAL library — `skill add` has --slug;
#    `skill install` does NOT (verified: install_cmd takes only slug/--agents/--scope/-p)
agent-toolkit-cli skill add ajanderson1/skills-infra/contexts --slug servers --owned --ref main
# 2) re-derive in EVERY project lock that registers `servers` — discovered from
#    the lock scan, NOT hardcoded (a missed consumer would otherwise surface only
#    at the Task 8 gate). Per project: capture prior agents with the script's
#    scanner BEFORE uninstall (NOT `--agents all` on install — the known
#    over-install trap; `all` expands to every detected agent on the machine),
#    purge a stale canonical (same predicate as apply_action), then re-derive.
uv run python - <<'PY'
import os, subprocess
from pathlib import Path
import importlib.util
s = importlib.util.spec_from_file_location("m", "scripts/migrate_skills_split.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
from agent_toolkit_cli.skill_paths import canonical_skill_dir
glob = Path(os.path.expanduser("~/.agent-toolkit/skills-lock.json"))
locks = [L for L in m.discover_lock_paths([Path(os.path.expanduser("~"))])
         if L.resolve() != glob.resolve()]
for L in m.find_lock_scopes_for_slug("servers", lock_paths=locks):
    proj = L.parent
    agents = m.projected_agents("servers", "project", L)   # capture BEFORE uninstall
    if not agents:
        raise SystemExit(f"STOP: {proj} registers servers with NO projections — "
                         f"choose its agent set deliberately, install by hand, re-run")
    stale = canonical_skill_dir("servers", scope="project", project=proj)
    t = str(stale.resolve()) if stale.is_symlink() else ""
    if "/_parents/ajanderson1/skills/" in t or "/_parents/ajanderson1/skills@" in t:
        stale.unlink()   # else content silently freezes on the soon-archived cache
    run = lambda *cmd: subprocess.run(cmd, cwd=proj, check=True)
    run("agent-toolkit-cli", "skill", "uninstall", "servers", "-p", "--agents", "all")
    run("agent-toolkit-cli", "skill", "install", "servers", "-p", "--agents", ",".join(agents))
    print(f"re-pointed servers @ {proj} [agents={','.join(agents)}]")
PY
```

*(Live note: review found zero `servers` projections at `~/GitHub/contexts/servers`, so expect its STOP — decide that project's intended agent set (its sibling consumer `~/GitHub/agent-toolkit/conventions` is the reference), run the uninstall/install pair by hand with the explicit list, then re-run the block.)*

- [ ] **Step 2b: Re-run the Step 1b stale-canonical assertion.** Step 1b ran BEFORE this step and filters on `ajanderson1/skills-*` sources, so the just-re-pointed `servers` entries were not covered by it. Re-run the Step 1b block now; expected `NONE` again.

- [ ] **Step 3: Re-run dry-run — must be a no-op**

Run: `uv run python scripts/migrate_skills_split.py`
Expected: `nothing to do (all scopes already migrated)`. (servers is no longer old-source.) Proves idempotency + full `$HOME`-wide coverage.

---

## Task 8: Verify all locks; remove local stray

- [ ] **Step 1: No lock under `$HOME` (excl. worktrees) still references the old repo**

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
locks=[Path(os.path.expanduser("~/.agent-toolkit/skills-lock.json"))]
locks+=[p for p in Path(os.path.expanduser("~")).rglob("skills-lock.json")
        if ".worktrees" not in p.parts and ".cache" not in p.parts
        and not (".claude" in p.parts and "worktrees" in p.parts)]
bad=[]
for L in locks:
    d=json.loads(L.read_text())   # fail loud
    for s,e in d.get("skills",{}).items():
        if e.get("source")=="ajanderson1/skills": bad.append((str(L),s))
print("LEFTOVER old-source entries:", bad or "NONE")
PY
```

Expected: `NONE`.

- [ ] **Step 2: Remove the local untracked `telegram-botfather` stray**

```bash
rm -rf ~/.agent-toolkit/skills/_parents/ajanderson1/skills/telegram-botfather
echo "removed local stray (was never tracked / never a lock entry)"
```

*(Usually already gone: the orphan sweep in `skill remove` rmtrees the whole parent clone when the last old-source slug is removed during Task 7 — that's why the pre-flight rescues anything valuable from this clone FIRST. `rm -rf` on a missing path exits 0 either way.)*

---

## Task 9: Resolution, doctor, push round-trip, releases; skill-content; archive

- [ ] **Step 1: `skill doctor` clean everywhere**

```bash
agent-toolkit-cli skill doctor -g
# exclusions: the GLOBAL lock dir (already covered by `doctor -g` above —
# cd'ing into ~/.agent-toolkit would scope-default doctor to project and audit
# all global entries against a phantom project store, deadlocking the STOP
# gate on spurious findings) + cache/worktree snapshots
for P in $(find "$HOME" -name skills-lock.json \
             -not -path '*/.worktrees/*' -not -path '*/.claude/worktrees/*' \
             -not -path '*/.cache/*' -not -path "$HOME/.agent-toolkit/*" \
             -exec dirname {} \;); do
  echo "== $P =="; ( cd "$P" && agent-toolkit-cli skill doctor )
done
```

Expected: zero findings for migrated slugs (incl. `servers` alias). **STOP and fix any finding.**

- [ ] **Step 2: One moved skill loads + applies in a fresh session** — start a NEW agent session (fresh cmux pane / fresh `claude`, NOT the session that ran the migration), invoke the `journal` skill, and confirm it loads. Then verify resolution on disk:

```bash
readlink -f ~/.claude/skills/journal   # must contain _parents/ajanderson1/skills-journal
```

Record the tested skill + resolved path in the Task 9 Step 8 commit body (e.g. `verified fresh load: journal <- ajanderson1/skills-journal`).

- [ ] **Step 3: `skill push` round-trips to the new repo**

```bash
agent-toolkit-cli skill push journal   # PR opened against ajanderson1/skills-journal
```

Close the test PR after confirming the target repo.

- [ ] **Step 4: release-please valid + deterministic first version — ALL 8 repos**

```bash
for CAT in skills-workflow skills-orchestration skills-authoring skills-journal \
           skills-finance skills-infra skills-comms skills-android; do
  gh api "repos/ajanderson1/$CAT/contents/.github/workflows/release-please.yml" -q .name >/dev/null 2>&1 \
    && echo "$CAT: workflow present" || echo "$CAT: WORKFLOW MISSING"
done
# after the initial feat: commit, a release-please PR should appear per repo:
gh pr list --repo ajanderson1/skills-journal
```

Expected: all 8 `workflow present`; release-please PR cuts a deterministic version (0.0.0→first). If a repo doesn't cut, investigate `bootstrap-sha`/`Release-As:` on the initial commit.

- [ ] **Step 5: Update skill-content monorepo references** (feasibility finding)

Two distinct kinds of update — don't conflate them:

1. **Mechanical search-replace (no judgment):** in `skills/AGENTS.md`, `cmux-pm/README.md`, and the working-clone refs in `contexts`, `journal`, `journal-maintenance`, `obsidian`, replace `ajanderson1/skills` / `_parents/ajanderson1/skills/` with each skill's owning category repo (`ajanderson1/skills-<category>` / `_parents/ajanderson1/skills-<category>@main/`, per `CATEGORY_MAP`).
2. **Content redesign (one judgment call):** `skill-builder` (SKILL.md + build-mode-phases) currently hardcodes the monorepo as its authoring target. Its updated content must PROMPT the author for which category repo a new skill belongs in (suggesting a default from the category topics) instead of assuming a single repo.

Commit + push each change into the skill's NEW category repo.

- [ ] **Step 6: Third-party + aj-workflow untouched**

```bash
agent-toolkit-cli skill doctor -g | grep -Ei "mattpocock|anthropics|aj-workflow" || echo "no findings against untouched skills"
```

- [ ] **Step 7: Archive the old monorepo** (LAST — only after all above pass)

```bash
gh repo archive ajanderson1/skills --yes
gh repo view ajanderson1/skills --json isArchived -q .isArchived   # -> true
```

- [ ] **Step 8: Final CLI suite green + migration record commit**

```bash
cd ~/GitHub/projects/agent-toolkit-cli && uv run pytest -q
git add scripts/migrate_skills_split.py
git commit --no-verify -m "chore(migrate): finalize skills repo split (#341)

8 category repos live; 31 skills re-registered (global + ~13 project locks);
servers alias re-pointed; secrets sanitized; telegram-botfather stray removed;
ajanderson1/skills archived.

Closes #341
Device: $(hostname -s)" || echo "nothing new to commit"
git push origin main
```

---

## Self-Review (completed inline)

- **Spec coverage:** every corrected-DoD item maps to a task — sanitize+scan (T4,T6.1,T6.4), private+visibility (T6.3), `git archive`/.gitignore (T6.2), Phase A global (T7.1), Phase B project via uninstall/install (T7.1), servers alias (T7.2), `$HOME`-wide no-leftover (T8.1), local stray rm (T8.2), doctor clean (T9.1), fresh-session load (T9.2), push round-trip (T9.3), all-8 release-please (T9.4), skill-content updates (T9.5), untouched (T9.6), archive (T9.7), suite + unmapped guard (T1,T9.8).
- **Mechanism correctness:** Phase A precedes Phase B (asserted T3); project scopes use `uninstall -p`/`install -p` (global-only `add`/`remove` bug fixed); Phase A triples `remove`+`add`+`install` restore global projections; missing global entries replan as prerequisite adds (project-only slugs + stranded-state self-heal); the global lock is excluded from Phase B discovery; stale project canonicals are purged before `install -p`; `--apply` is real + fail-loud + rollback-on-failure with a Phase B crash journal (T5), not a stub; projection scans emit only `--agents`-valid tokens (synthetic catalog names skipped, bundle links collapse to the literal `universal` token); projection-less scopes plan as `needs-decision` and block `--apply` BEFORE anything is destroyed (and the journal never replays empty-agents installs); cache + Claude-worktree lock snapshots are excluded at every discovery site (T2, T7.1b, T8.1, T9.1); `servers` consumers are discovered dynamically with prior-agent capture + canonical purge (T7.2, re-asserted T7.2b); BOTH parent clones (`skills`, `skills@main`) are gated pre-flight.
- **Placeholder scan:** operational `<slug>`/`$CAT` substitution loops over `CATEGORY_MAP`/the dry-run output — fully enumerated, no TODO.
- **Type consistency:** `Action(phase, verb, slug, scope, new_source, agents)`, `build_action_plan`, `find_lock_scopes_for_slug`, `discover_lock_paths`, `unmapped_first_party_slugs`, `scan_for_secrets`, `apply_action`, `CATEGORY_MAP`, `MIGRATED_SLUGS`, `ALIAS_REMAP` used consistently across Tasks 1–9 and tests.
- **Count integrity:** 31 mapped (= 31 tracked dirs), of which 30 are registered globally and ≥1 (`apk-workbench`) is project-only and gets a prerequisite global add; `servers` is an alias of `contexts` (not a 32nd skill); `telegram-botfather` is a local rm (no repo/lock op).

## Deferred / Open Questions

### From 2026-06-10 review

- **Archived source repo retains pre-sanitization git history** — Task 9 — Step 7: Archive the old monorepo (P2, security-lens, confidence 75)

  The plan sanitizes the HEAD of `ajanderson1/skills` and then archives the repo, but GitHub archive makes the repo read-only while preserving the entire git history — every prior commit containing `credentials.md`/`learnings.md` (real Bitwarden vault UUIDs, name/email/phone, bank account numbers) remains browseable via `git log`/`git show`/the web UI. Private visibility limits exposure to current collaborators, but a future visibility mistake or token compromise would expose the historical secrets without warning. Decide before Task 9 Step 7: run `git filter-repo` (or BFG) to expunge the two files from all history and force-push before archiving, or record an explicit accepted-risk note (private repo, sole collaborator) in the plan/spec.

  <!-- dedup-key: section="task 9 step 7 archive the old monorepo" title="archived source repo retains presanitization git history" evidence="original `ajanderson1/skills` is **archived** read-only after verification — history preserved, nothing resolves from it." -->

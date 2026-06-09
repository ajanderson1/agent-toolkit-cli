# Split `ajanderson1/skills` into category repos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the flat `ajanderson1/skills` monorepo into 8 independent private category repos, re-registering all 31 mapped skills across the global library + ~13 project locks (incl. `~/Journal`), sanitizing tracked secrets, re-pointing the broken `servers` alias, removing the local `telegram-botfather` stray, and archiving the old repo — with zero broken skills.

**Architecture:** A test-driven, idempotent, **transactional** Python migration script (`scripts/migrate_skills_split.py`) owns the deterministic logic AND a real `--apply` path that DRIVES the shipped `agent-toolkit-cli` verbs in two ordered phases — **Phase A global library** (`skill remove`/`add`, which are global-only), then **Phase B project scopes** (`skill uninstall -p`/`install -p`, which re-derive from the global lock). No CLI source change (ownership is owner-keyed via `OWNED_OWNERS={"ajanderson1"}`). A pre-copy security scan gates repo population; repos are filled via `git archive` (respects `.gitignore`). Repo creation + archive are operational `gh` steps gated by explicit verification.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `gh` CLI, `git`, `agent-toolkit-cli`.

---

## Pre-flight (do once, before any task)

- [ ] **Confirm clean baseline.** `cd ~/GitHub/projects/agent-toolkit-cli && git status --short` (revert any spurious `uv.lock`). On `main`, up to date with origin.
- [ ] **Confirm no active agent sessions** (cmux-pm / aj-run panes) — `skill remove` unlinks projections before re-install recreates them; a live session would see skills vanish mid-run.
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
| Modify (skill content): `skill-builder`, `skills/AGENTS.md`, working-clone refs | Update hardcoded `ajanderson1/skills` build targets (Task 10). |

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

    found = mss.discover_lock_paths([tmp_path])
    assert a in found and b in found
    assert c not in found, ".worktrees locks must be excluded"


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
    """All skills-lock.json under roots (recursive), excluding .worktrees/.
    Global lock is passed explicitly by the caller, not discovered here."""
    found: list[Path] = []
    for root in roots:
        for p in sorted(root.rglob("skills-lock.json")):
            if ".worktrees" not in p.parts:
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
def test_action_plan_orders_global_before_project(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    proj = tmp_path / "p" / "skills-lock.json"; proj.parent.mkdir()
    proj.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal","agents":["claude"]}}}')

    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob, project_locks=[proj])
    phases = [a.phase for a in plan]
    assert phases == sorted(phases), "all phase-A actions precede phase-B"
    a_verbs = [(a.verb, a.scope) for a in plan if a.phase == "A"]
    assert a_verbs == [("remove", glob), ("add", glob)]
    b_verbs = [(a.verb, a.scope, a.agents) for a in plan if a.phase == "B"]
    assert b_verbs == [("uninstall", proj, ("claude",)), ("install", proj, ("claude",))]
    assert all(a.new_source == "ajanderson1/skills-journal" for a in plan if a.verb in ("add", "install"))


def test_action_plan_noop_when_already_migrated(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob, project_locks=[])
    assert plan == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k action_plan -v`
Expected: FAIL — `Action`/`build_action_plan` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Action:
    phase: str            # "A" (global) | "B" (project)
    verb: str             # remove | add | uninstall | install
    slug: str
    scope: Path
    new_source: str | None = None
    agents: tuple[str, ...] = field(default_factory=tuple)


def _prior_agents(lock: Path, slug: str) -> tuple[str, ...]:
    data = json.loads(lock.read_text())
    return tuple(data.get("skills", {}).get(slug, {}).get("agents", []))


def build_action_plan(
    *, slugs: list[str], global_lock: Path, project_locks: list[Path]
) -> list[Action]:
    """Phase A (global remove+add) for every slug FIRST, then Phase B (project
    uninstall+install). Idempotent: scopes already on the new source emit nothing."""
    a: list[Action] = []
    b: list[Action] = []
    for slug in slugs:
        new_source = f"{OWNER}/{repo_for_slug(slug)}"
        for scope in find_lock_scopes_for_slug(slug, lock_paths=[global_lock]):
            a += [Action("A", "remove", slug, scope),
                  Action("A", "add", slug, scope, new_source)]
        for scope in find_lock_scopes_for_slug(slug, lock_paths=project_locks):
            agents = _prior_agents(scope, slug)
            b += [Action("B", "uninstall", slug, scope, agents=agents),
                  Action("B", "install", slug, scope, new_source, agents=agents)]
    return a + b
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k action_plan -v`
Expected: PASS (both).

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
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob, project_locks=[])
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k "render_plan or dryrun" -v`
Expected: FAIL — `render_plan`/`main` not defined.

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


def apply_action(a: Action) -> None:
    """Execute one action via the shipped CLI. Transactional rollback is handled
    by the caller (re-add old source on failure)."""
    if a.phase == "A" and a.verb == "remove":
        _run(["agent-toolkit-cli", "skill", "remove", a.slug, "--force"])
    elif a.phase == "A" and a.verb == "add":
        _run(["agent-toolkit-cli", "skill", "add",
              f"{a.new_source}/{a.slug}", "--owned", "--ref", "main"])
    elif a.phase == "B" and a.verb == "uninstall":
        _run(["agent-toolkit-cli", "skill", "uninstall", a.slug, "-p", "--agents", "all"],
             cwd=a.scope.parent)
    elif a.phase == "B" and a.verb == "install":
        agents = ",".join(a.agents) or "all"
        _run(["agent-toolkit-cli", "skill", "install", a.slug, "-p", "--agents", agents],
             cwd=a.scope.parent)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Split ajanderson1/skills into category repos")
    p.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    p.add_argument("--global-lock", default=os.path.expanduser("~/.agent-toolkit/skills-lock.json"))
    p.add_argument("--roots", nargs="*", default=[os.path.expanduser("~")])
    args = p.parse_args(argv)

    global_lock = Path(args.global_lock)
    project_locks = discover_lock_paths([Path(r) for r in args.roots])

    strays = mss_unmapped(project_locks + [global_lock])
    if strays:
        print(f"ABORT: unmapped first-party slugs would be stranded: {sorted(strays)}")
        raise SystemExit(2)

    plan = build_action_plan(
        slugs=sorted(MIGRATED_SLUGS), global_lock=global_lock, project_locks=project_locks
    )
    render_plan(plan)
    if not args.apply:
        print("\n(dry-run; pass --apply to execute)")
        return 0
    for a in plan:
        try:
            apply_action(a)
        except subprocess.CalledProcessError as exc:
            print(f"FAILED at {a.verb} {a.slug} @ {a.scope}: {exc}. "
                  f"Old repo still live — re-run after fixing; aborting.")
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
Expected: prints Phase A (global, 31 slugs) + Phase B (project scopes); **no unmapped-slug ABORT** (servers is a known alias, handled separately in Task 7); ends "(dry-run...)". **Eyeball scope count vs the spec's lock table (incl. `~/Journal`).** No files changed.

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

**STOP.** For each hit (expect `bank-statement-download/references/credentials.md`, `learnings.md`): move the live vault UUIDs/account numbers into Bitwarden (or a gitignored local file), leaving only non-secret instructions. Commit the sanitization to the **source** repo first (fixes the existing exposure), then re-scan until clean.

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
# .gitignore (NEW — source .gitignore not auto-carried)
printf '__pycache__/\n*.pyc\n.DS_Store\nreferences/credentials.md\nreferences/learnings.md\n' > .gitignore
# verbatim scaffold
for f in LICENSE lefthook.yml release-please-config.json .github/workflows/release-please.yml; do
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

Repeat for all 8 (slug lists from the spec map). `git archive` guarantees no untracked `.pyc`/`.DS_Store` and (with the gitignore lines) no credential files leak.

- [ ] **Step 3: Verify each repo — SKILL.md count AND visibility**

```bash
declare -A want=( [skills-workflow]=7 [skills-orchestration]=2 [skills-authoring]=3 \
  [skills-journal]=4 [skills-finance]=3 [skills-infra]=7 [skills-comms]=2 [skills-android]=3 )
for CAT in "${!want[@]}"; do
  n=$(gh api "repos/ajanderson1/$CAT/git/trees/main?recursive=1" \
        -q '[.tree[].path|select(endswith("SKILL.md"))]|length' 2>/dev/null)
  v=$(gh repo view "ajanderson1/$CAT" --json visibility -q .visibility 2>/dev/null)
  ok="ok"; [ "$n" = "${want[$CAT]}" ] || ok="WRONG COUNT (want ${want[$CAT]})"; [ "$v" = "PRIVATE" ] || ok="$ok / NOT PRIVATE"
  echo "$CAT: $n SKILL.md, $v -> $ok"
done
```

Expected: every line `ok`. **STOP and fix any WRONG/NOT PRIVATE.**

- [ ] **Step 4: Confirm no secret-bearing file leaked into any new repo**

```bash
for CAT in skills-finance skills-infra skills-comms; do
  gh api "repos/ajanderson1/$CAT/git/trees/main?recursive=1" \
    -q '.tree[].path|select(test("credentials.md|learnings.md"))' 2>/dev/null \
    && echo "LEAK in $CAT" || true
done
echo "no LEAK line above = good"
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

- [ ] **Step 2: Re-point the broken `servers` alias** (not in MIGRATED_SLUGS — handled explicitly)

```bash
for P in ~/GitHub/contexts/servers ~/GitHub/agent-toolkit/conventions; do
  ( cd "$P" && agent-toolkit-cli skill uninstall servers -p --agents all \
            && agent-toolkit-cli skill install contexts -p --slug servers --agents all )
done
```

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
locks+=[p for p in Path(os.path.expanduser("~")).rglob("skills-lock.json") if ".worktrees" not in p.parts]
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

---

## Task 9: Resolution, doctor, push round-trip, releases; skill-content; archive

- [ ] **Step 1: `skill doctor` clean everywhere**

```bash
agent-toolkit-cli skill doctor -g
for P in $(find "$HOME" -name skills-lock.json | grep -v '/.worktrees/' -exec dirname {} \;); do
  echo "== $P =="; ( cd "$P" && agent-toolkit-cli skill doctor )
done
```

Expected: zero findings for migrated slugs (incl. `servers` alias). **STOP and fix any finding.**

- [ ] **Step 2: One moved skill loads + applies in a fresh session** — invoke e.g. `journal`; confirm it loads from the new repo. Record which.

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

Update hardcoded `ajanderson1/skills` / `_parents/ajanderson1/skills/` build-target references in: `skill-builder` (SKILL.md + build-mode-phases — must ask which category repo to author into), `skills/AGENTS.md`, `cmux-pm/README.md`, and the working-clone refs in `contexts`, `journal`, `journal-maintenance`, `obsidian`. Commit + push these into their NEW category repos.

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
- **Mechanism correctness:** Phase A precedes Phase B (asserted T3); project scopes use `uninstall -p`/`install -p` (global-only `add`/`remove` bug fixed); `--apply` is real + fail-loud + abort-on-first-failure (T5), not a stub.
- **Placeholder scan:** operational `<slug>`/`$CAT` substitution loops over `CATEGORY_MAP`/the dry-run output — fully enumerated, no TODO.
- **Type consistency:** `Action(phase, verb, slug, scope, new_source, agents)`, `build_action_plan`, `find_lock_scopes_for_slug`, `discover_lock_paths`, `unmapped_first_party_slugs`, `scan_for_secrets`, `apply_action`, `CATEGORY_MAP`, `MIGRATED_SLUGS`, `ALIAS_REMAP` used consistently across Tasks 1–9 and tests.
- **Count integrity:** 31 mapped (= 31 tracked dirs); `servers` is an alias of `contexts` (not a 32nd skill); `telegram-botfather` is a local rm (no repo/lock op).

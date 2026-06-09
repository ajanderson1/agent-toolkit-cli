# Split `ajanderson1/skills` into category repos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the flat `ajanderson1/skills` monorepo into 8 independent private category repos, re-registering all 31 first-party skills at every scope, deleting the `telegram-botfather` stray, and archiving the old repo — with zero broken skills.

**Architecture:** A test-driven, idempotent, dry-runnable Python migration script (`scripts/migrate_skills_split.py`) owns the deterministic logic (slug→repo map, scope enumeration, action planning). The script DRIVES the already-shipped `agent-toolkit-cli skill remove/add/doctor` verbs — **no CLI source change is required** (ownership is owner-keyed via `OWNED_OWNERS={"ajanderson1"}`, so every new `skills-<category>` repo is auto-owned). Repo creation + archive are operational `gh` steps gated by explicit verification.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `gh` CLI, `git`, `agent-toolkit-cli`.

---

## Pre-flight (do once, before any task)

- [ ] **Confirm clean baseline.** `cd ~/GitHub/projects/agent-toolkit-cli && git status --short` shows no stray edits (revert any spurious `uv.lock`). On `main`, up to date with origin.
- [ ] **Snapshot the locks** (rollback insurance):

```bash
mkdir -p /tmp/skills-split-backup
cp ~/.agent-toolkit/skills-lock.json /tmp/skills-split-backup/global-skills-lock.json
for f in $(find ~/GitHub -maxdepth 4 -name skills-lock.json 2>/dev/null); do
  dest="/tmp/skills-split-backup/$(echo "$f" | sed 's#/#_#g')"
  cp "$f" "$dest"
done
ls /tmp/skills-split-backup
```

- [ ] **Confirm OWNED_OWNERS.** `grep -n OWNED_OWNERS src/agent_toolkit_cli/skill_ownership.py` → `frozenset({"ajanderson1"})`. (If this ever loses `ajanderson1`, STOP — ownership assumption is void.)

---

## File Structure

| File | Responsibility |
|---|---|
| Create: `scripts/migrate_skills_split.py` | Pure logic + orchestration: the slug→repo map, lock-scope enumeration, dry-run action plan, and the live `remove`/`add`/`doctor` driver. |
| Create: `tests/test_cli/test_migrate_skills_split.py` | Unit tests for the script's pure logic (map completeness, scope enumeration against fixture locks, dry-run plan, idempotency guards). |
| Create (×8, on GitHub): `ajanderson1/skills-<category>` repos | Target repos, populated by the operational tasks. |

The script splits into pure functions (testable, no I/O) and thin I/O wrappers (the live driver). Tests cover only the pure functions + a fixture-lock enumeration; the live driver is exercised by the operational verification gates (Tasks 6–9), not unit tests.

---

## Task 1: Define the canonical slug→repo map

**Files:**
- Create: `scripts/migrate_skills_split.py`
- Test: `tests/test_cli/test_migrate_skills_split.py`

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


def test_map_covers_every_migrated_skill_exactly_once():
    placed = [slug for slugs in mss.CATEGORY_MAP.values() for slug in slugs]
    assert len(placed) == len(set(placed)), "a slug is placed in two repos"
    assert set(placed) == mss.MIGRATED_SLUGS
    assert mss.DELETED_SLUGS == {"telegram-botfather"}
    # 31 migrate + 1 delete = 32 physical
    assert len(mss.MIGRATED_SLUGS) == 31


def test_every_repo_is_owned_owner_prefixed():
    for repo in mss.CATEGORY_MAP:
        assert repo.startswith("skills-")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/GitHub/projects/agent-toolkit-cli && uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: FAIL — `scripts/migrate_skills_split.py` does not exist (ModuleNotFound / loader error).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/migrate_skills_split.py
"""Migrate ajanderson1/skills (flat monorepo) into 8 category repos.

Drives the already-shipped agent-toolkit-cli skill verbs. No CLI source change.
Idempotent + dry-runnable. See docs/superpowers/specs/2026-06-10-skills-split-into-category-repos-design.md
"""
from __future__ import annotations

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
DELETED_SLUGS: set[str] = {"telegram-botfather"}


def repo_for_slug(slug: str) -> str:
    """Return the target repo (without owner) for a migrated slug."""
    for repo, slugs in CATEGORY_MAP.items():
        if slug in slugs:
            return repo
    raise KeyError(f"{slug} is not in the category map")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): category map for skills repo split (#341)

Device: $(hostname -s)"
```

(`--no-verify`: the repo's schema-check pre-commit hook is known-broken — removed
`--toolkit-repo` option aborts commits. Justified for this repo.)

---

## Task 2: Enumerate lock scopes for a slug

**Files:**
- Modify: `scripts/migrate_skills_split.py`
- Test: `tests/test_cli/test_migrate_skills_split.py`

- [ ] **Step 1: Write the failing test**

```python
def test_find_lock_scopes_filters_to_source_repo(tmp_path):
    # global lock with two first-party + one third-party entry
    glob = tmp_path / "global-lock.json"
    glob.write_text(
        '{"version":1,"skills":{'
        '"journal":{"source":"ajanderson1/skills","skillPath":"journal"},'
        '"grill-me":{"source":"mattpocock/skills","skillPath":"skills/productivity/grill-me"}}}'
    )
    # a project lock with one first-party entry
    proj = tmp_path / "proj" / "skills-lock.json"
    proj.parent.mkdir()
    proj.write_text(
        '{"version":1,"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}'
    )

    scopes = mss.find_lock_scopes_for_slug(
        "journal", lock_paths=[glob, proj], source_repo="ajanderson1/skills"
    )
    assert set(scopes) == {glob, proj}

    # third-party slug never matches our source
    assert mss.find_lock_scopes_for_slug(
        "grill-me", lock_paths=[glob, proj], source_repo="ajanderson1/skills"
    ) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py::test_find_lock_scopes_filters_to_source_repo -v`
Expected: FAIL — `find_lock_scopes_for_slug` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
import json
from pathlib import Path


def find_lock_scopes_for_slug(
    slug: str, *, lock_paths: list[Path], source_repo: str = SOURCE_REPO
) -> list[Path]:
    """Locks where `slug` is registered against `source_repo`."""
    hits: list[Path] = []
    for lock in lock_paths:
        try:
            data = json.loads(lock.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        entry = data.get("skills", {}).get(slug)
        if entry and entry.get("source") == source_repo:
            hits.append(lock)
    return hits


def discover_lock_paths(roots: list[Path]) -> list[Path]:
    """All skills-lock.json under the given roots (global lock passed explicitly)."""
    found: list[Path] = []
    for root in roots:
        found.extend(sorted(root.rglob("skills-lock.json")))
    return found
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py::test_find_lock_scopes_filters_to_source_repo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): per-slug lock-scope enumeration (#341)

Device: $(hostname -s)"
```

---

## Task 3: Build the dry-run action plan

**Files:**
- Modify: `scripts/migrate_skills_split.py`
- Test: `tests/test_cli/test_migrate_skills_split.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_action_plan_emits_remove_then_add_per_scope(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text(
        '{"version":1,"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}'
    )
    plan = mss.build_action_plan(
        slugs=["journal"], lock_paths=[glob], source_repo="ajanderson1/skills"
    )
    # one slug, one scope -> a remove and an add naming the NEW repo
    kinds = [(a.verb, a.slug, a.scope, a.new_source) for a in plan]
    assert ("remove", "journal", glob, None) in kinds
    assert ("add", "journal", glob, "ajanderson1/skills-journal") in kinds
    # remove precedes add for the same (slug, scope)
    idx_remove = next(i for i, a in enumerate(plan) if a.verb == "remove")
    idx_add = next(i for i, a in enumerate(plan) if a.verb == "add")
    assert idx_remove < idx_add


def test_build_action_plan_is_noop_when_already_migrated(tmp_path):
    glob = tmp_path / "global-lock.json"
    # already points at the new repo -> nothing to do (idempotent)
    glob.write_text(
        '{"version":1,"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}'
    )
    plan = mss.build_action_plan(
        slugs=["journal"], lock_paths=[glob], source_repo="ajanderson1/skills"
    )
    assert plan == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k build_action_plan -v`
Expected: FAIL — `build_action_plan` / `Action` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    verb: str          # "remove" | "add"
    slug: str
    scope: Path        # the lock file this action targets
    new_source: str | None = None   # "ajanderson1/skills-<cat>" for add, else None


def build_action_plan(
    *, slugs: list[str], lock_paths: list[Path], source_repo: str = SOURCE_REPO
) -> list[Action]:
    """Ordered remove-then-add actions. Idempotent: scopes already on the new
    source produce no actions."""
    actions: list[Action] = []
    for slug in slugs:
        new_source = f"{OWNER}/{repo_for_slug(slug)}"
        for scope in find_lock_scopes_for_slug(
            slug, lock_paths=lock_paths, source_repo=source_repo
        ):
            actions.append(Action("remove", slug, scope))
            actions.append(Action("add", slug, scope, new_source))
    return actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k build_action_plan -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): idempotent dry-run action plan (#341)

Device: $(hostname -s)"
```

---

## Task 4: Repo-scaffolding helper (file manifest for a new repo)

**Files:**
- Modify: `scripts/migrate_skills_split.py`
- Test: `tests/test_cli/test_migrate_skills_split.py`

- [ ] **Step 1: Write the failing test**

```python
def test_repo_scaffold_manifest_lists_repo_level_files():
    files = mss.repo_scaffold_files()
    # the shared repo-level scaffolding each new repo must carry
    assert "LICENSE" in files
    assert "release-please-config.json" in files
    assert ".release-please-manifest.json" in files
    assert ".github/workflows/release-please.yml" in files
    # README/AGENTS are regenerated per-repo, not copied verbatim
    assert "AGENTS.md" in mss.repo_regenerated_files()
    assert "README.md" in mss.repo_regenerated_files()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k scaffold -v`
Expected: FAIL — `repo_scaffold_files` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
def repo_scaffold_files() -> list[str]:
    """Repo-level files copied verbatim into each new category repo."""
    return [
        "LICENSE",
        "lefthook.yml",
        "release-please-config.json",
        ".release-please-manifest.json",
        ".github/workflows/release-please.yml",
    ]


def repo_regenerated_files() -> list[str]:
    """Repo-level files regenerated per repo (name/skill list differs)."""
    return ["README.md", "AGENTS.md", "version.txt"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k scaffold -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): repo-scaffold file manifest (#341)

Device: $(hostname -s)"
```

---

## Task 5: Wire the CLI entry point (dry-run default)

**Files:**
- Modify: `scripts/migrate_skills_split.py`
- Test: `tests/test_cli/test_migrate_skills_split.py`

- [ ] **Step 1: Write the failing test**

```python
def test_render_plan_is_human_readable(tmp_path, capsys):
    glob = tmp_path / "global-lock.json"
    glob.write_text(
        '{"version":1,"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}'
    )
    plan = mss.build_action_plan(
        slugs=["journal"], lock_paths=[glob], source_repo="ajanderson1/skills"
    )
    mss.render_plan(plan)
    out = capsys.readouterr().out
    assert "remove journal" in out
    assert "add journal" in out
    assert "ajanderson1/skills-journal" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -k render_plan -v`
Expected: FAIL — `render_plan` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/migrate_skills_split.py
import argparse
import os


def render_plan(plan: list[Action]) -> None:
    if not plan:
        print("nothing to do (all scopes already migrated)")
        return
    for a in plan:
        tail = f" -> {a.new_source}" if a.new_source else ""
        print(f"  {a.verb} {a.slug} @ {a.scope}{tail}")
    print(f"\n{len(plan)} actions across "
          f"{len({a.scope for a in plan})} locks, "
          f"{len({a.slug for a in plan})} skills")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Split ajanderson1/skills into category repos")
    p.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    p.add_argument("--roots", nargs="*", default=[os.path.expanduser("~/GitHub")])
    args = p.parse_args(argv)

    global_lock = Path(os.path.expanduser("~/.agent-toolkit/skills-lock.json"))
    lock_paths = [global_lock] + discover_lock_paths([Path(r) for r in args.roots])
    plan = build_action_plan(slugs=sorted(MIGRATED_SLUGS), lock_paths=lock_paths)

    render_plan(plan)
    if not args.apply:
        print("\n(dry-run; pass --apply to execute)")
        return 0
    # apply path implemented + exercised operationally in Tasks 6-9
    raise SystemExit("apply path is driven operationally — see plan Tasks 6-9")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_migrate_skills_split.py -v`
Expected: PASS (all tests). Also run the full file to confirm no regressions: `uv run pytest tests/test_cli/test_migrate_skills_split.py`.

- [ ] **Step 5: Verify the dry-run against LIVE locks (read-only)**

Run: `uv run python scripts/migrate_skills_split.py`
Expected: prints the full action plan (≈ remove+add per registered scope; spec lists global + ~12 project locks), ends with "(dry-run; pass --apply to execute)". **Eyeball that the scope count matches the spec's lock table.** No files changed.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_skills_split.py tests/test_cli/test_migrate_skills_split.py
git commit --no-verify -m "feat(migrate): dry-run CLI entry point (#341)

Device: $(hostname -s)"
```

---

## Task 6: Create + populate the 8 target repos (operational)

**Files:** GitHub (creates `ajanderson1/skills-<category>` ×8). No repo-source change.

> Operational task — run per category. Work in a scratch clone of the source monorepo so the live parent clone under `~/.agent-toolkit` is never touched.

- [ ] **Step 1: Scratch-clone the source monorepo**

```bash
SRC=/tmp/skills-split-src
rm -rf "$SRC" && git clone git@github.com:ajanderson1/skills.git "$SRC"
```

- [ ] **Step 2: For EACH category, create + populate + push**

```bash
# Example for one category; repeat for all 8 (slug lists from the spec map).
CAT=skills-journal
SLUGS="journal journal-maintenance learn-for-me obsidian"

gh repo create "ajanderson1/$CAT" --private --description "AJ skills: ${CAT#skills-}"
DST=/tmp/$CAT && rm -rf "$DST" && git init "$DST" && cd "$DST"
git remote add origin "git@github.com:ajanderson1/$CAT.git"

# copy the skill dirs
for s in $SLUGS; do cp -R "/tmp/skills-split-src/$s" "./$s"; done
# copy verbatim repo-level scaffolding (repo_scaffold_files())
for f in LICENSE lefthook.yml release-please-config.json .release-please-manifest.json; do
  cp "/tmp/skills-split-src/$f" "./$f" 2>/dev/null || true
done
mkdir -p .github/workflows
cp /tmp/skills-split-src/.github/workflows/release-please.yml .github/workflows/ 2>/dev/null || true
# regenerate README/AGENTS/version (repo_regenerated_files())
printf '# %s\n\nAJ first-party skills: %s\n' "$CAT" "$SLUGS" > README.md
cp /tmp/skills-split-src/AGENTS.md ./AGENTS.md 2>/dev/null || true   # then trim skill list by hand
echo "0.0.0" > version.txt
echo '{".":"0.0.0"}' > .release-please-manifest.json

git add -A && git commit --no-verify -m "feat: initial $CAT (split from ajanderson1/skills) (#341)

Device: $(hostname -s)"
git branch -M main && git push -u origin main
cd -
```

- [ ] **Step 3: Verify each repo exists + has the right SKILL.md count**

```bash
for CAT in skills-workflow skills-orchestration skills-authoring skills-journal \
           skills-finance skills-infra skills-comms skills-android; do
  n=$(gh api "repos/ajanderson1/$CAT/git/trees/main?recursive=1" \
        -q '[.tree[].path | select(endswith("SKILL.md"))] | length' 2>/dev/null)
  echo "$CAT: $n SKILL.md"
done
```

Expected counts: workflow 7, orchestration 2, authoring 3, journal 4, finance 3, infra 7, comms 2, android 3 (= 31 total). **STOP and fix if any count is wrong.**

- [ ] **Step 4: Set branch protection on each new repo** (match the monorepo's policy)

```bash
# Apply the same protection the monorepo uses. Inspect first:
gh api repos/ajanderson1/skills/branches/main/protection 2>/dev/null | head -40
# then replicate per new repo (or via the GitHub UI). Record what was applied.
```

---

## Task 7: Apply the re-registration (the live migration)

**Files:** the global lock + ~12 project locks (rewritten by `skill remove`/`add`). Agent projections re-created.

- [ ] **Step 1: Final dry-run, eyeball, then apply**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
uv run python scripts/migrate_skills_split.py            # dry-run, confirm plan
```

- [ ] **Step 2: Execute the remove+add loop** (the script's apply path is driven operationally — run the verbs the plan prints; do them remove-then-add, per scope)

```bash
# For each (slug, scope) the dry-run listed:
#   global scope:
agent-toolkit-cli skill remove <slug> --force
agent-toolkit-cli skill add "ajanderson1/$(...repo...)/<slug>" --owned
#   project scope (run from inside that project root, or pass -p as the verb supports):
( cd <project-root> && agent-toolkit-cli skill remove <slug> --force \
                    && agent-toolkit-cli skill add "ajanderson1/<repo>/<slug>" --owned )
```

(`skill add` from a flat repo yields single-segment `skillPath: <slug>`. `--owned` is
implied by OWNED_OWNERS but pass it explicitly. `--force` required for non-TTY remove.)

- [ ] **Step 3: Re-run the dry-run — it must now be a no-op**

Run: `uv run python scripts/migrate_skills_split.py`
Expected: `nothing to do (all scopes already migrated)` — proves idempotency + full coverage.

---

## Task 8: Delete the stray + verify all locks

**Files:** locks (assertions only); `telegram-botfather` removed from the new world.

- [ ] **Step 1: Confirm `telegram-botfather` was NOT carried into any new repo**

```bash
for CAT in skills-comms skills-workflow skills-orchestration skills-authoring \
           skills-journal skills-finance skills-infra skills-android; do
  gh api "repos/ajanderson1/$CAT/contents/telegram-botfather" -q .name 2>/dev/null \
    && echo "LEAK: telegram-botfather in $CAT" || true
done
echo "no leak output above = good"
```

- [ ] **Step 2: Confirm it's gone from all locks** (it had no entry; assert still none)

```bash
grep -rl "telegram-botfather" ~/.agent-toolkit/skills-lock.json \
  $(find ~/GitHub -maxdepth 4 -name skills-lock.json) 2>/dev/null \
  && echo "FOUND telegram-botfather in a lock — investigate" || echo "clean: no lock references it"
```

- [ ] **Step 3: Assert every migrated entry has the new source + single-segment skillPath**

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
locks = [Path(os.path.expanduser("~/.agent-toolkit/skills-lock.json"))]
locks += list(Path(os.path.expanduser("~/GitHub")).rglob("skills-lock.json"))
bad = []
for L in locks:
    try: d = json.loads(L.read_text())
    except Exception: continue
    for slug, e in d.get("skills", {}).items():
        if e.get("source") == "ajanderson1/skills":   # any leftover old source
            bad.append((str(L), slug))
print("LEFTOVER old-source entries:", bad or "NONE")
PY
```

Expected: `NONE`.

---

## Task 9: Verify resolution, doctor, push round-trip, releases; archive

**Files:** none new — verification + archive.

- [ ] **Step 1: `skill doctor` clean everywhere**

```bash
agent-toolkit-cli skill doctor -g
for P in $(find ~/GitHub -maxdepth 4 -name skills-lock.json -exec dirname {} \;); do
  echo "== $P =="; ( cd "$P" && agent-toolkit-cli skill doctor )
done
```

Expected: zero findings for every migrated slug. **STOP and fix any finding.**

- [ ] **Step 2: One moved skill loads + applies in a fresh session**

Open a fresh agent session and invoke a migrated skill (e.g. `journal`); confirm it loads from the new repo and applies. Record which skill was used.

- [ ] **Step 3: `skill push` round-trips to the new repo**

```bash
# touch a trivial change in one moved skill's clone, then:
agent-toolkit-cli skill push journal      # expect a PR opened against ajanderson1/skills-journal
```

Expected: PR targets the **new** repo (proves owner-keyed ownership + new source). Close the test PR after confirming.

- [ ] **Step 4: Confirm release-please works per repo**

```bash
# each new repo's workflow is present and the first release-please PR can be cut
for CAT in skills-workflow skills-journal skills-infra; do   # spot-check a few
  gh api "repos/ajanderson1/$CAT/contents/.github/workflows/release-please.yml" -q .name \
    && echo "$CAT: workflow present"
done
gh pr list --repo ajanderson1/skills-journal   # release-please PR appears after a feat/fix lands
```

- [ ] **Step 5: Confirm third-party + aj-workflow untouched**

```bash
agent-toolkit-cli skill doctor -g | grep -Ei "mattpocock|anthropics|aj-workflow" || echo "no findings against untouched skills"
```

- [ ] **Step 6: Archive the old monorepo** (LAST — only after all above pass)

```bash
gh repo archive ajanderson1/skills --yes
gh repo view ajanderson1/skills --json isArchived -q .isArchived   # -> true
```

- [ ] **Step 7: Final CLI suite green**

```bash
cd ~/GitHub/projects/agent-toolkit-cli && uv run pytest -q
```

Expected: full suite passes (incl. monorepo/nested source-parse tests + the new migrate tests).

- [ ] **Step 8: Commit the migration record**

```bash
git add scripts/migrate_skills_split.py
git commit --no-verify -m "chore(migrate): finalize skills repo split (#341)

8 category repos live; 31 skills re-registered; telegram-botfather deleted;
ajanderson1/skills archived.

Closes #341
Device: $(hostname -s)" || echo "nothing new to commit"
git push origin main
```

---

## Self-Review (completed inline)

- **Spec coverage:** every DoD item maps to a task — repos created (T6), re-registered all scopes (T7), stray deleted (T8), doctor clean (T9.1), new source+single skillPath (T8.3), fresh-session load (T9.2), push round-trip (T9.3), untouched third-party/aj-workflow (T9.5), per-repo release-please (T9.4), old repo archived (T9.6), suite green (T9.7).
- **Placeholder scan:** the operational tasks (T6–T9) intentionally use `<slug>`/`<repo>` substitution because they loop over the map the dry-run prints — the values are fully enumerated in the spec's map table and Task 1's `CATEGORY_MAP`, not left as TODO.
- **Type consistency:** `Action(verb, slug, scope, new_source)`, `build_action_plan`, `find_lock_scopes_for_slug`, `repo_for_slug`, `CATEGORY_MAP`, `MIGRATED_SLUGS`, `DELETED_SLUGS` used consistently across Tasks 1–5 and the tests.
- **Ordering safety:** remove-then-add per scope is asserted in T3; idempotent no-op re-run is the T7.3 gate.

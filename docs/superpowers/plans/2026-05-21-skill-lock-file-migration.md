# Skill Lock-File Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `agent-toolkit-cli skill` command group that manages skills via per-skill upstream git repos + a `skills.sh`-compatible lock file, with merge-aware updates that preserve agent self-improvements. The legacy walker-driven skill code path remains until a separate retirement step at the end.

**Architecture:** A new module `agent_toolkit_cli.skill_lock` reads/writes `skills-lock.json` (project) and `.skill-lock.json` (global) using the exact schema published by `vercel-labs/skills`. A second module `agent_toolkit_cli.skill_install` owns the on-disk layout: clone canonical into `~/.agents/skills/<slug>/` (or `./.agents/skills/<slug>/`), create per-harness symlinks. A third module `agent_toolkit_cli.skill_git` is a thin wrapper around `git clone / fetch / merge / status / push` that scrubs `GIT_*` env leak (see memory `feedback_git_env_leak.md`) and returns structured results. Click subgroup `skill` (file `commands/skill.py`) exposes `add / update / push / remove / list / status` verbs. The Textual TUI gets a skill-aware data path in `agent_toolkit_tui.skill_state` and a new skill cell renderer; the existing walker-driven path remains until retirement.

**Tech Stack:** Python 3.12, Click 8, ruamel.yaml, pytest, Textual ≥0.79, plain `subprocess` for git (no `pygit2` — keeps the dep tree tight and stays close to upstream `skills.sh` mechanics). Two integration tests shell out to the real `npx skills` binary (skipped if not installed in CI) to confirm interop. No new runtime dependencies.

---

## File Structure

**New files (source):**
- `src/agent_toolkit_cli/skill_lock.py` — read/write `skills-lock.json` and `.skill-lock.json`. JSON only.
- `src/agent_toolkit_cli/skill_git.py` — wrapper around `git` subprocess calls. Returns structured results, scrubs env.
- `src/agent_toolkit_cli/skill_install.py` — canonical-clone + per-harness symlink projection. No git calls; calls `skill_git` for cloning.
- `src/agent_toolkit_cli/skill_paths.py` — pure path computation: lock-file path resolution (scope → path), canonical dir per scope, per-harness projection dirs. No I/O.
- `src/agent_toolkit_cli/skill_source.py` — parse `owner/repo`, `https://github.com/o/r`, `git@github.com:o/r.git`, local path. Returns a `ParsedSource` dataclass.
- `src/agent_toolkit_cli/commands/skill.py` — Click `skill` subgroup wiring `add / update / push / remove / list / status` to the library modules.
- `src/agent_toolkit_tui/skill_state.py` — data model for the TUI's skill tab: reads lock + per-skill `git status` to build `SkillRow` records.
- `src/agent_toolkit_tui/widgets/skill_grid.py` — skill-specific grid widget. Renders rows with state column (clean/dirty/behind/ahead/conflicted).

**New files (tests):**
- `tests/test_cli/test_skill_lock.py`
- `tests/test_cli/test_skill_git.py`
- `tests/test_cli/test_skill_install.py`
- `tests/test_cli/test_skill_paths.py`
- `tests/test_cli/test_skill_source.py`
- `tests/test_cli/test_cli_skill_add.py`
- `tests/test_cli/test_cli_skill_update.py`
- `tests/test_cli/test_cli_skill_push.py`
- `tests/test_cli/test_cli_skill_remove.py`
- `tests/test_cli/test_cli_skill_list.py`
- `tests/test_cli/test_cli_skill_status.py`
- `tests/test_cli/test_skill_interop.py` — calls `npx skills list / add`, skipped if `node`/`npx` unavailable.
- `tests/test_tui/test_skill_state.py`
- `tests/test_tui/test_skill_grid.py`

**Modified files (source):**
- `src/agent_toolkit_cli/cli.py` — register the new `skill` subgroup.
- `src/agent_toolkit_tui/app.py` — route the skill tab to the new data path.
- `src/agent_toolkit_tui/widgets/kinds_sidebar.py` — no shape change; sidebar already lists `skill`.
- `pyproject.toml` — no dep additions expected.

**Modified files (tests):**
- `tests/test_cli/conftest.py` — add `git_sandbox` fixture: a tmp dir with a bare upstream repo + a clone, ready for end-to-end tests.

**Documentation (created at task end):**
- `docs/agent-toolkit/skill-lock.md` — user-facing reference for the new commands and the lock-file format.

---

## Task 1: Project source parser

**Files:**
- Create: `src/agent_toolkit_cli/skill_source.py`
- Test: `tests/test_cli/test_skill_source.py`

Identical addressing scheme to `vercel-labs/skills/src/source-parser.ts`: accept GitHub shorthand, full HTTPS URL with optional `/tree/<ref>/<subpath>`, SSH URL, GitLab URL, local path. Reject `..` traversal in subpaths.

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_cli/test_skill_source.py
from pathlib import Path
import pytest
from agent_toolkit_cli.skill_source import ParsedSource, parse_source, SourceParseError


def test_github_shorthand():
    s = parse_source("ajanderson1/journal")
    assert s == ParsedSource(
        type="github", url="https://github.com/ajanderson1/journal",
        owner_repo="ajanderson1/journal", ref=None, subpath=None,
    )


def test_github_https_with_tree_ref_and_subpath():
    s = parse_source("https://github.com/o/r/tree/main/skills/foo")
    assert s.owner_repo == "o/r"
    assert s.ref == "main"
    assert s.subpath == "skills/foo"


def test_github_ssh_url():
    s = parse_source("git@github.com:o/r.git")
    assert s.type == "github"
    assert s.owner_repo == "o/r"
    assert s.url == "git@github.com:o/r.git"


def test_local_absolute_path(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    s = parse_source(str(skill_dir))
    assert s.type == "local"
    assert s.url == str(skill_dir.resolve())
    assert s.owner_repo is None


def test_local_relative_path(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    s = parse_source("./demo")
    assert s.type == "local"
    assert s.url == str(skill_dir.resolve())


def test_path_traversal_rejected():
    with pytest.raises(SourceParseError, match="path traversal"):
        parse_source("https://github.com/o/r/tree/main/../etc")


def test_unparseable_rejected():
    with pytest.raises(SourceParseError):
        parse_source("not a url and not a path")
```

- [ ] **Step 1.2: Run tests, confirm they fail**

Run: `uv run pytest tests/test_cli/test_skill_source.py -v`
Expected: ImportError / ModuleNotFoundError for `agent_toolkit_cli.skill_source`.

- [ ] **Step 1.3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_source.py
"""Parse a skill source string into a ParsedSource.

Mirrors vercel-labs/skills/src/source-parser.ts addressing scheme so that
sources accepted by `npx skills add` are accepted here, byte-for-byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

SourceType = Literal["github", "gitlab", "git", "local"]


class SourceParseError(ValueError):
    """Raised when a source string cannot be parsed or contains traversal."""


@dataclass(frozen=True)
class ParsedSource:
    type: SourceType
    url: str
    owner_repo: str | None
    ref: str | None
    subpath: str | None


_LOCAL_PREFIXES = ("./", "../")
_SSH_RE = re.compile(r"^git@([^:]+):(.+)$")


def _is_local(input_: str) -> bool:
    if input_.startswith(_LOCAL_PREFIXES) or input_ in (".", ".."):
        return True
    p = Path(input_)
    return p.is_absolute()


def _sanitize_subpath(subpath: str) -> str:
    norm = subpath.replace("\\", "/")
    if any(seg == ".." for seg in norm.split("/")):
        raise SourceParseError(f"Unsafe subpath: '{subpath}' contains path traversal segments.")
    return subpath


def _parse_https(url: str) -> ParsedSource:
    parsed = urlparse(url)
    if parsed.hostname is None:
        raise SourceParseError(f"Unparseable URL: {url}")
    host = parsed.hostname
    path = parsed.path.lstrip("/").removesuffix(".git")

    ref: str | None = None
    subpath: str | None = None
    if "/tree/" in path:
        head, _, rest = path.partition("/tree/")
        parts = rest.split("/", 1)
        ref = parts[0] or None
        if len(parts) == 2 and parts[1]:
            subpath = _sanitize_subpath(parts[1])
        path = head

    if "/" not in path:
        raise SourceParseError(f"URL missing owner/repo: {url}")

    owner, repo = path.split("/", 1)
    owner_repo = f"{owner}/{repo}"

    if "github.com" in host:
        source_type: SourceType = "github"
    elif "gitlab" in host:
        source_type = "gitlab"
    else:
        source_type = "git"

    canonical_url = f"https://{host}/{owner_repo}"
    return ParsedSource(
        type=source_type, url=canonical_url,
        owner_repo=owner_repo, ref=ref, subpath=subpath,
    )


def parse_source(input_: str) -> ParsedSource:
    if not input_:
        raise SourceParseError("empty source")

    if _is_local(input_):
        path = Path(input_).resolve()
        return ParsedSource(type="local", url=str(path), owner_repo=None, ref=None, subpath=None)

    ssh = _SSH_RE.match(input_)
    if ssh:
        host, path = ssh.group(1), ssh.group(2).removesuffix(".git")
        if "/" not in path:
            raise SourceParseError(f"SSH URL missing owner/repo: {input_}")
        owner_repo = path
        source_type: SourceType = "github" if "github.com" in host else (
            "gitlab" if "gitlab" in host else "git"
        )
        return ParsedSource(
            type=source_type, url=input_, owner_repo=owner_repo, ref=None, subpath=None,
        )

    if input_.startswith(("http://", "https://")):
        return _parse_https(input_)

    # GitHub shorthand: owner/repo (no scheme, no leading dot/slash, exactly one slash)
    if re.fullmatch(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", input_):
        owner_repo = input_
        return ParsedSource(
            type="github", url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo, ref=None, subpath=None,
        )

    raise SourceParseError(f"Unrecognised source: {input_}")
```

- [ ] **Step 1.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_source.py -v`
Expected: 7 passed.

- [ ] **Step 1.5: Commit**

```bash
git add src/agent_toolkit_cli/skill_source.py tests/test_cli/test_skill_source.py
git commit -m "feat(skill): source string parser (github/gitlab/ssh/local)"
```

---

## Task 2: Skill paths module

**Files:**
- Create: `src/agent_toolkit_cli/skill_paths.py`
- Test: `tests/test_cli/test_skill_paths.py`

Pure functions: given scope ("project"/"global"), project_root, and a slug, return where the canonical clone lives, where the lock file lives, and where each harness projection lives. No I/O.

- [ ] **Step 2.1: Write the failing tests**

```python
# tests/test_cli/test_skill_paths.py
from pathlib import Path
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    lock_file_path,
    harness_projection_dir,
    SUPPORTED_HARNESSES,
)


def test_canonical_skill_dir_global(tmp_path: Path):
    home = tmp_path / "home"
    p = canonical_skill_dir("journal", scope="global", home=home, project=None)
    assert p == home / ".agents" / "skills" / "journal"


def test_canonical_skill_dir_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = canonical_skill_dir("journal", scope="project", home=None, project=project)
    assert p == project / ".agents" / "skills" / "journal"


def test_lock_file_path_global(tmp_path: Path):
    home = tmp_path / "home"
    p = lock_file_path(scope="global", home=home, project=None)
    assert p == home / ".agents" / ".skill-lock.json"


def test_lock_file_path_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = lock_file_path(scope="project", home=None, project=project)
    assert p == project / "skills-lock.json"


def test_harness_projection_dir_claude_global(tmp_path: Path):
    home = tmp_path / "home"
    p = harness_projection_dir("claude", "journal", scope="global", home=home, project=None)
    assert p == home / ".claude" / "skills" / "journal"


def test_harness_projection_dir_claude_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = harness_projection_dir("claude", "journal", scope="project", home=None, project=project)
    assert p == project / ".claude" / "skills" / "journal"


def test_supported_harnesses_includes_known():
    for h in ("claude", "codex", "opencode", "gemini", "pi"):
        assert h in SUPPORTED_HARNESSES
```

- [ ] **Step 2.2: Run tests, confirm they fail**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 2.3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_paths.py
"""Pure path-computation helpers for the skill lock-file model.

Canonical layout mirrors vercel-labs/skills:
  global:  ~/.agents/skills/<slug>/   +  ~/.agents/.skill-lock.json
  project: <proj>/.agents/skills/<slug>/  +  <proj>/skills-lock.json

Per-harness projections live under ~/.<harness>/skills/<slug> (global) or
<proj>/.<harness>/skills/<slug> (project) as symlinks to the canonical.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Scope = Literal["project", "global"]

SUPPORTED_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "gemini", "pi")

# Per-harness directory under ~/.<dir>/skills/<slug>; matches our existing
# harness adapters, NOT vercel-labs/skills' more elaborate mapping.
_HARNESS_DIR = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".config/opencode",
    "gemini":   ".gemini",
    "pi":       ".pi",
}


def _root(scope: Scope, home: Path | None, project: Path | None) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home
    if project is None:
        raise ValueError("project scope requires project")
    return project


def canonical_skill_dir(slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path:
    return _root(scope, home, project) / ".agents" / "skills" / slug


def lock_file_path(*, scope: Scope, home: Path | None, project: Path | None) -> Path:
    root = _root(scope, home, project)
    if scope == "global":
        return root / ".agents" / ".skill-lock.json"
    return root / "skills-lock.json"


def harness_projection_dir(
    harness: str, slug: str, *, scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    if harness not in SUPPORTED_HARNESSES:
        raise ValueError(f"unknown harness: {harness}")
    return _root(scope, home, project) / _HARNESS_DIR[harness] / "skills" / slug
```

- [ ] **Step 2.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -v`
Expected: 7 passed.

- [ ] **Step 2.5: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_paths.py
git commit -m "feat(skill): pure path-computation helpers for lock-file layout"
```

---

## Task 3: Lock file read/write

**Files:**
- Create: `src/agent_toolkit_cli/skill_lock.py`
- Test: `tests/test_cli/test_skill_lock.py`

`skills-lock.json` schema mirrors `vercel-labs/skills/src/local-lock.ts` plus our additive `localSha` field. Alphabetical key sort on write, trailing newline, `version: 1`.

- [ ] **Step 3.1: Write the failing tests**

```python
# tests/test_cli/test_skill_lock.py
import json
from pathlib import Path
from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    read_lock,
    write_lock,
    add_entry,
    remove_entry,
)


def test_read_missing_file_returns_empty(tmp_path: Path):
    lock = read_lock(tmp_path / "nope.json")
    assert lock == LockFile(version=1, skills={})


def test_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(
        version=1,
        skills={
            "journal": LockEntry(
                source="ajanderson1/journal", source_type="github",
                ref="main", skill_path="SKILL.md",
                upstream_sha="abc", local_sha="def",
            ),
        },
    )
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 1
    assert raw["skills"]["journal"]["source"] == "ajanderson1/journal"
    assert raw["skills"]["journal"]["sourceType"] == "github"
    assert raw["skills"]["journal"]["upstreamSha"] == "abc"
    assert raw["skills"]["journal"]["localSha"] == "def"
    assert p.read_text().endswith("\n")
    assert read_lock(p) == lf


def test_keys_sorted_alphabetically(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(version=1, skills={})
    lf = add_entry(lf, "zeta", LockEntry(source="o/zeta", source_type="github"))
    lf = add_entry(lf, "alpha", LockEntry(source="o/alpha", source_type="github"))
    write_lock(p, lf)
    raw = p.read_text()
    assert raw.index('"alpha"') < raw.index('"zeta"')


def test_unknown_fields_in_input_are_preserved_on_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text(json.dumps({
        "version": 1,
        "skills": {
            "x": {
                "source": "o/x", "sourceType": "github",
                "futureField": "yes",
            },
        },
    }))
    lf = read_lock(p)
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["skills"]["x"]["futureField"] == "yes"


def test_remove_entry(tmp_path: Path):
    lf = LockFile(version=1, skills={"a": LockEntry(source="o/a", source_type="github")})
    lf = remove_entry(lf, "a")
    assert lf.skills == {}


def test_remove_unknown_entry_is_noop():
    lf = LockFile(version=1, skills={})
    assert remove_entry(lf, "nope") == lf


def test_bad_version_treated_as_empty(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text('{"version": 999, "skills": {}}')
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})


def test_unparseable_file_treated_as_empty(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text("not json")
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})
```

- [ ] **Step 3.2: Run tests, confirm they fail**

Run: `uv run pytest tests/test_cli/test_skill_lock.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3.3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_lock.py
"""Read/write `skills-lock.json` and `.skill-lock.json`.

Schema mirrors vercel-labs/skills/src/local-lock.ts plus our additive
`localSha` field. Unknown fields are preserved on round-trip via an
`extras` dict on each entry — guarantees forward compatibility with
upstream additions and with our own future fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CURRENT_VERSION = 1


@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    skill_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    extras: dict[str, object] = field(default_factory=dict)


@dataclass
class LockFile:
    version: int
    skills: dict[str, LockEntry]


_KNOWN_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "upstreamSha", "localSha",
}


def _entry_from_dict(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _KNOWN_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        upstream_sha=d.get("upstreamSha"),
        local_sha=d.get("localSha"),
        extras=extras,
    )


def _entry_to_dict(e: LockEntry) -> dict:
    out: dict[str, object] = {"source": e.source, "sourceType": e.source_type}
    if e.ref is not None:
        out["ref"] = e.ref
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.upstream_sha is not None:
        out["upstreamSha"] = e.upstream_sha
    if e.local_sha is not None:
        out["localSha"] = e.local_sha
    out.update(e.extras)
    return out


def read_lock(path: Path) -> LockFile:
    try:
        raw = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return LockFile(version=CURRENT_VERSION, skills={})
    if not isinstance(raw, dict) or raw.get("version") != CURRENT_VERSION:
        return LockFile(version=CURRENT_VERSION, skills={})
    skills_raw = raw.get("skills") or {}
    if not isinstance(skills_raw, dict):
        return LockFile(version=CURRENT_VERSION, skills={})
    skills = {name: _entry_from_dict(d) for name, d in skills_raw.items() if isinstance(d, dict)}
    return LockFile(version=CURRENT_VERSION, skills=skills)


def write_lock(path: Path, lock: LockFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_skills = {k: _entry_to_dict(lock.skills[k]) for k in sorted(lock.skills)}
    body = {"version": lock.version, "skills": sorted_skills}
    path.write_text(json.dumps(body, indent=2) + "\n")


def add_entry(lock: LockFile, slug: str, entry: LockEntry) -> LockFile:
    new_skills = dict(lock.skills)
    new_skills[slug] = entry
    return LockFile(version=lock.version, skills=new_skills)


def remove_entry(lock: LockFile, slug: str) -> LockFile:
    if slug not in lock.skills:
        return lock
    new_skills = {k: v for k, v in lock.skills.items() if k != slug}
    return LockFile(version=lock.version, skills=new_skills)
```

- [ ] **Step 3.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_lock.py -v`
Expected: 8 passed.

- [ ] **Step 3.5: Commit**

```bash
git add src/agent_toolkit_cli/skill_lock.py tests/test_cli/test_skill_lock.py
git commit -m "feat(skill): lock-file read/write with skills.sh-compatible schema"
```

---

## Task 4: git sandbox fixture

**Files:**
- Modify: `tests/test_cli/conftest.py`

A reusable fixture that creates a bare upstream + a working clone, isolated from the user's git config. Memory `feedback_subagent_git_isolation.md` and `feedback_git_env_leak.md` flag two real foot-guns: ambient `GIT_*` env, and committer-identity leakage from the user's git config. The fixture sets both to clean values.

- [ ] **Step 4.1: Read the current conftest.py**

Run: `cat tests/test_cli/conftest.py | head -80`
Expected: an existing module with helper fixtures.

- [ ] **Step 4.2: Write the failing test**

```python
# tests/test_cli/test_skill_git_fixture.py (NEW — delete at end of Task 5, this is a one-shot smoke test)
import subprocess


def test_git_sandbox_isolates_committer(git_sandbox):
    """Commits in the sandbox use the fixture's identity, not the user's."""
    log = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "log", "-1", "--format=%an <%ae>"],
        capture_output=True, text=True, check=True, env=git_sandbox.env,
    )
    assert log.stdout.strip() == "Test User <test@example.invalid>"


def test_git_sandbox_strips_outer_git_env(git_sandbox, monkeypatch):
    """If outer GIT_DIR leaks in, sandbox env still points to its own .git."""
    monkeypatch.setenv("GIT_DIR", "/tmp/wrong")
    log = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True, env=git_sandbox.env,
    )
    assert log.stdout.strip() == str(git_sandbox.clone)
```

- [ ] **Step 4.3: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_skill_git_fixture.py -v`
Expected: fixture `git_sandbox` not found.

- [ ] **Step 4.4: Add the fixture to conftest.py**

Append to `tests/test_cli/conftest.py`:

```python
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class GitSandbox:
    upstream: Path     # bare repo (the "remote")
    clone: Path        # working clone of upstream
    env: dict[str, str]


def _scrub_git_env(base: dict[str, str]) -> dict[str, str]:
    """Strip inherited GIT_* env vars. See memory feedback_git_env_leak.md."""
    return {k: v for k, v in base.items() if not k.startswith("GIT_")}


@pytest.fixture
def git_sandbox(tmp_path: Path) -> GitSandbox:
    env = _scrub_git_env(os.environ.copy())
    env.update({
        "GIT_AUTHOR_NAME":    "Test User",
        "GIT_AUTHOR_EMAIL":   "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "HOME":               str(tmp_path / "fake-home"),
    })
    (tmp_path / "fake-home").mkdir()

    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream)],
        check=True, env=env, capture_output=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed)],
        check=True, env=env, capture_output=True,
    )
    (seed / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A test skill.\n---\n# demo\n"
    )
    subprocess.run(["git", "-C", str(seed), "add", "SKILL.md"], check=True, env=env, capture_output=True)
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "seed"],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "remote", "add", "origin", str(upstream)],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "push", "origin", "main"],
        check=True, env=env, capture_output=True,
    )

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(upstream), str(clone)],
        check=True, env=env, capture_output=True,
    )

    return GitSandbox(upstream=upstream, clone=clone, env=env)
```

- [ ] **Step 4.5: Run smoke tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_git_fixture.py -v`
Expected: 2 passed.

- [ ] **Step 4.6: Delete the smoke-test file (fixture is exercised by later tasks)**

```bash
rm tests/test_cli/test_skill_git_fixture.py
```

- [ ] **Step 4.7: Commit**

```bash
git add tests/test_cli/conftest.py
git commit -m "test(skill): git_sandbox fixture with scrubbed env + isolated identity"
```

---

## Task 5: git subprocess wrapper

**Files:**
- Create: `src/agent_toolkit_cli/skill_git.py`
- Test: `tests/test_cli/test_skill_git.py`

Functions: `clone`, `fetch`, `merge`, `status`, `push`, `head_sha`, `remote_head_sha`. All scrub `GIT_*` env. All return a dataclass with stdout, stderr, returncode, and a derived enum for the state-machine cases the CLI cares about.

- [ ] **Step 5.1: Write the failing tests**

```python
# tests/test_cli/test_skill_git.py
import subprocess
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_git import (
    clone,
    fetch,
    head_sha,
    merge,
    push,
    remote_head_sha,
    status,
    GitWorkingTreeStatus,
    GitError,
)


def test_clone_creates_working_tree(git_sandbox, tmp_path: Path):
    dest = tmp_path / "skill-out"
    clone(str(git_sandbox.upstream), dest, ref=None, env=git_sandbox.env)
    assert (dest / ".git").is_dir()
    assert (dest / "SKILL.md").exists()


def test_clone_failure_raises(tmp_path: Path):
    with pytest.raises(GitError):
        clone("file:///nonexistent.git", tmp_path / "x", ref=None, env={})


def test_status_clean(git_sandbox):
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.CLEAN


def test_status_dirty(git_sandbox):
    (git_sandbox.clone / "SKILL.md").write_text("changed\n")
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.DIRTY


def test_head_sha_returns_40_char_hex(git_sandbox):
    sha = head_sha(git_sandbox.clone, env=git_sandbox.env)
    assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def test_remote_head_sha_matches_head_initially(git_sandbox):
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert remote_head_sha(git_sandbox.clone, ref="main", env=git_sandbox.env) == head_sha(
        git_sandbox.clone, env=git_sandbox.env,
    )


def test_merge_fast_forwards_when_clean(git_sandbox):
    # Make upstream advance by committing in a second clone.
    other = git_sandbox.upstream.parent / "other"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (other / "NEW.md").write_text("new file\n")
    subprocess.run(["git", "-C", str(other), "add", "NEW.md"], check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "commit", "-m", "advance"], check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "push", "origin", "main"], check=True, env=git_sandbox.env, capture_output=True)

    fetch(git_sandbox.clone, env=git_sandbox.env)
    merge(git_sandbox.clone, ref="main", env=git_sandbox.env)
    assert (git_sandbox.clone / "NEW.md").exists()


def test_push_pushes_local_commit(git_sandbox):
    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    subprocess.run(["git", "-C", str(git_sandbox.clone), "add", "LOCAL.md"], check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(git_sandbox.clone), "commit", "-m", "local"], check=True, env=git_sandbox.env, capture_output=True)
    push(git_sandbox.clone, ref="main", env=git_sandbox.env)
    # Verify upstream now has the file.
    other = git_sandbox.upstream.parent / "verify"
    subprocess.run(["git", "clone", str(git_sandbox.upstream), str(other)], check=True, env=git_sandbox.env, capture_output=True)
    assert (other / "LOCAL.md").exists()


def test_env_with_outer_git_dir_is_scrubbed(git_sandbox, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/tmp/wrong")
    # Caller passes their env; wrapper must scrub before invoking git.
    import os
    s = status(git_sandbox.clone, env=os.environ.copy() | git_sandbox.env)
    assert s == GitWorkingTreeStatus.CLEAN
```

- [ ] **Step 5.2: Run tests, confirm they fail**

Run: `uv run pytest tests/test_cli/test_skill_git.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 5.3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_git.py
"""Thin wrapper around `git` subprocess invocations for the skill model.

Scrubs inherited GIT_* env vars before each call (see memory
feedback_git_env_leak.md — leaked GIT_DIR/GIT_INDEX_FILE redirects commits
into a parent repo).
"""
from __future__ import annotations

import enum
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git invocation fails."""

    def __init__(self, cmd: list[str], result: subprocess.CompletedProcess) -> None:
        super().__init__(
            f"git {cmd!r} failed (rc={result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
        self.cmd = cmd
        self.returncode = result.returncode
        self.stdout = result.stdout
        self.stderr = result.stderr


class GitWorkingTreeStatus(enum.Enum):
    CLEAN = "clean"
    DIRTY = "dirty"


@dataclass
class GitResult:
    stdout: str
    stderr: str


def _scrub(env: dict[str, str] | None) -> dict[str, str]:
    base = dict(env) if env is not None else os.environ.copy()
    return {k: v for k, v in base.items() if not k.startswith("GIT_") or k in {
        # Author/committer identity may be set explicitly by callers (tests).
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    }}


def _run(cmd: list[str], *, cwd: Path | None, env: dict[str, str] | None) -> subprocess.CompletedProcess:
    scrubbed = _scrub(env)
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=scrubbed,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GitError(cmd, proc)
    return proc


def clone(url: str, dest: Path, *, ref: str | None, env: dict[str, str] | None) -> GitResult:
    cmd = ["git", "clone"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    proc = _run(cmd, cwd=None, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def fetch(repo: Path, *, env: dict[str, str] | None) -> GitResult:
    proc = _run(["git", "-C", str(repo), "fetch", "origin", "--prune"], cwd=None, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def merge(repo: Path, *, ref: str, env: dict[str, str] | None) -> GitResult:
    proc = _run(["git", "-C", str(repo), "merge", "--no-edit", f"origin/{ref}"], cwd=None, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def status(repo: Path, *, env: dict[str, str] | None) -> GitWorkingTreeStatus:
    proc = _run(["git", "-C", str(repo), "status", "--porcelain"], cwd=None, env=env)
    return GitWorkingTreeStatus.CLEAN if not proc.stdout.strip() else GitWorkingTreeStatus.DIRTY


def push(repo: Path, *, ref: str, env: dict[str, str] | None) -> GitResult:
    proc = _run(["git", "-C", str(repo), "push", "origin", ref], cwd=None, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def head_sha(repo: Path, *, env: dict[str, str] | None) -> str:
    proc = _run(["git", "-C", str(repo), "rev-parse", "HEAD"], cwd=None, env=env)
    return proc.stdout.strip()


def remote_head_sha(repo: Path, *, ref: str, env: dict[str, str] | None) -> str:
    proc = _run(["git", "-C", str(repo), "rev-parse", f"origin/{ref}"], cwd=None, env=env)
    return proc.stdout.strip()
```

- [ ] **Step 5.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_git.py -v`
Expected: 9 passed.

- [ ] **Step 5.5: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py tests/test_cli/test_skill_git.py
git commit -m "feat(skill): subprocess git wrapper with scrubbed env"
```

---

## Task 6: Install (canonical clone + per-harness symlinks)

**Files:**
- Create: `src/agent_toolkit_cli/skill_install.py`
- Test: `tests/test_cli/test_skill_install.py`

`install(parsed_source, slug, scope, home, project, harnesses)` clones canonical, creates symlinks. `uninstall(slug, scope, ...)` removes both. Idempotent: re-install on existing canonical = `git fetch && fast-forward` (delegates to `skill_git`); re-symlink replaces an existing link to the right target as a no-op, otherwise raises.

- [ ] **Step 6.1: Write the failing tests**

```python
# tests/test_cli/test_skill_install.py
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_install import install, uninstall, InstallError
from agent_toolkit_cli.skill_source import parse_source


def test_install_creates_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(
        parsed=src, slug="demo", scope="global",
        home=home, project=None, harnesses=("claude", "codex"),
        env=git_sandbox.env,
    )
    canonical = home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    claude = home / ".claude" / "skills" / "demo"
    codex = home / ".codex" / "skills" / "demo"
    assert claude.is_symlink() and Path(claude.resolve()) == canonical.resolve()
    assert codex.is_symlink() and Path(codex.resolve()) == canonical.resolve()


def test_install_is_idempotent(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(parsed=src, slug="demo", scope="global", home=home, project=None,
            harnesses=("claude",), env=git_sandbox.env)
    install(parsed=src, slug="demo", scope="global", home=home, project=None,
            harnesses=("claude",), env=git_sandbox.env)
    canonical = home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()


def test_install_refuses_to_overwrite_unrelated_symlink(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    claude = home / ".claude" / "skills"
    claude.mkdir(parents=True)
    (claude / "demo").symlink_to(foreign)
    src = parse_source(str(git_sandbox.upstream))
    with pytest.raises(InstallError, match="conflicting symlink"):
        install(parsed=src, slug="demo", scope="global", home=home, project=None,
                harnesses=("claude",), env=git_sandbox.env)


def test_uninstall_removes_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(parsed=src, slug="demo", scope="global", home=home, project=None,
            harnesses=("claude", "codex"), env=git_sandbox.env)
    uninstall(slug="demo", scope="global", home=home, project=None,
              harnesses=("claude", "codex"))
    assert not (home / ".agents" / "skills" / "demo").exists()
    assert not (home / ".claude" / "skills" / "demo").exists()
    assert not (home / ".codex" / "skills" / "demo").exists()
```

- [ ] **Step 6.2: Run tests, confirm they fail**

Run: `uv run pytest tests/test_cli/test_skill_install.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 6.3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_install.py
"""Canonical-clone + per-harness symlink projection.

Layout matches vercel-labs/skills:
  canonical: <root>/.agents/skills/<slug>/   (a real git clone)
  symlinks:  <root>/.<harness>/skills/<slug> -> canonical

Idempotent: re-install on existing canonical fast-forwards the clone;
re-symlink to the right target is a no-op.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    harness_projection_dir,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Raised when install would clobber a conflicting symlink or path."""


def install(
    *,
    parsed: ParsedSource,
    slug: str,
    scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
    env: dict[str, str] | None,
) -> Path:
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if canonical.exists():
        skill_git.fetch(canonical, env=env)
        # Best-effort fast-forward; if the user has local commits this is a no-op.
        try:
            skill_git.merge(canonical, ref=parsed.ref or "main", env=env)
        except skill_git.GitError:
            pass
    else:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(parsed.url, canonical, ref=parsed.ref, env=env)

    for harness in harnesses:
        link_path = harness_projection_dir(harness, slug, scope=scope, home=home, project=project)
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if link_path.is_symlink():
            target = link_path.resolve()
            if target != canonical.resolve():
                raise InstallError(
                    f"conflicting symlink at {link_path}: points to {target}, expected {canonical}"
                )
        elif link_path.exists():
            raise InstallError(
                f"conflicting non-symlink at {link_path}; refusing to overwrite"
            )
        else:
            link_path.symlink_to(canonical)

    return canonical


def uninstall(
    *,
    slug: str,
    scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
) -> None:
    for harness in harnesses:
        link_path = harness_projection_dir(harness, slug, scope=scope, home=home, project=project)
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if canonical.exists():
        shutil.rmtree(canonical)
```

- [ ] **Step 6.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_skill_install.py -v`
Expected: 4 passed.

- [ ] **Step 6.5: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_skill_install.py
git commit -m "feat(skill): canonical clone + per-harness symlink projection"
```

---

## Task 7: CLI `skill add`

**Files:**
- Create: `src/agent_toolkit_cli/commands/skill.py`
- Test: `tests/test_cli/test_cli_skill_add.py`
- Modify: `src/agent_toolkit_cli/cli.py`

Wire `add` end-to-end: parse source → install → write lock entry. Flags: `-g/--global`, `-p/--project`, `--ref`, `--harness` (multi, default = all supported).

- [ ] **Step 7.1: Write the failing test**

```python
# tests/test_cli/test_cli_skill_add.py
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_add_global_writes_lock_and_creates_symlinks(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo", "-g", "--harness", "claude", "--harness", "codex",
    ])
    assert result.exit_code == 0, result.output

    canonical = fake_home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    assert (fake_home / ".claude" / "skills" / "demo").is_symlink()
    assert (fake_home / ".codex" / "skills" / "demo").is_symlink()

    lock = json.loads((fake_home / ".agents" / ".skill-lock.json").read_text())
    assert lock["version"] == 1
    assert "demo" in lock["skills"]
    entry = lock["skills"]["demo"]
    assert entry["source"] == str(git_sandbox.upstream)
    assert entry["sourceType"] in {"git", "local"}
    assert entry["upstreamSha"] and entry["localSha"]
```

- [ ] **Step 7.2: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_cli_skill_add.py -v`
Expected: `no such command 'skill'`.

- [ ] **Step 7.3: Implement the command**

```python
# src/agent_toolkit_cli/commands/skill.py
"""`agent-toolkit-cli skill ...` subcommand group.

Add/update/push/remove/list/status verbs for the skill lock-file model.
Other asset kinds remain on the legacy walker path.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_install import install, uninstall, InstallError
from agent_toolkit_cli.skill_lock import (
    LockEntry,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)
from agent_toolkit_cli.skill_paths import SUPPORTED_HARNESSES, lock_file_path
from agent_toolkit_cli.skill_source import SourceParseError, parse_source


def _scope_and_roots(global_: bool, project: bool, ctx_project: Path | None):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    # Default = project when -p is set OR when no scope flag is supplied.
    # Tests pass -g explicitly; -p is mostly an alias here.
    project_root = ctx_project or Path.cwd()
    return "project", None, project_root


def _harness_tuple(harness: tuple[str, ...] | None) -> tuple[str, ...]:
    if not harness:
        return SUPPORTED_HARNESSES
    for h in harness:
        if h not in SUPPORTED_HARNESSES:
            raise click.UsageError(f"unknown harness: {h}")
    return tuple(harness)


@click.group()
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""


@skill.command("add")
@click.argument("source", required=True)
@click.option("--slug", default=None,
              help="Override the local slug (defaults to repo name).")
@click.option("--ref", default=None, help="Branch or tag to install.")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--harness", multiple=True,
              help=f"Restrict to one or more of: {', '.join(SUPPORTED_HARNESSES)}.")
@click.pass_context
def add(
    ctx: click.Context,
    source: str,
    slug: str | None,
    ref: str | None,
    global_: bool,
    project_flag: bool,
    harness: tuple[str, ...],
) -> None:
    """Add a skill from SOURCE (owner/repo, URL, or local path)."""
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc

    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
        else:
            slug = Path(parsed.url).name
    if ref is not None:
        import dataclasses
        parsed = dataclasses.replace(parsed, ref=ref)

    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    harnesses = _harness_tuple(harness)

    try:
        canonical = install(
            parsed=parsed, slug=slug, scope=scope,
            home=home, project=project_root, harnesses=harnesses, env=None,
        )
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    upstream_sha = skill_git.remote_head_sha(canonical, ref=parsed.ref or "main", env=None)
    local_sha = skill_git.head_sha(canonical, env=None)

    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    source_type = parsed.type
    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=source_type,
        ref=parsed.ref,
        skill_path="SKILL.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))
    click.echo(f"added {slug} <- {parsed.url}")
```

- [ ] **Step 7.4: Register the subgroup**

In `src/agent_toolkit_cli/cli.py`, add the import alongside the existing ones and register it:

```python
from agent_toolkit_cli.commands.skill import skill  # noqa: F401
...
main.add_command(skill)
```

- [ ] **Step 7.5: Run, verify pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_add.py -v`
Expected: 1 passed.

- [ ] **Step 7.6: Confirm `--help` lists the new subgroup**

Run: `uv run agent-toolkit-cli skill --help`
Expected output contains `add`.

- [ ] **Step 7.7: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill.py src/agent_toolkit_cli/cli.py tests/test_cli/test_cli_skill_add.py
git commit -m "feat(skill): add subcommand (clone + symlink + lock entry)"
```

---

## Task 8: CLI `skill list` and `skill status`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill.py`
- Test: `tests/test_cli/test_cli_skill_list.py`, `tests/test_cli/test_cli_skill_status.py`

`list` prints `slug  source  ref  upstream_sha[:7]` from the lock file. `status` computes per-skill state (`clean / dirty / behind / ahead / conflicted`) by running `git status` + `git rev-list --count` against the canonical clone.

- [ ] **Step 8.1: Write the failing `list` test**

```python
# tests/test_cli/test_cli_skill_list.py
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_list_shows_added_skill(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output


def test_skill_list_empty_when_no_lock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    (tmp_path / "empty-home").mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0
    assert "demo" not in result.output
```

- [ ] **Step 8.2: Write the failing `status` test**

```python
# tests/test_cli/test_cli_skill_status.py
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_status_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g", "--harness", "claude"])
    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0
    assert "demo" in result.output and "clean" in result.output


def test_skill_status_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g", "--harness", "claude"])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("self-edit\n")
    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0
    assert "dirty" in result.output
```

- [ ] **Step 8.3: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_cli_skill_list.py tests/test_cli/test_cli_skill_status.py -v`
Expected: `no such command 'list'` / `'status'`.

- [ ] **Step 8.4: Implement `list` and `status`**

Append to `src/agent_toolkit_cli/commands/skill.py`:

```python
@skill.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def list_(ctx: click.Context, global_: bool, project_flag: bool) -> None:
    """List installed skills from the lock file."""
    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    if not lock.skills:
        click.echo("(no skills installed)")
        return
    for slug in sorted(lock.skills):
        e = lock.skills[slug]
        ref = e.ref or "main"
        short = (e.upstream_sha or "")[:7]
        click.echo(f"{slug}\t{e.source}\t{ref}\t{short}")


@skill.command("status")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(
    ctx: click.Context, slugs: tuple[str, ...], global_: bool, project_flag: bool,
) -> None:
    """Show per-skill working-tree status (clean/dirty/behind/ahead/conflicted)."""
    from agent_toolkit_cli.skill_paths import canonical_skill_dir

    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    targets = slugs or tuple(sorted(lock.skills))
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}\t(not in lock)")
            continue
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project_root)
        if not canonical.exists():
            click.echo(f"{slug}\tmissing")
            continue
        wt = skill_git.status(canonical, env=None)
        state = "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        click.echo(f"{slug}\t{state}")
```

- [ ] **Step 8.5: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_list.py tests/test_cli/test_cli_skill_status.py -v`
Expected: 4 passed.

- [ ] **Step 8.6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill.py tests/test_cli/test_cli_skill_list.py tests/test_cli/test_cli_skill_status.py
git commit -m "feat(skill): list and status subcommands"
```

---

## Task 9: CLI `skill update` (fast-forward, merge, conflict surface)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill.py`
- Test: `tests/test_cli/test_cli_skill_update.py`

`update` does `git fetch && git merge --no-edit origin/<ref>`. On clean fast-forward: silent success. On dirty + non-overlap upstream: real merge commit. On conflict: surfaces `<<<<<<<` markers in working copy, exits non-zero with the conflicted slug + file list.

- [ ] **Step 9.1: Write the failing tests**

```python
# tests/test_cli/test_cli_skill_update.py
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner, env, fake_home, upstream_path):
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo", "-g", "--harness", "claude",
    ])


def _advance_upstream(git_sandbox, files: dict[str, str]):
    other = git_sandbox.upstream.parent / "advancer"
    if other.exists():
        import shutil; shutil.rmtree(other)
    subprocess.run(["git", "clone", str(git_sandbox.upstream), str(other)],
                   check=True, env=git_sandbox.env, capture_output=True)
    for name, content in files.items():
        (other / name).write_text(content)
        subprocess.run(["git", "-C", str(other), "add", name],
                       check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "commit", "-m", "advance"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)


def test_update_fast_forwards_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.env, fake_home, git_sandbox.upstream).exit_code == 0
    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert (fake_home / ".agents" / "skills" / "demo" / "NEW.md").exists()


def test_update_surfaces_conflict_and_exits_nonzero(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.env, fake_home, git_sandbox.upstream).exit_code == 0

    canonical = fake_home / ".agents" / "skills" / "demo"
    # Local edit that overlaps with upcoming upstream edit.
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Local edit.\n---\n# demo local\n"
    )
    subprocess.run(["git", "-C", str(canonical), "add", "SKILL.md"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(canonical), "commit", "-m", "local"],
                   check=True, env=git_sandbox.env, capture_output=True)

    _advance_upstream(git_sandbox, {"SKILL.md":
        "---\nname: demo\ndescription: Upstream edit.\n---\n# demo upstream\n"})
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert "<<<<<<<" in (canonical / "SKILL.md").read_text()
```

- [ ] **Step 9.2: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_cli_skill_update.py -v`
Expected: `no such command 'update'`.

- [ ] **Step 9.3: Implement `update`**

Append to `src/agent_toolkit_cli/commands/skill.py`:

```python
@skill.command("update")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def update_cmd(
    ctx: click.Context, slugs: tuple[str, ...], global_: bool, project_flag: bool,
) -> None:
    """Fetch + merge upstream for each skill. Surfaces real git conflicts."""
    from agent_toolkit_cli.skill_paths import canonical_skill_dir

    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    had_conflict = False
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_conflict = True
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project_root)
        ref = entry.ref or "main"
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(f"{slug}: conflict during merge (resolve in working copy)")
            click.echo(exc.stderr)
            had_conflict = True
            continue
        new_local = skill_git.head_sha(canonical, env=None)
        new_upstream = skill_git.remote_head_sha(canonical, ref=ref, env=None)
        entry.local_sha = new_local
        entry.upstream_sha = new_upstream
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")
    if had_conflict:
        ctx.exit(1)
```

- [ ] **Step 9.4: Run tests, verify pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_update.py -v`
Expected: 2 passed.

- [ ] **Step 9.5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill.py tests/test_cli/test_cli_skill_update.py
git commit -m "feat(skill): update subcommand (fast-forward / merge / conflict surface)"
```

---

## Task 10: CLI `skill push` (self-improvement)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill.py`
- Test: `tests/test_cli/test_cli_skill_push.py`

If working tree has uncommitted changes: `git add -A && git commit -m "self-improvement: <ISO timestamp>"`. Then `git push origin <ref>`. No-op when clean.

- [ ] **Step 10.1: Write the failing test**

```python
# tests/test_cli/test_cli_skill_push.py
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_push_publishes_local_edits(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g", "--harness", "claude",
    ])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("---\nname: demo\ndescription: Improved.\n---\n# improved\n")

    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0, result.output

    verify = tmp_path / "verify"
    subprocess.run(["git", "clone", str(git_sandbox.upstream), str(verify)],
                   check=True, env=git_sandbox.env, capture_output=True)
    assert "Improved" in (verify / "SKILL.md").read_text()


def test_push_clean_is_noop(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g", "--harness", "claude",
    ])
    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0
    assert "clean" in result.output.lower() or "nothing" in result.output.lower()
```

- [ ] **Step 10.2: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_cli_skill_push.py -v`
Expected: `no such command 'push'`.

- [ ] **Step 10.3: Implement `push`**

Append to `src/agent_toolkit_cli/commands/skill.py`:

```python
import datetime as _dt
import subprocess as _subprocess


def _commit_dirty(canonical: Path, env: dict[str, str] | None) -> bool:
    """Stage + commit any working-tree changes. Returns True if a commit was created."""
    if skill_git.status(canonical, env=env) == skill_git.GitWorkingTreeStatus.CLEAN:
        return False
    _subprocess.run(
        ["git", "-C", str(canonical), "add", "-A"], check=True, capture_output=True, text=True,
    )
    msg = f"self-improvement: {_dt.datetime.utcnow().isoformat()}Z"
    _subprocess.run(
        ["git", "-C", str(canonical), "commit", "-m", msg],
        check=True, capture_output=True, text=True,
    )
    return True


@skill.command("push")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def push_cmd(
    ctx: click.Context, slugs: tuple[str, ...], global_: bool, project_flag: bool,
) -> None:
    """Commit and push self-improvements upstream. No-op when clean."""
    from agent_toolkit_cli.skill_paths import canonical_skill_dir

    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project_root)
        committed = _commit_dirty(canonical, env=None)
        if not committed:
            click.echo(f"{slug}: clean — nothing to push")
            continue
        skill_git.push(canonical, ref=entry.ref or "main", env=None)
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: pushed")
```

- [ ] **Step 10.4: Run, verify pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_push.py -v`
Expected: 2 passed.

- [ ] **Step 10.5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill.py tests/test_cli/test_cli_skill_push.py
git commit -m "feat(skill): push subcommand (commit + push self-improvements)"
```

---

## Task 11: CLI `skill remove`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill.py`
- Test: `tests/test_cli/test_cli_skill_remove.py`

Removes symlinks, removes canonical clone, removes lock entry. Refuses (exits non-zero) if working tree is dirty unless `--force`.

- [ ] **Step 11.1: Write the failing test**

```python
# tests/test_cli/test_cli_skill_remove.py
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_remove_clears_everything(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
                         "--harness", "claude"])
    result = runner.invoke(main, ["skill", "remove", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert not (fake_home / ".agents" / "skills" / "demo").exists()
    assert not (fake_home / ".claude" / "skills" / "demo").exists()
    import json
    lock = json.loads((fake_home / ".agents" / ".skill-lock.json").read_text())
    assert "demo" not in lock["skills"]


def test_remove_refuses_dirty_without_force(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
                         "--harness", "claude"])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("uncommitted\n")
    result = runner.invoke(main, ["skill", "remove", "demo", "-g"])
    assert result.exit_code != 0
    assert "dirty" in result.output.lower()
    assert canonical.exists()  # not deleted
```

- [ ] **Step 11.2: Run, confirm failure**

Run: `uv run pytest tests/test_cli/test_cli_skill_remove.py -v`
Expected: `no such command 'remove'`.

- [ ] **Step 11.3: Implement `remove`**

Append to `src/agent_toolkit_cli/commands/skill.py`:

```python
@skill.command("remove")
@click.argument("slugs", nargs=-1, required=True)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--force", is_flag=True, help="Remove even if working tree is dirty.")
@click.pass_context
def remove_cmd(
    ctx: click.Context, slugs: tuple[str, ...],
    global_: bool, project_flag: bool, force: bool,
) -> None:
    """Remove a skill: canonical clone, projections, and lock entry."""
    from agent_toolkit_cli.skill_paths import canonical_skill_dir

    scope, home, project_root = _scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    had_dirty = False
    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            continue
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project_root)
        if canonical.exists() and not force:
            wt = skill_git.status(canonical, env=None)
            if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(f"{slug}: dirty — push or use --force to discard")
                had_dirty = True
                continue
        uninstall(slug=slug, scope=scope, home=home, project=project_root,
                  harnesses=SUPPORTED_HARNESSES)
        lock = remove_entry(lock, slug)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: removed")
    if had_dirty:
        ctx.exit(1)
```

- [ ] **Step 11.4: Run, verify pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_remove.py -v`
Expected: 2 passed.

- [ ] **Step 11.5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill.py tests/test_cli/test_cli_skill_remove.py
git commit -m "feat(skill): remove subcommand with dirty-tree guard"
```

---

## Task 12: skills.sh interop smoke test

**Files:**
- Create: `tests/test_cli/test_skill_interop.py`

Confirms that a lock file written by our CLI is parseable by `npx skills list`, and that a repo populated by our `skill add` is installable by `npx skills add` against the same source. Skipped automatically if `npx` is not on PATH.

- [ ] **Step 12.1: Write the failing test**

```python
# tests/test_cli/test_skill_interop.py
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


_HAVE_NPX = shutil.which("npx") is not None
skip_no_npx = pytest.mark.skipif(not _HAVE_NPX, reason="npx not on PATH")


@skip_no_npx
def test_npx_skills_list_reads_our_lock(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("DISABLE_TELEMETRY", "1")

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    # Our global lock is `~/.agents/.skill-lock.json` (skills.sh shape).
    # Their `list -g` reads that same file.
    proc = subprocess.run(
        ["npx", "--yes", "skills@latest", "ls", "-g"],
        capture_output=True, text=True,
        env={**git_sandbox.env, "HOME": str(fake_home), "DISABLE_TELEMETRY": "1"},
        timeout=120,
    )
    # The upstream CLI must at least exit cleanly and mention the slug.
    assert proc.returncode == 0, proc.stderr
    assert "demo" in proc.stdout
```

- [ ] **Step 12.2: Run**

Run: `uv run pytest tests/test_cli/test_skill_interop.py -v`
Expected: either PASS (if `npx` is installed) or SKIPPED.

If you see UNEXPECTED FAILURES instead of PASS/SKIP, the most likely cause is that the upstream CLI's global lock path uses `$XDG_STATE_HOME` instead of `$HOME/.agents/.skill-lock.json`. In that case, also set `XDG_STATE_HOME` in the test env to point at `$HOME/.local/state` so both CLIs agree.

- [ ] **Step 12.3: Commit**

```bash
git add tests/test_cli/test_skill_interop.py
git commit -m "test(skill): skills.sh interop smoke test (npx skills ls)"
```

---

## Task 13: TUI skill state reader

**Files:**
- Create: `src/agent_toolkit_tui/skill_state.py`
- Test: `tests/test_tui/test_skill_state.py`

Reads the lock file + computes per-skill `clean/dirty` (extension to `behind/ahead/conflicted` is a follow-on; minimum viable is the same two states the CLI exposes). Returns `list[SkillRow]`.

- [ ] **Step 13.1: Write the failing tests**

```python
# tests/test_tui/test_skill_state.py
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_tui.skill_state import SkillRow, build_skill_rows


def test_build_skill_rows_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    rows = build_skill_rows(scope="global", home=fake_home, project=None)
    assert rows == [SkillRow(
        slug="demo", source=str(git_sandbox.upstream),
        ref="main", state="clean",
    )]


def test_build_skill_rows_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    (fake_home / ".agents" / "skills" / "demo" / "SKILL.md").write_text("edit\n")
    rows = build_skill_rows(scope="global", home=fake_home, project=None)
    assert rows[0].state == "dirty"


def test_build_skill_rows_empty(tmp_path: Path):
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    assert rows == []
```

- [ ] **Step 13.2: Run, confirm failure**

Run: `uv run pytest tests/test_tui/test_skill_state.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 13.3: Write minimal implementation**

```python
# src/agent_toolkit_tui/skill_state.py
"""Data model for the TUI's skill tab.

Reads `.skill-lock.json` (or `skills-lock.json`) and queries `git status`
on each canonical clone to produce SkillRow records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path

State = Literal["clean", "dirty", "missing"]


@dataclass(frozen=True)
class SkillRow:
    slug: str
    source: str
    ref: str
    state: State


def build_skill_rows(*, scope, home: Path | None, project: Path | None) -> list[SkillRow]:
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    rows: list[SkillRow] = []
    for slug in sorted(lock.skills):
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
        if not canonical.exists():
            state: State = "missing"
        else:
            wt = skill_git.status(canonical, env=None)
            state = "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "main", state=state,
        ))
    return rows
```

- [ ] **Step 13.4: Run, verify pass**

Run: `uv run pytest tests/test_tui/test_skill_state.py -v`
Expected: 3 passed.

- [ ] **Step 13.5: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py tests/test_tui/test_skill_state.py
git commit -m "feat(tui): skill_state reader (lock + per-skill git status)"
```

---

## Task 14: TUI skill grid widget

**Files:**
- Create: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Test: `tests/test_tui/test_skill_grid.py`

Minimal Textual widget: DataTable with columns `slug | source | ref | state`. Renders from `list[SkillRow]`. State column color-coded (`clean` green, `dirty` yellow, `missing` red).

- [ ] **Step 14.1: Write the failing test**

```python
# tests/test_tui/test_skill_grid.py
import pytest
from textual.app import App, ComposeResult

from agent_toolkit_tui.skill_state import SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_skill_grid_renders_rows():
    rows = [
        SkillRow(slug="journal", source="ajanderson1/journal", ref="main", state="clean"),
        SkillRow(slug="aj-workflow", source="ajanderson1/aj-workflow", ref="main", state="dirty"),
    ]

    class _Harness(App):
        def compose(self) -> ComposeResult:
            yield SkillGrid(rows, id="skill-grid")

    async with _Harness().run_test() as pilot:
        grid = pilot.app.query_one(SkillGrid)
        assert grid.row_count == 2
        cells = grid.row_slugs
        assert cells == ["aj-workflow", "journal"]  # alpha-sorted


@pytest.mark.asyncio
async def test_skill_grid_empty():
    class _Harness(App):
        def compose(self) -> ComposeResult:
            yield SkillGrid([], id="skill-grid")

    async with _Harness().run_test() as pilot:
        grid = pilot.app.query_one(SkillGrid)
        assert grid.row_count == 0
```

- [ ] **Step 14.2: Run, confirm failure**

Run: `uv run pytest tests/test_tui/test_skill_grid.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 14.3: Write minimal implementation**

```python
# src/agent_toolkit_tui/widgets/skill_grid.py
"""DataTable widget for the TUI's skill tab.

Renders SkillRow records. State column color-coded.

NOTE: avoid method names beginning with `_render_*` — they collide with
Textual internal flags and produce 'bool not callable' errors from
compose() (see memory feedback_textual_render_methods.md).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import SkillRow

_STATE_MARKUP = {
    "clean":   "[green]clean[/]",
    "dirty":   "[yellow]dirty[/]",
    "missing": "[red]missing[/]",
}


class SkillGrid(Vertical):
    """Skill tab grid: one row per locked skill."""

    DEFAULT_CSS = """
    SkillGrid { border: round $primary; }
    SkillGrid DataTable { height: 1fr; }
    """

    def __init__(self, rows: list[SkillRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def compose(self) -> ComposeResult:
        table: DataTable = DataTable(id="skill-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("slug", "source", "ref", "state")
        for r in self._rows:
            table.add_row(r.slug, r.source, r.ref, _STATE_MARKUP.get(r.state, r.state))
        yield table
```

- [ ] **Step 14.4: Run, verify pass**

Run: `uv run pytest tests/test_tui/test_skill_grid.py -v`
Expected: 2 passed.

- [ ] **Step 14.5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid.py
git commit -m "feat(tui): SkillGrid widget for lock-file-driven skill tab"
```

---

## Task 15: TUI integration — route skill kind to new path

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Test: `tests/test_tui/test_app.py` (extend)

When the kinds sidebar selects `skill`, the content area mounts `SkillGrid(build_skill_rows(...))` instead of the existing `AssetGrid`. All other kinds still mount `AssetGrid`. Toggle scope (global/project) re-reads from the appropriate lock file.

- [ ] **Step 15.1: Read current app.py compose() / mount logic**

Run: `grep -n -E "compose|mount|AssetGrid|KindChanged" src/agent_toolkit_tui/app.py | head -30`
Expected: shows where the right-pane widget is mounted and how `KindChanged` is handled.

- [ ] **Step 15.2: Write the failing integration test**

Add to `tests/test_tui/test_app.py` (append at end):

```python
import pytest
from click.testing import CliRunner
from agent_toolkit_cli.cli import main as cli_main


@pytest.mark.asyncio
async def test_app_skill_tab_renders_lock_rows(git_sandbox, tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(cli_main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])

    from agent_toolkit_tui.app import AgentToolkitTUI  # type: ignore[attr-defined]
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid
    app = AgentToolkitTUI(scope="global")
    async with app.run_test() as pilot:
        # Sidebar default may differ; explicitly select skill kind.
        await pilot.app.action_select_kind("skill")  # see app changes below
        await pilot.pause()
        grid = pilot.app.query_one(SkillGrid)
        assert grid.row_slugs == ["demo"]
```

- [ ] **Step 15.3: Run, confirm failure**

Run: `uv run pytest tests/test_tui/test_app.py -v -k test_app_skill_tab_renders_lock_rows`
Expected: fails because `SkillGrid` is not mounted and/or `action_select_kind` does not exist.

- [ ] **Step 15.4: Modify `app.py`**

Edit `src/agent_toolkit_tui/app.py` to:

1. Add the import `from agent_toolkit_tui.skill_state import build_skill_rows` and `from agent_toolkit_tui.widgets.skill_grid import SkillGrid` near other widget imports.
2. Add a single accessor `action_select_kind(self, kind: str)` that posts the same `KindChanged` message the sidebar would, then awaits a `pause` (Textual built-in) so tests can drive it without keyboard.
3. In the handler for `KindChanged`, branch on `message.kind`:
   - If `"skill"`: detach any currently-mounted right-pane widget, mount `SkillGrid(build_skill_rows(scope=self._scope, home=Path.home() if self._scope=="global" else None, project=self._project if self._scope=="project" else None))`.
   - Else: existing path (mount `AssetGrid`).

Concrete patch:

```python
# At top of app.py with other imports:
from pathlib import Path
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets.skill_grid import SkillGrid

# Inside the App class, somewhere alongside other on_* handlers:
async def action_select_kind(self, kind: str) -> None:
    """Test-driving helper. Posts KindChanged so the normal handler runs."""
    self.post_message(KindChanged(kind))

# Replace whatever code currently handles KindChanged (find via:
#   grep -n KindChanged src/agent_toolkit_tui/app.py
# ) with branching mount:
async def on_kind_changed(self, message: KindChanged) -> None:
    container = self.query_one("#content-pane", expect_type=Vertical)
    await container.remove_children()
    if message.kind == "skill":
        home = Path.home() if self._scope == "global" else None
        project = self._project if self._scope == "project" else None
        rows = build_skill_rows(scope=self._scope, home=home, project=project)
        await container.mount(SkillGrid(rows, id="skill-grid"))
    else:
        # Existing AssetGrid path — preserve current behavior.
        await container.mount(AssetGrid(self._state, id="asset-grid"))
        self.query_one(AssetGrid).set_kind(message.kind)
```

If the existing `app.py` uses a different container id or mount pattern, adapt the patch accordingly — the principle is: **branch by `message.kind == "skill"` and pick `SkillGrid` vs `AssetGrid`**. Do NOT delete the AssetGrid mount path; it serves the six non-migrating kinds.

- [ ] **Step 15.5: Run the new test + the existing TUI test suite**

Run: `uv run pytest tests/test_tui/ -v`
Expected: all TUI tests pass, including the new skill-tab test.

- [ ] **Step 15.6: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_app.py
git commit -m "feat(tui): route skill kind to SkillGrid (lock-file-driven)"
```

---

## Task 16: Full suite + lint + manual POC

- [ ] **Step 16.1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (existing 991 + the new ones added across tasks 1–15).

- [ ] **Step 16.2: Run ruff / lint**

Run: `uv run ruff check src/ tests/`
Expected: clean.

- [ ] **Step 16.3: Manual POC against a throwaway GitHub repo**

```bash
gh repo create ajanderson1/test-migration-skill --private --add-readme=false
mkdir -p /tmp/poc && cd /tmp/poc
git init --initial-branch=main
cat > SKILL.md <<'EOF'
---
name: test-migration-skill
description: POC for the skill lock-file migration.
---
# test-migration-skill
EOF
git add SKILL.md
git commit -m "seed"
git remote add origin git@github.com:ajanderson1/test-migration-skill.git
git push -u origin main

# Now exercise every verb:
uv run agent-toolkit-cli skill add ajanderson1/test-migration-skill -g --harness claude
uv run agent-toolkit-cli skill list -g
uv run agent-toolkit-cli skill status -g

# Edit the canonical clone:
echo "self-improvement!" >> ~/.agents/skills/test-migration-skill/SKILL.md
uv run agent-toolkit-cli skill status -g    # expect: dirty
uv run agent-toolkit-cli skill push test-migration-skill -g
uv run agent-toolkit-cli skill status -g    # expect: clean

# Advance upstream from elsewhere, then pull:
# (push a change directly via gh / web UI, or from another clone)
uv run agent-toolkit-cli skill update test-migration-skill -g

uv run agent-toolkit-cli skill remove test-migration-skill -g
```

Expected: every command exits 0; final filesystem under `~/.agents/skills/` and `~/.claude/skills/` is empty for `test-migration-skill`; lock file no longer lists it.

- [ ] **Step 16.4: Write the user-facing docs**

Create `docs/agent-toolkit/skill-lock.md` with three sections:
1. **Overview** — what the `skill` subgroup does, the lock-file model, the `.agents/skills/` canonical + per-harness symlink layout.
2. **Command reference** — one paragraph per verb (`add / update / push / remove / list / status`), with examples copied from the manual POC above.
3. **Lock file format** — annotated example showing every field (`source`, `sourceType`, `ref`, `skillPath`, `upstreamSha`, `localSha`).

- [ ] **Step 16.5: Commit docs**

```bash
git add docs/agent-toolkit/skill-lock.md
git commit -m "docs(skill): user-facing reference for skill subcommand and lock format"
```

- [ ] **Step 16.6: Push, open PR**

```bash
git push -u origin <your-branch-name>
gh pr create --title "feat(skill): lock-file migration (Option A, skills only)" --body "$(cat <<'EOF'
## Summary
- Adds `agent-toolkit-cli skill {add,update,push,remove,list,status}` subgroup.
- Introduces `skills-lock.json` (project) and `.skill-lock.json` (global), bit-compatible with `vercel-labs/skills` schema.
- Canonical clone at `~/.agents/skills/<slug>/` with per-harness symlinks.
- Merge-aware `update` preserves agent self-improvements; real `git` conflicts surface in the working copy.

Spec: `docs/superpowers/specs/2026-05-21-agent-toolkit-lock-file-migration-design.md`

Other six asset kinds are untouched — Phase 2 territory.

## Test plan
- [ ] `uv run pytest -q` — full suite
- [ ] `uv run ruff check`
- [ ] Manual POC against `ajanderson1/test-migration-skill` (steps in plan task 16.3)
- [ ] `npx skills@latest ls -g` against the lock file we wrote (skipped in CI if `npx` not present)
EOF
)"
```

---

## A note on the sidecar (spec §7)

The spec calls for eliminating the `.toolkit.yaml` sidecar for skills, with metadata moving entirely into `SKILL.md` frontmatter. This plan delivers that **passively**: the new `skill add` flow never authors a sidecar (the POC skill in Task 16.3 ships only `SKILL.md`). Existing sidecars on skills still in the monorepo remain untouched and are removed during the future extraction sweep that is explicitly parked below.

## Out of scope (parked, will appear in follow-on specs)

- Migrating any non-skill asset kind. The six other kinds (agent, command, mcp, hook, plugin, pi-extension) remain on the existing walker + sidecar model.
- Auto-push hook (end-of-session self-improvement publish).
- Extracting real existing skills from the monorepo into per-skill repos. This plan ships the *mechanism* and validates it against a throwaway POC; the extraction sweep is a separate, more mechanical task.
- Retiring the walker's skill discovery path. Stays in place until the extraction sweep completes; removal is a single follow-up commit.
- `behind`/`ahead`/`conflicted` granularity in the TUI state column. Today: `clean | dirty | missing`. Refinement is a small follow-on if needed.

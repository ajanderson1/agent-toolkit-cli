# skill add: monorepo skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent-toolkit-cli skill add` install one named skill from a parent monorepo via `--skill <name>`, `owner/repo/<subpath>`, or `https://www.skills.sh/<owner>/<repo>/<skill>` — with a lock entry byte-compatible with `npx skills add`.

**Architecture:** Parser learns three new input shapes (third path segment, `--skill`, skills.sh URL) and adds `skill_name` to `ParsedSource`. `LockEntry` gains `parent_url` and `read_only`. `skill add` detects monorepo input shapes and clones the parent into `library_root()/_parents/<owner>/<repo>[@<ref>]/`, then symlinks the library canonical at `library_root()/<slug>/` into `<parent>/<subpath>/` (copy fallback if symlinks fail). `update` for monorepo entries pulls the parent; `push` refuses monorepo entries with a message naming `parent_url`.

**Tech Stack:** Python 3.11+, Click 8.x, pytest (existing test layout), uv (already running pre-commit pytest in worktree).

---

## Task 1: Fixture — monorepo parent repo

The integration tests need a parent repo with two `SKILL.md` files at different subpaths and distinguishable `name:` frontmatter. Build it once; reuse from add and update tests.

**Files:**
- Create: `tests/fixtures/monorepo_skills/.gitkeep`
- Create: `tests/fixtures/monorepo_skills/mkdocs/SKILL.md`
- Create: `tests/fixtures/monorepo_skills/docker/SKILL.md`
- Create: `tests/fixtures/monorepo_skills/README.md`

- [ ] **Step 1: Create the fixture tree on disk**

Create `tests/fixtures/monorepo_skills/mkdocs/SKILL.md`:

```markdown
---
name: mkdocs
description: MkDocs site scaffolding skill (fixture, not a real skill).
---
# mkdocs
fixture content
```

Create `tests/fixtures/monorepo_skills/docker/SKILL.md`:

```markdown
---
name: docker
description: Docker scaffolding skill (fixture, not a real skill).
---
# docker
fixture content
```

Create `tests/fixtures/monorepo_skills/README.md`:

```markdown
# Monorepo skills fixture

Used by `test_skill_add_monorepo.py` and `test_skill_update_monorepo.py`.
Each subfolder is a self-contained skill; the parent is just the wrapper.
```

`.gitkeep` keeps the directory present even if all .md files are renamed later.

- [ ] **Step 2: Verify fixture is staged**

```bash
ls tests/fixtures/monorepo_skills/
git status --short tests/fixtures/monorepo_skills/
```
Expected: three new files + `.gitkeep` listed as untracked.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/monorepo_skills/
git commit -m "test(fixtures): monorepo parent with mkdocs + docker SKILL.md"
```

---

## Task 2: Parser — `skill_name` field, third-segment shorthand, skills.sh URL, ambiguity guard

**Files:**
- Modify: `src/agent_toolkit_cli/skill_source.py`
- Create: `tests/test_cli/test_skill_source_monorepo.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli/test_skill_source_monorepo.py`:

```python
"""Parser coverage for monorepo input shapes (issue #162)."""
import pytest
from agent_toolkit_cli.skill_source import (
    ParsedSource, SourceParseError, parse_source,
)


def test_third_segment_shorthand_is_subpath():
    s = parse_source("vamseeachanta/workspace-hub/mkdocs")
    assert s.type == "github"
    assert s.owner_repo == "vamseeachanta/workspace-hub"
    assert s.subpath == "mkdocs"
    assert s.skill_name is None
    assert s.url == "https://github.com/vamseeachanta/workspace-hub"


def test_third_segment_shorthand_with_nested_subpath():
    s = parse_source("o/r/sub/dir")
    assert s.owner_repo == "o/r"
    assert s.subpath == "sub/dir"


def test_skills_sh_url_translates_to_github_with_skill_name():
    s = parse_source("https://www.skills.sh/vamseeachanta/workspace-hub/mkdocs")
    assert s.type == "github"
    assert s.url == "https://github.com/vamseeachanta/workspace-hub"
    assert s.owner_repo == "vamseeachanta/workspace-hub"
    assert s.skill_name == "mkdocs"
    assert s.subpath is None
    assert s.ref is None


def test_skills_sh_url_bare_host_also_works():
    # No www.
    s = parse_source("https://skills.sh/o/r/skill-name")
    assert s.skill_name == "skill-name"
    assert s.owner_repo == "o/r"


def test_skills_sh_url_missing_skill_segment_rejected():
    with pytest.raises(SourceParseError):
        parse_source("https://www.skills.sh/o/r")


def test_github_tree_ref_subpath_still_works():
    # Unchanged: regression guard.
    s = parse_source("https://github.com/o/r/tree/main/skills/foo")
    assert s.owner_repo == "o/r"
    assert s.ref == "main"
    assert s.subpath == "skills/foo"
    assert s.skill_name is None


def test_shorthand_third_segment_traversal_rejected():
    with pytest.raises(SourceParseError):
        parse_source("o/r/../bad")


def test_existing_owner_repo_unchanged_shape():
    # Regression: two-segment shorthand still works.
    s = parse_source("o/r")
    assert s.owner_repo == "o/r"
    assert s.subpath is None
    assert s.skill_name is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli/test_skill_source_monorepo.py -v
```
Expected: collection errors or assertion failures — `ParsedSource` has no `skill_name`; third-segment shorthand is rejected; skills.sh URL parses as `github` but doesn't extract `skill_name`.

- [ ] **Step 3: Add `skill_name` field to `ParsedSource`**

Edit `src/agent_toolkit_cli/skill_source.py`:

```python
@dataclass(frozen=True)
class ParsedSource:
    type: SourceType
    url: str
    owner_repo: str | None
    ref: str | None
    subpath: str | None
    skill_name: str | None = None
```

Update the three `ParsedSource(...)` constructions in this file to pass `skill_name=None` explicitly (frozen dataclasses with defaults are fine, but explicit is clearer in tests).

- [ ] **Step 4: Loosen shorthand regex to accept third segment**

Replace the current shorthand block:

```python
    # GitHub shorthand: owner/repo (no scheme, no leading dot/slash, exactly one slash).
    if re.fullmatch(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", input_):
        owner_repo = input_
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=None,
            subpath=None,
        )
```

with this:

```python
    # GitHub shorthand: owner/repo[/subpath]. owner and repo are tight;
    # subpath is anything that doesn't start with '/' and doesn't include '..'.
    m = re.fullmatch(
        r"(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+)(?:/(?P<subpath>[^\s].*))?",
        input_,
    )
    if m:
        owner_repo = f"{m['owner']}/{m['repo']}"
        subpath = _sanitize_subpath(m["subpath"]) if m["subpath"] else None
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=None,
            subpath=subpath,
            skill_name=None,
        )
```

- [ ] **Step 5: Add skills.sh URL handler inside `_parse_https`**

Insert at the top of `_parse_https`, immediately after `path = parsed.path.lstrip("/").removesuffix(".git")`:

```python
    if host in ("skills.sh", "www.skills.sh"):
        parts = path.split("/")
        if len(parts) < 3 or not all(parts[:3]):
            raise SourceParseError(
                f"skills.sh URL needs /<owner>/<repo>/<skill>: {url}"
            )
        owner, repo, skill_name = parts[0], parts[1], parts[2]
        owner_repo = f"{owner}/{repo}"
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=None,
            subpath=None,
            skill_name=skill_name,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_skill_source_monorepo.py -v
uv run pytest tests/test_cli/test_skill_source.py -v
```
Expected: all new monorepo tests PASS; existing parser tests still PASS (regression check).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/skill_source.py tests/test_cli/test_skill_source_monorepo.py
git commit -m "feat(skill-source): #162 monorepo input shapes — subpath, skills.sh, skill_name"
```

---

## Task 3: Lock — `parent_url` and `read_only` fields, v1 + v3 round-trip

**Files:**
- Modify: `src/agent_toolkit_cli/skill_lock.py`
- Create: `tests/test_cli/test_skill_lock_monorepo.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli/test_skill_lock_monorepo.py`:

```python
"""Round-trip parent_url + read_only through v1 and v3 lock formats."""
import json
from pathlib import Path

from agent_toolkit_cli.skill_lock import (
    LockEntry, LockFile, add_entry, read_lock, write_lock,
)


def test_v1_writes_parent_url_and_read_only(tmp_path: Path):
    entry = LockEntry(
        source="vamseeachanta/workspace-hub",
        source_type="github",
        ref="main",
        skill_path="mkdocs",
        parent_url="https://github.com/vamseeachanta/workspace-hub",
        read_only=True,
    )
    lock = add_entry(LockFile(version=1, skills={}), "mkdocs", entry)
    path = tmp_path / "skills-lock.json"
    write_lock(path, lock)
    raw = json.loads(path.read_text())
    assert raw["skills"]["mkdocs"]["parentUrl"] == (
        "https://github.com/vamseeachanta/workspace-hub"
    )
    assert raw["skills"]["mkdocs"]["readOnly"] is True


def test_v1_round_trip_preserves_new_fields(tmp_path: Path):
    entry = LockEntry(
        source="o/r", source_type="github", ref="main",
        skill_path="sub", parent_url="https://github.com/o/r",
        read_only=True,
    )
    lock = add_entry(LockFile(version=1, skills={}), "sub", entry)
    path = tmp_path / "skills-lock.json"
    write_lock(path, lock)
    read = read_lock(path)
    e2 = read.skills["sub"]
    assert e2.parent_url == "https://github.com/o/r"
    assert e2.read_only is True
    assert e2.skill_path == "sub"


def test_v3_round_trip_preserves_new_fields(tmp_path: Path):
    # Seed a v3 file on disk to lock the version through read_lock/write_lock.
    raw = {
        "version": 3,
        "skills": {
            "mkdocs": {
                "source": "o/r",
                "sourceType": "github",
                "sourceUrl": "https://github.com/o/r",
                "skillPath": "mkdocs",
                "parentUrl": "https://github.com/o/r",
                "readOnly": True,
                "installedAt": "2026-05-21T00:00:00Z",
                "updatedAt": "2026-05-21T00:00:00Z",
            }
        },
    }
    path = tmp_path / ".skill-lock.json"
    path.write_text(json.dumps(raw))
    read = read_lock(path)
    assert read.version == 3
    e = read.skills["mkdocs"]
    assert e.parent_url == "https://github.com/o/r"
    assert e.read_only is True
    write_lock(path, read)
    raw2 = json.loads(path.read_text())
    assert raw2["skills"]["mkdocs"]["parentUrl"] == "https://github.com/o/r"
    assert raw2["skills"]["mkdocs"]["readOnly"] is True


def test_read_only_defaults_to_false_when_absent(tmp_path: Path):
    raw = {
        "version": 1,
        "skills": {
            "x": {"source": "o/r", "sourceType": "github", "skillPath": "SKILL.md"}
        },
    }
    path = tmp_path / "skills-lock.json"
    path.write_text(json.dumps(raw))
    read = read_lock(path)
    assert read.skills["x"].read_only is False
    assert read.skills["x"].parent_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli/test_skill_lock_monorepo.py -v
```
Expected: `LockEntry.__init__()` rejects `parent_url=` / `read_only=` (no such fields). Read returns entries with no such attribute.

- [ ] **Step 3: Add `parent_url` and `read_only` to `LockEntry`**

Edit `src/agent_toolkit_cli/skill_lock.py`:

```python
@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    skill_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    parent_url: str | None = None
    read_only: bool = False
    extras: dict[str, object] = field(default_factory=dict)
```

- [ ] **Step 4: Wire v1 read + write**

Update `_V1_ENTRY_FIELDS` set:

```python
_V1_ENTRY_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "upstreamSha", "localSha",
    "parentUrl", "readOnly",
}
```

Update `_entry_from_dict_v1`:

```python
def _entry_from_dict_v1(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _V1_ENTRY_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        upstream_sha=d.get("upstreamSha"),
        local_sha=d.get("localSha"),
        parent_url=d.get("parentUrl"),
        read_only=bool(d.get("readOnly", False)),
        extras=extras,
    )
```

Update `_entry_to_dict_v1` — insert after the existing optional fields, before the `extras` loop:

```python
def _entry_to_dict_v1(e: LockEntry) -> dict:
    out: dict[str, object] = {"source": e.source, "sourceType": e.source_type}
    if e.ref is not None:
        out["ref"] = e.ref
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.upstream_sha is not None:
        out["upstreamSha"] = e.upstream_sha
    if e.local_sha is not None:
        out["localSha"] = e.local_sha
    if e.parent_url is not None:
        out["parentUrl"] = e.parent_url
    if e.read_only:
        out["readOnly"] = True
    for k, v in e.extras.items():
        if k in {"sourceUrl", "installedAt", "updatedAt", "skillFolderHash",
                 "pluginName"}:
            continue
        out[k] = v
    return out
```

- [ ] **Step 5: Wire v3 read + write**

Update `_V3_ENTRY_FIELDS` set:

```python
_V3_ENTRY_FIELDS = {
    "source", "sourceType", "sourceUrl", "ref", "skillPath",
    "skillFolderHash", "installedAt", "updatedAt", "pluginName",
    "parentUrl", "readOnly",
}
```

Update `_entry_from_dict_v3` to add the two new fields, mirroring v1:

```python
def _entry_from_dict_v3(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _V3_ENTRY_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        upstream_sha=d.get("skillFolderHash"),
        local_sha=None,
        parent_url=d.get("parentUrl"),
        read_only=bool(d.get("readOnly", False)),
        extras={
            **extras,
            **({"sourceUrl": d["sourceUrl"]} if "sourceUrl" in d else {}),
            **({"installedAt": d["installedAt"]} if "installedAt" in d else {}),
            **({"updatedAt": d["updatedAt"]} if "updatedAt" in d else {}),
            **({"pluginName": d["pluginName"]} if "pluginName" in d else {}),
        },
    )
```

Update `_entry_to_dict_v3` — insert the two new fields after `skill_path` and before timestamps:

```python
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.parent_url is not None:
        out["parentUrl"] = e.parent_url
    if e.read_only:
        out["readOnly"] = True
    if e.upstream_sha is not None:
        out["skillFolderHash"] = e.upstream_sha
```

(The full surrounding block stays the same; only these three new `if` clauses are inserted.)

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_cli/test_skill_lock_monorepo.py tests/test_cli/test_skill_lock.py -v
```
Expected: new tests PASS, all existing lock tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/skill_lock.py tests/test_cli/test_skill_lock_monorepo.py
git commit -m "feat(skill-lock): #162 parentUrl + readOnly fields (v1 + v3 round-trip)"
```

---

## Task 4: Path helper + symlink-with-copy-fallback utility

`skill_paths.parent_clone_path()` and a tiny `skill_install._symlink_or_copy()` helper. Both are leaf utilities used by Task 5.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py`
- Modify: `src/agent_toolkit_cli/skill_install.py`
- Modify: `tests/test_cli/test_skill_paths.py`
- Create: `tests/test_cli/test_skill_install_symlink_fallback.py`

- [ ] **Step 1: Write the failing path-helper test**

Append to `tests/test_cli/test_skill_paths.py`:

```python
import os


def test_parent_clone_path_no_ref(monkeypatch, tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "skills"))
    p = parent_clone_path("vamseeachanta", "workspace-hub", ref=None)
    assert p == tmp_path / "skills" / "_parents" / "vamseeachanta" / "workspace-hub"


def test_parent_clone_path_with_ref(monkeypatch, tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "skills"))
    p = parent_clone_path("o", "r", ref="v1.2.3")
    assert p.name == "r@v1.2.3"
    assert p.parent.name == "o"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_cli/test_skill_paths.py -v -k parent_clone_path
```
Expected: ImportError — `parent_clone_path` doesn't exist.

- [ ] **Step 3: Implement `parent_clone_path`**

Add to `src/agent_toolkit_cli/skill_paths.py`, after `library_skill_path`:

```python
def parent_clone_path(
    owner: str, repo: str, *, ref: str | None,
    env: dict[str, str] | None = None,
) -> Path:
    """Where a monorepo parent is cloned, shared across all skills from it.

    Lives at <library_root>/_parents/<owner>/<repo>[@<ref>]/ so the cache is
    inside the AGENT_TOOLKIT_SKILLS_ROOT blast radius and travels with
    --toolkit-repo overrides.
    """
    leaf = repo if ref is None else f"{repo}@{ref}"
    return library_root(env) / "_parents" / owner / leaf
```

- [ ] **Step 4: Run path tests**

```bash
uv run pytest tests/test_cli/test_skill_paths.py -v
```
Expected: all PASS.

- [ ] **Step 5: Write the failing symlink-fallback test**

Create `tests/test_cli/test_skill_install_symlink_fallback.py`:

```python
"""_symlink_or_copy creates a symlink when possible; falls back to copy."""
from pathlib import Path

from agent_toolkit_cli.skill_install import _symlink_or_copy


def test_symlink_or_copy_creates_symlink(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("hi")
    dest = tmp_path / "dest"

    mode = _symlink_or_copy(src, dest)
    assert mode == "symlink"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert (dest / "f.txt").read_text() == "hi"


def test_symlink_or_copy_falls_back_to_copy(monkeypatch, tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("hi")
    dest = tmp_path / "dest"

    # Force the fallback by making symlink_to raise.
    def raise_oserror(self, target, target_is_directory=False):
        raise OSError("simulated platform refusal")
    monkeypatch.setattr(Path, "symlink_to", raise_oserror)

    mode = _symlink_or_copy(src, dest)
    assert mode == "copy"
    assert not dest.is_symlink()
    assert dest.is_dir()
    assert (dest / "f.txt").read_text() == "hi"


def test_symlink_or_copy_refuses_to_overwrite(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    import pytest
    from agent_toolkit_cli.skill_install import InstallError
    with pytest.raises(InstallError):
        _symlink_or_copy(src, dest)
```

- [ ] **Step 6: Run to verify failure**

```bash
uv run pytest tests/test_cli/test_skill_install_symlink_fallback.py -v
```
Expected: ImportError — `_symlink_or_copy` doesn't exist.

- [ ] **Step 7: Implement `_symlink_or_copy`**

Add to `src/agent_toolkit_cli/skill_install.py` (near the top, after `InstallError`):

```python
def _symlink_or_copy(src: Path, dest: Path) -> str:
    """Materialise `dest` to refer to `src`. Try symlink; fall back to copy.

    Returns 'symlink' or 'copy' so the caller can record the materialisation
    mode in the lock entry's extras (relevant for `update`: copy-mode needs
    re-copy, symlink-mode just needs the parent to be re-pulled).
    """
    if dest.exists() or dest.is_symlink():
        raise InstallError(
            f"{dest}: refusing to overwrite existing path"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return "symlink"
    except OSError:
        shutil.copytree(src, dest)
        return "copy"
```

(Note: `shutil` is already imported at the top of `skill_install.py`.)

- [ ] **Step 8: Run all new tests**

```bash
uv run pytest tests/test_cli/test_skill_install_symlink_fallback.py tests/test_cli/test_skill_paths.py -v
```
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py src/agent_toolkit_cli/skill_install.py tests/test_cli/test_skill_paths.py tests/test_cli/test_skill_install_symlink_fallback.py
git commit -m "feat(skill): #162 parent_clone_path + _symlink_or_copy utilities"
```

---

## Task 5: `skill add` — monorepo path + `--skill` flag

The integration. When `parsed.subpath` or `parsed.skill_name` is set, `skill add` clones the parent and symlinks the library canonical into the right subfolder. Otherwise, behaviour is unchanged.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Create: `tests/test_cli/test_skill_add_monorepo.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_cli/test_skill_add_monorepo.py`:

```python
"""End-to-end `skill add` against a fixture monorepo parent."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import cli


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    """Initialise the fixture into a bare-ish git repo and return its file URL."""
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=parent_src, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "add", "."], cwd=parent_src, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=parent_src, check=True,
    )
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def test_skill_add_with_skill_flag_installs_subpath(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library

    runner = CliRunner()
    # Reach into the source so we don't depend on a github fetch.
    result = runner.invoke(cli, [
        "skill", "add", parent_url, "--skill", "mkdocs",
    ])
    assert result.exit_code == 0, result.output

    # Library canonical exists at <library>/skills/mkdocs/ and resolves into the
    # parent clone's mkdocs/ subfolder.
    canonical = library / "skills" / "mkdocs"
    assert canonical.exists()
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: mkdocs")

    # Parent clone lives under _parents/.
    parents_dir = library / "skills" / "_parents"
    parent_clones = list(parents_dir.glob("*/*"))
    assert len(parent_clones) == 1
    assert (parent_clones[0] / "mkdocs" / "SKILL.md").exists()
    assert (parent_clones[0] / "docker" / "SKILL.md").exists()

    # Lock entry records the monorepo shape.
    lock_path = library / "skills-lock.json"
    raw = json.loads(lock_path.read_text())
    e = raw["skills"]["mkdocs"]
    assert e["skillPath"] == "mkdocs"
    assert e["readOnly"] is True
    assert e["parentUrl"].endswith("/parent-src")


def test_skill_add_with_explicit_subpath(tmp_path, monkeypatch, isolated_library):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    # owner/repo/subpath shorthand isn't valid against a local file:// URL,
    # so we exercise the URL-tree form here for the subpath path.
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", f"{parent_url}/tree/main/docker",
    ])
    assert result.exit_code == 0, result.output
    canonical = library / "skills" / "docker"
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: docker")
    lock = json.loads((library / "skills-lock.json").read_text())
    assert lock["skills"]["docker"]["skillPath"] == "docker"
    assert lock["skills"]["docker"]["readOnly"] is True


def test_skill_add_with_skill_flag_unknown_name_fails(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", parent_url, "--skill", "nonexistent",
    ])
    assert result.exit_code != 0
    assert "nonexistent" in result.output
    # Error mentions available names so the user can fix the typo.
    assert "mkdocs" in result.output or "docker" in result.output


def test_skill_add_same_parent_twice_reuses_clone(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "docker"])
    assert r2.exit_code == 0, r2.output
    parents = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parents) == 1  # single shared parent clone


def test_skill_add_ambiguous_subpath_and_skill_flag_rejected(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", f"{parent_url}/tree/main/docker", "--skill", "mkdocs",
    ])
    assert result.exit_code != 0
    assert "ambiguous" in result.output.lower() or "both" in result.output.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_cli/test_skill_add_monorepo.py -v
```
Expected: `skill add` doesn't have a `--skill` option; ambiguity check is missing; monorepo install path doesn't exist.

- [ ] **Step 3: Add `--skill` flag and monorepo dispatch**

Edit `src/agent_toolkit_cli/commands/skill/__init__.py`. Replace the existing `add` command with this version:

```python
@skill.command("add")
@click.argument("source", required=True)
@click.option("--slug", default=None,
              help="Override the local slug.")
@click.option("--ref", default=None, help="Branch or tag to clone.")
@click.option("--skill", "skill_name_flag", default=None,
              help="Pick one skill from a monorepo by SKILL.md `name:`.")
@click.pass_context
def add(
    ctx: click.Context, source: str, slug: str | None,
    ref: str | None, skill_name_flag: str | None,
) -> None:
    """Add SOURCE to the library.

    Monorepo: pass --skill <name>, owner/repo/<subpath>, or a
    https://www.skills.sh/<owner>/<repo>/<skill> URL.
    """
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc

    if ref is not None:
        parsed = dataclasses.replace(parsed, ref=ref)

    # Merge the --skill flag into parsed.skill_name. Reject ambiguity.
    if skill_name_flag is not None:
        if parsed.subpath is not None:
            raise click.UsageError(
                "--skill is ambiguous when SOURCE already names a subpath; "
                "pick one form."
            )
        if parsed.skill_name and parsed.skill_name != skill_name_flag:
            raise click.UsageError(
                f"--skill {skill_name_flag} conflicts with SOURCE's skill "
                f"({parsed.skill_name}); pick one form."
            )
        parsed = dataclasses.replace(parsed, skill_name=skill_name_flag)

    if parsed.subpath or parsed.skill_name:
        _add_monorepo(parsed, slug)
    else:
        _add_single(parsed, slug)
```

- [ ] **Step 4: Extract the existing single-skill add into `_add_single`**

Move the original body of `add` (everything from `if slug is None:` to the end, except `parsed = dataclasses.replace(parsed, ref=ref)` which now lives in the wrapper) into a new module-level function:

```python
def _add_single(parsed, slug: str | None) -> None:
    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
            if slug.endswith("-skill"):
                slug = slug[:-6]
        else:
            slug = Path(parsed.url).name

    library_dir = library_skill_path(slug)
    lock_path = library_lock_path()

    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(slug)

    if existing_entry is not None:
        requested = parsed.owner_repo or parsed.url
        if existing_entry.source != requested:
            raise click.ClickException(
                f"{slug}: library entry exists with source {existing_entry.source!r}; "
                f"refusing to overwrite with {requested!r}. "
                f"Run `skill remove {slug}` first."
            )

    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parsed.url, library_dir, ref=parsed.ref, env=None)
        except Exception as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc

    if skill_git.is_git_repo(library_dir):
        upstream_sha = skill_git.remote_head_sha(
            library_dir, ref=parsed.ref or "main", env=None,
        )
        local_sha = skill_git.head_sha(library_dir, env=None)
    else:
        upstream_sha = None
        local_sha = None

    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        skill_path="SKILL.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))
    click.echo(f"added {slug} to library <- {parsed.url}")
```

- [ ] **Step 5: Implement `_add_monorepo`**

Add to the same file:

```python
def _add_monorepo(parsed, slug: str | None) -> None:
    """Clone parent, resolve subpath, symlink library canonical into it."""
    import os
    import yaml  # already a dependency of this repo
    from agent_toolkit_cli.skill_install import _symlink_or_copy
    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
    from agent_toolkit_cli.skill_paths import parent_clone_path

    if parsed.owner_repo is None:
        # Defensive — _parse_https / shorthand always sets owner_repo for
        # github/gitlab/git types we accept here.
        raise click.UsageError("monorepo source must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)

    parent_dir = parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parsed.url, parent_dir, ref=parsed.ref, env=None)
        except Exception as exc:
            raise click.ClickException(f"parent clone failed: {exc}") from exc
    else:
        # Idempotent: refresh.
        try:
            skill_git.fetch(parent_dir, env=None)
        except Exception:
            pass

    # Resolve subpath.
    if parsed.subpath:
        subpath = parsed.subpath
    else:
        subpath = _resolve_skill_name_to_subpath(parent_dir, parsed.skill_name)

    skill_root = parent_dir / subpath
    if not (skill_root / "SKILL.md").exists():
        raise click.ClickException(
            f"{subpath}/SKILL.md not found in parent {parsed.owner_repo}"
        )

    final_slug = slug or parsed.skill_name or Path(subpath).name
    library_dir = library_skill_path(final_slug)
    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    if final_slug in lock.skills:
        existing = lock.skills[final_slug]
        requested = parsed.owner_repo
        if existing.source != requested or existing.skill_path != subpath:
            raise click.ClickException(
                f"{final_slug}: library entry exists with source "
                f"{existing.source!r} skillPath={existing.skill_path!r}; "
                f"refusing to overwrite with {requested!r} skillPath={subpath!r}. "
                f"Run `skill remove {final_slug}` first."
            )

    materialised = "symlink"
    if not library_dir.exists() and not library_dir.is_symlink():
        materialised = _symlink_or_copy(skill_root, library_dir)

    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )
    entry = LockEntry(
        source=parsed.owner_repo,
        source_type=parsed.type,
        ref=parsed.ref,
        skill_path=subpath,
        upstream_sha=parent_sha,
        local_sha=None,
        parent_url=parsed.url,
        read_only=True,
        extras={"materialised": materialised} if materialised == "copy" else {},
    )
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}/{subpath}")


def _resolve_skill_name_to_subpath(parent_dir: Path, skill_name: str) -> str:
    """Walk parent_dir for SKILL.md files; pick the one whose frontmatter name matches.

    Raises ClickException with available names if none match.
    """
    import yaml
    candidates = []
    matches = []
    for skill_md in parent_dir.rglob("SKILL.md"):
        try:
            text = skill_md.read_text()
        except OSError:
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end == -1:
            continue
        try:
            fm = yaml.safe_load(text[4:end])
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue
        name = fm.get("name")
        if name is None:
            continue
        rel = skill_md.parent.relative_to(parent_dir)
        candidates.append(str(name))
        if name == skill_name:
            matches.append(rel)
    if not matches:
        listing = ", ".join(sorted(candidates)) or "(none found)"
        raise click.ClickException(
            f"skill {skill_name!r} not found in parent. "
            f"Available: {listing}"
        )
    if len(matches) > 1:
        raise click.ClickException(
            f"skill {skill_name!r} matches multiple SKILL.md files: "
            f"{', '.join(str(m) for m in matches)}"
        )
    return str(matches[0])
```

- [ ] **Step 6: Run integration tests**

```bash
uv run pytest tests/test_cli/test_skill_add_monorepo.py -v
```
Expected: all five tests PASS. If any fail, fix in place — do not move on.

- [ ] **Step 7: Run regression on existing skill tests**

```bash
uv run pytest tests/test_cli/test_skill_add_monorepo.py tests/test_cli/test_cli_skill_add.py tests/test_cli/test_skill_install.py -v
```
Expected: all PASS. Existing single-skill add path is unchanged.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_add_monorepo.py
git commit -m "feat(skill): #162 skill add --skill / monorepo / skills.sh URL support"
```

---

## Task 6: `update` and `push` branch on `parent_url` / `read_only`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_git.py`
- Modify: `src/agent_toolkit_cli/commands/skill/update_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/skill/push_cmd.py`
- Create: `tests/test_cli/test_skill_update_monorepo.py`
- Create: `tests/test_cli/test_skill_push_monorepo.py`

- [ ] **Step 1: Write the failing update test**

Create `tests/test_cli/test_skill_update_monorepo.py`:

```python
"""skill update for monorepo entries pulls the parent clone."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import cli


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _init_parent(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent)], check=True)
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent, check=True)
    return parent


def test_update_monorepo_pulls_parent_and_reflects_new_content(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    # Mutate the parent.
    (parent / "mkdocs" / "SKILL.md").write_text(
        "---\nname: mkdocs\ndescription: updated\n---\nnew body\n"
    )
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "update"],
    ):
        subprocess.run(cmd, cwd=parent, check=True)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs"])
    assert r2.exit_code == 0, r2.output

    canonical = library / "skills" / "mkdocs"
    assert "new body" in (canonical / "SKILL.md").read_text()
```

- [ ] **Step 2: Write the failing push test**

Create `tests/test_cli/test_skill_push_monorepo.py`:

```python
"""skill push refuses monorepo (read_only) entries with a clear message."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import cli


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def test_push_monorepo_skill_refuses_with_parent_url(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent)], check=True)
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent, check=True)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    result = runner.invoke(cli, ["skill", "push", "mkdocs"])
    assert result.exit_code != 0
    assert "read-only" in result.output.lower() or "read_only" in result.output.lower()
    assert parent_url.split("file://", 1)[1] in result.output or parent_url in result.output
```

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/test_cli/test_skill_update_monorepo.py tests/test_cli/test_skill_push_monorepo.py -v
```
Expected: update silently does nothing useful (canonical is a symlink, the existing merge path fails on the non-git symlink target); push tries to commit/push the parent and succeeds-or-fails non-deterministically.

- [ ] **Step 4: Add `pull_ff_only` helper to `skill_git`**

Edit `src/agent_toolkit_cli/skill_git.py`. After `merge`:

```python
def pull_ff_only(
    repo: Path, *, ref: str, env: dict[str, str] | None,
) -> GitResult:
    """`git pull --ff-only origin <ref>` for monorepo-parent refresh.

    Same env scrubbing as the other helpers in this module.
    """
    proc = _run(["git", "-C", str(repo), "pull", "--ff-only",
                 "origin", ref], env=env)
    if proc.returncode != 0:
        raise GitError(["pull", "--ff-only", ref], proc)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)
```

- [ ] **Step 5: Branch `update_cmd` on `entry.parent_url`**

Edit `src/agent_toolkit_cli/commands/skill/update_cmd.py`. Replace the inside of the `for slug in targets:` loop:

```python
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_conflict = True
            continue
        entry = lock.skills[slug]

        # Monorepo entries: pull the parent clone, the symlinked canonical
        # picks up the new content automatically.
        if entry.parent_url is not None:
            from agent_toolkit_cli.skill_paths import parent_clone_path
            if scope != "global":
                click.echo(f"{slug}: monorepo update only supported at global scope")
                had_conflict = True
                continue
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(owner, repo, ref=entry.ref, env=None)
            if not skill_git.is_git_repo(parent_dir):
                click.echo(f"{slug}: parent clone missing or not a git repo at {parent_dir}")
                had_conflict = True
                continue
            ref = entry.ref or "main"
            try:
                skill_git.pull_ff_only(parent_dir, ref=ref, env=None)
            except skill_git.GitError as exc:
                click.echo(f"{slug}: parent pull failed (non-fast-forward?)")
                click.echo(exc.stderr)
                had_conflict = True
                continue
            entry.upstream_sha = skill_git.head_sha(parent_dir, env=None)
            write_lock(lock_path, lock)
            click.echo(f"{slug}: updated (parent {entry.source} @ {ref})")
            continue

        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot update; remove and "
                f"re-add to switch to git-managed",
            )
            had_conflict = True
            continue
        ref = entry.ref or "main"
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(
                f"{slug}: conflict during merge (resolve in working copy)"
            )
            click.echo(exc.stderr)
            had_conflict = True
            continue
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")
```

- [ ] **Step 6: Branch `push_cmd` on `entry.read_only`**

Edit `src/agent_toolkit_cli/commands/skill/push_cmd.py`. Insert immediately after the `entry = lock.skills[slug]` line:

```python
        if entry.read_only:
            click.echo(
                f"{slug}: read-only (monorepo skill from {entry.parent_url}); "
                f"`skill push` is rejected. Open a PR against the parent repo."
            )
            continue
```

- [ ] **Step 7: Run all tests in this task**

```bash
uv run pytest tests/test_cli/test_skill_update_monorepo.py tests/test_cli/test_skill_push_monorepo.py -v
```
Expected: both PASS.

- [ ] **Step 8: Regression**

```bash
uv run pytest tests/test_cli/test_cli_skill_update.py tests/test_cli/test_cli_skill_push.py tests/test_cli/test_skill_git.py -v
```
Expected: existing single-skill update/push tests still PASS. The `parent_url is None` branch is the original code path.

- [ ] **Step 9: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py src/agent_toolkit_cli/commands/skill/update_cmd.py src/agent_toolkit_cli/commands/skill/push_cmd.py tests/test_cli/test_skill_update_monorepo.py tests/test_cli/test_skill_push_monorepo.py
git commit -m "feat(skill): #162 update pulls monorepo parent; push refuses read-only"
```

---

## Task 7: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/agent-toolkit/cli.md`

- [ ] **Step 1: Update README Skills section**

Edit `README.md`. The current `skill add` line is:

```text
agent-toolkit-cli skill add <source> [-g|-p] [--ref <ref>] [--harness <h>]...
```

Replace with:

```text
agent-toolkit-cli skill add <source> [--skill <name>] [--ref <ref>]
agent-toolkit-cli skill install <slug> --agents <names>
```

Add a paragraph after the existing `vercel-labs/skills` byte-compat line:

```text
**Monorepo skills:** A `<source>` may name a parent repo that contains several skills. Pick one with `--skill <name>` (matches `SKILL.md` frontmatter `name:`), or pass the subpath inline (`owner/repo/<subpath>` or `<repo>/tree/<ref>/<subpath>`). `https://www.skills.sh/<owner>/<repo>/<skill>` URLs also work end-to-end. Monorepo entries are read-only; `skill push` refuses them and points at the parent repo.
```

- [ ] **Step 2: Update cli.md**

Edit `docs/agent-toolkit/cli.md`. Find the `skill add` heading. Append the same `--skill` flag description as in README, plus a worked example block:

````markdown
### Monorepo skills

These three commands install the same `mkdocs` skill, lock-file equivalent:

```bash
agent-toolkit-cli skill add vamseeachanta/workspace-hub --skill mkdocs
agent-toolkit-cli skill add vamseeachanta/workspace-hub/mkdocs
agent-toolkit-cli skill add https://www.skills.sh/vamseeachanta/workspace-hub/mkdocs
```

The parent repo is cloned once under `$AGENT_TOOLKIT_SKILLS_ROOT/_parents/<owner>/<repo>/` (or `~/.agent-toolkit/skills/_parents/<owner>/<repo>/` by default). The library canonical at `<library>/<slug>/` is a symlink into the parent's subfolder; on platforms where symlinks fail, the CLI falls back to a recursive copy and records `materialised: "copy"` in the lock entry.

`skill update <slug>` for monorepo entries runs `git pull --ff-only` against the parent clone — the symlinked canonical sees the new content immediately.

`skill push <slug>` for monorepo entries is refused; the message names the parent URL so you can open a PR there instead.
````

- [ ] **Step 3: Commit**

```bash
git add README.md docs/agent-toolkit/cli.md
git commit -m "docs: #162 document --skill flag, skills.sh URL form, monorepo behaviour"
```

---

## Self-review

- [ ] **Spec coverage check** — every spec section maps to a task:

| Spec section | Implemented by |
|---|---|
| Parser changes | Task 2 |
| Lock fields (`parent_url`, `read_only`) | Task 3 |
| Parent cache path + symlink fallback | Task 4 |
| `skill add` monorepo path + `--skill` flag | Task 5 |
| `update`/`push` branching | Task 6 |
| README + cli.md docs | Task 7 |
| Fixture parent repo | Task 1 |
| Definition-of-done acceptance examples | Tasks 5 (add) + 6 (update/push) |
| Lock round-trip with npx skills | Task 3 |

- [ ] **Placeholder scan** — none. Every step has runnable code, exact commands, and expected outcomes.
- [ ] **Type consistency** — `ParsedSource.skill_name`, `LockEntry.parent_url`, `LockEntry.read_only`, `_symlink_or_copy()`, `parent_clone_path()`, `_add_monorepo()`, `_add_single()`, `_resolve_skill_name_to_subpath()`, `skill_git.pull_ff_only()` — all defined in earlier tasks before later tasks reference them.

## Execution

Subagent-driven execution: each task is self-contained (own test file, own commit) and can be implemented + reviewed independently. Tasks 5 and 6 have integration tests that exercise real git through subprocess, so the runner needs a working `git` on PATH (already true in this repo's CI).

# Paperclip Company Skill Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Paperclip a filesystem-backed main Skills harness whose project-scope projections land in the detected company skill library.

**Architecture:** Add one pure Paperclip company-path resolver, normalize skill project roots through it, and special-case only the `paperclip` skill projection at the existing projection boundary. Keep Agent Toolkit’s global library, external project canonical, lockfile, install engine, and ownership safeguards; expose availability explicitly in the TUI so company-only cells cannot be toggled elsewhere.

**Tech Stack:** Python 3.12+, Click, pathlib, pytest, Textual, existing Agent Toolkit skill install engine and documentation generator.

## Global Constraints

- Paperclip integration is filesystem-only; do not add HTTP, API, authentication, credential, or individual-agent assignment code.
- A company root is `~/.paperclip/instances/<instance>/companies/<company-id>` and its skill root is the sibling `~/.paperclip/instances/<instance>/skills/<company-id>`.
- Walk upward from descendants to the nearest valid company root.
- Keep `<company-root>/skills-lock.json` and the existing external project canonical model.
- A Paperclip-only install must not create `<company-root>/.agents/skills/<slug>`.
- Paperclip is actionable only for the Skills asset type at project scope in a detected company context.
- Reject missing context and destination conflicts before materializing a project canonical or writing a project lock.
- Add no runtime dependency and do not change persisted lock schemas.
- Use test-driven development and preserve all unrelated working-tree changes.

---

## File structure

### New files

- `src/agent_toolkit_cli/paperclip_paths.py` — pure company-context detection, normalization, and required-context errors.
- `tests/test_cli/test_paperclip_paths.py` — path recognition and normalization contract.
- `tests/test_cli/test_cli_skill_paperclip.py` — end-to-end CLI projection, preflight, conflict, and uninstall coverage.
- `tests/test_tui/test_paperclip_skill_tui.py` — company-only TUI availability, toggling, and apply coverage.
- `docs/harnesses/paperclip.md` — generated Paperclip capability page.
- `assets/verification/issue-474/` — CLI and multi-state TUI evidence with written visual judgment.

### Modified files

- `src/agent_toolkit_cli/skill_agents.py` — register `paperclip` as a real, non-Standard Skills harness.
- `src/agent_toolkit_cli/skill_paths.py` — resolve the Paperclip project projection destination at the existing path boundary.
- `src/agent_toolkit_cli/skill_install.py` — preflight company-only projection targets before any mutation.
- `src/agent_toolkit_cli/_install_core.py` — skip contextually unavailable Paperclip during catalog-wide projection scans.
- `src/agent_toolkit_cli/skill_doctor.py` — scan the resolved Paperclip company projection root without breaking ordinary projects.
- `src/agent_toolkit_cli/commands/skill/_common.py` — normalize implicit/explicit skill project roots and recognize Paperclip context before lockfile fallback.
- `src/agent_toolkit_cli/commands/skill/__init__.py` — make omitted install/uninstall scope Paperclip-aware while preserving the ordinary global default.
- `src/agent_toolkit_tui/skill_state.py` — represent unavailable company-only cells and probe Paperclip projections safely.
- `src/agent_toolkit_tui/widgets/skill_grid.py` — render unavailable cells, block toggles, and explain context requirements.
- `src/agent_toolkit_tui/app.py` — use the normalized skill project root for refresh/apply and preflight before canonical materialization.
- `src/agent_toolkit_tui/composition.py` — include `paperclip` in the main harness set.
- `src/agent_toolkit_tui/display_names.py` — render `Paperclip`.
- `tests/test_cli/test_skill_agents.py` — pin the new catalog count/configuration.
- `tests/test_cli/test_cli_skill_scope_banner.py` — pin Paperclip implicit project-scope behavior.
- `tests/test_cli/test_cli_skill_list.py` — pin harness-filtered Paperclip projection state and ordinary-scope scans.
- `tests/test_cli/test_cli_skill_doctor.py` — pin correct/missing/foreign/stray Paperclip company projections.
- `tests/test_harness_docs.py` — pin generated Paperclip company-only Skills metadata.
- `tests/test_tui/test_composition.py` — pin main-harness coverage and exclude unsupported asset actions.
- `tests/test_tui/test_display_names.py` — pin the Paperclip display label.
- `tests/test_tui/test_skill_grid_apply.py` — teach shared fixtures about cell availability.
- `docs/agent-toolkit/harness-matrix.md` — add Paperclip to all-harness parity rows and update counts.
- `scripts/gen_harness_docs.py` — mark Paperclip as headline and supply its logo metadata.
- `docs/matrix.md` and `mkdocs.yml` — regenerated compatibility views/navigation.

---

### Task 1: Detect and normalize Paperclip company roots

**Files:**
- Create: `src/agent_toolkit_cli/paperclip_paths.py`
- Create: `tests/test_cli/test_paperclip_paths.py`
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py`
- Modify: `tests/test_cli/test_cli_skill_scope_banner.py`

**Interfaces:**
- Produces: `PaperclipCompanyContext`, `PaperclipContextError`, `detect_paperclip_company(path, *, paperclip_root=None)`, `require_paperclip_company(path, *, paperclip_root=None)`, and `normalize_skill_project_root(path, *, paperclip_root=None)`.
- Consumes: `Path.home()` only as the production default; tests pass an explicit temporary `paperclip_root`.

- [ ] **Step 1: Write failing path-context tests**

```python
# tests/test_cli/test_paperclip_paths.py
from pathlib import Path

import pytest

from agent_toolkit_cli.paperclip_paths import (
    PaperclipContextError,
    detect_paperclip_company,
    normalize_skill_project_root,
    require_paperclip_company,
)


def _company(tmp_path: Path, instance: str = "default", company: str = "company-123"):
    root = tmp_path / ".paperclip"
    company_root = root / "instances" / instance / "companies" / company
    company_root.mkdir(parents=True)
    return root, company_root


def test_detects_exact_company_and_derives_skill_root(tmp_path):
    root, company = _company(tmp_path)
    ctx = detect_paperclip_company(company, paperclip_root=root)
    assert ctx is not None
    assert ctx.company_root == company.resolve()
    assert ctx.instance_root == (root / "instances/default").resolve()
    assert ctx.instance_name == "default"
    assert ctx.company_id == "company-123"
    assert ctx.skills_root == (root / "instances/default/skills/company-123").resolve()


def test_walks_up_from_company_descendant(tmp_path):
    root, company = _company(tmp_path, "staging", "abc")
    descendant = company / "workspace" / "nested"
    descendant.mkdir(parents=True)
    assert normalize_skill_project_root(descendant, paperclip_root=root) == company.resolve()


@pytest.mark.parametrize("parts", [
    ("instances", "default", "company", "abc"),
    ("instance", "default", "companies", "abc"),
    ("instances", "default", "companies"),
])
def test_rejects_lookalike_layouts(tmp_path, parts):
    root = tmp_path / ".paperclip"
    candidate = root.joinpath(*parts)
    candidate.mkdir(parents=True)
    assert detect_paperclip_company(candidate, paperclip_root=root) is None


def test_require_fails_with_expected_shape(tmp_path):
    project = tmp_path / "ordinary"
    project.mkdir()
    with pytest.raises(PaperclipContextError, match=r"instances/<instance>/companies/<company-id>"):
        require_paperclip_company(project, paperclip_root=tmp_path / ".paperclip")
```

- [ ] **Step 2: Run the path tests and confirm the missing-module failure**

Run: `uv run pytest tests/test_cli/test_paperclip_paths.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'agent_toolkit_cli.paperclip_paths'`.

- [ ] **Step 3: Implement the pure path resolver**

```python
# src/agent_toolkit_cli/paperclip_paths.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PaperclipContextError(ValueError):
    """The requested path is not inside a Paperclip company root."""


@dataclass(frozen=True)
class PaperclipCompanyContext:
    company_root: Path
    instance_root: Path
    instance_name: str
    company_id: str
    skills_root: Path


def detect_paperclip_company(
    path: Path, *, paperclip_root: Path | None = None,
) -> PaperclipCompanyContext | None:
    root = (paperclip_root or (Path.home() / ".paperclip")).resolve()
    current = path.resolve()
    for candidate in (current, *current.parents):
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if (
            len(parts) == 4
            and parts[0] == "instances"
            and parts[1]
            and parts[2] == "companies"
            and parts[3]
            and candidate.is_dir()
        ):
            instance_root = root / "instances" / parts[1]
            return PaperclipCompanyContext(
                company_root=candidate,
                instance_root=instance_root,
                instance_name=parts[1],
                company_id=parts[3],
                skills_root=instance_root / "skills" / parts[3],
            )
    return None


def require_paperclip_company(
    path: Path, *, paperclip_root: Path | None = None,
) -> PaperclipCompanyContext:
    context = detect_paperclip_company(path, paperclip_root=paperclip_root)
    if context is None:
        raise PaperclipContextError(
            "Paperclip skills require project scope inside "
            "~/.paperclip/instances/<instance>/companies/<company-id>"
        )
    return context


def normalize_skill_project_root(
    path: Path, *, paperclip_root: Path | None = None,
) -> Path:
    context = detect_paperclip_company(path, paperclip_root=paperclip_root)
    return context.company_root if context is not None else path
```

- [ ] **Step 4: Run path tests and confirm they pass**

Run: `uv run pytest tests/test_cli/test_paperclip_paths.py -q`

Expected: all tests pass.

- [ ] **Step 5: Add failing scope-resolution tests**

```python
# tests/test_cli/test_cli_skill_scope_banner.py

def test_scope_and_roots_implicit_paperclip_project_without_lock(tmp_path):
    company = tmp_path / ".paperclip/instances/default/companies/company-123"
    nested = company / "workspace"
    nested.mkdir(parents=True)
    scope, home, root, implicit = scope_and_roots(
        False, False, nested, read_only=True,
    )
    assert (scope, home, root, implicit) == ("project", None, company.resolve(), True)


def test_scope_and_roots_explicit_project_normalizes_paperclip_descendant(tmp_path):
    company = tmp_path / ".paperclip/instances/default/companies/company-123"
    nested = company / "workspace"
    nested.mkdir(parents=True)
    assert scope_and_roots(False, True, nested) == (
        "project", None, company.resolve(), False,
    )
```

Use `monkeypatch.setenv("HOME", str(tmp_path))` in both tests so production default detection resolves the fixture root.

- [ ] **Step 6: Normalize roots in the shared skill scope helper**

```python
# src/agent_toolkit_cli/commands/skill/_common.py
from agent_toolkit_cli.paperclip_paths import (
    detect_paperclip_company,
    normalize_skill_project_root,
)

# In scope_and_roots(), after choosing `project_root = ctx_project or Path.cwd()`:
paperclip = detect_paperclip_company(project_root)
normalized = normalize_skill_project_root(project_root)
if project:
    return "project", None, normalized, False
if paperclip is not None:
    return "project", None, normalized, True
if read_only and not (project_root / "skills-lock.json").exists():
    return "global", Path.home(), None, True
return "project", None, normalized, True
```

Keep the explicit-global branch first so `-g` never redirects.

- [ ] **Step 7: Run focused scope parity tests**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py tests/test_cli/test_scope_resolution_parity.py -q`

Expected: Paperclip tests pass; parity tests pass without changing agent/MCP/Pi-extension behavior.

- [ ] **Step 8: Commit the path/root unit**

```bash
git add src/agent_toolkit_cli/paperclip_paths.py src/agent_toolkit_cli/commands/skill/_common.py tests/test_cli/test_paperclip_paths.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(paperclip): detect company project roots" -m "Device: $(hostname -s)"
```

---

### Task 2: Project Paperclip skills through the existing install engine

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py`
- Modify: `src/agent_toolkit_cli/skill_paths.py`
- Modify: `src/agent_toolkit_cli/skill_install.py`
- Modify: `src/agent_toolkit_cli/_install_core.py`
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Modify: `tests/test_cli/test_skill_agents.py`
- Create: `tests/test_cli/test_cli_skill_paperclip.py`
- Modify: `tests/test_cli/test_cli_skill_list.py`
- Modify: `tests/test_cli/test_cli_skill_doctor.py`

**Interfaces:**
- Consumes: `require_paperclip_company()` and `normalize_skill_project_root()` from Task 1.
- Produces: catalog token `paperclip`, `is_skill_projection_available(agent_name, scope, project)`, Paperclip-aware `agent_projection_dir()`, and `validate_projection_context(slug, target_agents, scope, home, project)`.

- [ ] **Step 1: Write failing catalog and destination tests**

```python
# tests/test_cli/test_skill_agents.py

def test_paperclip_is_company_scoped_skill_harness():
    cfg = AGENTS["paperclip"]
    assert cfg.display_name == "Paperclip"
    assert not cfg.is_standard
    assert cfg.subagent_mechanism == "none"
    assert "company-scoped Skills" in cfg.disabled_reason
    assert not cfg.detect_installed()  # context-constrained; resolved explicitly

# Update the catalog-size assertion from 57 to 58.
```

```python
# tests/test_cli/test_cli_skill_paperclip.py
from agent_toolkit_cli.skill_paths import agent_projection_dir


def _company(tmp_path):
    company = tmp_path / ".paperclip/instances/default/companies/company-123"
    company.mkdir(parents=True)
    return company


def test_projection_destination_is_company_skill_library(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    company = _company(tmp_path)
    assert agent_projection_dir(
        "paperclip", "demo", scope="project", home=None, project=company,
    ) == tmp_path / ".paperclip/instances/default/skills/company-123/demo"
```

- [ ] **Step 2: Run the focused tests and confirm missing catalog support**

Run: `uv run pytest tests/test_cli/test_skill_agents.py tests/test_cli/test_cli_skill_paperclip.py::test_projection_destination_is_company_skill_library -q`

Expected: failures show missing `AGENTS['paperclip']` and unsupported projection resolution.

- [ ] **Step 3: Register the Paperclip harness and projection boundary**

```python
# src/agent_toolkit_cli/skill_agents.py — add a real catalog row
"paperclip": AgentConfig(
    name="paperclip",
    display_name="Paperclip",
    # A non-Standard sentinel; project resolution is handled by skill_paths.
    skills_dir=".paperclip-company/skills",
    global_skills_dir=HOME / ".paperclip" / "skills",
    # Catalog detection has no scope/project arguments. Keep this false so
    # global `all` operations never accidentally select a company-only target;
    # _resolve_agents adds Paperclip only in a detected company project.
    detect_installed=lambda: False,
    subagent_mechanism="none",
    disabled_reason="company-scoped Skills harness only; no Agent asset adapter",
),
```

```python
# src/agent_toolkit_cli/skill_paths.py
from agent_toolkit_cli.paperclip_paths import (
    detect_paperclip_company,
    require_paperclip_company,
)


def is_skill_projection_available(
    agent_name: str, *, scope: Scope, project: Path | None,
) -> bool:
    if agent_name != "paperclip":
        return True
    return (
        scope == "project"
        and project is not None
        and detect_paperclip_company(project) is not None
    )


# At the start of agent_projection_dir(), after validating agent_name:
if agent_name == "paperclip":
    if not is_skill_projection_available(
        agent_name, scope=scope, project=project,
    ):
        raise ValueError("Paperclip skills are company-scoped and require project scope")
    assert project is not None
    return require_paperclip_company(project).skills_root / slug
```

Catalog-wide scanners are different from explicit targets: update `_install_core._current_linked_agents()` to `continue` when `is_skill_projection_available()` is false, and update `skill_doctor` projection-root enumeration to skip unavailable Paperclip while deriving available roots through `agent_projection_dir(name, "__probe__", scope=scope, home=home, project=project).parent`. Explicit Paperclip targets still call preflight and fail loudly. Add regression tests proving global and generic-project `plan()`, harness-filtered list, and doctor complete normally when Paperclip is unselected.

- [ ] **Step 4: Add projection preflight before any mutation**

```python
# src/agent_toolkit_cli/skill_install.py
from agent_toolkit_cli.paperclip_paths import PaperclipContextError, require_paperclip_company


def validate_projection_context(
    *,
    slug: str,
    target_agents: Iterable[str],
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> None:
    agents = tuple(target_agents)
    if "paperclip" not in agents:
        return
    if not slug or slug in {".", ".."} or Path(slug).name != slug or Path(slug).is_absolute():
        raise InstallError(
            f"{slug!r}: Paperclip skill slug must be one non-empty leaf name"
        )
    if scope != "project" or project is None:
        raise InstallError(
            "paperclip: company-scoped skills require project scope inside "
            "~/.paperclip/instances/<instance>/companies/<company-id>"
        )
    try:
        context = require_paperclip_company(project)
    except PaperclipContextError as exc:
        raise InstallError(f"paperclip: {exc}") from exc
    canonical = canonical_skill_dir(
        slug, scope="project", home=home, project=project,
    )
    destination = context.skills_root / slug
    # Paperclip's instance/company library is expected to be a real directory
    # chain. Reject an existing symlinked ancestor rather than following a
    # redirect outside the instance tree. Missing parents remain creatable.
    for ancestor in (context.instance_root / "skills", context.skills_root):
        if ancestor.is_symlink():
            raise InstallError(
                f"{slug}/paperclip: symlinked projection parent is unsupported: "
                f"{ancestor}"
            )
    try:
        destination.parent.resolve(strict=False).relative_to(
            (context.instance_root / "skills").resolve(strict=False)
        )
    except ValueError as exc:
        raise InstallError(
            f"{slug}/paperclip: projection escapes the instance skills root"
        ) from exc
    if destination.is_symlink():
        if destination.resolve() != canonical.resolve():
            raise InstallError(
                f"{slug}/paperclip: conflicting symlink at {destination}: "
                f"points to {destination.resolve()}, expected {canonical}"
            )
    elif destination.exists():
        raise InstallError(
            f"{slug}/paperclip: conflicting non-symlink at {destination}; "
            "refusing to overwrite"
        )
```

At the start of `plan()`, materialize `target_agents = tuple(target_agents)` once, then pass that tuple to validation and `_core_plan` so generator inputs are not consumed. At the start of `apply()`, validate the union `(*plan.add_agents, *plan.remove_agents)` before canonical or lock resolution so direct removal callers receive the same ownership checks. Call the validator from the CLI before `ensure_project_canonical()`; Task 3 adds the corresponding TUI call. Add direct-engine generator-input and Paperclip-removal conflict tests. These checks ensure destination conflicts cannot leave a new project canonical or lock entry behind.

- [ ] **Step 5: Write failing CLI integration tests**

```python
# tests/test_cli/test_cli_skill_paperclip.py
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_paths import project_store_root


@pytest.fixture
def paperclip_install(git_sandbox, tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    company = home / ".paperclip/instances/default/companies/company-123"
    company.mkdir(parents=True)
    library = tmp_path / "library/skills"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library))
    for key, value in git_sandbox.env.items():
        monkeypatch.setenv(key, value)
    runner = CliRunner()
    added = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert added.exit_code == 0, added.output
    projection = home / ".paperclip/instances/default/skills/company-123/demo"
    return SimpleNamespace(
        home=home,
        company=company,
        projection=projection,
        runner=runner,
    )


def test_implicit_install_projects_only_to_paperclip_company(paperclip_install):
    env = paperclip_install
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code == 0, result.output
    assert env.projection.is_symlink()
    assert (env.company / "skills-lock.json").is_file()
    assert not (env.company / ".agents/skills/demo").exists()


def test_generic_project_refuses_before_lock_or_canonical(
    paperclip_install, tmp_path,
):
    env = paperclip_install
    project = tmp_path / "ordinary"
    project.mkdir()
    result = env.runner.invoke(main, [
        "--project", str(project), "skill", "install", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "paperclip" in result.output.lower()
    assert not (project / "skills-lock.json").exists()
    assert not project_store_root(project).exists()


def test_global_paperclip_install_is_rejected_without_writes(paperclip_install):
    env = paperclip_install
    result = env.runner.invoke(main, [
        "skill", "install", "demo", "--scope", "global", "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "require project scope" in result.output
    assert not (env.home / ".paperclip/skills/demo").exists()
    assert not (env.home / ".agents/skills/demo").exists()


def test_repeated_install_is_idempotent(paperclip_install):
    env = paperclip_install
    args = [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ]
    first = env.runner.invoke(main, args)
    second = env.runner.invoke(main, args)
    assert first.exit_code == second.exit_code == 0
    assert env.projection.is_symlink()
    assert env.projection.resolve() == project_store_root(env.company).joinpath("demo").resolve()


def test_foreign_symlink_conflict_is_preserved(paperclip_install):
    env = paperclip_install
    foreign = env.home / "foreign-skill"
    foreign.mkdir()
    env.projection.parent.mkdir(parents=True)
    env.projection.symlink_to(foreign)
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "conflicting symlink" in result.output
    assert env.projection.resolve() == foreign.resolve()
    assert not (env.company / "skills-lock.json").exists()
    assert not project_store_root(env.company).exists()


def test_real_directory_conflict_is_preserved(paperclip_install):
    env = paperclip_install
    env.projection.mkdir(parents=True)
    marker = env.projection / "keep.txt"
    marker.write_text("owned elsewhere")
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "conflicting non-symlink" in result.output
    assert marker.read_text() == "owned elsewhere"
    assert not (env.company / "skills-lock.json").exists()


def test_uninstall_removes_only_owned_projection(paperclip_install):
    env = paperclip_install
    install = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert install.exit_code == 0, install.output
    canonical = env.projection.resolve()
    uninstall = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "uninstall", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert uninstall.exit_code == 0, uninstall.output
    assert not env.projection.exists()
    assert canonical.exists()
    assert (env.company / "skills-lock.json").exists()


def test_uninstall_refuses_foreign_projection(paperclip_install):
    env = paperclip_install
    foreign = env.home / "foreign-skill"
    foreign.mkdir()
    env.projection.parent.mkdir(parents=True)
    env.projection.symlink_to(foreign)
    uninstall = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "uninstall", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert uninstall.exit_code != 0
    assert "conflicting symlink" in uninstall.output
    assert env.projection.resolve() == foreign.resolve()


def test_global_all_ignores_context_constrained_paperclip(paperclip_install):
    env = paperclip_install
    result = env.runner.invoke(main, [
        "skill", "install", "demo", "--scope", "global", "--agents", "all",
    ])
    assert result.exit_code == 0, result.output
    assert "company-scoped" not in result.output


def test_company_list_filter_reads_paperclip_projection(paperclip_install):
    env = paperclip_install
    assert env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ]).exit_code == 0
    listed = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "list", "-p",
        "--agent", "paperclip", "--json",
    ])
    assert listed.exit_code == 0, listed.output
    assert '"slug": "demo"' in listed.output


def test_generic_project_plan_and_doctor_skip_unavailable_paperclip(
    paperclip_install, tmp_path,
):
    env = paperclip_install
    project = tmp_path / "ordinary"
    project.mkdir()
    listed = env.runner.invoke(main, [
        "--project", str(project), "skill", "list", "-p", "--json",
    ])
    doctor = env.runner.invoke(main, [
        "--project", str(project), "skill", "doctor", "-p",
    ])
    assert listed.exit_code == 0, listed.output
    assert doctor.exit_code == 0, doctor.output


def test_doctor_finds_stray_company_projection(paperclip_install):
    env = paperclip_install
    stray = env.projection.parent / "stray"
    target = env.home / "stray-target"
    target.mkdir()
    stray.parent.mkdir(parents=True)
    stray.symlink_to(target)
    doctor = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "doctor", "-p",
    ])
    assert doctor.exit_code != 0
    assert "stray" in doctor.output
    assert stray.is_symlink()


@pytest.mark.parametrize("slug", ["", ".", "..", "../escape", "nested/escape", "/tmp/escape"])
def test_engine_rejects_non_leaf_paperclip_slugs_before_writes(
    paperclip_install, slug,
):
    env = paperclip_install
    with pytest.raises(InstallError, match="one non-empty leaf name"):
        validate_projection_context(
            slug=slug,
            target_agents=(name for name in ("paperclip",)),
            scope="project",
            home=None,
            project=env.company,
        )
    assert not (env.company / "skills-lock.json").exists()


def test_symlinked_skills_parent_is_rejected(paperclip_install):
    env = paperclip_install
    skills = env.home / ".paperclip/instances/default/skills"
    redirected = env.home / "redirected"
    redirected.mkdir()
    skills.parent.mkdir(parents=True, exist_ok=True)
    skills.symlink_to(redirected)
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "symlinked projection parent" in result.output
    assert not (redirected / "company-123/demo").exists()
```

- [ ] **Step 6: Make omitted install/uninstall scope Paperclip-aware**

Change the Click scope option from a hard default to an explicit/implicit distinction:

```python
@click.option(
    "--scope", "scope", default=None,
    type=click.Choice(["global", "project"]),
    help="Scope (default: global, or project inside a Paperclip company).",
)
```

Resolve scope/root before expanding agent tokens in both commands:

```python
candidate = (ctx.obj.get("project_root") if ctx.obj else None) or Path.cwd()
context = detect_paperclip_company(candidate)
if project_flag:
    scope = "project"
elif scope is None:
    scope = "project" if context is not None else "global"
project_root = normalize_skill_project_root(candidate) if scope == "project" else None

target_agents = _resolve_agents(
    agents_str, scope, project=project_root,
)
validate_projection_context(
    slug=slug,
    target_agents=target_agents,
    scope=scope,
    home=None if scope == "project" else Path.home(),
    project=project_root,
)
```

Make `all` context-aware without changing catalog-wide detection:

```python
def _resolve_agents(
    agents_str: str, scope: str, *, project: Path | None = None,
) -> tuple[str, ...]:
    if agents_str == "all":
        resolved = list(detect_installed_agents())
        if is_skill_projection_available(
            "paperclip", scope=scope, project=project,
        ):
            resolved.append("paperclip")
        return tuple(dict.fromkeys(resolved))
    # Preserve existing explicit-token parsing below.
```

For bare uninstall, append `paperclip` to the existing maximal target only when `is_skill_projection_available("paperclip", scope=scope, project=project_root)` is true. Preserve ordinary behavior: outside Paperclip, `skill install demo` still installs Standard globally; global `--agents all` remains valid even when `~/.paperclip` exists; inside a company, `all` and bare uninstall include Paperclip.

- [ ] **Step 7: Run CLI integration and regression tests**

Run: `uv run pytest tests/test_cli/test_cli_skill_paperclip.py tests/test_cli/test_cli_skill_install.py tests/test_cli/test_skill_install_engine.py tests/test_cli/test_skill_paths.py tests/test_cli/test_cli_skill_list.py tests/test_cli/test_cli_skill_doctor.py -q`

Expected: all tests pass; no test writes beneath the real home directory.

- [ ] **Step 8: Commit the projection unit**

```bash
git add src/agent_toolkit_cli/skill_agents.py src/agent_toolkit_cli/skill_paths.py src/agent_toolkit_cli/skill_install.py src/agent_toolkit_cli/_install_core.py src/agent_toolkit_cli/skill_doctor.py src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_agents.py tests/test_cli/test_cli_skill_paperclip.py tests/test_cli/test_cli_skill_list.py tests/test_cli/test_cli_skill_doctor.py
git commit -m "feat(paperclip): project skills into company libraries" -m "Device: $(hostname -s)"
```

---

### Task 3: Expose safe Paperclip controls in the Skills TUI

**Files:**
- Modify: `src/agent_toolkit_tui/composition.py`
- Modify: `src/agent_toolkit_tui/display_names.py`
- Modify: `src/agent_toolkit_tui/skill_state.py`
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Modify: `src/agent_toolkit_tui/app.py`
- Modify: `tests/test_tui/test_composition.py`
- Modify: `tests/test_tui/test_display_names.py`
- Modify: `tests/test_tui/test_skill_grid_apply.py`
- Create: `tests/test_tui/test_paperclip_skill_tui.py`

**Interfaces:**
- Consumes: `detect_paperclip_company()`, `normalize_skill_project_root()`, and `validate_projection_context()`.
- Produces: `SkillCell.available: bool`, `SkillCell.unavailable_reason: str`, and a non-toggleable `—` Paperclip cell outside company project context.

- [ ] **Step 1: Write failing composition and availability tests**

```python
# tests/test_tui/test_composition.py

def test_main_harnesses_members():
    assert MAIN_HARNESSES == (
        "claude-code", "gemini-cli", "codex", "opencode", "pi", "cursor",
        "hermes-agent", "paperclip",
    )


def test_skills_nonstandard_main_today():
    assert skills_nonstandard_main() == (
        "claude-code", "pi", "hermes-agent", "paperclip",
    )


def test_paperclip_is_not_actionable_in_other_asset_compositions():
    assert "paperclip" not in instructions_nonstandard_main()
    assert all("paperclip" not in agents_nonstandard_main(scope) for scope in ("global", "project"))
    assert "paperclip" not in _MCP_HARNESSES
    assert "paperclip" not in command_state.INTERACTIVE_HARNESSES
```

```python
# tests/test_tui/test_paperclip_skill_tui.py

def test_paperclip_cell_unavailable_in_generic_project(tmp_path, skill_library):
    rows = build_skill_rows(scope="project", home=tmp_path, project=tmp_path / "ordinary")
    cell = rows[0].cells[("paperclip", "project")]
    assert not cell.available
    assert "company-scoped" in cell.unavailable_reason


def test_paperclip_cell_probes_company_projection(tmp_path, monkeypatch, skill_library):
    monkeypatch.setenv("HOME", str(tmp_path))
    company = _company(tmp_path)
    # Create the expected canonical and owned projection fixture.
    rows = build_skill_rows(scope="project", home=tmp_path, project=company)
    assert rows[0].cells[("paperclip", "project")].available
```

- [ ] **Step 2: Run focused TUI tests and confirm failures**

Run: `uv run pytest tests/test_tui/test_composition.py tests/test_tui/test_display_names.py tests/test_tui/test_paperclip_skill_tui.py -q`

Expected: failures show Paperclip missing from composition/display and `SkillCell` lacking availability.

- [ ] **Step 3: Add main-harness metadata**

```python
# src/agent_toolkit_tui/composition.py
MAIN_HARNESSES = (
    "claude-code", "gemini-cli", "codex", "opencode", "pi", "cursor",
    "hermes-agent", "paperclip",
)
```

```python
# src/agent_toolkit_tui/display_names.py
_HARNESS_LABELS["paperclip"] = "Paperclip"
```

- [ ] **Step 4: Represent unavailable cells in skill state**

```python
# src/agent_toolkit_tui/skill_state.py
@dataclass(frozen=True)
class SkillCell:
    linked: bool
    drift: bool
    skipped: bool
    stray: bool = False
    available: bool = True
    unavailable_reason: str = ""

# At the start of _cell_for() after the Standard branch:
if agent_name == "paperclip":
    # Global cells still need the caller's current company context to explain
    # whether the correction is “switch scope” or “open a company project.”
    context_path = project or Path.cwd()
    context = detect_paperclip_company(context_path)
    if scope != "project" or context is None:
        if scope == "global" and context is not None:
            reason = "Paperclip is project-only; switch the TUI to Project scope."
        else:
            reason = (
                "Paperclip skills are company-scoped; open the TUI inside "
                "~/.paperclip/instances/<instance>/companies/<company-id>."
            )
        return SkillCell(
            linked=False,
            drift=False,
            skipped=False,
            available=False,
            unavailable_reason=reason,
        )
```

All existing `SkillCell` construction remains valid through defaults. Paperclip company project cells continue through the existing link/drift/stray probe using `agent_projection_dir()`.

- [ ] **Step 5: Block unavailable toggles and explain them**

```python
# src/agent_toolkit_tui/widgets/skill_grid.py
# In _toggle_at() and both loops in action_toggle_column():
if cell is None or cell.skipped or not cell.available:
    return  # use continue inside column loops

# In _cell_glyph(), before skipped:
elif not cell.available:
    base = "—"

# At the start of _info_body_for_cell():
if not cell.available:
    return f"[dim]Unavailable.[/]\n{cell.unavailable_reason}"
```

Ensure `_info_body_for_cell()` returns before calling `agent_projection_dir()` so unavailable global/generic-project Paperclip cells never raise.

- [ ] **Step 6: Normalize the TUI skill root and preflight apply**

Add a skill-specific root helper rather than changing other asset panes:

```python
# src/agent_toolkit_tui/app.py
def _skill_project_root(self) -> Path:
    return normalize_skill_project_root(Path.cwd())

# _refresh_skill_view(): use self._skill_project_root() for project.
# _apply_skill_pending(): use self._skill_project_root() instead of Path.cwd().
# Before ensure_project_canonical():
validate_projection_context(
    slug=slug,
    target_agents=(*adds, *removes),
    scope=scope,
    home=home,
    project=project,
)
```

In `SkillGrid._info_body_for_cell()`, normalize `Path.cwd()` for project canonical and projection paths. This keeps the displayed target identical to the apply target.

- [ ] **Step 7: Add interaction tests for unavailable and company cells**

```python
# tests/test_tui/test_paperclip_skill_tui.py
@pytest.mark.asyncio
async def test_unavailable_paperclip_cell_cannot_queue(tmp_path):
    row = _row_with_paperclip(available=False)
    # Mount SkillGrid, select Paperclip, press space.
    assert grid.pending_entries() == {}


@pytest.mark.asyncio
async def test_company_paperclip_cell_queues_project_link(tmp_path):
    row = _row_with_paperclip(available=True)
    # Mount in project scope, select Paperclip, press space.
    assert grid.pending_entries() == {("project", "paperclip", "demo"): "link"}


@pytest.mark.asyncio
async def test_unavailable_paperclip_column_bulk_toggle_queues_nothing(tmp_path):
    row = _row_with_paperclip(available=False)
    # Mount SkillGrid, focus Paperclip, press `a`.
    assert grid.pending_entries() == {}


@pytest.mark.asyncio
async def test_unavailable_info_copy_distinguishes_scope_from_context(tmp_path):
    # Open `i` on global-in-company and project-outside-company fixtures.
    assert "switch the TUI to Project scope" in global_body
    assert "instances/<instance>/companies/<company-id>" in generic_body


@pytest.mark.asyncio
async def test_apply_uses_normalized_company_root(monkeypatch, tmp_path):
    # Run TUIApp from a descendant; monkeypatch engine_apply and
    # ensure_project_canonical; assert both receive the detected company root,
    # never the descendant and never a .agents projection target.


@pytest.mark.asyncio
async def test_paperclip_apply_round_trip_updates_cell_and_footer(tmp_path):
    # Use the real hermetic project canonical/projection flow. After Apply,
    # assert the projection exists, refreshed Paperclip cell.linked is true,
    # and footer contains `applied: 1 ok, 0 failed`.


@pytest.mark.asyncio
async def test_paperclip_conflict_preserves_pending_and_shows_error(tmp_path):
    # Seed a foreign destination, Apply a queued Paperclip link, then assert:
    # error footer + notification, pending link retained, foreign destination
    # unchanged, and no project canonical or skills-lock created.
```

Update shared `_row()` helpers only by relying on the new defaults unless a test explicitly needs `available=False`.

- [ ] **Step 8: Run all Skills TUI tests**

Run: `uv run pytest tests/test_tui/test_paperclip_skill_tui.py tests/test_tui/test_composition.py tests/test_tui/test_display_names.py tests/test_tui/test_skill_state.py tests/test_tui/test_skill_grid_apply.py tests/test_tui/test_skill_grid_groups.py -q`

Expected: all tests pass; unavailable Paperclip cells queue no operations.

- [ ] **Step 9: Commit the TUI unit**

```bash
git add src/agent_toolkit_tui/composition.py src/agent_toolkit_tui/display_names.py src/agent_toolkit_tui/skill_state.py src/agent_toolkit_tui/widgets/skill_grid.py src/agent_toolkit_tui/app.py tests/test_tui/test_composition.py tests/test_tui/test_display_names.py tests/test_tui/test_skill_grid_apply.py tests/test_tui/test_paperclip_skill_tui.py
git commit -m "feat(tui): expose Paperclip company skills" -m "Device: $(hostname -s)"
```

---

### Task 4: Document Paperclip without implying unsupported asset support

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md`
- Modify: `scripts/gen_harness_docs.py`
- Regenerate: `docs/matrix.md`
- Create through generator: `docs/harnesses/paperclip.md`
- Regenerate: `mkdocs.yml`
- Test: `tests/test_instructions_matrix.py`
- Test: `tests/test_subagent_matrix.py`
- Create: `tests/test_harness_docs.py`

**Interfaces:**
- Consumes: catalog token `paperclip` and TUI main-harness decision.
- Produces: complete parity-table rows and generated public documentation.

- [ ] **Step 1: Run parity/generator checks to observe the missing-row failure**

Run: `uv run pytest tests/test_instructions_matrix.py tests/test_subagent_matrix.py -q`

Expected: both parity suites report `paperclip` missing after Task 2’s catalog addition.

- [ ] **Step 2: Add honest Paperclip matrix rows and update counts**

In `docs/agent-toolkit/harness-matrix.md`:

- Change both table row counts from 54 to 55.
- Change Skills compliance from `14 / 54` to `14 / 55`; Paperclip is adapter-backed, not Standard.
- Change Instructions and Agents denominators to 55 and add one unsupported/unknown row to their summary arithmetic.
- Add the alphabetically placed Instructions row:

```markdown
| `paperclip` | unsupported (by design) | none | none / none | no |  | Paperclip company integration in Agent Toolkit is intentionally Skills-only; issue #474 |
```

- Add the alphabetically placed Subagents row:

```markdown
| `paperclip` | unsupported (by design) |  |  | company-scoped Skills library only; no Agent asset adapter | issue #474 |
```

Do not claim Paperclip reads `AGENTS.md`, commands, MCP configuration, or Agent Toolkit agent definitions.

- [ ] **Step 3: Add generator headline/logo and contextual Skills metadata**

```python
# scripts/gen_harness_docs.py
MAIN = ["claude-code", "pi", "codex", "gemini-cli", "opencode", "paperclip"]
LOGOS["paperclip"] = _fav("paperclip.ing")

SKILLS_OVERRIDES = {
    "paperclip": {
        "summary": (
            "Supported at project scope for a detected Paperclip company; "
            "global scope is unavailable."
        ),
        "project_dir": "<instance-root>/skills/<company-id>",
        "global_dir": "unavailable — Paperclip skills are company-scoped",
        "general": "no — gets a company-library projection",
        "source": "Agent Toolkit issue #474 and its approved design",
    },
}
```

Update `skills_section()` to render `SKILLS_OVERRIDES[slug]` when present and retain the existing catalog-based branch for every other harness. The Paperclip page must never render the catalog sentinel `.paperclip-company/skills`, the non-actionable `~/.paperclip/skills`, or vercel-labs attribution as the source for this custom entry.

- [ ] **Step 4: Regenerate owned documentation**

Run: `uv run python scripts/gen_harness_docs.py`

Expected: `docs/harnesses/paperclip.md` is created, `docs/matrix.md` includes Paperclip as a headline harness, and the generated harness navigation in `mkdocs.yml` includes Paperclip.

- [ ] **Step 5: Run matrix and generated-doc tests**

Run: `uv run pytest tests/test_instructions_matrix.py tests/test_subagent_matrix.py tests/test_harness_docs.py tests/test_tui/test_composition.py -q`

Expected: all parity and main-harness coverage tests pass.

- [ ] **Step 6: Inspect the generated Paperclip page for honest capability labels**

Run:

```bash
rg -n "Paperclip|Skills|Instructions|Subagents|Commands|MCP|instances/.*/skills" docs/harnesses/paperclip.md docs/matrix.md
! rg -n "\.paperclip-company/skills|~/.paperclip/skills|vercel-labs/skills" docs/harnesses/paperclip.md
```

Expected: Skills is supported through the company-scoped project path, global scope is unavailable, custom-source attribution is honest, and unsupported/unknown asset types do not show actionable support. Add a generator test that asserts these exact inclusions/exclusions so later regeneration cannot reintroduce sentinel paths.

- [ ] **Step 7: Commit documentation and generated views**

```bash
git add docs/agent-toolkit/harness-matrix.md scripts/gen_harness_docs.py docs/matrix.md docs/harnesses/paperclip.md mkdocs.yml tests/test_harness_docs.py
git commit -m "docs: add Paperclip harness compatibility" -m "Device: $(hostname -s)"
```

---

### Task 5: Verify the complete company-scope lifecycle and visible TUI

**Files:**
- Modify if required by failures: only files already listed in Tasks 1–4
- Create evidence: `assets/verification/issue-474/`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: full-suite evidence and a written visual judgment for issue #474.

- [ ] **Step 1: Run focused Paperclip and regression tests**

Run:

```bash
uv run pytest \
  tests/test_cli/test_paperclip_paths.py \
  tests/test_cli/test_cli_skill_paperclip.py \
  tests/test_cli/test_cli_skill_install.py \
  tests/test_cli/test_skill_install_engine.py \
  tests/test_cli/test_cli_skill_list.py \
  tests/test_cli/test_cli_skill_doctor.py \
  tests/test_tui/test_paperclip_skill_tui.py \
  tests/test_tui/test_skill_state.py \
  tests/test_tui/test_skill_grid_apply.py \
  tests/test_tui/test_composition.py \
  tests/test_harness_docs.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the project’s declared verification floor**

If `TESTING.md` exists, run its highest committed rung. Otherwise run:

`uv run pytest -q`

Expected: zero failures.

- [ ] **Step 3: Exercise a hermetic CLI lifecycle**

Create a temporary HOME and Paperclip company fixture through the integration-test helper or a checked-in test script; do not target the live `~/.paperclip` tree. Verify:

- install from a descendant resolves the company root;
- `skills-lock.json` appears only at the company root;
- `<instance>/skills/<company-id>/<slug>` resolves to the external canonical;
- `.agents/skills/<slug>` is absent;
- uninstall removes the owned Paperclip projection;
- a foreign destination is preserved and returns non-zero.

Save command output to `assets/verification/issue-474/cli.txt`.

- [ ] **Step 4: Capture TUI evidence and written visual judgment**

Capture these named artifacts under `assets/verification/issue-474/`:

- `paperclip-company-before-apply.*` — company project Skills pane with actionable Paperclip cell;
- `paperclip-company-after-apply.*` — linked cell plus visible success footer;
- `paperclip-global-unavailable.*` — global-scope unavailable glyph with the `i` info screen explaining “switch to Project scope”;
- `paperclip-unsupported-pane.*` — one non-Skills pane showing no Paperclip action.

Write `assets/verification/issue-474/verdict.md` containing:

```markdown
# Visual judgment

PASS — `paperclip-company-before-apply` and `paperclip-company-after-apply` show the dedicated Paperclip Skills column transition from actionable to linked with success feedback. `paperclip-global-unavailable` shows the non-actionable global state and corrective copy. `paperclip-unsupported-pane` confirms no Paperclip action leaks into unsupported asset panes.
```

- [ ] **Step 5: Check the final diff for forbidden API/auth scope**

Run:

```bash
base=$(git merge-base origin/main HEAD)
git diff "$base"..HEAD -- src tests | rg -n "requests|httpx|urllib|/api/|PAPERCLIP_API|API_KEY|token|Authorization" || true
```

Expected: no new Paperclip API, authentication, token, or credential implementation.

- [ ] **Step 6: Commit verification evidence**

```bash
git add assets/verification/issue-474
git commit -m "test(paperclip): verify company skill lifecycle" -m "Device: $(hostname -s)"
```

- [ ] **Step 7: Final status audit**

Run: `git status --short && git log --oneline --decorate -6`

Expected: implementation worktree clean; commits are scoped to issue #474; no unrelated files are staged or committed.

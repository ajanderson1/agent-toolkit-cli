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

### Modified files

- `src/agent_toolkit_cli/skill_agents.py` — register `paperclip` as a real, non-Standard Skills harness.
- `src/agent_toolkit_cli/skill_paths.py` — resolve the Paperclip project projection destination at the existing path boundary.
- `src/agent_toolkit_cli/skill_install.py` — preflight company-only projection targets before any mutation.
- `src/agent_toolkit_cli/commands/skill/_common.py` — normalize implicit/explicit skill project roots and recognize Paperclip context before lockfile fallback.
- `src/agent_toolkit_cli/commands/skill/__init__.py` — make omitted install/uninstall scope Paperclip-aware while preserving the ordinary global default.
- `src/agent_toolkit_tui/skill_state.py` — represent unavailable company-only cells and probe Paperclip projections safely.
- `src/agent_toolkit_tui/widgets/skill_grid.py` — render unavailable cells, block toggles, and explain context requirements.
- `src/agent_toolkit_tui/app.py` — use the normalized skill project root for refresh/apply and preflight before canonical materialization.
- `src/agent_toolkit_tui/composition.py` — include `paperclip` in the main harness set.
- `src/agent_toolkit_tui/display_names.py` — render `Paperclip`.
- `tests/test_cli/test_skill_agents.py` — pin the new catalog count/configuration.
- `tests/test_cli/test_cli_skill_scope_banner.py` — pin Paperclip implicit project-scope behavior.
- `tests/test_tui/test_composition.py` — pin main-harness coverage and exclude unsupported asset actions.
- `tests/test_tui/test_display_names.py` — pin the Paperclip display label.
- `tests/test_tui/test_skill_grid_apply.py` — teach shared fixtures about cell availability.
- `docs/agent-toolkit/harness-matrix.md` — add Paperclip to all-harness parity rows and update counts.
- `scripts/gen_harness_docs.py` — mark Paperclip as headline and supply its logo metadata.
- `docs/matrix.md`, `docs/harnesses/paperclip.md`, `mkdocs.yml` — regenerated compatibility views/navigation.

---

### Task 1: Detect and normalize Paperclip company roots

**Files:**
- Create: `src/agent_toolkit_cli/paperclip_paths.py`
- Create: `tests/test_cli/test_paperclip_paths.py`
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py`
- Modify: `tests/test_cli/test_cli_skill_scope_banner.py`

**Interfaces:**
- Produces: `PaperclipCompanyContext`, `PaperclipContextError`, `detect_paperclip_company(path, *, paperclip_root=None)`, `require_paperclip_company(path, *, paperclip_root=None)`, and `normalize_skill_project_root(path)`.
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
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Modify: `tests/test_cli/test_skill_agents.py`
- Create: `tests/test_cli/test_cli_skill_paperclip.py`

**Interfaces:**
- Consumes: `require_paperclip_company()` and `normalize_skill_project_root()` from Task 1.
- Produces: catalog token `paperclip`, Paperclip-aware `agent_projection_dir()`, and `validate_projection_context(slug, target_agents, scope, home, project)`.

- [ ] **Step 1: Write failing catalog and destination tests**

```python
# tests/test_cli/test_skill_agents.py

def test_paperclip_is_company_scoped_skill_harness():
    cfg = AGENTS["paperclip"]
    assert cfg.display_name == "Paperclip"
    assert not cfg.is_standard
    assert cfg.subagent_mechanism == "none"
    assert "company-scoped Skills" in cfg.disabled_reason

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
    detect_installed=lambda: (HOME / ".paperclip").exists(),
    subagent_mechanism="none",
    disabled_reason="company-scoped Skills harness only; no Agent asset adapter",
),
```

```python
# src/agent_toolkit_cli/skill_paths.py
from agent_toolkit_cli.paperclip_paths import require_paperclip_company

# At the start of agent_projection_dir(), after validating agent_name:
if agent_name == "paperclip":
    if scope != "project" or project is None:
        raise ValueError("Paperclip skills are company-scoped and require project scope")
    return require_paperclip_company(project).skills_root / slug
```

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
    if "paperclip" not in target_agents:
        return
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

Call `validate_projection_context()` with concrete `slug`, agents, scope, home, and project arguments at the top of both `plan()` and `apply()` before canonical or lock resolution. Also call it from CLI/TUI project install before `ensure_project_canonical()`. This ensures direct engine callers receive the same fail-loud contract and destination conflicts cannot leave a new project canonical or lock entry behind.

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

Then resolve before materialization in both commands:

```python
candidate = (ctx.obj.get("project_root") if ctx.obj else None) or Path.cwd()
context = detect_paperclip_company(candidate)
if project_flag:
    scope = "project"
elif scope is None:
    scope = "project" if context is not None else "global"
project_root = normalize_skill_project_root(candidate) if scope == "project" else None
validate_projection_context(
    slug=slug,
    target_agents=target_agents,
    scope=scope,
    home=None if scope == "project" else Path.home(),
    project=project_root,
)
```

Preserve the existing ordinary no-flag behavior: outside Paperclip, `skill install demo` still installs Standard globally.

- [ ] **Step 7: Run CLI integration and regression tests**

Run: `uv run pytest tests/test_cli/test_cli_skill_paperclip.py tests/test_cli/test_cli_skill_install.py tests/test_cli/test_skill_install_engine.py tests/test_cli/test_skill_paths.py -q`

Expected: all tests pass; no test writes beneath the real home directory.

- [ ] **Step 8: Commit the projection unit**

```bash
git add src/agent_toolkit_cli/skill_agents.py src/agent_toolkit_cli/skill_paths.py src/agent_toolkit_cli/skill_install.py src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_agents.py tests/test_cli/test_cli_skill_paperclip.py
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
    if scope != "project" or project is None or detect_paperclip_company(project) is None:
        return SkillCell(
            linked=False,
            drift=False,
            skipped=False,
            available=False,
            unavailable_reason=(
                "Paperclip skills are company-scoped; open the TUI inside "
                "~/.paperclip/instances/<instance>/companies/<company-id>."
            ),
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
async def test_apply_uses_normalized_company_root(monkeypatch, tmp_path):
    # Run TUIApp from a descendant; monkeypatch engine_apply and
    # ensure_project_canonical; assert both receive the detected company root,
    # never the descendant and never a .agents projection target.
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

- [ ] **Step 3: Add generator headline/logo metadata**

```python
# scripts/gen_harness_docs.py
MAIN = ["claude-code", "pi", "codex", "gemini-cli", "opencode", "paperclip"]
LOGOS["paperclip"] = _fav("paperclip.ing")
```

- [ ] **Step 4: Regenerate owned documentation**

Run: `uv run python scripts/gen_harness_docs.py`

Expected: `docs/harnesses/paperclip.md` is created, `docs/matrix.md` includes Paperclip as a headline harness, and the generated harness navigation in `mkdocs.yml` includes Paperclip.

- [ ] **Step 5: Run matrix and generated-doc tests**

Run: `uv run pytest tests/test_instructions_matrix.py tests/test_subagent_matrix.py tests/test_tui/test_composition.py -q`

Expected: all parity and main-harness coverage tests pass.

- [ ] **Step 6: Inspect the generated Paperclip page for honest capability labels**

Run: `rg -n "Paperclip|Skills|Instructions|Subagents|Commands|MCP" docs/harnesses/paperclip.md docs/matrix.md`

Expected: Skills is supported through the company-scoped path; unsupported/unknown asset types do not show actionable support.

- [ ] **Step 7: Commit documentation and generated views**

```bash
git add docs/agent-toolkit/harness-matrix.md scripts/gen_harness_docs.py docs/matrix.md docs/harnesses/paperclip.md mkdocs.yml
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
  tests/test_tui/test_paperclip_skill_tui.py \
  tests/test_tui/test_skill_state.py \
  tests/test_tui/test_skill_grid_apply.py \
  tests/test_tui/test_composition.py -q
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

Launch the TUI against the temporary company fixture, capture the Skills pane, and save the artifact under `assets/verification/issue-474/`. Write `assets/verification/issue-474/verdict.md` containing:

```markdown
# Visual judgment

PASS — The Skills pane shows Paperclip as a dedicated main-harness column in company project scope. The Paperclip cell is actionable in the company fixture, unavailable outside company scope, and no unsupported asset pane presents a Paperclip action.
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

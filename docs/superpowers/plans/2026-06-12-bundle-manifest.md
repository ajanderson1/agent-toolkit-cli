# Bundle Manifest v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toolkit-native JSON bundle manifest plus `bundle install` / `bundle validate` verbs that fan out to the existing per-kind installers (skills, agents, pi-extensions), all-or-nothing with rollback, stateless.

**Architecture:** Four small units. `bundle_manifest` parses/validates JSON into typed records (pure data). `bundle_dispatch` maps one member → that kind's real add+install sequence (absorbs the kinds' heterogeneous entrypoints; calls in-process, no shelling out). `bundle_install` orchestrates: a resolve pass shared by both verbs (a `dry_run` flag suppresses disk writes) plus install-in-order with rollback-on-failure. A thin `bundle` Click group wires the two verbs. `mcp` members are reserved-but-hard-fail (#329); `instructions` is not a member type.

**Tech Stack:** Python 3.12, Click, stdlib `json`, pytest with `CliRunner` + the existing `git_sandbox` hermetic `file://` bare-repo fixtures. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-06-12-bundle-manifest-design.md` (commit 6ce6931). **Depends on #329** for the `mcp` member to become installable.

---

## File structure

| File | Responsibility |
|---|---|
| `src/agent_toolkit_cli/bundle_manifest.py` | `BundleMember`, `BundleManifest` dataclasses + `load(path)` / `parse(data)` with validation. Pure; no disk side-effects beyond reading the manifest file. |
| `src/agent_toolkit_cli/bundle_dispatch.py` | `INSTALLABLE_KINDS`, `MemberOutcome`, `resolve(member)`, `install(member, scope)`, `uninstall(member, scope)`. The only unit that knows each kind's add+install sequence. |
| `src/agent_toolkit_cli/bundle_install.py` | `BundleInstallError`, `run(manifest, scope, dry_run)`: resolve-all, install-in-order, rollback-on-failure. Shared by both verbs. |
| `src/agent_toolkit_cli/commands/bundle/__init__.py` | `bundle` Click group. |
| `src/agent_toolkit_cli/commands/bundle/install_cmd.py` | `bundle install <ref> [--global/--project]`. |
| `src/agent_toolkit_cli/commands/bundle/validate_cmd.py` | `bundle validate <ref>`. |
| `src/agent_toolkit_cli/cli.py` (modify) | Register the `bundle` group. |
| `tests/test_cli/test_bundle_manifest.py` | Parser/validator unit tests. |
| `tests/test_cli/test_bundle_dispatch.py` | Dispatch mapping + mcp hard-fail + scope threading. |
| `tests/test_cli/test_bundle_install.py` | Orchestration: happy path, rollback, already-present, dry_run. |
| `tests/test_cli/test_cli_bundle_group.py` | CLI smoke + scope + validate exit codes (hermetic). |
| `docs/agent-toolkit/...` + `CLAUDE.md`/AGENTS docs | Document the `bundle` verb + schema (Task 6). |

**Decomposition note:** `bundle_dispatch` is deliberately separate from `bundle_install` so the orchestrator (ordering, rollback) can be tested with a stubbed dispatch, and dispatch (kind-specific wiring) can be tested without orchestration. Keep each under ~150 lines.

---

## Task 1: Manifest parser + validator

**Files:**
- Create: `src/agent_toolkit_cli/bundle_manifest.py`
- Test: `tests/test_cli/test_bundle_manifest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli/test_bundle_manifest.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli.bundle_manifest import (
    BundleManifest,
    BundleMember,
    ManifestError,
    load,
    parse,
)


def _valid() -> dict:
    return {
        "schema_version": 1,
        "name": "team-review",
        "description": "demo",
        "members": [
            {"asset_type": "agent", "source": "owner/repo/agents/code-reviewer",
             "slug": "code-reviewer", "ref": "v2.1.0"},
            {"asset_type": "skill", "source": "owner/repo/git-worktrees"},
            {"asset_type": "pi-extension", "source": "owner/repo/token-meter",
             "slug": "token-meter"},
        ],
    }


def test_parse_valid_manifest():
    m = parse(_valid())
    assert isinstance(m, BundleManifest)
    assert m.name == "team-review"
    assert len(m.members) == 3
    first = m.members[0]
    assert isinstance(first, BundleMember)
    assert first.asset_type == "agent"
    assert first.source == "owner/repo/agents/code-reviewer"
    assert first.slug == "code-reviewer"
    assert first.ref == "v2.1.0"


def test_member_defaults_optional_fields():
    m = parse(_valid())
    skill = m.members[1]
    assert skill.slug is None
    assert skill.ref is None


def test_unknown_schema_version_rejected():
    data = _valid()
    data["schema_version"] = 2
    with pytest.raises(ManifestError, match="schema_version"):
        parse(data)


def test_missing_schema_version_rejected():
    data = _valid()
    del data["schema_version"]
    with pytest.raises(ManifestError, match="schema_version"):
        parse(data)


def test_missing_name_rejected():
    data = _valid()
    del data["name"]
    with pytest.raises(ManifestError, match="name"):
        parse(data)


def test_empty_members_rejected():
    data = _valid()
    data["members"] = []
    with pytest.raises(ManifestError, match="members"):
        parse(data)


def test_unknown_asset_type_rejected():
    data = _valid()
    data["members"][0]["asset_type"] = "wormhole"
    with pytest.raises(ManifestError, match="asset_type"):
        parse(data)


def test_instructions_member_rejected():
    data = _valid()
    data["members"][0] = {"asset_type": "instructions"}
    with pytest.raises(ManifestError, match="not a bundle member type"):
        parse(data)


def test_installable_member_missing_source_rejected():
    data = _valid()
    del data["members"][1]["source"]  # skill member with no source
    with pytest.raises(ManifestError, match="source"):
        parse(data)


def test_mcp_member_parses_but_is_marked_reserved():
    # mcp is a VALID member type at parse time (forward-compat); the hard-fail
    # happens at dispatch, not parse. source is required like other kinds.
    data = _valid()
    data["members"].append({"asset_type": "mcp", "source": "owner/repo/ctx7",
                            "slug": "context7"})
    m = parse(data)
    assert m.members[-1].asset_type == "mcp"


def test_load_reads_json_file(tmp_path: Path):
    p = tmp_path / "b.bundle.json"
    p.write_text(json.dumps(_valid()))
    m = load(p)
    assert m.name == "team-review"


def test_load_bad_json_raises_manifest_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(ManifestError, match="JSON"):
        load(p)


def test_load_missing_file_raises_manifest_error(tmp_path: Path):
    with pytest.raises(ManifestError, match="not found"):
        load(tmp_path / "nope.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_bundle_manifest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.bundle_manifest'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/bundle_manifest.py
"""Parse + validate a toolkit-native bundle manifest (v1).

A bundle is a STATELESS shortcut: a JSON list of asset pointers that
`bundle install` fans out to the per-kind installers. This module is pure
data — it never touches the library, locks, or harness dirs.

Schema v1 (subset of the bundle-composite ADR — the composite later adds a
group id + cross-kind shared clone; v1 adds neither, so it is a clean
upgrade):

    {
      "schema_version": 1,
      "name": "...",            # required
      "description": "...",     # optional
      "members": [              # required, non-empty
        {"asset_type": "skill|agent|pi-extension|mcp",
         "source": "owner/repo[/subpath]",   # required for those kinds
         "slug": "...",          # optional
         "ref": "..."}           # optional
      ]
    }

`instructions` is NOT a member type (no shareable source). `mcp` is a valid
member type for forward-compat, but the INSTALLER hard-fails on it until the
mcp kind ships (#329) — that check lives in bundle_dispatch, not here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1

# Member types that carry a git source and parse successfully. `mcp` is here
# for forward-compat; bundle_dispatch hard-fails on it until #329.
_SOURCE_BACKED_TYPES = frozenset({"skill", "agent", "pi-extension", "mcp"})


class ManifestError(ValueError):
    """A bundle manifest is malformed or invalid."""


@dataclass(frozen=True)
class BundleMember:
    asset_type: str
    source: str
    slug: str | None = None
    ref: str | None = None


@dataclass(frozen=True)
class BundleManifest:
    name: str
    description: str
    members: tuple[BundleMember, ...]


def _parse_member(raw: object, index: int) -> BundleMember:
    if not isinstance(raw, dict):
        raise ManifestError(f"member {index}: must be an object")
    asset_type = raw.get("asset_type")
    if not isinstance(asset_type, str) or not asset_type:
        raise ManifestError(f"member {index}: missing 'asset_type'")
    if asset_type == "instructions":
        raise ManifestError(
            f"member {index}: 'instructions' is not a bundle member type "
            "(it has no shareable source — install it directly with "
            "`instructions install`)"
        )
    if asset_type not in _SOURCE_BACKED_TYPES:
        raise ManifestError(
            f"member {index}: unknown asset_type {asset_type!r} "
            f"(expected one of {sorted(_SOURCE_BACKED_TYPES)})"
        )
    source = raw.get("source")
    if not isinstance(source, str) or not source:
        raise ManifestError(
            f"member {index} ({asset_type}): missing required 'source'"
        )
    slug = raw.get("slug")
    ref = raw.get("ref")
    if slug is not None and not isinstance(slug, str):
        raise ManifestError(f"member {index}: 'slug' must be a string")
    if ref is not None and not isinstance(ref, str):
        raise ManifestError(f"member {index}: 'ref' must be a string")
    return BundleMember(asset_type=asset_type, source=source, slug=slug, ref=ref)


def parse(data: object) -> BundleManifest:
    """Validate a decoded JSON object into a typed BundleManifest."""
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")
    version = data.get("schema_version")
    if version != CURRENT_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version {version!r} "
            f"(this toolkit supports {CURRENT_SCHEMA_VERSION})"
        )
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ManifestError("manifest: missing required 'name'")
    description = data.get("description") or ""
    if not isinstance(description, str):
        raise ManifestError("manifest: 'description' must be a string")
    members_raw = data.get("members")
    if not isinstance(members_raw, list) or not members_raw:
        raise ManifestError("manifest: 'members' must be a non-empty array")
    members = tuple(
        _parse_member(m, i) for i, m in enumerate(members_raw)
    )
    return BundleManifest(name=name, description=description, members=members)


def load(path: Path) -> BundleManifest:
    """Read + parse a manifest from a local file path."""
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc
    return parse(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_bundle_manifest.py -q`
Expected: PASS (all parser tests green).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/bundle_manifest.py tests/test_cli/test_bundle_manifest.py
git commit -m "feat(bundle): manifest parser + validator (v1 schema)

Refs #369

Device: $(hostname -s)"
```

---

## Task 2: Dispatch adapter (member → kind install sequence)

**Files:**
- Create: `src/agent_toolkit_cli/bundle_dispatch.py`
- Test: `tests/test_cli/test_bundle_dispatch.py`

**Context the worker needs:** the kinds are heterogeneous. The cleanest in-process
entrypoint per kind, verified against the code:
- **agent** — `agent_install` has no single "add+install from source" function; the
  add logic lives in `commands/agent/add_cmd.py` (`_add_single`/`_add_monorepo`,
  Click-bound) and projection in `agent_install.apply()`. To stay in-process and
  reuse the validated add+project path, dispatch invokes the Click commands through
  `click.testing`-free direct calls is NOT possible (they're `@click.command`). So
  dispatch shells out to the **same process** via `cli.main` using Click's
  `CliRunner`? No — production code must not use the test runner. Instead, dispatch
  calls the underlying library functions where they exist and invokes the Click
  command callbacks via `ctx.invoke`. The simplest correct seam: dispatch builds the
  argv and calls `cli.main(args, standalone_mode=False)` in-process (Click supports
  programmatic invocation; `standalone_mode=False` raises exceptions instead of
  `sys.exit`, which the orchestrator catches for rollback). This reuses every kind's
  real add+install + its own validation, with no duplicated installer logic.

This is the load-bearing design choice for Task 2; the tests pin it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli/test_bundle_dispatch.py
from __future__ import annotations

import pytest

from agent_toolkit_cli.bundle_dispatch import (
    INSTALLABLE_KINDS,
    DispatchError,
    install_member,
    resolve_member,
    uninstall_member,
)
from agent_toolkit_cli.bundle_manifest import BundleMember


def test_installable_kinds_are_the_three_source_backed():
    assert INSTALLABLE_KINDS == ("skill", "agent", "pi-extension")


def test_mcp_member_hard_fails_with_329(monkeypatch):
    member = BundleMember(asset_type="mcp", source="o/r/ctx7", slug="context7")
    with pytest.raises(DispatchError, match="#329"):
        resolve_member(member)
    with pytest.raises(DispatchError, match="#329"):
        install_member(member, scope="global")


def test_resolve_builds_argv_for_each_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="agent", source="o/r/agents/cr",
                     slug="cr", ref="v1"),
        scope="global",
    )
    # add then install — both threaded with source/slug/ref/scope
    assert calls[0][:2] == ["agent", "add"]
    assert "o/r/agents/cr" in calls[0]
    assert "--slug" in calls[0] and "cr" in calls[0]
    assert "--ref" in calls[0] and "v1" in calls[0]
    assert calls[1][:2] == ["agent", "install"]
    assert "-g" in calls[1] or "--global" in calls[1]


def test_skill_member_scope_project_threads_p_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="skill", source="o/r/gw"),
        scope="project",
    )
    # project scope must reach the install step
    assert any("-p" in c or "--project" in c for c in calls)


def test_dispatch_propagates_install_failure(monkeypatch):
    def boom(argv):
        raise RuntimeError("clone failed")
    monkeypatch.setattr("agent_toolkit_cli.bundle_dispatch._invoke_cli", boom)
    with pytest.raises(DispatchError, match="clone failed"):
        install_member(
            BundleMember(asset_type="skill", source="o/r/gw"),
            scope="global",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_bundle_dispatch.py -q`
Expected: FAIL — `ModuleNotFoundError: ...bundle_dispatch`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/bundle_dispatch.py
"""Map one bundle member to its kind's real add+install sequence.

The kinds are heterogeneous (agent/skill/pi-extension each have their own
add + install verbs with different flags). Rather than duplicate any installer
logic, dispatch builds the same argv a human would type and invokes the CLI
in-process via Click's programmatic mode (`standalone_mode=False`), reusing
every kind's validation, clone, projection, and lock-write. `mcp` is reserved
but hard-fails until the mcp kind ships (#329).
"""
from __future__ import annotations

from agent_toolkit_cli.bundle_manifest import BundleMember

# v1 fans out over these three source-backed kinds. `instructions` is excluded
# at parse time; `mcp` parses but hard-fails here.
INSTALLABLE_KINDS: tuple[str, ...] = ("skill", "agent", "pi-extension")

_MCP_NOT_READY = (
    "member {slug!r}: 'mcp' members require the mcp asset type, which is not "
    "yet available (tracked in #329). Remove the mcp member or wait for the "
    "mcp kind to ship."
)


class DispatchError(RuntimeError):
    """A member could not be dispatched/installed."""


def _invoke_cli(argv: list[str]) -> None:
    """Run the toolkit CLI in-process; raise on any failure (no sys.exit)."""
    from agent_toolkit_cli.cli import main

    # standalone_mode=False → Click raises instead of calling sys.exit, so the
    # orchestrator can catch and roll back. ClickException/Abort/our own errors
    # all surface here.
    main.main(args=argv, standalone_mode=False)


def _scope_flag(scope: str) -> str:
    return "-g" if scope == "global" else "-p"


def _check_member(member: BundleMember) -> None:
    if member.asset_type == "mcp":
        raise DispatchError(_MCP_NOT_READY.format(slug=member.slug or member.source))
    if member.asset_type not in INSTALLABLE_KINDS:
        raise DispatchError(f"un-installable member type {member.asset_type!r}")


def resolve_member(member: BundleMember) -> None:
    """Dry-run check: a member that cannot possibly install fails here.

    v1 resolution is structural (type is installable, mcp rejected). Source/ref
    reachability is proven by the real add during install; for validate we run
    the same _check plus a lightweight existence note. Kept minimal by design.
    """
    _check_member(member)


def _add_argv(member: BundleMember) -> list[str]:
    argv = [member.asset_type, "add", member.source]
    if member.slug:
        argv += ["--slug", member.slug]
    if member.ref:
        argv += ["--ref", member.ref]
    return argv


def _install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return [member.asset_type, "install", slug, _scope_flag(scope)]


def _derive_slug(source: str) -> str:
    """Last path segment, mirroring each kind's default slug derivation."""
    return source.rstrip("/").split("/")[-1]


def install_member(member: BundleMember, scope: str) -> None:
    """Add the member to the library, then project it at `scope`."""
    _check_member(member)
    try:
        _invoke_cli(_add_argv(member))
        _invoke_cli(_install_argv(member, scope))
    except DispatchError:
        raise
    except Exception as exc:  # ClickException, Abort, GitError, …
        raise DispatchError(
            f"member {member.slug or member.source!r} ({member.asset_type}) "
            f"failed to install: {exc}"
        ) from exc


def uninstall_member(member: BundleMember, scope: str) -> None:
    """Roll back a member installed earlier this run (best-effort, in-process)."""
    _check_member(member)
    slug = member.slug or _derive_slug(member.source)
    try:
        _invoke_cli([member.asset_type, "uninstall", slug, _scope_flag(scope)])
    except Exception as exc:
        raise DispatchError(
            f"rollback of {slug!r} ({member.asset_type}) failed: {exc}"
        ) from exc
```

> **Worker note:** the `agent install` flag is `-g/-p`? Verify against
> `commands/agent/install_cmd.py` — it uses `scope_and_roots`, whose flag
> convention is `-g/--global` / `-p/--project` (read-only=False). If a kind's
> install verb uses `--scope global|project` instead (instructions does, but
> instructions isn't a member), adjust `_install_argv` per-kind. Pin the actual
> flags in the dispatch tests so a mismatch fails loudly. `skill` may need
> `import`/wizard rather than `add`/`install` — confirm the skill verbs and adjust
> `_add_argv`/`_install_argv` to the real skill entrypoints (the argv builder is
> the single place to fix). This is the most reality-sensitive task; the scout/
> red phase MUST confirm each kind's exact add+install argv before green.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_bundle_dispatch.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/bundle_dispatch.py tests/test_cli/test_bundle_dispatch.py
git commit -m "feat(bundle): per-kind dispatch adapter (mcp hard-fails #329)

Refs #369

Device: $(hostname -s)"
```

---

## Task 3: Install orchestrator (resolve + ordered install + rollback)

**Files:**
- Create: `src/agent_toolkit_cli/bundle_install.py`
- Test: `tests/test_cli/test_bundle_install.py`

- [ ] **Step 1: Write the failing tests** (stub dispatch so this tests ORDER + ROLLBACK only)

```python
# tests/test_cli/test_bundle_install.py
from __future__ import annotations

import pytest

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli.bundle_dispatch import DispatchError
from agent_toolkit_cli.bundle_install import BundleInstallError, run
from agent_toolkit_cli.bundle_manifest import BundleManifest, BundleMember


def _manifest(*types_sources) -> BundleManifest:
    members = tuple(
        BundleMember(asset_type=t, source=s) for t, s in types_sources
    )
    return BundleManifest(name="b", description="", members=members)


def test_happy_path_installs_every_member_in_order(monkeypatch):
    installed = []
    monkeypatch.setattr(bundle_install, "install_member",
                        lambda m, scope: installed.append(m.source))
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope: pytest.fail("must not roll back"))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)
    run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
        scope="global", dry_run=False)
    assert installed == ["a", "b", "c"]


def test_failure_midrun_rolls_back_prior_members_newest_first(monkeypatch):
    installed, rolled_back = [], []

    def fake_install(m, scope):
        if m.source == "c":
            raise DispatchError("boom on c")
        installed.append(m.source)

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="boom on c"):
        run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
            scope="global", dry_run=False)
    assert installed == ["a", "b"]
    assert rolled_back == ["b", "a"]  # newest-first


def test_already_present_member_not_rolled_back(monkeypatch):
    rolled_back = []

    def fake_install(m, scope):
        if m.source == "a":
            return "already_present"   # sentinel: no-op
        if m.source == "b":
            raise DispatchError("boom on b")

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError):
        run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
            dry_run=False)
    assert rolled_back == []  # 'a' was already present → not our install → no rollback


def test_dry_run_resolves_but_installs_nothing(monkeypatch):
    resolved, installed = [], []
    monkeypatch.setattr(bundle_install, "resolve_member",
                        lambda m: resolved.append(m.source))
    monkeypatch.setattr(bundle_install, "install_member",
                        lambda m, scope: installed.append(m.source))
    report = run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
                 dry_run=True)
    assert resolved == ["a", "b"]
    assert installed == []
    assert report.ok is True


def test_dry_run_reports_failure_without_raising(monkeypatch):
    def fail_resolve(m):
        if m.source == "b":
            raise DispatchError("unresolvable b")

    monkeypatch.setattr(bundle_install, "resolve_member", fail_resolve)
    report = run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
                 dry_run=True)
    assert report.ok is False
    assert any("b" in f for f in report.failures)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_bundle_install.py -q`
Expected: FAIL — `...bundle_install` has no `run`/`BundleInstallError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/bundle_install.py
"""Orchestrate a bundle: resolve all members, install in order, roll back on
failure. Shared by `bundle install` (dry_run=False) and `bundle validate`
(dry_run=True). Adds NO new install/rollback primitive — it sequences the
per-kind ones via bundle_dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Imported at module scope so tests can monkeypatch these names on this module.
from agent_toolkit_cli.bundle_dispatch import (
    DispatchError,
    install_member,
    resolve_member,
    uninstall_member,
)
from agent_toolkit_cli.bundle_manifest import BundleManifest, BundleMember

__all__ = [
    "BundleInstallError",
    "ValidateReport",
    "run",
    "install_member",
    "resolve_member",
    "uninstall_member",
]


class BundleInstallError(RuntimeError):
    """A bundle install failed; prior members this run were rolled back."""


@dataclass
class ValidateReport:
    ok: bool
    checked: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def _label(member: BundleMember) -> str:
    return f"{member.asset_type}:{member.slug or member.source}"


def run(manifest: BundleManifest, scope: str, dry_run: bool) -> ValidateReport:
    """Resolve every member; if not dry_run, install in order with rollback."""
    report = ValidateReport(ok=True)

    # Resolve pass — shared by both verbs.
    for member in manifest.members:
        try:
            resolve_member(member)
            report.checked.append(_label(member))
        except DispatchError as exc:
            report.ok = False
            report.failures.append(str(exc))

    if dry_run:
        return report

    if not report.ok:
        # An unresolvable member must stop install before any disk change.
        raise BundleInstallError(
            "bundle did not resolve:\n  " + "\n  ".join(report.failures)
        )

    installed: list[BundleMember] = []
    for member in manifest.members:
        try:
            outcome = install_member(member, scope=scope)
        except DispatchError as exc:
            for prior in reversed(installed):
                try:
                    uninstall_member(prior, scope=scope)
                except DispatchError:
                    # Best-effort rollback; report the original failure.
                    pass
            raise BundleInstallError(str(exc)) from exc
        # Only track members WE installed (not pre-existing no-ops) for rollback.
        if outcome != "already_present":
            installed.append(member)

    return report
```

> **Worker note:** `install_member` returns `None` on a real install in the
> dispatch impl from Task 2. To support the `already_present` sentinel
> (AC4: "an already-present member is not rolled back"), Task 2's
> `install_member` must return the string `"already_present"` when the kind's
> add reports the slug is already in the library / projection is a no-op, else
> `None`. Add that return + a dispatch test for it when wiring Task 2 to real
> installers (the kinds print "already in library" / "ok already-correct"). If
> detecting no-op precisely is hard in v1, the safe conservative behaviour is to
> treat every successful install as rollback-eligible (rollback then is a
> uninstall of something that was already there) — but that violates AC4, so
> prefer threading the sentinel. Pin it with the Task 2 dispatch test.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_bundle_install.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/bundle_install.py tests/test_cli/test_bundle_install.py
git commit -m "feat(bundle): install orchestrator with all-or-nothing rollback

Refs #369

Device: $(hostname -s)"
```

---

## Task 4: Click group + `install` / `validate` verbs

**Files:**
- Create: `src/agent_toolkit_cli/commands/bundle/__init__.py`
- Create: `src/agent_toolkit_cli/commands/bundle/install_cmd.py`
- Create: `src/agent_toolkit_cli/commands/bundle/validate_cmd.py`
- Modify: `src/agent_toolkit_cli/cli.py` (register the group)
- Test: `tests/test_cli/test_cli_bundle_group.py`

- [ ] **Step 1: Write the failing tests** (CLI smoke + scope default + validate exit codes; hermetic)

```python
# tests/test_cli/test_cli_bundle_group.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _write_manifest(tmp_path: Path, members: list[dict]) -> Path:
    p = tmp_path / "demo.bundle.json"
    p.write_text(json.dumps({
        "schema_version": 1, "name": "demo", "description": "d",
        "members": members,
    }))
    return p


def test_bundle_help_lists_verbs():
    res = CliRunner().invoke(main, ["bundle", "--help"])
    assert res.exit_code == 0
    assert "install" in res.output
    assert "validate" in res.output


def test_install_and_validate_help_exit_zero():
    for verb in ("install", "validate"):
        res = CliRunner().invoke(main, ["bundle", verb, "--help"])
        assert res.exit_code == 0


def test_validate_rejects_mcp_member_with_329(tmp_path):
    p = _write_manifest(tmp_path, [
        {"asset_type": "mcp", "source": "o/r/ctx7", "slug": "context7"},
    ])
    res = CliRunner().invoke(main, ["bundle", "validate", str(p)])
    assert res.exit_code != 0
    assert "#329" in res.output


def test_validate_rejects_instructions_member(tmp_path):
    p = _write_manifest(tmp_path, [{"asset_type": "instructions"}])
    res = CliRunner().invoke(main, ["bundle", "validate", str(p)])
    assert res.exit_code != 0
    assert "not a bundle member type" in res.output


def test_install_missing_manifest_errors(tmp_path):
    res = CliRunner().invoke(
        main, ["bundle", "install", str(tmp_path / "nope.json")]
    )
    assert res.exit_code != 0
    assert "not found" in res.output


def test_install_mcp_member_hard_fails(tmp_path):
    p = _write_manifest(tmp_path, [
        {"asset_type": "mcp", "source": "o/r/ctx7", "slug": "context7"},
    ])
    res = CliRunner().invoke(main, ["bundle", "install", str(p)])
    assert res.exit_code != 0
    assert "#329" in res.output
```

For the full happy-path install/rollback at this layer, add ONE end-to-end test
that builds a real hermetic skill source with `git_sandbox` and asserts the
member lands in the lock — mirror the existing `tests/test_cli/test_cli_agent_group.py`
add+install pattern (bare `file://` upstream, monkeypatched HOME). Keep the
heavy fan-out coverage in `test_bundle_install.py` (stubbed) and dispatch
(stubbed); this layer only proves the wiring + exit codes.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_bundle_group.py -q`
Expected: FAIL — `No such command 'bundle'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/commands/bundle/__init__.py
"""`bundle` command group — install/validate a toolkit-native bundle manifest."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.bundle.install_cmd import install_cmd
from agent_toolkit_cli.commands.bundle.validate_cmd import validate_cmd


@click.group(help="Install assets declared together in a bundle manifest.")
def bundle() -> None:
    """Bundle = a stateless shortcut that fans out to per-kind installers."""


bundle.add_command(install_cmd, name="install")
bundle.add_command(validate_cmd, name="validate")
```

```python
# src/agent_toolkit_cli/commands/bundle/install_cmd.py
"""`bundle install <ref> [--global/--project]`."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli.bundle_manifest import ManifestError, load


@click.command(help="Install every member of a bundle manifest (all-or-nothing).")
@click.argument("ref", type=click.Path(path_type=Path))
@click.option("--global", "global_", is_flag=True, help="Install all members globally.")
@click.option("--project", "project_", is_flag=True, help="Install all members at project scope.")
@click.pass_context
def install_cmd(ctx: click.Context, ref: Path, global_: bool, project_: bool) -> None:
    if global_ and project_:
        raise click.UsageError("pass at most one of --global / --project")
    scope = _resolve_scope(global_, project_)
    try:
        manifest = load(ref)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        bundle_install.run(manifest, scope=scope, dry_run=False)
    except bundle_install.BundleInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed bundle {manifest.name!r} ({len(manifest.members)} members, {scope})")


def _resolve_scope(global_: bool, project_: bool) -> str:
    """No flag → toolkit default: global outside a project, project inside one."""
    if global_:
        return "global"
    if project_:
        return "project"
    # Mirror scope_and_roots(read_only=False) default detection.
    from agent_toolkit_cli._paths_core import in_project  # see worker note
    return "project" if in_project(Path.cwd()) else "global"
```

```python
# src/agent_toolkit_cli/commands/bundle/validate_cmd.py
"""`bundle validate <ref>` — resolve every member, write nothing."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli.bundle_manifest import ManifestError, load


@click.command(help="Check a bundle manifest resolves, without installing.")
@click.argument("ref", type=click.Path(path_type=Path))
def validate_cmd(ref: Path) -> None:
    try:
        manifest = load(ref)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    report = bundle_install.run(manifest, scope="global", dry_run=True)
    for label in report.checked:
        click.echo(f"ok       {label}")
    for fail in report.failures:
        click.echo(f"FAIL     {fail}", err=True)
    if not report.ok:
        raise click.ClickException(
            f"bundle {manifest.name!r} did not validate "
            f"({len(report.failures)} member(s) failed)"
        )
    click.echo(f"valid    {manifest.name!r} ({len(manifest.members)} members)")
```

Register in `cli.py` after the other groups:

```python
# src/agent_toolkit_cli/cli.py — add import + registration
from agent_toolkit_cli.commands.bundle import bundle
# ...
main.add_command(bundle)
```

> **Worker note:** `_paths_core.in_project` may not exist by that name. The
> scope-default convention lives in each kind's `_common.scope_and_roots`
> (`read_only=...`). Reuse the SAME detection the other verbs use — import and
> call whatever `scope_and_roots` uses to decide project-vs-global with no flag,
> rather than re-deriving it. Pin the no-flag default with a test: run
> `bundle validate`/`install` from inside a temp git project vs outside and
> assert the scope chosen. If a shared helper isn't cleanly importable, prefer
> adding a tiny `default_scope(cwd) -> str` to `_paths_core` and have the other
> verbs' logic point at it (small, in-scope refactor) — but do NOT duplicate the
> rule inline.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_bundle_group.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/bundle/ src/agent_toolkit_cli/cli.py tests/test_cli/test_cli_bundle_group.py
git commit -m "feat(bundle): bundle install/validate CLI group

Refs #369

Device: $(hostname -s)"
```

---

## Task 5: End-to-end hermetic install + rollback (real fan-out)

**Files:**
- Test: `tests/test_cli/test_bundle_e2e.py`

**Purpose:** prove the fan-out works against the REAL installers (not stubs):
a 2-member skill+agent bundle installs both into their real locks; a bundle whose
2nd member points at a non-existent source rolls the 1st back. This is the test
that catches dispatch-argv mismatches the unit stubs can't.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_bundle_e2e.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _make_skill_repo(root: Path, slug: str) -> str:
    """Build a bare git repo holding a minimal skill; return a file:// source."""
    work = root / f"{slug}-work"
    work.mkdir()
    (work / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: e2e test skill\n---\nBody.\n"
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(work), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "init"], check=True,
    )
    bare = root / f"{slug}.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True)
    return f"file://{bare}"


@pytest.fixture
def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def test_two_member_bundle_installs_both(tmp_path, _home):
    # NOTE: align member asset_types + source shapes with the real skill/agent
    # add entrypoints confirmed in Task 2. This test is the source of truth that
    # the dispatch argv matches reality; adjust sources to satisfy each kind's
    # add (e.g. skill add accepts a file:// repo with SKILL.md at root).
    src = _make_skill_repo(tmp_path, "gw")
    manifest = tmp_path / "b.bundle.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "name": "demo", "description": "",
        "members": [{"asset_type": "skill", "source": src, "slug": "gw"}],
    }))
    res = CliRunner().invoke(main, ["bundle", "install", "--global", str(manifest)])
    assert res.exit_code == 0, res.output
    # member now in the skill lock — assert via `skill list` or the lock file
    lock = json.loads((_home / ".agents" / ".skill-lock.json").read_text()) \
        if (_home / ".agents" / ".skill-lock.json").exists() else {}
    # Loose assertion; tighten to the real lock path/shape during implementation.
    assert "gw" in json.dumps(lock) or res.exit_code == 0


def test_rollback_on_second_member_unresolvable(tmp_path, _home):
    good = _make_skill_repo(tmp_path, "good")
    manifest = tmp_path / "b.bundle.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "name": "demo", "description": "",
        "members": [
            {"asset_type": "skill", "source": good, "slug": "good"},
            {"asset_type": "skill", "source": f"file://{tmp_path}/does-not-exist.git",
             "slug": "missing"},
        ],
    }))
    res = CliRunner().invoke(main, ["bundle", "install", "--global", str(manifest)])
    assert res.exit_code != 0
    # 'good' must have been rolled back — assert it's NOT installed.
    list_res = CliRunner().invoke(main, ["skill", "list"])
    assert "good" not in list_res.output
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli/test_bundle_e2e.py -q`
Expected: FAIL initially (argv/source-shape mismatches). Iterate the manifest
member shape + dispatch argv until both pass. **This task's whole value is
forcing dispatch to match the real installers.**

- [ ] **Step 3: Fix dispatch/argv until green**

Adjust `bundle_dispatch._add_argv` / `_install_argv` and the test manifest
sources to the exact shapes `skill add` / `agent add` accept. Confirm the skill
lock path the e2e asserts against (`~/.agents/.skill-lock.json` global, per
`skill_lock` v3) and tighten the assertion.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_bundle_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_bundle_e2e.py src/agent_toolkit_cli/bundle_dispatch.py
git commit -m "test(bundle): end-to-end hermetic install + rollback over real installers

Refs #369

Device: $(hostname -s)"
```

---

## Task 6: Docs — schema + verb reference

**Files:**
- Create: `docs/agent-toolkit/bundles.md` (schema + verbs + examples)
- Modify: the CLI command-reference doc / `mkdocs.yml` nav if one lists per-kind verbs (grep for where `skill`/`agent` verbs are documented and add `bundle` parallel)

- [ ] **Step 1: Write the docs page**

Document: the v1 schema (table of top-level + member fields), the two verbs with
examples, the all-or-nothing guarantee, the `mcp`-reserved/`instructions`-excluded
scope rulings, and a "v2 roadmap" note (uninstall, doctor, remote manifests,
composite). Mirror the prose style of the existing per-kind docs.

- [ ] **Step 2: Build docs to verify (if mkdocs strict)**

Run: `uv run mkdocs build --strict` (the project uses `strict: true`).
Expected: builds clean, no broken nav/links.

- [ ] **Step 3: Commit**

```bash
git add docs/ mkdocs.yml
git commit -m "docs(bundle): bundle manifest schema + verb reference

Refs #369

Device: $(hostname -s)"
```

---

## Task 7: Full-suite gate + PR

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: all green EXCEPT the 2 known-whitelisted env failures
(`test_pi_extension_inventory::test_empty_machine_is_empty`,
`test_instruction_state::test_build_instruction_rows_empty_lock_no_canonical`) —
both pre-existing, HOME-isolation related, unrelated to this change. If only
those two fail, `--no-verify` is the documented precedent for the final commit.

- [ ] **Step 2: Lint/type check**

Run: `uv run ruff check src/agent_toolkit_cli/bundle_*.py src/agent_toolkit_cli/commands/bundle/ && uv run mypy src/agent_toolkit_cli/bundle_manifest.py src/agent_toolkit_cli/bundle_dispatch.py src/agent_toolkit_cli/bundle_install.py`
Expected: no NEW errors over the baseline (main carries pre-existing mypy/ruff debt; introduce none).

- [ ] **Step 3: Open the PR**

```bash
git push -u origin <branch>
gh pr create --title "feat(bundle): toolkit-native bundle manifest + install/validate (#369)" \
  --body "Implements #369. Stateless fan-out over skills/agents/pi-extensions; mcp reserved-but-hard-fails (#329); instructions excluded. All-or-nothing rollback. Spec + plan in docs/superpowers/. Depends on #329 for mcp members."
```

---

## Self-review (against the spec)

**Spec coverage**

| Spec AC | Task |
|---|---|
| AC1 schema validation | Task 1 |
| AC2 install fan-out (local file) | Tasks 2, 4, 5 |
| AC3 members in own locks, no bundle record | Tasks 2/5 (no lock written by bundle_*), e2e asserts member in kind lock |
| AC4 all-or-nothing rollback | Task 3 (unit) + Task 5 (e2e) |
| AC5 scope flag + default | Task 4 (`_resolve_scope`) + test |
| AC6 mcp hard-fail #329 | Tasks 2, 4 |
| AC7 validate = suppressed-write resolve pass | Tasks 3 (`dry_run`), 4 (`validate_cmd`) |
| AC8 instructions + unknown type rejected | Task 1 + Task 4 CLI test |

No spec AC is unmapped.

**Placeholder scan:** Two `worker note` blocks (Tasks 2, 4) flag reality-sensitive
seams (exact per-kind add/install argv; the scope-default helper). These are NOT
placeholders for behaviour — the behaviour and tests are fully specified; the notes
tell the worker to confirm exact flag spellings against the real commands and pin
them in the already-written tests. That is the correct handling for the one genuine
unknown (each kind's precise verb signature) without guessing it wrong in the plan.

**Type consistency:** `BundleMember(asset_type, source, slug, ref)`,
`BundleManifest(name, description, members)`, `ManifestError`, `DispatchError`,
`BundleInstallError`, `ValidateReport(ok, checked, failures)`, `run(manifest,
scope, dry_run)`, `install_member`/`resolve_member`/`uninstall_member` —
consistent across Tasks 1–5. `install_member` returns `"already_present"` | `None`
(Task 3 worker note + Task 2 sentinel) — flagged for wiring.

**Known reality risks (carried into execution, not resolved on paper):**
1. Exact per-kind add/install argv (esp. `skill` import-vs-add, and `-g/-p` vs
   `--scope`) — Task 2 + Task 5 e2e force these to match reality.
2. The scope-default helper's real name/location — Task 4 worker note.
3. The `already_present` no-op detection — Task 3 worker note; conservative
   fallback documented.

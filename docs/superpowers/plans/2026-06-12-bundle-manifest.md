# Bundle Manifest v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toolkit-native JSON bundle manifest plus `bundle install` / `bundle validate` verbs that fan out to the existing per-kind installers (skills, agents, pi-extensions), all-or-nothing with rollback, stateless.

**Architecture:** Four small units. `bundle_manifest` parses/validates JSON into typed records (pure data; rejects `-`-prefixed fields and a `pi-extension` with `ref`). `bundle_dispatch` maps one member → that kind's real add+install sequence using a **per-kind argv table** (the kinds are heterogeneous: skill uses `--scope`+`--agents`, agent/pi-ext use `-g/-p`, pi-ext has no `--ref`); it invokes the CLI in-process (no shelling out), inserts a `--` end-of-options sentinel before manifest positionals, and lock-prechecks for `already_present`. `bundle_install` orchestrates: a resolve pass shared by both verbs (a `dry_run` flag suppresses disk writes) plus install-in-order with rollback-on-failure (rollback failures warn, never swallow). A thin `bundle` Click group wires the two verbs and resolves the no-flag scope via a new `_paths_core.default_scope`. `mcp` members are reserved-but-hard-fail (#329); `instructions` is not a member type.

**Tech Stack:** Python 3.12, Click, stdlib `json`, pytest with `CliRunner` + the existing `git_sandbox` hermetic `file://` bare-repo fixtures. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-06-12-bundle-manifest-design.md` (revised 2026-06-13 to resolve critical-review findings F1–F10). **Depends on #329** for the `mcp` member to become installable. **#393/#394 (default `skill install --agents standard`) is DONE**, so a skill member installs with no special-casing.

---

## File structure

| File | Responsibility |
|---|---|
| `src/agent_toolkit_cli/bundle_manifest.py` | `BundleMember`, `BundleManifest` dataclasses + `load(path)` / `parse(data)` with validation. Pure; no disk side-effects beyond reading the manifest file. |
| `src/agent_toolkit_cli/bundle_dispatch.py` | `INSTALLABLE_KINDS`, `DispatchError`, `resolve_member(member)`, `install_member(member, scope, project_root)`, `uninstall_member(member, scope, project_root)`. The only unit that knows each kind's per-kind add+install argv. |
| `src/agent_toolkit_cli/_paths_core.py` (modify) | Add `default_scope(cwd) -> str` (F3): project if any per-kind lock file is present in `cwd`, else global. The shared no-flag scope default for `bundle install`/`validate`. |
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


def test_pi_extension_member_with_ref_rejected():
    # F6: `pi-extension add` has no --ref option, so a pi-ext member carrying
    # `ref` is rejected at parse — never silently dropped.
    data = _valid()
    data["members"][2]["ref"] = "v1.2.3"  # the pi-extension member
    with pytest.raises(ManifestError, match="pi-extension does not support ref"):
        parse(data)


@pytest.mark.parametrize("field", ["source", "slug", "ref"])
def test_dash_prefixed_field_rejected(field):
    # F5 option-injection guard: a field value starting with '-' could be read
    # by Click as a flag (e.g. slug="--force"). Reject at parse.
    data = _valid()
    data["members"][0][field] = "--force"
    with pytest.raises(ManifestError, match="must not start with '-'"):
        parse(data)
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

Two parse-time guards (resolved critical-review findings):
- F5: any `source`/`slug`/`ref` value starting with '-' is rejected (an
  option-injection guard — the value is later placed into a CLI argv).
- F6: a `pi-extension` member carrying `ref` is rejected — `pi-extension add`
  has no --ref option, so a pin cannot be honoured and must not be dropped.
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
    # F6: pi-extension `add` has no --ref option — reject a ref here rather than
    # silently dropping the pin.
    if asset_type == "pi-extension" and ref is not None:
        raise ManifestError(
            f"member {index} (pi-extension): pi-extension does not support ref "
            "(its `add` has no --ref option). Remove the 'ref' field."
        )
    # F5 option-injection guard: a manifest-supplied value that begins with '-'
    # could be interpreted by Click as a flag once placed into argv (e.g.
    # slug='--force'). Reject every positional-bound field up front. Dispatch
    # additionally inserts a `--` end-of-options sentinel (defence in depth).
    for field_name, value in (("source", source), ("slug", slug), ("ref", ref)):
        if isinstance(value, str) and value.startswith("-"):
            raise ManifestError(
                f"member {index}: {field_name!r} must not start with '-' "
                f"(got {value!r}) — rejected as a possible option injection"
            )
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

**The seam (decided — F10).** Dispatch builds the same argv a human would type
and invokes the toolkit CLI in-process via `cli.main.main(args=argv,
standalone_mode=False)` (Click's programmatic mode raises on failure instead of
`sys.exit`, so the orchestrator catches it for rollback). This reuses every kind's
real validation, clone, projection, and lock-write with no duplicated installer
logic. The install cores (`skill_install.apply`, `agent_install.apply`,
`pi_extension_install.apply`) are importable, but the **add** halves are
Click-command-bound (`_add_single`/`_add_monorepo` live under the command), so a
pure-function seam would require extracting add cores first — widening v1. The
in-process CLI is the smaller, reuse-maximising v1 choice.

**The argv is per-kind, not uniform.** The kinds diverge (verified against the
code, post-#394):

| kind | add argv | install argv |
|---|---|---|
| `skill` | `skill add <source> [--slug …] [--ref …]` | `skill install <slug> --scope <global\|project>` (NOT `-g/-p`; `--agents` defaults to `standard` since #393/#394, so it is omitted) |
| `agent` | `agent add <source> [--slug …] [--ref …]` | `agent install <slug> <-g\|-p>` |
| `pi-extension` | `pi-extension add <source> [--slug …]` (**no `--ref`**) | `pi-extension install <slug> <-g\|-p>` |

So dispatch has a **per-kind argv builder**, not one uniform `_install_argv`. Each
builder puts all `--flag value` options FIRST, then the `--` end-of-options
sentinel (F5 defence-in-depth), then exactly one manifest-derived positional LAST
— because `--` makes everything after it positional, an option placed after the
sentinel (e.g. `["skill","install","--","gw","--scope","project"]`) is rejected by
Click as an unexpected extra argument; the correct form is
`["skill","install","--scope","project","--","gw"]`. When project scope is active
dispatch prepends `--project <root>` to the child argv (F8). `install_member` also
lock-prechecks the slug BEFORE add and returns `"already_present"` when it is
already in the library (F2). The tests below pin all of this.

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


def _stub_not_present(monkeypatch):
    """Lock-precheck always says 'not present' so install proceeds (F2)."""
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._lock_has_member",
        lambda member: False,
    )


def test_agent_member_builds_full_argv_with_g_flag(monkeypatch):
    _stub_not_present(monkeypatch)
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
    # agent: add then install -g; full argv asserted (F1). `--` ordering: options
    # FIRST, then `--`, then the single positional LAST.
    assert calls[0] == ["agent", "add", "--slug", "cr", "--ref", "v1",
                        "--", "o/r/agents/cr"]
    assert calls[1] == ["agent", "install", "-g", "--", "cr"]


def test_skill_member_scope_project_threads_scope_not_p(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="skill", source="o/r/gw"),
        scope="project",
    )
    # F1: skill install uses --scope project, NOT -p; --agents is omitted
    # (defaults to standard since #393/#394). Slug derived from source.
    # `--` ordering: --scope option BEFORE `--`, slug positional LAST.
    assert calls[0] == ["skill", "add", "--", "o/r/gw"]
    assert calls[1] == ["skill", "install", "--scope", "project", "--", "gw"]
    assert "-p" not in calls[1]
    assert "--agents" not in calls[1]


def test_pi_extension_member_omits_ref_and_uses_g_flag(monkeypatch):
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="pi-extension", source="o/r/tm", slug="tm"),
        scope="global",
    )
    # F6: pi-extension add NEVER emits --ref (the option does not exist).
    # `--` ordering: --slug option BEFORE `--`, source/slug positional LAST.
    assert calls[0] == ["pi-extension", "add", "--slug", "tm", "--", "o/r/tm"]
    assert "--ref" not in calls[0]
    assert calls[1] == ["pi-extension", "install", "-g", "--", "tm"]


def test_end_of_options_sentinel_precedes_positionals(monkeypatch):
    # F5: a `--` sentinel sits before every manifest-derived positional so a
    # crafted value can never be parsed as a flag. (Dash-prefixed values are
    # already rejected at parse — this is defence in depth.)
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(BundleMember(asset_type="skill", source="o/r/gw"),
                   scope="global")
    # `--` is the second-to-last element and the manifest positional is LAST, so
    # no option ever follows the sentinel (which would be parsed as positional).
    assert calls[0][-2:] == ["--", "o/r/gw"]
    assert calls[1][-2:] == ["--", "gw"]


def test_project_scope_prepends_project_root(monkeypatch):
    # F8: when project scope is active and a project_root is supplied, each child
    # argv is prefixed with `--project <root>` (the top-level flag is NOT
    # inherited across independent in-process main() calls).
    _stub_not_present(monkeypatch)
    calls = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: calls.append(argv),
    )
    install_member(
        BundleMember(asset_type="agent", source="o/r/agents/cr", slug="cr"),
        scope="project",
        project_root="/tmp/proj",
    )
    assert calls[0][:2] == ["--project", "/tmp/proj"]
    assert calls[1][:2] == ["--project", "/tmp/proj"]


def test_already_present_skips_add_and_returns_sentinel(monkeypatch):
    # F2: install_member reads the kind's library lock BEFORE add. If the slug
    # is already present with the same source, it returns "already_present" and
    # never invokes the CLI.
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._lock_has_member",
        lambda member: True,
    )
    called = []
    monkeypatch.setattr(
        "agent_toolkit_cli.bundle_dispatch._invoke_cli",
        lambda argv: called.append(argv),
    )
    outcome = install_member(
        BundleMember(asset_type="skill", source="o/r/gw", slug="gw"),
        scope="global",
    )
    assert outcome == "already_present"
    assert called == []  # add+install skipped entirely


def test_lock_has_member_reads_real_lock_shape(tmp_path, monkeypatch):
    # Pin the on-disk lock key shape: _lock_has_member must return True for a slug
    # genuinely present in a REAL written library lock (NOT monkeypatched). Guards
    # against the `entries` vs `skills` key-shape bug.
    from agent_toolkit_cli import bundle_dispatch
    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock

    lock_path = tmp_path / "skills-lock.json"
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "gw",
        LockEntry(source="o/r/gw", source_type="github", skill_path="SKILL.md"),
    ))
    monkeypatch.setattr(
        "agent_toolkit_cli._paths_core.library_lock_path_for_asset_type",
        lambda binding: lock_path,
    )
    assert bundle_dispatch._lock_has_member(
        BundleMember(asset_type="skill", source="o/r/gw", slug="gw")
    ) is True
    # Different source for the same slug → NOT our member.
    assert bundle_dispatch._lock_has_member(
        BundleMember(asset_type="skill", source="o/r/OTHER", slug="gw")
    ) is False


def test_dispatch_propagates_install_failure(monkeypatch):
    _stub_not_present(monkeypatch)

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

The kinds are heterogeneous (skill uses `--scope`+`--agents`; agent/pi-extension
use `-g/-p`; pi-extension's `add` has no `--ref`). Rather than duplicate any
installer logic, dispatch builds the same argv a human would type, per kind, and
invokes the CLI in-process via Click's programmatic mode (`standalone_mode=False`),
reusing every kind's validation, clone, projection, and lock-write. `mcp` is
reserved but hard-fails until the mcp kind ships (#329).

Three hardening rules (resolved critical-review findings):
- F2 `already_present`: install_member reads the kind's library lock for the slug
  BEFORE add. If present with the same source, it returns "already_present" and
  skips add+install (so the orchestrator excludes it from the rollback set).
- F5 sentinel: a `--` end-of-options marker precedes every manifest-derived
  positional, so a crafted value can never be parsed by Click as a flag.
- F8 `--project`: each independent in-process main() call is a fresh Click parse
  with no inherited top-level flag, so when project scope is active dispatch
  prepends `["--project", str(project_root)]` to the child argv.
"""
from __future__ import annotations

from pathlib import Path

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


def _project_prefix(scope: str, project_root: str | None) -> list[str]:
    """F8: prepend the top-level --project when installing at project scope.

    Each in-process main() call is an independent Click parse; the top-level
    --project is not inherited, so it must ride on every child argv.
    """
    if scope == "project" and project_root:
        return ["--project", str(project_root)]
    return []


def _check_member(member: BundleMember) -> None:
    if member.asset_type == "mcp":
        raise DispatchError(_MCP_NOT_READY.format(slug=member.slug or member.source))
    if member.asset_type not in INSTALLABLE_KINDS:
        raise DispatchError(f"un-installable member type {member.asset_type!r}")


def _derive_slug(source: str) -> str:
    """Last path segment, mirroring each kind's default slug derivation."""
    return source.rstrip("/").split("/")[-1]


def resolve_member(member: BundleMember) -> None:
    """Dry-run check: a member that cannot possibly install fails here.

    v1 resolution is structural (type is installable, mcp rejected). Source/ref
    reachability is proven by the real add during install; validate does NOT
    probe the network (AC7). Kept minimal by design.
    """
    _check_member(member)


# ── per-kind argv builders (F1) ────────────────────────────────────────────
# A single uniform builder is WRONG: skill install takes `--scope <s>` (and
# `--agents` defaults to standard since #393/#394), while agent/pi-extension
# take `-g/-p`, and pi-extension's `add` has no `--ref`. Each kind owns its argv.

def _scope_flag(scope: str) -> str:
    return "-g" if scope == "global" else "-p"


# `--` ORDERING (verified against the real Click CLI): the `--` end-of-options
# sentinel makes EVERYTHING after it positional, so options must come BEFORE it
# and the single manifest-derived positional must be LAST. E.g.
# `["skill","install","--","gw","--scope","project"]` FAILS ("unexpected extra
# arguments --scope project"); the correct form is
# `["skill","install","--scope","project","--","gw"]`. Every builder below puts
# `--flag value` options first, then `--`, then exactly one positional.

def _skill_add_argv(member: BundleMember) -> list[str]:
    argv = ["skill", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    if member.ref:
        argv += ["--ref", member.ref]
    return [*argv, "--", member.source]


def _skill_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    # `--agents` is omitted: it defaults to `standard` (#393/#394). skill uses
    # `--scope global|project`, NOT `-g/-p`. Options BEFORE `--`, slug LAST.
    return ["skill", "install", "--scope", scope, "--", slug]


def _agent_add_argv(member: BundleMember) -> list[str]:
    argv = ["agent", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    if member.ref:
        argv += ["--ref", member.ref]
    return [*argv, "--", member.source]


def _agent_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return ["agent", "install", _scope_flag(scope), "--", slug]


def _pi_ext_add_argv(member: BundleMember) -> list[str]:
    # F6: pi-extension add has NO --ref. (A pi-ext member carrying ref is already
    # rejected at parse; we never emit --ref here regardless.)
    argv = ["pi-extension", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    return [*argv, "--", member.source]


def _pi_ext_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return ["pi-extension", "install", _scope_flag(scope), "--", slug]


_ADD_BUILDERS = {
    "skill": _skill_add_argv,
    "agent": _agent_add_argv,
    "pi-extension": _pi_ext_add_argv,
}
_INSTALL_BUILDERS = {
    "skill": _skill_install_argv,
    "agent": _agent_install_argv,
    "pi-extension": _pi_ext_install_argv,
}
_UNINSTALL_KIND_FLAG = {  # skill uninstall also uses --scope; others -g/-p
    "skill": lambda slug, scope: ["skill", "uninstall", "--scope", scope,
                                  "--", slug],
    "agent": lambda slug, scope: ["agent", "uninstall", _scope_flag(scope),
                                  "--", slug],
    "pi-extension": lambda slug, scope: ["pi-extension", "uninstall",
                                         _scope_flag(scope), "--", slug],
}


def _lock_has_member(member: BundleMember) -> bool:
    """F2: is this slug already in the kind's GLOBAL library lock at the same
    source? The library (add) lock is scope-independent — add clones once into
    `~/.agent-toolkit/<kind>/` regardless of projection scope — so a present
    slug means a prior install we must not roll back.

    Reads the per-kind library lock via that kind's lock reader + path helper.
    Returns False on any read error (treat as 'not present' → proceed to add,
    which is itself idempotent).
    """
    from agent_toolkit_cli import _paths_core
    # All three kinds serialize their library lock via the SAME primitives
    # (agent_lock and pi_extension_lock re-export skill_lock.read_lock/write_lock),
    # so the typed reader handles every kind. Using the typed reader — NOT raw
    # json — means the on-disk key shape (`{"version":…, "skills": {slug: entry}}`)
    # and the LockEntry field names (`source`) come from one place and cannot drift.
    from agent_toolkit_cli.skill_lock import read_lock

    binding = {
        "skill": _paths_core.SKILL_BINDING,
        "agent": _paths_core.AGENT_BINDING,
        "pi-extension": _paths_core.PI_EXTENSION_BINDING,
    }[member.asset_type]
    lock_path = _paths_core.library_lock_path_for_asset_type(binding)
    slug = member.slug or _derive_slug(member.source)
    try:
        lock = read_lock(lock_path)  # returns an empty LockFile if absent
    except (OSError, ValueError):
        # Corrupt lock → treat as 'not present' and proceed to add (idempotent).
        # NOTE: this is a fallback, not a guarantee — a corrupt lock silently
        # disables already_present detection rather than failing loud.
        return False
    entry = lock.skills.get(slug)
    if entry is None:
        return False
    # Same slug AND same source = a prior install of THIS member.
    return entry.source == member.source


def install_member(
    member: BundleMember,
    scope: str,
    project_root: str | None = None,
) -> str | None:
    """Add the member to the library, then project it at `scope`.

    Returns "already_present" if the lock-precheck (F2) finds the slug already in
    the library at the same source (add+install skipped); otherwise returns None
    after a real add+install. project_root threads the top-level --project (F8).
    """
    _check_member(member)
    if _lock_has_member(member):
        return "already_present"
    prefix = _project_prefix(scope, project_root)
    try:
        _invoke_cli(prefix + _ADD_BUILDERS[member.asset_type](member))
        _invoke_cli(prefix + _INSTALL_BUILDERS[member.asset_type](member, scope))
    except DispatchError:
        raise
    except Exception as exc:  # ClickException, Abort, GitError, …
        raise DispatchError(
            f"member {member.slug or member.source!r} ({member.asset_type}) "
            f"failed to install: {exc}"
        ) from exc
    return None


def uninstall_member(
    member: BundleMember,
    scope: str,
    project_root: str | None = None,
) -> None:
    """Roll back a member installed earlier this run (in-process)."""
    _check_member(member)
    slug = member.slug or _derive_slug(member.source)
    prefix = _project_prefix(scope, project_root)
    try:
        _invoke_cli(prefix + _UNINSTALL_KIND_FLAG[member.asset_type](slug, scope))
    except Exception as exc:
        raise DispatchError(
            f"rollback of {slug!r} ({member.asset_type}) failed: {exc}"
        ) from exc
```

> **Worker note (verify-then-pin, not redesign):** the argv shapes above are the
> verified post-#394 reality — pin them in the dispatch tests so any future drift
> fails loudly. `_lock_has_member` uses the **typed** `skill_lock.read_lock` (which
> all three kinds re-export) and reads `lock.skills[slug].source` — so the on-disk
> `{"version":…, "skills": {…}}` shape and the `source` field name come from one
> typed source and cannot drift. Step 1's `test_already_present_skips_add_*` test
> uses a REAL written lock (not a monkeypatched `_lock_has_member`) so the key shape
> is genuinely pinned. Do NOT change the argv builders or the seam; those are decided.

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
                        lambda m, scope, project_root=None: installed.append(m.source))
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: pytest.fail("must not roll back"))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)
    run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
        scope="global", dry_run=False)
    assert installed == ["a", "b", "c"]


def test_failure_midrun_rolls_back_prior_members_newest_first(monkeypatch):
    installed, rolled_back = [], []

    def fake_install(m, scope, project_root=None):
        if m.source == "c":
            raise DispatchError("boom on c")
        installed.append(m.source)

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="boom on c"):
        run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
            scope="global", dry_run=False)
    assert installed == ["a", "b"]
    assert rolled_back == ["b", "a"]  # newest-first


def test_already_present_member_not_rolled_back(monkeypatch):
    # 'a' is reported already_present by the dispatch lock-precheck (F2) → it is
    # excluded from the rollback set when a later member fails.
    rolled_back = []

    def fake_install(m, scope, project_root=None):
        if m.source == "a":
            return "already_present"   # lock-precheck: pre-existing, not ours
        if m.source == "b":
            raise DispatchError("boom on b")

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member",
                        lambda m, scope, project_root=None: rolled_back.append(m.source))
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError):
        run(_manifest(("skill", "a"), ("agent", "b")), scope="global",
            dry_run=False)
    assert rolled_back == []  # 'a' was already present → not our install → no rollback


def test_rollback_failure_is_warned_not_swallowed(monkeypatch, capsys):
    # F9: a rollback uninstall that itself raises must NOT be silently swallowed —
    # emit a warning naming the member and still propagate the original error.
    def fake_install(m, scope, project_root=None):
        if m.source == "c":
            raise DispatchError("boom on c")
        return None

    def failing_uninstall(m, scope, project_root=None):
        raise DispatchError(f"uninstall of {m.source} blew up")

    monkeypatch.setattr(bundle_install, "install_member", fake_install)
    monkeypatch.setattr(bundle_install, "uninstall_member", failing_uninstall)
    monkeypatch.setattr(bundle_install, "resolve_member", lambda m: None)

    with pytest.raises(BundleInstallError, match="boom on c"):
        run(_manifest(("skill", "a"), ("agent", "b"), ("pi-extension", "c")),
            scope="global", dry_run=False)
    err = capsys.readouterr().err
    # both prior members failed to roll back → both warned, original error stands
    assert "warning: rollback" in err
    assert "skill:a" in err and "agent:b" in err


def test_dry_run_resolves_but_installs_nothing(monkeypatch):
    resolved, installed = [], []
    monkeypatch.setattr(bundle_install, "resolve_member",
                        lambda m: resolved.append(m.source))
    monkeypatch.setattr(bundle_install, "install_member",
                        lambda m, scope, project_root=None: installed.append(m.source))
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

import click

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


def run(
    manifest: BundleManifest,
    scope: str,
    dry_run: bool,
    project_root: str | None = None,
) -> ValidateReport:
    """Resolve every member; if not dry_run, install in order with rollback.

    `project_root` (F8) is threaded to dispatch so project-scope child argv carry
    `--project <root>`.
    """
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
            outcome = install_member(member, scope=scope, project_root=project_root)
        except DispatchError as exc:
            failed_rollbacks = _rollback(installed, scope, project_root)
            msg = str(exc)
            if failed_rollbacks:
                msg += (
                    "\n  NOTE: rollback failed for "
                    f"{', '.join(failed_rollbacks)} — manual cleanup may be needed."
                )
            raise BundleInstallError(msg) from exc
        # Only track members WE installed (not pre-existing no-ops) for rollback.
        if outcome != "already_present":
            installed.append(member)

    return report


def _rollback(
    installed: list[BundleMember], scope: str, project_root: str | None
) -> list[str]:
    """Roll back this run's installs, newest-first. F9: a rollback failure is
    WARNED (never swallowed) and the failed labels are collected and returned so
    the caller can name them in the propagated BundleInstallError.
    """
    failed: list[str] = []
    for prior in reversed(installed):
        label = _label(prior)
        try:
            uninstall_member(prior, scope=scope, project_root=project_root)
        except DispatchError as exc:
            click.echo(f"warning: rollback of {label} failed: {exc}", err=True)
            failed.append(label)
    return failed
```

> **Worker note:** `install_member` returns `"already_present"` (lock-precheck,
> F2) or `None`; the orchestrator keys the rollback set on that. This is fully
> resolved in Task 2 — no conservative fallback, no AC4 tension. The rollback
> loop never swallows a failed uninstall (F9): it warns on stderr and still
> raises the original `BundleInstallError`. Pin both with the Task 3 tests above.

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
- Modify: `src/agent_toolkit_cli/_paths_core.py` (add `default_scope`, F3)
- Create: `src/agent_toolkit_cli/commands/bundle/__init__.py`
- Create: `src/agent_toolkit_cli/commands/bundle/install_cmd.py`
- Create: `src/agent_toolkit_cli/commands/bundle/validate_cmd.py`
- Modify: `src/agent_toolkit_cli/cli.py` (register the group)
- Test: `tests/test_cli/test_paths_core_default_scope.py`
- Test: `tests/test_cli/test_cli_bundle_group.py`

- [ ] **Step 0 (F3): add `default_scope` to `_paths_core` — RED then GREEN**

`_paths_core` has **no** `in_project` and **no** `default_scope` today (verified
against main). The existing per-kind `scope_and_roots` keys project-vs-global on a
per-kind lock filename; there is no binding-neutral "in a project" helper. Add one
small, documented function — it is the single source of the no-flag scope default,
reused by both bundle verbs. Each `AssetTypeBinding` already carries its
`lock_filename` (`skills-lock.json` / `agents-lock.json` / `pi-extensions-lock.json`),
so `default_scope` checks for any of those in `cwd`.

Write the failing test first:

```python
# tests/test_cli/test_paths_core_default_scope.py
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli._paths_core import default_scope


def test_default_scope_project_when_a_lock_present(tmp_path: Path):
    (tmp_path / "skills-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"


def test_default_scope_project_for_any_kind_lock(tmp_path: Path):
    (tmp_path / "agents-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"
    (tmp_path / "pi-extensions-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"


def test_default_scope_global_when_no_lock(tmp_path: Path):
    assert default_scope(tmp_path) == "global"
```

Then the implementation:

```python
# src/agent_toolkit_cli/_paths_core.py — add near the other path helpers

# The per-kind project-lock filenames that mark a directory as "a project".
# Sourced from the bindings so it stays in step if a kind's lock filename changes.
_PROJECT_LOCK_FILENAMES: tuple[str, ...] = (
    SKILL_BINDING.lock_filename,
    AGENT_BINDING.lock_filename,
    PI_EXTENSION_BINDING.lock_filename,
)


def default_scope(cwd: Path) -> str:
    """Toolkit no-flag scope default (F3): 'project' if `cwd` holds any per-kind
    project lock (skills-/agents-/pi-extensions-lock.json), else 'global'.

    This is the binding-neutral analogue of the per-kind `scope_and_roots`
    detection; the per-kind verbs key on their own lock filename, while a bundle
    spans kinds and so checks for any of them. instructions-lock.json is NOT
    counted — instructions is not a bundle member type.
    """
    for filename in _PROJECT_LOCK_FILENAMES:
        if (cwd / filename).is_file():
            return "project"
    return "global"
```

Run: `uv run pytest tests/test_cli/test_paths_core_default_scope.py -q` (RED →
add `default_scope` → GREEN). This step can ride the Task 4 commit or be its own.

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


def test_install_threads_project_root_to_run(tmp_path, monkeypatch):
    # F8: --project resolves a project_root and threads it into bundle_install.run.
    import agent_toolkit_cli.commands.bundle.install_cmd as install_cmd_mod

    captured = {}

    def fake_run(manifest, scope, dry_run, project_root=None):
        captured["scope"] = scope
        captured["project_root"] = project_root
        from agent_toolkit_cli.bundle_install import ValidateReport
        return ValidateReport(ok=True)

    monkeypatch.setattr(install_cmd_mod.bundle_install, "run", fake_run)
    p = _write_manifest(tmp_path, [{"asset_type": "skill", "source": "o/r/gw"}])
    res = CliRunner().invoke(
        main, ["bundle", "install", "--project", str(p)], catch_exceptions=False
    )
    assert res.exit_code == 0, res.output
    assert captured["scope"] == "project"
    # project_root is the resolved project directory (cwd-derived), not None.
    assert captured["project_root"] is not None


def test_no_flag_scope_uses_default_scope(tmp_path, monkeypatch):
    # AC5/F3: with no flag, scope follows _paths_core.default_scope(cwd).
    import agent_toolkit_cli.commands.bundle.install_cmd as install_cmd_mod

    monkeypatch.setattr(install_cmd_mod, "default_scope", lambda cwd: "global")
    captured = {}

    def fake_run(manifest, scope, dry_run, project_root=None):
        captured["scope"] = scope
        from agent_toolkit_cli.bundle_install import ValidateReport
        return ValidateReport(ok=True)

    monkeypatch.setattr(install_cmd_mod.bundle_install, "run", fake_run)
    p = _write_manifest(tmp_path, [{"asset_type": "skill", "source": "o/r/gw"}])
    res = CliRunner().invoke(main, ["bundle", "install", str(p)],
                            catch_exceptions=False)
    assert res.exit_code == 0, res.output
    assert captured["scope"] == "global"
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
from agent_toolkit_cli._paths_core import default_scope  # F3 shared helper
from agent_toolkit_cli.bundle_manifest import ManifestError, load


@click.command(help="Install every member of a bundle manifest (all-or-nothing).")
@click.argument("ref", type=click.Path(path_type=Path))
@click.option("--global", "global_", is_flag=True, help="Install all members globally.")
@click.option("--project", "project_", is_flag=True, help="Install all members at project scope.")
def install_cmd(ref: Path, global_: bool, project_: bool) -> None:
    if global_ and project_:
        raise click.UsageError("pass at most one of --global / --project")
    scope = _resolve_scope(global_, project_)
    # F8: at project scope, resolve the project root so dispatch can prepend
    # `--project <root>` to each child argv (the top-level flag is not inherited
    # across independent in-process main() calls). Mirrors scope_and_roots'
    # `ctx_project or Path.cwd()` convention.
    project_root = str(Path.cwd()) if scope == "project" else None
    try:
        manifest = load(ref)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        bundle_install.run(
            manifest, scope=scope, dry_run=False, project_root=project_root
        )
    except bundle_install.BundleInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed bundle {manifest.name!r} ({len(manifest.members)} members, {scope})")


def _resolve_scope(global_: bool, project_: bool) -> str:
    """No flag → toolkit default via the shared `default_scope` helper (F3):
    project inside a project (a per-kind lock present in cwd), else global."""
    if global_:
        return "global"
    if project_:
        return "project"
    return default_scope(Path.cwd())
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

> **Worker note:** the no-flag scope default is the new `_paths_core.default_scope`
> from Step 0 (F3) — `in_project` does NOT exist and must not be imported. The
> bundle command imports `default_scope` directly (so the Task 4 test can
> monkeypatch it on the module). `default_scope` is binding-neutral on purpose: a
> bundle spans kinds, so it treats ANY per-kind lock in cwd as "in a project",
> whereas each per-kind `scope_and_roots` keys only on its own lock. Pin the
> no-flag default with the Step-0 test and the `test_no_flag_scope_uses_default_scope`
> CLI test above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_paths_core_default_scope.py tests/test_cli/test_cli_bundle_group.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py src/agent_toolkit_cli/commands/bundle/ src/agent_toolkit_cli/cli.py tests/test_cli/test_paths_core_default_scope.py tests/test_cli/test_cli_bundle_group.py
git commit -m "feat(bundle): bundle install/validate CLI group + default_scope helper

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
    # add (e.g. skill add accepts a file:// repo with SKILL.md at root). The real
    # fan-out goes `skill add --slug gw -- <src>` then
    # `skill install --scope global -- gw` (Task 2 argv: options first, then `--`,
    # then the positional last) — the bundle `--global` flag is not forwarded.
    src = _make_skill_repo(tmp_path, "gw")
    manifest = tmp_path / "b.bundle.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "name": "demo", "description": "",
        "members": [{"asset_type": "skill", "source": src, "slug": "gw"}],
    }))
    res = CliRunner().invoke(main, ["bundle", "install", "--global", str(manifest)])
    assert res.exit_code == 0, res.output
    # member now in the GLOBAL skill LIBRARY lock at ~/.agent-toolkit/skills-lock.json
    # (the add lock; projection lands separately). Tighten path/shape to the real
    # skill_lock during implementation.
    lib_lock = _home / ".agent-toolkit" / "skills-lock.json"
    assert lib_lock.exists()
    assert "gw" in lib_lock.read_text()


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

- [ ] **Step 3: Fix the test manifest sources until green (argv is decided)**

The per-kind argv builders are already pinned by the Task 2 unit tests — do NOT
re-shape them here. This task's job is confirming the manifest `source` shapes the
real `skill add` / `agent add` accept (a `file://` bare repo with `SKILL.md` at
root) and tightening the e2e assertion against the real **library** lock path
(`~/.agent-toolkit/skills-lock.json`, NOT the `~/.agents/.skill-lock.json`
projection lock). If a real-installer mismatch surfaces, fix the Task 2 builder +
its unit test together (single source of truth) — never let the e2e and the unit
test disagree.

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

Document: the v1 schema (table of top-level + member fields, including that a
`pi-extension` member must NOT carry `ref` (F6) and that `source`/`slug`/`ref`
cannot start with `-` (F5)), the two verbs with examples, the all-or-nothing
guarantee (with the already-present member excluded from rollback), the scope flag
+ no-flag default, the `mcp`-reserved/`instructions`-excluded rulings, and a "v2
roadmap" note (uninstall, doctor, remote manifests, composite). Mirror the prose
style of the existing per-kind docs.

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
| AC3 members in own locks, no bundle record | Tasks 2/5 (no lock written by bundle_*), e2e asserts member in kind library lock |
| AC4 all-or-nothing rollback (already-present excluded) | Task 3 (unit, incl. F2 lock-precheck + F9 warn-on-rollback-fail) + Task 5 (e2e) |
| AC5 scope flag + default via `default_scope` (F3) | Task 4 Step 0 (`_paths_core.default_scope`) + `_resolve_scope` + tests |
| AC6 mcp hard-fail #329 (resolve pass) | Tasks 2, 4 |
| AC7 validate = suppressed-write resolve pass (structural only, no network probe) | Tasks 3 (`dry_run`), 4 (`validate_cmd`) |
| AC8 instructions + unknown type rejected | Task 1 + Task 4 CLI test |
| AC9 option-injection guard (`-`-prefixed fields rejected at parse; `--` sentinel in argv) | Task 1 (F5 parse guard) + Task 2 (F5 sentinel) |

Plus the cross-AC findings now pinned: F6 (pi-extension `ref` rejected at parse,
Task 1), F8 (`--project` threaded into the fan-out, Tasks 2/4). No spec AC is
unmapped.

**Placeholder scan:** The two remaining `worker note` blocks (Tasks 2, 4) are
*verify-then-pin* notes, not behaviour placeholders. The per-kind argv, the seam,
the `default_scope` helper, and the `already_present` lock-precheck are all decided
and fully written; the notes only ask the worker to confirm two narrow code
realities against the running tree (the library-lock entry field names the F2
precheck reads; the `file://` source shape `skill add` accepts) and keep the
already-written tests as the single source of truth.

**Type consistency:** `BundleMember(asset_type, source, slug, ref)`,
`BundleManifest(name, description, members)`, `ManifestError`, `DispatchError`,
`BundleInstallError`, `ValidateReport(ok, checked, failures)`, `run(manifest,
scope, dry_run, project_root=None)`,
`install_member(member, scope, project_root=None) -> "already_present" | None`,
`resolve_member(member)`, `uninstall_member(member, scope, project_root=None)`,
`_paths_core.default_scope(cwd) -> str` — consistent across Tasks 1–5. The
`already_present` value is produced by the Task 2 lock-precheck (F2) and consumed
by the Task 3 rollback set; no sentinel guess, no fallback.

**Resolved on revision (were "known reality risks", now decided in spec + plan):**
1. **Per-kind add/install argv** — resolved: skill uses `--scope` (+ `--agents`
   defaulting to standard, omitted), agent/pi-ext use `-g/-p`, pi-ext omits
   `--ref`. Per-kind argv builders, full-argv unit tests (F1/F6).
2. **`already_present` detection** — resolved: a library-lock precheck BEFORE add
   (F2), not a return-scrape and not a conservative fallback. AC4 fully satisfied.
3. **Scope-default helper** — resolved: new `_paths_core.default_scope(cwd)` (F3);
   `in_project` never existed and is gone from the plan.
4. **skill `--agents`** — resolved: defaults to `standard` post-#393/#394, so a
   skill member installs with no special-casing.

**Residual execution-time confirmations (narrow, non-blocking):** the library-lock
entry field shape the F2 precheck reads (Task 2 note) and the exact `file://`
source `skill add` accepts in the e2e (Task 5 note). Both pinned by already-written
tests; neither is a design fork.

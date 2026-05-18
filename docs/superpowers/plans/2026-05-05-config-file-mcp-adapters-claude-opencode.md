# Config-file MCP adapters for Claude and OpenCode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `claude` and `opencode` adapter stubs in `src/agent_toolkit_cli/harness_adapters/` with real `ConfigFileAdapter` implementations that mutate `~/.claude.json` and `~/.config/opencode/opencode.json`, register them in the harness-adapter registry, and update the `harness-matrix.md` doc + parity test fixtures.

**Architecture:** Both adapters mirror the existing codex `ConfigFileAdapter` pattern (read → mutate → dump → atomic write via the dispatcher). They differ from codex in (a) JSON instead of TOML — `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)` for deterministic output — and (b) the managed key path inside the document (`mcpServers.<name>` for Claude, `mcp.<name>` for OpenCode). Pre-flight `can_install` is permissive: both Claude and OpenCode handle `stdio`, `sse`, and `http` transports natively, so the only entry-shape variation is in how transport maps to the on-disk record. The `force` flag in `_mcp_dispatch.apply_link` stays in the signature for CLI parity but its `noqa` comment is updated since no current adapter wires it.

**Tech Stack:** Python 3.12+, stdlib `json`, pytest, no new third-party dependencies. Same `ConfigFileAdapter` Protocol from `src/agent_toolkit_cli/harness_adapters/base.py`.

---

## File Structure

**Create:**
- `src/agent_toolkit_cli/harness_adapters/claude.py` — `ClaudeAdapter(ConfigFileAdapter)`. Single file, ~150 lines (matches codex ~220-line ceiling).
- `src/agent_toolkit_cli/harness_adapters/opencode.py` — `OpenCodeAdapter(ConfigFileAdapter)`. Single file, similar size.
- `tests/test_mcp_adapters_claude.py` — round-trip suite mirroring `tests/test_mcp_adapters_codex.py`.
- `tests/test_mcp_adapters_opencode.py` — round-trip suite mirroring same.

**Modify:**
- `src/agent_toolkit_cli/harness_adapters/__init__.py:25-37` — add lazy-imported branches for `claude` and `opencode` next to the existing `codex` branch.
- `src/agent_toolkit_cli/commands/_mcp_dispatch.py:57` — update the `force` flag comment.
- `docs/agent-toolkit/harness-matrix.md` — three localised edits: line-18 `plugin_folder` prose; line-54 mcp row cells for claude/opencode/pi; lines-137-139 "Why some pairs are by design" mcp bullet.
- `tests/test_mcp_dispatch.py:226-240` — switch the UnimplementedAdapter probe from `claude` to `pi`.
- `tests/test_doctor_mcps.py:216-230` — same switch.

The new adapter files keep one responsibility each; the `__init__.py` registry is the only place that imports them. The dispatcher and CLI surface do not change beyond the comment cleanup.

---

## Background notes for the implementer

**Read these files first** (paths relative to repo root):

- `src/agent_toolkit_cli/harness_adapters/codex.py` — your reference. Every method on `ClaudeAdapter` and `OpenCodeAdapter` has a same-named counterpart here.
- `src/agent_toolkit_cli/harness_adapters/base.py` — `ConfigFileAdapter` Protocol, `McpEntry`, `WriteAction`, `CannotInstall`, `Scope`. You implement the Protocol; do not import it as a base class.
- `src/agent_toolkit_cli/commands/_mcp_dispatch.py` — the dispatcher that calls your `adapter.diff()`. You don't touch this except for the comment on line 57.
- `tests/test_mcp_adapters_codex.py` — the test pattern. Copy structure verbatim, rename harness, swap paths.
- `docs/superpowers/specs/2026-05-05-config-file-mcp-adapters-claude-opencode-design.md` — the spec; refer back for entry-shape mapping (§ Entry shape mapping) when writing `_build_entry_dict`.

**Conventions in this codebase:**
- Adapter classes are *not* subclasses; they implement the Protocol via duck typing. The `__init__.py` factory returns instances; the parity test verifies `.strategy` matches the matrix doc.
- `from __future__ import annotations` at the top of every adapter file.
- Type hints: `Path`, `Scope`, `set[str]`, `list[McpEntry]`, `list[WriteAction]`, `dict`. No optional dependencies.
- Module docstring opens with one sentence stating the strategy + target file, followed by the ownership rule and any pre-flight refusal. Look at `codex.py` lines 1-10 for the shape.
- Tests import inside the function body (`from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter`) — keeps test collection fast and avoids loading every adapter eagerly.

**Tooling commands:**
- Tests: `uv run pytest tests/test_mcp_adapters_claude.py -x -v` (or `..._opencode.py`).
- Full suite: `uv run pytest -q`.
- Lint: `uv run ruff check .` (project doesn't have a separate fmt step in CI; `ruff check` is the gate).
- The lefthook pre-commit hook runs `pytest -q` and the schema-vendor check. **Tests must pass at every commit.**

---

## Task 1: Set up `ClaudeAdapter` skeleton + the simple introspection methods

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/claude.py` (currently a 2-line stub — replace it)
- Test: `tests/test_mcp_adapters_claude.py` (create)

The strategy: write the four "trivial" tests first (basic_attrs, user_target, project_target, can_install) and the methods that satisfy them. Defer `diff` to Task 2.

- [ ] **Step 1: Create `tests/test_mcp_adapters_claude.py` with the first four failing tests**

```python
"""Claude adapter — ConfigFileAdapter against ~/.claude.json."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None,
                url: str | None = None,
                headers: dict[str, str] | None = None):
    from agent_toolkit_cli.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env

    spec: dict = {"transport": transport, "install_method": "npx"}
    if url is not None:
        spec["url"] = url
    if headers is not None:
        spec["headers"] = headers

    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec=spec,
    )


def test_claude_adapter_basic_attrs():
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    a = ClaudeAdapter()
    assert a.name == "claude"
    assert a.strategy == "config_file"


def test_claude_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".claude.json"


def test_claude_project_config_target_requires_file(tmp_path):
    """Project target only set when .mcp.json exists at project_root."""
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = ClaudeAdapter()
    # No .mcp.json → no target
    assert a.config_target("project", proj) is None
    # Create .mcp.json → target appears
    (proj / ".mcp.json").write_text("{}\n")
    assert a.config_target("project", proj) == proj / ".mcp.json"


def test_claude_can_install_accepts_all_transports():
    """Claude supports stdio/sse/http natively — adapter does not refuse any."""
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    a = ClaudeAdapter()
    a.can_install(_make_entry(transport="stdio"))  # no exception
    a.can_install(_make_entry(transport="sse", url="https://x"))  # no exception
    a.can_install(_make_entry(transport="http", url="https://x"))  # no exception
```

- [ ] **Step 2: Run the tests, confirm they fail with ImportError on `ClaudeAdapter`**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: FAIL — every test errors with `ImportError: cannot import name 'ClaudeAdapter' from 'agent_toolkit_cli.harness_adapters.claude'`.

- [ ] **Step 3: Replace the stub at `src/agent_toolkit_cli/harness_adapters/claude.py` with the skeleton**

```python
"""Claude MCP adapter — ConfigFileAdapter against ~/.claude.json.

Round-trip via stdlib json. Managed namespace: top-level `mcpServers.<name>`.

Ownership rule (manage by name; same as codex): we own every name in
`previously_allowed ∪ {e.name for e in entries}`. On-disk entries whose names
fall outside that union are hand-rolled and preserved verbatim.

No transport refusal — Claude MCP loader supports stdio, sse, http natively.
The adapter maps `mcp_spec.transport` to the on-disk `type` field.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class ClaudeAdapter:
    name: str = "claude"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".claude.json"
        target = project_root / ".mcp.json"
        if not target.is_file():
            return None
        return target

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        # Claude supports stdio/sse/http natively; nothing to refuse.
        return None

    # ---- introspection (stubs for now; Task 3) ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        raise NotImplementedError

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        raise NotImplementedError

    # ---- diff (stub for now; Task 2) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        raise NotImplementedError
```

- [ ] **Step 4: Run the tests; the four basic ones should pass**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: PASS — `test_claude_adapter_basic_attrs`, `test_claude_user_config_target`, `test_claude_project_config_target_requires_file`, `test_claude_can_install_accepts_all_transports` all green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/claude.py tests/test_mcp_adapters_claude.py
git commit -m "feat(#55): claude adapter skeleton — config_target + can_install"
```

---

## Task 2: Implement `ClaudeAdapter.diff` for the create-when-missing case

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/claude.py` (replace `diff` stub)
- Modify: `tests/test_mcp_adapters_claude.py` (add tests)

- [ ] **Step 1: Add the failing tests for `diff` on a missing file and on a file with other top-level keys**

Append to `tests/test_mcp_adapters_claude.py`:

```python
def test_claude_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No .claude.json on disk → one create-action with rendered bytes."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.path == tmp_path / ".claude.json"
    assert act.op == "create"
    assert act.bytes_before is None
    assert act.bytes_after is not None

    parsed = json.loads(act.contents)
    assert "mcpServers" in parsed
    assert "context7" in parsed["mcpServers"]
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@upstash/context7-mcp"]
    assert server["env"] == {"TOK": "x"}


def test_claude_diff_preserves_other_top_level_keys(monkeypatch, tmp_path):
    """Adding an MCP to a .claude.json with other settings yields one update;
    the other top-level keys (theme, numStartups) survive."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "theme": "dark",
        "numStartups": 12,
    }, indent=2, sort_keys=True))
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert parsed["theme"] == "dark"
    assert parsed["numStartups"] == 12
    assert "context7" in parsed["mcpServers"]


def test_claude_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    """If on-disk already matches the desired render, diff returns []."""
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []
```

- [ ] **Step 2: Run the new tests, confirm `NotImplementedError`**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v -k "diff"`
Expected: FAIL — `NotImplementedError` from the `diff` stub.

- [ ] **Step 3: Implement `diff` and the entry-mapping helper**

Replace the `diff` stub in `src/agent_toolkit_cli/harness_adapters/claude.py` (and add the helper just below it):

```python
    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        """Reconcile on-disk config to the desired entry set.

        Ownership union: previously_allowed | {e.name for e in entries}.
        Any on-disk mcpServers.<X> whose X is outside this union is preserved.
        """
        target = self.config_target(scope, project_root)
        if target is None:
            return []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        if not target.is_file():
            doc: dict = {}
            self._merge_entries(doc, entries,
                                managed_names=managed_names,
                                desired_names=desired_names)
            rendered = self._dump(doc)
            if not rendered or rendered == b"{}\n":
                return []
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        self._merge_entries(doc, entries,
                            managed_names=managed_names,
                            desired_names=desired_names)
        after_bytes = self._dump(doc)
        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)

    @staticmethod
    def _dump(doc: dict) -> bytes:
        # Stable formatting: 2-space indent, sorted keys, trailing newline.
        return (
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")

    def _merge_entries(
        self,
        doc: dict,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        """Mutate `doc` so its `mcpServers.<X>` entries match the desired state.

        - Removes managed entries (in `managed_names`) no longer in `desired_names`.
        - Upserts each entry in `entries`.
        - Hand-rolled entries (names NOT in `managed_names`) are preserved.
        - If both `mcpServers` is absent on disk AND no entries → leave doc alone.
        """
        servers = doc.get("mcpServers")
        if servers is None and not entries:
            return

        if "mcpServers" not in doc:
            doc["mcpServers"] = {}
        servers = doc["mcpServers"]

        for name in list(servers.keys()):
            if name in managed_names and name not in desired_names:
                del servers[name]

        for entry in sorted(entries, key=lambda e: e.name):
            servers[entry.name] = self._build_entry_dict(entry)

        # Drop the empty `mcpServers` block if we ended up with nothing — keeps
        # round-trip clean when the only managed entry is unlinked.
        if not doc["mcpServers"]:
            del doc["mcpServers"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        """Translate inner_config + mcp_spec into the on-disk Claude shape.

        stdio  → {"type": "stdio", "command", "args"?, "env"?}
        sse/http → {"type": <transport>, "url", "headers"?}
        """
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport in ("sse", "http"):
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport={transport!r}"
                )
            out: dict = {"type": transport, "url": url}
            headers = spec.get("headers")
            if headers:
                out["headers"] = {str(k): str(v) for k, v in headers.items()}
            return out

        # stdio — same fields as codex
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for stdio"
            )
        out = {"type": "stdio", "command": cmd}
        if cfg.get("args"):
            out["args"] = list(cfg["args"])
        if cfg.get("env"):
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            out["env"] = {str(k): str(v) for k, v in env_dict.items()}
        return out
```

- [ ] **Step 4: Run the tests, confirm pass**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: PASS — all seven tests so far (4 from Task 1 + 3 from this task).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/claude.py tests/test_mcp_adapters_claude.py
git commit -m "feat(#55): claude adapter — diff() + entry-shape mapping for stdio/sse/http"
```

---

## Task 3: ClaudeAdapter — `list_installed`, `entry_drift`, unlink + hand-rolled preservation

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/claude.py` (replace introspection stubs)
- Modify: `tests/test_mcp_adapters_claude.py` (add tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_mcp_adapters_claude.py`:

```python
def test_claude_unlink_removes_managed_entry_via_previously_allowed(monkeypatch, tmp_path):
    """unlink semantics: entries=[], previously_allowed={'context7'} → removes context7."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    assert "context7" in json.loads(target.read_bytes())["mcpServers"]

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert "mcpServers" not in parsed or "context7" not in parsed.get("mcpServers", {})


def test_claude_unlink_does_not_touch_handrolled_entries(monkeypatch, tmp_path):
    """Names not in previously_allowed | desired are hand-rolled — preserved."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "mcpServers": {
            "preexisting": {"type": "stdio", "command": "node",
                            "args": ["./local-mcp.js"]}
        },
        "theme": "dark",
    }, indent=2, sort_keys=True) + "\n")
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    after_link = json.loads(target.read_bytes())
    assert "context7" in after_link["mcpServers"]
    assert "preexisting" in after_link["mcpServers"]
    assert after_link["theme"] == "dark"

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcpServers", {})
    assert "preexisting" in parsed["mcpServers"]
    assert parsed["theme"] == "dark"


def test_claude_link_unlink_round_trip_idempotent(monkeypatch, tmp_path):
    """Source with hand-rolled entry → link unrelated MCP → unlink → structurally equal."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    src_doc = {
        "mcpServers": {
            "preexisting": {"type": "stdio", "command": "node",
                            "args": ["./local-mcp.js"]}
        },
        "theme": "dark",
        "numStartups": 7,
    }
    target.write_text(json.dumps(src_doc, indent=2, sort_keys=True) + "\n")

    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    target.write_bytes(actions[0].contents)

    after = json.loads(target.read_bytes())
    assert after == src_doc, (
        f"Round-trip is not structurally equal.\n"
        f"src={src_doc}\nafter={after}"
    )


def test_claude_list_installed_returns_all_mcp_server_names(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "mcpServers": {
            "context7": {"type": "stdio", "command": "npx"},
            "preexisting": {"type": "stdio", "command": "node"},
        }
    }, indent=2, sort_keys=True) + "\n")
    a = ClaudeAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_claude_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_claude_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False


def test_claude_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True


def test_claude_re_link_byte_identical_when_already_linked(monkeypatch, tmp_path):
    """AC #2 analogue: re-running link with same allow-list yields no write."""
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [first] = a.diff("user", tmp_path, [entry])
    target.write_bytes(first.contents)
    actions = a.diff("user", tmp_path, [entry], previously_allowed={"context7"})
    assert actions == []
```

- [ ] **Step 2: Run, confirm `NotImplementedError` on `list_installed` / `entry_drift`**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: FAIL with NotImplementedError on list_installed, entry_drift, and the unlink-handrolled tests pass already (they only use diff).

- [ ] **Step 3: Implement `list_installed` and `entry_drift`**

Replace the two stubs in `src/agent_toolkit_cli/harness_adapters/claude.py`:

```python
    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcpServers")
        if not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        """True iff on-disk single entry differs from its template render.

        Returns False when entry is not installed — callers check
        `list_installed` separately for presence.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcpServers") or {}
        on_disk = servers.get(entry.name)
        if on_disk is None:
            return False
        template = self._build_entry_dict(entry)
        return on_disk != template
```

- [ ] **Step 4: Run all claude tests, confirm pass**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: PASS — all 14 tests so far (4 from Task 1 + 3 from Task 2 + 7 from this task).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/claude.py tests/test_mcp_adapters_claude.py
git commit -m "feat(#55): claude adapter — list_installed + entry_drift + ownership round-trip"
```

---

## Task 4: ClaudeAdapter — http/sse transport mapping + project-scope path

**Files:**
- Modify: `tests/test_mcp_adapters_claude.py` (add tests; the implementation already handles these from Task 2)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_mcp_adapters_claude.py`:

```python
def test_claude_diff_handles_http_transport(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(
        name="remote-mcp", transport="http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer xyz"},
    )
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["remote-mcp"]
    assert server["type"] == "http"
    assert server["url"] == "https://example.com/mcp"
    assert server["headers"] == {"Authorization": "Bearer xyz"}
    # No stdio fields present
    assert "command" not in server
    assert "args" not in server


def test_claude_diff_handles_sse_transport(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(name="sse-mcp", transport="sse",
                        url="https://example.com/sse")
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["sse-mcp"]
    assert server["type"] == "sse"
    assert server["url"] == "https://example.com/sse"


def test_claude_can_install_refuses_remote_without_url():
    """spec.transport=http with no spec.url → CannotInstall."""
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter
    from agent_toolkit_cli.harness_adapters.base import CannotInstall

    a = ClaudeAdapter()
    # can_install accepts everything — the refusal lives in _build_entry_dict,
    # surfaced via diff() at render time.
    entry = _make_entry(name="bad", transport="http")  # no url
    a.can_install(entry)  # passes
    with pytest.raises(CannotInstall, match="url"):
        a.diff("user", Path("/tmp"), [entry])


def test_claude_project_scope_round_trip(tmp_path):
    """Project-scope mutation against `<proj>/.mcp.json`."""
    import json
    from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".mcp.json").write_text("{}\n")
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("project", proj, [entry])
    assert act.path == proj / ".mcp.json"
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert "context7" in parsed["mcpServers"]
```

- [ ] **Step 2: Run, all four should pass already (Task 2 implemented the shape mapping)**

Run: `uv run pytest tests/test_mcp_adapters_claude.py -x -v`
Expected: PASS — 18 tests total now.

- [ ] **Step 3: Commit (test-only — no implementation change)**

```bash
git add tests/test_mcp_adapters_claude.py
git commit -m "test(#55): claude adapter — http/sse transports + project-scope round-trip"
```

---

## Task 5: OpenCodeAdapter — full implementation in one shot

The OpenCode adapter mirrors Claude almost exactly but uses a different managed key path (`mcp.<name>` instead of `mcpServers.<name>`) and a different on-disk entry shape. We can ship it in fewer steps because we just validated the pattern in Tasks 1-4.

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/opencode.py` (replace the 2-line stub)
- Test: `tests/test_mcp_adapters_opencode.py` (create)

- [ ] **Step 1: Create `tests/test_mcp_adapters_opencode.py` with the full suite**

```python
"""OpenCode adapter — ConfigFileAdapter against ~/.config/opencode/opencode.json."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None,
                url: str | None = None,
                headers: dict[str, str] | None = None):
    from agent_toolkit_cli.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env

    spec: dict = {"transport": transport, "install_method": "npx"}
    if url is not None:
        spec["url"] = url
    if headers is not None:
        spec["headers"] = headers

    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec=spec,
    )


def test_opencode_adapter_basic_attrs():
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    a = OpenCodeAdapter()
    assert a.name == "opencode"
    assert a.strategy == "config_file"


def test_opencode_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    assert a.config_target("user", tmp_path) == (
        tmp_path / ".config" / "opencode" / "opencode.json"
    )


def test_opencode_project_config_target_requires_dir(tmp_path):
    """Project target only set when .opencode/ exists in project_root."""
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = OpenCodeAdapter()
    assert a.config_target("project", proj) is None
    (proj / ".opencode").mkdir()
    assert a.config_target("project", proj) == (
        proj / ".opencode" / "opencode.json"
    )


def test_opencode_can_install_accepts_all_transports():
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    a = OpenCodeAdapter()
    a.can_install(_make_entry(transport="stdio"))
    a.can_install(_make_entry(transport="http", url="https://x"))
    a.can_install(_make_entry(transport="sse", url="https://x"))


def test_opencode_diff_creates_file_when_missing_local_shape(monkeypatch, tmp_path):
    """stdio entry → on-disk {type: 'local', command: [str, ...], environment, enabled}."""
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    [act] = a.diff("user", tmp_path, [entry])
    assert act.op == "create"
    assert act.path == tmp_path / ".config" / "opencode" / "opencode.json"
    parsed = json.loads(act.contents)
    assert "mcp" in parsed
    server = parsed["mcp"]["context7"]
    assert server["type"] == "local"
    assert server["command"] == ["npx", "-y", "@upstash/context7-mcp"]
    assert server["environment"] == {"TOK": "x"}
    assert server["enabled"] is True


def test_opencode_diff_remote_shape_for_http(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    entry = _make_entry(name="remote-mcp", transport="http",
                        url="https://example.com/mcp",
                        headers={"X-Token": "abc"})

    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcp"]["remote-mcp"]
    assert server["type"] == "remote"
    assert server["url"] == "https://example.com/mcp"
    assert server["headers"] == {"X-Token": "abc"}
    assert server["enabled"] is True


def test_opencode_diff_preserves_other_top_level_keys(monkeypatch, tmp_path):
    """theme/model/etc at top level survive link/unlink."""
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "theme": "tokyonight",
        "model": "anthropic/claude-sonnet-4",
    }, indent=2, sort_keys=True) + "\n")

    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    assert parsed["theme"] == "tokyonight"
    assert parsed["model"] == "anthropic/claude-sonnet-4"
    assert "context7" in parsed["mcp"]


def test_opencode_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    assert a.diff("user", tmp_path, [entry]) == []


def test_opencode_unlink_removes_managed_entry(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcp", {})


def test_opencode_unlink_does_not_touch_handrolled_entries(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "mcp": {
            "preexisting": {"type": "local", "command": ["node", "./local-mcp.js"],
                            "enabled": True},
        },
        "theme": "tokyonight",
    }, indent=2, sort_keys=True) + "\n")
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcp", {})
    assert "preexisting" in parsed["mcp"]
    assert parsed["theme"] == "tokyonight"


def test_opencode_link_unlink_round_trip_idempotent(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    src_doc = {
        "mcp": {
            "preexisting": {"type": "local", "command": ["node", "./local-mcp.js"],
                            "enabled": True},
        },
        "theme": "tokyonight",
        "model": "anthropic/claude-sonnet-4",
    }
    target.write_text(json.dumps(src_doc, indent=2, sort_keys=True) + "\n")

    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    [act2] = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    target.write_bytes(act2.contents)

    after = json.loads(target.read_bytes())
    assert after == src_doc


def test_opencode_list_installed_returns_all_mcp_names(monkeypatch, tmp_path):
    import json
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "mcp": {
            "context7": {"type": "local", "command": ["npx"], "enabled": True},
            "preexisting": {"type": "local", "command": ["node"], "enabled": True},
        }
    }, indent=2, sort_keys=True) + "\n")
    a = OpenCodeAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_opencode_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_opencode_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    assert a.entry_drift("user", tmp_path, entry) is False


def test_opencode_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    text = target.read_text().replace('"enabled": true', '"enabled": false')
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True


def test_opencode_re_link_is_no_op_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [first] = a.diff("user", tmp_path, [entry])
    target.write_bytes(first.contents)
    assert a.diff("user", tmp_path, [entry], previously_allowed={"context7"}) == []
```

- [ ] **Step 2: Run, confirm all fail with ImportError**

Run: `uv run pytest tests/test_mcp_adapters_opencode.py -x -v`
Expected: FAIL — ImportError on every test.

- [ ] **Step 3: Replace the stub at `src/agent_toolkit_cli/harness_adapters/opencode.py`**

```python
"""OpenCode MCP adapter — ConfigFileAdapter against ~/.config/opencode/opencode.json.

Round-trip via stdlib json. Managed namespace: top-level `mcp.<name>`.

Ownership rule (manage by name; same as codex/claude): we own every name in
`previously_allowed ∪ {e.name for e in entries}`. On-disk entries whose names
fall outside that union are hand-rolled and preserved verbatim.

Entry shape (from https://opencode.ai/docs/mcp-servers/):
  - stdio  → {"type": "local",  "command": [...], "environment": {...}, "enabled": True}
  - http   → {"type": "remote", "url": ..., "headers": {...}, "enabled": True}
  - sse    → {"type": "remote", "url": ..., "headers": {...}, "enabled": True}

Note on `enabled`: managed entries are always rendered as `enabled: True`. If a
user hand-edits an MCP entry's `enabled: False`, the next reconcile (link/fix)
re-aligns it. To disable an MCP, remove it from the allowlist instead.

No transport refusal — all three transports map to a valid on-disk shape.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class OpenCodeAdapter:
    name: str = "opencode"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".config" / "opencode" / "opencode.json"
        opencode_dir = project_root / ".opencode"
        if not opencode_dir.is_dir():
            return None
        return opencode_dir / "opencode.json"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        return None

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcp")
        if not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcp") or {}
        on_disk = servers.get(entry.name)
        if on_disk is None:
            return False
        return on_disk != self._build_entry_dict(entry)

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        if target is None:
            return []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        if not target.is_file():
            doc: dict = {}
            self._merge_entries(doc, entries,
                                managed_names=managed_names,
                                desired_names=desired_names)
            rendered = self._dump(doc)
            if not rendered or rendered == b"{}\n":
                return []
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        self._merge_entries(doc, entries,
                            managed_names=managed_names,
                            desired_names=desired_names)
        after_bytes = self._dump(doc)
        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)

    @staticmethod
    def _dump(doc: dict) -> bytes:
        return (
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")

    def _merge_entries(
        self,
        doc: dict,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        servers = doc.get("mcp")
        if servers is None and not entries:
            return

        if "mcp" not in doc:
            doc["mcp"] = {}
        servers = doc["mcp"]

        for name in list(servers.keys()):
            if name in managed_names and name not in desired_names:
                del servers[name]

        for entry in sorted(entries, key=lambda e: e.name):
            servers[entry.name] = self._build_entry_dict(entry)

        if not doc["mcp"]:
            del doc["mcp"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport in ("http", "sse"):
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport={transport!r}"
                )
            out: dict = {
                "type": "remote",
                "url": url,
                "enabled": True,
            }
            headers = spec.get("headers")
            if headers:
                out["headers"] = {str(k): str(v) for k, v in headers.items()}
            return out

        # stdio → local
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for stdio"
            )
        # OpenCode merges command + args into a single list.
        full_command: list[str] = [str(cmd)]
        if cfg.get("args"):
            full_command.extend(str(a) for a in cfg["args"])
        out = {
            "type": "local",
            "command": full_command,
            "enabled": True,
        }
        if cfg.get("env"):
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            out["environment"] = {str(k): str(v) for k, v in env_dict.items()}
        return out
```

- [ ] **Step 4: Run all opencode tests**

Run: `uv run pytest tests/test_mcp_adapters_opencode.py -x -v`
Expected: PASS — all 16 opencode tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/opencode.py tests/test_mcp_adapters_opencode.py
git commit -m "feat(#55): opencode adapter — config_file against ~/.config/opencode/opencode.json"
```

---

## Task 6: Wire both adapters into the registry

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/__init__.py:25-37`

- [ ] **Step 1: Run the existing parity tests, confirm they FAIL because doc says `unsupported (gap)` and code is about to claim `config_file`**

Run: `uv run pytest tests/test_harness_matrix.py -v`
Expected: PASS for now — the matrix doc still says `unsupported (gap)` for claude/opencode mcp, and the parity test only fails when the doc claims `config_file` without an adapter, or vice-versa. We will update the doc in Task 7 to flip both at once.

- [ ] **Step 2: Add a regression test confirming both adapters are now real**

Append to `tests/test_mcp_adapters_base.py`:

```python
def test_get_adapter_returns_real_claude_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("claude")
    assert not isinstance(a, UnimplementedAdapter)
    assert a.name == "claude"
    assert a.strategy == "config_file"


def test_get_adapter_returns_real_opencode_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("opencode")
    assert not isinstance(a, UnimplementedAdapter)
    assert a.name == "opencode"
    assert a.strategy == "config_file"


def test_get_adapter_pi_remains_unimplemented():
    """Pi MCP is unsupported by design; adapter stays UnimplementedAdapter."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("pi")
    assert isinstance(a, UnimplementedAdapter)
```

- [ ] **Step 3: Run, confirm the two new "real adapter" tests fail and `pi` test passes**

Run: `uv run pytest tests/test_mcp_adapters_base.py -x -v -k "get_adapter"`
Expected: FAIL on `test_get_adapter_returns_real_claude_adapter` and `test_get_adapter_returns_real_opencode_adapter`; PASS on `test_get_adapter_pi_remains_unimplemented`.

- [ ] **Step 4: Wire the adapters into the registry**

Edit `src/agent_toolkit_cli/harness_adapters/__init__.py`. Replace:

```python
def get_adapter(harness: str):
    """Return the adapter for `harness`.

    Raises ValueError on unknown harness names.
    Returns UnimplementedAdapter for known-but-pending harnesses.
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex":
        # Lazy import so the dependency on tomlkit (and any future codex deps)
        # only loads when the codex adapter is actually requested.
        from agent_toolkit_cli.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    return UnimplementedAdapter(harness)
```

with:

```python
def get_adapter(harness: str):
    """Return the adapter for `harness`.

    Raises ValueError on unknown harness names.
    Returns UnimplementedAdapter for known-but-pending harnesses (currently `pi`).
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex":
        from agent_toolkit_cli.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    if harness == "claude":
        from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter
        return ClaudeAdapter()
    if harness == "opencode":
        from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter
        return OpenCodeAdapter()
    return UnimplementedAdapter(harness)
```

- [ ] **Step 5: Run, confirm pass**

Run: `uv run pytest tests/test_mcp_adapters_base.py tests/test_mcp_adapters_claude.py tests/test_mcp_adapters_opencode.py -x -v`
Expected: PASS — all adapter tests green.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/__init__.py tests/test_mcp_adapters_base.py
git commit -m "feat(#55): registry wires claude + opencode ConfigFileAdapter instances"
```

---

## Task 7: Update the harness matrix doc + clean up the force-flag comment

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md` (three localised edits)
- Modify: `src/agent_toolkit_cli/commands/_mcp_dispatch.py:57`

- [ ] **Step 1: Run the matrix-parity test as a baseline — should still PASS**

Run: `uv run pytest tests/test_harness_matrix.py -x -v`
Expected: PASS (the doc still says "unsupported (gap)" for claude/opencode mcp, which is consistent with both old and new code paths — gap cells aren't required to have adapters; only `config_file` and `plugin_folder` cells are).

- [ ] **Step 2: Update the Mechanisms section line-18 prose**

Edit `docs/agent-toolkit/harness-matrix.md`. Replace:

```
- **plugin_folder** — adapter owns a whole subfolder (e.g.
  `~/.claude/plugins/agent-toolkit/`). Currently used for MCPs in Claude.
```

with:

```
- **plugin_folder** — adapter owns a whole subfolder (e.g.
  `~/.claude/plugins/agent-toolkit/`). Currently unused; reserved for future
  kinds that own a directory rather than a config file.
```

- [ ] **Step 3: Update the matrix row for `mcp`**

In the same file, replace the `mcp` row (line 54):

```
| **mcp** | unsupported (gap) — adapter not yet implemented | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | unsupported (gap) — adapter not yet implemented | unsupported (gap) — adapter not yet implemented |
```

with:

```
| **mcp** | config_file → `~/.claude.json` `mcpServers.<name>` | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | config_file → `~/.config/opencode/opencode.json` `mcp.<name>` | unsupported (by design) — Pi has no MCP concept |
```

- [ ] **Step 4: Update the "Why some pairs are by design" mcp bullet (lines 137-139)**

Replace:

```
- **mcp** is currently three gaps + one supported (codex). All four
  harnesses support MCP servers; the gaps are CLI work, not design
  limits.
```

with:

```
- **mcp** is supported on three of four harnesses (claude, codex,
  opencode) via `config_file` adapters. Pi has no MCP concept — it
  loads tools from its own extension API instead, see the
  `pi-extension` row.
```

- [ ] **Step 5: Update the `_mcp_dispatch.py` force-flag comment**

Edit `src/agent_toolkit_cli/commands/_mcp_dispatch.py`. On line 57, replace:

```python
    force: bool = False,  # noqa: ARG001 — CLI-PR-2 wires this for Claude; ignored here
```

with:

```python
    force: bool = False,  # noqa: ARG001 — reserved; not wired by any current adapter
```

- [ ] **Step 6: Run the matrix-parity test, confirm PASS**

Run: `uv run pytest tests/test_harness_matrix.py -x -v`
Expected: PASS — every config_file cell now has a real adapter (codex, claude, opencode); the pi cell is `unsupported (by design)` which never required an adapter.

- [ ] **Step 7: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md src/agent_toolkit_cli/commands/_mcp_dispatch.py
git commit -m "docs(#55): matrix — claude/opencode MCP supported, pi by design; clean force-flag comment"
```

---

## Task 8: Update the two "UnimplementedAdapter" test fixtures

The dispatcher and doctor tests both use `harness="claude"` to obtain an `UnimplementedAdapter` — that's now wrong because `claude` returns a real adapter. Switch both probes to `harness="pi"` (the only remaining unimplemented harness).

**Files:**
- Modify: `tests/test_mcp_dispatch.py:226-240`
- Modify: `tests/test_doctor_mcps.py:216-230`

- [ ] **Step 1: Run both files — they should fail or behave wrongly**

Run: `uv run pytest tests/test_mcp_dispatch.py::test_apply_link_unimplemented_adapter_is_silent_noop tests/test_doctor_mcps.py::test_doctor_mcps_skips_unimplemented_harness -x -v`

Expected:
- `test_apply_link_unimplemented_adapter_is_silent_noop` likely FAILS — `get_adapter("claude")` no longer returns `UnimplementedAdapter`, so the test's premise is wrong. The test asserts `actions == []` and empty stdout; with the real adapter and `entries=[]`, that will probably still hold by accident (claude diff with no entries → no actions). So it might pass-but-test-the-wrong-thing.
- `test_doctor_mcps_skips_unimplemented_harness` will probably FAIL because the real claude adapter is now used and the doctor surface for claude is no longer the "no MCP adapter" message.

- [ ] **Step 2: Edit `tests/test_mcp_dispatch.py:226-240`**

Replace the test:

```python
def test_apply_link_unimplemented_adapter_is_silent_noop(monkeypatch, tmp_path):
    """Unimplemented adapter returns []; caller is responsible for the skip-print
    (apply_link itself does nothing — caller should detect and print skip_message)."""
    from agent_toolkit_cli.commands._mcp_dispatch import apply_link
    from agent_toolkit_cli.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))

    a = get_adapter("claude")  # UnimplementedAdapter

    buf = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=[],
                         dry_run=False, stdout=buf)
    assert actions == []
    assert buf.getvalue() == ""
```

with:

```python
def test_apply_link_unimplemented_adapter_is_silent_noop(monkeypatch, tmp_path):
    """Unimplemented adapter returns []; caller is responsible for the skip-print
    (apply_link itself does nothing — caller should detect and print skip_message).

    Pi remains UnimplementedAdapter (Pi has no MCP support by design).
    """
    from agent_toolkit_cli.commands._mcp_dispatch import apply_link
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    monkeypatch.setenv("HOME", str(tmp_path))

    a = get_adapter("pi")  # UnimplementedAdapter
    assert isinstance(a, UnimplementedAdapter), (
        "Test assumes pi remains unimplemented — update if pi MCP support is ever added."
    )

    buf = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=[],
                         dry_run=False, stdout=buf)
    assert actions == []
    assert buf.getvalue() == ""
```

- [ ] **Step 3: Edit `tests/test_doctor_mcps.py:216-230`**

Replace:

```python
def test_doctor_mcps_skips_unimplemented_harness(monkeypatch, tmp_path):
    """harness=claude → group reports OK with 'no adapter' note (no checks attempted)."""
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    result = run(toolkit_root=tmp_path, harness="claude", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK
    assert any("no MCP adapter" in f for f in result.findings)
```

with:

```python
def test_doctor_mcps_skips_unimplemented_harness(monkeypatch, tmp_path):
    """harness=pi → group reports OK with 'no adapter' note (Pi MCP unsupported by design)."""
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    result = run(toolkit_root=tmp_path, harness="pi", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK
    assert any("no MCP adapter" in f for f in result.findings)
```

- [ ] **Step 4: Run both modified tests, confirm pass**

Run: `uv run pytest tests/test_mcp_dispatch.py::test_apply_link_unimplemented_adapter_is_silent_noop tests/test_doctor_mcps.py::test_doctor_mcps_skips_unimplemented_harness -x -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_mcp_dispatch.py tests/test_doctor_mcps.py
git commit -m "test(#55): switch UnimplementedAdapter probes from claude to pi"
```

---

## Task 9: Final full-suite + lint pass

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -q`
Expected: PASS — all 556 prior tests + the new claude/opencode/registry tests.

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`
Expected: clean (no new violations). If any violation appears in the new adapter files, fix in place — typically import order or unused imports.

- [ ] **Step 3: If anything failed, fix and re-run from Step 1. Commit any fixes:**

```bash
git add -A
git commit -m "fix(#55): address lint/test follow-ups"
```

---

## Self-review

**Spec coverage:**

- Spec § 1 (Claude adapter) — Tasks 1-4. ✓
- Spec § 2 (OpenCode adapter) — Task 5. ✓
- Spec § 3 (registry wiring) — Task 6. ✓
- Spec § 4 (force-flag comment cleanup) — Task 7 step 5. ✓
- Spec § 5 (matrix doc updates) — Task 7 steps 2-4. ✓
- Spec § 6 (tests) — Tasks 1-6 cover the new adapter tests; Task 8 covers the two existing-test edits. ✓
- Spec § 7 (entry shape mapping) — implemented in Task 2 step 3 (claude `_build_entry_dict`) and Task 5 step 3 (opencode `_build_entry_dict`). ✓
- Spec § 8 (round-trip rationale) — embedded in Task 2-3 implementation comments and the `_dump` formatter contract; tests in Tasks 3 & 5 verify structural-equal round-trip. ✓
- Acceptance criteria 1-10 — all mapped: AC1/2 = Task 6; AC3 = Tasks 3 & 5 (round-trip tests); AC4 = Tasks 3 & 5 (handrolled-preserve tests); AC5 = Tasks 2 & 5 (preserve-other-keys tests); AC6 = covered by the existing doctor harness, asserted in Task 8; AC7 = Task 7 + parity test; AC8 = Task 7 step 5; AC9 = Task 8; AC10 = Task 9.

**Placeholder scan:** none. Every step has concrete code and an exact command.

**Type consistency:** `_build_entry_dict` returns `dict` in both adapters. `_merge_entries` mutates `doc: dict` in both. `_read` returns `dict` in both. `_dump` returns `bytes` in both. Method names and signatures match across adapters.

**One adjustment for honesty:** Task 8 step 1 says "test will probably FAIL"; it might pass-by-accident with `entries=[]` and the real claude adapter (which would also return `[]` for empty entries). Either outcome is fine — what matters is that the test now intentionally targets the still-unimplemented harness, which the new code in Task 8 step 2 makes explicit via the `isinstance(...)` assertion. The test now means what it says.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-config-file-mcp-adapters-claude-opencode.md`. The flow harness chose subagent-driven execution as the default. Tasks are independent enough to dispatch one subagent each (with the codex adapter as the canonical reference), and the test suite is the safety net at every step.

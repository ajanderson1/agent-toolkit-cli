# MCP Library Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a global `mcps-library.json` the authoritative MCP-library
inventory, provide explicit legacy migration, and diagnose materialisation drift
without changing projection-lock semantics.

**Architecture:** A new `mcp_manifest.py` owns the strict, atomic v1 manifest
and converts between an authoring record and the current config/sidecar pair.
`mcp_library.py` owns physical-pair I/O; authoring commands commit the manifest
first and then materialise it. `mcp migrate` is the only backfill writer, while
`mcp doctor` compares the global manifest to the library read-only.

**Tech Stack:** Python 3.12+, Click, PyYAML, pytest, `uv`.

## Global Constraints

- Manifest path is exactly `~/.agent-toolkit/mcps-library.json`; it is global,
  strict v1 JSON, sorted, newline-terminated, and atomically written with
  `mcp_adapters.atomic_write_text`.
- A record always has `slug`, `install_method`, `transport`, `source`,
  `command`, `args`, `env`, `description`, and `resolved_version`. Nullable
  values are explicit; `args` and `env` are lists.
- `mcp add` and `mcp update` are manifest-first. Do not roll back a committed
  manifest if materialisation later fails; doctor must expose the state.
- `mcp migrate` is explicit, idempotent, non-destructive, and global-only.
  `mcp add`/`update` never silently backfill a non-empty legacy library.
- `mcp doctor` never writes. `install`, `uninstall`, and `remove` never write
  the manifest. `mcp remove` remains projection-only.
- Manifest data and diagnostics must never include literal secrets. Use only
  field paths and the literal word `redacted` in output. Quarantine every legacy
  config `env` map because v1 cannot losslessly recreate its values.
- No new runtime dependency, no `mcps-lock.json` schema change, no import/export,
  no bundle work, and no standard-harness change.
- Use explicit pathspec-limited commits only. Each authored commit includes
  `Device: $(hostname -s)`.

---

## File structure

| Path | Responsibility |
|---|---|
| `src/agent_toolkit_cli/mcp_manifest.py` | Strict manifest model, safe authoring-record validation, atomic read/write, conversion to/from materialisations. |
| `src/agent_toolkit_cli/mcp_library.py` | Atomic config/sidecar materialisation and complete-pair discovery. |
| `src/agent_toolkit_cli/commands/mcp/migrate_cmd.py` | Explicit idempotent legacy adoption command. |
| `src/agent_toolkit_cli/commands/mcp/add_cmd.py` | Build a record from flags, commit it first, then materialise it. |
| `src/agent_toolkit_cli/commands/mcp/update_cmd.py` | Resolve and rewrite the manifest record first, then re-project its authority. |
| `src/agent_toolkit_cli/commands/mcp/list_cmd.py` | Prefer manifest inventory after migration; retain legacy directory fallback before it. |
| `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py` | Read-only library reconciliation plus existing projection checks. |
| `src/agent_toolkit_cli/mcp_install.py` | Project the manifest-derived configuration after migration; retain legacy fallback before it. |
| `src/agent_toolkit_cli/commands/mcp/__init__.py` | Register `migrate`. |
| `tests/test_mcp_manifest.py` | Model, strict envelope, conversion, and safety unit tests. |
| `tests/test_mcp_library.py` | Atomic pair materialisation and physical scan tests. |
| `tests/test_cli_mcp.py` | CLI migration, add/update, doctor, list, and remove integration tests. |
| `tests/test_mcp_install.py` | Projection authority test. |
| `docs/agent-toolkit/cli.md` | CLI command/reference contract. |
| `docs/asset-types/mcp.md` | Library/manifest/projection mental model. |

## Shared interfaces

The implementation introduces these exact public module-level interfaces:

- `McpManifestEntry(slug, install_method, transport, source, command, args, env,
  description, resolved_version)`: frozen, typed authoring record.
- `UnsafeMcpSpecError`: redacted failure when a literal-looking secret is found.
- `MANIFEST_FILENAME = "mcps-library.json"` and `MANIFEST_VERSION = 1`.
- `manifest_path(home)`, `read_manifest(path)`, and `write_manifest(path, entries)`:
  global path plus strict atomic serialization.
- `entry_to_inner_config(entry)`, `entry_to_metadata(entry)`, and
  `entry_from_materialisation(asset)`: the only semantic conversion boundary.
- `assert_safe_entry(entry)`: safety validation used before every persistence or
  diagnostic conversion.
- `scan_entry_files(library)`: a sorted union of config and sidecar paths.
- `materialize_entry(library, entry, overwrite)`: atomic config-first pair writer.

`scan_entry_files` returns the union of config-directory slugs and sidecar slugs,
so a sidecar-only entry is observable. `materialize_entry` uses the manifest
conversion functions, atomically writes config first then sidecar, and never
uses `README.md` as state.

---

### Task 1: Add the strict manifest model and safety boundary

**Files:**
- Create: `src/agent_toolkit_cli/mcp_manifest.py`
- Create: `tests/test_mcp_manifest.py`

**Interfaces:**
- Consumes: `McpAsset`, `atomic_write_text`, Python `json`, and `Path`.
- Produces: `McpManifestEntry`, manifest read/write functions, safe
  authoring-record conversion, and `UnsafeMcpSpecError` for all later tasks.

- [x] **Step 1: Write failing manifest-envelope tests**

```python
def test_manifest_round_trip_is_sorted_and_newline_terminated(tmp_path):
    entries = {
        "zeta": McpManifestEntry("zeta", "url", "http", "https://z/sse", None, (), (), None, None),
        "alpha": McpManifestEntry("alpha", "npx", "stdio", "alpha", "npx", ("-y", "alpha@1.0.0"), ("API_TOKEN",), "x", "1.0.0"),
    }
    path = manifest_path(tmp_path)
    write_manifest(path, entries)
    assert list(json.loads(path.read_text())["mcps"]) == ["alpha", "zeta"]
    assert path.read_text().endswith("\n")
    assert read_manifest(path) == entries

@pytest.mark.parametrize("body", [
    '{"version": 2, "mcps": {}}',
    '{"version": 1, "mcps": {"a": {"slug": "other"}}}',
    '{not json}',
])
def test_read_manifest_fails_loud_on_invalid_envelope(tmp_path, body):
    path = tmp_path / "mcps-library.json"
    path.write_text(body)
    with pytest.raises((ValueError, json.JSONDecodeError)):
        read_manifest(path)
```

- [x] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest -q tests/test_mcp_manifest.py`

Expected: collection failure because `mcp_manifest` does not exist.

- [x] **Step 3: Implement the model and serializer**

Create the frozen dataclass exactly as declared in Shared interfaces. Implement
`manifest_path(home)` as `home / ".agent-toolkit" / MANIFEST_FILENAME`.

`read_manifest` must:

```python
raw = json.loads(path.read_text(encoding="utf-8"))
if raw.get("version") != MANIFEST_VERSION or not isinstance(raw.get("mcps"), dict):
    raise ValueError(f"{path}: unsupported or malformed MCP library manifest")
```

Then validate every required key and type, require the entry slug to equal its
map key, reject unknown entry keys, call `assert_safe_entry`, and return a
`dict[str, McpManifestEntry]`. A missing file returns `{}` only at this low-level
reader; callers distinguish an absent file from an empty manifest with
`path.is_file()`. `entry_from_materialisation` must reject a legacy inner
`env` map before conversion, because retaining names while silently dropping its
values would violate the lossless-migration contract.

`write_manifest` must sort slugs, emit every record field (including nulls and
empty lists), and call `atomic_write_text(path, json.dumps(body, indent=2) + "\n")`.
Do not write a temporary manifest by hand.

- [x] **Step 4: Add conversion and safety tests**

```python
def test_url_entry_materialises_from_source_only():
    entry = McpManifestEntry("remote", "url", "http", "https://host/sse", None, (), (), None, None)
    assert entry_to_inner_config(entry) == {"type": "http", "url": "https://host/sse"}

@pytest.mark.parametrize(
    ("entry", "literal"),
    [
        (McpManifestEntry("bad-url", "url", "http", "https://u:pw@host/sse", None, (), (), None, None), "pw"),
        (McpManifestEntry("bad-arg", "local", "stdio", "/srv/mcp", "python", ("server.py", "--token=real-secret"), (), None, None), "real-secret"),
    ],
)
def test_unsafe_entry_error_redacts_literal(entry, literal):
    with pytest.raises(UnsafeMcpSpecError) as raised:
        assert_safe_entry(entry)
    assert literal not in str(raised.value)
    assert "redacted" in str(raised.value)

@pytest.mark.parametrize("entry", [
    McpManifestEntry("uv", "uvx", "stdio", "uv-server", "uvx", ("uv-server==1.0.0",), (), None, "1.0.0"),
    McpManifestEntry("docker", "docker", "stdio", "ghcr.io/org/server:latest", "docker", ("run", "--rm", "-i", "ghcr.io/org/server:latest"), (), None, "latest"),
    McpManifestEntry("local", "local", "stdio", "/srv/server", "python", ("server.py",), ("API_TOKEN",), None, "abc123"),
])
def test_method_records_materialise_without_losing_authoring_fields(entry):
    inner = entry_to_inner_config(entry)
    metadata = entry_to_metadata(entry)
    assert entry_from_materialisation(McpAsset(entry.slug, inner, metadata)) == entry
```

Implement a field-aware high-confidence detector: URL userinfo and
secret-named query values; secret-named command options/assignments and Bearer
values; non-reference values on secret-named `env` keys in legacy config; and
well-known provider-token prefixes. `$NAME` and `${NAME}` pass. Errors retain
only a field path such as `args[1]`, never a matched substring.

Implement `entry_to_inner_config`, `entry_to_metadata`, and
`entry_from_materialisation` with the four method mappings in the spec. Reject
legacy materialisations that cannot losslessly supply all authoring fields
rather than guessing a source token.

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_mcp_manifest.py`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/mcp_manifest.py tests/test_mcp_manifest.py
git commit --only -m "feat(mcp): add library manifest model" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/mcp_manifest.py tests/test_mcp_manifest.py
```

### Task 2: Make manifest records materialise as atomic library pairs

**Files:**
- Modify: `src/agent_toolkit_cli/mcp_library.py`
- Modify: `tests/test_mcp_library.py`

**Interfaces:**
- Consumes: `McpManifestEntry`, `entry_to_inner_config`, `entry_to_metadata`,
  `atomic_write_text`.
- Produces: `scan_entry_files` and `materialize_entry` for migration, add,
  update, and doctor.

- [x] **Step 1: Write failing physical-pair tests**

```python
def test_scan_entry_files_includes_config_only_and_sidecar_only(tmp_path):
    (tmp_path / "config-only").mkdir()
    (tmp_path / "config-only" / "config.json").write_text("{}")
    (tmp_path / "sidecar-only.toolkit.yaml").write_text("name: sidecar-only\n")
    scanned = scan_entry_files(tmp_path)
    assert scanned["config-only"][0] == tmp_path / "config-only" / "config.json"
    assert scanned["config-only"][1] is None
    assert scanned["sidecar-only"] == (None, tmp_path / "sidecar-only.toolkit.yaml")

def test_materialize_entry_writes_config_and_sidecar_from_manifest(tmp_path):
    entry = McpManifestEntry("demo", "npx", "stdio", "pkg", "npx", ("-y", "pkg@1.0.0"), ("API_TOKEN",), "Demo", "1.0.0")
    materialize_entry(tmp_path, entry, overwrite=False)
    assert json.loads((tmp_path / "demo" / "config.json").read_text())["args"] == ["-y", "pkg@1.0.0"]
    assert yaml.safe_load((tmp_path / "demo.toolkit.yaml").read_text())["env"] == ["API_TOKEN"]
```

- [x] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest -q tests/test_mcp_library.py`

Expected: import failure for the two new functions.

- [x] **Step 3: Implement scan and materialisation**

Implement `scan_entry_files` by collecting every immediate child directory with
`config.json` and every root `*.toolkit.yaml`, stripping only the exact suffix.
Return sorted deterministic keys with `(config_path | None, sidecar_path | None)`.

Implement `materialize_entry` as follows:

```python
entry_dir = library / entry.slug
config_path = entry_dir / "config.json"
sidecar_path = library / f"{entry.slug}.toolkit.yaml"
if not overwrite and (config_path.exists() or sidecar_path.exists()):
    raise FileExistsError(f"MCP '{entry.slug}' already exists in the library: {entry_dir}")
entry_dir.mkdir(parents=True, exist_ok=True)
atomic_write_text(config_path, json.dumps(entry_to_inner_config(entry), indent=2) + "\n")
if not (entry_dir / "README.md").exists():
    atomic_write_text(entry_dir / "README.md", f"# {entry.slug}\n")
atomic_write_text(sidecar_path, yaml.safe_dump(entry_to_metadata(entry), sort_keys=True))
```

Keep `load_mcp_asset`, `list_library`, and `_validate_inner_config` for legacy
reading and structural validation. Replace direct writes in `write_entry` with a
compatibility wrapper around the atomic materialisation path or retire it only
after all callers move; do not leave a second non-atomic writer.

- [x] **Step 4: Add a failure-between-writes test**

```python
def test_materialize_entry_leaves_config_only_when_sidecar_write_fails(tmp_path, monkeypatch):
    real_write = mcp_library.atomic_write_text
    def fail_sidecar(path, content):
        if path.name.endswith(".toolkit.yaml"):
            raise OSError("simulated sidecar failure")
        real_write(path, content)
    monkeypatch.setattr(mcp_library, "atomic_write_text", fail_sidecar)
    entry = McpManifestEntry(
        "demo", "npx", "stdio", "pkg", "npx", ("-y", "pkg@1.0.0"), (), None, "1.0.0"
    )
    with pytest.raises(OSError):
        materialize_entry(tmp_path, entry, overwrite=False)
    assert (tmp_path / "demo" / "config.json").is_file()
    assert not (tmp_path / "demo.toolkit.yaml").exists()
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_mcp_library.py tests/test_mcp_manifest.py`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/mcp_library.py tests/test_mcp_library.py
git commit --only -m "feat(mcp): materialize manifest library entries" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/mcp_library.py tests/test_mcp_library.py
```

### Task 3: Add explicit, resumable `mcp migrate`

**Files:**
- Create: `src/agent_toolkit_cli/commands/mcp/migrate_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/mcp/__init__.py`
- Modify: `tests/test_cli_mcp.py`

**Interfaces:**
- Consumes: `scan_entry_files`, `load_mcp_asset`, `entry_from_materialisation`,
  `read_manifest`, `write_manifest`, and `manifest_path`.
- Produces: global-only `agent-toolkit-cli mcp migrate`.

- [x] **Step 0: Add shared CLI test helpers**

Add these helpers near the existing `_seed`, `_git`, and `_head_sha` helpers in
`tests/test_cli_mcp.py`; they make every later test setup deterministic.

```python
def _manifest_file(home: Path) -> Path:
    return home / ".agent-toolkit" / "mcps-library.json"

def _manifest_entry(slug: str, *, description: str | None = None) -> dict:
    return {
        "slug": slug,
        "install_method": "npx",
        "transport": "stdio",
        "source": "ctx7",
        "command": "npx",
        "args": ["-y", "ctx7@9.9.9"],
        "env": [],
        "description": description,
        "resolved_version": "9.9.9",
    }

def _read_manifest(home: Path) -> dict:
    return json.loads(_manifest_file(home).read_text())["mcps"]

def _write_manifest(home: Path, entries: dict[str, dict]) -> None:
    path = _manifest_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "mcps": entries}, indent=2) + "\n")

def _migrate_seeded_library(home: Path, monkeypatch) -> None:
    _seed(home)
    monkeypatch.setenv("HOME", str(home))
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    assert result.exit_code == 0, result.output

def _snapshot_library(home: Path) -> dict[str, bytes]:
    root = home / ".agent-toolkit"
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

def _fail_sidecar_write(monkeypatch) -> None:
    import agent_toolkit_cli.mcp_library as mcp_library
    real_write = mcp_library.atomic_write_text
    def fail_sidecar(path: Path, content: str) -> None:
        if path.name.endswith(".toolkit.yaml"):
            raise OSError("simulated sidecar failure")
        real_write(path, content)
    monkeypatch.setattr(mcp_library, "atomic_write_text", fail_sidecar)

def _setup_complete_pair_without_manifest(home: Path) -> None:
    _seed(home)

def _setup_manifest_entry_without_pair(home: Path) -> None:
    _write_manifest(home, {"missing": _manifest_entry("missing")})

def _setup_manifest_entry_with_config_only(home: Path) -> None:
    library = home / ".agent-toolkit" / "mcps"
    (library / "half").mkdir(parents=True)
    (library / "half" / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"]}\n')
    _write_manifest(home, {"half": _manifest_entry("half")})

def _setup_manifest_entry_with_tampered_pair(home: Path) -> None:
    _seed(home)
    _write_manifest(home, {"context7": _manifest_entry("context7")})
    config = home / ".agent-toolkit" / "mcps" / "context7" / "config.json"
    config.write_text('{"type":"stdio","command":"evil","args":[]}\n')

def _seed_credentialed_url_entry(home: Path, *, slug: str) -> None:
    library = home / ".agent-toolkit" / "mcps"
    (library / slug).mkdir(parents=True)
    (library / slug / "config.json").write_text('{"type":"http","url":"https://user:credential-value@host/sse"}\n')
    (library / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ninstall_method: url\ntransport: http\n"
    )
```

- [x] **Step 1: Write failing CLI migration tests**

```python
def test_mcp_migrate_adopts_legacy_library(tmp_path, monkeypatch):
    _seed(tmp_path, slug="context7", env=["API_TOKEN"])
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    assert result.exit_code == 0, result.output
    manifest = json.loads((tmp_path / ".agent-toolkit" / "mcps-library.json").read_text())
    assert manifest["mcps"]["context7"]["source"] == "ctx7"
    assert manifest["mcps"]["context7"]["env"] == ["API_TOKEN"]
    assert "adopted context7" in result.output

def test_mcp_migrate_is_idempotent_and_preserves_existing_manifest_record(tmp_path, monkeypatch):
    _seed(tmp_path, slug="one")
    _seed(tmp_path, slug="two")
    monkeypatch.setenv("HOME", str(tmp_path))
    first = CliRunner().invoke(main, ["mcp", "migrate"])
    before = (tmp_path / ".agent-toolkit" / "mcps-library.json").read_text()
    second = CliRunner().invoke(main, ["mcp", "migrate"])
    assert first.exit_code == second.exit_code == 0
    assert "0 adopted" in second.output
    assert (tmp_path / ".agent-toolkit" / "mcps-library.json").read_text() == before

def test_mcp_migrate_resumes_partial_manifest_without_overwriting_authority(tmp_path, monkeypatch):
    _seed(tmp_path, slug="one")
    _seed(tmp_path, slug="two")
    _write_manifest(tmp_path, {"one": _manifest_entry("one", description="authoritative")})
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    assert result.exit_code == 0, result.output
    manifest = _read_manifest(tmp_path)
    assert manifest["one"]["description"] == "authoritative"
    assert "two" in manifest
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli_mcp.py -k migrate`

Expected: `migrate` is not registered.

- [x] **Step 3: Implement migration and registration**

Define a Click `migrate` command with no `-g`/`-p` flags. It:

1. Resolves `home = Path.home()`, library root, and global manifest path.
2. Reads existing manifest when the file exists; otherwise starts with `{}`.
3. Iterates `scan_entry_files(library)` in slug order.
4. Skips existing manifest slugs without reading or overwriting their pair.
5. For absent slugs, accepts only a complete pair, raw-materialisation safety
   inspection success, `load_mcp_asset` success, lossless
   `entry_from_materialisation` success, and `assert_safe_entry` success. A
   legacy inner `env` map fails the lossless conversion and reports no values.
6. Accumulates all successful records, then makes exactly one `write_manifest`
   call whenever the manifest path is absent or the merged mapping differs from
   the original.
7. Prints `adopted ` followed by each actual adopted slug, `skipped ` followed
   by each rejected slug and a redacted reason, then `summary: N adopted, M skipped`.

Register the command after `add_cmd` in `commands/mcp/__init__.py`.

- [x] **Step 4: Add edge-case tests**

```python
def test_mcp_migrate_creates_empty_manifest_when_only_half_pair_exists(tmp_path, monkeypatch):
    library = tmp_path / ".agent-toolkit" / "mcps"
    (library / "half").mkdir(parents=True)
    (library / "half" / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    assert result.exit_code == 0, result.output
    assert _read_manifest(tmp_path) == {}
    assert "half" in result.output

def test_mcp_migrate_adopts_uvx_docker_and_url_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    library = tmp_path / ".agent-toolkit" / "mcps"
    fixtures = {
        "uv": ('{"type":"stdio","command":"uvx","args":["uv-server==1.0.0"]}\n', "name: uv\ninstall_method: uvx\ntransport: stdio\nresolved_version: 1.0.0\n"),
        "docker": ('{"type":"stdio","command":"docker","args":["run","--rm","-i","ghcr.io/org/server:latest"]}\n', "name: docker\ninstall_method: docker\ntransport: stdio\nresolved_version: latest\n"),
        "remote": ('{"type":"http","url":"https://host/sse"}\n', "name: remote\ninstall_method: url\ntransport: http\n"),
    }
    for slug, (config, sidecar) in fixtures.items():
        (library / slug).mkdir(parents=True)
        (library / slug / "config.json").write_text(config)
        (library / f"{slug}.toolkit.yaml").write_text(sidecar)
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    manifest = _read_manifest(tmp_path)
    assert result.exit_code == 0, result.output
    assert manifest["uv"]["source"] == "uv-server"
    assert manifest["docker"]["source"] == "ghcr.io/org/server:latest"
    assert manifest["remote"]["source"] == "https://host/sse"

def test_mcp_migrate_quarantines_config_env_without_echoing_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    library = tmp_path / ".agent-toolkit" / "mcps"
    (library / "legacy-env").mkdir(parents=True)
    (library / "legacy-env" / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"],"env":{"API_TOKEN":"credential-value"}}\n'
    )
    (library / "legacy-env.toolkit.yaml").write_text(
        "name: legacy-env\ninstall_method: npx\ntransport: stdio\nresolved_version: 9.9.9\n"
    )
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    assert result.exit_code == 0, result.output
    assert "legacy-env" not in _read_manifest(tmp_path)
    assert "credential-value" not in result.output

def test_mcp_migrate_adopts_local_entry_with_source_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "myserver"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "server.py").write_text("print('v1')\n")
    _git(repo, "add", "server.py")
    _git(repo, "commit", "-q", "-m", "v1")
    sha = _head_sha(repo)
    library = tmp_path / ".agent-toolkit" / "mcps"
    (library / "loc").mkdir(parents=True)
    (library / "loc" / "config.json").write_text('{"type":"stdio","command":"python","args":["server.py"]}\n')
    (library / "loc.toolkit.yaml").write_text(
        f"name: loc\ninstall_method: local\ntransport: stdio\nsource_dir: {repo.resolve()}\nresolved_version: {sha}\n"
    )
    result = CliRunner().invoke(main, ["mcp", "migrate"])
    entry = _read_manifest(tmp_path)["loc"]
    assert result.exit_code == 0, result.output
    assert entry["source"] == str(repo.resolve())
    assert entry["command"] == "python"
    assert entry["args"] == ["server.py"]
    assert entry["resolved_version"] == sha
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_cli_mcp.py -k migrate`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/commands/mcp/migrate_cmd.py src/agent_toolkit_cli/commands/mcp/__init__.py tests/test_cli_mcp.py
git commit --only -m "feat(mcp): add explicit library migration" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/commands/mcp/migrate_cmd.py src/agent_toolkit_cli/commands/mcp/__init__.py tests/test_cli_mcp.py
```

### Task 4: Make `mcp add` manifest-first without implicit migration

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/add_cmd.py`
- Modify: `tests/test_cli_mcp.py`

**Interfaces:**
- Consumes: raw add flags, `McpManifestEntry`, manifest helpers, and
  `materialize_entry`.
- Produces: an add operation whose expected state exists before its pair.

- [x] **Step 1: Write failing add-contract tests**

```python
def test_mcp_add_writes_manifest_before_materialisation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(_resolve, "resolve_npm_version", lambda _: "1.2.3")
    result = CliRunner().invoke(main, ["mcp", "add", "--npx", "pkg", "--env", "API_TOKEN"])
    assert result.exit_code == 0, result.output
    manifest = _read_manifest(tmp_path)
    assert manifest["pkg"]["source"] == "pkg"
    assert manifest["pkg"]["env"] == ["API_TOKEN"]

@pytest.mark.parametrize("legacy_shape", ["config", "sidecar"])
def test_mcp_add_refuses_to_implicitly_backfill_any_legacy_shape(tmp_path, monkeypatch, legacy_shape):
    library = tmp_path / ".agent-toolkit" / "mcps"
    if legacy_shape == "config":
        (library / "legacy").mkdir(parents=True)
        (library / "legacy" / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    else:
        library.mkdir(parents=True)
        (library / "legacy.toolkit.yaml").write_text("name: legacy\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "add", "--url", "https://new/sse"])
    assert result.exit_code != 0
    assert "agent-toolkit-cli mcp migrate" in result.output
    assert not (tmp_path / ".agent-toolkit" / "mcps-library.json").exists()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli_mcp.py -k 'add and (manifest or backfill)'`

Expected: the legacy-library case currently creates an entry instead of
requiring migration.

- [x] **Step 3: Refactor add around an authoring record**

Keep current Click validation, slug derivation, version resolution, and output.
Immediately after determining all values, build one `McpManifestEntry` using:

- normalized source token as `source`: versionless package for npx/uvx,
  effective-tag image for docker, direct URL, or resolved absolute local path,
- actual generated stdio command/args or URL null-command shape,
- `tuple(env_vars)`, `description`, and resolved version.

Call `assert_safe_entry` before any write. Then:

```python
path = manifest_path(Path.home())
library = library_root(Path.home())
if not path.is_file() and scan_entry_files(library):
    raise click.ClickException("MCP library manifest is missing; run: agent-toolkit-cli mcp migrate")
manifest = read_manifest(path)
if final_slug in manifest or (library / final_slug / "config.json").exists():
    raise click.ClickException(f"{final_slug} already in the library; use 'mcp update {final_slug}'")
write_manifest(path, {**manifest, final_slug: entry})
materialize_entry(library, entry, overwrite=False)
```

The manifest write must occur before calling `materialize_entry`. Do not touch
`mcps-lock.json`.

- [x] **Step 4: Add unsafe-input and interrupted-write tests**

```python
def test_mcp_add_rejects_secret_without_echoing_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "add", "--url", "https://u:literal-secret@host/sse"])
    assert result.exit_code != 0
    assert "literal-secret" not in result.output
    assert not (tmp_path / ".agent-toolkit" / "mcps-library.json").exists()

def test_mcp_add_keeps_authoritative_manifest_if_sidecar_write_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _fail_sidecar_write(monkeypatch)
    result = CliRunner().invoke(main, ["mcp", "add", "--url", "https://host/sse", "--slug", "demo"])
    assert result.exit_code != 0
    assert "demo" in _read_manifest(tmp_path)
```

Use the Task 2 writer-failure fixture rather than inventing a second failure
mechanism. Doctor coverage for this final state belongs to Task 6.

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_cli_mcp.py -k 'add or migrate'`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/commands/mcp/add_cmd.py tests/test_cli_mcp.py
git commit --only -m "feat(mcp): record additions in library manifest" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/commands/mcp/add_cmd.py tests/test_cli_mcp.py
```

### Task 5: Make updates, listing, and projections honor the manifest

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/update_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/mcp/list_cmd.py`
- Modify: `src/agent_toolkit_cli/mcp_install.py`
- Modify: `tests/test_cli_mcp.py`
- Modify: `tests/test_mcp_install.py`

**Interfaces:**
- Consumes: authoritative `McpManifestEntry` and its derived inner config.
- Produces: update/re-project/list behavior that cannot accept materialisation
  edits as new library truth.

- [x] **Step 1: Write failing authority tests**

```python
def test_mcp_update_requires_explicit_migration_for_legacy_library(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert result.exit_code != 0
    assert "agent-toolkit-cli mcp migrate" in result.output

def test_mcp_install_uses_manifest_not_tampered_materialisation(tmp_path, monkeypatch):
    _migrate_seeded_library(tmp_path, monkeypatch)
    config = tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json"
    config.write_text('{"type":"stdio","command":"evil"}\n')
    project = tmp_path / "proj"; project.mkdir()
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    assert result.exit_code == 0, result.output
    assert json.loads((project / ".mcp.json").read_text())["mcpServers"]["context7"]["command"] == "npx"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli_mcp.py tests/test_mcp_install.py -k 'migration or manifest or tampered'`

Expected: update still reads the sidecar/config and install projects the
hand-edited materialisation.

- [x] **Step 3: Refactor update and projection loading**

In `update_cmd.py`, require a manifest file for non-empty libraries and look up
the slug in `read_manifest`. Refactor `_reresolve` to receive
`McpManifestEntry`, resolve `entry.source`, and return an updated immutable
entry with fresh `resolved_version` and regenerated config args. Write the
replacement manifest first, call
`materialize_entry(library, updated_entry, overwrite=True)`, then re-project
exactly as current code does.

In `mcp_install.py`, introduce a small loader:

```python
def _library_asset(slug: str, *, library_root: Path, home: Path) -> McpAsset:
    path = manifest_path(home)
    if not path.is_file():
        return load_mcp_asset(library_root, slug)  # legacy compatibility only
    entries = read_manifest(path)
    if slug not in entries:
        raise FileNotFoundError(
            f"MCP '{slug}' is not in the library manifest; run: agent-toolkit-cli mcp doctor -g"
        )
    entry = entries[slug]
    return McpAsset(slug=slug, inner_config=entry_to_inner_config(entry), metadata=entry_to_metadata(entry))
```

Use it only as the library source for `apply`; do not write or repair either
manifest or materialisation. Convert an absent manifest slug into the existing
Click-facing not-found error style.

In `list_cmd.py`, list manifest slugs when it exists and derive version/env
columns directly from each manifest record, never by reloading a physical pair.
Before migration, retain `list_library` behavior and print a concise `mcp migrate`
advisory once; do not write.

- [x] **Step 4: Add regression tests**

```python
def test_mcp_update_manifest_first_then_doctor_reports_drift(tmp_path, monkeypatch):
    _migrate_seeded_library(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version", lambda _: "10.0.0"
    )
    _fail_sidecar_write(monkeypatch)
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    doctor = CliRunner().invoke(main, ["mcp", "doctor", "-g"])
    assert result.exit_code != 0
    assert _read_manifest(tmp_path)["context7"]["resolved_version"] == "10.0.0"
    assert doctor.exit_code == 1
    assert "library-entry-drift" in doctor.output

def test_mcp_remove_preserves_manifest_and_library_entry(tmp_path, monkeypatch):
    _migrate_seeded_library(tmp_path, monkeypatch)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    installed = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"]
    )
    removed = CliRunner().invoke(main, ["mcp", "remove", "context7", "-p"])
    assert installed.exit_code == 0, installed.output
    assert removed.exit_code == 0, removed.output
    assert "context7" in _read_manifest(tmp_path)
    assert (tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").is_file()
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_cli_mcp.py tests/test_mcp_install.py`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/commands/mcp/update_cmd.py src/agent_toolkit_cli/commands/mcp/list_cmd.py src/agent_toolkit_cli/mcp_install.py tests/test_cli_mcp.py tests/test_mcp_install.py
git commit --only -m "feat(mcp): use manifest as library authority" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/commands/mcp/update_cmd.py src/agent_toolkit_cli/commands/mcp/list_cmd.py src/agent_toolkit_cli/mcp_install.py tests/test_cli_mcp.py tests/test_mcp_install.py
```

### Task 6: Add read-only library reconciliation to `mcp doctor`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py`
- Modify: `tests/test_cli_mcp.py`

**Interfaces:**
- Consumes: `read_manifest`, `scan_entry_files`, `load_mcp_asset`,
  `entry_from_materialisation`, and secret-safety errors.
- Produces: library findings plus unchanged projection findings and non-zero exit
  on any finding.

- [x] **Step 1: Write failing doctor tests for every finding family**

```python
@pytest.mark.parametrize(
    ("setup", "finding"),
    [
        (_setup_complete_pair_without_manifest, "library-entry-orphan"),
        (_setup_manifest_entry_without_pair, "library-entry-missing"),
        (_setup_manifest_entry_with_config_only, "library-entry-half-written"),
        (_setup_manifest_entry_with_tampered_pair, "library-entry-drift"),
    ],
)
def test_mcp_doctor_reports_library_findings_read_only(tmp_path, monkeypatch, setup, finding):
    setup(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    before = _snapshot_library(tmp_path)
    result = CliRunner().invoke(main, ["mcp", "doctor", "-g"])
    assert result.exit_code == 1
    assert finding in result.output
    assert _snapshot_library(tmp_path) == before

def test_mcp_doctor_missing_manifest_prints_exact_migration_remediation(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "doctor", "-g"])
    assert "remediation: agent-toolkit-cli mcp migrate" in result.output
    assert not (tmp_path / ".agent-toolkit" / "mcps-library.json").exists()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_cli_mcp.py -k doctor`

Expected: current doctor only checks projection locks and returns clean for the
library-only setups.

- [x] **Step 3: Implement the library diagnosis pass**

Add a helper returning library `Finding` objects plus an optional remediation
flag. It must:

1. Determine manifest path from the effective home, with no scope-dependent
   path.
2. Scan physical pair paths first.
3. If absent, classify complete entries as `library-entry-orphan`; classify
   incomplete entries as `library-entry-half-written`; set remediation.
4. If present, `read_manifest` fail-loud, compare the union of manifest and
   physical slugs, and apply this exact precedence: half-written, missing,
   orphan, drift.
5. For complete pairs, reconstruct an entry with `entry_from_materialisation`
   and compare dataclass equality to the manifest entry; never compare YAML/JSON
   formatting or `README.md`.
6. Catch unsafe-literal detection only to emit the existing highest-signal
   library finding with `unsafe literal at args[1]; value redacted`; never echo
   the value.

Render library findings with a stable `library` locus, for example:

```text
context7 · library · library-entry-drift
  detail: materialisation differs from manifest
```

Print the exact migration remediation after all findings when the manifest is
absent. Do not call `write_manifest`, `materialize_entry`, or `migrate`.

- [x] **Step 4: Add secret-redaction and clean-state tests**

```python
def test_mcp_doctor_redacts_secret_in_orphaned_legacy_entry(tmp_path, monkeypatch):
    _seed_credentialed_url_entry(tmp_path, slug="unsafe")
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["mcp", "doctor", "-g"])
    assert result.exit_code == 1
    assert "unsafe literal" in result.output
    assert "value redacted" in result.output
    assert "credential-value" not in result.output

def test_mcp_doctor_clean_manifest_and_pair_is_clean(tmp_path, monkeypatch):
    _migrate_seeded_library(tmp_path, monkeypatch)
    result = CliRunner().invoke(main, ["mcp", "doctor", "-g"])
    assert result.exit_code == 0, result.output
    assert "all clean" in result.output
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_cli_mcp.py -k doctor`

Expected: PASS.

- [x] **Step 6: Commit the unit**

```bash
git add src/agent_toolkit_cli/commands/mcp/doctor_cmd.py tests/test_cli_mcp.py
git commit --only -m "feat(mcp): diagnose library manifest drift" -m "Device: $(hostname -s)" -- src/agent_toolkit_cli/commands/mcp/doctor_cmd.py tests/test_cli_mcp.py
```

### Task 7: Document the authority boundary and run the full verification set

**Files:**
- Modify: `docs/agent-toolkit/cli.md`
- Modify: `docs/asset-types/mcp.md`
- Modify: `tests/test_cli_mcp.py` only if final integration coverage needs a
  shared test helper.

**Interfaces:**
- Consumes: implemented commands and documented paths.
- Produces: discoverable migration/remediation behavior and release-quality
  verification evidence.

- [x] **Step 1: Write documentation assertions as an explicit review checklist**

Add these exact facts to both relevant docs where they fit their existing
structure:

```markdown
- Global MCP library inventory: `~/.agent-toolkit/mcps-library.json`.
- `mcp migrate` adopts a legacy on-disk library explicitly and is idempotent.
- The manifest is authoritative; config/sidecar files are materialisations.
- `mcps-lock.json` records per-scope harness projections, not library membership.
- `mcp doctor` is read-only and tells a missing-manifest user to run `agent-toolkit-cli mcp migrate`.
- `mcp remove` removes projections only and keeps the library manifest entry.
```

- [x] **Step 2: Update the CLI reference and MCP asset page**

In `docs/agent-toolkit/cli.md`, add `agent-toolkit-cli mcp migrate` to the MCP
command block and describe when migration is required. In
`docs/asset-types/mcp.md`, add a distinct **Library manifest** subsection after
**How it works** that contrasts it with `mcps-lock.json` and explains doctor’s
read-only boundary.

- [x] **Step 3: Run targeted verification**

Run:

```bash
uv run pytest -q tests/test_mcp_manifest.py tests/test_mcp_library.py tests/test_mcp_install.py tests/test_cli_mcp.py
rg -n "mcps-library\.json|mcp migrate|mcps-lock\.json|projection" docs/agent-toolkit/cli.md docs/asset-types/mcp.md
```

Expected: pytest exits 0; the grep shows each required documentation fact.

- [x] **Step 4: Run the repository suite**

Run: `uv run pytest -q`

Expected: PASS. Store terminal output and any manual CLI smoke transcript in
`assets/verification/issue-481/` before opening a PR.

- [x] **Step 5: Commit the unit**

```bash
git add docs/agent-toolkit/cli.md docs/asset-types/mcp.md tests/test_cli_mcp.py
git commit --only -m "docs(mcp): explain library manifest migration" -m "Device: $(hostname -s)" -- docs/agent-toolkit/cli.md docs/asset-types/mcp.md tests/test_cli_mcp.py
```

## Final implementation verification

1. `uv run pytest -q tests/test_mcp_manifest.py tests/test_mcp_library.py tests/test_mcp_install.py tests/test_cli_mcp.py`
2. `uv run pytest -q`
3. `agent-toolkit-cli mcp migrate` against an isolated `$HOME` fixture, then run it again and confirm `0 adopted`.
4. `agent-toolkit-cli mcp doctor -g` against the isolated fixture; verify clean
   state, each drift fixture, and the exact no-write remediation.
5. Save command output under `assets/verification/issue-481/` and write the
   final visual/CLI judgment: **CLI output names manifest state and remediation
   clearly; no literal secret appears.**

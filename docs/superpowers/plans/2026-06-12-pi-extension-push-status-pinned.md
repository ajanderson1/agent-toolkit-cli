# pi-extension push/status on SHA-pinned entries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pi-extension push` skips SHA-pinned entries (informational, exit 0, batch-safe) and `pi-extension status` reports the pin as a trailing column (issue #346).

**Architecture:** Three small units mirroring the #330 `update`/`reset` precedent. (1) `push_cmd` gains a `looks_like_sha(entry.ref)` skip before the divergence machinery. (2) `InventoryRecord` gains a `pinned_sha` field, populated in `build_inventory` from the lock entry. (3) `status_cmd` appends a `pinned:<sha7>` column. Detection is the existing `looks_like_sha` heuristic — no dependency on the open #345 schema split.

**Tech Stack:** Python 3.13, Click, pytest + CliRunner. Spec: `docs/superpowers/specs/2026-06-12-pi-extension-push-status-pinned-design.md`.

**Verification baseline:** main @ 1338e35 (the spec + plan commits; line numbers cited below are HEAD-relative). Run tests with `uv run pytest`. Two pre-existing environment failures are whitelisted (fail locally on any branch, HOME-isolation): `tests/test_cli/test_pi_extension_inventory.py::test_empty_machine_is_empty`, `tests/test_tui/test_instruction_state.py::test_build_instruction_rows_empty_lock_no_canonical`.

**Commit discipline:** at /aj-run time this lands in its own worktree (own git index). The `--only <file>...` discipline and leaving pre-existing `skills-lock.json`/`uv.lock` modifications untouched is good hygiene. If pre-commit fails ONLY on the 2 whitelisted tests, `--no-verify` is approved.

---

## File structure

| File | Change |
|---|---|
| `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py` | import `looks_like_sha`; add SHA-pin skip in the loop (after line 81) |
| `src/agent_toolkit_cli/pi_extension_inventory.py` | import `looks_like_sha`; add `pinned_sha` field; populate in the lock pass |
| `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py` | append `pinned:<sha7>` 4th column |
| `tests/test_cli/test_pi_extension_inventory.py` | unit test: `pinned_sha` populated for pinned, None otherwise |
| `tests/test_cli/test_cli_pi_extension_lifecycle.py` | CLI tests: push-pinned skip + batch isolation + dirty-pinned skip; status-pinned column + unpinned-empty-field |

Facts the implementation relies on (verified on main @ 1338e35):

- `looks_like_sha(ref)` lives in `pi_extension_add.py:36`; returns True for `[0-9a-f]{7,40}`. `update_cmd.py:71` and `reset_cmd.py:77` already import and use it with the message `f"{slug}: pinned to {entry.ref[:7]} — skipping (remove and re-add to change the pin)"`.
- `push_cmd` loop: `not in lock` (l.63) → `npm row` sets `rejected` (l.70) → `copy-mode` (l.76) → `resolve_ref` (l.83). The pin skip goes after copy-mode, before `resolve_ref`.
- `build_inventory` scopes are `[("global", None), ("project", project)]` (`pi_extension_inventory.py:94-96`) — global pass first, project second, so refreshing `pinned_sha` every lock iteration makes project win, matching how `source` already behaves (l.117). The store-owned construction is `setdefault` at l.111.
- `status_cmd` prints `f"{r.slug}\t{r.origin}\t{loaded}"` (l.39).
- Test idiom `_seed_pinned_entry(tmp_path, git_sandbox)` (`test_cli_pi_extension_lifecycle.py:133`) adds a store-owned ext `pinned` via `file://{upstream}/tree/{sha}` and returns the SHA. `git_sandbox` exposes `.upstream`, `.clone`, `.env`. The pinned-entry tests set HOME + sandbox env via `monkeypatch.setenv`.

---

### Task 1: `push` skips SHA-pinned entries

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py`
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_pi_extension_lifecycle.py` (after `test_push_dirty_store_via_pr_or_direct`, ~line 217; `_seed_pinned_entry` is already defined at line 133):

```python
def test_push_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """A SHA-pinned entry must not poison `push`: skip + exit 0 (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "push", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output


def test_push_pinned_does_not_poison_batch(tmp_path, monkeypatch, git_sandbox):
    """A pinned entry alongside a clean store-owned entry: bare push over both
    stays exit 0 — the pin is a benign skip, not a rejection (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)  # 'demo', unpinned
    sha = _seed_pinned_entry(tmp_path, git_sandbox)                    # 'pinned'

    r = CliRunner().invoke(main, ["pi-extension", "push", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output


def test_push_pinned_skips_even_when_dirty(tmp_path, monkeypatch, git_sandbox):
    """The skip is unconditional w.r.t. working-tree state: a pinned checkout
    with a local edit still skips (the edit is intentionally unreachable via
    push — remove+re-add to publish) (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)
    canonical = pep.library_pi_extension_path("pinned", env={})
    (canonical / "ext.ts").write_text("// local edit on a pinned checkout")

    r = CliRunner().invoke(main, ["pi-extension", "push", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert "pushed" not in r.output.lower()  # the local edit was NOT pushed
```

(`pep` is the module alias `import agent_toolkit_cli.pi_extension_paths as pep`, already imported at the top of this test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -k "push_skips_pinned or push_pinned_does_not_poison or push_pinned_skips_even_when_dirty" -v`
Expected: all three FAIL — today `resolve_ref` on the raw SHA / divergence against `origin/<sha>` errors or reports nonsense; the `pinned to` string is absent (and the dirty-pinned case would attempt a real commit/push instead of skipping).

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py`, add the import in the `agent_toolkit_cli` import block. Place it between the `_common` import (`from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots`, line 18) and the `pi_extension_lock` import (line 19) so the block stays alphabetically ordered — exactly mirroring `update_cmd.py:13` and `reset_cmd.py:13`:

```python
from agent_toolkit_cli.pi_extension_add import looks_like_sha
```

Do NOT insert it after the multi-line `pi_extension_paths` import (lines 20-23) — that would split that block and ruff/isort would reorder it.

Then insert the skip in the loop, immediately after the copy-mode guard's closing `continue` (current line 81) and before `ref = skill_git.resolve_ref(...)` (current line 83):

```python
        if looks_like_sha(entry.ref):
            click.echo(
                f"{slug}: pinned to {entry.ref[:7]} — skipping "
                f"(remove and re-add to change the pin)"
            )
            continue
```

Do NOT set `rejected = True` — a pin is a benign no-op (nothing to push from a detached pin), unlike the `npm row` guard above which is a genuine user error. This is the batch-safety guarantee.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -k "push" -v`
Expected: ALL push tests PASS (the 2 new ones plus the pre-existing `test_push_*`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_pi_extension_lifecycle.py src/agent_toolkit_cli/commands/pi_extension/push_cmd.py
git commit --only tests/test_cli/test_cli_pi_extension_lifecycle.py --only src/agent_toolkit_cli/commands/pi_extension/push_cmd.py -m "fix(pi-extension): push skips SHA-pinned entries (#346)"
```

(If pre-commit fails ONLY on the 2 whitelisted tests, `--no-verify` is approved.)

---

### Task 2: `InventoryRecord.pinned_sha`

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_inventory.py`
- Test: `tests/test_cli/test_pi_extension_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_pi_extension_inventory.py`:

```python
def test_pinned_entry_records_pinned_sha(tmp_path):
    """A store-owned lock entry whose ref is a SHA exposes pinned_sha (#346)."""
    (tmp_path / ".agent-toolkit").mkdir()
    (tmp_path / ".agent-toolkit" / "pi-extensions-lock.json").write_text(
        json.dumps({
            "version": 1,
            "skills": {
                "pinned": {
                    "source": "acme/ext",
                    "sourceType": "github",
                    "ref": "abc1234def5678",
                },
                "tracked": {
                    "source": "acme/ext2",
                    "sourceType": "github",
                    "ref": "main",
                },
                "regfoo": {"source": "foo", "sourceType": "npm"},
            },
        }) + "\n"
    )
    records = {r.slug: r for r in build_inventory(home=tmp_path)}
    assert records["pinned"].pinned_sha == "abc1234def5678"
    assert records["tracked"].pinned_sha is None
    assert records["regfoo"].pinned_sha is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_inventory.py::test_pinned_entry_records_pinned_sha -v`
Expected: FAIL with `AttributeError: 'InventoryRecord' object has no attribute 'pinned_sha'`.

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/pi_extension_inventory.py`:

3a. Add the import near the top (alongside the other `agent_toolkit_cli` imports):

```python
from agent_toolkit_cli.pi_extension_add import looks_like_sha
```

3b. Add the field to the dataclass (currently `pi_extension_inventory.py:28-34`):

```python
@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False
    pinned_sha: str | None = None
```

3c. Populate it in the lock pass. Replace the body of the `for slug, entry in lock.skills.items():` loop (currently `pi_extension_inventory.py:107-117`) with:

```python
        for slug, entry in lock.skills.items():
            origin: Origin = "npm" if entry.source_type == "npm" else "store-owned"
            pinned_sha = entry.ref if looks_like_sha(entry.ref) else None
            rec = by_slug.setdefault(
                slug,
                InventoryRecord(
                    slug=slug, origin=origin, source=entry.source,
                    pinned_sha=pinned_sha,
                ),
            )
            # A slug that appears in both scopes: store-owned beats npm in the
            # global lock. Project lock rows refine the loaded flags only.
            if rec.origin != "store-owned" or origin == "store-owned":
                rec.origin = origin
            rec.source = entry.source
            rec.pinned_sha = pinned_sha
```

The trailing `rec.pinned_sha = pinned_sha` refreshes on every lock pass (global then project), so a slug present in both scopes ends up with the project lock's pin — matching how `rec.source` already behaves.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_inventory.py -v`
Expected: ALL PASS (the new test plus every pre-existing inventory test — the new field defaults to None so npm/untracked/loose rows are unaffected).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_pi_extension_inventory.py src/agent_toolkit_cli/pi_extension_inventory.py
git commit --only tests/test_cli/test_pi_extension_inventory.py --only src/agent_toolkit_cli/pi_extension_inventory.py -m "feat(pi-extension): InventoryRecord carries pinned_sha (#346)"
```

---

### Task 3: `status` trailing pin column

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py`
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_pi_extension_lifecycle.py`:

```python
def test_status_reports_pin_column(tmp_path, monkeypatch, git_sandbox):
    """status over a pinned entry shows a trailing pinned:<sha7> column (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert r.exit_code == 0, r.output
    line = next(ln for ln in r.output.splitlines() if ln.startswith("pinned\t"))
    fields = line.split("\t")
    assert fields[-1] == f"pinned:{sha[:7]}"
    # load-scope column preserved (4 fields: slug, origin, loaded, pin)
    assert len(fields) == 4


def test_status_unpinned_has_empty_pin_field(tmp_path, monkeypatch, git_sandbox):
    """A non-pinned store-owned entry prints an empty 4th field (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)  # 'demo'

    r = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert r.exit_code == 0, r.output
    line = next(ln for ln in r.output.splitlines() if ln.startswith("demo\t"))
    fields = line.split("\t")
    assert len(fields) == 4
    assert fields[-1] == ""
    assert "pinned:" not in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -k "status_reports_pin or status_unpinned" -v`
Expected: both FAIL — today's line has 3 fields (`slug\torigin\tloaded`), so `len(fields) == 4` fails and `fields[-1]` is the loaded value, not the pin.

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py`, replace the output line (currently `status_cmd.py:39`):

```python
        click.echo(f"{r.slug}\t{r.origin}\t{loaded}")
```

with:

```python
        pin = f"pinned:{r.pinned_sha[:7]}" if r.pinned_sha else ""
        click.echo(f"{r.slug}\t{r.origin}\t{loaded}\t{pin}")
```

(`loaded` is computed exactly as before, immediately above — unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -k "status" -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_pi_extension_lifecycle.py src/agent_toolkit_cli/commands/pi_extension/status_cmd.py
git commit --only tests/test_cli/test_cli_pi_extension_lifecycle.py --only src/agent_toolkit_cli/commands/pi_extension/status_cmd.py -m "feat(pi-extension): status reports SHA pin as trailing column (#346)"
```

---

### Task 4: full-suite verification

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest`
Expected: green, except (possibly) the 2 whitelisted HOME-isolation environment failures (`tests/test_cli/test_pi_extension_inventory.py::test_empty_machine_is_empty`, `tests/test_tui/test_instruction_state.py::test_build_instruction_rows_empty_lock_no_canonical`) — both reproduce on clean main and are NOT caused by this change.

- [ ] **Step 2: Lint + types**

Run: `uv run ruff check src/agent_toolkit_cli/commands/pi_extension/push_cmd.py src/agent_toolkit_cli/commands/pi_extension/status_cmd.py src/agent_toolkit_cli/pi_extension_inventory.py tests/test_cli/test_cli_pi_extension_lifecycle.py tests/test_cli/test_pi_extension_inventory.py && uv run mypy src/agent_toolkit_cli/commands/pi_extension/push_cmd.py src/agent_toolkit_cli/commands/pi_extension/status_cmd.py src/agent_toolkit_cli/pi_extension_inventory.py`
Expected: ruff clean; mypy no NEW errors vs main on these files (main carries pre-existing repo-wide counts — the bar is no-new-errors).

- [ ] **Step 3: Manual smoke (optional, sandbox HOME)**

```bash
HOME=$(mktemp -d) uv run agent-toolkit-cli pi-extension push nonexistent -g; echo "exit=$?"
```
Expected: a `not in` message (the not-in-lock path, unchanged) — confirms the binary runs. (A true pinned smoke needs the git_sandbox fixture; the CLI tests cover it.)

# Plan: pi-advisories — drift check should audit project scope too

Issue: #108
Spec: `docs/superpowers/specs/2026-05-19-pi-advisories-project-scope-drift-design.md`

## Task 1 — Failing tests for project-scope drift

File: `tests/test_doctor_pi_advisories.py`

1. Update the existing `test_drift_warns_when_pi_packages_declares_missing_resolution`
   to also assert the message contains `"(user)"`. (Will fail until Task 3.)
2. Add `test_drift_warns_for_project_scope`:
   - Write `<project>/.agent-toolkit.yaml` with `pi_packages: [npm:phantom]`.
   - Write `<project>/.pi/settings.json` with `{"packages": []}`.
   - Expect an advisory message containing `phantom`, `drift`, `(project)`,
     and `--scope project`.
3. Add `test_drift_independent_scopes_both_emit`:
   - User scope declares `npm:alpha` with no resolution.
   - Project scope declares `npm:beta` with no resolution.
   - Expect exactly 2 drift advisories, one labelled `(user)` mentioning
     `alpha`, one labelled `(project)` mentioning `beta`.

Run pytest: tests 1–3 fail.

## Task 2 — Refactor `_drift` to take scope + paths

File: `src/agent_toolkit_cli/doctor/pi_advisories.py`

Change signature from:

```python
def _drift(pp: PiPaths, *, declared_packages: list[str]) -> list[PiAdvisory]: ...
```

to:

```python
def _drift(
    *,
    scope: str,                  # "user" | "project"
    declared_packages: list[str],
    settings_json: Path,
    node_modules_dir: Path,
) -> list[PiAdvisory]: ...
```

Message format:

```
drift ({scope}): pi_packages declares {source!r} but missing from {missing}.
Run `agent-toolkit-cli pi load {source} --scope {scope}` to reconcile.
```

## Task 3 — Wire both scopes in `audit_pi`

In `audit_pi`:

1. Continue reading the user allowlist (`home / ".agent-toolkit.yaml"`).
2. Also read the project allowlist (`project_root / ".agent-toolkit.yaml"`).
3. Call `_drift` once per scope, passing the scope literal, its
   `pi_packages` list, and the matching `PiPaths` settings/node_modules
   properties.
4. Slug-collision call remains user-scope only (per spec § Out of scope).

Run pytest: all new tests pass, existing pass.

## Task 4 — Manual sanity

- `pytest tests/test_doctor_pi_advisories.py -v`
- Spot-check messages format with one print/repr in a scratch test if useful
  (don't commit).

## Notes

- `_pi_paths.PiPaths.project_settings_json` and `project_node_modules_dir`
  already exist — no path-resolver changes needed.
- `read_allowlist` tolerates missing files; both scopes safe to call.

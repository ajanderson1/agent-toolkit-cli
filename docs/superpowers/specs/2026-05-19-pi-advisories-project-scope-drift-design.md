# Spec: pi-advisories — drift check should audit project scope too

Issue: #108
Date: 2026-05-19

## Problem

`doctor/pi_advisories.py`'s drift check currently only audits user scope: it
reads `pi_packages:` from `~/.agent-toolkit.yaml`, `packages[]` from
`~/.pi/agent/settings.json`, and looks in `~/.pi/agent/npm/node_modules/`.
Project-scope drift (allowlist + settings.json + node_modules under
`<project_root>/.pi/`) is not checked. This is asymmetric with the
hand-authored check, which already walks both scopes.

## Goal

Drift advisories cover **both** user and project scopes, with messages that
name the scope so the operator knows which `pi load --scope <…>` invocation
reconciles each finding.

## Design

### Behaviour

For each scope (user, project):

1. Read `pi_packages:` from the scope-appropriate allowlist file.
2. Read `packages[]` from the scope-appropriate `settings.json`.
3. Enumerate the scope-appropriate `node_modules/` dir.
4. For each declared package, if it is missing from settings.json **or**
   missing from node_modules, emit a `warn` advisory.

Scope is named in the advisory message and in the `pi load` fix hint:

```
drift (user):    pi_packages declares 'npm:foo' but missing from settings.json. Run `agent-toolkit-cli pi load npm:foo --scope user` to reconcile.
drift (project): pi_packages declares 'npm:bar' but missing from node_modules. Run `agent-toolkit-cli pi load npm:bar --scope project` to reconcile.
```

### Code shape

Refactor `_drift(pp, *, declared_packages)` so it walks one scope at a time
and let `audit_pi` call it once per scope. Two options:

- **A.** Parametrise `_drift` with a scope literal + paths to settings.json
  and node_modules. `audit_pi` calls it twice.
- **B.** Inline a scope loop inside `_drift` that takes both
  scope→{declared_packages, paths} bundles.

Option **A** is the simpler default (smaller change, mirrors
`_hand_authored`'s shape — iterate at the caller, not inside the helper). Use
A.

### Public API

`audit_pi(home, project_root) -> list[PiAdvisory]` is unchanged. Doctor's
runner adapter (`run`) is unchanged.

### Tests

Add three cases mirroring the existing user-scope one:

1. `test_drift_warns_when_project_pi_packages_declares_missing_resolution`
   — project allowlist declares `npm:phantom`, project settings.json has
   `packages: []`, expect an advisory naming `phantom` and `project`.
2. `test_drift_user_scope_message_names_user_scope` — extend the existing
   user-scope test to assert `"(user)"` appears in the message.
3. `test_drift_independent_scopes` — both scopes have independent drift;
   expect two advisories, each labelled with its scope.

### Slug-collision check

Unchanged scope-wise — it operates on the user allowlist's
`pi_extensions` ∩ `pi_packages`. Issue #108 only names drift; leaving slug
collision for a future issue keeps this PR tight.

## Out of scope

- Slug-collision project-scope audit (separate concern, no issue).
- Auto-fix for drift (advisories are read-only by design).
- Performance optimisation — drift walks small dirs; one extra scope is fine.

## Acceptance

- `pytest tests/test_doctor_pi_advisories.py -q` passes including 3 new cases.
- Drift advisory messages contain `(user)` or `(project)`.
- `audit_pi` signature unchanged.

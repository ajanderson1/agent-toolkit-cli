# Spec — codex skill translator (#40-C)

## Problem

Codex's native skill loader requires `description:` at the YAML top level of every `SKILL.md`. The toolkit's v1alpha2 wrapper nests it under `metadata.description`, so codex rejects every toolkit skill at session start with:

```
ERROR codex_core::session: failed to load skill .../SKILL.md: missing field `description`
```

The skill is never registered, so codex cannot description-match it. The model falls back to ad-hoc filesystem reads, which works but bypasses the registration that makes skills discoverable.

PRs A and B prepared the machinery. **PR-C drops in the actual `(codex, skill)` translator and the matrix wiring** — and **closes #40**.

## Empirical verification (already done)

See `assets/verification/40-c/codex-frontmatter-empirical.md`. Three SKILL.md shapes were tested against `codex 0.128.0`:

| Shape | Loads | Registered |
|---|---|---|
| Bare (`description:` only) | ✓ | ✓ |
| Translated (`description:` + `agent_toolkit_cli:` wrapper) | ✓ | ✓ |
| Original v1alpha2 (no top-level `description`) | ✗ — `missing field 'description'` | ✗ |

The translated shape is the right target: minimal codex requirement met, full toolkit wrapper preserved for round-tripping.

## Translator output

```yaml
---
description: <metadata.description>
agent_toolkit_cli:
  apiVersion: <apiVersion>
  metadata: <metadata>
  spec: <spec>
---
<body>
```

This mirrors `_translate_opencode_command` exactly (no `mode:` field — codex skills don't have a sub-type concept). Reuses the existing `_render`, `_wrapper_block`, and `_description` helpers.

## Acceptance criteria (from issue #40)

1. **No-error `codex exec` startup** when a project-scope skill is linked via the toolkit. ✓ (verified empirically with the translated shape).
2. **Skill is discoverable by codex's normal description-match path** (registered). ✓ (verified empirically — `probe-skill` was listed by codex itself).

Plus PR-internal:

3. `(codex, skill)` is in `TRANSLATORS` (alongside `(opencode, agent)` and `(opencode, command)`).
4. `harness-matrix.md` cell for codex/skill goes from `symlink → ~/.codex/skills/<slug>/` to a `translate` description.
5. `_TRANSLATE_PATH_RE` in `test_harness_matrix.py` is widened to also match `skills/<slug>/SKILL.md`.
6. Unit tests for the new translator mirror the OpenCode tests.
7. The end-to-end test from PR-B (which used a stub translator) is removed in favour of using the real translator without the monkeypatch fixture.
8. `uv run pytest -q` passes.

## Out of scope

- The `claude` and `opencode` skills paths (still symlink — they don't need translation).
- Any change to the v1alpha2 schema. The fix is purely a projection-layer concern.
- Any change to MCP or non-skill kinds.

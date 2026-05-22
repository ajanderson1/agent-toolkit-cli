# Plan: skill doctor — normalise ssh ↔ https URL forms

Spec: `docs/superpowers/specs/2026-05-22-normalise-git-url-design.md`. Closes #191.

## Tasks

1. **Update `_normalise_git_url`** in `src/agent_toolkit_cli/skill_doctor.py`.
   - Add module-level `re` import (check existing imports first; reuse if already present).
   - Add `_SSH_RE` and `_HTTPS_RE` module-level compiled patterns.
   - Replace the function body per the spec. Keep the fallback `.git` strip for non-matching inputs.

2. **Add unit tests** in `tests/test_cli/test_skill_doctor.py`.
   - `test_normalise_git_url_ssh_https_equivalent` — asserts the two forms collapse to the same string.
   - `test_normalise_git_url_strips_dot_git_suffix` — `…/bar` and `…/bar.git` (HTTPS) compare equal.
   - `test_normalise_git_url_different_repos_differ` — `foo/bar` and `foo/baz` (HTTPS) compare unequal.
   - `test_normalise_git_url_fallback` — non-URL input (e.g. local `/tmp/x.git` path) still gets the trailing-`.git` strip.

3. **Run `uv run pytest -q`.** Must pass, including the pre-existing `test_diagnose_lock_source_mismatch`.

## Touched files

- `src/agent_toolkit_cli/skill_doctor.py`
- `tests/test_cli/test_skill_doctor.py`
- `docs/superpowers/specs/2026-05-22-normalise-git-url-design.md` (new)
- `docs/superpowers/plans/2026-05-22-normalise-git-url.md` (new)

# Plan — fix #251 (skill import SSH-only hang)

Spec: `docs/superpowers/specs/2026-05-27-skill-import-ssh-only-hosts-design.md`

## Task 1 — Fail loudly in `skill_git.clone` (Fix #2)

`src/agent_toolkit_cli/skill_git.py`:
- In `clone()`, build the clone-specific env: start from the scrubbed env that `_run`
  would use, then force `GIT_TERMINAL_PROMPT=0` and default `GIT_SSH_COMMAND` to
  `ssh -o BatchMode=yes` (do not clobber a caller-provided `GIT_SSH_COMMAND`).
- Pass that env to `_run`. Other git helpers unchanged.
- Keep GIT_* scrubbing intact (these two are non-`GIT_DIR`/`GIT_INDEX_FILE` and must
  survive the scrub — `GIT_TERMINAL_PROMPT` and `GIT_SSH_COMMAND` start with `GIT_` so
  they'd be scrubbed; set them on the env passed to `clone` *after* the helper builds it,
  i.e. inside a dedicated clone env-prep that re-adds them post-scrub).

Implementation detail: `_run` scrubs `GIT_*`. So clone must inject the two vars in a way
that survives the scrub. Cleanest: give `clone` its own prep that calls `_scrub` then adds
the two keys, and pass the result straight to `subprocess` via `_run(..., env=prepped)`
— but `_run` re-scrubs. To avoid double-scrub stripping them, add an allowlist entry for
`GIT_TERMINAL_PROMPT` and `GIT_SSH_COMMAND` is wrong (those aren't identity). Instead:
add a `_clone_env(env)` that scrubs then sets the two vars, and have `clone` call
`subprocess.run` through a thin path that does NOT re-scrub — reuse `_run` but extend the
allowlist with the two non-leaking clone vars. Decision: extend `_IDENTITY_ALLOWLIST`-style
handling by introducing a separate `_CLONE_SAFE` set checked in `_scrub`. Simpler: have
`clone` set the vars and call `_run`, and make `_scrub` preserve `GIT_TERMINAL_PROMPT`
and `GIT_SSH_COMMAND` (they cannot redirect commits like GIT_DIR can). Add them to a
preserved set alongside the identity allowlist.

Concretely: rename intent — add `_CLONE_PASSTHROUGH = {"GIT_TERMINAL_PROMPT",
"GIT_SSH_COMMAND"}` and make `_scrub` keep keys in identity allowlist OR clone passthrough.
Then `clone` sets the two vars on the env dict it passes to `_run`.

## Task 2 — `insteadOf`-aware clone URL (Fix #1a)

`src/agent_toolkit_cli/skill_lock.py`:
- Add `_apply_insteadof(url: str) -> str`: shell out to
  `git config --get-regexp '^url\..*\.insteadof$'` (scrubbed env, capture, tolerate
  non-zero / missing git → return url unchanged). Parse `url.<base>.insteadof <rewrite>`
  lines; for each whose `<rewrite>` value is a prefix of `url`, record (base, rewrite).
  Pick the longest matching `<rewrite>` (git precedence). Return
  `base + url[len(rewrite):]`. No match → url unchanged.
- In `clone_url_from_entry`, after computing the github/gitlab HTTPS URL, return
  `_apply_insteadof(that_url)`. Explicit `sourceUrl` and local passthrough are returned
  as-is (no rewrite — explicit URL wins; git still rewrites natively at clone time).
- Keep the function import-light and side-effect-free except the read-only git config read.

Note: this is `skill_lock.py` which currently has no subprocess import — add `subprocess`
+ reuse the same GIT_* scrub philosophy (read-only `git config`, scrub env).

## Task 3 — Incremental lock persistence (Fix #3)

`src/agent_toolkit_cli/commands/skill/import_cmd.py`:
- Move `write_lock(library_lock_path(), current)` to fire **after each** successful
  `add_entry` inside the loop (right after the `click.echo("  added ...")`), instead of
  the single post-loop write.
- Drop the now-redundant `if added: write_lock(...)` block (or keep a final write as a
  harmless no-op — prefer removing to keep one write path). Summary/notes/exit unchanged.

## Task 4 — Tests

- `tests/test_cli/test_skill_lock.py`:
  - `test_clone_url_insteadof_rewrites_github`: monkeypatch a fake `git` on PATH (or use a
    real temp `HOME` + `git config --global url."git@github.com:".insteadOf
    "https://github.com/"`) so `_apply_insteadof` rewrites
    `https://github.com/foo/bar.git` → `git@github.com:foo/bar.git`. Use an isolated
    `HOME`/`GIT_CONFIG_GLOBAL` so the host config never leaks in.
  - `test_clone_url_no_insteadof_passthrough`: with empty global config, github short-form
    still returns the HTTPS URL.
  - `test_clone_url_explicit_sourceurl_not_rewritten`: extras `sourceUrl` returned verbatim.
- `tests/test_cli/test_skill_git.py`:
  - `test_clone_sets_terminal_prompt_zero`: assert the clone subprocess runs with
    `GIT_TERMINAL_PROMPT=0` and a BatchMode `GIT_SSH_COMMAND`. Implement by monkeypatching
    `subprocess.run` to capture the `env=` kwarg, or by a wrapper-level assertion.
- `tests/test_cli/test_skill_import.py`:
  - `test_import_writes_lock_incrementally`: drive import of two skills where the SECOND
    fails; assert the FIRST is already in the on-disk lock (proves per-skill write, not
    end-of-loop). Build on existing `git_sandbox` + bad-source pattern from
    `test_import_partial_failure_exit_1_but_writes_good`.

All new git-touching tests set their own clean env (autouse `_strip_git_env` covers
os.environ; use isolated HOME/GIT_CONFIG_GLOBAL for config-reading tests).

## Task 5 — Verify + pre-flight

- `uv run ruff check` / format, `uv run mypy` (project recipe), `uv run pytest -q`.
- Capture to `assets/verification/251/`.

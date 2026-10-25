# Skill pinned reset and child dirty-state verification

## Scope

AJ requested working force reset to the configured pin and child-specific clean/dirty reporting after editing frontend-design in a shared parent checkout. Implemented inline in `fix/skill-pins-and-dirty-state`, based on local main `79caf00deeb1092c3087d1e177e20f42486b55d0`. No independent subagent review was requested or run for this increment.

- Existing `skills reset SLUG -g --force` fetches, then resets to the configured commit pin, peeled tag or fetched branch tip. It never changes a commit pin to main. A reset remains parent-wide: sibling tracked edits and local commits are discarded too. No `git clean` is added; unrelated untracked notes survive. Git's normal hard-reset handling of files obstructing tracked paths still applies.
- Explicit update remains nondestructive merge behavior; a pinned no-op update preserves local edits. Invalid or missing targets fail before reset writes. A missing checked-out branch does not fall back to a same-named tag. Full symbolic branch names avoid Git's ambiguous `heads/main` abbreviation.
- Skills acquisition/reset/update revision records use configured-target resolution. The generic `remote_head_sha` branch-observation contract is unchanged, preserving Pi pinned-add metadata. This also resolves the previously observed standalone full-SHA skill-add revision-recording failure.
- CLI/TUI child dirty states inspect only their repository-relative directory, for both third-party/read-only and owned entries. Central project status prefers the source-verified actual canonical backing rather than assuming a project-private parent cache.
- TUI parent badges report repository-wide clean/dirty state, including root files and filter-hidden children. Parent state is computed from existing local backing only, without acquiring content or probing asset remotes. Git status reads do not refresh the index.
- No schema, dependency, package-version, release, multi-kind catalogue or deletion-policy changes. Existing library-removal safety and asynchronous header-count issues remain outside scope. No reset was run on AJ's live skills.

## Evidence

- Clean focused baseline: **61 passed**.
- Initial regressions reproduced the origin/SHA failure, sibling dirty-state bleed and legacy derived-child bleed. Project cases initially exposed an invalid multi-slug install test setup; corrected to the shipped single-slug CLI before verifying the actual central-backing status failure.
- Real headless Textual tests witnessed RED for a repository-dirty parent still rendering the literal collection label, then verified parent and child badges independently.
- First full run: **3152 passed, 10 skipped, 1 failed** (`test_add_sha_pinned_lands_on_pin`). Fixed by restoring the generic branch-observation contract and limiting configured-target metadata changes to Skills.
- Second full run: **3154 passed, 10 skipped, 1 failed** (new `test_missing_branch_does_not_reset_to_same_named_tag`). A disposable Git probe proved abbreviated branch output becomes `heads/main` with a same-named tag; full symbolic refs fix the safety guard.
- Final focused compatibility gate: **110 passed**.
- Final full suite: **3155 passed, 10 skipped in 442.84s** (`uv run pytest -q`).
- Strict docs build passed. Generated uv.lock package-version synchronization was restored; no lock/dependency change is retained.

New regression files: `tests/test_cli/test_skill_pinned_reset.py` and `tests/test_tui/test_skill_dirty_paths.py`. They use disposable Git repositories and isolated assets, not AJ's live configuration.

Logs: `/tmp/skill-pins-baseline.log`, `/tmp/skill-pins-red.log`, `/tmp/skill-pins-path-red.log`, `/tmp/skill-pins-badges-red.log`, `/tmp/skill-pins-metadata-red.log`, `/tmp/skill-pins-missing-branch-red.log`, `/tmp/skill-pins-focused-compat-final.log`, `/tmp/skill-pins-full-verified.log`, `/tmp/skill-pins-docs-final.log`.

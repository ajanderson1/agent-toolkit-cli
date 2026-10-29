# Host-specific global instruction deployment

## Approved scope

AJ approved the preceding proposal: version host-named instruction files in the
asset workspace, explicitly download the latest host content from `main` into
the global canonical file, and retain the existing CLI/TUI pointer-exposure model.
AJ clarified that Git history provides rollback: no manual version numbers/tags.
Publication, package installation and live consumer cutover remain separate.

## Contract

- `atc instructions pull --source SOURCE --host HOST [--ref REF] [--replace]
  [--dry-run] [--yes]` selects `AGENTS.<host>.md` from an exported repository
  root or `agents-instructions/AGENTS.<host>.md` from a workspace Git source.
  Exactly one must exist; duplicate candidate paths are refused as ambiguous.
  Host is normalized to lowercase; source is a repository root (HTTPS/SSH,
  owner/repo shorthand, or an explicit local repository path for offline use).
- Scope is always global, independent of cwd and root `--project` selection.
- Default to freshly fetched `main` on each pull; optional `--ref` overrides it.
  Resolve the branch/ref to a commit for provenance, not as a manual version step.
  Shared rollback is an ordinary Git revert/push followed by another host pull.
  Fetch only into a disposable bare repo.
  Never checkout or execute fetched content. Reject missing, linked, non-UTF-8,
  empty, control-character-containing or oversized instruction blobs.
- Show source, host, exact commit, digest, destination and unified diff before
  confirmation. `--dry-run` and declining confirmation leave HOME unchanged.
- Existing canonical content requires `--replace`; automation also requires
  `--yes`. Canonical symlinks and nonregular files are refused, even with flags.
- Preserve a unique private deployment directory with new content, JSON provenance
  and previous content before atomically replacing canonical. No backup overwrites.
  Metadata describes a prepared deployment, not authoritative exposure state;
  compare its SHA-256 with canonical when establishing the active revision.
- `atc instructions restore DEPLOYMENT [--dry-run] [--replace] [--yes]` restores
  that deployment's previous bytes via the same safety/backup/confirmation path.
  Reject arbitrary paths, missing backups and linked backup files.
- Serialize deployment writers and recheck canonical after confirmation/staging.
  Existing harness pointers, project instructions and legacy locks stay untouched.
- No Instructions source-library registration or installation lock is introduced.
  Install/uninstall, status, doctor and TUI keep their existing pointer semantics.

## Implementation / checks

Use Python standard library plus existing Click/source parsing conventions.
Keep acquisition/deployment in `instructions_source.py`, command presentation in
`commands/instructions/pull_cmd.py`; register both commands in the group.
Tests use real local Git sources and disposable HOME; cover latest-main updates,
Git-revert rollback, optional historical selection,
preview/decline, conflicts, backup/restore, provenance, failed fetch/write and
pointer/TUI compatibility. Run focused pytest, full pytest, `uv build` and
`make docs-build`. ReleasePlease retains version/changelog authority.

## Delivery boundaries

Source publication, opening a CLI PR, package installation and live global
content/exposure changes are separate approval stages. This change supports both
standalone subtree exports and full-workspace sources; it does not publish a
user's private instructions or configure their actual host inventory. Keep
operator-specific repository identities, machine details and deployment records
outside the public CLI specification. No live host adoption is part of this PR.

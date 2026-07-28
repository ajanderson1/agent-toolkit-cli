# MCP Library Manifest Design Spec

**Issue:** [#481](https://github.com/ajanderson1/agent-toolkit-cli/issues/481)
**Status:** implementation-ready
**Decision authority:** #481 acceptance criteria; PM/CTO decisions, 2026-07-28

## Goal

Make `~/.agent-toolkit/mcps-library.json` the global, authoritative inventory of
MCP authoring specifications. The existing `<slug>/config.json` and
`<slug>.toolkit.yaml` files become materialisations that `mcp doctor` can compare
against that inventory.

## Scope and decisions

- The manifest is a separate global file, never a section in per-scope
  `mcps-lock.json`. Library authorship is global; projection locks are global or
  project scoped.
- Add `agent-toolkit-cli mcp migrate` as the sole legacy-backfill path. It is
  explicit, idempotent, non-destructive, and never runs implicitly.
- `mcp add` and `mcp update` write the manifest and materialise its entry.
  `mcp install`, `uninstall`, and `remove` do not write it.
- `mcp remove` remains a maximal projection uninstall. It deliberately keeps the
  library entry and manifest record; changing its cross-kind semantics is out of
  scope.
- `mcp doctor` stays read-only. It detects a missing/stale manifest and prints
  exactly `agent-toolkit-cli mcp migrate` as remediation.
- No import/export, bundle integration, `mcps-lock.json` semantic change, or
  standard-harness change is included.

## Manifest contract

`mcps-library.json` is newline-terminated JSON with a strict v1 envelope and
lexically sorted slugs:

```json
{
  "version": 1,
  "mcps": {
    "context7": {
      "slug": "context7",
      "install_method": "npx",
      "transport": "stdio",
      "source": "@upstash/context7-mcp",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@1.2.3"],
      "env": ["CONTEXT7_API_KEY"],
      "description": "Up-to-date documentation.",
      "resolved_version": "1.2.3"
    }
  }
}
```

Every record contains all fields above. `command`, `description`, and
`resolved_version` are `null` when inapplicable; `args` and `env` are empty
arrays when absent. `slug` must equal its map key. Only v1 and its declared
fields are accepted; malformed, unsupported-version, duplicate, or unsafe
records fail loud without printing sensitive values.

`source` is the normalized authoring token used for future updates. It preserves
source behavior rather than a user's original syntactic spelling:

| Method | `source` | Materialised config / sidecar |
|---|---|---|
| `npx`, `uvx` | versionless package token | stdio `command` + `args` from the record |
| `docker` | image including its effective tag | stdio `command` + normalized image argument |
| `url` | URL supplied to `--url` | `{ "type": "http", "url": source }`; `command: null`, `args: []` |
| `local` | resolved absolute directory | stdio `command` + `args`; sidecar `source_dir: source` |

Materialisation derives the sidecar deterministically: `name`, `install_method`,
and `transport` are always present; `resolved_version`, `source_dir`, `env`, and
`description` appear only when meaningful. `README.md` remains human prose and
is not part of semantic comparison.

## Authority, writes, and compatibility

The manifest is the sole expected state after migration. An entry pair is output,
not a second authority:

1. Validate the complete authoring record, including secret hygiene.
2. Serialize and atomically replace `mcps-library.json` using the existing
   same-directory temp-file plus `os.replace` helper.
3. Atomically replace `config.json`, then its sidecar, from that committed record.
4. Create or retain the simple `README.md` without using it for state.

There is deliberately no multi-file transaction or rollback after step 2. A crash
therefore leaves one authoritative record and either no pair, a half pair, or a
drifted pair; `mcp doctor` reports the resulting state. This is preferable to
silently losing the intended library record.

For a fresh empty library, `mcp add` writes its one-entry manifest first. If any
legacy physical entry exists (config-only, sidecar-only, or complete) and there
is no manifest, `mcp add` and `mcp update` fail with the explicit migration
command rather than creating an incomplete inventory.

Once a manifest exists, `mcp list`, `mcp update`, and projection reads use its
records as the source. A manually changed materialisation cannot change the
spec used for a projection. Before migration, legacy `list` and projection
behaviour remains directory-backed for compatibility; `doctor` explains how to
adopt it.

## `mcp migrate`

`mcp migrate` is global-only and has no scope flag. It scans the union of
`<slug>/config.json` directories and `<slug>.toolkit.yaml` sidecars, validates
complete pairs with the existing structural validator, reconstructs a manifest
record only when the historical fields are losslessly knowable, and atomically
merges those records into the manifest.

- It never edits, moves, deletes, or repairs library files.
- With no manifest, it always creates an envelope, including an empty one when
  every candidate is skipped; otherwise it contains every valid, safe pair it
  can reconstruct.
- With a manifest, it preserves every manifest record unchanged and adopts only
  valid materialisations whose slug is absent. This resumes a prior partial
  migration without treating disk as a peer authority.
- Config-only, sidecar-only, malformed, unknown-shape, unsafe, or non-lossless
  entries are logically quarantined: left untouched and omitted. A legacy
  `config.json` containing an `env` map is non-lossless because v1 stores only
  declared names, not its values, so it is quarantined even when no value looks
  secret. Output reports adopted and skipped slugs/counts without source values.
- A re-run after convergence writes no changed state and reports zero adoptions.

## Doctor reconciliation

Keep all existing projection checks. Add a global-library pass before them that
loads the manifest fail-loud and compares its records to physical entry pairs.
A missing manifest is never created by doctor; it emits redacted orphan results
for complete on-disk pairs and one exact remediation line:

```text
remediation: agent-toolkit-cli mcp migrate
```

Use one highest-signal finding per slug, in this precedence order:

1. `library-entry-half-written` — exactly one of config/sidecar exists.
2. `library-entry-missing` — a manifest record has neither materialisation file.
3. `library-entry-orphan` — a complete physical pair has no manifest record,
   including a skipped unsafe or non-lossless migration candidate; unsafe details
   name only the field path and say `value redacted`.
4. `library-entry-drift` — a complete pair and manifest record exist but their
   reconstructed authoring records differ.

`doctor` compares normalized authoring records, not file bytes or `README.md`.
It remains non-zero for any library or projection finding. Existing projection
findings keep their current scope and output semantics.

## Secret hygiene

The manifest stores declared environment **names** only, never `env` values.
A centralized field-aware detector checks manifest records and legacy
materialisations before persistence, migration, or diagnostics. It treats as
unsafe: URL userinfo or sensitive query parameters; non-reference values for
secret-named environment variables; secret-named CLI assignments/options or
Bearer credentials; and high-confidence provider-token prefixes. `$NAME` and
`${NAME}` references are safe references, not literals. Independently, migration
quarantines every legacy config `env` map because no v1 record can losslessly
recreate its values.

- `mcp add` rejects an unsafe requested authoring spec before writing any file.
- `mcp migrate` quarantines unsafe historical entries as described above.
- `mcp doctor` identifies the slug and field path only (for example,
  `args[2]`); it never includes the matched value in output, exceptions, or
  remediation.
- An unsafe manifest record fails loud with a redacted field-path error; it is
  never projected or rewritten.

## Test and documentation requirements

Tests must cover strict manifest serialization/read failure; fresh add;
explicit migration of npx, uvx, docker, URL, and `--local` entries; empty,
idempotent, and partial-manifest migration; no implicit migration when either
physical side of a legacy entry exists; config-only, sidecar-only, and config
`env` migration inputs; manifest-first failure between pair writes; each doctor
library finding; manifest-over-materialisation authority; safe redaction; and
unchanged projection-only `mcp remove` behavior.

Update the CLI reference and MCP asset-type page with the manifest path,
authority boundary, explicit migration command, doctor remediation, and the
unchanged distinction between library inventory and `mcps-lock.json`
projections.

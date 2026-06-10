# Rename "kind" terminology to "asset" / "asset type" — design

**Issue:** #355 · **Tier:** standard · **Date:** 2026-06-10

## Problem

The project's central classifier — the taxonomy over skill / agent / instructions /
pi-extension — is named "kind". The word is a poor fit:

- It is a zero-information classifier in a domain already saturated with generic
  nouns (agent, skill, instruction, extension, harness).
- Two of its members ("agent", "instruction") need "kind" to disambiguate from
  their other senses — circularly.
- It is anti-greppable: it collides with ordinary prose ("this kind of thing")
  throughout the docs.
- It compounds badly, and the compounds are everywhere: per-kind, cross-kind,
  multi-kind, meta-kind, fifth-kind, kinds-sidebar.
- It is overloaded **inside the codebase itself**: the doctor machinery has an
  unrelated `FindingKind` (missing / stray / unmanaged / …) sharing the word.
- It carries foreign baggage (Kubernetes `kind`, TypeScript `SyntaxKind`).

"Asset" is already latent in the project's own documentation ("asset kinds" in
`docs/agent-toolkit/harness-matrix.md`); this rename ratifies existing usage.

## Decision

Full rename, one atomic PR, zero behavioural change.

### Terminology contract

| Concept | Term |
|---|---|
| The things the tool manages | **assets** |
| The classifier over them | **asset type** |
| Literal alias in code | `AssetType` |
| Fields / params in code | `asset_type` |
| The frozen binding dataclass | `AssetTypeBinding` |
| Prose (docs, help text, comments) | "asset type" / "asset types" |

The four classifier **values** (`"skill"`, `"agent"`, `"instructions"`,
`"pi-extension"`) are unchanged — they are load-bearing strings (library dir
names and lock filenames derive from them).

### Code rename map (mechanical, behaviour-preserving)

- `_paths_core.py`: `KindBinding` → `AssetTypeBinding`; field `kind` →
  `asset_type`; `library_root_for_kind()` → `library_root_for_asset_type()`;
  `library_lock_path_for_kind()` → `library_lock_path_for_asset_type()`. The
  four `*_BINDING` constants keep their names.
- All consumer modules follow (~24 in `src/agent_toolkit_cli/`): the per-type
  facades (`skill_paths`, `agent_paths`, `instructions_paths`,
  `pi_extension_paths`), locks, installs, adapters, `_install_core.py`
  (`kind_noun` → `asset_type_noun`).
- Doctors: `FindingKind` → `FindingType`; `Finding.kind` → `Finding.finding_type`
  (in `skill_doctor.py`, `pi_extension_doctor.py`, and the agent doctor path).
  Printed doctor output is **byte-identical** — the f-strings print the *value*
  ("stray", "missing"), never the word "kind".
- TUI (`src/agent_toolkit_tui/`): `Kind` → `AssetType`; `_active_kind` →
  `_active_asset_type`; `action_kind` → `action_asset_type` (called directly,
  not via Textual binding strings — verified); `_show_kind` →
  `_show_asset_type`; CSS/DOM ids `kinds-sidebar` / `kinds-list` / `kind-*` →
  `asset-types-sidebar` / `asset-types-list` / `asset-type-*` (internal ids;
  the visible sidebar option labels stay exactly their current literal strings
  — `instruction` (singular, a pre-existing TUI choice distinct from the
  binding value `"instructions"`), `skill`, `pi-extension`, `agent`). The one
  intended visible TUI text change is the sidebar rail header `Static("Kind")`
  → `Static("Asset type")`.
- Comments, docstrings, and test names sweep along.

### Non-touch allowlist (the no-breaking-changes guarantee)

1. `agent_adapters/translate.py` — the `"kind"` entry in the frontmatter
   passthrough key list is a **foreign** key from external agent formats.
   Untouched.
2. Lockfile schemas (`skills-lock.json`, `agents-lock.json`,
   `pi-extensions-lock.json`, `instructions-lock.json`) — no `kind` key exists
   in any of them; zero change.
3. CLI command names, flags, arguments, exit codes, machine-readable output —
   unchanged. No `--kind` flag exists anywhere. Only help-text prose changes
   (e.g. "Per-harness verdict for the instructions kind." → "… for the
   instructions asset type.").
4. Historical dated documents — `docs/superpowers/specs/`,
   `docs/superpowers/plans/`, `docs/solutions/` — untouched; they are records
   of past decisions.
5. Library layout on disk (`~/.agent-toolkit/<dir>/`) — unchanged; dir names
   derive from the unchanged classifier values.

### Living docs renamed

`docs/agent-toolkit/harness-matrix.md` (~19 uses), any other current
`docs/agent-toolkit/` content, docstrings, and in-repo agent instructions
(CLAUDE.md / AGENTS.md) if they use the word for this taxonomy. README and
`docs/agent-toolkit/cli.md` already contain zero uses.

The MkDocs site (landed 5e1cc73, same day as this spec) is in scope:
`docs/kinds/` → `docs/asset-types/` (`git mv`), the `mkdocs.yml` nav section
label and paths, the `docs/glossary.md` "kind" entry (renamed to "asset type"
with a one-line former-name pointer), and `scripts/gen_harness_docs.py` (the
generator owns `docs/matrix.md` + `docs/harnesses/*.md` — edit the generator,
then regenerate; never hand-edit generated pages). The site is brand-new and
not yet published, so the `kinds/` → `asset-types/` URL change has no external
consumers. Historical-docs exclusions extend to `docs/audit/` and
`docs/agent-toolkit/research/` (dated point-in-time artifacts).

## Alternatives considered

- **Docs + user-visible only** — leaves code speaking the old language;
  rejected (drift).
- **Phased PRs** — mixed-terminology window between merges, re-touches shared
  call sites; rejected since nothing is serialized and atomicity is cheap.
- **Alias-and-deprecate** — no external consumer imports the Python API (it is
  a uv-tool CLI); aliases are residue with no beneficiary; rejected.
- **`asset_kind` / `AssetKind`** — keeps the disliked word; rejected.
- **Leave `FindingKind`** — would keep "kind" greppable noise forever; rejected.

## Verification

1. Full `pytest`, `mypy --strict`, `ruff` green.
2. Sandbox-HOME before/after diff of `skill|agent|instructions|pi-extension
   list / status / doctor` output: identical except help text.
3. Final audit: `grep -rniw kind src/ tests/` hits only the translate.py
   allowlist line; docs grep clean outside historical dirs.

## Delivery

One atomic PR titled `refactor: rename 'kind' terminology to 'asset type'`.
The `refactor:` type keeps release-please from cutting a feature release.
Known risk: merge conflicts with in-flight #351 work — rebase cost accepted.

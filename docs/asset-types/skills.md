# Skills

Skills are `SKILL.md` folders with optional references, scripts and supporting files. **Add registers library content; install makes it visible.** Canonicals are standalone Git checkouts or symlinks into shared parent checkouts; harness projections point to those canonicals.

- Global library: `~/.agent-toolkit/skills/`; global lock: `~/.agent-toolkit/skills-lock.json`.
- Project backing store: `~/.agent-toolkit/projects/<id>/skills/`, outside the consumer repo; project lock: `<project>/skills-lock.json`.
- Standard visibility: `.agents/skills/<slug>` (project), `~/.agents/skills/<slug>` (global). Other harnesses use their catalog-specific slots.
- `AGENT_TOOLKIT_SKILLS_ROOT` relocates the skills library and associated state; it is not an override for every kind.

## Use

```bash
agent-toolkit-cli skills add owner/repo --skill my-skill
agent-toolkit-cli skills install my-skill --scope project --agents standard
agent-toolkit-cli skills status my-skill -p
agent-toolkit-cli skills uninstall my-skill --scope project --agents standard
```

Scope defaults differ by verb; add/remove/import are library-only. Read/update/push/reset/doctor scope depends on the skills project lock; install/uninstall default global except for detected Paperclip companies. [Exact flags and defaults](../agent-toolkit/cli.md#scope-and-target-selection).

## Collections and ownership

Repository-wide add registers all real children (including a genuine root); explicit subpaths, `--skill NAME` or `--path PATH` select one. `--path` selects the recorded repository-relative directory even when its slug differs from its frontmatter name. Parent checkouts are shared by source/ref under `skills/_parents/`. A TUI collection groups these real entries rather than introducing another kind or lock schema. Source-batch install uses persisted membership, not future upstream discovery.

Owned monorepo push commits only the selected child subpath and opens a PR by default; third-party read-only parents refuse push. Update merges upstream; reset is explicitly destructive. Repeated add preserves local work and does not advance the shared checkout. Legacy rootless wrappers reconcile only during targeted install/selection-changing Apply. Missing `SKILL.md` is unhealthy; unsafe root+nested exposure combinations refuse before writes. [Storage/Git deep dive](../agent-toolkit/skill-lock.md) · [Collection controls and recovery](../agent-toolkit/tui.md#skill-collections).

## Support and unmanaged inventory

The catalog supplies skill paths, not proof that every harness supports every other kind. Standard readers share a slot; `--agents all` selects detected harnesses, not all catalog rows. Paperclip is **company/project-only** and requires a detected company; global Paperclip is unavailable. Hermes profile homes use their profile-local skill directory. See the [generated harness pages](../matrix.md) for placement.

Bounded unmanaged discovery is observational. Doctor can import supported local entries only with `--repair` and explicit per-finding confirmation; `--no-fix` does not write. Foreign destinations are not silently replaced. Explicit single-child copy fallback remains supported, but collections do not promise filtered copies or independent exposure for every loader.

Use [Commands](commands.md) for a lightweight reusable prompt; use a skill for a workflow needing richer content or support files.

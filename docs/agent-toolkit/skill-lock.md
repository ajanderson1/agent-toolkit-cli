# Skills: library, Git ownership and locks

**Add registers source; install chooses visibility.** A skill is a real `SKILL.md` folder, either a standalone checkout or a child of a shared parent checkout. Locks record source/ref/SHA metadata; the actual canonical and projection paths still need to exist and be healthy. [All lock formats](lock-files.md) · [Exact CLI surface and defaults](cli.md).

## On-disk layout

```text
~/.agent-toolkit/
├── skills-lock.json
├── skills/<slug>/                         # standalone clone or child symlink
├── skills/_parents/<owner>/<repo>[@<ref>]/ # shared monorepo checkout
└── projects/<id>/skills/                   # separate project backing store
    ├── <slug>/
    └── _parents/...

<project>/skills-lock.json                 # project source/install metadata
<project>/.agents/skills/<slug>            # Standard visibility symlink
<project>/.claude/skills/<slug>            # explicit Claude visibility symlink
```

Global projections are equivalent paths under the user's home. Standard writes `~/.agents/skills/<slug>` globally; several harnesses (including Pi) read that shared slot. Per-project canonicals live **outside** the consumer repository; only the lock and visibility links live inside it. `AGENT_TOOLKIT_SKILLS_ROOT` overrides the global skill library root; its parent holds the global lock and project store. Parent caches are under the **skills** root, not directly under `~/.agent-toolkit/`.

## Normal workflow

```bash
agent-toolkit-cli skills add owner/repo --skill my-skill
agent-toolkit-cli skills install my-skill --scope global --agents standard
agent-toolkit-cli skills list -g

# Edit the canonical SKILL.md or supporting files, then inspect and publish.
agent-toolkit-cli skills status my-skill -g
agent-toolkit-cli skills update my-skill -g
agent-toolkit-cli skills push my-skill -g
```

Add is global-library only and does not install projections. Remove is also a library operation (no `-g/-p`); uninstall chooses scope and keeps library content. List/status/update/push/reset/doctor infer project from a skills project lock, otherwise global (Paperclip company detection is an exception). Install/uninstall default global except in detected Paperclip company projects. Prefer explicit scope; do not infer it from Git membership.

| Operation | Effect / risk |
|---|---|
| `add` | Clone/register real skills; no harness visibility. Repeated registration preserves existing local work. |
| `install` / `uninstall` | Add/remove requested visibility; project install prepares separate backing content. |
| `status` | Inspect local Git state, scoped to the child subpath for owned monorepos. |
| `update` | Fetch and merge upstream; real conflicts remain for manual Git resolution. |
| `push` | Commit local changes and publish a PR branch by default; read-only monorepos refuse. |
| `reset SLUGS...` | Fetch + hard reset to upstream; explicit slugs required. Dirty trees refuse unless `--force`. This can discard local changes/commits; it is not projection repair. |
| `remove` | Delete library entry/canonical and owned projections; dirty content requires `--force`. Shared backing checkouts needed by other entries are not disposable. |
| `doctor --no-fix` | Diagnose without repair. |

## Sources, refs and collections

Sources accept `owner/repo`, Git URLs (HTTPS/SSH), local paths, skills.sh URLs and explicit repository subpaths. Select by frontmatter `name:` using `--skill NAME`, use `owner/repo/path/to/skill`, or supply `SOURCE --path path/to/skill` for an exact directory (including `.` for a real root skill). `--ref` selects a branch/tag/ref; `owner/repo@ref` is suitable only for unambiguous refs. Use `--ref` for slash-containing refs or a ref combined with a subpath.

```bash
agent-toolkit-cli skills add owner/repo/path/to/skill --ref main
agent-toolkit-cli skills add owner/repo --path packs/child --slug custom-child --ref feature/work
agent-toolkit-cli skills add --source owner/repo --ref main
agent-toolkit-cli skills install --source owner/repo --scope global --agents standard
```

Repository-wide add discovers all supported real skills, including a genuine root skill. Each is an ordinary persisted child; the TUI's **collection** is a derived source/ref group, not a fake skill or new schema. Source install selects already registered children for the exact source (across refs); it does not fetch and activate later upstream additions.

One parent checkout is reused per source/ref. Child canonicals symlink into it. Repeated registration does not advance its HEAD or disturb commits, index, unstaged/untracked files or custom slugs. Update deliberately before registering a child that only exists upstream. Explicit single-child add retains its existing whole-child copy fallback if symlinks fail; repeated add preserves its `materialised: copy` snapshot. Collection exposure is not a filtered-copy implementation or a promise about every harness loader.

Legacy rootless whole-repo wrappers reconcile inside a **targeted install or selection-changing Apply**, without a separate conversion command. Checkout history/index/local work stay intact; only targeted owned exposure changes after desired real-child links can succeed. Inventory, toggles, Revert, no-op Apply and unrelated Apply do not reconcile. Genuine root+nested combinations whose independent exposure cannot be proven are conservatively refused. Missing real `SKILL.md` content is unhealthy and cannot be repaired by pretending installation succeeded. [Collection controls, failures and recovery](tui.md#skill-collections).

### Project conversion and doctor

Project-only legacy conversion registers the complete sibling set in the project lock, exposes only selected children, and leaves the global library unchanged. A retained rootless backing is not a missing root skill. Inventory and full doctor recognize derived children through matching source/ref/path, Git backing ownership and actual canonical targets; this does not grant a library-only container permission to retire project projections.

Ordinary project-only entries can still produce an optional library-inclusion warning. Doctor does not infer project corruption from missing library membership. When offered, **add to library** uses the displayed command with the recorded child path, ref and custom slug. A recorded genuine root uses `--path .`, not repository-wide discovery, even if nested siblings now exist. It changes only global library registration/content: no project lock/projection repair, no global harness installation, and no copying of local project edits. Missing payloads, source conflicts and foreign projections remain diagnostic. Inspect any conflict before retrying; registration never resets an existing checkout.

Separate existing global clones (for example an old wrapper plus a doctor-added child) remain intact. Conflicting physical child identities retain conservative ambiguity diagnostics; no automatic deduplication or old-copy cleanup is performed.

## Git ownership and publishing

Standalone skills have their own Git working tree. Monorepo skills share a checkout; `parentUrl` and `skillPath` locate the child. Owned parents (recognized owner or explicit `--owned`) allow push; third-party parents normally carry `readOnly: true` and refuse push. Read-only here restricts publishing, not an assurance that update will discard local work.

**Push normally opens a PR.** For owned monorepos it stages/commits only the selected child subpath, preserving dirty/staged siblings. If `gh` cannot open the PR, a pushed branch and manual-opening hint may remain; inspect the output. `--direct` explicitly opts into pushing the tracked ref, not the recommended shared workflow. Default PR publishing leaves lock advancement to the later merged update.

Update fetches and merges rather than resetting. Nonoverlapping committed local edits can merge; overlapping edits produce a real conflict and a nonzero result. Resolve in the reported canonical/parent working tree, commit the resolution, then retry. Uncommitted changes can prevent a merge. Project monorepo update/reset are refused: `-g` selects the **different global library**, not an in-place re-scope of a project entry.

## Lock schema

```json
{
  "version": 1,
  "skills": {
    "my-skill": {
      "source": "owner/repo",
      "sourceType": "github",
      "ref": "main",
      "skillPath": "skills/my-skill",
      "parentUrl": "https://github.com/owner/repo.git",
      "upstreamSha": "0123456789abcdef0123456789abcdef01234567",
      "readOnly": true
    }
  }
}
```

| Field | Meaning |
|---|---|
| `source`, `sourceType` | Re-fetch address and source category. |
| `ref` | Requested branch/tag/commit reference; distinct from the observed SHA. |
| `skillPath` | Root entrypoint (`SKILL.md`) or selected parent subpath. |
| `upstreamSha` | Observed upstream commit; shared children observe parent HEAD. Not a separate user pin. |
| `localSha` | Recorded local HEAD where available; does not replace live Git inspection. |
| `parentUrl` | Shared parent repository URL; absent for standalone entries. |
| `readOnly` | Publishing refusal for read-only parents; omitted/false for owned ones. |

Unknown entry fields survive round-trip. Entries are written deterministically. Existing v3 locks retain their version and extra metadata; new locks use v1. A branch/ref and an observed SHA are not interchangeable, and one shared working tree cannot represent incompatible child pins.

## Interoperability and moving machines

The serializer accepts compatible v1/v3 skills locks; existing v3 wrapper metadata is preserved. The toolkit's global lock lives at `~/.agent-toolkit/skills-lock.json`; `npx skills` can use `~/.agents/.skill-lock.json`. Do not assume two tools share installation paths automatically. The interop test checks format compatibility, not equivalent ownership, merge or projection semantics.

Copy the global lock and run `skills import FILE` on the destination. Import is additive, skips existing entries, and reconstructs at recorded upstream SHAs unless `--latest`; it does not transport local-only edits or install projections. Incompatible existing shared-parent pins refuse rather than move siblings. [Cross-machine workflow](cli.md#moving-to-a-new-machine-cross-machine-sync).

There is no automatic end-of-session push, no public skills.sh catalog submission, and no dedicated migrate-to-monorepo command. Re-home source/history deliberately, then register the new source and reinstall desired projections.

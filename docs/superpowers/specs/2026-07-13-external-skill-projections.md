# External Skill Projection Registry

## Goal

Allow `agent-toolkit-cli skill doctor -g` to distinguish user-declared, externally managed skill symlinks from stale agent-toolkit projections, so it never offers to delete active Paperclip skills while retaining stray-symlink detection everywhere else.

## Context

`skill doctor` currently marks every symlink in a harness skill directory whose basename is absent from `skills-lock.json` as `stray_symlink`. Himalayas uses four valid Pi projections managed by Paperclip: three package skills from its transient `npx` installation and one company-owned Wiki Query skill. They are active agent dependencies, not agent-toolkit library entries.

## Design

### Registry

A global, user-owned JSON registry at `~/.agent-toolkit/external-skill-projections.json` declares exact projection paths and the target glob each is allowed to resolve to:

```json
{
  "version": 1,
  "projections": [
    {
      "path": ".pi/agent/skills/paperclip",
      "targetGlob": ".npm/_npx/*/node_modules/@paperclipai/server/skills/paperclip",
      "owner": "Paperclip"
    }
  ]
}
```

`path` and `targetGlob` are relative to the current user home directory. The target glob is evaluated at doctor runtime, allowing the volatile `npx` cache segment to change without exempting an arbitrary link.

### Doctor behavior

During the global stray-symlink scan, doctor suppresses a candidate only when all conditions hold:

1. The candidate projection path exactly matches a registry `path`.
2. The symlink resolves successfully.
3. The resolved target equals a path matched by that record's `targetGlob`.

A missing, changed, or mismatched target remains a normal `stray_symlink` finding with the existing unlink repair action. Project-scope scans do not read the global registry.

### Validation and failures

The registry is optional. When absent, doctor behavior is unchanged. When present, it must be valid JSON with `version: 1` and a `projections` list of non-empty string `path`, `targetGlob`, and `owner` fields. Invalid content makes `skill doctor` fail with a concise error rather than silently skipping protection.

## Non-goals

- Do not add externally managed entries to `skills-lock.json`.
- Do not install, update, delete, or otherwise control Paperclip skills.
- Do not suppress non-matching or undeclared symlinks.
- Do not add a registry-editing CLI surface in this change.

## Verification

- A declared matching external symlink produces no doctor finding.
- The same symlink with a mismatched target remains a `stray_symlink`.
- A malformed registry fails loudly.
- Existing stray-symlink behavior remains covered by the current test suite.
- Himalayas' four Paperclip entries are registered and `skill doctor -g --no-fix` exits clean after the deployed CLI is refreshed.

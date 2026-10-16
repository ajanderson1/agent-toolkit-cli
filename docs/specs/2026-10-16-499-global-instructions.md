# Scope-Aware Global Instructions (#499)

## Approved scope

Parent orchestrator w3B:p4 authorized native inline implementation through PR, not merge. Codex, OpenCode, and Pi remain native project AGENTS.md readers but gain managed global pointers. Other harness behavior remains unchanged; this is not an audit of all native readers.

## Contract and acceptance criteria

- Global Codex, OpenCode, and Pi pointers use ~/.codex/AGENTS.md, ~/.config/opencode/AGENTS.md, and ~/.pi/agent/AGENTS.md respectively and target canonical ~/.agent-toolkit/AGENTS.md.
- Project installs for these harnesses remain native/no-pointer; never replace project AGENTS.md with a self-link.
- The instructions matrix is the packaged source of verdicts. Scope defaults to project for existing parser callers and CLI list; explicit global list reports these three as symlink.
- Global install records the selected harness in the existing instructions lock. Apply, plan, uninstall, status, and doctor use the correct scope-specific pointer availability.
- Existing correct pointers are idempotent. Real files and foreign symlinks are never overwritten by install/uninstall. Existing explicit doctor real-file adoption remains unchanged.
- Doctor reports unmanaged global symlinks resolving to ~/.conventions/CONVENTIONS.md, including indirect and dangling targets. Findings are report-only: no adoption, replacement, or lock modification. Managed conflicts remain reported once.
- TUI shows actionable global cells for the three harnesses, project-native informational coverage, scope-correct column help, and existing global indicator behavior.
- Preserve all unrelated files and concurrent lanes. Shared composition/column-help edits require coordination approval.

## Verification gates

1. Record failing focused tests before implementation, then passing tests after each task.
2. Until #514 is integrated, run no ordinary test/pre-push command. Confine HOME, XDG_CONFIG_HOME, toolkit paths, and writable test caches to disposable paths, and inspect test startup first; otherwise wait for integration.
3. Exercise global install/status/uninstall for each harness, project native refusal, conflict preservation, unmanaged stale direct/indirect/dangling pointers, report-only doctor, and TUI scope switching.
4. Run instructions-focused CLI/adapter/matrix/TUI tests and full suite after isolation prerequisite. Build wheel and sdist; verify packaged matrix scope behavior outside source checkout.
5. Deliver PR with Closes #499 and exact tested SHA to parent for independent fresh-pane review. Do not merge.

## Exclusions

No changes to skill/agent/command/Pi extension behavior, settings, generic UI primitives, or other native harness adapters. No mutation of real user configuration during verification. Environment override policy beyond existing instructions path conventions is not introduced here.

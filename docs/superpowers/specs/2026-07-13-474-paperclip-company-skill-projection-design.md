# Spec: install Paperclip company skills through project scope

Issue: #474

## Problem

Agent Toolkit treats every project-scoped skill consumer as a conventional filesystem project. From a Paperclip company directory, it therefore creates the normal `<project>/.agents/skills/<slug>` projection. Paperclip does not consume company skills from that location.

A local Paperclip instance separates company records and company skill libraries:

- company root: `~/.paperclip/instances/<instance>/companies/<company-id>`
- company skill root: `~/.paperclip/instances/<instance>/skills/<company-id>`

Agent Toolkit should recognize this relationship while preserving its existing skill-library, project-lock, canonical-clone, projection, status, update, and uninstall model.

## Product decision

Paperclip is a main Agent Toolkit harness for the Skills asset type. It is filesystem-backed and company-scoped:

- A Paperclip company is an Agent Toolkit project scope.
- `<company-root>/skills-lock.json` remains Agent Toolkit’s project lock.
- Paperclip receives projections at `<instance-root>/skills/<company-id>/<slug>`.
- Agent Toolkit does not call Paperclip APIs, authenticate to Paperclip, or assign skills to individual Paperclip agents.

## Requirements

### R1 — Paperclip company context detection

Add a pure path resolver that walks upward from a supplied path and recognizes the nearest directory whose resolved shape is:

`<paperclip-root>/instances/<instance>/companies/<company-id>`

For the default installation, `<paperclip-root>` is `~/.paperclip`. Tests must inject a temporary home/root rather than touching the live installation.

The resolved context contains:

- company root
- instance root
- instance name
- company ID
- company skill root (`<instance-root>/skills/<company-id>`)

Detection works from the exact company root and any descendant. Paths that merely contain similarly named segments but do not have the required `instances/<instance>/companies/<company-id>` relationship are not Paperclip contexts.

### R2 — Implicit project scope and root normalization

When no explicit scope is supplied and the working path resolves to a Paperclip company context, skill operations use project scope even if `skills-lock.json` does not yet exist. The normalized project root is the detected company root, not the descendant working directory.

Explicit user scope remains authoritative:

- an explicit project path inside a company resolves to that company root;
- explicit global scope remains global and does not silently redirect into Paperclip.

This behavior applies consistently to skill read and write verbs that use implicit scope. Existing non-Paperclip scope behavior remains unchanged.

### R3 — Existing project ownership model remains intact

Paperclip project scope uses the existing Agent Toolkit lifecycle:

- project lock: `<company-root>/skills-lock.json`
- project canonical: the existing external Agent Toolkit project store derived from the normalized company root
- source reconstruction, pinning, dirty-state detection, update, push, doctor, and removal: unchanged unless they need the normalized root passed through

Paperclip’s company skill directory is a harness projection destination, not a replacement canonical clone and not a second lockfile location.

### R4 — Paperclip skill projection

Add `paperclip` as a skills harness token and catalog entry. At Paperclip project scope, its per-skill destination is:

`<instance-root>/skills/<company-id>/<slug>`

Installing creates a symlink from that destination to the existing project canonical. Parent directories may be created when the Paperclip context is valid.

The Paperclip projection follows existing ownership safeguards:

- an absent destination may be created;
- an existing symlink to the expected canonical is an idempotent no-op;
- a foreign symlink or non-symlink destination is a loud conflict;
- uninstall removes only a symlink that resolves to the expected canonical;
- no operation deletes a hand-authored directory or foreign target.

Selecting Paperclip alone must not create `<company-root>/.agents/skills/<slug>`. The Standard projection is created only when Standard is separately selected.

### R5 — Context failures are explicit

Paperclip installation is valid only at project scope with a detected Paperclip company context. Attempts to target Paperclip:

- at global scope;
- from a generic project;
- from a malformed company path; or
- when the expected instance/company relationship cannot be resolved

must fail before creating a canonical, lock entry, parent directory, or projection. Error text identifies the missing Paperclip company context and the expected path shape.

Ordinary Agent Toolkit operations from a generic project continue normally when Paperclip is not selected.

### R6 — TUI main-harness representation

Add `paperclip` to the TUI’s `MAIN_HARNESSES` source of truth and render its display name as `Paperclip`.

Skills pane behavior:

- Paperclip has a dedicated main-harness column because it is not covered by Standard.
- In a detected Paperclip company project, cells probe and toggle the company projection destination.
- Outside a detected Paperclip company project, and at global scope, Paperclip cells are visibly unavailable and cannot queue an install.
- Cell information explains that Paperclip skills are company-scoped and names the expected company-root shape without exposing unrelated local data.

Other panes remain honest:

- no Paperclip Agents, Commands, MCP, Instructions, or Pi Extension action is added;
- composition tests prove unsupported asset panes do not acquire Paperclip controls merely because it is a main harness.

### R7 — No Paperclip control-plane integration

The implementation must not add:

- HTTP or Paperclip API calls;
- API URL configuration;
- credentials, tokens, authentication, or secret storage;
- company lookup through a running Paperclip service;
- individual-agent skill assignment or synchronization;
- Paperclip-specific CLI verbs outside the existing skill command family.

## Components

### Paperclip path context

A focused module owns recognition and normalization of Paperclip company paths. It has no network, environment mutation, or filesystem-write behavior. Consumers ask it either to detect an optional context or require one with a clear domain error.

### Skill scope/root resolution

Skill scope helpers consult the path context before lockfile fallback. Install/uninstall paths that currently default directly to `Path.cwd()` receive the same normalized project root so CLI and TUI cannot disagree.

### Skill projection resolver

The generic projection boundary delegates the `paperclip` destination to the Paperclip context resolver. Existing catalog-driven destinations remain unchanged. Paperclip is rejected where no valid company context exists.

### TUI state and apply

The Skills state model represents Paperclip availability separately from linked/drift/stray state so an unavailable company-only cell cannot be mistaken for an unchecked actionable cell. Apply continues to use the existing skill install facade; it does not gain a Paperclip-specific mutation path.

## User flows

### Install from a company descendant

1. The user starts the CLI or TUI under `<company-root>/...`.
2. Agent Toolkit walks upward and normalizes project scope to `<company-root>`.
3. The user selects the Paperclip harness for a library skill.
4. Agent Toolkit preflights the Paperclip destination and ordinary project canonical.
5. Existing project materialization creates or reuses the canonical and writes `<company-root>/skills-lock.json`.
6. The projection engine creates `<instance-root>/skills/<company-id>/<slug>` pointing to the canonical.
7. Status/TUI read back the actual projection before reporting it installed.

### Uninstall

1. Agent Toolkit resolves the same company context and canonical.
2. It removes the Paperclip symlink only when ownership matches.
3. It preserves the project canonical and lock entry according to the existing skill-uninstall contract.

## Error handling

- Resolve and validate Paperclip context before any Paperclip-targeted mutation.
- Reject explicit global Paperclip installs.
- Reject generic-project Paperclip installs rather than falling back to `.agents/skills`.
- Preserve existing conflict errors for non-symlinks and foreign symlinks.
- Do not catch-and-ignore Paperclip context or projection errors.
- Never infer a company ID from arbitrary directory names outside the required layout.

## Testing

### Unit tests

- Exact company-root detection.
- Descendant-to-company-root walk-up.
- Multiple instance names, including `default`.
- Lookalike and malformed paths rejected.
- Correct company skill root derivation.
- Implicit Paperclip project scope without a lockfile.
- Explicit global scope remains global.
- Explicit project descendant normalizes to company root.
- Paperclip projection destination resolution.
- Paperclip global/generic-project refusal.

### CLI integration tests

- Install creates the project lock and Paperclip projection, but no Standard projection.
- Repeated install is idempotent.
- Foreign symlink and real-directory conflicts fail without partial projection.
- Uninstall removes owned projection only.
- Status/doctor observe the Paperclip projection correctly.
- Existing generic-project and global skill tests remain unchanged.

### TUI tests

- `MAIN_HARNESSES` includes `paperclip` in canonical order.
- Skills composition includes a dedicated Paperclip column.
- Display label is `Paperclip`.
- Paperclip company project cells can queue/apply projection changes.
- Generic-project and global Paperclip cells are unavailable and non-toggleable.
- Other asset panes do not gain Paperclip actions.

### Verification

Run focused CLI/path/TUI tests first, then `uv run pytest -q`. Because this changes a user-facing TUI surface, capture a written visual judgment and evidence showing the Paperclip column in a company-context fixture or safe test environment.

## Non-goals

- Paperclip API integration.
- Paperclip agent assignment.
- Managing Paperclip companies or instances.
- Copying skills instead of using Agent Toolkit’s existing canonical-plus-projection model.
- Adding Paperclip support to asset types other than Skills.
- Redesigning project scope or harness adapters unrelated to the Paperclip path exception.

## Classification

**L** — adding Paperclip as a main harness is an explicit new-harness risk signal. The implementation is intentionally narrow and filesystem-only, but still requires the L critical-review gate.

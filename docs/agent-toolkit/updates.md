# Toolkit package updates

Package updates replace the **Toolkit application**, including both CLI and TUI.
They are different from refreshing a skill, agent, command, extension, or MCP
registration. Updating Toolkit does not acquire assets, enable/disable harness
exposure, migrate backing, or apply pending TUI edits.

```bash
atc update --check  # Check the newest stable release now; do not change the package
atc update          # Update both applications from that release
att update          # Same updater, without opening the TUI
```

The long forms `agent-toolkit-cli update` and `agent-toolkit-tui update` are
identical. These are commands to run **in your shell**, not in the TUI grid.
Older clients without `update` require the
[one-time package-manager upgrade](installation.md#upgrade-an-older-toolkit).

## Command reference

```text
atc update [--check] [--main]
att update [--check] [--main]
```

| Option | Behavior |
|---|---|
| No options | Resolve the latest published stable GitHub release and update a supported installation if its version is newer. |
| `--check` | Force a fresh metadata check; no build, installation or checkout changes. Writes only the release-check cache for stable checks. |
| `--main` | Explicitly use the newest canonical `main` commit instead of a stable release. |
| `--main --check` | Compare that commit with available installed-source provenance; report unknown provenance honestly. |
| `--help` | Show help without making network requests or changing files. |

A successful `--check` exits **zero even when an update is available**. It is
informational, not a CI "outdated package" failure policy. Explicit network,
build and installation errors exit nonzero. There is no `update --force`,
automatic update, scheduled background installer, or in-TUI package replacement.

Top-level CLI `--project DIRECTORY` does not select a different Toolkit package,
update channel, or installation scope. The updater targets the current uv tool
environment, not a project virtual environment or asset lock.

## Stable releases and development commits

Stable checks use GitHub's latest published, non-draft/non-prerelease release
from `ajanderson1/agent-toolkit-cli`. The updater accepts stable numeric release
tags and compares versions, not lexicographic strings. An equal or newer
installed version is left alone; stable update does not downgrade it.

Development builds can share a version number across commits:

```bash
atc update --main --check
atc update --main
```

Here the updater compares **commit SHAs**. A matching known commit is left alone;
a different or unknown commit can be built even when the package version is the
same. Selecting `--main` does not change future automatic checks: they continue
to look for stable releases. To deliberately replace a development build with an
equal/older stable release, use an explicitly pinned package-manager command
from the [installation guide](installation.md), not an invented force flag.

## Startup notices

Example, using illustrative version numbers:

```text
New update available: 7.1.0 → 7.2.0. Run `atc update` to update.
```

| Invocation | Automatic check/notice |
|---|---|
| Ordinary CLI command, with **both stdout and stderr terminals** | Check cached release metadata; print a newer-version notice to **stderr**. |
| CLI output piped or redirected | No automatic check or notice. |
| CLI `--json` or explicit `--format` | No automatic check or notice, including explicit table format. |
| Help, version, shell completion, or explicit update/completion utilities | No extra automatic check. Explicit `update --check` still makes its requested check. |
| Interactive TUI startup | Check in a background worker after mounting; show a notification titled **Toolkit update**, normally for 15 seconds. |
| Headless TUI | No automatic check. |

The current version remains visible in the TUI header. An absent notice is not
proof that the network was reached or that a fresh check succeeded: it may be
cached, suppressed, disabled, or offline.

### Cache, timeouts and privacy

- Successful release observations are cached for **six hours**.
- Failed checks back off for **15 minutes**, retaining any last-known release.
  A known newer release can still produce a notice while offline.
- Automatic failures are silent and do not stop normal CLI/TUI use. Explicit
  checks refresh regardless of cache age and report errors.
- The automatic checker uses a **one-second network socket timeout**. This is
  not a strict overall startup deadline: DNS and network/proxy behavior can add
  latency. TUI I/O stays off the UI thread. Explicit metadata requests use a
  ten-second socket timeout.
- Requests concern public GitHub release/commit metadata; local assets, locks,
  credentials and project contents are not uploaded. GitHub rate limits apply.

The shared cache is:

```text
${XDG_CACHE_HOME:-~/.cache}/agent-toolkit/update.json
```

It is **not** an asset installation lock or a TUI preference. `update --check`
refreshes it without needing you to edit the JSON.

### Opt out of automatic checks

For one invocation in Bash/Zsh:

```bash
AGENT_TOOLKIT_NO_UPDATE_CHECK=1 atc skills list -g
AGENT_TOOLKIT_NO_UPDATE_CHECK=1 att
```

Or export the variable in your environment. Fish users can use
`set -gx AGENT_TOOLKIT_NO_UPDATE_CHECK 1`. Values `1`, `true`, and `yes`
(case-insensitive) disable automatic checks. There is no corresponding
`tui-settings.json` or `config.json` setting.

`atc update --check` and `att update --check` remain explicit network requests
even when this variable is set. This opt-out does not disable catalogue fetches
from an explicitly configured [subscription](catalog.md), nor is it a general
offline mode for asset operations.

## Supported installations and safeguards

Changing the package requires **uv, Git, and a non-editable `uv tool`
installation**. The updater checks the current environment against uv's tool
directory, installed metadata and editable status. Other environments are
refused rather than silently replaced. A read-only `--check` does not require
those installation prerequisites.

The updater:

1. Resolves the chosen canonical tag or `main` to a full commit SHA.
2. Fetches that exact SHA into a temporary checkout, separate from operator
   checkouts, and verifies the fetched commit.
3. Builds one wheel with `uv build`; a stable wheel's version must match its
   selected release.
4. Retains the wheel and source-bound build receipt.
5. Uses `uv tool install` to replace the package, keeping the current base Python
   interpreter. Both long and short entry points come from the same wheel.

Fetch/build/identity failures occur before replacement and leave the existing
installation untouched. uv resolves application dependencies during replacement;
package-manager failures are reported, and there is **no automatic rollback** of
an interrupted or failed installation. Inspect uv's error before retrying.
Running TUIs and other Python processes do not reload automatically.

## Build and installation provenance

Self-built update artifacts remain at:

```text
${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/updates/
├── .update-lock/                 # present only during an update, unless interrupted
└── <commit-prefix>-<unique-id>/
    ├── agent_toolkit-<version>-py3-none-any.whl
    └── receipt.json
```

The receipt records `repository`, `commit`, `ref`, `version`, `wheel`,
`wheel_sha256`, and `built_at` (Unix time). It describes a **locally built wheel**;
it is not the published GitHub `deployment-receipt.json`, a signature, or a claim
of byte-for-byte reproducibility with a published artifact. A version alone
cannot identify either build. [Official release verification](installation.md#verify-a-published-wheel).

Installed commit discovery uses canonical Git installation metadata, or an
updater receipt bound to the installed wheel's URL and archive hash. If uv omits
a local archive hash, the checker verifies the retained wheel hash and compares
its contents with installed files, excluding installer-rewritten `RECORD`.
Unrelated receipts and version strings are not source identity. A separately
saved published-release receipt is not automatically imported into this lookup;
missing/unverifiable provenance is reported as **unknown**.

Keep the wheel and matching receipt for the current installation. Deleting them
can lose provenance or make future uv operations depend on a missing file.
Retained artifacts from unsuccessful attempts are not proof that those builds
were installed.

## Troubleshooting and recovery

| Symptom | Action |
|---|---|
| `update` or `atc` is unknown | Use the manual upgrade from a pre-7.1.0 client; check `PATH` and old aliases. |
| No startup notice | Check TTY/output suppression, cache age and the opt-out variable; use `atc update --check` for a fresh explicit result. |
| Offline, GitHub rate limit or metadata error | Normal use remains available; retry the explicit check after connectivity/rate limits recover. Do not treat an error as "current". |
| Editable or non-uv environment refused | Update with its original manager, or your normal development Git workflow plus `uv sync`. |
| Equal-version main build will not advance with stable update | Compare/update with explicit `--main`; stable mode only replaces a lower package version. |
| "Another update may be running" | Wait for the other updater. After a hard interruption, remove only the named `.update-lock` directory **after confirming no update is running**. |
| Fetch/build/version verification fails | Existing installation was not replaced. Inspect the reported error; do not reset a development checkout to repair a temporary build. |
| uv replacement fails | Inspect installed command/version state. Reinstall a known verified wheel or tagged release with uv if needed; no automated rollback is provided. |
| TUI still shows an old version | Exit and restart it. Save/apply only the asset edits you actually intend before closing. |

For manual recovery, retain the prior verified wheel and its source/hash receipt,
then deliberately select that wheel with `uv tool install --from ... agent-toolkit`.
Do not delete asset libraries, reset Git-backed assets, or remove native harness
configuration as a package-repair step.

See also: [Installation](installation.md) · [Shell completion](shell-completion.md) ·
[CLI reference](cli.md) · [Storage](lock-files.md#toolkit-package-state-is-not-an-asset-lock).

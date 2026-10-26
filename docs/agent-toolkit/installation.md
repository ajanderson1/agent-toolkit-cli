# Install and verify Toolkit

Install the **`agent-toolkit` Python package** once to get both the CLI and TUI.
This does not acquire assets, subscribe to a catalogue, or enable any harness
exposure. Those are separate [asset operations](../glossary.md#verb-model).

## Requirements

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/).
- **Git** for installation from source and for package self-updates.
- A terminal for the Textual TUI; this is a local application, not a web server.

The POSIX shell examples below work in Bash or Zsh. Native Pi npm operations
have additional Node/Pi requirements described in the
[Pi extensions guide](../asset-types/pi-extensions.md); they are not required
just to open the Toolkit CLI or TUI.

There is **no configured PyPI publication**. Use the canonical Git repository or
the verified assets on [GitHub Releases](https://github.com/ajanderson1/agent-toolkit-cli/releases),
not an assumed `pip install agent-toolkit` registry release.

## Install the stable release

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.1.0 agent-toolkit
atc --version
att --version
```

The tag selects release **7.1.0**, not the moving development branch. `uv tool`
creates a dedicated environment and exposes these four executables:

| Executable | Equivalent long name | Purpose |
|---|---|---|
| `atc` | `agent-toolkit-cli` | Asset CLI, package updater, completion setup. |
| `att` | `agent-toolkit-tui` | Open the TUI; also accepts `update` and `completion` from the shell. |

The short names are package entry points, **not shell aliases**. No `.zshrc`
edit is required to run them. Completion is an optional, separate
[shell integration](shell-completion.md).

On a fresh uv setup, ensure its executable directory is on `PATH`:

```bash
uv tool dir --bin
uv tool update-shell
```

Open a new terminal after uv changes your shell startup configuration. The usual
POSIX executable directory is `~/.local/bin`, but `uv tool dir --bin` is the
authoritative location for your configuration.

## Upgrade an older Toolkit

Versions before 7.1.0 do not provide the short names, package updater, or
completion utility. Bootstrap those features with the existing package manager:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.1.0 agent-toolkit
agent-toolkit-cli --version
agent-toolkit-tui --version
```

Normal `uv tool install` replaces that tool's existing installation. If uv reports
an executable collision, inspect it rather than automatically overwriting an
unrelated tool with `--force`. An old shell alias/function may also shadow a new
entry point; [check command resolution](#command-not-found-or-wrong-version).

Once on 7.1.0 or later, use:

```bash
atc update --check
atc update
```

Both CLI and TUI update together. Restart an already-running TUI afterward.
Package upgrades do **not** migrate project backing, change subscriptions,
refresh asset repositories, or alter harness exposure. Per-kind migration and
update commands remain explicit. [Full updater behavior](updates.md).

## Verify a published wheel

GitHub releases include a wheel, sdist, `SHA256SUMS`, and
`deployment-receipt.json`. The receipt records the source commit, artifact names,
sizes, hashes, and release smoke results. **A version string alone is not build
identity.**

For the official **7.1.0** release:

| Identity | Value |
|---|---|
| Canonical repository | `https://github.com/ajanderson1/agent-toolkit-cli` |
| Tag | `v7.1.0` |
| Source commit | `4c7196db8764ac1ad3b9b7bc50584c28026d7f41` |
| Wheel | `agent_toolkit-7.1.0-py3-none-any.whl` |
| Wheel SHA-256 | `d9d4cd0308e9c36c75b7b90eea9a08b8c6d971308a8343d339efff69b4564aff` |

For example, download the four assets using the optional
[GitHub CLI](https://cli.github.com/) into a **durable** directory:

```bash
artifacts="${XDG_STATE_HOME:-$HOME/.local/state}/agent-toolkit/releases/v7.1.0/artifacts"
mkdir -p "$artifacts"
gh release download v7.1.0 --repo ajanderson1/agent-toolkit-cli --dir "$artifacts"
cd "$artifacts"
```

Use a fresh directory; do not overwrite previously verified evidence. Check both
archives against the published sums, and inspect the receipt's commit against
the release tag. On macOS:

```bash
shasum -a 256 -c SHA256SUMS
```

On Linux:

```bash
sha256sum -c SHA256SUMS
```

**Stop if verification fails.** After verifying, install the wheel:

```bash
uv tool install --from "$artifacts/agent_toolkit-7.1.0-py3-none-any.whl" agent-toolkit
atc --version
att --version
```

Retain the downloaded wheel, receipt and checksums. uv records its source URL;
a deleted temporary wheel path loses useful provenance and may break later
package-manager operations. A self-update builds a **new local wheel** from a
pinned canonical commit; its hash is not assumed to equal this published wheel.
[Update receipts](updates.md#build-and-installation-provenance) explain the distinction.

## Launch and choose a consumer project

```bash
atc --help
atc --project /path/to/project skills list -p
```

`--project DIRECTORY` selects the CLI's consumer directory; `-p` selects project
**scope** for verbs that support it. Defaults vary by kind and verb; see the
[scope table](cli.md#scope-and-target-selection).

The TUI uses its launch directory, not a CLI `--project` flag:

```bash
cd /path/to/project
att
```

Opening the TUI can fetch an explicitly subscribed catalogue and check for a
package update, but does not acquire advertised assets or apply queued changes.
See [TUI controls and limits](tui.md).

## Development and other package managers

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli
cd agent-toolkit-cli
uv sync --all-extras
uv run atc --help
uv run att
```

An editable checkout is not the global uv tool installation. The package updater
refuses editable and non-`uv tool` environments; use your normal Git workflow and
`uv sync` for development, or the original manager for other installations.
Read-only `update --check` does not require a uv-managed tool environment.

For a deliberate global development build, omit the tag in the Git installation
command, or use `atc update --main` from a supported existing tool installation.
This explicitly opts into unreleased code. Stable releases remain the default.

## Command not found or wrong version

1. Check `uv tool list` and `uv tool dir --bin`.
2. Ensure that directory is on `PATH`, then start a new shell.
3. Run `type -a atc att agent-toolkit-cli agent-toolkit-tui` in Bash/Zsh to find
   old aliases, functions, or another environment earlier on `PATH`.
4. Remove an obsolete alias from your own configuration only after identifying
   it. Toolkit does not automatically delete user-authored aliases.
5. If the installed version is older than 7.1.0, use the one-time upgrade above.
6. Restart a running TUI: replacing its files does not reload its Python process.

Next: [Package updates](updates.md) · [Shell completion](shell-completion.md) ·
[CLI reference](cli.md) · [TUI reference](tui.md).

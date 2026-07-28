# TUI settings schema

The TUI owns one user-level preferences file:

```text
~/.agent-toolkit/tui-settings.json
```

Set `AGENT_TOOLKIT_TUI_SETTINGS` to an absolute path to override that location.
The value must not be empty or whitespace-only; relative and whitespace paths
are rejected with a visible diagnostic and never resolve against the current
working directory. The CLI never reads this file: CLI output and install
targets remain independent of TUI presentation preferences.

## Schema v1

```json
{
  "schema": "agent-toolkit-tui-settings/v1",
  "theme": "gruvbox",
  "harnesses": ["claude-code", "gemini-cli", "codex", "opencode", "pi"]
}
```

| Field | Meaning |
|---|---|
| `schema` | Required marker. The only accepted value is `agent-toolkit-tui-settings/v1`. |
| `theme` | A Textual theme name from the running app's `available_themes`. Defaults to `gruvbox`. |
| `harnesses` | Main harnesses allowed to render standalone columns. An empty list is valid. |

The harness list is a selection over the real `AGENTS` catalog harnesses
(`MAIN_HARNESS_CANDIDATES`). Fresh installs default to today's eight primary
harnesses. Standard columns and their counts are filesystem facts and do not
change. The same selection reaches Skills, Instructions, Agents, MCPs, and
Commands within each asset type's supported set.

Theme selection and harness selection apply directly via the command palette (`ctrl+p`):

- selecting a theme in **Theme** atomically writes it immediately while preserving
  the active main-harness list;
- toggling a harness in **Main harnesses** immediately adds or removes it from your
  selection, saves to disk, and rebuilds every grid;
- if any grid has queued edits, a confirmation prompt asks before discarding them.

Supported v1 writes use a temporary sibling file followed by `os.replace`.
Unknown top-level v1 fields, unknown harness names, and an unavailable persisted
theme survive unrelated saves. Unsupported schemas are read-only until an
explicit migration or reset exists.

## Failure behaviour

| State | Result |
|---|---|
| File missing | `gruvbox` plus every main harness; no notice. |
| Invalid `AGENT_TOOLKIT_TUI_SETTINGS` override | Defaults plus a status-bar notice explaining that an absolute, non-whitespace path is required. |
| Unreadable file | Defaults plus a status-bar notice naming the path and error. |
| Invalid UTF-8, malformed JSON, or invalid field types | Defaults plus a status-bar notice naming the path and reason. |
| Unknown schema | Defaults plus a status-bar notice; no coercion or write until an explicit migration/reset exists. |
| Theme unavailable in the installed Textual version | `gruvbox` plus a notice; the unavailable name is retained on unrelated saves. |
| Unknown top-level v1 field | Retained on later saves. |
| Harness name absent from `MAIN_HARNESS_CANDIDATES` | Ignored for rendering, reported, and retained on later saves. |
| Empty `harnesses` list | Accepted; grids keep their asset, Standard where applicable, State, and Source columns. |

See [TUI reference](tui.md) for the palette workflow. Implementation lives in
`src/agent_toolkit_tui/settings.py` and
`src/agent_toolkit_tui/app.py`.

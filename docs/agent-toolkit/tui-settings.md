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

The harness list is a filter over the curated `MAIN_HARNESSES` tuple; it cannot
add unsupported or long-tail columns. Standard columns and their counts are
filesystem facts and do not change. The same filter reaches Skills,
Instructions, Agents, MCPs, and Commands within each asset type's supported
set.

Theme selection and harness selection have deliberately different commit
boundaries:

- selecting a theme atomically writes it immediately while preserving the last
  committed harness list;
- harness checkboxes remain drafts until **Save**; **Cancel** or **Escape**
  discards only those drafts;
- saving harnesses rebuilds every grid. Existing grid `set_rows()` semantics
  clear pending queues, so apply or revert queued changes first.

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
| Harness name absent from `MAIN_HARNESSES` | Ignored for rendering, reported, and retained on later saves. |
| Empty `harnesses` list | Accepted; grids keep their asset, Standard where applicable, State, and Source columns. |

See [TUI reference](tui.md) for the palette workflow. Implementation lives in
`src/agent_toolkit_tui/settings.py` and
`src/agent_toolkit_tui/screens/settings.py`.

# agent-toolkit asset schema

Every asset carries an `agent_toolkit_cli` metadata block.  For Markdown-based
kinds the block is YAML frontmatter; for JSON-based kinds it lives under the
`agent_toolkit_cli` top-level key.

## Canonical directory layout

| Kind | Path |
|------|------|
| skill | `skills/<slug>/SKILL.md` |
| agent | `agents/<slug>.md` |
| command | `commands/<slug>.md` |
| hook | `hooks/<slug>.meta.yaml` |
| mcp | `mcps/<slug>/README.md` + `mcps/<slug>/config.json` |
| **plugin** | `plugins/<slug>/.claude-plugin/plugin.json` (single-plugin) |
| **plugin** | `plugins/<slug>/.claude-plugin/marketplace.json` (marketplace) |
| pi-extension | `extensions/<slug>/extension.meta.yaml` |

## Plugin example

`plugins/my-plugin/.claude-plugin/plugin.json`:

```json
{
  "agent_toolkit_cli": {
    "apiVersion": "agent-toolkit/v1alpha2",
    "metadata": {
      "name": "my-plugin",
      "description": "One sentence ending with a period.",
      "lifecycle": "experimental"
    },
    "spec": {
      "origin": "first-party",
      "vendored_via": "none",
      "harnesses": ["claude"]
    }
  }
}
```

The walker discovers `plugins/<slug>/.claude-plugin/plugin.json` (or
`marketplace.json` for a multi-plugin distribution) and reads the
`agent_toolkit_cli` block for metadata.  `agent-toolkit new plugin <slug>`
scaffolds this layout automatically.

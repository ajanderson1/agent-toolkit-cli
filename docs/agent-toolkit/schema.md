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

Plugins are Claude-only and metadata lives in a sidecar
`plugins/<slug>.toolkit.yaml` (preferred). The legacy inline form
(`agent_toolkit_cli` JSON key in `plugin.json`) still parses but emits a
deprecation warning during `check`.

`plugins/superpowers.toolkit.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: superpowers
  description: TDD, debugging, brainstorming, plan-writing.
  kind: plugin
  lifecycle: stable
spec:
  origin: third-party
  upstream: https://github.com/anthropics/claude-plugins-official
  vendored_via: none
  harnesses: [claude]
  source:
    marketplace: claude-plugins-official
    marketplaceSource:
      source: git
      url: https://github.com/anthropics/claude-plugins-official.git
    plugin: superpowers
    version: latest
```

### `spec.source` fields

| Field | Type | Notes |
|---|---|---|
| `marketplace` | string | Marketplace identifier (matches the key under `known_marketplaces.json`). |
| `marketplaceSource.source` | enum | One of `git`, `github`, `directory`. |
| `marketplaceSource.url` | string | Required when `source: git`. |
| `marketplaceSource.repo` | string | Required when `source: github` (e.g. `org/name`). |
| `marketplaceSource.path` | string | Required when `source: directory`. Absolute path. |
| `plugin` | string | Plugin slug as advertised by the marketplace. |
| `version` | string | `latest` or a pinned semver. |

The walker discovers `plugins/<slug>.toolkit.yaml` first; if absent, it
falls back to the legacy `plugins/<slug>/.claude-plugin/plugin.json` (or
`marketplace.json`) and reads the inline `agent_toolkit_cli` block.
`agent-toolkit new plugin <slug>` scaffolds the sidecar form automatically.

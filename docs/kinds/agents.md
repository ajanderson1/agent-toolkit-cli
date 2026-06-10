# Agents (subagents)

The `agent` [kind](../glossary.md#kind) manages subagent definitions —
markdown-with-frontmatter descriptions of a delegable assistant — and projects
them into each harness's agent slot.

## How it works

The toolkit keeps one canonical definition and projects it per harness using
the cheapest [mechanism](../glossary.md#mechanism) that harness accepts:

- **symlink** — the harness accepts Claude-compatible markdown unchanged; a
  per-asset symlink into its agents directory is enough.
- **translate** — the harness wants different frontmatter, another filename
  suffix, or a non-markdown format (TOML/JSON); the toolkit generates a
  flavored file in a managed cache and symlinks the slot to it.
- **config_file+folder** — the harness requires an explicit registry entry
  (e.g. Codex's `[agents.<role>]` in `config.toml`) alongside the artefact;
  both surfaces commit and roll back together.
- **dual-symlink** — two slot directories mirror the same source (Pi).

## Support across harnesses

Per the [compatibility matrix](../matrix.md): **28 supported** · 11 gaps ·
10 not applicable · 5 unknown. The supported set splits 14 symlink ·
9 translate · 4 registry · 1 dual-symlink. Two verdict-supported cells
([Codex](../harnesses/codex.md), [Firebender](../harnesses/firebender.md))
are currently disabled in the toolkit because their mechanism would mutate a
shared config file — each harness page shows its live adapter status.

## CLI

```bash
agent-toolkit-cli agent add <source>
agent-toolkit-cli agent install
agent-toolkit-cli agent uninstall        # non-destructive (canonical kept)
agent-toolkit-cli agent remove           # destructive (canonical deleted)
```

See also: [Skills](skills.md) · [Instructions](instructions.md) ·
[Glossary](../glossary.md)

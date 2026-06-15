# Pi extensions

The `pi-extension` [asset type](../glossary.md#asset-type) manages extension packages for
[Pi](../harnesses/pi.md) — the only harness with an extension-package concept,
which is why this column of the [compatibility matrix](../matrix.md) has a
single ✅.

## How it works

Extensions are git-sourced and cloned into the library, then
[projected](../glossary.md#projection) by symlink into Pi's extension
directory. Sources can be pinned to a branch or to an exact commit SHA — a
SHA-pinned add lands on that commit and stays there until you re-pin.

- **Lock file:** records repo, subpath, `ref`/SHA pin, and resolved commit
- **Doctor:** detects missing or foreign symlinks and drifted pins

## CLI

```bash
agent-toolkit-cli pi-extension add <source>[@ref-or-sha]
agent-toolkit-cli pi-extension list
agent-toolkit-cli pi-extension update
agent-toolkit-cli pi-extension doctor
```

See also: [Skills](skills.md) · [Agents](agents.md) ·
[Glossary](../glossary.md)

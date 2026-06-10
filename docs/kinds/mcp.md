# MCP servers (planned)

A placeholder [kind](../glossary.md#kind): managing MCP (Model Context
Protocol) server registrations across harnesses is on the
[roadmap](../agent-toolkit/roadmap.md) but not yet implemented — the
[compatibility matrix](../matrix.md) shows an empty column until it lands.

The shape will follow the other kinds: one canonical definition, a lock file,
and per-harness [projection](../glossary.md#projection) into whatever
registration surface each harness exposes (typically a JSON/TOML config
entry, which puts most cells in
[config_file](../glossary.md#mechanism) territory).

See also: [Skills](skills.md) · [Agents](agents.md) ·
[Glossary](../glossary.md)

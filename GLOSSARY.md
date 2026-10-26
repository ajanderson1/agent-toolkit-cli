# Glossary

Authoritative product vocabulary for agent-toolkit-cli and its TUI. Read this
before discussing, documenting or changing asset lifecycle behavior. The
[public glossary](docs/glossary.md) adds storage and adapter detail; the
[CLI reference](docs/agent-toolkit/cli.md) records exact shipped command syntax.
This is current terminology, not the superseded issue #538 lifecycle proposal.

## Lifecycle vocabulary

| Term | Meaning |
|---|---|
| **Library** | The user's global collection of registered assets and their backing sources. Library membership is separate from harness exposure. |
| **Add** | Add an asset to the global library; for source-backed assets this normally obtains content and records its source. Adding does not itself enable harness exposure. |
| **Remove** | Remove an asset from the global library, subject to kind-specific ownership, reference and local-work guards. This can delete backing content; it is not how to disable an asset. |
| **Enable** | Make an asset available through selected supported harness targets in the global or project scope. |
| **Disable** | Retract selected harness exposure while retaining the library source and local work. |
| **Update** | Refresh from the recorded source using the asset type's supported behavior. Git-backed Skills, Agents and Pi extensions fetch and merge; this is not automatic activation or a destructive reset. |
| **Push** | Publish owned source changes through the supported workflow, normally a PR. |
| **Reset** | Explicitly synchronize supported Git backing to upstream; it can discard local work and is not a synonym for repairing exposure. |
| **Projection** | The actual harness-visible link, translated file, pointer or configuration entry used to expose an asset. |
| **Effective availability** | What a harness can discover through all applicable global, project and native routes. |

**Use add/remove for global library membership and enable/disable for harness
exposure in explanations and product discussions.** Do not call these exposure
operations install/uninstall merely because those are current command names.

### Current command spellings and exceptions

Terminology does not imply every CLI group already has `enable`/`disable` verbs.
Source-backed Skills, Agents, Commands and Git Pi extensions currently spell
projection operations `install`/`uninstall`. Use those exact tokens in runnable
examples, identifying their effect as enabling/disabling exposure. A CLI rename
or compatibility-alias change is separate work, not something this glossary ships.

Do not assume every asset type implements the same lifecycle:

- **Instructions:** no source-library membership or installation lock. User-owned
  canonical content is exposed through pointers; removing pointers preserves it.
- **MCP:** `add` authors a global library manifest entry, but the current `remove`
  command retracts scoped projections and **retains library membership/files**.
  Describe that actual effect; do not claim it removes an MCP from the library.
- **Native Pi npm packages:** Pi settings and npm metadata are authoritative;
  there is no Toolkit npm library registry. Current `add`/`install` downloads and
  configures a package and may activate resources; `remove`/`uninstall` removes
  the scoped installation/declaration. `enable`/`disable` changes extension filters
  without deleting files. Keep package installation distinct from enablement.
- **Bundles:** an installation utility with `install`/`validate`, not another
  asset type or library membership model.

## Core terms

| Term | Definition |
|---|---|
| Asset | One skill, agent definition, command, canonical instruction file, Pi extension or MCP server registration. |
| Asset type / kind | One of those six categories; kind is internal shorthand. |
| Harness | A coding assistant that can discover/load supported assets; catalog presence does not prove adapter support. |
| Inventory | Known or discovered assets within the locations Toolkit inspected. Presence in inventory does not imply management or enablement. |
| Discovery | Read-only inspection of records, content and harness configuration. It does not add, enable or adopt assets. |
| Origin | Where an inventory item comes from: `library` for Toolkit library content, `local` for discovered local content, `npm` for native Pi/npm packages, or `catalog` for an unacquired shared-catalogue entry. Not a visibility scope or proof of enablement. |
| Source | The recorded origin used to identify or obtain content or a server definition. |
| Canonical | Authoritative asset content to which projections refer; not a separate copy per harness. |
| Collection | A derived source/ref group of real skill children, not an extra skill, asset type or lock entry. |
| Ref | A requested Git branch, tag or commit; distinct from the observed upstream SHA. |
| Shared checkout | One Git working tree containing content for multiple assets. Referenced history and local work are not disposable cache data. |
| Local copy | One physical content tree; aliases to it are not additional copies. |
| Global scope | User-level harness exposure, separate from each project's exposure. Not a synonym for library membership. |
| Project scope | One consumer project's harness exposure, regardless of where backing files live. New project installations share central library backing by default; recorded legacy private backing remains supported. |
| Profile | A harness-specific context, not an additional Toolkit scope. |
| Standard | An asset-specific shared projection slot and its verified reader set, not another harness. The CLI token is `standard`, not `general` or `universal`. |
| Managed | Toolkit has verified the identity and records needed for supported operations. This alone does not authorize deletion or publishing. |
| Local changes | Staged, unstaged or untracked changes in the selected asset's content. |
| Unpublished commits | Local commits not proven reachable from the relevant upstream; clean files do not prove publication. |
| Health | Whether required content, records and exposure are readable, consistent and usable. |
| Doctor | Kind-specific diagnosis, with only supported, explicitly authorized repairs. It does not automatically add discovered local assets to the library. |

## Essential distinctions

- **In the library does not mean enabled for any harness.**
- **Visible in Toolkit does not mean enabled or loaded by an agent.**
- **Disabled in a project does not mean unavailable through global/native routes.**
- **Disable is not unload:** a running agent may retain previously loaded content.
- **Remove is not disable:** removing library content can affect consumers sharing it.
- **A lock entry does not prove the content or projection exists.** Instructions
  has no installation lock; native Pi npm uses its own settings/metadata.
- **One upstream source can have distinct local copies.** Do not merge or delete
  them merely because names, URLs, refs or current bytes match.
- **Unlinking a symlink preserves its target; deleting content does not.**

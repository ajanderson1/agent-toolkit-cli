# Glossary

Target vocabulary for [issue #538](https://github.com/ajanderson1/agent-toolkit-cli/issues/538).
This planning document does not claim the proposed commands already ship.
Definitions describe the intended product; implementation and compatibility are
specified in [the design](docs/specs/2026-10-17-538-asset-lifecycle.md).

| Term | Definition |
|---|---|
| Asset | One skill, agent definition, command, instruction source, Pi extension, or MCP server definition. |
| Asset type | One of those six categories. Bundles group operations; they are not another asset type. |
| Harness | A coding assistant that can discover or load supported assets. |
| Inventory | All known or discovered assets within the locations Toolkit inspected. |
| Discovery | Read-only inspection of records, content, and harness configuration to find assets and problems. |
| Scan coverage | Locations inspected, skipped, inaccessible, or excluded during discovery. |
| Source | The origin used to identify or obtain content or a server definition. |
| Collection | Related skills grouped by source and ref; its heading is not an extra skill. |
| Ref | A requested Git branch, tag, or commit; distinct from the currently checked-out commit. |
| Local copy | One physical content tree; aliases to that tree are not additional copies. |
| Shared checkout | One Git working tree containing content for multiple assets. |
| Storage unit | An independently selectable owned checkout, content copy, or definition record; never a synthetic collection heading. |
| Global | The current user's scope, separate from every project's scope. |
| Project | One identified project's scope, regardless of where its backing files are stored. |
| Profile | A harness-specific context within a scope, not an additional Toolkit scope. |
| Discovered | Observed content or configuration not yet under verified Toolkit management. |
| Managed | Toolkit has verified the identity and records needed for supported lifecycle operations. |
| Ownership | Evidence permitting a particular change; management alone does not authorize deleting or publishing content. |
| Add source | Obtain or register content in the chosen scope without enabling it. |
| Manage | Adopt existing content into Toolkit management without changing its content or exposure. |
| Enable | Make an asset discoverable through selected supported harness targets in one scope. |
| Disable | Remove selected scoped exposure, preserving source content and local work. |
| Effective availability | What a harness can discover through all applicable project and global routes. |
| Projection | A harness-visible link, translated file, pointer, or configuration entry. |
| Standard | An asset-specific shared target read by a verified set of harnesses; not an extra harness. |
| Local changes | Staged, unstaged, or untracked changes within the selected asset's content. |
| Unpublished commits | Local commits not proven reachable from the relevant upstream; clean files do not prove publication. |
| Health | Whether required content, records, and exposure are readable, consistent, and usable. |
| Preview changes | Inspect proposed Toolkit operations before applying them. |
| Reviewed plan | Exact proposed effects and expected resource state; conditional Apply refuses changed targets rather than replanning. |
| Unmanage | Release Toolkit management records while preserving content; residual discovered content remains visible. |
| Delete local copy | Explicitly remove owned stored content after reference, ownership, and local-work safety checks. |
| Doctor | Diagnose inventory and lifecycle problems; apply only supported, explicitly authorized repairs. |
| Finding | A diagnosed condition with evidence, severity, and a repair or clear reason repair is unavailable. |
| Repair | An explicit, guarded action correcting a finding without silently changing scope or discarding work. |
| Recovery | Account for and safely resolve an interrupted operation using recorded evidence and current ownership. |
| Library | Legacy/internal storage terminology, never a third scope or synonym for globally enabled. |

## Essential distinctions

- **Visible in Toolkit does not mean enabled for an agent.**
- **Disabled in this project does not mean unavailable globally.**
- **Managed does not mean safe to delete, publish, or execute.**
- **A recorded source does not prove a local copy exists.**
- **Disable is not unload:** a running agent may retain previously loaded content.
- **One source can have several different local copies.** Never merge them merely
  because their names, URLs, refs, or current contents match.
- **Deletion is not hiding:** anything left on disk remains discoverable.

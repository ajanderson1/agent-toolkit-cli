# Spec — mkdocs-redirects for `kinds/` → `asset-types/` URL moves (#364)

**Tier:** light. One semantic file edit (`mkdocs.yml`) plus the mechanical
dependency-add artifacts (`pyproject.toml`, `uv.lock`) from a single
`uv add --group docs`. No critical review.

## Problem

PR #363 (the #355 kind→asset-type rename) git-mv'd the five compatibility pages
`docs/kinds/{instructions,skills,agents,pi-extensions,mcp}.md` →
`docs/asset-types/…` with no redirect mapping. `mkdocs.yml` declares
`site_url: https://ajanderson1.github.io/agent-toolkit-cli/` but its plugin list
is only `search` + `mkdocstrings`. Once the site deploys at the new paths, any
inbound link to `…/kinds/<page>/` 404s — old GitHub issues/PRs, the historical
dated specs/plans that cite `docs/kinds/` paths (the #355 spec/plan themselves),
and any bookmarks. #355 ruled redirect plumbing out of scope on the premise "site
unpublished; no external URLs to preserve"; PM review of #363 overrides that —
inbound links from the repo's own durable record are worth preserving.

## Solution

Add the **`mkdocs-redirects`** plugin to the `docs` dependency-group and register
a five-entry `redirect_maps` block in `mkdocs.yml`. The plugin generates a tiny
meta-refresh HTML stub at each old path that bounces the browser to the new page.

### Dependency placement

The repo's convention is the `[dependency-groups] docs` group (where
`mkdocs-material` + `mkdocstrings` already live), **not** a bare `--dev`. Add via:

```
uv add --group docs mkdocs-redirects
```

This updates `pyproject.toml` (`docs = [...]`) and `uv.lock` together — both are
mechanical artifacts of the one command, not separate semantic edits.

### `mkdocs.yml` plugins block

Append `redirects` to the existing `plugins:` list (which currently holds `search`
and `mkdocstrings`). The redirect source/target keys use the on-disk markdown
paths relative to `docs/`:

```yaml
plugins:
  - search
  - mkdocstrings:
      enabled: !ENV [ENABLE_MKDOCSTRINGS, true]
      handlers: …            # unchanged
  - redirects:
      redirect_maps:
        kinds/instructions.md: asset-types/instructions.md
        kinds/skills.md: asset-types/skills.md
        kinds/agents.md: asset-types/agents.md
        kinds/pi-extensions.md: asset-types/pi-extensions.md
        kinds/mcp.md: asset-types/mcp.md
```

The `plugins:` block sits well away from the `# BEGIN/END GENERATED HARNESS NAV`
markers in `nav:`, so `scripts/gen_harness_docs.py` never touches it — no
collision.

### Strict-build compatibility

`mkdocs.yml` sets `strict: true` at the top level, so every build is strict.
`mkdocs-redirects` is strict-clean: it emits redirect stubs in a post-build hook;
the source `kinds/*.md` files do not exist as real pages, which is exactly what
`redirect_maps` expects (the key is a *deleted* path, the value an existing one).
The build must complete with no warnings-as-errors. This is the one thing to
verify (test surface below).

## Acceptance criteria

1. `mkdocs-redirects` is listed in `pyproject.toml`'s `docs` dependency-group and
   pinned in `uv.lock`.
2. `mkdocs.yml` `plugins:` contains a `redirects:` entry with a `redirect_maps`
   block mapping all five `kinds/<page>.md` → `asset-types/<page>.md`.
3. `uv run mkdocs build` (strict, per `strict: true`) completes successfully with
   no warnings-as-errors, and the built site contains a redirect stub at each of
   the five `site/kinds/<page>/index.html` locations pointing at the new path.
4. No change to any page *content*, the `nav:`, or the GENERATED HARNESS NAV block.

## Out of scope (resolved)

- **Glossary `#kind` anchor.** `docs/glossary.md` already keeps a
  `**Kind** { #kind }` pointer entry ("Former name for asset type", links to
  `#asset-type`), so inbound `glossary.md#kind` links still resolve on the
  published site. `mkdocs-redirects` cannot redirect anchors anyway. No coverage
  needed — confirmed against the file, not assumed.
- Publishing/CI: no GitHub Pages deploy workflow exists yet; this issue only makes
  the redirect mapping correct *for when* the site deploys. Adding a deploy
  workflow is separate work.

## Links

- Issue: #364
- Origin: PR #363 (#355 kind→asset-type rename), which moved the pages.
- mkdocs-redirects: https://github.com/mkdocs/mkdocs-redirects

# Plan — mkdocs-redirects for `kinds/` → `asset-types/` (#364)

**Tier:** light. Spec:
`docs/superpowers/specs/2026-06-12-mkdocs-redirects-kinds-asset-types-design.md`.

Files:
- `pyproject.toml` — add `mkdocs-redirects` to the `docs` dependency-group.
- `uv.lock` — pinned by the same `uv add` (mechanical).
- `mkdocs.yml` — append the `redirects:` plugin with `redirect_maps`.

No source code, no tests directory change. Verification is a strict `mkdocs build`
plus a stub-existence check (AC3).

## Step 1 — RED: prove the redirect stubs are absent today

Before any edit, build the site and confirm the old paths produce no redirect
stub (so the green check is meaningful):

```
uv run mkdocs build --clean
test ! -f site/kinds/instructions/index.html && echo "RED: no stub (expected)"
```

Expect: `site/kinds/*` does not exist — the rename left no trace at the old URLs.
This is the failing baseline AC3 will flip to green.

## Step 2 — add the dependency

```
uv add --group docs mkdocs-redirects
```

Confirm `pyproject.toml` `docs = [...]` now lists `mkdocs-redirects` and `uv.lock`
gained the package (AC1). Do not hand-edit the lock; let `uv` own it. If `uv add`
churns unrelated lock entries, keep only the `mkdocs-redirects` addition is not
required — a clean `uv add` against an up-to-date lock should be minimal; review
the `uv.lock` diff and revert any spurious unrelated rewrites if they appear.

## Step 3 — register the plugin in `mkdocs.yml`

Append to the existing `plugins:` list (after the `mkdocstrings:` block), exactly
the five-entry `redirect_maps` from the spec. Touch nothing else — not `nav:`, not
the GENERATED HARNESS NAV markers, not page content (AC2, AC4).

## Step 4 — GREEN: strict build + stub presence

```
uv run mkdocs build --clean
```

Must exit 0 with no warnings-as-errors (the file's `strict: true` makes every
build strict). Then assert all five redirect stubs exist and point at the new
paths (AC3):

```
for p in instructions skills agents pi-extensions mcp; do
  f="site/kinds/$p/index.html"
  test -f "$f" || { echo "MISSING stub: $f"; exit 1; }
  grep -q "asset-types/$p/" "$f" || { echo "stub does not target asset-types/$p: $f"; exit 1; }
done
echo "GREEN: all five redirect stubs present and targeting asset-types/"
```

## Step 5 — clean up + verify scope

`rm -rf site/` (build artifact, gitignored — confirm it is, else don't commit it).
`git status` must show only `pyproject.toml`, `uv.lock`, `mkdocs.yml` staged. The
pre-existing `skills-lock.json` working-tree change predates this issue — leave it
out of the commit.

## Test surface

- Strict `mkdocs build` is the gate (AC3). No unit tests — this is a docs-config
  change; the build *is* the test. Run it locally per `ci.md` local-first.
- No CI workflow runs `mkdocs build` today, so the local strict build is the only
  verification. Note that in the PR so a reviewer knows it was run, not assumed.

## Risks

- `mkdocs-redirects` could pull a transitive dep that conflicts with the pinned
  `mkdocs 1.6.1` / `mkdocs-material 9.7.6`. The `uv add` will fail loudly if so;
  if it does, raise rather than force a resolution.
- Strict mode treats redirect-target validation: if a `redirect_maps` *value*
  names a non-existent page, the build errors. All five targets exist
  (`docs/asset-types/*.md` confirmed present), so this should pass first try.

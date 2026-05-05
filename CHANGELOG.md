# Changelog

## [0.3.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.2.0...v0.3.0) (2026-05-05)


### Features

* **adapters:** codex ConfigFileAdapter — manage by name via previously_allowed (no markers) ([8f2fb3c](https://github.com/ajanderson1/agent-toolkit-cli/commit/8f2fb3c8f4c3dc8ba9e217e10526232331e38b70))
* **adapters:** codex ConfigFileAdapter — tomlkit round-trip, AC[#1](https://github.com/ajanderson1/agent-toolkit-cli/issues/1)-3,8 ([b4d8198](https://github.com/ajanderson1/agent-toolkit-cli/commit/b4d8198a9969a8d2d578bf692909b69a4cfd6e6b))
* **adapters:** scaffold harness_adapters package + base Protocols + registry ([fd4a93e](https://github.com/ajanderson1/agent-toolkit-cli/commit/fd4a93eeea4bcdae004dec72bace5cbd5481020e))
* **doctor,link:** warn when target harness home is missing ([#22](https://github.com/ajanderson1/agent-toolkit-cli/issues/22)) ([c427dfd](https://github.com/ajanderson1/agent-toolkit-cli/commit/c427dfde70266d6ac8824f07c4404d7b76cbf1c4))
* **doctor:** add mcps group — drift, env, prereq, optional verify ([ac09732](https://github.com/ajanderson1/agent-toolkit-cli/commit/ac0973276eb295761a0e41b5cf9c444da8e9287f))
* **doctor:** audit allow-list rot and cross-toolkit symlinks ([#23](https://github.com/ajanderson1/agent-toolkit-cli/issues/23)) ([cc1dfa9](https://github.com/ajanderson1/agent-toolkit-cli/commit/cc1dfa9e3a1a938ae80e50e38f6768935f222d4d))
* **fix:** reconcile MCP drift via apply_link (preserves AGENTS.md regen) ([c2438d6](https://github.com/ajanderson1/agent-toolkit-cli/commit/c2438d6da250a81b3c052fe6d3eed86c3bc7db66))
* **list:** accept --project DIR for symmetry with link/unlink/diff ([#20](https://github.com/ajanderson1/agent-toolkit-cli/issues/20)) ([9234d50](https://github.com/ajanderson1/agent-toolkit-cli/commit/9234d500acf877d69c3426ee0a7740c8245aa3d2))
* **list:** add --report for grouped human-readable inventory ([#25](https://github.com/ajanderson1/agent-toolkit-cli/issues/25)) ([ac94326](https://github.com/ajanderson1/agent-toolkit-cli/commit/ac94326abd77f7f159ae5b06ea578582d18f5caa))
* **list:** replace MCP unsupported overload with four-glyph status ([08134e1](https://github.com/ajanderson1/agent-toolkit-cli/commit/08134e1fca3dfb969ad636a0c075587f8ccf25bd))
* **mcp:** codex adapter, four-glyph list, doctor/fix MCP support ([#29](https://github.com/ajanderson1/agent-toolkit-cli/issues/29)) ([e06dc1c](https://github.com/ajanderson1/agent-toolkit-cli/commit/e06dc1c704d17787b554fb3c6024ff4322761ede))
* **mcp:** dispatcher — apply_link with previously_allowed, atomic write, loud-print ([c68e11d](https://github.com/ajanderson1/agent-toolkit-cli/commit/c68e11da0a6c8ab7e934b32f2cf5d62b53ea43a7))
* **mcp:** foundations — allow-list, walker, projection no-op (Plan A) ([#28](https://github.com/ajanderson1/agent-toolkit-cli/issues/28)) ([d44a98f](https://github.com/ajanderson1/agent-toolkit-cli/commit/d44a98fd51f5a0eeaea3c50e6dd74923a332d728))
* **mcp:** wire link/unlink/all/plan through harness adapter via apply_link ([ffd159d](https://github.com/ajanderson1/agent-toolkit-cli/commit/ffd159ddab326febbd8c3c635d0192fd2bb5422b))
* **pi-extension:** add pi-extension as first-class asset kind ([#27](https://github.com/ajanderson1/agent-toolkit-cli/issues/27)) ([81f7adb](https://github.com/ajanderson1/agent-toolkit-cli/commit/81f7adbac3aba53d32bccfa01f751950e602a0bc))
* **schema:** add v1alpha2 schema (parallel to v1alpha1) ([24aaa59](https://github.com/ajanderson1/agent-toolkit-cli/commit/24aaa596200bb5d3bba1cd356307788fbb77f6d4))
* **schema:** replace v1alpha1 with v1alpha2; cross-check kind; require spec.mcp for mcps; new mcp scaffold ([bb768dd](https://github.com/ajanderson1/agent-toolkit-cli/commit/bb768dd7fce1d773323c068dbdb6ddaab1c43da9))
* **tui:** add 'a' key to select/deselect all visible rows in a column ([3bb5391](https://github.com/ajanderson1/agent-toolkit-cli/commit/3bb5391753bbf8681b3f38539180d8ba061c0c96))
* **tui:** add filter bar, drop harness checkboxes, default scope to project ([e571434](https://github.com/ajanderson1/agent-toolkit-cli/commit/e5714343330b8d6d07de6c98d54be0a720295244))
* **tui:** unicode checkbox glyphs + ctrl+z revert pending ([52fe291](https://github.com/ajanderson1/agent-toolkit-cli/commit/52fe2919272ad3047ace15d45937df681882a5d2))


### Bug Fixes

* **mcp-dispatch:** use explicit utf-8 encoding when reading config.json ([2e76204](https://github.com/ajanderson1/agent-toolkit-cli/commit/2e762043783ed91eeabc83a9bdd814d9245a4e82))
* **tui:** _toggle_at must skip installed-not-allowlisted cells (consistency) ([7c238f4](https://github.com/ajanderson1/agent-toolkit-cli/commit/7c238f44003dfbbf1918a426bf79cec478fc584c))


### Documentation

* **adapters:** clarify entry_drift absent-entry contract and diff ownership rule ([aa89777](https://github.com/ajanderson1/agent-toolkit-cli/commit/aa897776b39589c196a68870f9c83dc3f52cf832))
* **mcp:** document codex adapter, four-glyph list, doctor/fix --harness ([7cd9b58](https://github.com/ajanderson1/agent-toolkit-cli/commit/7cd9b58594216ecab5374b63276fc9fa2f7be0cb))
* **superpowers:** MCP adapters design (Plan B) ([8f4c51f](https://github.com/ajanderson1/agent-toolkit-cli/commit/8f4c51f2c5b2ceaed73357f5f6e45148bfeea8ba))
* **superpowers:** MCP adapters implementation plan (Codex proof + full wiring) ([25b50f5](https://github.com/ajanderson1/agent-toolkit-cli/commit/25b50f5a01b56fa8c4c72cf5ce2d55ce705127ec))
* **superpowers:** patch MCP adapters spec per review ([6539383](https://github.com/ajanderson1/agent-toolkit-cli/commit/6539383390ca422cb2486bdfbf320457a896353d))
* sweep stale v1alpha1 references in AGENTS.md, cli.md ([9b38c18](https://github.com/ajanderson1/agent-toolkit-cli/commit/9b38c18e0e9be38e51e3dd647966196c2836f8aa))

## [0.2.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.1.0...v0.2.0) (2026-05-03)


### Features

* **cli:** reject unknown harness in link and unlink ([#15](https://github.com/ajanderson1/agent-toolkit-cli/issues/15)) ([c174070](https://github.com/ajanderson1/agent-toolkit-cli/commit/c174070f0db07cddbd91bb4d4a418b76fab1a8f0))
* **cli:** unify CLI — port bash subcommands (link/unlink/list/diff) to Python ([#5](https://github.com/ajanderson1/agent-toolkit-cli/issues/5)) ([82ce6fb](https://github.com/ajanderson1/agent-toolkit-cli/commit/82ce6fbbd2b089ff5d979e440aee1eb768cef06a))
* **doctor:** add duplicates group — flag (kind, slug) collisions ([80d8aa9](https://github.com/ajanderson1/agent-toolkit-cli/commit/80d8aa9948a2549148c7a09d0e1298c9bbad1f98))


### Bug Fixes

* **cli:** subcommands honour the four-step toolkit-repo resolver, not just CWD ([929e5ad](https://github.com/ajanderson1/agent-toolkit-cli/commit/929e5ad5074ecb757615da4840e2615c89b843fb))
* **tui:** escape [x] so Rich doesn't swallow linked-cell glyph ([#3](https://github.com/ajanderson1/agent-toolkit-cli/issues/3)) ([294cf88](https://github.com/ajanderson1/agent-toolkit-cli/commit/294cf883e83ee9446efa9056f52cd6fcfa1b202a))
* **tui:** give HarnessPicker labels auto width so scope/harness controls render ([#4](https://github.com/ajanderson1/agent-toolkit-cli/issues/4)) ([15a9ea9](https://github.com/ajanderson1/agent-toolkit-cli/commit/15a9ea91504abdb1240a99b9b522e87733d8990c))
* **tui:** locate bin/agent-toolkit from this CLI's source tree ([9e15d8b](https://github.com/ajanderson1/agent-toolkit-cli/commit/9e15d8bd7bf4beaa7baae27beda121e72c4aee95))


### Documentation

* **cli:** disambiguate `list` (bash, project-scoped) vs `inventory` (python, library-scoped) ([7517f4c](https://github.com/ajanderson1/agent-toolkit-cli/commit/7517f4ca6ea0caf257619b53ea130402ea0bb722))


### CI

* drop install-smoke (cross-repo private checkout not viable without PAT) ([bc7af3a](https://github.com/ajanderson1/agent-toolkit-cli/commit/bc7af3ab28fe1362070eb6ad1faf50bcb79a7b5b))
* start versioning with release-please ([#14](https://github.com/ajanderson1/agent-toolkit-cli/issues/14)) ([0a76c10](https://github.com/ajanderson1/agent-toolkit-cli/commit/0a76c1080d53c861ed89370213eeb7b888a6bbfc))

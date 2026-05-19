# Changelog

## [0.5.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.5.0...v0.5.1) (2026-05-19)


### Bug Fixes

* **#97:** translate (gemini, agent) — slot filename + strip wrapper ([#100](https://github.com/ajanderson1/agent-toolkit-cli/issues/100)) ([e7333c6](https://github.com/ajanderson1/agent-toolkit-cli/commit/e7333c6b833d29b0067a7580c1875c1d5e11fd85))
* **tui:** scope toggle — clearer paired styling and working mouse click ([#102](https://github.com/ajanderson1/agent-toolkit-cli/issues/102)) ([367829a](https://github.com/ajanderson1/agent-toolkit-cli/commit/367829a8431c187ce9be47013cc4191f34378d2e))

## [0.5.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.4.0...v0.5.0) (2026-05-19)


### Features

* **#53:** add Gemini CLI as fifth supported harness ([#95](https://github.com/ajanderson1/agent-toolkit-cli/issues/95)) ([f9ec4d5](https://github.com/ajanderson1/agent-toolkit-cli/commit/f9ec4d5c16ef675a2cc92e8fa086afbd6a37ec15))
* **#55:** config_file MCP adapters for Claude and OpenCode ([#70](https://github.com/ajanderson1/agent-toolkit-cli/issues/70)) ([3450efd](https://github.com/ajanderson1/agent-toolkit-cli/commit/3450efdc464653a8f367001aeb18233f219c5e18))
* **#56:** Codex config_file+folder hook adapter ([#76](https://github.com/ajanderson1/agent-toolkit-cli/issues/76)) ([af1dc30](https://github.com/ajanderson1/agent-toolkit-cli/commit/af1dc3012ddd126e98b29415866c1391e29d37f0))
* **#74:** codex MCP adapter supports HTTP transport ([#83](https://github.com/ajanderson1/agent-toolkit-cli/issues/83)) ([6f6035e](https://github.com/ajanderson1/agent-toolkit-cli/commit/6f6035eb97c43a733322d5a5688599f6169a1931))
* **#75:** dual-write pi/agent symlinks at both legacy and new paths ([#84](https://github.com/ajanderson1/agent-toolkit-cli/issues/84)) ([4622ab2](https://github.com/ajanderson1/agent-toolkit-cli/commit/4622ab2cbdfbc1654d66d5a1347d6cda9b9a7579))
* **#85:** single 's' toggle for scope; chip clicks already wired ([#88](https://github.com/ajanderson1/agent-toolkit-cli/issues/88)) ([7bcc07a](https://github.com/ajanderson1/agent-toolkit-cli/commit/7bcc07a18e0feeb163b5b8e5b83b0348b9574b10))
* **#86:** visual indicator on project-scope view when asset linked at user scope ([#91](https://github.com/ajanderson1/agent-toolkit-cli/issues/91)) ([f44cba8](https://github.com/ajanderson1/agent-toolkit-cli/commit/f44cba801cc9125ae42bb529bd581b17d0d903b6))


### Bug Fixes

* **#72:** ingest reads .claude-plugin/plugin.json + embedded agent_toolkit block ([#81](https://github.com/ajanderson1/agent-toolkit-cli/issues/81)) ([8a4bc6e](https://github.com/ajanderson1/agent-toolkit-cli/commit/8a4bc6ebb1cff5966ffce98b6b39f18ebcff134f))
* **#82:** link claude command/agent slots with .md suffix ([#92](https://github.com/ajanderson1/agent-toolkit-cli/issues/92)) ([8661034](https://github.com/ajanderson1/agent-toolkit-cli/commit/8661034e9413a72d0c5b539febc5aa49749982d4))
* **#87:** preserve list scroll position when toggling an asset ([#89](https://github.com/ajanderson1/agent-toolkit-cli/issues/89)) ([a47c344](https://github.com/ajanderson1/agent-toolkit-cli/commit/a47c344c5b17d0b2c1610588a239c4cbde3b179a))
* **tui:** use four-step toolkit-repo resolution when --toolkit-repo omitted ([#79](https://github.com/ajanderson1/agent-toolkit-cli/issues/79)) ([9b370f4](https://github.com/ajanderson1/agent-toolkit-cli/commit/9b370f4916078669d491d81546c4b2e037caa388))


### Refactors

* **#93:** rename _translated_slot_filename to _slot_filename ([#94](https://github.com/ajanderson1/agent-toolkit-cli/issues/94)) ([c59833f](https://github.com/ajanderson1/agent-toolkit-cli/commit/c59833fa1c3cb3ff4ce3074862e48edbdaf62b6b))
* rename top-level package agent_toolkit -&gt; agent_toolkit_cli ([#77](https://github.com/ajanderson1/agent-toolkit-cli/issues/77)) ([60c81cf](https://github.com/ajanderson1/agent-toolkit-cli/commit/60c81cf015252745740696e3d5116313c74c8a04))


### Documentation

* **#54:** final leftovers — opencode.json typo + stale [#32](https://github.com/ajanderson1/agent-toolkit-cli/issues/32) pointer ([#80](https://github.com/ajanderson1/agent-toolkit-cli/issues/80)) ([4edf6e8](https://github.com/ajanderson1/agent-toolkit-cli/commit/4edf6e881d0256a0542af1985a60027c86be7265))
* **harness-matrix:** correct stale rows from late-2025/early-2026 harness changes ([#73](https://github.com/ajanderson1/agent-toolkit-cli/issues/73)) ([f682a40](https://github.com/ajanderson1/agent-toolkit-cli/commit/f682a40ffdca22aa9c8dc66ede4986621b003f51))
* **matrix:** correct plugin_folder prose — currently unused ([#96](https://github.com/ajanderson1/agent-toolkit-cli/issues/96)) ([b21e237](https://github.com/ajanderson1/agent-toolkit-cli/commit/b21e237f582ce69e952f721c2b420040c1763d5a))

## [0.4.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.3.0...v0.4.0) (2026-05-05)


### Features

* **#40-B:** extend translate machinery for directory-slot kinds ([#45](https://github.com/ajanderson1/agent-toolkit-cli/issues/45)) ([cfa7c0e](https://github.com/ajanderson1/agent-toolkit-cli/commit/cfa7c0ed3c056767dae335224472098f2b0e161f)), closes [#40](https://github.com/ajanderson1/agent-toolkit-cli/issues/40)
* **#40-C:** codex skill translator — top-level description for native loader ([#46](https://github.com/ajanderson1/agent-toolkit-cli/issues/46)) ([f884cb8](https://github.com/ajanderson1/agent-toolkit-cli/commit/f884cb884b2e9ca7b6e2f71555f9d48b850fd57f)), closes [#40](https://github.com/ajanderson1/agent-toolkit-cli/issues/40)
* **#59:** make scope chips mouse-clickable ([#60](https://github.com/ajanderson1/agent-toolkit-cli/issues/60)) ([77c40c0](https://github.com/ajanderson1/agent-toolkit-cli/commit/77c40c0623d9eebcf56a844ee1fb7771f46f6d97))
* **linker:** enforce spec.requires at link time ([#35](https://github.com/ajanderson1/agent-toolkit-cli/issues/35)) ([9aa661a](https://github.com/ajanderson1/agent-toolkit-cli/commit/9aa661a77142177786c6ffde2f6c52291d049720))
* Phase 3 — translate projection mechanism for OpenCode ([#37](https://github.com/ajanderson1/agent-toolkit-cli/issues/37)) ([e867dbe](https://github.com/ajanderson1/agent-toolkit-cli/commit/e867dbe859cfa0667a642d98b9649bd098ac05c0))
* **tui:** confirm-discard modal on quit when pending edits exist ([7598db4](https://github.com/ajanderson1/agent-toolkit-cli/commit/7598db404d4f713e01bf6049b7f71740f6273bab))


### Bug Fixes

* **#30:** hard-stop on unsupported (harness, kind) pairs via _support SSOT ([#33](https://github.com/ajanderson1/agent-toolkit-cli/issues/33)) ([58a42b6](https://github.com/ajanderson1/agent-toolkit-cli/commit/58a42b62fa49cf92bec5c27858f7f215c34ecc71))
* **#38:** correct opencode home path to .config/opencode ([afb88bd](https://github.com/ajanderson1/agent-toolkit-cli/commit/afb88bdcabc313289a4f19a991aaa41ba6152e4e))
* **#39:** expose MCPs in the V1 Navigator kind sidebar ([#51](https://github.com/ajanderson1/agent-toolkit-cli/issues/51)) ([18dede3](https://github.com/ajanderson1/agent-toolkit-cli/commit/18dede3fe711447ad6ac537d532c7a6d8cbb57f5)), closes [#39](https://github.com/ajanderson1/agent-toolkit-cli/issues/39)
* **#40-A:** use translated slot filename when probing link status ([#44](https://github.com/ajanderson1/agent-toolkit-cli/issues/44)) ([366f58f](https://github.com/ajanderson1/agent-toolkit-cli/commit/366f58f56f8b2c57c19492154c64403f20f4ad3a))
* **#41:** project-scope skills work for opencode and pi ([#48](https://github.com/ajanderson1/agent-toolkit-cli/issues/48)) ([f7b7ff6](https://github.com/ajanderson1/agent-toolkit-cli/commit/f7b7ff60f4f1e876e4d1cfea77fce018c0a30679)), closes [#41](https://github.com/ajanderson1/agent-toolkit-cli/issues/41)
* **#52:** #content-header height auto so chips render visibly ([#57](https://github.com/ajanderson1/agent-toolkit-cli/issues/57)) ([ed55dc3](https://github.com/ajanderson1/agent-toolkit-cli/commit/ed55dc3207f4f64df9eb0783b49cf8e4035b88a0))
* **walker:** discover plugins under .claude-plugin/ (issue [#64](https://github.com/ajanderson1/agent-toolkit-cli/issues/64)) ([#68](https://github.com/ajanderson1/agent-toolkit-cli/issues/68)) ([02943f0](https://github.com/ajanderson1/agent-toolkit-cli/commit/02943f092a792b4d64dddd0a040cb2da685d5514))


### Documentation

* **matrix:** expand by-design rationale for plugins, hooks, commands ([#36](https://github.com/ajanderson1/agent-toolkit-cli/issues/36)) ([fed6357](https://github.com/ajanderson1/agent-toolkit-cli/commit/fed635719968aa9c23ab9963cc2cc2ca0fec2491))
* warn against pip install -e . shadowing uv tool install shim ([#66](https://github.com/ajanderson1/agent-toolkit-cli/issues/66)) ([f1f9640](https://github.com/ajanderson1/agent-toolkit-cli/commit/f1f9640d10c0cd7317f610cf06252c64cc447026)), closes [#62](https://github.com/ajanderson1/agent-toolkit-cli/issues/62)

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

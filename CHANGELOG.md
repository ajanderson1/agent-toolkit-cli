# Changelog

## [4.2.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v4.2.0...v4.2.1) (2026-06-15)


### Bug Fixes

* **skill:** parent-clone ref-guard edge cases — hex-named branch + doctor gate ([#422](https://github.com/ajanderson1/agent-toolkit-cli/issues/422)) ([#439](https://github.com/ajanderson1/agent-toolkit-cli/issues/439)) ([0122040](https://github.com/ajanderson1/agent-toolkit-cli/commit/0122040d715ebccea2d289c0a58f14799cd467c1))


### Documentation

* **cli:** document import / cross-machine sync and the no-export design ([#428](https://github.com/ajanderson1/agent-toolkit-cli/issues/428)) ([#435](https://github.com/ajanderson1/agent-toolkit-cli/issues/435)) ([de8f738](https://github.com/ajanderson1/agent-toolkit-cli/commit/de8f73835d93b8e1bed2d9c48b4b0a5d393be0c6))

## [4.2.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v4.1.0...v4.2.0) (2026-06-15)


### Features

* **agent:** surface implicitly-resolved scope via banner ([#418](https://github.com/ajanderson1/agent-toolkit-cli/issues/418)) ([#424](https://github.com/ajanderson1/agent-toolkit-cli/issues/424)) ([ac00a6f](https://github.com/ajanderson1/agent-toolkit-cli/commit/ac00a6f371fb3d2f6763213a427c993711a68794))
* **mcp:** surface implicitly-resolved scope via banner ([#419](https://github.com/ajanderson1/agent-toolkit-cli/issues/419)) ([#426](https://github.com/ajanderson1/agent-toolkit-cli/issues/426)) ([812e588](https://github.com/ajanderson1/agent-toolkit-cli/commit/812e588c467dd2152d1e6a59998f2c562c03e5b4))
* **pi-extension:** surface implicitly-resolved scope via banner ([#420](https://github.com/ajanderson1/agent-toolkit-cli/issues/420)) ([#430](https://github.com/ajanderson1/agent-toolkit-cli/issues/430)) ([a239aae](https://github.com/ajanderson1/agent-toolkit-cli/commit/a239aae6151a05fcd9a2d77da6ff3c62cfd9adea))
* **skill:** surface implicitly-resolved scope when no -g/-p given ([#417](https://github.com/ajanderson1/agent-toolkit-cli/issues/417)) ([4d0eed1](https://github.com/ajanderson1/agent-toolkit-cli/commit/4d0eed1e749dc4a94134b7114093cfc6abe7cf44))
* **tui:** 🌐 global marker on the instructions grid ([#388](https://github.com/ajanderson1/agent-toolkit-cli/issues/388)) ([4471e4b](https://github.com/ajanderson1/agent-toolkit-cli/commit/4471e4b0bece9b5ad454466e3e81e151b8ba096f))


### Bug Fixes

* **bundle:** correct stale mcp-rejection message (kind shipped in v4.0.0) ([#404](https://github.com/ajanderson1/agent-toolkit-cli/issues/404)) ([b647eb6](https://github.com/ajanderson1/agent-toolkit-cli/commit/b647eb61dafef9c97e1b96b315d3a9274f8012e1))
* **security:** block git ref option-injection + untrack internal planning corpus ([#425](https://github.com/ajanderson1/agent-toolkit-cli/issues/425)) ([09db458](https://github.com/ajanderson1/agent-toolkit-cli/commit/09db458356c14ac7445dc372fb9a8c9bcaca4425))
* **skill update:** locate legacy bare-named parent clones via shared resolver ([#412](https://github.com/ajanderson1/agent-toolkit-cli/issues/412)) ([#416](https://github.com/ajanderson1/agent-toolkit-cli/issues/416)) ([907dc2b](https://github.com/ajanderson1/agent-toolkit-cli/commit/907dc2b496047a945e45790994fc0f5652c20de3))
* **tests:** make the two env-leaking tests honor isolation ([19f5515](https://github.com/ajanderson1/agent-toolkit-cli/commit/19f55153f1d6945f0f903d2056101fe93043653d))


### Documentation

* clarify skill monorepo mechanism, add TUI reference, trim shipped roadmap items ([#411](https://github.com/ajanderson1/agent-toolkit-cli/issues/411)) ([79996a5](https://github.com/ajanderson1/agent-toolkit-cli/commit/79996a51380d60f9bc57ae9afa12012517138617))
* deprecate auto-generated mkdocstrings API reference ([30dbb27](https://github.com/ajanderson1/agent-toolkit-cli/commit/30dbb27c0b702663def64e5ecdf9511b2a4677cf))
* **glossary,roadmap:** define the two-axis verb model ([#406](https://github.com/ajanderson1/agent-toolkit-cli/issues/406)) ([0b5976a](https://github.com/ajanderson1/agent-toolkit-cli/commit/0b5976a5ad07743e6f110a4697b46cc93e92c6b8))
* **harness-matrix:** make the SSOT symmetric + add convention-compliance view ([#410](https://github.com/ajanderson1/agent-toolkit-cli/issues/410)) ([31ba993](https://github.com/ajanderson1/agent-toolkit-cli/commit/31ba9932de6ee3b899a971893c52518db7f1805a))
* **lock-files:** add unified lock-file schema reference ([85cde95](https://github.com/ajanderson1/agent-toolkit-cli/commit/85cde959f43f671e7dda4527eeb4ab2d9e7fffad))
* **nav:** wire orphaned lock-files.md into Reference nav ([#414](https://github.com/ajanderson1/agent-toolkit-cli/issues/414)) ([f26f6ba](https://github.com/ajanderson1/agent-toolkit-cli/commit/f26f6ba119f11086a319a805d322a94a884f4a95))
* **plan:** [#412](https://github.com/ajanderson1/agent-toolkit-cli/issues/412) parent-clone resolver — 8 TDD tasks ([c45d98b](https://github.com/ajanderson1/agent-toolkit-cli/commit/c45d98b9b385d6d2efc55a0a8f956fd8e71f23db))
* **plan:** [#423](https://github.com/ajanderson1/agent-toolkit-cli/issues/423) verb×asset×harness coverage — guard + G1-G4 tasks ([fe18739](https://github.com/ajanderson1/agent-toolkit-cli/commit/fe18739ef93d7655b6907cb2613e6d8e0a09b006))
* **plan:** 🌐 global marker on instructions grid ([#388](https://github.com/ajanderson1/agent-toolkit-cli/issues/388)) ([868583e](https://github.com/ajanderson1/agent-toolkit-cli/commit/868583ed7388a50289e696d1d2be57f833ea5efd))
* **plan:** implicit-scope banner implementation plan ([#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413)) ([1f32f68](https://github.com/ajanderson1/agent-toolkit-cli/commit/1f32f68d64cfc04163861657591cc0da3c5b12e0))
* **readme:** point verb model to the glossary SSOT ([#407](https://github.com/ajanderson1/agent-toolkit-cli/issues/407)) ([c68c3bf](https://github.com/ajanderson1/agent-toolkit-cli/commit/c68c3bf70ef90f6400502af21176663bc78267be))
* reconcile docs site with v4.1.0 reality (MCP, bundles, asset-types) ([#403](https://github.com/ajanderson1/agent-toolkit-cli/issues/403)) ([04cbe7b](https://github.com/ajanderson1/agent-toolkit-cli/commit/04cbe7b6861d54de49fe4044c56fb6ed177ee8f7))
* **roadmap:** link two-axis verb mention to the callout anchor ([#408](https://github.com/ajanderson1/agent-toolkit-cli/issues/408)) ([41184a8](https://github.com/ajanderson1/agent-toolkit-cli/commit/41184a8aa6838fea0eb93ec89360fc7bbf9021b2))
* **spec,plan:** apply [#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413) critical-review findings (stdout banner, reset reword, fixture, doctor read) ([2470e0d](https://github.com/ajanderson1/agent-toolkit-cli/commit/2470e0d67a22ae92bcdacb47a7087d8c7e8635f2))
* **spec+plan:** [#418](https://github.com/ajanderson1/agent-toolkit-cli/issues/418) agent implicit-scope banner (mirror [#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413)) ([d6df8df](https://github.com/ajanderson1/agent-toolkit-cli/commit/d6df8df8a98d775eba1ecb7e6b48ec90cf9f118e))
* **spec+plan:** [#419](https://github.com/ajanderson1/agent-toolkit-cli/issues/419) mcp implicit-scope banner (mirror [#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413)) ([428e0bc](https://github.com/ajanderson1/agent-toolkit-cli/commit/428e0bcc77dc38cb82e3865b4b5a4a32b7058eff))
* **spec+plan:** [#420](https://github.com/ajanderson1/agent-toolkit-cli/issues/420) pi-extension implicit-scope banner (mirror [#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413)) ([848adfa](https://github.com/ajanderson1/agent-toolkit-cli/commit/848adfaae01b775eb59c936e8b0223af9ca22994))
* **spec+plan:** apply [#423](https://github.com/ajanderson1/agent-toolkit-cli/issues/423) critical-review findings ([38f2310](https://github.com/ajanderson1/agent-toolkit-cli/commit/38f2310d7e98348e836ab2fec2f06c1c3fb49654))
* **spec+plan:** fold ce-doc-review findings into [#412](https://github.com/ajanderson1/agent-toolkit-cli/issues/412) ([54733bd](https://github.com/ajanderson1/agent-toolkit-cli/commit/54733bd16bd2a43d98cbe00508dff3b65e397775))
* **spec:** 🌐 global marker on instructions grid ([#388](https://github.com/ajanderson1/agent-toolkit-cli/issues/388)) ([f08ede1](https://github.com/ajanderson1/agent-toolkit-cli/commit/f08ede18844e17251dab242a2457d5be88bb71b8))
* **spec:** asset-type-aware lock key for agents/pi-extensions ([#409](https://github.com/ajanderson1/agent-toolkit-cli/issues/409)) ([77ddeea](https://github.com/ajanderson1/agent-toolkit-cli/commit/77ddeea6690bb353d25596ad26314198117273f4))
* **spec:** drop [#409](https://github.com/ajanderson1/agent-toolkit-cli/issues/409) lock-key spec — won't-fix, documented instead ([fe5ce45](https://github.com/ajanderson1/agent-toolkit-cli/commit/fe5ce452f501c739781dd9d45840aa2293f3f389))
* **spec:** fold ce-doc-review findings into [#409](https://github.com/ajanderson1/agent-toolkit-cli/issues/409) lock-key spec ([c5986a3](https://github.com/ajanderson1/agent-toolkit-cli/commit/c5986a317a798f659bad0d58818541beaaaf4407))
* **spec:** implicit-scope banner + monorepo-refusal wording ([#413](https://github.com/ajanderson1/agent-toolkit-cli/issues/413)) ([503b115](https://github.com/ajanderson1/agent-toolkit-cli/commit/503b115fdcffca06614b98d2dd9ce7cef638a4c3))
* **spec:** probe-both parent-clone resolver + doctor alias cleanup ([#412](https://github.com/ajanderson1/agent-toolkit-cli/issues/412)) ([9d24869](https://github.com/ajanderson1/agent-toolkit-cli/commit/9d24869997967123d602f5ade4da0435ffb3d8da))
* **spec:** verb×asset×harness coverage — close real gaps + coverage guard ([c6d27af](https://github.com/ajanderson1/agent-toolkit-cli/commit/c6d27af9359c67424bc096de67b3c87930e464b8))
* **strategy:** refresh users, metrics, and tracks for v4 reality ([55c58e9](https://github.com/ajanderson1/agent-toolkit-cli/commit/55c58e9cd067f0012974ae91a28c268f61388662))


### Build

* **docs:** bind `make docs` to all interfaces for meshnet access ([998751d](https://github.com/ajanderson1/agent-toolkit-cli/commit/998751dfb6015c53808bcdee86f2cf8863777727))

## [4.1.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v4.0.0...v4.1.0) (2026-06-14)


### Features

* **mcp:** add a "standard" projection — the canonical .mcp.json/mcpServers file ([#401](https://github.com/ajanderson1/agent-toolkit-cli/issues/401)) ([145baec](https://github.com/ajanderson1/agent-toolkit-cli/commit/145baecf8090384d13a44638e8243956d0a12330))
* **tui:** add mcp tab to the asset-types sidebar ([#402](https://github.com/ajanderson1/agent-toolkit-cli/issues/402)) ([2282135](https://github.com/ajanderson1/agent-toolkit-cli/commit/2282135e4d8347c29b57efe8c15eb4bb34cadea2))


### Documentation

* **plan:** MCP standard projection implementation plan ([#399](https://github.com/ajanderson1/agent-toolkit-cli/issues/399)) ([286c0af](https://github.com/ajanderson1/agent-toolkit-cli/commit/286c0af08d2ca5fdf1ecd479a3fb57b5660ab0b6))
* **plan:** MCP TUI tab implementation plan ([#398](https://github.com/ajanderson1/agent-toolkit-cli/issues/398)) ([33d9b23](https://github.com/ajanderson1/agent-toolkit-cli/commit/33d9b239ff69a502dd75486687adadec57f6682c))
* **spec,plan:** fold critical-review findings into [#398](https://github.com/ajanderson1/agent-toolkit-cli/issues/398) design ([2686baf](https://github.com/ajanderson1/agent-toolkit-cli/commit/2686bafba95f009485ec4a3491124ad4f3f1b2bc))
* **spec,plan:** fold deep-review findings into [#399](https://github.com/ajanderson1/agent-toolkit-cli/issues/399) design ([a4ac6b7](https://github.com/ajanderson1/agent-toolkit-cli/commit/a4ac6b7c45a583467562f4d5ccdd6484aff00679))
* **spec,plan:** round-2 review fixes for [#399](https://github.com/ajanderson1/agent-toolkit-cli/issues/399) ([f7abd00](https://github.com/ajanderson1/agent-toolkit-cli/commit/f7abd000aa660ce21cd818db3951b4abf7715155))
* **spec:** MCP standard projection design ([#399](https://github.com/ajanderson1/agent-toolkit-cli/issues/399)) ([6960200](https://github.com/ajanderson1/agent-toolkit-cli/commit/6960200d8244590206f99970aa3e79d61aee5da6))
* **spec:** MCP TUI tab design ([#398](https://github.com/ajanderson1/agent-toolkit-cli/issues/398)) ([b5c65c5](https://github.com/ajanderson1/agent-toolkit-cli/commit/b5c65c5ae3eecf9717c03bc624efba7e9ac4baeb))

## [4.0.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.9.0...v4.0.0) (2026-06-13)


### ⚠ BREAKING CHANGES

* **agents:** 'universal', 'general-skill', 'general-agent' are no longer accepted as agent/harness tokens — use 'standard' / 'standard-skill' / 'standard-agent'. This is the v4.0.0 trigger.

### Features

* **agent:** agent add supports category-repo subpaths (monorepo agents) ([#391](https://github.com/ajanderson1/agent-toolkit-cli/issues/391)) ([060622e](https://github.com/ajanderson1/agent-toolkit-cli/commit/060622ec8b273e6828b062e031cf2cf658f0686d))
* **bundle:** toolkit-native bundle manifest + install/validate ([#369](https://github.com/ajanderson1/agent-toolkit-cli/issues/369)) ([#395](https://github.com/ajanderson1/agent-toolkit-cli/issues/395)) ([2406951](https://github.com/ajanderson1/agent-toolkit-cli/commit/2406951d4b33ad10cdfd4dc5c3f19d2d243c45eb))
* **lock:** distinguish user SHA-pin from observed upstream tip ([#392](https://github.com/ajanderson1/agent-toolkit-cli/issues/392)) ([40fee83](https://github.com/ajanderson1/agent-toolkit-cli/commit/40fee835daa094257232117f6a6b4d51c449f9a6))
* **mcp:** re-port the MCP asset kind into the v3 per-kind architecture ([#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329)) ([#397](https://github.com/ajanderson1/agent-toolkit-cli/issues/397)) ([a2d376f](https://github.com/ajanderson1/agent-toolkit-cli/commit/a2d376f5fbfde04d72a9223e9c112b6ce07493ba))
* **skill:** default skill install/uninstall --agents ([#393](https://github.com/ajanderson1/agent-toolkit-cli/issues/393)) ([#394](https://github.com/ajanderson1/agent-toolkit-cli/issues/394)) ([186b952](https://github.com/ajanderson1/agent-toolkit-cli/commit/186b95263689d9aaf400ac2321b725ffdc6f1af3))


### Bug Fixes

* **agent:** adapter read-path failures surface as InstallError with slug ([#373](https://github.com/ajanderson1/agent-toolkit-cli/issues/373)) ([#384](https://github.com/ajanderson1/agent-toolkit-cli/issues/384)) ([09b7c24](https://github.com/ajanderson1/agent-toolkit-cli/commit/09b7c246c29d4d4e8979fd69da4927972d5db906))
* **agents:** remove deprecated universal/general-* token aliases ([#356](https://github.com/ajanderson1/agent-toolkit-cli/issues/356)) ([#390](https://github.com/ajanderson1/agent-toolkit-cli/issues/390)) ([16c234e](https://github.com/ajanderson1/agent-toolkit-cli/commit/16c234e03e9c647642c8543f6d578aa3d0742304))
* pi-extension push/status define behaviour on SHA-pinned entries ([#386](https://github.com/ajanderson1/agent-toolkit-cli/issues/386)) ([1abdef4](https://github.com/ajanderson1/agent-toolkit-cli/commit/1abdef4fbb5d800896840346dede2ed5cd7afb1c))
* **pi-extension:** add heals a non-repo store dir; doctor surfaces it as half_dir ([#347](https://github.com/ajanderson1/agent-toolkit-cli/issues/347)) ([#387](https://github.com/ajanderson1/agent-toolkit-cli/issues/387)) ([52f7372](https://github.com/ajanderson1/agent-toolkit-cli/commit/52f7372e8e0389499ca9ea7c3d4bbe8154bbe583))
* push not-in-lock hints the other scope's lock and exits 1 ([#383](https://github.com/ajanderson1/agent-toolkit-cli/issues/383)) ([70bb897](https://github.com/ajanderson1/agent-toolkit-cli/commit/70bb8971560fcc46a3e071aca3a9c02841e80b0c))
* **tui:** agent grid missing 🌐 global marker at project scope ([#385](https://github.com/ajanderson1/agent-toolkit-cli/issues/385)) ([e8b27eb](https://github.com/ajanderson1/agent-toolkit-cli/commit/e8b27eb59c732faf4cd19eaef2e772a381df78df))


### Documentation

* add mkdocs-redirects mapping for kinds→asset-types page moves ([#389](https://github.com/ajanderson1/agent-toolkit-cli/issues/389)) ([6f7bc48](https://github.com/ajanderson1/agent-toolkit-cli/commit/6f7bc486935d5142a29d4f74fc78d75453e9c742)), closes [#364](https://github.com/ajanderson1/agent-toolkit-cli/issues/364)
* **mcp:** clean-start v3 spec for [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329); retire v1 MCP design generation ([dd5e61b](https://github.com/ajanderson1/agent-toolkit-cli/commit/dd5e61b760b799584c17147b44de7f3ea5ffc572))
* **plan:** agent grid 🌐 global marker implementation plan for [#374](https://github.com/ajanderson1/agent-toolkit-cli/issues/374) ([3e2e740](https://github.com/ajanderson1/agent-toolkit-cli/commit/3e2e740699bff2a9066f71c1748ac08413466c20))
* **plan:** bundle manifest v1 implementation plan for [#369](https://github.com/ajanderson1/agent-toolkit-cli/issues/369) ([a6ab17c](https://github.com/ajanderson1/agent-toolkit-cli/commit/a6ab17cc3a508bf0556fbcd178a1fc9282b4aaed))
* **plan:** default skill install --agents implementation plan for [#393](https://github.com/ajanderson1/agent-toolkit-cli/issues/393) ([ccac9cb](https://github.com/ajanderson1/agent-toolkit-cli/commit/ccac9cbc1d403c9604e6d5ac47f9c798f4675aea))
* **plan:** fix F2 lock-precheck key shape (re-review) for [#369](https://github.com/ajanderson1/agent-toolkit-cli/issues/369) ([2f151c6](https://github.com/ajanderson1/agent-toolkit-cli/commit/2f151c66bd9154dd8c1fd771c545d40673a17b49))
* **plan:** lock pin-vs-observed-tip implementation plan for [#345](https://github.com/ajanderson1/agent-toolkit-cli/issues/345) ([0cdb01d](https://github.com/ajanderson1/agent-toolkit-cli/commit/0cdb01d6c706f78d5dc113a303b20f743f2446a1))
* **plan:** mkdocs-redirects kinds→asset-types spec+plan for [#364](https://github.com/ajanderson1/agent-toolkit-cli/issues/364) ([0f4a8d9](https://github.com/ajanderson1/agent-toolkit-cli/commit/0f4a8d9c680ea536da67ba072e6e305f6825d0a5))
* **plan:** pi-extension half-dir heal+doctor implementation plan for [#347](https://github.com/ajanderson1/agent-toolkit-cli/issues/347) ([6f1906f](https://github.com/ajanderson1/agent-toolkit-cli/commit/6f1906f9237e96caffba87c5145af4c2b779ef01))
* **plan:** pi-extension push/status SHA-pinned implementation plan for [#346](https://github.com/ajanderson1/agent-toolkit-cli/issues/346) ([1338e35](https://github.com/ajanderson1/agent-toolkit-cli/commit/1338e355895636726852c97565683557c3a3b2c8))
* **plan:** push not-in-lock cross-scope hint implementation plan for [#371](https://github.com/ajanderson1/agent-toolkit-cli/issues/371) ([a870e0a](https://github.com/ajanderson1/agent-toolkit-cli/commit/a870e0ad4f2ede7141b8fe16a318bf7424d53ee1))
* **plan:** resolve critical-review findings for [#347](https://github.com/ajanderson1/agent-toolkit-cli/issues/347) (line numbers, Task-1 git env loop) ([3791bcc](https://github.com/ajanderson1/agent-toolkit-cli/commit/3791bcc7475116425dc4c7be16c397cb6aa80518))
* **plan:** resolve critical-review findings for [#374](https://github.com/ajanderson1/agent-toolkit-cli/issues/374) (task reorder F1, comment sweeps F2/A2) ([63a19e3](https://github.com/ajanderson1/agent-toolkit-cli/commit/63a19e33bfd278c121f90c7eac6b619a0e059d1d))
* **spec,plan:** adapter read-path hardening for [#373](https://github.com/ajanderson1/agent-toolkit-cli/issues/373) ([adad5b3](https://github.com/ajanderson1/agent-toolkit-cli/commit/adad5b3d1d0403a1fd1d9e8383d7b32db8a4d198))
* **spec,plan:** resolve critical-review findings for [#346](https://github.com/ajanderson1/agent-toolkit-cli/issues/346) ([05d71ea](https://github.com/ajanderson1/agent-toolkit-cli/commit/05d71ead6c321502f44c86cb1d4985db73d03807))
* **spec,plan:** resolve critical-review findings for [#371](https://github.com/ajanderson1/agent-toolkit-cli/issues/371) ([2561624](https://github.com/ajanderson1/agent-toolkit-cli/commit/256162407e290ad68be7da5849d9a109f9f062a1))
* **spec,plan:** resolve critical-review findings for [#373](https://github.com/ajanderson1/agent-toolkit-cli/issues/373) ([8b92435](https://github.com/ajanderson1/agent-toolkit-cli/commit/8b924359ff5f8a1fb2b60b6e6e1d70c937ad523f))
* **spec+plan:** remove deprecated token aliases for [#356](https://github.com/ajanderson1/agent-toolkit-cli/issues/356) ([f9e7ae6](https://github.com/ajanderson1/agent-toolkit-cli/commit/f9e7ae61a2715306523defc70e0d956024d8ba4e))
* **spec+plan:** resolve critical-review findings for [#345](https://github.com/ajanderson1/agent-toolkit-cli/issues/345) ([493a14b](https://github.com/ajanderson1/agent-toolkit-cli/commit/493a14b28382f2e83e1a8ec8229ba914e3721214))
* **spec+plan:** resolve critical-review findings for [#356](https://github.com/ajanderson1/agent-toolkit-cli/issues/356) ([0c25bc9](https://github.com/ajanderson1/agent-toolkit-cli/commit/0c25bc901867975fbf51983eac0d13ea4f870df3))
* **spec+plan:** resolve critical-review findings for [#369](https://github.com/ajanderson1/agent-toolkit-cli/issues/369) ([645e6ad](https://github.com/ajanderson1/agent-toolkit-cli/commit/645e6ad89ebbb1c560e360874306822fe8c566f9))
* **spec+plan:** resolve critical-review findings for [#393](https://github.com/ajanderson1/agent-toolkit-cli/issues/393) ([b671d14](https://github.com/ajanderson1/agent-toolkit-cli/commit/b671d14c2a9f86bd0f234c0ea14cfd92fce0253e))
* **spec:** agent grid 🌐 global marker design for [#374](https://github.com/ajanderson1/agent-toolkit-cli/issues/374) ([90332dd](https://github.com/ajanderson1/agent-toolkit-cli/commit/90332dde95deab8886fc01d067b1abb5ad3bbdaf))
* **spec:** bundle manifest v1 design for [#369](https://github.com/ajanderson1/agent-toolkit-cli/issues/369) ([48d8a0f](https://github.com/ajanderson1/agent-toolkit-cli/commit/48d8a0fba90bda14c225f8b9dd4d797678bdb781))
* **spec:** default skill install --agents to standard for [#393](https://github.com/ajanderson1/agent-toolkit-cli/issues/393) ([99cb679](https://github.com/ajanderson1/agent-toolkit-cli/commit/99cb6794b2f1b1fe3f544a4e2c3e064c7eea81b2))
* **spec:** lock pin-vs-observed-tip derived-reader design for [#345](https://github.com/ajanderson1/agent-toolkit-cli/issues/345) ([25114eb](https://github.com/ajanderson1/agent-toolkit-cli/commit/25114eb9a2199eca95285f3338da3f0922933bf5))
* **spec:** pi-extension half-dir heal+doctor design for [#347](https://github.com/ajanderson1/agent-toolkit-cli/issues/347) ([07a0a3f](https://github.com/ajanderson1/agent-toolkit-cli/commit/07a0a3f72f5bfa38b3be8c98d7ccf5d2e368d305))
* **spec:** pi-extension push/status SHA-pinned behaviour design for [#346](https://github.com/ajanderson1/agent-toolkit-cli/issues/346) ([e68244a](https://github.com/ajanderson1/agent-toolkit-cli/commit/e68244a9045f0b634b57d790ad2a82151306ba56))
* **spec:** push not-in-lock cross-scope hint + exit 1 design for [#371](https://github.com/ajanderson1/agent-toolkit-cli/issues/371) ([ced519e](https://github.com/ajanderson1/agent-toolkit-cli/commit/ced519e847a317c345589c1ff77df32d76970327))


### CI

* **release-please:** bump release-please-action v4 -&gt; v5 (Node 24 runtime) ([#396](https://github.com/ajanderson1/agent-toolkit-cli/issues/396)) ([8ae27af](https://github.com/ajanderson1/agent-toolkit-cli/commit/8ae27af53db4d661563fda26bb7ff3d6ea2dd3d0))

## [3.9.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.8.0...v3.9.0) (2026-06-12)


### Features

* **instructions:** doctor backup-then-symlink fix when canonical is populated ([#379](https://github.com/ajanderson1/agent-toolkit-cli/issues/379)) ([4724d3e](https://github.com/ajanderson1/agent-toolkit-cli/commit/4724d3e571c319ecd9c97c1478863c58dfc1646d))


### Bug Fixes

* **agent:** agent install -p writes no project lock entry — project list/TUI/doctor blind to installed agents ([#362](https://github.com/ajanderson1/agent-toolkit-cli/issues/362)) ([#378](https://github.com/ajanderson1/agent-toolkit-cli/issues/378)) ([429c184](https://github.com/ajanderson1/agent-toolkit-cli/commit/429c1846e6e8568f4b538e23af5ce8e65ad00026))
* **agent:** per-adapter sentinel adoption — symlink/translate ownership sidecars ([#368](https://github.com/ajanderson1/agent-toolkit-cli/issues/368)) ([#380](https://github.com/ajanderson1/agent-toolkit-cli/issues/380)) ([7e39e71](https://github.com/ajanderson1/agent-toolkit-cli/commit/7e39e711f1c6a7da1fe40bd7f9cb93d145ca174f))


### Documentation

* **plan:** agent install -p project lock entry plan for [#362](https://github.com/ajanderson1/agent-toolkit-cli/issues/362) ([eb3d011](https://github.com/ajanderson1/agent-toolkit-cli/commit/eb3d01157d1175706a370425bfb0612280f8b7cc))
* **plan:** backup-then-symlink doctor fix plan for [#375](https://github.com/ajanderson1/agent-toolkit-cli/issues/375) ([7e5cd44](https://github.com/ajanderson1/agent-toolkit-cli/commit/7e5cd449a40532c22abcef499fe1228d58d79108))
* **plan:** per-adapter sentinel adoption implementation plan for [#368](https://github.com/ajanderson1/agent-toolkit-cli/issues/368) ([c184771](https://github.com/ajanderson1/agent-toolkit-cli/commit/c1847716d931f657601c2a9fd71a2fc422ce5bff))
* **spec,plan:** light-tier spec+plan for [#365](https://github.com/ajanderson1/agent-toolkit-cli/issues/365) both-spellings architecture guard ([80c7565](https://github.com/ajanderson1/agent-toolkit-cli/commit/80c75658a912e85a283226f6d3df9b1ea4aa2401))
* **spec,plan:** resolve critical-review findings for [#362](https://github.com/ajanderson1/agent-toolkit-cli/issues/362) ([62e0e46](https://github.com/ajanderson1/agent-toolkit-cli/commit/62e0e469ce5b96a2b7f0865186aa5b809b9e9849))
* **spec,plan:** resolve critical-review findings for [#368](https://github.com/ajanderson1/agent-toolkit-cli/issues/368) ([2c905d0](https://github.com/ajanderson1/agent-toolkit-cli/commit/2c905d0ab7e342fcb2db337e0a56dadd5a5d909a))
* **spec,plan:** resolve critical-review findings for [#375](https://github.com/ajanderson1/agent-toolkit-cli/issues/375) ([34da7e6](https://github.com/ajanderson1/agent-toolkit-cli/commit/34da7e6fcf3837a13b25b021e6d6ddf778951b2b))
* **spec:** agent install -p project lock entry design for [#362](https://github.com/ajanderson1/agent-toolkit-cli/issues/362) ([6799298](https://github.com/ajanderson1/agent-toolkit-cli/commit/67992987b90caa9bf3fda7fb10ad5c8b1199a8dc))
* **spec:** backup-then-symlink doctor fix design for [#375](https://github.com/ajanderson1/agent-toolkit-cli/issues/375) ([99305d8](https://github.com/ajanderson1/agent-toolkit-cli/commit/99305d835e8bae5f525607f3a0dc55c039a172e2))
* **spec:** per-adapter sentinel adoption design for [#368](https://github.com/ajanderson1/agent-toolkit-cli/issues/368) ([4ebf315](https://github.com/ajanderson1/agent-toolkit-cli/commit/4ebf3152950e0c647be33087c85252966fa3e241))

## [3.8.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.7.0...v3.8.0) (2026-06-11)


### Features

* **agent:** standard agents projection (.claude/agents) + Standard column on the agents tab ([#366](https://github.com/ajanderson1/agent-toolkit-cli/issues/366)) ([05eb9b7](https://github.com/ajanderson1/agent-toolkit-cli/commit/05eb9b7c98fe52cda4d77d25ec1178e473da81a7))
* **rename:** universal/general-* → standard throughout CLI and TUI ([#350](https://github.com/ajanderson1/agent-toolkit-cli/issues/350)) ([#357](https://github.com/ajanderson1/agent-toolkit-cli/issues/357)) ([fc639b6](https://github.com/ajanderson1/agent-toolkit-cli/commit/fc639b6e9eadbe2919cf7711aaf229eb9c692103))
* **tui:** row-universe union — unlisted project installs visible across kinds ([#360](https://github.com/ajanderson1/agent-toolkit-cli/issues/360)) ([#367](https://github.com/ajanderson1/agent-toolkit-cli/issues/367)) ([7e503b0](https://github.com/ajanderson1/agent-toolkit-cli/commit/7e503b01a65af5506d11849ac1d76b513e6e9dc4))
* **tui:** standard/non-standard matrix column groups ([#351](https://github.com/ajanderson1/agent-toolkit-cli/issues/351)) ([#359](https://github.com/ajanderson1/agent-toolkit-cli/issues/359)) ([728414f](https://github.com/ajanderson1/agent-toolkit-cli/commit/728414f1aa759838cd1090eb8f294469f15016b3))


### Bug Fixes

* **agent:** agent install default fan-out — clean error for translate-emitter frontmatter failures ([#372](https://github.com/ajanderson1/agent-toolkit-cli/issues/372)) ([f0a29fd](https://github.com/ajanderson1/agent-toolkit-cli/commit/f0a29fd2c7a175bae7e0510f0ac3f36f7efb73bc))


### Refactors

* rename 'kind' terminology to 'asset type' ([#363](https://github.com/ajanderson1/agent-toolkit-cli/issues/363)) ([268c855](https://github.com/ajanderson1/agent-toolkit-cli/commit/268c855e242e8f7df77b35cbc9bea93e1772ddb1))


### Documentation

* compatibility matrix page, per-harness + per-kind atomic notes, glossary ([91d3b66](https://github.com/ajanderson1/agent-toolkit-cli/commit/91d3b66e1608d9be6b7d42f48db21890de631458))
* **glossary:** subsections, condensed def-list, conformance concepts ([ff3c443](https://github.com/ajanderson1/agent-toolkit-cli/commit/ff3c44370531eef7cb9eb853d2c286104bb5fa70))
* **harnesses:** validating source link for every per-kind claim + richer Kind definition ([d29dbfb](https://github.com/ajanderson1/agent-toolkit-cli/commit/d29dbfba81c0d6913f8c9d6791c98f9d5a16d981))
* **mcp:** [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329) deep critical review — 16 fixes into spec+plan, catalog+lock decisions ([1c3fbe4](https://github.com/ajanderson1/agent-toolkit-cli/commit/1c3fbe43b012e07d87130419e3bf47afdc6adea2))
* **mcp:** [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329) final mechanism — direct writes, greedy scope-less update, unmanaged [!] coexistence ([c992b7f](https://github.com/ajanderson1/agent-toolkit-cli/commit/c992b7f494710a928f49cdc084c09738a77763f3))
* **mcp:** [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329) mechanism revision — library model, source flags, version transparency, update verb ([1f66650](https://github.com/ajanderson1/agent-toolkit-cli/commit/1f6665044aaaf57b4e11b1012b2fb9c5eb0c2e5f))
* **mcp:** [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329) update-verb scope semantics — two independent reconciliations ([c79cd06](https://github.com/ajanderson1/agent-toolkit-cli/commit/c79cd067a02d8b2b810b9f0ee32c6169c765e2dd))
* **plan:** [#360](https://github.com/ajanderson1/agent-toolkit-cli/issues/360) TUI row-universe union implementation plan ([f2ece86](https://github.com/ajanderson1/agent-toolkit-cli/commit/f2ece86e9a2c970fb4690c331993f22e0f241562))
* **plan:** standard-agents-projection implementation plan for [#361](https://github.com/ajanderson1/agent-toolkit-cli/issues/361) ([330f746](https://github.com/ajanderson1/agent-toolkit-cli/commit/330f746c07bdbda7be7ae26c5f6d13dc9679515b))
* scaffold MkDocs Material site ([b144f1a](https://github.com/ajanderson1/agent-toolkit-cli/commit/b144f1a4d23dc74997fdeaeb7800d14f0bb80c29))
* **site:** remap matrix glyphs, publish SSOT page, unbold nav mains ([e8ccbbe](https://github.com/ajanderson1/agent-toolkit-cli/commit/e8ccbbe9fa2e4fc36e1a801a651f03552e53f0b9))
* **site:** restore Material styling on the matrix table ([d075bcf](https://github.com/ajanderson1/agent-toolkit-cli/commit/d075bcf788e7baf7d08637c699933c3b54caa2f3))
* **site:** single foldable matrix, headline-first nav, harness logos ([086bab4](https://github.com/ajanderson1/agent-toolkit-cli/commit/086bab477eb76db7b3b67077eb6f469d8fea06d5))
* **spec,plan:** apply critical-review findings to [#360](https://github.com/ajanderson1/agent-toolkit-cli/issues/360) ([1b70b86](https://github.com/ajanderson1/agent-toolkit-cli/commit/1b70b86fa63442745d143f31fd49bedb830a7a6f))
* **spec,plan:** apply PM adversarial review to [#361](https://github.com/ajanderson1/agent-toolkit-cli/issues/361) — sentinel is the ownership record ([caa7720](https://github.com/ajanderson1/agent-toolkit-cli/commit/caa7720da298b7494abc22eda98ea9c4ff55fb32))
* **spec,plan:** kind→asset-type rename plan for [#355](https://github.com/ajanderson1/agent-toolkit-cli/issues/355); spec covers mkdocs site ([21521fd](https://github.com/ajanderson1/agent-toolkit-cli/commit/21521fdfddcb138c2e05b6b0765a47869d873bf4))
* **spec,plan:** resolve critical-review findings for [#355](https://github.com/ajanderson1/agent-toolkit-cli/issues/355) ([0a42890](https://github.com/ajanderson1/agent-toolkit-cli/commit/0a42890d2c0723653c8944ddcab1d37a1af73928))
* **spec,plan:** resolve critical-review findings for [#361](https://github.com/ajanderson1/agent-toolkit-cli/issues/361) ([dd71d97](https://github.com/ajanderson1/agent-toolkit-cli/commit/dd71d972f2113abd15e2e88ab0bf4d132165ff3e))
* **spec,plan:** resolve critical-review findings for [#370](https://github.com/ajanderson1/agent-toolkit-cli/issues/370) ([a551334](https://github.com/ajanderson1/agent-toolkit-cli/commit/a551334a982190fb9b4057e966d933012461f393))
* **spec,plan:** translate-emitter ValueError clean-error design for [#370](https://github.com/ajanderson1/agent-toolkit-cli/issues/370) ([be0969e](https://github.com/ajanderson1/agent-toolkit-cli/commit/be0969e7de891cc591d382192c0649617d301423))
* **spec:** [#360](https://github.com/ajanderson1/agent-toolkit-cli/issues/360) TUI row-universe union — unlisted project installs visible across kinds ([9260cf3](https://github.com/ajanderson1/agent-toolkit-cli/commit/9260cf398c6da19c1e8e4f99688af7190f445069))
* **spec:** [#361](https://github.com/ajanderson1/agent-toolkit-cli/issues/361) spec tracks the long-tail-CLI-only + MAIN_HARNESSES decisions from the [#351](https://github.com/ajanderson1/agent-toolkit-cli/issues/351) demo ([62992a1](https://github.com/ajanderson1/agent-toolkit-cli/commit/62992a101f37a3c644a77cd3e8dcac7617019342))
* **spec:** kind→asset-type rename design for [#355](https://github.com/ajanderson1/agent-toolkit-cli/issues/355) ([e3e0c32](https://github.com/ajanderson1/agent-toolkit-cli/commit/e3e0c32718fed4d1eb0824b0d59c40302916045b))
* **spec:** standard agents projection design for [#361](https://github.com/ajanderson1/agent-toolkit-cli/issues/361) ([4d7aa0f](https://github.com/ajanderson1/agent-toolkit-cli/commit/4d7aa0f65057fb5ba6313c7f41ca53a1ba0aa077))

## [3.7.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.6.4...v3.7.0) (2026-06-10)


### Features

* **tui:** pi grid follows the app-wide scope toggle ([#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349)) ([22c71a9](https://github.com/ajanderson1/agent-toolkit-cli/commit/22c71a9f566ae97a6201fe354c0e072699798af6))


### Documentation

* **plan:** pi-grid scope toggle implementation plan ([#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349)) ([dd30812](https://github.com/ajanderson1/agent-toolkit-cli/commit/dd30812acfbcd83e4710f0e778f6ac80ca12f64f))
* **plan:** standard-matrix-groups implementation plan for [#351](https://github.com/ajanderson1/agent-toolkit-cli/issues/351) ([42dd94b](https://github.com/ajanderson1/agent-toolkit-cli/commit/42dd94b1095c5ac6789c1842c702e4afb523043d))
* **plan:** standard-rename implementation plan for [#350](https://github.com/ajanderson1/agent-toolkit-cli/issues/350) ([b8d593c](https://github.com/ajanderson1/agent-toolkit-cli/commit/b8d593c544d339481f7c3d8a1ac5657ad2462cc3))
* **spec,plan:** resolve critical-review findings for [#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349) ([e611388](https://github.com/ajanderson1/agent-toolkit-cli/commit/e6113885918ad55f072453fe97b7996a77166131))
* **spec,plan:** resolve critical-review findings for [#350](https://github.com/ajanderson1/agent-toolkit-cli/issues/350) ([d461825](https://github.com/ajanderson1/agent-toolkit-cli/commit/d461825ca17fd9455c9161037d14a11634894445))
* **spec,plan:** resolve critical-review findings for [#351](https://github.com/ajanderson1/agent-toolkit-cli/issues/351) ([e155b1d](https://github.com/ajanderson1/agent-toolkit-cli/commit/e155b1df8354df8303d4d61fec9533809587a2c7))
* **spec:** [#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349) preservation goes app-wide via single app-side site (PM correction) ([2e811eb](https://github.com/ajanderson1/agent-toolkit-cli/commit/2e811eb1eb525454ec12cf9120ba3ed4f1d4d2cd))
* **spec:** pi grid joins app-wide scope toggle ([#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349)) ([4fc7db4](https://github.com/ajanderson1/agent-toolkit-cli/commit/4fc7db4c032218fd4f6dbcda0605d573aa84b94b))
* **spec:** standard-rename design for [#350](https://github.com/ajanderson1/agent-toolkit-cli/issues/350) (premise-corrected, no migration) ([73961df](https://github.com/ajanderson1/agent-toolkit-cli/commit/73961dfbf6610ed2eaa6f4d0b31de9c4cabfc6b4))
* **spec:** standard/non-standard matrix groups design for [#351](https://github.com/ajanderson1/agent-toolkit-cli/issues/351) ([5d9251e](https://github.com/ajanderson1/agent-toolkit-cli/commit/5d9251ea8916f5edc49f2a11df19672f13115f25))

## [3.6.4](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.6.3...v3.6.4) (2026-06-10)


### Bug Fixes

* **pi-extension:** SHA-pinned add lands on the pinned commit ([#330](https://github.com/ajanderson1/agent-toolkit-cli/issues/330)) ([#343](https://github.com/ajanderson1/agent-toolkit-cli/issues/343)) ([6635496](https://github.com/ajanderson1/agent-toolkit-cli/commit/6635496a121518b63228f09bc32e16e203839d81))

## [3.6.3](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.6.2...v3.6.3) (2026-06-10)


### Documentation

* **plan:** fix SHA-pinned pi-extension add ([#330](https://github.com/ajanderson1/agent-toolkit-cli/issues/330)) ([97710e9](https://github.com/ajanderson1/agent-toolkit-cli/commit/97710e90efe99ad25d121ba91e347a64fd653a98))
* **plan:** skills repo split implementation plan ([#341](https://github.com/ajanderson1/agent-toolkit-cli/issues/341)) ([bbb909a](https://github.com/ajanderson1/agent-toolkit-cli/commit/bbb909a0c8ca0b008dd148a57c750328d2c1266e))
* **solutions:** ADRs for bundle/plugin capability on clone-and-project ([1392bfe](https://github.com/ajanderson1/agent-toolkit-cli/commit/1392bfeb204c0935c2fe1818ddd765bde978e6f7))
* **spec,plan:** correct skills-split after critical review ([#341](https://github.com/ajanderson1/agent-toolkit-cli/issues/341)) ([df7f309](https://github.com/ajanderson1/agent-toolkit-cli/commit/df7f30983cbe089eb84a6493f9cb827c737bd98e))
* **spec,plan:** resolve critical-review findings for [#330](https://github.com/ajanderson1/agent-toolkit-cli/issues/330) ([fcdb1e2](https://github.com/ajanderson1/agent-toolkit-cli/commit/fcdb1e2f50f2f8ae8b3f2b5da8000f1274fd4c01))
* **spec:** fix SHA-pinned pi-extension add ([#330](https://github.com/ajanderson1/agent-toolkit-cli/issues/330)) ([d9ee095](https://github.com/ajanderson1/agent-toolkit-cli/commit/d9ee095635ec1952dc93975adfe3f05335242dd0))
* **spec:** split ajanderson1/skills into category repos ([#341](https://github.com/ajanderson1/agent-toolkit-cli/issues/341)) ([903e104](https://github.com/ajanderson1/agent-toolkit-cli/commit/903e104ea153098725c258c72870548d3a486044))

## [3.6.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.6.1...v3.6.2) (2026-06-09)


### Features

* **instructions:** doctor detects and adopts an unmanaged CLAUDE.md as AGENTS.md ([#340](https://github.com/ajanderson1/agent-toolkit-cli/issues/340)) ([09852da](https://github.com/ajanderson1/agent-toolkit-cli/commit/09852da50931a9c68d1b1fa10ae513e77dda02cd)), closes [#337](https://github.com/ajanderson1/agent-toolkit-cli/issues/337)


### Bug Fixes

* align all 'list' command output into padded human-readable tables ([#338](https://github.com/ajanderson1/agent-toolkit-cli/issues/338)) ([dcc266b](https://github.com/ajanderson1/agent-toolkit-cli/commit/dcc266bc75b1aada6f6e1ce1af5162aa593b9882))
* **tui:** deselecting a pi extension at global scope reverts and doesn't remove it ([#339](https://github.com/ajanderson1/agent-toolkit-cli/issues/339)) ([6d7b52e](https://github.com/ajanderson1/agent-toolkit-cli/commit/6d7b52e5e33deee37923f206da5b7f5905608d86))
* **tui:** sync sidebar Kind highlight to the active kind ([#328](https://github.com/ajanderson1/agent-toolkit-cli/issues/328)) ([#334](https://github.com/ajanderson1/agent-toolkit-cli/issues/334)) ([9a5ee52](https://github.com/ajanderson1/agent-toolkit-cli/commit/9a5ee520183a2e02ec23f7879dcb85dbc6ed8946))

## [3.6.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.6.0...v3.6.1) (2026-06-08)


### Bug Fixes

* **skill:** detect upstream default branch instead of assuming main ([#332](https://github.com/ajanderson1/agent-toolkit-cli/issues/332)) ([a46099f](https://github.com/ajanderson1/agent-toolkit-cli/commit/a46099ff00590ce4607d281a2e8f3a08c36c020c))


### Documentation

* **mcp:** v3 foundations plan + empty-{} failure-mode note ([b6c45c2](https://github.com/ajanderson1/agent-toolkit-cli/commit/b6c45c22a5ba12339a9b89c2007358acccbfa13e))

## [3.6.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.5.3...v3.6.0) (2026-06-07)


### Features

* **tui:** add instruction kind to the TUI ([#323](https://github.com/ajanderson1/agent-toolkit-cli/issues/323)) ([5484480](https://github.com/ajanderson1/agent-toolkit-cli/commit/5484480d4ed5c08945f48495e5684736c0c781e8)), closes [#319](https://github.com/ajanderson1/agent-toolkit-cli/issues/319)


### Bug Fixes

* **tui:** preserve view-pane position when toggling a checkbox ([#326](https://github.com/ajanderson1/agent-toolkit-cli/issues/326)) ([d5961f5](https://github.com/ajanderson1/agent-toolkit-cli/commit/d5961f5726653aee26809e369b1f04ae1a1e8c51)), closes [#321](https://github.com/ajanderson1/agent-toolkit-cli/issues/321)
* **tui:** rebind scope toggle from 's' to ctrl+g ([#325](https://github.com/ajanderson1/agent-toolkit-cli/issues/325)) ([9ceba4b](https://github.com/ajanderson1/agent-toolkit-cli/commit/9ceba4bf6883844b81bc77565a32df1067624277)), closes [#320](https://github.com/ajanderson1/agent-toolkit-cli/issues/320)

## [3.5.3](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.5.2...v3.5.3) (2026-06-03)


### Bug Fixes

* clean up orphan canonical on failed agent add, teach doctor to detect them ([#313](https://github.com/ajanderson1/agent-toolkit-cli/issues/313)) ([#316](https://github.com/ajanderson1/agent-toolkit-cli/issues/316)) ([b8ce543](https://github.com/ajanderson1/agent-toolkit-cli/commit/b8ce5432247121506052fa31fadbf65c542167c0))
* delete instructions-lock.json when last entry removed ([#317](https://github.com/ajanderson1/agent-toolkit-cli/issues/317)) ([8dd9912](https://github.com/ajanderson1/agent-toolkit-cli/commit/8dd991250bc1dc7d638e846a61ee48c21d6dcdc1))
* doctor squatted_projection finding + inventory symlink-ownership gate ([#314](https://github.com/ajanderson1/agent-toolkit-cli/issues/314)) ([#315](https://github.com/ajanderson1/agent-toolkit-cli/issues/315)) ([89eb5e9](https://github.com/ajanderson1/agent-toolkit-cli/commit/89eb5e979e5f4f4428da5d1f4c25035988f691a7))

## [3.5.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.5.1...v3.5.2) (2026-06-01)


### Bug Fixes

* restore wheel force-include of harness matrix ([#305](https://github.com/ajanderson1/agent-toolkit-cli/issues/305) redux) ([#310](https://github.com/ajanderson1/agent-toolkit-cli/issues/310)) ([7c74c0b](https://github.com/ajanderson1/agent-toolkit-cli/commit/7c74c0b95cd0f8f1e7f4fc72145e2bc7fc6a731e))

## [3.5.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.5.0...v3.5.1) (2026-06-01)


### Bug Fixes

* **303:** agent uninstall must be non-destructive ([#306](https://github.com/ajanderson1/agent-toolkit-cli/issues/306)) ([86f5aea](https://github.com/ajanderson1/agent-toolkit-cli/commit/86f5aea84fccc6c72d6695cec4595727a3d968fb))
* agent-kind minor fixes — status scope, add validation, TUI label ([#304](https://github.com/ajanderson1/agent-toolkit-cli/issues/304)) ([#307](https://github.com/ajanderson1/agent-toolkit-cli/issues/307)) ([9d39ed8](https://github.com/ajanderson1/agent-toolkit-cli/commit/9d39ed8f498ae8db94cf3a98210be9ce2813ac67))
* instructions list crashes on packaged installs ([#305](https://github.com/ajanderson1/agent-toolkit-cli/issues/305)) ([#308](https://github.com/ajanderson1/agent-toolkit-cli/issues/308)) ([2ef5712](https://github.com/ajanderson1/agent-toolkit-cli/commit/2ef57128362eed1666fc88bac6d1a0362e7a4798))

## [3.5.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.4.0...v3.5.0) (2026-05-31)


### Features

* agent kind TUI tab — completes agent-native TUI parity ([#252](https://github.com/ajanderson1/agent-toolkit-cli/issues/252)) ([#301](https://github.com/ajanderson1/agent-toolkit-cli/issues/301)) ([48a5430](https://github.com/ajanderson1/agent-toolkit-cli/commit/48a543074ffdbc974425994473c758209e53dc62))

## [3.4.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.3.0...v3.4.0) (2026-05-31)


### Features

* agent kind CLI group (add/install/uninstall/remove/list/status/+lifecycle) ([#297](https://github.com/ajanderson1/agent-toolkit-cli/issues/297)) ([e2e89f6](https://github.com/ajanderson1/agent-toolkit-cli/commit/e2e89f6daf4e47e13603ba17f6182692078d560d)), closes [#252](https://github.com/ajanderson1/agent-toolkit-cli/issues/252)
* agent kind PR4 — enable aider-desk + dexto subagent cells (self-owned writes) ([#252](https://github.com/ajanderson1/agent-toolkit-cli/issues/252)) ([#300](https://github.com/ajanderson1/agent-toolkit-cli/issues/300)) ([c82d406](https://github.com/ajanderson1/agent-toolkit-cli/commit/c82d406f55232308308983900c72457d626b7946))


### Refactors

* agent kind PR3 — universal→general rename + per-kind arch guard ([#252](https://github.com/ajanderson1/agent-toolkit-cli/issues/252)) ([#299](https://github.com/ajanderson1/agent-toolkit-cli/issues/299)) ([3822077](https://github.com/ajanderson1/agent-toolkit-cli/commit/3822077041ff60d775d0fafc9e7b54780d3abdde))

## [3.3.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v3.2.0...v3.3.0) (2026-05-31)


### Features

* pi-extension kind PR2a — write path (settings writer + add/install/uninstall/remove) ([#293](https://github.com/ajanderson1/agent-toolkit-cli/issues/293)) ([293fdda](https://github.com/ajanderson1/agent-toolkit-cli/commit/293fddaadb57ea38efa0e9a5c7fa7006b65ce315))
* pi-extension kind PR2b — git lifecycle + adoption (import/update/push/reset/doctor) ([#295](https://github.com/ajanderson1/agent-toolkit-cli/issues/295)) ([82cce74](https://github.com/ajanderson1/agent-toolkit-cli/commit/82cce741389baf2f40bde73a0ae8186f7d4c5246))
* pi-extension kind PR3 — TUI grid + kind sidebar (agent-native parity) ([#296](https://github.com/ajanderson1/agent-toolkit-cli/issues/296)) ([e8f442a](https://github.com/ajanderson1/agent-toolkit-cli/commit/e8f442ad1084a0e226d52736601ef0ae57adc4fe))

## [3.2.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.15.0...v3.2.0) (2026-05-30)


### Documentation

* add v3.2.0 milestone to strategy ([#290](https://github.com/ajanderson1/agent-toolkit-cli/issues/290)) ([f27ce47](https://github.com/ajanderson1/agent-toolkit-cli/commit/f27ce4713a5b355a6e24f83fa66b2e4c0e61b74b))

## [2.15.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.14.3...v2.15.0) (2026-05-30)


### Features

* instructions asset kind — link AGENTS.md/CLAUDE.md across harnesses ([#269](https://github.com/ajanderson1/agent-toolkit-cli/issues/269)) ([#283](https://github.com/ajanderson1/agent-toolkit-cli/issues/283)) ([ef73ce6](https://github.com/ajanderson1/agent-toolkit-cli/commit/ef73ce6ce35992cbe46a48b0e18b2c8ae66b5b60))
* pi-extension kind PR1 — read-only inventory (list/status) ([#273](https://github.com/ajanderson1/agent-toolkit-cli/issues/273)) ([#286](https://github.com/ajanderson1/agent-toolkit-cli/issues/286)) ([aff5467](https://github.com/ajanderson1/agent-toolkit-cli/commit/aff546768fe9301f1b495a5f2c2a32ee22241fc6))


### Documentation

* v3 follow-up plans + decisions (pi-ext PR2 write-path, extensions[] classification, agent PR3-5, disabled-cells) ([#287](https://github.com/ajanderson1/agent-toolkit-cli/issues/287)) ([5328e60](https://github.com/ajanderson1/agent-toolkit-cli/commit/5328e6031df0777f9f7eff594d3c9cddcb9dee75))

## [2.14.3](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.14.2...v2.14.3) (2026-05-29)


### Bug Fixes

* skill push publishes committed-but-unpushed changes instead of reporting clean ([#280](https://github.com/ajanderson1/agent-toolkit-cli/issues/280)) ([#281](https://github.com/ajanderson1/agent-toolkit-cli/issues/281)) ([0001723](https://github.com/ajanderson1/agent-toolkit-cli/commit/00017238bd50c4e87ca40b7a74c3873f1b3281d5))

## [2.14.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.14.1...v2.14.2) (2026-05-29)


### Bug Fixes

* non-TTY prompt crash + monorepo status/cache staleness ([#274](https://github.com/ajanderson1/agent-toolkit-cli/issues/274), [#276](https://github.com/ajanderson1/agent-toolkit-cli/issues/276)) ([#279](https://github.com/ajanderson1/agent-toolkit-cli/issues/279)) ([2679522](https://github.com/ajanderson1/agent-toolkit-cli/commit/267952288c6b3eb1aca42cb47c4b0725d12cad3d))


### Documentation

* pi-extension-kind design + repoint project lock to skills monorepo ([#277](https://github.com/ajanderson1/agent-toolkit-cli/issues/277)) ([2563360](https://github.com/ajanderson1/agent-toolkit-cli/commit/2563360453356dffb1d7830d1809734bd70e6519))

## [2.14.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.14.0...v2.14.1) (2026-05-29)


### Bug Fixes

* correct monorepo handling for nested (multi-segment) skill paths ([#271](https://github.com/ajanderson1/agent-toolkit-cli/issues/271)) ([63e1271](https://github.com/ajanderson1/agent-toolkit-cli/commit/63e12710c479e62e8f85fb4f72e360123c965b99))

## [2.14.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.13.0...v2.14.0) (2026-05-28)


### Features

* owned-monorepo support for skill add/push/update/status ([#260](https://github.com/ajanderson1/agent-toolkit-cli/issues/260)) ([#264](https://github.com/ajanderson1/agent-toolkit-cli/issues/264)) ([ed03bf5](https://github.com/ajanderson1/agent-toolkit-cli/commit/ed03bf53e138b4154f4a4fe43c7c40caf2617182))
* skill migrate-to-monorepo ([#258](https://github.com/ajanderson1/agent-toolkit-cli/issues/258) PR2) ([#266](https://github.com/ajanderson1/agent-toolkit-cli/issues/266)) ([89a22f8](https://github.com/ajanderson1/agent-toolkit-cli/commit/89a22f8ff92d6e31c551cb6098e3776cebb7b649))

## [2.13.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.12.1...v2.13.0) (2026-05-27)


### Features

* add fuzzy-filter search box to the TUI ([#262](https://github.com/ajanderson1/agent-toolkit-cli/issues/262)) ([d6cb183](https://github.com/ajanderson1/agent-toolkit-cli/commit/d6cb18334c24d75676b13f3e66a5edaa4eebba9f))


### Bug Fixes

* shallow-clone source repos in skill import ([#259](https://github.com/ajanderson1/agent-toolkit-cli/issues/259)) ([#261](https://github.com/ajanderson1/agent-toolkit-cli/issues/261)) ([5af9a79](https://github.com/ajanderson1/agent-toolkit-cli/commit/5af9a791bac8066f503bc640cb1aa34d9339ffec))

## [2.12.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.12.0...v2.12.1) (2026-05-27)


### Bug Fixes

* release 2.12.1 (TUI counters [#250](https://github.com/ajanderson1/agent-toolkit-cli/issues/250), SSH-only import [#251](https://github.com/ajanderson1/agent-toolkit-cli/issues/251)) ([2be7797](https://github.com/ajanderson1/agent-toolkit-cli/commit/2be7797aec44f6317bdb9f39e8452e5932d59e77))

## [2.12.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.11.2...v2.12.0) (2026-05-26)


### Features

* **skill:** add import command skeleton (guard + notes) ([cc3b104](https://github.com/ajanderson1/agent-toolkit-cli/commit/cc3b1046646b9be183249d358368e4e3e4c8d5e2))
* **skill:** cross-machine library sync via `skill import` ([40fe639](https://github.com/ajanderson1/agent-toolkit-cli/commit/40fe639f95d31e93c6808787e2b05d1d23f9188a))
* **skill:** extract reconstruct_skill_into_library helper ([5432e48](https://github.com/ajanderson1/agent-toolkit-cli/commit/5432e48b1bd3cf57257889c6deed818811e6fa16))
* **skill:** import adds new single-repo skill pinned to recorded sha ([a370ec0](https://github.com/ajanderson1/agent-toolkit-cli/commit/a370ec0379f3ed2961f7ba9155d60f9803a9a5ed))
* **skill:** import reconstructs monorepo entries via parent symlink ([c879305](https://github.com/ajanderson1/agent-toolkit-cli/commit/c879305598a4841f4dca4e839f9c71af3e379f5f))


### Documentation

* skill import (cross-machine library sync) design spec ([98651df](https://github.com/ajanderson1/agent-toolkit-cli/commit/98651df4bc0c3426cdaa404b505cb170e4f14e2d))
* skill import implementation plan ([a54d355](https://github.com/ajanderson1/agent-toolkit-cli/commit/a54d355c83a8ca2b8ceb4e753e23fad2b7839098))

## [2.11.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.11.1...v2.11.2) (2026-05-25)


### Bug Fixes

* **skill:** multi-match error suggests explicit-subpath commands ([#243](https://github.com/ajanderson1/agent-toolkit-cli/issues/243)) ([67a3abf](https://github.com/ajanderson1/agent-toolkit-cli/commit/67a3abf04e2c02f496d02fd6acff34a4169cf7ad))

## [2.11.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.11.0...v2.11.1) (2026-05-25)


### Bug Fixes

* **skill install:** surface stray-symlink failures and point at doctor ([#229](https://github.com/ajanderson1/agent-toolkit-cli/issues/229)) ([2d9858f](https://github.com/ajanderson1/agent-toolkit-cli/commit/2d9858fbc38039d733dd218f7e8ba6828bc546ac))

## [2.11.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.10.1...v2.11.0) (2026-05-25)


### Features

* **doctor:** flag orphan real-dir strays in ~/.agents/skills ([#231](https://github.com/ajanderson1/agent-toolkit-cli/issues/231)) ([#241](https://github.com/ajanderson1/agent-toolkit-cli/issues/241)) ([ae74393](https://github.com/ajanderson1/agent-toolkit-cli/commit/ae74393d814d6a951afa7ac8ee3ec26575f1da79))


### Bug Fixes

* **tui:** allow universal uninstall at project scope ([#232](https://github.com/ajanderson1/agent-toolkit-cli/issues/232)) ([#239](https://github.com/ajanderson1/agent-toolkit-cli/issues/239)) ([f623abe](https://github.com/ajanderson1/agent-toolkit-cli/commit/f623abe771a35e3cd5cbe7a77f0fa97c05facbc8))

## [2.10.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.10.0...v2.10.1) (2026-05-25)


### Bug Fixes

* **skill:** universal bundle toggle works at project scope ([#237](https://github.com/ajanderson1/agent-toolkit-cli/issues/237)) ([cffb49a](https://github.com/ajanderson1/agent-toolkit-cli/commit/cffb49a775e0e5985a9d7656f11e6de1f829f895))

## [2.10.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.9.0...v2.10.0) (2026-05-25)


### Features

* **skill:** relocate project canonical out of the project tree ([#235](https://github.com/ajanderson1/agent-toolkit-cli/issues/235)) ([2551db3](https://github.com/ajanderson1/agent-toolkit-cli/commit/2551db39dc19def7563f83543b84a8da74ac43de))

## [2.9.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.8.1...v2.9.0) (2026-05-25)


### Features

* **skill install:** project-scope monorepo support via parent-clone + symlink ([#233](https://github.com/ajanderson1/agent-toolkit-cli/issues/233)) ([503092f](https://github.com/ajanderson1/agent-toolkit-cli/commit/503092f2c0c2ec2c91472ed30551ef8e7dc8a906))

## [2.8.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.8.0...v2.8.1) (2026-05-23)


### Bug Fixes

* **skill doctor:** detect and clean stray projection symlinks ([#227](https://github.com/ajanderson1/agent-toolkit-cli/issues/227)) ([c7b6f28](https://github.com/ajanderson1/agent-toolkit-cli/commit/c7b6f288dc7586f6140431815c8975e154ce74a6))

## [2.8.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.7.2...v2.8.0) (2026-05-23)


### Features

* **skill reset:** support monorepo skills via parent-clone reset ([#225](https://github.com/ajanderson1/agent-toolkit-cli/issues/225)) ([d15f530](https://github.com/ajanderson1/agent-toolkit-cli/commit/d15f530829093b195b112eef2c1c01db64fa33bd)), closes [#220](https://github.com/ajanderson1/agent-toolkit-cli/issues/220)

## [2.7.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.7.1...v2.7.2) (2026-05-22)


### Bug Fixes

* **skill push:** open PR by default; --direct preserves push-to-tracked-ref ([#224](https://github.com/ajanderson1/agent-toolkit-cli/issues/224)) ([5751ade](https://github.com/ajanderson1/agent-toolkit-cli/commit/5751ade99e216b26ecacb294c51802c2f81a54ab))
* **skill scope:** default to global for push/update/reset/doctor ([#220](https://github.com/ajanderson1/agent-toolkit-cli/issues/220)) ([#222](https://github.com/ajanderson1/agent-toolkit-cli/issues/222)) ([9b141d8](https://github.com/ajanderson1/agent-toolkit-cli/commit/9b141d8d997f10fa2556d434e6b9277c5a66ce9b))

## [2.7.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.7.0...v2.7.1) (2026-05-22)


### Bug Fixes

* **doctor:** cover trailing-slash + `ssh://` URL variants in `_normalise_git_url` ([#215](https://github.com/ajanderson1/agent-toolkit-cli/issues/215)) ([6e4c86b](https://github.com/ajanderson1/agent-toolkit-cli/commit/6e4c86b8e7346cbeb700059e7a2b0b1a4a58e1d3))
* **skill list:** default to global scope when no project lock at cwd ([#216](https://github.com/ajanderson1/agent-toolkit-cli/issues/216)) ([e22265e](https://github.com/ajanderson1/agent-toolkit-cli/commit/e22265e76e05bb3b7737a5faa345ddd2fe266a19))
* **skill remove:** handle monorepo symlinks ([#207](https://github.com/ajanderson1/agent-toolkit-cli/issues/207)) ([#217](https://github.com/ajanderson1/agent-toolkit-cli/issues/217)) ([9ac15e0](https://github.com/ajanderson1/agent-toolkit-cli/commit/9ac15e0d906ff332d2595fed177b84740c679cd0))
* **tui:** agent-toolkit-tui --version prints version, exits 0 ([#211](https://github.com/ajanderson1/agent-toolkit-cli/issues/211)) ([#213](https://github.com/ajanderson1/agent-toolkit-cli/issues/213)) ([f82a99d](https://github.com/ajanderson1/agent-toolkit-cli/commit/f82a99daaf4e4a8f5e6b512fc6f0698a94d18cbe))
* **tui:** four info-panel cosmetic issues ([#212](https://github.com/ajanderson1/agent-toolkit-cli/issues/212)) ([#219](https://github.com/ajanderson1/agent-toolkit-cli/issues/219)) ([7d79232](https://github.com/ajanderson1/agent-toolkit-cli/commit/7d79232ed80f50f20d899a5340241220d4eeb411))

## [2.7.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.6.0...v2.7.0) (2026-05-22)


### Features

* **tui:** drop Description column; surface description in slug-cell info modal ([#200](https://github.com/ajanderson1/agent-toolkit-cli/issues/200)) ([c6a583f](https://github.com/ajanderson1/agent-toolkit-cli/commit/c6a583f92354581d933b084d107ab0d7dd8570f9))


### Bug Fixes

* **doctor:** classify v2.1 bundle target as drift, not foreign ([#192](https://github.com/ajanderson1/agent-toolkit-cli/issues/192)) ([#205](https://github.com/ajanderson1/agent-toolkit-cli/issues/205)) ([d9b4385](https://github.com/ajanderson1/agent-toolkit-cli/commit/d9b4385c9ef15e3de8edb646a04bf1af7b011e38))
* **doctor:** normalise ssh ↔ https git URLs in _normalise_git_url ([#201](https://github.com/ajanderson1/agent-toolkit-cli/issues/201)) ([a6aab7e](https://github.com/ajanderson1/agent-toolkit-cli/commit/a6aab7e4da80ec26641719a5e755835b5eb9272e)), closes [#191](https://github.com/ajanderson1/agent-toolkit-cli/issues/191)
* **skill add:** reject ambiguous owner/repo@&lt;ref&gt;/&lt;subpath&gt; shorthand ([#203](https://github.com/ajanderson1/agent-toolkit-cli/issues/203)) ([36783f1](https://github.com/ajanderson1/agent-toolkit-cli/commit/36783f1c8de025f928d431884ea9e062e437aa12))
* **skill-git:** inject synthetic identity in commit_all() ([#197](https://github.com/ajanderson1/agent-toolkit-cli/issues/197)) ([#206](https://github.com/ajanderson1/agent-toolkit-cli/issues/206)) ([22097a2](https://github.com/ajanderson1/agent-toolkit-cli/commit/22097a2e1dfc9ba444b64efcdbe3d0fb9b4cc475))
* **skill-source:** align `_sanitize_ref` with `git check-ref-format` ([#204](https://github.com/ajanderson1/agent-toolkit-cli/issues/204)) ([f685397](https://github.com/ajanderson1/agent-toolkit-cli/commit/f68539725e425006f7d6dd4436836e8977d8c198))

## [2.6.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.5.0...v2.6.0) (2026-05-22)


### Features

* **tui:** re-implement globally-installed indicator in Project scope ([#188](https://github.com/ajanderson1/agent-toolkit-cli/issues/188)) ([#195](https://github.com/ajanderson1/agent-toolkit-cli/issues/195)) ([9cffcde](https://github.com/ajanderson1/agent-toolkit-cli/commit/9cffcdeaf92caaaf2b7b0d7d2c2e3fc3d8b0a7bc))

## [2.5.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.4.0...v2.5.0) (2026-05-22)


### Features

* skill doctor + TUI i cell-info modal ([#190](https://github.com/ajanderson1/agent-toolkit-cli/issues/190)) ([14fe8c9](https://github.com/ajanderson1/agent-toolkit-cli/commit/14fe8c94f840107082dd3a85b6411dde8f27322d))
* **skills:** monorepo skills are locally editable (three-way merge + clean/dirty state) ([#189](https://github.com/ajanderson1/agent-toolkit-cli/issues/189)) ([421c424](https://github.com/ajanderson1/agent-toolkit-cli/commit/421c4245cfe4a585aa665e2d473079353335e6c5))

## [2.4.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.3.3...v2.4.0) (2026-05-21)


### Features

* **cli:** accept `skills` as alias for `skill` command group ([#183](https://github.com/ajanderson1/agent-toolkit-cli/issues/183)) ([cb2d1fe](https://github.com/ajanderson1/agent-toolkit-cli/commit/cb2d1fe9d721e9159956d5e40e2d202a439cf71b)), closes [#180](https://github.com/ajanderson1/agent-toolkit-cli/issues/180)
* **tui:** add description and upstream-source columns to SkillGrid ([#186](https://github.com/ajanderson1/agent-toolkit-cli/issues/186)) ([4acdd97](https://github.com/ajanderson1/agent-toolkit-cli/commit/4acdd972b5cb701d024bbf911d2481b65accbcf1)), closes [#182](https://github.com/ajanderson1/agent-toolkit-cli/issues/182)


### Bug Fixes

* **skill add:** accept owner/repo@&lt;ref&gt;[/&lt;subpath&gt;] shorthand ([#185](https://github.com/ajanderson1/agent-toolkit-cli/issues/185)) ([6dd7cba](https://github.com/ajanderson1/agent-toolkit-cli/commit/6dd7cba72ff5a9ba6839ba04614997a0888b023d))

## [2.3.3](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.3.2...v2.3.3) (2026-05-21)


### Features

* **tui:** ⓘ info affordance on Universal column header ([#167](https://github.com/ajanderson1/agent-toolkit-cli/issues/167)) ([#175](https://github.com/ajanderson1/agent-toolkit-cli/issues/175)) ([ba7943e](https://github.com/ajanderson1/agent-toolkit-cli/commit/ba7943eb060eb0efe4754f216a45c2c5741bc470))


### Bug Fixes

* **deps:** add pyyaml as runtime dependency ([#178](https://github.com/ajanderson1/agent-toolkit-cli/issues/178)) ([f5ef948](https://github.com/ajanderson1/agent-toolkit-cli/commit/f5ef9489b1eb03d023f917524003adc9947e0e59))

## [2.3.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.3.1...v2.3.2) (2026-05-21)


### Documentation

* **cli:** add Examples section to `skill --help` ([#171](https://github.com/ajanderson1/agent-toolkit-cli/issues/171)) ([96d8f91](https://github.com/ajanderson1/agent-toolkit-cli/commit/96d8f91307f8ee5c321cf7aa7aa19b4054b3c03f))

## [2.3.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v2.3.0...v2.3.1) (2026-05-21)


### Bug Fixes

* **tui:** align with v2.3 skill-only CLI ([#166](https://github.com/ajanderson1/agent-toolkit-cli/issues/166)) ([a52929b](https://github.com/ajanderson1/agent-toolkit-cli/commit/a52929be4be3e4695c13d2ef9b2e563045e3316f))

## [2.3.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v1.0.0...v2.3.0) (2026-05-21)


### ⚠ BREAKING CHANGES

* **cli:** All pre-v2 CLI commands (`check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink`) were removed in [#160](https://github.com/ajanderson1/agent-toolkit-cli/issues/160). Only `skill` remains. Install from the `v1.0.0` tag to restore the legacy surface: `uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`. See tracker [#163](https://github.com/ajanderson1/agent-toolkit-cli/issues/163) for the per-command v2 rebuild status.
* **tui:** The TUI no longer surfaces agent/command/hook/mcp/plugin/pi-extension tabs by default. `AGENT_TOOLKIT_TUI_LEGACY=1` restores the old layout.

### Features

* **skill:** Lock-file-driven `skill add | list | status | update | push | remove` — byte-compatible with `vercel-labs/skills`. ([#154](https://github.com/ajanderson1/agent-toolkit-cli/pull/154))
* **skill-agents:** 55-agent catalog ported from `vercel-labs/skills`; universal vs. per-harness install model.
* **tui:** Interactive `SkillGrid` (claude-code + pi) replaces the legacy multi-tab default.
* **skill:** Interactive `skill` wizard via `questionary`.
* **v2.2:** library/install split + universal bundle ([#158](https://github.com/ajanderson1/agent-toolkit-cli/pull/158)).

### Bug Fixes

* **tui:** `apply-skill` crash with bad git clone URL for v1 global lock ([#161](https://github.com/ajanderson1/agent-toolkit-cli/pull/161))

### Chores

* **cli:** Deprecate pre-v2 CLI commands; keep only `skill` ([#164](https://github.com/ajanderson1/agent-toolkit-cli/pull/164)). 97 → 19 source files; 1129 → 216 tests; dropped `jsonschema` / `pyyaml` / `ruamel.yaml` / `tomlkit` deps.

## [1.0.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.8.0...v1.0.0) (2026-05-20)


### Features

* claude/plugin asset kind — config_file adapter for Claude plugins ([#149](https://github.com/ajanderson1/agent-toolkit-cli/issues/149)) ([#153](https://github.com/ajanderson1/agent-toolkit-cli/issues/153)) ([19e745f](https://github.com/ajanderson1/agent-toolkit-cli/commit/19e745f5eaf7af8162f2dbef225dc2328cf5e19b))
* **skills:** split harness-facing SKILL.md frontmatter from toolkit sidecar ([#150](https://github.com/ajanderson1/agent-toolkit-cli/issues/150)) ([#151](https://github.com/ajanderson1/agent-toolkit-cli/issues/151)) ([27896cb](https://github.com/ajanderson1/agent-toolkit-cli/commit/27896cb75cb0542aeea8719a44958ffb6c328e91))

## [0.8.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.7.4...v0.8.0) (2026-05-19)


### Features

* **codex:** (codex, agent) adapter — per-asset TOML translator ([#146](https://github.com/ajanderson1/agent-toolkit-cli/issues/146)) ([d80ea10](https://github.com/ajanderson1/agent-toolkit-cli/commit/d80ea10482b3c86cdf42f44374ddeebbeea6f2c8))

## [0.7.4](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.7.3...v0.7.4) (2026-05-19)


### Bug Fixes

* **list-json:** report 'unlinked' for declared-but-unwired MCP/hook cells ([#145](https://github.com/ajanderson1/agent-toolkit-cli/issues/145)) ([395342f](https://github.com/ajanderson1/agent-toolkit-cli/commit/395342f7d0b634d628fbfa480c613cd489813e3a)), closes [#141](https://github.com/ajanderson1/agent-toolkit-cli/issues/141)
* **unlink:** prune stale projections in per-asset path when slug absent ([#142](https://github.com/ajanderson1/agent-toolkit-cli/issues/142)) ([#143](https://github.com/ajanderson1/agent-toolkit-cli/issues/143)) ([02771f6](https://github.com/ajanderson1/agent-toolkit-cli/commit/02771f6c51f068f131efcaa77193f7ee9d727c5d))

## [0.7.3](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.7.2...v0.7.3) (2026-05-19)


### Bug Fixes

* **link:** [#137](https://github.com/ajanderson1/agent-toolkit-cli/issues/137) (gemini, command) slot pruned by its own sweep ([#138](https://github.com/ajanderson1/agent-toolkit-cli/issues/138)) ([5935ce2](https://github.com/ajanderson1/agent-toolkit-cli/commit/5935ce2ae8ffb466e25678db3d2f44b59efb8993))

## [0.7.2](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.7.1...v0.7.2) (2026-05-19)


### Bug Fixes

* **unlink:** prune stale projections when slug absent from allowlist ([#135](https://github.com/ajanderson1/agent-toolkit-cli/issues/135)) ([11702ed](https://github.com/ajanderson1/agent-toolkit-cli/commit/11702ed9d720f1e601543028ab9d91a1eb420909))

## [0.7.1](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.7.0...v0.7.1) (2026-05-19)


### Bug Fixes

* **mcp:** create project-scope target when absent ([#125](https://github.com/ajanderson1/agent-toolkit-cli/issues/125)) ([#133](https://github.com/ajanderson1/agent-toolkit-cli/issues/133)) ([fb0a7b1](https://github.com/ajanderson1/agent-toolkit-cli/commit/fb0a7b1faba6841fb0b7f3b616d3b52f03eb58ee))

## [0.7.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.6.0...v0.7.0) (2026-05-19)


### Features

* toolkit audit process (helpers + 20 demos + findings doc) ([#118](https://github.com/ajanderson1/agent-toolkit-cli/issues/118)) ([f2d1d0c](https://github.com/ajanderson1/agent-toolkit-cli/commit/f2d1d0c5c43383417ad3dfd7158ffa7d519c0d27))


### Bug Fixes

* **doctor:** add --strict flag tripping on WARN or FAIL ([#127](https://github.com/ajanderson1/agent-toolkit-cli/issues/127)) ([77c959d](https://github.com/ajanderson1/agent-toolkit-cli/commit/77c959d16c2c0ffc749d34fdfbba5bae2414a971))
* **doctor:** detect symlink slots replaced by file or directory under claude ([#129](https://github.com/ajanderson1/agent-toolkit-cli/issues/129)) ([f9b85e5](https://github.com/ajanderson1/agent-toolkit-cli/commit/f9b85e564d3b60435100a79591f27f4087206aa0))
* **doctor:** handle broken codex TOML without crashing ([#122](https://github.com/ajanderson1/agent-toolkit-cli/issues/122)) ([#128](https://github.com/ajanderson1/agent-toolkit-cli/issues/128)) ([9d58cc8](https://github.com/ajanderson1/agent-toolkit-cli/commit/9d58cc8125feb2671206f2034a0aae9109280c50))
* **link:** prune stale projections on reconcile after hand-edit ([#120](https://github.com/ajanderson1/agent-toolkit-cli/issues/120)) ([#131](https://github.com/ajanderson1/agent-toolkit-cli/issues/131)) ([968d66d](https://github.com/ajanderson1/agent-toolkit-cli/commit/968d66ddb74da80bfc8ff949d97aa6edb4b767ff))
* **support:** drop (claude, hook) from matrix until adapter exists ([#132](https://github.com/ajanderson1/agent-toolkit-cli/issues/132)) ([3b27f09](https://github.com/ajanderson1/agent-toolkit-cli/commit/3b27f0923c2277223262e85723c675deffd9df17))
* **unlink:** prune `.md`-suffixed claude slots in per-asset path ([#119](https://github.com/ajanderson1/agent-toolkit-cli/issues/119)) ([#130](https://github.com/ajanderson1/agent-toolkit-cli/issues/130)) ([046b94a](https://github.com/ajanderson1/agent-toolkit-cli/commit/046b94a125588b9ac017b319e86d796aa69023fa))

## [0.6.0](https://github.com/ajanderson1/agent-toolkit-cli/compare/v0.5.1...v0.6.0) (2026-05-19)


### Features

* **doctor:** pi-advisories — drift audits project scope ([#108](https://github.com/ajanderson1/agent-toolkit-cli/issues/108)) ([#110](https://github.com/ajanderson1/agent-toolkit-cli/issues/110)) ([f857450](https://github.com/ajanderson1/agent-toolkit-cli/commit/f857450860fefd4df2679e9887cf1c25c594e1ce))
* **pi:** surface settings.json extensions[] overrides in inventory ([#116](https://github.com/ajanderson1/agent-toolkit-cli/issues/116)) ([1f05cca](https://github.com/ajanderson1/agent-toolkit-cli/commit/1f05cca24636dc49f27ad28841f834b5f55c5e49))
* **pi:** unified extension inventory + load/unload across both channels ([#106](https://github.com/ajanderson1/agent-toolkit-cli/issues/106)) ([77734a2](https://github.com/ajanderson1/agent-toolkit-cli/commit/77734a2d10779c44d594c61cd3d65f93ee8dd7b5))
* **sidecar:** metadata discovery for skill + mcp (PR 1 of 2) ([#104](https://github.com/ajanderson1/agent-toolkit-cli/issues/104)) ([aee34b4](https://github.com/ajanderson1/agent-toolkit-cli/commit/aee34b4ceb7189874c68c9148b63495226651676))
* **sidecar:** remove legacy MCP path + activate doctor --fix writes (PR 3 of 2) ([#114](https://github.com/ajanderson1/agent-toolkit-cli/issues/114)) ([a990fa1](https://github.com/ajanderson1/agent-toolkit-cli/commit/a990fa158f7e4028d58f9ef654e8b55be4911b8b))
* **tui:** pi tab u/p toggle bindings ([#107](https://github.com/ajanderson1/agent-toolkit-cli/issues/107)) ([#115](https://github.com/ajanderson1/agent-toolkit-cli/issues/115)) ([3aa7add](https://github.com/ajanderson1/agent-toolkit-cli/commit/3aa7add79ea6783d4aa11d3e94d0c3c24a879f26))


### Bug Fixes

* **walker:** mutex predicate requires toolkit-shape frontmatter ([#117](https://github.com/ajanderson1/agent-toolkit-cli/issues/117)) ([600a3cc](https://github.com/ajanderson1/agent-toolkit-cli/commit/600a3cc34f0046d7270e9042342ebaf5d3067cc6))

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

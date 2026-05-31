# Changelog

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

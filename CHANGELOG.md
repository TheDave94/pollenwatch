# Changelog

## [3.1.0](https://github.com/TheDave94/pollenwatch/compare/v3.0.2...v3.1.0) (2026-06-29)


### Features

* **analytics:** flag divergence on any non-unanimity (closes [#1](https://github.com/TheDave94/pollenwatch/issues/1)) ([a4eed05](https://github.com/TheDave94/pollenwatch/commit/a4eed0545aabe24c782af46527d3e8b29fc2a673))

## [3.0.2](https://github.com/TheDave94/pollenwatch/compare/v3.0.1...v3.0.2) (2026-06-20)


### Documentation

* reusable screenshot harness + layout/state gallery ([223bf84](https://github.com/TheDave94/pollenwatch/commit/223bf84736cffa0d84f8252cf01756b2bdf2d92b))

## [3.0.1](https://github.com/TheDave94/pollenwatch/compare/v3.0.0...v3.0.1) (2026-06-19)


### Bug Fixes

* **docs:** correct README to match shipped v3.0.0 ([237e8c3](https://github.com/TheDave94/pollenwatch/commit/237e8c34596676e6bc793192e116c6ef58632748))

## [3.0.0](https://github.com/TheDave94/pollenwatch/compare/v2.4.0...v3.0.0) (2026-06-19)


### ⚠ BREAKING CHANGES

* collapse config-entry migration + unify the species key

### Features

* **diagnostics:** implement config-entry diagnostics (location + key redaction) ([d18a788](https://github.com/TheDave94/pollenwatch/commit/d18a7880440798228b0c42543a74e14bdbd9b067))
* **thresholds:** refine ash onset 10→18 (cited) ([b10cf20](https://github.com/TheDave94/pollenwatch/commit/b10cf20fa99b9aef8e19d78582a3ea7eb3939ebf))


### Bug Fixes

* **config_flow:** preserve user input on error re-render ([52b1b9f](https://github.com/TheDave94/pollenwatch/commit/52b1b9f094f8e756dff5069a5a1c3725ea7918d9))
* **sensor:** guard empty current_time in forecast slice ([5257d67](https://github.com/TheDave94/pollenwatch/commit/5257d67ff93eed2293f3818f1f966362b12a0e88))


### Code Refactoring

* collapse config-entry migration + unify the species key ([56829bf](https://github.com/TheDave94/pollenwatch/commit/56829bf3ee36b6b2e8d5a174765251d04b9fc18b))

## [2.4.0](https://github.com/TheDave94/pollenwatch/compare/v2.3.0...v2.4.0) (2026-06-02)


### Features

* add bars multi-species layout to bundled card ([#19](https://github.com/TheDave94/pollenwatch/issues/19)) ([6a6ca0c](https://github.com/TheDave94/pollenwatch/commit/6a6ca0c8ba9c752b2ad1240563cd782b2fe7b025))
* add card layout option + pollenwatch/config WS endpoint ([#17](https://github.com/TheDave94/pollenwatch/issues/17)) ([da8d2fd](https://github.com/TheDave94/pollenwatch/commit/da8d2fd4e955026d048c4e07c1a35c10733dea77))
* add compact multi-species layout to bundled card ([#21](https://github.com/TheDave94/pollenwatch/issues/21)) ([ee3e900](https://github.com/TheDave94/pollenwatch/commit/ee3e900a861d6bc3213f81518550f6085c83e372))
* add tier-1 prerelease discovery gate ([#23](https://github.com/TheDave94/pollenwatch/issues/23)) ([4a0381f](https://github.com/TheDave94/pollenwatch/commit/4a0381faa94081b91796ad57133c6981d210fb02))
* add tiles multi-species layout to bundled card ([#22](https://github.com/TheDave94/pollenwatch/issues/22)) ([10b3871](https://github.com/TheDave94/pollenwatch/commit/10b3871f9acc816dafb526ea81ef22757f1ea303))

## [2.3.0](https://github.com/TheDave94/pollenwatch/compare/v2.2.1...v2.3.0) (2026-06-01)


### Features

* add threshold_basis derived attribute (provenance grouping for UI) ([#13](https://github.com/TheDave94/pollenwatch/issues/13)) ([398fbe2](https://github.com/TheDave94/pollenwatch/commit/398fbe2b194ba75a1a79d1399561b4570583a068))
* surface threshold provenance marker in bundled card ([#15](https://github.com/TheDave94/pollenwatch/issues/15)) ([e996c67](https://github.com/TheDave94/pollenwatch/commit/e996c674bcee2c3d726eab43cc214584dd8d42c8))

## [2.2.1](https://github.com/TheDave94/pollenwatch/compare/v2.2.0...v2.2.1) (2026-06-01)


### Bug Fixes

* **cleanroom:** harden settle — 180s ceiling + distinct SETTLE TIMEOUT (exit 10), unready=state-None-only, all-config-entries-loaded guard ([54fea58](https://github.com/TheDave94/pollenwatch/commit/54fea5864540e4c6af78fbe122582a4fd9f18c64))

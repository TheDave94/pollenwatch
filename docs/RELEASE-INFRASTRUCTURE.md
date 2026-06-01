# Release Infrastructure

How PollenWatch ships releases, and the credentials that make it work. Read this before touching `.github/workflows/release-please.yml`, the branch-protection rules on `main`, or the `pollenwatch-release-bot` GitHub App.

## How a release happens

PollenWatch uses release-please (`googleapis/release-please-action`, SHA-pinned to `45996ed` = v5.0.0). On every push to `main` it maintains a standing release PR titled `chore(main): release X.Y.Z`, computed from conventional-commit messages since the last tag. The release PR bumps the version and updates `CHANGELOG.md`. Merging it cuts a `vX.Y.Z` git tag and a matching GitHub Release; HACS installs from the tag directly (there is no build/asset step).

To ship: land conventional-commit work on `main`, review the release PR's diff, and merge it once the required checks are green. The tag and Release are created automatically by the second release-please run that fires on the merge.

Release PRs are merged manually today — see "Auto-merge" below.

## What gets version-bumped

The HACS-authoritative version is `custom_components/pollenwatch/manifest.json` -> `version`. That is the field HACS reads; it must be bumped on every release. release-please does this via `release-please-config.json` (`release-type: simple`) using two `extra-files` pointers: `custom_components/pollenwatch/manifest.json` via JSON pointer `$.version` (HACS-authoritative), and `pyproject.toml` via TOML pointer `$.project.version`.

The current version of record lives in `.release-please-manifest.json` (`"." : "X.Y.Z"`), which release-please reads to compute the next version and writes on each release. It was seeded at `2.2.0` (the last hand-shipped version) at adoption. `pyproject.toml` was stale at `0.0.1` beforehand; the first release-please run corrected it and it now tracks the real version.

## The pollenwatch-release-bot GitHub App

A private, single-purpose GitHub App, installed only on `TheDave94/pollenwatch`. Its installation token is what release-please runs under.

Permissions (the minimum): Contents = Read & write (version-bump commits, the tag, the GitHub Release); Pull requests = Read & write (open/update the release PR). Nothing else.

Why it exists — and why it's NOT oriel's reason. A PR opened by the default `GITHUB_TOKEN` has its checks held by GitHub in an "approval-required" suspended state: they don't run until a human clicks "Approve workflows to run". That would mean the release PR's required checks (cleanroom especially) never run on their own, the gate is moot, and the PR can't merge on the green path. A PR opened under a GitHub App identity is not suspended that way — its checks run automatically. So the App exists to make the release PR's required checks run automatically (and it is the prerequisite for any future auto-merge). This is a different rationale than `oriel-release-bot`, which exists because oriel needs the `release: published` event to fire its `release-build.yml`. PollenWatch has no `release:`-triggered workflow (HACS pulls source from the tag; there is no `release-build.yml`), so that reason does not apply here — only the approval-required-state reason does.

Token minting: `actions/create-github-app-token` (SHA-pinned to `bcd2ba4` = v3.2.0) in `release-please.yml`, using the `client-id` input (not the deprecated `app-id`).

Secrets (repo -> Settings -> Secrets -> Actions): `RELEASE_APP_CLIENT_ID` (the App's Client ID) and `RELEASE_APP_PRIVATE_KEY` (the full `.pem` private key).

Key rotation: unlike a PAT, the App private key has no auto-expiry, so nothing warns you. To rotate: generate a new private key in the App's settings, replace `RELEASE_APP_PRIVATE_KEY` with the new `.pem`, then delete the old key from the App. (Contrast: the cleanroom `CLEANROOM_HACS_PAT` does expire, ~2026-08-29.)

Troubleshooting: if the release-please workflow 404s on `GET /repos/TheDave94/pollenwatch/installation`, the App authenticates fine but is not installed on the repo — install it (App settings -> Install App -> Only select repositories -> pollenwatch). A 401 / PEM error instead means `RELEASE_APP_PRIVATE_KEY` is wrong or stale.

## Required checks on main

Branch protection on `main` requires three checks: `cleanroom-pretag (v1.3.0 → HEAD, Gates A–D)`, `Ruff + pytest`, and `Hassfest`. `HACS` runs but is intentionally NOT required (non-hermetic / flaky — same call as oriel). `enforce_admins` is `false`, preserving an admin bypass for emergencies.

The cleanroom check name contains two non-ASCII characters: `→` (U+2192) and `–` (U+2013). Never retype it — copy it from a check-run or the API, or branch protection will silently fail to match.

## The path-filter caveat (why some PRs need an admin merge)

`cleanroom.yml` is path-filtered: it triggers only on PRs touching `custom_components/pollenwatch/**`, `cleanroom/**`, `Makefile`, `requirements-cleanroom.txt`, or `.github/workflows/cleanroom.yml`. `Ruff + pytest` and `Hassfest` have no path filter and run on every PR.

Consequence: a PR touching none of cleanroom's paths — release-please config, this doc, other docs-only changes — never gets a `cleanroom-pretag` status, so it shows BLOCKED (a required check that cannot report). That is expected, not a failure; merge such PRs with `--admin`. Release PRs are fine on the normal green path because they bump `manifest.json`, which is inside cleanroom's allowlist, so cleanroom fires and gates them properly.

## Auto-merge (deliberately not wired)

Release PRs are merged by hand. Automatic merge is a separate, deliberate decision that has not been made; manual merge is a valid permanent resting state, not just a waypoint. The one piece auto-merge would need — an App token so a bot-opened PR's required checks actually run — is already in place. The remaining work, if ever revisited, is the auto-merge wiring itself plus defining what "safe to auto-merge" means (likely: all required checks green AND the PR is release-please-authored).

## Key files

- `.github/workflows/release-please.yml` — App-token step + release-please step
- `release-please-config.json` — `release-type: simple`, the two version extra-files
- `.release-please-manifest.json` — current version of record
- `.github/workflows/cleanroom.yml` — the migration gate (path-filtered)

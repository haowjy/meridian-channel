# Changelog

Caveman style. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/). Versions `0.0.6` through `0.0.25` in git history only — changelog fell stale, resumed at `[Unreleased]`.

## [Unreleased]

### Added
- `CHANGELOG.md` resumed after staleness. Now in caveman style.
- `AGENTS.md` → "Changelogs" section. Convention for `meridian-channel`, `meridian-base`, `meridian-dev-workflow`. All three keep own `CHANGELOG.md`, all caveman.

## [0.0.5] - 2026-03-21

### Added
- `gpt52` builtin alias for `gpt-5.2`; Claude `tools` passthrough in launch plan

### Changed
- Auto-resolve builtin aliases from discovered models; manifest-first bootstrap

## [0.0.4] - 2026-03-17

### Added
- Model catalog split with routing, visibility, descriptions, and `models.toml` config

## [0.0.3] - 2026-03-17

### Added
- Bootstrap state tracking with builtin skills and source recording; designer agent

## [0.0.2] - 2026-03-17

### Fixed
- `.meridian/.gitignore` seeding and stale CLI commands in docs

## [0.0.1] - 2026-02-25

Initial release — core CLI (`spawn`, `session`, `work`), harness adapters (Claude Code, Codex, OpenCode), agent profiles, skill system, sync engine, JSONL state stores.

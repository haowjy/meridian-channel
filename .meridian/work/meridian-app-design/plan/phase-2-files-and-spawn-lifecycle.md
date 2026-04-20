# Phase 2: Files Mode and Remaining Spawn Lifecycle

## Scope and Boundaries

Deliver Files mode plus the remaining spawn lifecycle mutations:

- `GET /api/files/tree`
- `GET /api/files/read`
- `GET /api/files/diff`
- `GET /api/files/meta`
- `GET /api/files/search`
- `POST /api/spawns/{spawn_id}/fork`
- `POST /api/spawns/{spawn_id}/archive`

In scope:

- project-root-relative path validation
- symlink-escape refusal
- diff/search/meta projections the UI needs
- spawn archive persistence and default list behavior
- fork behavior reusing existing spawn continuation logic where possible

Out of scope:

- catalog endpoints
- thread inspector endpoints
- in-browser editing or write APIs for files

## Touched Files and Modules

- Existing:
  - `src/meridian/lib/app/server.py`
  - `src/meridian/lib/app/spawn_routes.py`
  - `src/meridian/lib/ops/spawn/api.py`
  - `src/meridian/lib/state/spawn_store.py`
  - `tests/integration/launch/test_app_server.py`
- Planned new app modules:
  - `src/meridian/lib/app/file_routes.py`
  - `src/meridian/lib/app/file_service.py`
  - `src/meridian/lib/app/path_security.py`
  - `tests/integration/launch/test_app_files_api.py`
  - `tests/unit/app/test_path_security.py`

## Claimed Contract IDs

- `APP-SPAWN-01`
- `APP-SPAWN-02`
- `APP-FILES-01`
- `APP-FILES-02`
- `APP-FILES-03`
- `APP-FILES-04`
- `APP-FILES-05`

## Touched Refactor IDs

- none from local design package

## Dependencies

- Phase 1
- `design/file-explorer.md`
- `design/server-lifecycle.md`

## Subphases

### 2.1 Path Security and File Service Foundation

**Scope**

- Create a dedicated file-service layer rooted at the bound project root.
- Normalize and validate project-relative paths.
- Refuse:
  - absolute paths
  - parent-directory escapes
  - symlinks resolving outside the project root
  - malformed Windows/drive-prefixed escape attempts

**Files / modules touched**

- `src/meridian/lib/app/path_security.py`
- `src/meridian/lib/app/file_service.py`
- `tests/unit/app/test_path_security.py`

**Dependencies**

- Phase 1 route/service extraction

**Light verification**

- focused unit tests cover POSIX and Windows-style path edge cases
- validation helper can be reused uniformly by all file endpoints

**Estimated size**

- medium

### 2.2 File Tree, Read, Search, and Meta

**Scope**

- Implement tree listing, file reads, search, and metadata routes on top of the file service.
- Include the projections the UI expects:
  - lazy tree entries
  - size and mtime
  - git-status slots
  - referenced-by/session linkage placeholder only if it can be backed from current state
- Keep pagination/range handling explicit for large files and large result sets.

**Files / modules touched**

- `src/meridian/lib/app/file_routes.py`
- `src/meridian/lib/app/file_service.py`
- `src/meridian/lib/app/api_models.py`
- `tests/integration/launch/test_app_files_api.py`

**Dependencies**

- Subphase 2.1

**Light verification**

- integration tests cover root listing, nested listing, range reads, search narrowing, and metadata shape
- searches remain rooted to the project and never return escaped paths

**Estimated size**

- large

### 2.3 File Diff and Spawn Fork/Archive

**Scope**

- Implement `GET /api/files/diff` against working tree / refs.
- Implement spawn fork by reusing existing spawn continuation/fork primitives rather than duplicating launch logic in the app layer.
- Implement spawn archive as durable state, not an in-memory hide list, so list endpoints can exclude archived rows by default while keeping them queryable.

**Files / modules touched**

- `src/meridian/lib/app/file_routes.py`
- `src/meridian/lib/app/spawn_routes.py`
- `src/meridian/lib/ops/spawn/api.py`
- `src/meridian/lib/state/spawn_store.py`
- `tests/integration/launch/test_app_files_api.py`
- `tests/integration/launch/test_app_server.py`

**Dependencies**

- Subphase 2.2

**Light verification**

- integration tests cover diff against `HEAD` and explicit refs
- fork creates a new spawn with the expected source linkage
- archive hides rows from default list queries but keeps direct lookup working

**Estimated size**

- medium

## Phase Exit Gate

- `@verifier`
  - touched integration/unit tests pass
  - `ruff` and `pyright` stay green
- `@unit-tester`
  - path security helper covers escape, symlink, and Windows-style normalization cases
- `@integration-tester`
  - file tree/read/search/meta/diff contract
  - fork/archive semantics
  - archived spawns do not break existing list/detail behavior
- `@smoke-tester`
  - live app browse/read/diff/search against the real project root
  - manual symlink escape probe if the local repo can stage one safely

## Exit Criteria

- Files mode can browse and inspect project files through a hardened project-root boundary.
- Spawn `fork` and `archive` are durable lifecycle operations, not UI-only state.
- No file endpoint can escape the bound project root, including through symlinks or normalized path tricks.

# Feasibility Record

## Probe 1: Config File at Repo Root

**Question**: Can `meridian.toml` coexist with other root config files without conflicts?

**Evidence**: Current repo root contains: `mars.toml`, `mars.lock`, `pyproject.toml`, `uv.lock`. No TOML file named `meridian.toml` exists. The name is unambiguous and follows the `<tool>.toml` convention used by Ruff, Mars, and others.

**Verdict**: ✅ No conflict. Clean namespace.

---

## Probe 2: Config Loading Backward Compatibility

**Question**: Can the two-location fallback work without breaking existing users?

**Evidence**: `_resolve_project_toml()` in `settings.py` returns a single `Path | None`. Callers don't care where the file came from — they just parse the TOML. Changing the resolution function to check root first, then `.meridian/`, is transparent to all consumers. The schema is identical in both locations.

**Verdict**: ✅ Transparent migration. Same schema, different path.

---

## Probe 3: Claude --add-dir Injection (Previously Validated)

**Question**: Can workspace context-roots inject via `--add-dir`?

**Evidence**: `expand_claude_passthrough_args` in `claude_preflight.py` already builds `--add-dir` lists. Adding workspace-derived directories is a list extension. `dedupe_nonempty` handles dedup.

**Verdict**: ✅ Validated in prior design. No architectural changes needed.

---

## Probe 4: Codex/OpenCode Context-Root Mechanisms

**Question**: Do Codex and OpenCode support directory-inclusion flags?

**Evidence**: Inspected `project_codex_subprocess.py` and `project_opencode_subprocess.py`. Neither harness currently supports an `--add-dir` equivalent for injecting additional directory context.

Codex has `--read-dir` in some configurations but it is not used by Meridian's projection layer. OpenCode has no equivalent flag.

**Verdict**: ⚠️ Claude-only for first version. Context-roots silently skip for Codex/OpenCode. The architecture exposes `context_directories() → list[Path]` harness-agnostically so future adapter support requires only projection-layer changes.

---

## Probe 5: Gitignore Management at Root

**Question**: Can we reliably add `workspace.toml` to `<repo_root>/.gitignore`?

**Evidence**: Mars already manages `mars.local.toml` in root `.gitignore`. The current root `.gitignore` already has entries like `.mars/` and `.agents/`. Appending `workspace.toml` follows the same append-if-absent pattern.

The existing `.meridian/.gitignore` management in `state/paths.py` provides a reusable pattern (read file, check lines, append if missing, atomic write).

**Verdict**: ✅ Well-established pattern. One utility function.

---

## Probe 6: `workspace.toml` Key Format

**Question**: Do TOML dotted keys work well for `org/repo` identifiers?

**Evidence**: TOML spec requires quoting keys containing `/`. So entries look like:

```toml
[context-roots."meridian-flow/meridian-base"]
path = "../prompts/meridian-base"
```

The quoting is slightly verbose but unambiguous. Alternative: use `.` separator (`meridian-flow.meridian-base`) which avoids quoting but diverges from the canonical `org/repo` format used everywhere else.

**Verdict**: ✅ Quoted TOML keys work correctly. The slight verbosity is acceptable for the clarity of using the canonical `org/repo` format. Non-repo entries use simple keys: `[context-roots.shared-data]`.

---

## Probe 7: models.toml Location

**Question**: Where does models.toml loading happen and can it be redirected?

**Evidence**: Need to trace the model catalog loader to find where `.meridian/models.toml` is resolved. The `models.toml` content is a curated overlay (aliases, metadata, harness patterns, visibility filters). Its schema has top-level tables (`[aliases]`, `[metadata.*]`, `[harness_patterns]`, `[model_visibility]`) that are distinct from `config.toml` sections.

**Verdict**: ✅ Same migration pattern as config.toml. Check root first, fallback to `.meridian/`. Separate file (not merged into `meridian.toml`) because the schema is distinct and self-contained.

---

## Probe 8: `.meridian/.gitignore` Exception Removal

**Question**: Can we safely remove the `!config.toml` exception from `.meridian/.gitignore`?

**Evidence**: The `_REQUIRED_GITIGNORE_LINES` tuple in `paths.py` includes `"!config.toml"`. The `_merge_required_gitignore_lines` function adds missing required lines to existing gitignores. Removing `"!config.toml"` from `_REQUIRED_GITIGNORE_LINES` means it won't be added, but it also won't be removed from existing files.

For clean removal, add `"!config.toml"` to `_DEPRECATED_GITIGNORE_LINES` (which already exists for legacy entries). The existing merge logic already strips deprecated lines.

**Verdict**: ✅ Clean migration path via existing deprecated-lines mechanism.

---

## Open Questions

### OQ-1: Should `meridian config migrate` also migrate `models.toml`?

A single `meridian config migrate` command that moves both `config.toml` and `models.toml` to repo root would be convenient. Alternative: separate `meridian models migrate`. The former is simpler UX.

**Recommendation**: Single `meridian config migrate` moves both files.

### OQ-2: Per-harness context-root subsets

Some developers might want certain roots only for Claude (e.g., a large codebase that OpenCode can't handle). The current design omits per-harness filtering as a non-goal.

**Recommendation**: Defer. When the need arises, add an optional `harnesses = ["claude", "codex"]` field to context-root entries. The architecture already separates path resolution from harness injection, so this extension is additive.

### OQ-3: Should `models.toml` merge into `meridian.toml`?

Architecturally clean to keep separate (distinct schema). But having both `meridian.toml` and `models.toml` at root is two files where one could suffice. Users rarely edit models.toml directly — it's mostly for power users.

**Recommendation**: Keep separate. The schemas are orthogonal, and a `[models]` section in `meridian.toml` containing `[models.aliases]`, `[models.harness_patterns]` etc. creates awkward nesting. Two focused files > one cluttered file.

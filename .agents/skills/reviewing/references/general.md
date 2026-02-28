# General Rules (Cross-Cutting)

These rules apply to all stacks. Check every diff against them.

## Structure & Size

1. **SRP file size**: Files should be < 500 lines. If a changed file exceeds this, flag it.
2. **One store = one domain**: Stores should not mix unrelated concerns.
3. **No premature abstractions**: Don't create helpers/utilities for one-time operations. Three similar lines > a premature abstraction.

## Error Handling

4. **Never swallow errors**: No empty catch blocks. Every error must be logged, re-thrown, or handled meaningfully.
5. **Fail fast and loudly**: Don't silently return defaults when something is genuinely wrong.

## Data Handling

6. **Absence checks — use `!== undefined`**: Never use falsy checks (`if (content)`) for absence. Empty string `""` and empty array `[]` are valid data.
7. **Treat empty as valid**: `""` is valid, `[]` is valid. Only `undefined`/`null` means "absent".

## Comments & Documentation

8. **Comment the "why"**: Guards, race conditions, non-obvious logic must have comments explaining why they exist.
9. **No redundant comments**: Don't add docstrings/comments/type annotations to code you didn't change.

## Code Reuse

10. **Search before writing**: If a similar pattern exists in the codebase, reuse it. Don't reinvent.
11. **Consolidate duplicates**: If 2+ implementations of the same thing exist, consolidate to one.
12. **Check shared utilities before creating new ones**: Search the codebase for existing utility/helper directories before creating new ones.

## Feature Documentation

13. **Feature changes require doc updates**: Update feature/project documentation if the project maintains it.

## Security

14. **No secrets in committed files**: No API keys, tokens, passwords, or credentials in source code.
15. **Commit specific files**: Never `git add -A` or `git add .` — commit specific files by name.

## Over-Engineering

16. **Only requested changes**: Don't add features, refactor code, or make "improvements" beyond what was asked.
17. **No speculative error handling**: Don't add validation/fallbacks for scenarios that can't happen. Only validate at system boundaries.
18. **No backwards-compatibility hacks**: No renaming unused `_vars`, re-exporting types, or `// removed` comments. If unused, delete it.

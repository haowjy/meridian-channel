---
name: mermaid
description: Rules and validation for Mermaid diagrams. Use when creating or editing Mermaid diagrams in documentation.
user-invocable: false
---

# Mermaid Diagram Rules

**Always follow these rules when writing Mermaid diagrams.** After writing or editing any Mermaid block, validate with the co-located script: `scripts/check-mermaid.sh <file>`.

## Syntax Rules (Critical)

### 1. Always quote labels that contain special characters

Any label with `()`, `[]`, `<>`, `"`, `,`, `<br/>`, or emoji **must** be wrapped in `["..."]`:

```mermaid
%% ✅ GOOD — quoted labels
A["Turn 1: user"] --> B["blocks list"]
C["UI Panels (Thread, Tool)"]

%% ❌ BAD — unquoted special chars cause parse errors
A[Turn 1: user<br/>"Write a story"] --> B[blocks[]]
C[UI Panels (Thread, Tool)]
```

### 2. Quote edge labels that contain special characters

Edge labels with `()`, `<>`, `<br/>`, or `[]` must be quoted with `|"..."|`:

```mermaid
%% ✅ GOOD
A -->|"StreamEvents (Delta, Block)"| B
A -->|"JSON DTOs"| B

%% ❌ BAD — parentheses in edge labels
A -->|StreamEvents<br/>(Delta, Block)| B
A -->|JSON (DTOs)| B
```

### 3. Never use `<br/>` inside labels — use multiline with `\n` or separate lines

```mermaid
%% ✅ GOOD — no <br/>
A["Turn 1\nuser message"]

%% ❌ BAD — <br/> inside labels often breaks
A["Turn 1<br/>user message"]
```

**Note:** `<br/>` works in *some* Mermaid versions but not all. `\n` is safer.

### 4. Escape or avoid `[]` inside node text

```mermaid
%% ✅ GOOD
Store -->|"blocks list"| UI["Chat UI"]

%% ❌ BAD — nested [] conflicts with node shape syntax
Store -->|blocks[]| UI[Chat UI]
```

### 5. No emoji in node IDs or unquoted labels

```mermaid
%% ✅ GOOD
A["Step complete ✓"] --> B

%% ❌ BAD — emoji in unquoted context
A[Step ✓] --> B
```

### 6. Do not hardcode colors — rely on Mermaid's built-in themes

Hardcoded `style` / `classDef` colors override Mermaid's theme engine and break when switching between light and dark mode. Let the built-in `dark` / `default` themes handle node colors.

```mermaid
%% ✅ GOOD — no hardcoded colors, theme handles it
A[Service] --> B[Database]

%% ❌ BAD — hardcoded fill/color overrides theme
style A fill:#2d7d2d,color:#fff
classDef foo fill:#1a5276,color:#fff
```

For sequence diagram `rect` grouping, use near-transparent fills so they work in both themes:

```
rect rgba(128, 128, 128, 0.08)
    Note over A,B: Phase label
end
```

### 7. Semicolons in sequence diagrams

Sequence diagram statements must end with a newline, not a semicolon followed by more statements on the same line:

```mermaid
%% ✅ GOOD
Note over A: First
Note over A: Second

%% ❌ BAD — multiple statements on one line with semicolons
Note over A: First; isLoading=false
```

## Quick Reference: When to Quote

| Context | Needs quotes? | Example |
|---------|--------------|---------|
| Simple text only | No | `A[Hello World]` |
| Contains `()` | **Yes** | `A["Config (optional)"]` |
| Contains `[]` | **Yes** | `A["items list"]` (avoid `[]` entirely) |
| Contains `<br/>` | **Avoid** | Use `\n` instead |
| Contains emoji | **Yes** | `A["Done ✓"]` |
| Contains `"` | **Escape** | `A["Say 'hello'"]` |
| Edge with specials | **Yes** | `A -->\|"data (raw)"\| B` |

## Validation

The validation script lives at `scripts/check-mermaid.sh` within this skill directory. It extracts each ` ```mermaid ` block, validates it with `mmdc`, and reports file + line number for failures.

```bash
# Validate specific file
scripts/check-mermaid.sh path/to/file.md

# Validate all .md files recursively from cwd
scripts/check-mermaid.sh

# Validate a directory
scripts/check-mermaid.sh docs/features/
```

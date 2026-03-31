---
name: tech-docs
description: Technical writing methodology — structure, clarity, and navigability for documents that humans and agents rely on. Use whenever writing technical documents, design docs, reference material, architecture specs, or any structured documentation. Also activate when reviewing or restructuring existing docs.
---

# Tech Docs

Good technical writing lets a reader — human or agent — find what they need, understand it without chasing context across five files, and trust that what they're reading reflects reality. Bad technical writing gets skimmed, misunderstood, or ignored. Every doc you write either accelerates the next person or wastes their time.

## One Concept Per Document

A document that covers two concerns drifts twice as fast and gets read by people who only need half of it. Apply the same SRP discipline you'd apply to code:

- One component, one interface, one interaction pattern, one decision per file.
- When a doc starts covering two things, split it. The discomfort of having "too many files" is less than the cost of a doc that's half-relevant to every reader.
- Name files by what they describe, not by when they were written. `token-validation.md` ages better than `auth-redesign-notes.md`.

## Hierarchical Structure

Depth matches complexity. A simple topic gets a flat file. A complex subsystem gets nested directories. No artificial ceiling — let the hierarchy grow as deep as the subject requires.

```
overview.md
<area>/
  overview.md
  <topic>.md
  <sub-area>/
    <topic>.md
```

The overview at each level orients the reader: what exists here, how the pieces relate, and where to go deeper. Think of it as a table of contents that actually explains things. A reader who only reads the overview should still walk away oriented, even if they don't yet understand the details.

## Linked Web

Documents link to related docs using relative paths. A component doc links to the components it interacts with, the interfaces it implements, the tradeoffs that shaped it. An agent reading any doc can follow links to build context without reading everything.

```markdown
# Token Validation

Validates JWT tokens on every authenticated request.
See [auth overview](../overview.md) for how this fits into the auth system.
Uses the [key rotation](../key-management/rotation.md) component for public key discovery.
```

Links serve two purposes: they let readers navigate naturally, and they make dependency relationships explicit. When you'd write "this interacts with X" — make X a link. Broken links are broken promises; maintain them as you'd maintain broken imports.

## Writing for Agents

Agents read docs differently than humans. They scan for structure, match keywords, and build context from whatever file they're handed. Write docs that work when read in isolation:

- **Self-contained.** Include enough inline context that a reader doesn't need to read three other docs first. If understanding requires a chain of prerequisites, the doc is either too abstract or missing context.
- **Scannable.** Use headers, bullet lists, and tables so an agent can jump to the relevant section without parsing prose paragraphs. Bold key terms on first use.
- **Concrete.** Reference file paths, function names, and line numbers. "The auth module" is vague; "`src/auth/token.py:validate()`" is actionable.
- **State the invariants.** Agents don't infer constraints — they follow instructions. If a component assumes single-threaded access, say so explicitly. Unstated assumptions become violated assumptions.

## Progressive Disclosure

Not every reader needs every detail. Structure docs so readers can stop at the depth they need:

1. **Overview** orients — what exists, how pieces connect, what the important boundaries are.
2. **Topic docs** go deep — one concept fully explained, with enough context to be useful on its own.
3. **Detail sections** within a doc go deepest — edge cases, implementation notes, historical rationale.

A reader who needs the big picture reads the overview. A reader working on a specific component reads that component's doc. Neither is forced to wade through content meant for the other. This is the same progressive disclosure principle that makes good CLIs: simple by default, detailed on demand.

## When to Split vs. Merge

Watch for these signals:

**Split when:**
- A doc covers two concerns that change independently (different authors, different cadence)
- Readers consistently need only half the content
- The doc exceeds what you can hold in your head as a coherent unit
- A topic grows substantial sub-topics — promote them to their own files in a subdirectory

**Merge when:**
- Two docs are always read together and never independently
- A doc is so small it adds navigation overhead without adding clarity
- The split created artificial seams — concepts that are one thing got separated into two files

When in doubt, lean toward splitting. It's cheaper to follow a link than to scroll past content you don't need.

## Mining Decisions from Conversations

The richest source of decision rationale lives in conversations — orchestrator sessions, design discussions, review threads. Pivots, rejected alternatives, and tradeoff discussions happen there first; only the final choice lands in code or docs.

When working from conversation context, search for decision points: where direction changed, alternatives were weighed, or constraints were discovered. Extract those moments into documentation next to the technical explanation so readers get both the implementation shape and the reasoning behind it. The WHY context is what prevents future agents from undoing deliberate decisions that look arbitrary in source alone.

Don't wait to mine decisions retroactively — context decays fast. Capture rationale while it's fresh, during or immediately after the discussion that produced it.

## Writing Style

**Diagrams over words.** Prefer visual representations for flows, state machines, and dependency graphs. Tables for comparisons and reference data. Models default to prose — fight that instinct. A diagram that shows the relationship is worth more than three paragraphs describing it.

**Compress, don't narrate.** Every sentence earns its place. One sentence per concept, not a paragraph. If a diagram says it, don't also say it in text.

**Reference, don't duplicate.** Point to source locations rather than pasting code. Snippets only for critical patterns — atomic operations, race guards, non-obvious invariants. Duplicated content is content that will drift.

**WHAT and WHY, not HOW.** Code shows the how. Documentation captures what the code can't easily tell you: component relationships, dependency directions, data flows, and especially why the system ended up this way. When rationale is missing, go find it — don't guess and don't skip it.

## Verification

After writing or restructuring linked docs, run the co-located link checker to catch broken internal links and anchors:

```bash
scripts/check-md-links.sh <doc-root>
```

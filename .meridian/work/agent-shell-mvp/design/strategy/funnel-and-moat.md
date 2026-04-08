# Funnel And Moat

> What this is: the strategic through-line from local shell to marketplace to
> hosted continuity.
>
> What this is not: a marketplace feature spec.

Back up to [overview.md](./overview.md).

## 1. The Moat

**D22:** the moat is mars packaging. The shell is a neutral runtime. The value
accrues when users can install a package and get a working vertical composed
from:

- an agent profile,
- its skill bundle,
- one or more MCP servers, and
- any paired interaction-layer extensions.

This is why the shell must ship zero biomedical code. Shell-owned domain
features compete with the moat instead of strengthening it.

## 2. The Funnel

**D23:** the product has three acts.

1. **V0 local shell:** user installs packages and runs locally with their own
   harness account.
2. **V0.5 marketplace surface:** package provenance, signing hooks,
   discoverability, and author reputation start mattering.
3. **V1 hosted continuity:** the same packages run in a hosted environment for
   collaboration, continuity, and heavier workloads.

The key promise is constant across all three: **same packages, different
runtime**.

## 3. Concierge Seeding

**D24:** the marketplace does not bootstrap itself. The first packages are
hand-authored with customers. Yao Lab is the first such package set, and V0 is
not done until those packages use every extension point the shell claims to
support.

Concierge work answers three questions faster than abstraction-first design:

- Which seams are genuinely reusable?
- Which parts of a workflow belong in a package instead of the shell?
- Which capabilities are so common they deserve core renderer support?

## 4. What This Forces On The Design

- Package kinds must be open-ended even though V0 only ships four.
- Contracts must be published early enough that package authors can target
  them, even when implementation stays narrow.
- Extension relay is not optional, because interactive package experiences are
  part of the moat, not an add-on.
- Shell-local shortcuts that cannot survive hosted continuity are design bugs.

## 5. Read Next

- [../extensions/package-contract.md](../extensions/package-contract.md)
- [../execution/local-model.md](../execution/local-model.md)
- [../packaging/overview.md](../packaging/overview.md)

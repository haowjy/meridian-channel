# Strategy Overview

> What this is: the product and architecture posture that governs every other
> document in this tree.
>
> What this is not: a packaging schema or implementation plan.

Back up to [../overview.md](../overview.md).

## 1. Product Posture

**D21 governs the pass.** `agent-shell-mvp` replaces `meridian-flow` as the
first product step. V0 is a **local shell** that assumes the user brings a
Claude subscription and runs locally. We host nothing. The shell is not the
product destination; it is the cheapest way to learn which vertical deserves a
hosted product later.

This correction pass removes the old "biomedical shell" framing. Biomedical is
the **first concierge package set**, not a shell identity.

## 2. Governing Test

**D28 is the hard rule.** Every V0 choice must pass both tests:

1. Does removing this block Yao Lab validation?
2. If we succeed, does keeping this trap us in six months?

If the answer is `no / no`, cut it. If the answer is `yes / yes`, redesign it.

## 3. V0 Business Logic

- **Moat:** mars-packaged capability bundles, not custom shell panels.
- **Funnel:** V0 local shell, V0.5 marketplace/discoverability surface, V1
  hosted runtime continuity.
- **Concierge:** the first 5–10 packages are hand-authored with customers.
  Yao Lab is the first package-validation customer.
- **Continuity:** packages must survive local-to-hosted migration without being
  rewritten.

## 4. V0 Commitments

- The shell ships a neutral chat UI and contract surfaces only.
- The shell publishes versioned seams from V0: normalized events, frontend
  protocol, relay protocol, and mars integration points.
- The shell supports four package kinds in V0: `agent`, `skill`, `mcp_server`,
  and `interaction_layer_extension`.
- The shell does not embed domain runtimes, domain viewers, or domain-specific
  business logic.

## 5. Explicitly Open

- **Q7 stays open:** unify CLI spawn/session launching under the same adapter
  family later, but do not resolve it in this pass.
- **Marketplace UI stays deferred:** provenance and discoverability matter, but
  the V0 shell only needs the contract hooks that keep the later marketplace
  possible.
- **Hosted runtime stays deferred:** design for "same packages, different
  runtime" now; do not design tenancy, auth, billing, or remote orchestration
  here.

TODO(Q7/D28): decide whether `meridian spawn` migrates onto the session-lived
`HarnessAdapter` family once the shell contracts stabilize.

## 6. Read Next

- [funnel-and-moat.md](./funnel-and-moat.md) for the three-act market story.
- [../extensions/overview.md](../extensions/overview.md) for how packages add
  interaction surfaces.
- [../packaging/overview.md](../packaging/overview.md) for the shell-facing
  package contract.

# Frontend Overview

> What this is: the browser-side contract and UI posture for the shell.
>
> What this is not: a domain feature catalog.

Back up to [../overview.md](../overview.md).

## 1. Product Posture

**D25:** the frontend is a **generic chat UI**. It ships:

- message/thread chrome,
- session and connection state,
- a content-block dispatcher,
- 3–5 core built-in renderers, and
- extension mount points.

It does **not** ship biomedical viewers, DICOM panels, or shell-owned custom
domain surfaces.

## 2. V0 Surface

- [chat-ui.md](./chat-ui.md) defines the shell chrome and single-session rules.
- [content-blocks.md](./content-blocks.md) defines the built-in renderer set
  and extension dispatch rules.
- [protocol.md](./protocol.md) publishes the frontend wire contract.

## 3. Consequence

If a package needs a mesh viewer, image stack viewer, or interactive selector,
that arrives through the extension system. The shell only knows how to host it.

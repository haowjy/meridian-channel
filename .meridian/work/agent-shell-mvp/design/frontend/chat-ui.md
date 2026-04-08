# Chat UI

> What this is: the shell chrome and user-facing interaction model.
>
> What this is not: a plug-in system for arbitrary new shell panels.

Back up to [overview.md](./overview.md).

## 1. V0 Shell Chrome

The browser app is one route and one active session:

- transcript/message list,
- composer with attachments,
- session/connection status,
- inline content blocks, and
- extension mount points inside those content blocks.

No domain sidebar, DICOM panel, or biomedical-specific navigation ships in the
core shell.

## 2. Session Behavior

- The active tab is the controller.
- A second tab is read-only observer.
- Mid-turn composer enablement follows the adapter's declared mode.
- Long-lived work happens inline in the transcript; the shell does not split
  chat, analysis, and results into separate app modes.

## 3. Attachments

The composer sends the canonical shape documented in
[protocol.md](./protocol.md):

```json
{
  "messageId": "msg_001",
  "content": [
    { "kind": "text_markdown", "text": "Compare these outputs." }
  ],
  "turnHints": {}
}
```

Attachments belong inside `content`, not in a separate out-of-band carrier.

## 4. Read Next

- [content-blocks.md](./content-blocks.md)
- [protocol.md](./protocol.md)

# Content Blocks

> What this is: the browser-side block taxonomy and dispatcher rules.
>
> What this is not: the relay protocol for interactive extensions.

Back up to [overview.md](./overview.md).

## 1. Built-In Core Renderers

The shell ships only a small renderer set:

| Kind | Purpose |
|---|---|
| `text_markdown` | assistant/user prose |
| `image` | static PNG/JPEG/SVG outputs |
| `table` | rectangular tabular results |
| `chart_simple` | simple line/bar/scatter payloads |
| `status` | warnings, errors, progress, empty states |

This is the whole built-in set for V0. It is intentionally small.

## 2. Extension Dispatch

Any block kind outside the built-in set routes through the extension registry.
Examples:

- `mesh.3d`
- `dicom.stack`
- `image.roi_editor`

The shell frontend does not know how those blocks render internally. It only
knows which installed extension owns that kind.

## 3. Consequence For Biomedical

PyVista and biomedical rendering code leave the shell entirely. A biomedical
package may still publish a `mesh.3d` block, but the viewer arrives through an
installed extension package, not through a shell-owned renderer.

## 4. Read Next

- [protocol.md](./protocol.md)
- [../extensions/interaction-layer.md](../extensions/interaction-layer.md)

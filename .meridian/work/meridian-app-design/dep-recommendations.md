# Dependency Recommendations

Based on research conducted 2026-04-20.

## Python (App Server)

### Required

| Package | Size | Purpose |
|---------|------|---------|
| `fastapi` | - | Web framework |
| `uvicorn` | - | ASGI server |
| `sse-starlette` | 14kb | SSE endpoints |
| `qrcode` | 46kb | Terminal QR codes |

### Notes

- **WebSocket vs SSE**: Use WebSocket for bidirectional; SSE for one-way streams
- **Cloudflare Quick Tunnels**: Don't support SSE — use WebSocket or named tunnels
- **Process management**: Use `asyncio.create_subprocess_exec` (stdlib)
- **Browser opening**: Use `webbrowser` + Chrome `--app` mode (stdlib)
- **Skip `broadcaster`**: Marked Alpha, API unstable

---

## React (Frontend)

### Required

| Package | Purpose | Notes |
|---------|---------|-------|
| `wouter` | Routing | Tiny (~1.5kb), sufficient for `/sessions`, `/chat/:id`, `/files` |
| `@tanstack/react-query` | Server state | Strong cache primitives, SSE-friendly |
| `@tanstack/react-virtual` | Virtualization | Headless, good for trees/lists |
| `zustand` | Client state | Simple, for mode/layout/activeSession |

### Nice to Have

| Package | Purpose | Notes |
|---------|---------|-------|
| `diff2html` | Diff rendering | Mature, unified/git diff display |
| `prism-react-renderer` | Syntax highlighting | Lean React integration |
| `motion` | Animations | Add later if CSS insufficient |

### Skip

| Package | Why |
|---------|-----|
| `react-router` | Heavier than needed |
| `@tanstack/router` | More architectural than needed |
| `shiki` | Heavy in browser; use prism instead |
| `@monaco-editor/react` | Heavy; React 19 caveats |

---

## SSE + React Query Pattern

```tsx
// One shared EventSource per channel
const eventSource = new EventSource('/api/stream?spawns=p1,p2,p3')

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  // Route to query cache
  queryClient.setQueryData(
    ['spawn', data.spawn_id, 'events'],
    (old) => [...(old ?? []), data]
  )
}
```

Keep connection state in Zustand, not query cache.

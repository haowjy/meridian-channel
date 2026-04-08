# Frontend Integration — frontend-v2 → agent-shell

> Resolves **Q4** from `requirements.md`. Defines what gets copied from
> `../meridian-flow/frontend-v2/` into this repo's `frontend/`, what stays
> as-is, what gets cut, what gets extended, and what is genuinely new.
> Read the [frontend protocol](./frontend-protocol.md), the
> [interactive tool protocol](./interactive-tool-protocol.md), and the
> [repository layout](./repository-layout.md) before this doc — they are
> upstream constraints that this integration plan must satisfy.

The framing: **frontend-v2 is 80% of the shell already.** It has the activity
stream reducer, the WebSocket client, the thread/composer surface, the UI atoms,
and the theme system. What it lacks is a *product shell* — top-level layout,
routing, global state, an API client, and the new wire events that the
agent-shell backend emits. Those are the gaps this doc fills, plus an explicit
deletion list for the writing-app legacy that the biomedical pivot left
half-stripped.

All paths in this doc are relative to `frontend/src/` unless prefixed with
`frontend/`. The destination repo is `meridian-channel/`.

## 1. Inventory — stays / extends / cuts / new

| Subsystem | Path | Decision | Justification |
|---|---|---|---|
| **shadcn UI atoms** | `components/ui/**` | **STAYS** verbatim | Generated from `components.json` (`new-york`, Radix + CVA). Buttons, dialogs, popovers, tabs, scroll-area, sonner, tooltip — all generic. No domain coupling. Re-running shadcn `add` later is the upgrade path. |
| **Theme provider** | `components/theme-provider.tsx` | **STAYS** | `useSyncExternalStore`-driven, system-theme aware. Already light/dark with Geist + iA Writer Quattro. No reason to touch. |
| **Activity stream reducer** | `features/activity-stream/streaming/reducer.ts` | **EXTENDS** | Add `TOOL_OUTPUT`, `DISPLAY_RESULT`, `_unknown` cases, and a connection-scoped `SESSION_HELLO` handler at the provider layer. See §6. |
| **Activity item types** | `features/activity-stream/types.ts` | **EXTENDS** | Add `DisplayResultItem` to the `ActivityItem` union; add `stdout`/`stderr` chunks to `ToolItem`. See §6. |
| **ActivityBlock + headers** | `features/activity-stream/{ActivityBlock,ActivityBlockHeader}.tsx` | **STAYS** + small extension | Already supports collapsible card with last-content extraction. Add a render branch for `DisplayResultItem` that dispatches by `resultKind` (§8). |
| **Tool detail renderers** | `features/activity-stream/{ToolDetail,EditDetail,SearchDetail,WebSearchDetail,BashDetail,AgentDetail}.tsx` | **STAYS** | The dispatch table is already SOLID — `ToolDetail` switches by `toolName` and falls through to a generic input/output view. Biomedical tools (`python`, `bash`, `pick_points_on_mesh`) need new detail components, but adding them is *opening* the dispatch table, not modifying it. |
| **Activity stream examples / stories** | `features/activity-stream/examples/**`, `*.stories.tsx` | **STAYS** in dev, NOT in prod bundle | Storybook excludes them at build time via the `.storybook/main.ts` glob. They're useful for new-renderer development. |
| **Threads — TurnList / TurnRow / UserBubble** | `features/threads/components/**` | **STAYS** | The discriminated turn-row dispatch (`pending`, `error`, `cancelled`, `credit-limited`, `assistant`, `user`, `system`) is the core of the chat surface. `UserBubble` already handles `text | image | reference` blocks. |
| **Threads — composer** | `features/threads/composer/**` | **STAYS** + minor extension | `ChatComposer` + `ComposerEditor` (CM6 with submit/escape, history, placeholder) is exactly what's needed. `ComposerControls` ships today as a mock model picker — needs to be wired to backend `SESSION_HELLO.agentProfile` instead of local state, or stripped to send/stop only for V0. |
| **Threads — turn mapper** | `features/threads/turn-mapper.ts` | **STAYS** + extension | Already maps persisted turn blocks to activity items. Needs new branches for the persisted `tool_output` and `display_result` block kinds (already noted in `frontend-protocol.md` §6.1 as "adopted verbatim"). |
| **Threads — streaming provider** | `features/threads/streaming/{ThreadWsProvider,streaming-channel-client,use-thread-streaming}.{tsx,ts}` | **EXTENDS** | The provider, channel client, gap detector, sibling auto-follow, and reconnect resubscribe stay verbatim. The channel client gains a `SESSION_HELLO` handler that lifts capability flags into the new session store (§4). |
| **Chat scroll** | `features/chat-scroll/**` | **STAYS** | Generic IntersectionObserver-based scroll-pin. No coupling to either the writing app or biomedical. |
| **WS client + envelope** | `lib/ws/{ws-client.ts,protocol.ts,notify-handler.ts}` | **STAYS** + extension | Native `WebSocket` wrapper, exponential-backoff reconnect, ping/pong, binary frame parsing already at `ws-client.ts:115`. Extension: register the new `notify` ops emitted by the agent-shell backend (`work_item_files_changed`, `harness_died`) in `notify-handler.ts`. The envelope itself is unchanged — `frontend-protocol.md` §3 adopts it verbatim. |
| **Doc stream client** | `lib/ws/doc-stream-client.ts` | **CUTS** | Yjs document sync over WS. The agent shell does not have CRDT documents. Removing this also removes the entire `editor/transport/` surface (§2). |
| **Threads — `use-thread-simulator`** | `features/threads/hooks/use-thread-simulator.ts` | **CUTS from prod**, STAYS in `__stories__` | Storybook-only. Move into a `__stories__` subdirectory to make the prod boundary explicit. |
| **`features/docs/`** | `features/docs/**` | **CUTS** | Writing-app document tree. Not relevant to biomedical or any agent shell. Recoverable from git history if a "researcher notes panel" V1 wants to revive it. |
| **CodeMirror editor (drafting)** | `editor/**` | **PARTIAL CUT** — see §2 | The Yjs/CRDT layers go; the CM6 drafting surface stays for validation step 10 (drafting the results section). |
| **Storybook** | `.storybook/**` | **STAYS** in dev | Atom + ActivityBlock + ChatComposer stories are the only sane way to develop the new renderers. NOT bundled in prod (`pnpm build` skips `.stories.tsx`). |
| **`App.tsx`** | `App.tsx` | **NEW** — replace contents | Today: `ThemeProvider` + `Toaster` + null content. Becomes the shell layout with session bootstrap, route container, error boundary. See §3. |
| **Routes / pages** | `routes/**` | **NEW** | None exist. V0 is a single-route SPA — see §3. |
| **Global stores** | `stores/**` | **NEW** | No Redux/Zustand today. New `sessionStore`, `connectionStore`, `interactiveToolStore`, `meshCacheStore`. See §4. |
| **API client** | `lib/api/**` | **NEW** | No REST client today (the legacy backend was talked to over WS only). New `lib/api/` for `/api/turns`, session start, file upload. See §5. |
| **Mesh viewer** | `features/result-viewers/MeshView.tsx` | **NEW** | r3f-based 3D mesh viewer. Consumes `DISPLAY_RESULT` of `resultKind: "mesh"`. See §7. |
| **Inline result renderers** | `features/result-viewers/**` | **NEW** | `PlotlyView`, `MatplotlibView`, `DataFrameView`, `ImageView`, `MeshView`, `InteractivePendingView`, `UnknownResultView`. See §8. |
| **WebGL deps** | (`@react-three/fiber`, `@react-three/drei`, `three`) | **NEW** | Required for `MeshView`. ~300 KB gz. |
| **Plotly dep** | (`react-plotly.js`, `plotly.js-dist-min`) | **NEW** | Required for `PlotlyView`. ~1 MB gz; lazy-loaded via `React.lazy`. |
| **Hand-maintained wire types** | `lib/wire-types.ts` | **NEW** | V0 keeps frontend WS types hand-maintained and parity-checked by backend tests. See `frontend-protocol.md` §11. |

## 2. Editor subsystem — surgical cut

The editor subtree is the largest writing-app legacy artifact. Cutting it
wholesale loses the CM6 drafting capability needed for validation step 10
("draft results section"). Keeping it wholesale drags in Yjs, IndexedDB
persistence, multi-tab session pooling, and a CRDT transport that the agent
shell has no use for. **Cut surgically.**

Per-folder verdict:

| Folder | Verdict | Reason |
|---|---|---|
| `editor/Editor.tsx` | **STAYS** (rewritten thin) | Becomes a single-user CM6 mount. Drop the Yjs branch entirely; keep only the local `EditorState` path. ~150 lines instead of ~400. |
| `editor/extensions.ts` | **STAYS** + trim | Keep markdown parsing, focus/reveal, live preview, formatting, paste, interaction, keymap, history. **Drop** `yCollab`, `Y.UndoManager` keymap (replaced by CM6 native `historyKeymap`). |
| `editor/components/` | **STAYS** mostly | Keep `EditorShell`, drop `TabbedEditorShell` (multi-doc tab bar — single-doc shell is sufficient). |
| `editor/content/` | **STAYS** | Markdown serialization, content APIs. Pure CM6, no Yjs. |
| `editor/decorations/` | **STAYS** | CM6 decoration helpers. |
| `editor/export/` | **STAYS** | Keep markdown + HTML export. PDF/DOCX/EPUB are backend stubs (`exporters.ts:98`) — leave the stubs in place; biomedical V0 doesn't need them. |
| `editor/formatting/` | **STAYS** | CM6 markdown formatting commands (bold, italic, headings). |
| `editor/interaction/` | **STAYS** | CM6 click/key interaction handlers. |
| `editor/paste/` | **STAYS** + fix | Keep paste handling. The `![pasted image](TODO: upload)` placeholder (`paste-handler.ts:26`) gets wired to the new upload API client (§5). |
| `editor/title-header/` | **STAYS** | Title input + word count. Useful for the draft results section. |
| `editor/decorations/`, `editor/stories/` | stories: **CUTS from prod**, kept for dev | Same Storybook discipline as the rest. |
| `editor/collab/` | **CUTS** | Yjs collaboration (`yCollab`, awareness, cursors). Single user. Delete the folder. |
| `editor/persistence/` | **CUTS** | `y-indexeddb` persistence. Replace with a tiny `localStorage`-backed draft autosave (~30 lines, lives in the draft route, not in `editor/`). |
| `editor/session/` | **CUTS** | `DocSession`, `SessionPool`, `ViewController`, `useDocumentSessions`. The whole multi-doc lease/eviction model is for a tabbed multi-document writing app. Single-doc shell does not need it — `Editor.tsx` mounts directly. |
| `editor/transport/` | **CUTS** | `DocumentWsProviderImpl` + Yjs transport. Removed alongside `lib/ws/doc-stream-client.ts`. |

Trimmed editor tree:

```text
editor/
├── Editor.tsx              # rewritten — local-only CM6, no Yjs branch
├── extensions.ts           # trimmed — no yCollab, no Y.UndoManager
├── components/
│   └── EditorShell.tsx     # kept; TabbedEditorShell removed
├── content/                # kept
├── decorations/            # kept (no stories in prod)
├── export/                 # kept (markdown/HTML; PDF/DOCX/EPUB stubs)
├── formatting/             # kept
├── interaction/            # kept
├── paste/                  # kept; image-paste rewired to upload API
└── title-header/           # kept
```

Dependencies removed from `package.json`: `yjs`, `y-protocols`,
`y-indexeddb`, `y-codemirror.next`, `dexie`. Net bundle savings ~120 KB gz.

This trim is reversible — if a future domain needs multiplayer, the cut
folders are recoverable from the source `meridian-flow/frontend-v2` git
history.

## 3. Layouts and routes

### 3.1 What the biomedical-mvp pivot envisioned

The pivot's `frontend/mode-architecture.md` defined a **mode-driven** layout
where the same surface flips between *chat*, *analysis*, and *results* modes.
`thread-model.md` defined the canonical turn → block → activity-item mapping.
`state-management.md` was Zustand-leaning. None of those documents survived
the move out of meridian-flow as code, only as specs. **Adopt the spec, build
it minimally, do not chase mode-architecture's full taxonomy in V0.**

### 3.2 V0 layout: two-pane shell, no router

V0 ships **one route** (`/`) and **no routing library**. Reasoning: there's
exactly one work item per running shell, the URL has nothing useful to encode,
and adding React Router for a single route is dead weight. The "mode" the
biomedical-mvp pivot envisioned is folded into a single integrated surface
that always shows chat + results.

```text
┌──────────────────────────────────────────────────────────────────┐
│  TopBar — work item name · session status · theme toggle        │
├──────────────┬───────────────────────────────────────────────────┤
│              │                                                   │
│  Sidebar     │   ChatPane                                        │
│              │   ┌─────────────────────────────────────────────┐ │
│  ┌────────┐  │   │  TurnList                                  │ │
│  │Threads │  │   │   ▸ user bubble                            │ │
│  │ list   │  │   │   ▸ ActivityBlock (expanded streaming)     │ │
│  └────────┘  │   │     · thinking · text · tool · DISPLAY     │ │
│              │   │   ▸ user bubble                            │ │
│  ┌────────┐  │   └─────────────────────────────────────────────┘ │
│  │Datasets│  │   ┌─────────────────────────────────────────────┐ │
│  │ uploaded│ │   │  ChatComposer  [send] [stop]               │ │
│  └────────┘  │   └─────────────────────────────────────────────┘ │
│              │                                                   │
└──────────────┴───────────────────────────────────────────────────┘
```

**Inline results, not a third pane.** The biomedical-mvp pivot's three-pane
"chat / analysis / results" split was rejected: it forces the user to context-
switch away from the conversation to see the figure that the agent just
generated. Instead, every `DISPLAY_RESULT` renders inline inside the
ActivityBlock that produced it (§8). Mesh viewers, plots, dataframes — all
inline. The only thing that opens *outside* the browser is an interactive tool
window (PyVista), and that's a desktop OS window, not a third UI pane.

**File component layout:**

```text
src/
├── App.tsx                       # ThemeProvider + ShellLayout + ErrorBoundary
├── shell/
│   ├── ShellLayout.tsx           # 2-pane grid; TopBar + Sidebar + ChatPane
│   ├── TopBar.tsx                # work item name, session badge, theme toggle
│   ├── Sidebar.tsx               # threads list + datasets list (collapsible)
│   ├── ChatPane.tsx              # TurnList + ChatComposer host
│   ├── SessionBootstrap.tsx      # opens WS, waits for SESSION_HELLO, mounts children
│   └── ErrorBoundary.tsx         # top-level React error boundary
└── routes/                       # placeholder; empty for V0
```

`SessionBootstrap` is the gate: it instantiates the `WsClient` from
`lib/ws/ws-client.ts`, awaits the first `SESSION_HELLO` (per
`frontend-protocol.md` §2.2), pushes the payload into `sessionStore`, then
renders children. Until then it shows a centered spinner ("Connecting to
agent shell…"). On disconnect, it overlays a non-blocking toast and continues
to render the last good UI — the WS client handles reconnect, gap detection,
and stream replay underneath.

V1 may add React Router when there's a real second surface (e.g. a settings
page, an upload manifest browser). Defer until then.

## 4. State management

### 4.1 Decision: Zustand for shell state, useSyncExternalStore for streaming

Two state systems, by purpose:

- **Streaming state** (`StreamState` per turn, channel client subscriptions,
  ws-client connection state): **stays on `useSyncExternalStore`**, exactly
  as frontend-v2 does today. The reducer + channel client + `WsClient` are
  already store-shaped via external-store snapshots. Wrapping them in Zustand
  buys nothing and breaks the existing gap-detector contract.
- **Shell state** (session id, capability flags, active interactive tools,
  mesh data cache, sidebar toggles): **new Zustand stores**.

**Why Zustand and not more `useSyncExternalStore`?** The shell stores need:
selector subscriptions (re-render only on the slice that changed), dev-tools
integration, persistence to `localStorage` for sidebar collapse + last work
item, and ergonomic action methods. Hand-rolling that on `useSyncExternalStore`
duplicates Zustand's runtime for no win. Zustand is ~1 KB gz, has no provider,
plays nicely with Suspense and selectors, and is the minimum viable global
store. Redux is overkill for a single-user local shell. Jotai is reasonable
but biases toward atom-per-state which fragments the cross-cutting capability
flags.

### 4.2 Store shapes

```ts
// stores/sessionStore.ts
type SessionState = {
  sessionId: string | null;
  workItemId: string | null;
  harness: 'claude-code' | 'opencode' | null;
  harnessVersion: string | null;
  agentProfile: string | null;
  capabilities: Capabilities;          // from SESSION_HELLO
  serverProtocolVersion: string | null;
  resumed: boolean;
  setHello: (hello: SessionHelloPayload) => void;
  reset: () => void;
};
```

```ts
// stores/connectionStore.ts
type ConnectionState = {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
  lastError: string | null;
  reconnectAttempt: number;
  setStatus: (s: ConnectionState['status']) => void;
};
```

```ts
// stores/interactiveToolStore.ts
type InteractiveToolStatus = 'pending' | 'done' | 'error' | 'cancelled';
type InteractiveToolEntry = {
  displayId: string;
  toolCallId: string;
  toolName: string;
  status: InteractiveToolStatus;
  prompt: string;
  startedAt: number;
  finishedAt?: number;
  output?: unknown;
};
type InteractiveToolStoreState = {
  byDisplayId: Record<string, InteractiveToolEntry>;
  upsert: (e: InteractiveToolEntry) => void;
  resolve: (displayId: string, output: unknown) => void;
};
```

```ts
// stores/meshCacheStore.ts
type MeshBlob = { meshId: string; format: string; bytes: Uint8Array; bbox?: number[] };
type MeshCacheState = {
  byMeshId: Record<string, MeshBlob>;
  set: (mesh: MeshBlob) => void;
  evict: (meshId: string) => void;
  pendingRefs: Set<string>;            // displayIds awaiting a binary frame
  markPending: (displayId: string, meshId: string) => void;
};
```

```ts
// stores/uiStore.ts                   (persisted to localStorage)
type UiState = {
  sidebarCollapsed: boolean;
  lastWorkItemId: string | null;
  toggleSidebar: () => void;
};
```

`stores/index.ts` exports the hooks (`useSessionStore`, `useConnectionStore`,
…). The streaming reducer + channel client are NOT inside Zustand — they
remain in the `features/threads/streaming/**` and `features/activity-stream/
streaming/**` modules and integrate via `useSyncExternalStore`.

## 5. API client

### 5.1 Surface

```text
lib/api/
├── client.ts               # core fetch wrapper (base URL, JSON, errors)
├── turns.ts                # POST /api/turns/send, /api/turns/cancel
├── session.ts              # POST /api/session/reset, GET /api/session/info
├── datasets.ts             # POST /api/datasets/<name> multipart ingest, GET dataset listing
└── index.ts
```

### 5.2 Implementation discipline

- **Native `fetch`.** No axios, no ky. The only thing the wrapper does is base
  URL prepending, JSON encoding, error normalization, and abort-signal
  forwarding for `cancel_turn`.
- **Hand-maintained types in V0.** Request/response and WS wire types are kept
  by hand in the frontend. Backend tests assert parity for the load-bearing
  fields so drift fails in CI.
- **Most things go over WebSocket, not REST.** The frontend protocol §5 lists
  five client→server commands; all of them ride the `control` lane on the WS,
  not REST. REST is reserved for: starting a session, uploading files,
  fetching the work-item directory listing, fetching dataset manifests, and
  the initial turn list backfill on reload. Anything streaming or
  conversational is WS.
- **TanStack Query** is already in `package.json` and is used for the
  REST-fed surfaces (work items list, dataset list). No new query lib.

## 6. Activity stream extensions

### 6.1 Reducer extension sketch

The reducer at `features/activity-stream/streaming/reducer.ts:101` currently
handles the events listed in `frontend-protocol.md` §6.3. The required
additions are scoped:

```ts
// features/activity-stream/streaming/reducer.ts — additions only

case 'TOOL_OUTPUT': {
  const { toolCallId, stream, text, sequence } = event;
  return updateTool(state, toolCallId, (tool) => {
    const buffer = stream === 'stderr' ? tool.stderr : tool.stdout;
    return {
      ...tool,
      [stream]: appendStreamChunk(buffer, { seq: sequence, text }),
    };
  });
}

case 'DISPLAY_RESULT': {
  const { toolCallId, displayId, resultKind, data } = event;
  const existingIdx = state.activity.items.findIndex(
    (it) => it.kind === 'display_result' && it.displayId === displayId,
  );
  const newItem: DisplayResultItem = {
    kind: 'display_result',
    id: displayId,
    displayId,
    sourceToolId: toolCallId,
    resultKind,
    data,
    receivedAt: Date.now(),
  };
  if (existingIdx >= 0) {
    // replace-on-same-displayId per frontend-protocol.md §4.4
    const items = state.activity.items.slice();
    items[existingIdx] = newItem;
    return { ...state, activity: { ...state.activity, items } };
  }
  return {
    ...state,
    activity: {
      ...state.activity,
      items: [...state.activity.items, newItem],
    },
  };
}

default: {
  // forward-compat: log once per type, return state unchanged
  warnUnknownEvent((event as { type?: string }).type);
  return state;
}
```

Helpers (`appendStreamChunk`, `updateTool`, `warnUnknownEvent`) are pure and
testable. `appendStreamChunk` keeps a per-stream `seq` cursor and inserts in
order, dropping duplicates — gap detection is still done one level up by
`streaming-channel-client.ts`, so this is purely defensive.

### 6.2 SESSION_HELLO is not a reducer event

`SESSION_HELLO` is connection-scoped, not turn-scoped. It does NOT go through
the reducer. Instead `streaming-channel-client.ts` adds:

```ts
private handleControl(env: Envelope) {
  if (env.op === 'session_hello') {
    useSessionStore.getState().setHello(env.payload as SessionHelloPayload);
    useConnectionStore.getState().setStatus('connected');
    return;
  }
  // existing ping/pong, ack handling
}
```

This keeps `StreamState` purely about the active turn and lets the rest of the
shell react to capability changes via Zustand selectors.

### 6.3 Type union extensions

```ts
// features/activity-stream/types.ts — additions

export type DisplayResultKind =
  | 'plotly'
  | 'matplotlib'
  | 'dataframe'
  | 'mesh'
  | 'image'
  | 'text'
  | 'interactive_pending'
  | 'interactive_done'
  | 'unknown';

export interface DisplayResultItem {
  kind: 'display_result';
  id: string;
  displayId: string;
  sourceToolId: string;
  resultKind: DisplayResultKind;
  data: unknown;
  receivedAt: number;
}

export type ActivityItem =
  | ThinkingItem
  | ContentItem
  | ToolItem
  | DisplayResultItem;   // new

export interface StreamChunk { seq: number; text: string; }
export interface ToolItem {
  // existing fields …
  stdout: StreamChunk[];   // new
  stderr: StreamChunk[];   // new
}
```

## 7. Mesh viewer integration

### 7.1 Decision: react-three-fiber + drei

`MeshView` uses `@react-three/fiber` (R3F) plus `@react-three/drei` for camera
controls, environment lighting, and a bbox helper. Direct three.js was
considered and rejected — R3F's React component model fits the rest of the
shell, and drei eliminates ~200 lines of OrbitControls / lighting boilerplate.

**Important:** the in-browser mesh viewer is for **passive visualization**
only — the user can rotate, zoom, toggle labels. Picking landmarks or running
interactive widgets happens in the **separate desktop PyVista window** that
the agent spawns via the interactive-tool protocol (§7 of
`frontend-protocol.md`). The browser does not try to reproduce PyVista's
picking widgets. Two reasons: (a) the browser's WebGL stack can't match
PyVista's volume rendering for μCT data, and (b) the agent already has the
PyVista subprocess as a first-class tool — duplicating it in the browser is
strictly worse and orthogonal to V0 goals.

### 7.2 Component

```tsx
// features/result-viewers/MeshView.tsx
export function MeshView({ item }: { item: DisplayResultItem }) {
  const { meshId, format, bbox } = item.data as MeshDescriptor;
  const blob = useMeshCacheStore((s) => s.byMeshId[meshId]);

  if (!blob) return <MeshLoadingPlaceholder meshId={meshId} />;

  return (
    <div className="h-96 w-full rounded-md border">
      <Canvas camera={{ position: cameraFromBbox(bbox), fov: 45 }}>
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 10, 5]} />
        <MeshFromBuffer bytes={blob.bytes} format={format} />
        <OrbitControls makeDefault />
      </Canvas>
    </div>
  );
}
```

`MeshFromBuffer` is a Suspense-friendly component that decodes the binary
format (`stl-bin`, `ply`, or `draco`) into a `BufferGeometry`. STL is the
default for V0 — the simplest path from `trimesh.export()` server-side.

### 7.3 Binary frame plumbing

`ws-client.ts:115` already parses `[subId]\0[meshId]\0[payload]` binary frames.
The agent-shell extension wires the parsed payload into `meshCacheStore`:

```ts
// streaming-channel-client.ts handleBinary extension
handleBinary(subId: string, meshId: string, bytes: Uint8Array) {
  const desc = pendingMeshDescriptors.get(`${subId}:${meshId}`);
  useMeshCacheStore.getState().set({
    meshId,
    format: desc?.format ?? 'stl-bin',
    bytes,
    bbox: desc?.bbox,
  });
}
```

`pendingMeshDescriptors` is populated when `DISPLAY_RESULT` of `resultKind:
"mesh"` arrives — exactly the ordering invariant from `frontend-protocol.md`
§3.2 ("backend MUST emit binary frames AFTER the `DISPLAY_RESULT` event that
references `meshId`"). If a binary frame arrives without a matching descriptor
(out-of-order edge case, §13), it's stashed in a small ring buffer keyed by
`meshId` and consumed when the descriptor lands.

## 8. Inline result renderers

Each renderer consumes a `DisplayResultItem` of a specific `resultKind`. The
dispatcher lives in `features/activity-stream/items/DisplayResultRow.tsx`:

```tsx
export function DisplayResultRow({ item }: { item: DisplayResultItem }) {
  switch (item.resultKind) {
    case 'plotly':              return <PlotlyView item={item} />;
    case 'matplotlib':          return <MatplotlibView item={item} />;
    case 'dataframe':           return <DataFrameView item={item} />;
    case 'mesh':                return <MeshView item={item} />;
    case 'image':               return <ImageView item={item} />;
    case 'text':                return <TextResultView item={item} />;
    case 'interactive_pending': return <InteractivePendingView item={item} />;
    case 'interactive_done':    return <InteractiveDoneView item={item} />;
    case 'unknown':
    default:                    return <UnknownResultView item={item} />;
  }
}
```

Renderer file layout:

```text
features/result-viewers/
├── DisplayResultRow.tsx      # the dispatcher
├── PlotlyView.tsx            # lazy-loads react-plotly.js
├── MatplotlibView.tsx        # base64 PNG <img>
├── DataFrameView.tsx         # virtualized table (TanStack Table)
├── MeshView.tsx              # R3F canvas (§7)
├── ImageView.tsx             # base64 or URL <img> with caption
├── TextResultView.tsx        # <pre> with syntax highlight when language set
├── InteractivePendingView.tsx# "Window open on your desktop" affordance
├── InteractiveDoneView.tsx   # completion summary card
└── UnknownResultView.tsx     # collapsed JSON viewer for forward-compat
```

`InteractivePendingView` reads `interactiveToolStore` for pulse animation and
elapsed time. It renders the affordance described in
`interactive-tool-protocol.md` (the "waiting for PyVista window" placeholder).

`ActivityBlock` integration: extend the existing item-rendering switch in
`ActivityBlock.tsx` to handle `kind === 'display_result'` by rendering
`<DisplayResultRow item={item} />`. No structural rewrite — one new branch in
the existing item map.

## 9. Copy strategy

**Decision: one-shot `cp -r` snapshot, single commit, no history preservation.**

Options considered:

| Option | Verdict |
|---|---|
| `git subtree add --prefix=frontend ../meridian-flow main --squash` | Rejected. Adds an upstream link the user explicitly does not want; future `meridian-flow` history would be available via `git subtree pull`, which encourages cross-repo coupling. Decision 1 says copy *into* this repo, not link. |
| `git subtree` without squash | Rejected for the same reason plus history pollution. |
| `cp -r ../meridian-flow/frontend-v2 frontend && git add` (one commit) | **Chosen.** Clean break from meridian-flow history. The snapshot is the new origin. If you want to know the prior history, the meridian-flow repo still exists. |
| Symlink | Rejected by Decision 5. |

**Procedure:**

1. `cp -r ../meridian-flow/frontend-v2 frontend` from the repo root.
2. `cd frontend && rm -rf node_modules dist .git .turbo`.
3. Apply the cut list from §1 and §2 in a follow-up commit (delete
   `features/docs/`, `editor/collab/`, `editor/persistence/`, `editor/session/`,
   `editor/transport/`, `lib/ws/doc-stream-client.ts`, the Yjs deps from
   `package.json`).
4. `pnpm install` to regenerate the lockfile against the trimmed deps.
5. Single commit: `feat(frontend): copy frontend-v2 into shell`.
6. Follow-up commits land the new shell layout, stores, API client, reducer
   extensions, and result viewers.

The legacy `../meridian-flow/frontend-v2` source is **not deleted** by this
work item — that's a separate cleanup once the amalgamation is validated
(see Q1 in `requirements.md`).

## 10. Dev workflow

Two terminals.

**Terminal 1 — backend:**
```bash
cd meridian-channel
uv sync --extra shell --extra biomedical
uv run meridian shell dev --backend-only
# → uvicorn on http://127.0.0.1:8765, WS on /ws
```

**Terminal 2 — frontend:**
```bash
cd meridian-channel/frontend
pnpm install
pnpm dev
# → vite on http://127.0.0.1:5173 with proxy to :8765
```

`vite.config.ts` gains a proxy block:

```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8765',
    '/ws':  { target: 'ws://127.0.0.1:8765', ws: true },
  },
},
```

Storybook is `pnpm storybook` in the frontend dir; it runs against mocks
(`use-thread-simulator`) and does not need the backend.

## 11. Build and bundle

```bash
cd frontend && pnpm build      # → frontend/dist/
```

`meridian shell start` (the production launch path, see
`repository-layout.md` §4) serves the prebuilt `frontend/dist/` bundle as
static assets via FastAPI's `StaticFiles`. If `frontend/dist/` is missing, the
shell errors with a clear message: *"Frontend bundle missing. Run
`(cd frontend && pnpm build)` or use `meridian shell dev`."* `pnpm` is a dev
tooling requirement, not a runtime dependency for Dad's V0 install path.

CI:
- Python job: `uv sync --extra dev`, `uv run pyright`, `uv run pytest-llm`,
  `uv run ruff check .`.
- Node job (only when files under `frontend/` change): `pnpm install --frozen-
  lockfile`, `pnpm typecheck`, `pnpm build`, `pnpm test`.

The two jobs are independent and parallelizable.

## 12. Theme and branding

frontend-v2 ships with Geist, Geist Mono, and iA Writer Quattro, light/dark
theme tokens in `index.css` via `@theme inline`, and a system-aware
`ThemeProvider`. **Keep all of it.** The agent shell does not need its own
brand identity for V0; the existing tokens are professional enough that
Dad won't notice he's using a "developer-flavored" UI. Re-branding is a V1+
concern after validation.

Single change: replace the placeholder app name in `TopBar.tsx` with the work
item title pulled from `sessionStore`.

## 13. Edge cases

| Case | Handling |
|---|---|
| **`pnpm` not installed when running `meridian shell start`** | The backend serves the prebuilt `frontend/dist/`. If missing, error with the explicit "run pnpm build or use shell dev" message above. `pnpm` is **not** a runtime requirement of the production shell — only a dev requirement. |
| **WS reconnect mid-turn** | `streaming-channel-client.ts` already handles this: on reconnect it re-subscribes by `subId`, the new `SESSION_HELLO` carries `lastSeqByTurn` (V1) or triggers `RESET` (V0), and the gap detector retries once before falling through to REST refetch. The user sees a brief "reconnecting…" toast and the activity stream resumes. |
| **Unknown event type from server** | Reducer `default` branch logs once per type via `warnUnknownEvent` (deduped by `type`) and returns state unchanged. Forward-compat for V1 events landing before V0 reducer code is updated. See `frontend-protocol.md` §6.2 — this is a *protocol-level requirement*, not just defensive coding. |
| **Binary frame arrives before `DISPLAY_RESULT`** | `streaming-channel-client.ts` stashes the bytes in a small ring buffer keyed by `meshId`. When the descriptor arrives, the cache is populated immediately. Buffer is bounded (last 4 meshes) so a misbehaving server can't OOM the tab. |
| **Binary frame arrives for a `meshId` no descriptor ever references** | After 5 seconds, the ring buffer evicts the orphan and logs a `warn`. No user-visible error. |
| **Multiple browser tabs open against the same shell** | V0 has one backend process and one session per work item. Multiple tabs share that session and receive the same event fan-out. If two tabs try to send while a turn is active, the second gets `agent_busy`; otherwise last command wins. |
| **Tab closes during a long tool call** | The WS closes; the backend keeps the harness running for the 30-second replay window. Reopening within that window replays buffered events; after it expires the server emits `SESSION_RESYNC`. |
| **Plotly bundle weight** | `PlotlyView` is `React.lazy`-loaded. First plot in a session pays a ~1 MB gz fetch; subsequent plots reuse the cached chunk. Acceptable cost for biomedical figures. |
| **Mesh too large for a single binary frame** | Out of scope for V0. The backend chunks meshes >50 MB into multiple `[subId]\0[meshId]\0[bytes]` frames keyed by the same `meshId` and a `partN` suffix in V1. V0 caps `show_mesh()` at 50 MB and errors otherwise. |
| **`DISPLAY_RESULT` with `resultKind: "interactive_pending"` never resolves** | The agent's interactive tool subprocess died without writing a result. The interactive-tool protocol (`interactive-tool-protocol.md`) defines a server-side timeout that emits a final `interactive_done` with `status: "error"`. The frontend just renders whatever the server sent — no client-side timeout watchdog. |
| **Storybook stories drift from prod components** | Acceptable risk. Stories are dev-only; the prod boundary is `pnpm build`'s glob exclusion. CI does not run Storybook builds — the next time someone opens Storybook locally and a story is broken, they fix it then. |

## 14. Open questions for downstream

These are smaller decisions deferred to implementation, not blockers for the
design:

- Whether to ship a `make codegen` target or wire Pydantic→TS into the
  Python build. Lean: `make codegen`, manual, committed output. Decided in
  the impl phase.
- Whether `MeshView`'s default format is `stl-bin` or `ply`. Both are simple
  to decode; STL is smaller for closed surfaces and PLY supports vertex
  colors. The biomedical pipeline produces both — the agent specifies
  `format` per emission, so V0 can support both renderers and let the agent
  pick.
- Whether the Sidebar's "Datasets" panel deserves its own stage in V0 or
  defers to V1. If the upload pipeline is V0 (per Q2), then yes; if upload
  is V1, then the sidebar is just a threads list in V0.

## 15. Verification checklist

Before shipping V0, verify each:

- [ ] `frontend/` exists; `frontend/src/features/docs/` does not.
- [ ] `frontend/src/editor/collab/`, `persistence/`, `session/`, `transport/`
  do not exist.
- [ ] `frontend/package.json` has no `yjs`, `y-*`, `dexie` deps.
- [ ] `frontend/src/features/activity-stream/streaming/reducer.ts` has cases
  for `TOOL_OUTPUT`, `DISPLAY_RESULT`, and `default`.
- [ ] `frontend/src/stores/` exists with `sessionStore`, `connectionStore`,
  `interactiveToolStore`, `meshCacheStore`, `uiStore`.
- [ ] `frontend/src/lib/wire-types.ts` exists and matches the backend wire
  schema on load-bearing fields.
- [ ] `App.tsx` renders `ShellLayout` (not just `ThemeProvider` + `Toaster`).
- [ ] `pnpm typecheck` passes; `pnpm build` produces `dist/`.
- [ ] `meridian shell dev` brings up backend + Vite proxy and the UI shows
  a `SESSION_HELLO`-driven TopBar.
- [ ] A python tool that calls `show_mesh()` renders a 3D mesh inline in the
  ActivityBlock without opening a separate window.
- [ ] An interactive `pick_points_on_mesh` tool call shows the
  `interactive_pending` placeholder and updates to `interactive_done` once
  the desktop PyVista window closes.
- [ ] Killing the backend mid-turn shows the reconnect toast; bringing it
  back resumes the UI without a hard reload.

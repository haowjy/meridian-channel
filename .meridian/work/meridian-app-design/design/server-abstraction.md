# Server Model Abstraction

## Goal

Enable future cloud-hosted version of Meridian App without rewriting the frontend.

## Current Model: Local-First (Jupyter-like)

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (localhost:7676)                                       │
│  └── React App                                                  │
│       └── API Client → http://localhost:7676/api/*              │
│                       → ws://localhost:7676/api/sessions/*/ws   │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Same-origin, no auth
          │
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Server (localhost:7676)                                │
│  ├── SessionRegistry (sessions.jsonl)                           │
│  ├── SpawnManager (subprocess spawning)                         │
│  ├── FileExplorer (filesystem access)                           │
│  └── RootRegistry (roots.jsonl)                                 │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Subprocess + filesystem
          │
┌─────────────────────────────────────────────────────────────────┐
│  Harness Processes                                              │
│  claude | codex | opencode                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Local assumptions deeply embedded:**
- Same-origin requests (no CORS, no auth)
- File paths as identifiers
- Direct subprocess spawning
- Filesystem-based file explorer
- User-level state in `~/.meridian/`

## Future Model: Cloud-Hosted

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (app.meridian.io)                                      │
│  └── React App                                                  │
│       └── API Client → https://api.meridian.io/v1/*             │
│                       → wss://api.meridian.io/v1/sessions/*/ws  │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Auth (JWT), multi-tenant
          │
┌─────────────────────────────────────────────────────────────────┐
│  Cloud Backend                                                  │
│  ├── Auth Service (user identity)                               │
│  ├── Session Service (postgres/dynamo)                          │
│  ├── Spawn Orchestrator (k8s/lambda)                            │
│  └── Storage Service (S3/GCS)                                   │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Orchestrated compute
          │
┌─────────────────────────────────────────────────────────────────┐
│  Harness Workers (containers)                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Cloud requirements:**
- Cross-origin auth (OAuth, JWT)
- User/org scoping for sessions and work items
- Remote file access (cloud storage or tunneled local)
- Orchestrated harness execution
- Server-side session state

## Abstraction Strategy

### API Client Layer

Frontend uses an `ApiClient` abstraction:

```typescript
interface ApiClient {
  // Sessions
  listSessions(filter?: SessionFilter): Promise<SessionSummary[]>
  getSession(sessionId: string): Promise<SessionDetail>
  createSession(config: SessionConfig): Promise<CreateSessionResponse>
  cancelSession(sessionId: string): Promise<void>
  
  // Work Items
  listWorkItems(): Promise<WorkItemSummary[]>
  getWorkItem(workId: string): Promise<WorkItemDetail>
  
  // File Explorer
  listRoots(): Promise<ExplorerRoot[]>
  listDirectory(path: string): Promise<DirectoryEntry[]>
  readFile(path: string): Promise<FileContent>
  
  // WebSocket
  connectSession(sessionId: string): SessionChannel
}
```

Two implementations:
1. `LocalApiClient` — current implementation, calls `localhost:7676`
2. `CloudApiClient` — future implementation, calls cloud API with auth

### Configuration

```typescript
interface AppConfig {
  apiBaseUrl: string
  wsBaseUrl: string
  authProvider?: AuthProvider
}

const localConfig: AppConfig = {
  apiBaseUrl: 'http://localhost:7676/api',
  wsBaseUrl: 'ws://localhost:7676/api',
  // No auth for local
}

const cloudConfig: AppConfig = {
  apiBaseUrl: 'https://api.meridian.io/v1',
  wsBaseUrl: 'wss://api.meridian.io/v1',
  authProvider: new OAuthProvider({ ... }),
}
```

### What Changes for Cloud

| Feature | Local | Cloud |
|---------|-------|-------|
| Auth | None | OAuth/JWT |
| Session addressing | session_id | org_id/session_id |
| File paths | Absolute local | Relative to workspace |
| File explorer | Direct filesystem | Tunneled or cloud storage |
| Work items | Per-machine | Per-org |
| Roots | Local dirs | Cloud workspaces or tunnels |

### What Stays the Same

- Session/work item data shapes (add fields, don't change existing)
- Event streaming protocol (AG-UI compatible)
- Composer UX
- Thread rendering
- Status indicators

## Implementation Notes

### Phase 1: Abstraction

1. Create `ApiClient` interface
2. Implement `LocalApiClient` wrapping current fetch calls
3. All components use `ApiClient` via context
4. No behavior change

### Phase 2: Cloud Backend (Future)

1. Implement cloud session/spawn services
2. Implement `CloudApiClient`
3. Add auth flow to frontend
4. File explorer requires separate design (tunneling vs cloud storage)

### Constraint: File Explorer

File explorer is the most local-bound feature:
- Current: direct filesystem traversal
- Cloud option A: tunnel to local machine (complexity, security)
- Cloud option B: cloud storage / git repos only (limited)
- Cloud option C: disable explorer in cloud mode

**Recommendation**: Document that file explorer may be local-only initially. Cloud sessions would work with file references passed in prompts rather than UI-driven attachment.

## API Shape Documentation

To enable future cloud implementation, document the API contract explicitly:

| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/sessions` | GET | `?work_id=&unattached=` | `SessionSummary[]` |
| `/sessions` | POST | `SessionConfig` | `CreateSessionResponse` |
| `/sessions/:id` | GET | - | `SessionDetail` |
| `/sessions/:id` | DELETE | - | `{ok: true}` |
| `/sessions/:id/ws` | WS | - | Event stream |
| `/work-items` | GET | - | `WorkItemSummary[]` |
| `/work-items/:id` | GET | - | `WorkItemDetail` |
| `/explorer/roots` | GET | - | `ExplorerRoot[]` |
| `/explorer/list` | GET | `?path=` | `DirectoryEntry[]` |
| `/explorer/read` | GET | `?path=` | `FileContent` |

See individual design docs for full request/response shapes.

## Decision

**Proceed with local-first, but architect for swappability:**

1. Use `ApiClient` abstraction from the start
2. Document API shapes explicitly
3. Avoid leaking file paths into component props (use abstract identifiers)
4. Accept that file explorer may be local-only in cloud version
5. Cloud backend design is a separate future work item
